"""
Item 10, Phase 1 (Round 85; the design of commit 5d39bf6, ratified unamended):
a Telegram command-and-control loop for the Penta-Desk ecosystem.

WHAT IT IS. One detached loop that long-polls Telegram (outbound HTTPS only - no
inbound port, no webhook on a laptop) and answers five commands from an
allowlist of admin user ids: /status, /bankroll, /positions, /halt (alias
/killall) and /help.

WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS. No token or no allowlist: it does not
start. A message from a group chat, from an unlisted user, or older than
STALE_UPDATE_SECONDS (a restart must never replay a /halt sent hours ago) is
logged and never answered. /resume is console-only. The only thing it can change
on the machine is the HALT.flag sentinel that HL_Monarch's dynamic config already
reads as the emergency kill switch; it never terminates a process - the data
daemons hold no risk and killing them breaks the stamped series.

THE NETWORK IS ONE INJECTABLE CALLABLE. `http(method, params) -> dict` is the
whole surface; tests pass a fake and never open a socket. The bot token is never
printed, logged or echoed: `redact` scrubs it from anything that could carry it,
and --status reports only "set" / "unset".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

from cross_market.ingestors import pid_lock

DEV_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = DEV_ROOT / "cross_market" / "data"
DEFAULT_PID_FILE = DATA_DIR / "c2_bot.pid"
DEFAULT_OFFSET_FILE = DATA_DIR / "c2_bot_offset.json"
DEFAULT_HALT_FLAG = DEV_ROOT / "HALT.flag"          # dynamic_config.is_halt_flag_present() reads exactly this path
DEFAULT_COLLECTOR_STATUS = DEV_ROOT / "HyperLiquid" / "HL_Monarch" / "data" / "collector_status.json"
DEFAULT_PAPER_STATE = DEV_ROOT / "HyperLiquid" / "HL_Monarch" / "data" / "basis_paper_state.json"

C2_MARK = "c2_bot"                                     # what the lock holder's command line must contain
TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
ADMINS_ENV = "C2_ADMIN_IDS"
STALE_UPDATE_SECONDS = 120.0
MAX_REPLY_CHARS = 4000                                 # Telegram's limit is 4,096; leave headroom
HALT_CONFIRM = "CONFIRM"
STATUS_EXIT_STOPPED = 3
EXIT_REFUSED = 2
TELEGRAM_API = "https://api.telegram.org/bot%s/%s"

HELP_TEXT = "\n".join([
    "Penta-Desk C2 (Item 10, Phase 1) - commands:",
    "  /status     supervisor, collector, watcher, exporter, Item 18 gate, memory",
    "  /bankroll   safe deployable bankroll, tax escrow, after-tax arbitrage hurdle",
    "  /positions  open basis positions and recorded sports bets (PAPER)",
    "  /halt       two-step: /halt shows what it does, /halt CONFIRM [reason] engages HALT.flag",
    "  /killall    alias of /halt",
    "  /help       this list",
    "/resume is console-only: delete HALT.flag at the machine.",
])

ROLE_MARKS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("supervisor", ("run_collector_service.py",)),
    ("collector", ("main.py", "collector")),
    ("watcher", ("polymarket_fetcher", "--watch")),
    ("exporter", ("cross_market.interfaces.obsidian_exporter", "--watch")),
    ("c2 bot", ("c2_bot",)),
)


# ------------------------------------------------------------------ settings

def _registry_user_env(name: str) -> Optional[str]:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        value, _ = winreg.QueryValueEx(key, name)
    return value


def user_env(name: str, environ=None, registry=None) -> Optional[str]:
    """os.environ first, then the user-level registry value (a long-lived process sees neither refresh). Never raises."""
    environ = os.environ if environ is None else environ
    value = environ.get(name)
    if value:
        return str(value).strip() or None
    try:
        value = (registry or _registry_user_env)(name)
    except Exception:                                       # noqa: BLE001 - missing key, no registry, anything
        return None
    value = str(value).strip() if value is not None else ""
    return value or None


def parse_admin_ids(raw: Optional[str]) -> FrozenSet[int]:
    """Comma / space / semicolon separated Telegram user ids; anything that is not an integer is ignored."""
    out = set()
    for part in re.split(r"[,\s;]+", str(raw or "")):
        part = part.strip()
        if part and part.lstrip("-").isdigit():
            out.add(int(part))
    return frozenset(out)


def redact(text: Any, token: Optional[str]) -> str:
    text = "" if text is None else str(text)
    return text.replace(token, "<token>") if token else text


@dataclass
class Settings:
    token: Optional[str]
    admins: FrozenSet[int]
    stale_seconds: float = STALE_UPDATE_SECONDS

    @classmethod
    def from_env(cls, environ=None, registry=None) -> "Settings":
        return cls(token=user_env(TOKEN_ENV, environ, registry),
                   admins=parse_admin_ids(user_env(ADMINS_ENV, environ, registry)))

    def refusal(self) -> Optional[str]:
        """Why the loop must not start; None when it may."""
        if not self.token:
            return "no %s - refusing to start (fail-closed)" % TOKEN_ENV
        if not self.admins:
            return "%s is empty - every message would be rejected; refusing to start (fail-closed)" % ADMINS_ENV
        return None


# ------------------------------------------------------------------ inbound + authorization

@dataclass
class Inbound:
    update_id: int
    chat_id: int
    chat_type: str
    user_id: Optional[int]
    username: str
    text: str
    sent_at: Optional[int]                              # unix seconds, Telegram's `date`


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def parse_update(update: Any) -> Optional[Inbound]:
    """A text message with a chat and an update id; edited messages, channel posts and callbacks are None."""
    if not isinstance(update, dict):
        return None
    update_id = _as_int(update.get("update_id"))
    message = update.get("message")
    if update_id is None or not isinstance(message, dict):
        return None
    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    sender = message.get("from") if isinstance(message.get("from"), dict) else {}
    chat_id = _as_int(chat.get("id"))
    if chat_id is None:
        return None
    return Inbound(update_id=update_id, chat_id=chat_id, chat_type=str(chat.get("type") or ""),
                   user_id=_as_int(sender.get("id")), username=str(sender.get("username") or ""),
                   text=text.strip(), sent_at=_as_int(message.get("date")))


def authorize(inbound: Inbound, settings: Settings, now_ts: float) -> Tuple[bool, str]:
    """Fail-closed: every reason to refuse is checked before the one reason to accept."""
    if not settings.admins:
        return False, "no allowlist configured"
    if inbound.chat_type != "private":
        return False, "not a private chat (%s)" % (inbound.chat_type or "unknown")
    if inbound.user_id is None or inbound.user_id not in settings.admins:
        return False, "sender %s not allowlisted" % (inbound.user_id if inbound.user_id is not None else "unknown")
    if inbound.sent_at is None:
        return False, "no timestamp"
    age = float(now_ts) - float(inbound.sent_at)
    if age > settings.stale_seconds:
        return False, "stale update (age %.0fs > %.0fs)" % (age, settings.stale_seconds)
    return True, "ok"


# ------------------------------------------------------------------ readers (every live source, injectable)

def default_processes() -> List[Dict[str, Any]]:
    """The ecosystem's Python processes by role, with resident memory. psutil only; never raises."""
    import psutil
    out: List[Dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time", "memory_info"]):
        info = proc.info
        name = (info.get("name") or "").lower()
        if not name.startswith("python"):
            continue
        cmdline = " ".join(info.get("cmdline") or [])
        for role, marks in ROLE_MARKS:
            if all(mark in cmdline for mark in marks):
                mem = info.get("memory_info")
                out.append({"role": role, "pid": info["pid"],
                            "rss_mb": round(mem.rss / 1_048_576.0, 1) if mem else None,
                            "started": datetime.fromtimestamp(info["create_time"], timezone.utc).isoformat()
                            if info.get("create_time") else None})
                break
    return out


def default_collector_status(path: Path = DEFAULT_COLLECTOR_STATUS) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        return None
    checked = data.get("checked_at")
    if isinstance(checked, (int, float)):
        data["age_s"] = round(time.time() - float(checked), 1)
    return data


def default_watcher_status() -> Dict[str, Any]:
    from cross_market.ingestors.polymarket_fetcher import watcher_status
    return watcher_status()


def default_exporter_status() -> Dict[str, Any]:
    from cross_market.interfaces.obsidian_exporter import exporter_status
    return exporter_status()


def default_bankroll() -> Dict[str, Any]:
    from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
    hook = get_hook()
    return {"safe": float(hook.get_safe_bankroll()), "escrow": float(hook.get_tax_escrow()),
            "hurdle": float(hook.after_tax_arbitrage_hurdle()), "line": str(hook.status_line())}


def default_paper_state(path: Path = DEFAULT_PAPER_STATE) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        return None


def default_placed_bets() -> List[Dict[str, Any]]:
    from Sports_Desk.data.db import query_placed_bets
    return query_placed_bets()


@dataclass
class Readers:
    processes: Callable[[], List[Dict[str, Any]]] = default_processes
    collector_status: Callable[[], Optional[Dict[str, Any]]] = default_collector_status
    watcher_status: Callable[[], Dict[str, Any]] = default_watcher_status
    exporter_status: Callable[[], Dict[str, Any]] = default_exporter_status
    bankroll: Callable[[], Dict[str, Any]] = default_bankroll
    paper_state: Callable[[], Optional[Dict[str, Any]]] = default_paper_state
    placed_bets: Callable[[], List[Dict[str, Any]]] = default_placed_bets


@dataclass
class Context:
    readers: Readers
    halt_path: Path
    now: datetime
    actor: str = "console"


def _read(label: str, fn: Callable[[], Any]) -> Tuple[Any, Optional[str]]:
    try:
        return fn(), None
    except Exception as exc:                                # noqa: BLE001 - one dead source must not kill the reply
        return None, "%s unavailable: %s: %s" % (label, type(exc).__name__, exc)


def _money(value: Any) -> str:
    try:
        return "$%s" % format(float(value), ",.2f")
    except (TypeError, ValueError):
        return "n/a"


# ------------------------------------------------------------------ commands (pure: readers in, text out)

def halt_meta(path: Path) -> Optional[Dict[str, Any]]:
    """The JSON the bot wrote into HALT.flag, {} for a flag written by hand, None when absent."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:                                       # noqa: BLE001
        return {}


def cmd_status(ctx: Context) -> str:
    lines = ["STATUS at %s" % ctx.now.strftime("%Y-%m-%d %H:%M:%SZ")]
    procs, err = _read("processes", ctx.readers.processes)
    if err:
        lines.append("  " + err)
    else:
        by_role: Dict[str, List[Dict[str, Any]]] = {}
        for p in procs or []:
            by_role.setdefault(p["role"], []).append(p)
        for role, _marks in ROLE_MARKS:
            found = by_role.get(role) or []
            if not found:
                lines.append("  %-10s NOT RUNNING" % (role + ":"))
                continue
            lines.append("  %-10s %s" % (role + ":", "; ".join(
                "pid %s, %s MB" % (p["pid"], p["rss_mb"] if p["rss_mb"] is not None else "?") for p in found)))
    status, err = _read("collector status", ctx.readers.collector_status)
    if err:
        lines.append("  " + err)
    elif status is None:
        lines.append("  collector status file: missing")
    else:
        age = status.get("age_s")
        lines.append("  collector status: pid %s, %d dex(es), written %s" % (
            status.get("pid"), len(status.get("dexes_listed") or []),
            ("%.0fs ago" % age) if isinstance(age, (int, float)) else "at unknown time"))
    watcher, err = _read("watcher", ctx.readers.watcher_status)
    if err:
        lines.append("  " + err)
    else:
        age = watcher.get("newest_macro_age_s")
        tags = watcher.get("newest_macro_tags")
        lines.append("  watcher: %s; macro stamp %s; tags %s" % (
            ("RUNNING pid %s" % watcher.get("holder_pid")) if watcher.get("running") else "STOPPED",
            ("%.1f min old" % (age / 60.0)) if isinstance(age, (int, float)) else "none",
            "yes" if tags else ("no" if tags is False else "n/a")))
    exporter, err = _read("exporter", ctx.readers.exporter_status)
    if err:
        lines.append("  " + err)
    else:
        if exporter.get("lead_lag_ready"):
            series = "READY (%s pts, %.1fh)" % (exporter.get("lead_lag_points"), exporter.get("lead_lag_span_hours") or 0.0)
        else:
            series = "NOT READY - %s" % "; ".join(exporter.get("lead_lag_reasons") or ["no data"])
        lines.append("  exporter: %s" % (("RUNNING pid %s" % exporter.get("holder_pid")) if exporter.get("running") else "STOPPED"))
        lines.append("  Item 18: last run %s; macro series %s" % (exporter.get("lead_lag_last_run") or "never", series))
        if exporter.get("lead_lag_eta") and not exporter.get("lead_lag_ready"):
            lines.append("  Item 18 ETA: %s" % exporter["lead_lag_eta"])
    meta = halt_meta(ctx.halt_path)
    if meta is None:
        lines.append("  HALT.flag: absent (execution guard ARMED / normal)")
    else:
        lines.append("  HALT.flag: PRESENT since %s by %s - execution HALTED" % (meta.get("when", "?"), meta.get("who", "?")))
    return "\n".join(lines)


def cmd_bankroll(ctx: Context) -> str:
    data, err = _read("Tax Reserve Agent", ctx.readers.bankroll)
    if err:
        return "BANKROLL\n  " + err
    return "\n".join([
        "BANKROLL (Tax Reserve Agent)",
        "  safe deployable:   %s" % _money(data.get("safe")),
        "  tax escrow:        %s" % _money(data.get("escrow")),
        "  after-tax arbitrage hurdle: %.2f%%" % (float(data.get("hurdle") or 0.0) * 100.0),
        "  %s" % (data.get("line") or ""),
    ])


def cmd_positions(ctx: Context) -> str:
    lines = ["POSITIONS - PAPER (basis_paper_state.json)"]
    state, err = _read("paper state", ctx.readers.paper_state)
    if err:
        lines.append("  " + err)
    elif state is None:
        lines.append("  paper state file: missing")
    else:
        positions = state.get("positions") or {}
        lines.append("  cash %s · %d open · funding collected %s · realized %s · saved %s" % (
            _money(state.get("cash")), len(positions), _money(state.get("funding_collected")),
            _money(state.get("realized_pnl")), state.get("saved_at") or "?"))
        for key, pos in sorted(positions.items()):
            if not isinstance(pos, dict):
                continue
            lines.append("  - %s: capital %s, entry APR %.1f%%, accrued %s, held %.1f h" % (
                pos.get("coin") or key, _money(pos.get("capital")), float(pos.get("entry_funding_apr") or 0.0) * 100.0,
                _money(pos.get("funding_accrued")), float(pos.get("hours_held") or 0.0)))
    bets, err = _read("placed bets", ctx.readers.placed_bets)
    if err:
        lines.append("SPORTS BETS\n  " + err)
    else:
        bets = bets or []
        lines.append("SPORTS BETS (placed_bets: %d recorded, newest %d) - PAPER unless the desk says otherwise"
                     % (len(bets), min(10, len(bets))))
        for bet in bets[:10]:
            lines.append("  - %s %s @ %.2f stake %s %s %s" % (
                str(bet.get("placed_at") or "?")[:16], bet.get("selection") or "?", float(bet.get("decimal_odds") or 0.0),
                _money(bet.get("stake")), bet.get("book") or "", bet.get("bet_kind") or ""))
        if not bets:
            lines.append("  none recorded")
    return "\n".join(lines)


def cmd_halt(ctx: Context, args: str) -> str:
    """Two-step. Creates ONLY the sentinel; never touches a process. /resume is console-only."""
    path = Path(ctx.halt_path)
    meta = halt_meta(path)
    if meta is not None:
        return ("HALT already ENGAGED since %s by %s (%s). Nothing changed.\n/resume is console-only: delete %s at the machine."
                % (meta.get("when", "?"), meta.get("who", "?"), meta.get("reason", "no reason recorded"), path))
    words = args.split()
    if not words or words[0] != HALT_CONFIRM:
        return "\n".join([
            "This creates %s." % path,
            "Effect: HL_Monarch's dynamic config reads it as emergency_killswitch; the supervisor stops arming and",
            "rests no new orders on its next config read. Nothing is live today (basis is paper, fade and sweep",
            "are disabled). The data daemons (collector, watcher, exporter) keep running - they are never killed.",
            "To proceed send:  /halt %s [reason]" % HALT_CONFIRM,
        ])
    reason = " ".join(words[1:]).strip() or "telegram /halt"
    payload = {"who": ctx.actor, "when": ctx.now.isoformat(), "reason": reason, "source": "c2_bot"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return "\n".join([
        "HALT ENGAGED at %s by %s (%s)." % (payload["when"], ctx.actor, reason),
        "Wrote %s." % path,
        "Supervisor arming stops on its next config read. Data daemons untouched (collector, watcher, exporter).",
        "/resume is console-only: delete the file at the machine.",
    ])


def cmd_resume(ctx: Context) -> str:
    present = halt_meta(ctx.halt_path) is not None
    return ("Console-only: delete %s at the machine. The flag is currently %s."
            % (ctx.halt_path, "PRESENT" if present else "absent"))


def dispatch(text: str, ctx: Context) -> Optional[str]:
    """The reply for a command, or None for anything that is not one (ignored, never answered)."""
    stripped = (text or "").strip()
    if not stripped.startswith("/"):
        return None
    head, _, rest = stripped.partition(" ")
    command = head.split("@", 1)[0].lower()           # "/status@MyBot" in some clients
    if command in ("/status",):
        return cmd_status(ctx)
    if command == "/bankroll":
        return cmd_bankroll(ctx)
    if command == "/positions":
        return cmd_positions(ctx)
    if command in ("/halt", "/killall"):
        return cmd_halt(ctx, rest)
    if command == "/resume":
        return cmd_resume(ctx)
    if command in ("/help", "/start"):
        return HELP_TEXT
    return "Unknown command %s. /help lists the commands." % command


def chunk(text: str, limit: int = MAX_REPLY_CHARS) -> List[str]:
    """Split on line boundaries into pieces of at most `limit` characters; an over-long line is cut hard."""
    pieces: List[str] = []
    current = ""
    for line in (text or "").split("\n"):
        while len(line) > limit:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(line[:limit])
            line = line[limit:]
        candidate = line if not current else current + "\n" + line
        if len(candidate) > limit:
            pieces.append(current)
            current = line
        else:
            current = candidate
    if current or not pieces:
        pieces.append(current)
    return pieces


# ------------------------------------------------------------------ offset persistence (each update handled at most once)

def load_offset(path: Path) -> Optional[int]:
    try:
        return _as_int(json.loads(Path(path).read_text(encoding="utf-8")).get("next_update_id"))
    except Exception:                                       # noqa: BLE001
        return None


def save_offset(path: Path, next_update_id: int) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps({"next_update_id": int(next_update_id), "saved_at": _now().isoformat()}), encoding="utf-8")
    os.replace(tmp, p)


# ------------------------------------------------------------------ transport

class TelegramTransport:
    """Two Bot API calls behind one injectable `http(method, params) -> dict`. Never raises."""

    def __init__(self, token: str, http: Optional[Callable[[str, Dict[str, Any]], Any]] = None, timeout: float = 35.0):
        self.token = token
        self.http = http
        self.timeout = float(timeout)
        self.errors = 0
        self.last_error: Optional[str] = None

    def url(self, method: str) -> str:
        return TELEGRAM_API % (self.token, method)

    def _urllib(self, method: str, params: Dict[str, Any]) -> Any:
        import urllib.request
        body = json.dumps(params).encode("utf-8")
        request = urllib.request.Request(self.url(method), data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def call(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            result = (self.http or self._urllib)(method, params)
        except Exception as exc:                            # noqa: BLE001 - the loop must survive any transport failure
            self.errors += 1
            self.last_error = redact("%s: %s" % (type(exc).__name__, exc), self.token)
            return None
        return result if isinstance(result, dict) else None

    def get_updates(self, offset: Optional[int], timeout_s: float) -> Optional[List[Dict[str, Any]]]:
        params: Dict[str, Any] = {"timeout": max(0, int(timeout_s)), "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = int(offset)
        result = self.call("getUpdates", params)
        if not result or not result.get("ok"):
            return None
        return [u for u in (result.get("result") or []) if isinstance(u, dict)]

    def send(self, chat_id: int, text: str) -> bool:
        result = self.call("sendMessage", {"chat_id": int(chat_id), "text": text, "disable_web_page_preview": True})
        return bool(result and result.get("ok"))


# ------------------------------------------------------------------ the loop

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def process_updates(updates: Sequence[Dict[str, Any]], settings: Settings, readers: Readers, transport: TelegramTransport,
                    offset_path: Path, halt_path: Path, now: datetime, log: Callable[[str], None],
                    dry_run: bool = False) -> Dict[str, Any]:
    """
    Every update is acknowledged (offset saved) BEFORE it is acted on, so a crash
    mid-command can never replay a /halt. Rejections are logged, never answered.
    """
    stats: Dict[str, Any] = {"handled": 0, "rejected": 0, "ignored": 0, "sent": 0, "send_failed": 0, "next_update_id": None}
    for raw in updates:
        update_id = _as_int(raw.get("update_id")) if isinstance(raw, dict) else None
        if update_id is not None:
            stats["next_update_id"] = update_id + 1
            save_offset(offset_path, update_id + 1)
        inbound = parse_update(raw)
        if inbound is None:
            stats["ignored"] += 1
            continue
        ok, reason = authorize(inbound, settings, now.timestamp())
        if not ok:
            stats["rejected"] += 1
            log("[C2] rejected update %d from user %s in chat %s (%s): %s"
                % (inbound.update_id, inbound.user_id, inbound.chat_id, inbound.chat_type or "?", reason))
            continue
        actor = "%s(%s)" % (inbound.username or "user", inbound.user_id)
        reply = dispatch(inbound.text, Context(readers=readers, halt_path=halt_path, now=now, actor=actor))
        if reply is None:
            stats["ignored"] += 1
            continue
        stats["handled"] += 1
        for piece in chunk(reply):
            if dry_run:
                log("[C2] dry-run reply to chat %s:\n%s" % (inbound.chat_id, piece))
                stats["sent"] += 1
            elif transport.send(inbound.chat_id, piece):
                stats["sent"] += 1
            else:
                stats["send_failed"] += 1
        log("[C2] %s from %s -> %d char(s)%s" % (inbound.text.split()[0], actor, len(reply),
                                                  "" if not stats["send_failed"] else " (send FAILED)"))
    return stats


def run_loop(settings: Settings, readers: Readers, transport: TelegramTransport, offset_path: Path, halt_path: Path,
             interval: float = 5.0, max_polls: Optional[int] = None, log: Callable[[str], None] = print,
             dry_run: bool = False, sleep: Optional[Callable[[float], None]] = None,
             clock: Optional[Callable[[], datetime]] = None) -> Dict[str, int]:
    """Long-poll Telegram for `interval` seconds per request; a transport error waits one interval and retries."""
    pause = sleep or _sleep
    tick = clock or _now
    offset = load_offset(offset_path)
    totals: Dict[str, int] = {"polls": 0, "handled": 0, "rejected": 0, "ignored": 0, "sent": 0, "send_failed": 0, "errors": 0}
    while max_polls is None or totals["polls"] < max_polls:
        totals["polls"] += 1
        updates = transport.get_updates(offset, timeout_s=interval)
        if updates is None:
            totals["errors"] += 1
            log("[C2] poll %d: transport error (%s) - retrying in %gs" % (totals["polls"], transport.last_error or "no detail", interval))
            pause(interval)
            continue
        if not updates:
            pause(min(interval, 1.0))
            continue
        stats = process_updates(updates, settings, readers, transport, offset_path, halt_path, tick(), log, dry_run=dry_run)
        if stats["next_update_id"] is not None:
            offset = stats["next_update_id"]
        for key in ("handled", "rejected", "ignored", "sent", "send_failed"):
            totals[key] += stats[key]
    return totals


# ------------------------------------------------------------------ operator status (read-only, never the token)

def bot_status(pid_file=None, offset_path=None, halt_path=None, settings: Optional[Settings] = None,
               now: Optional[datetime] = None, probe=None, alive=None) -> Dict[str, Any]:
    lock = Path(pid_file or DEFAULT_PID_FILE)
    now = now or _now()
    holder = pid_lock.read_pid_file(lock)
    running = holder is not None and not pid_lock.is_stale(lock, probe=probe, mark=C2_MARK, alive=alive)
    info: Dict[str, Any] = {
        "running": running, "holder_pid": holder if running else None, "pid_file": str(lock),
        "stale_pid_file": bool(lock.exists() and not running), "holder_started": None, "holder_cmdline": None,
        "checked_at": now.isoformat(),
        "token_set": bool(settings and settings.token), "admins": len(settings.admins) if settings else 0,
        "stale_seconds": settings.stale_seconds if settings else STALE_UPDATE_SECONDS,
        "next_update_id": load_offset(Path(offset_path or DEFAULT_OFFSET_FILE)),
        "halt_flag": str(Path(halt_path or DEFAULT_HALT_FLAG)),
        "halt_meta": halt_meta(Path(halt_path or DEFAULT_HALT_FLAG)),
    }
    if running:
        try:
            import psutil
            proc = psutil.Process(holder)
            info["holder_started"] = datetime.fromtimestamp(proc.create_time(), timezone.utc).isoformat()
            info["holder_cmdline"] = redact(" ".join(proc.cmdline()), settings.token if settings else None)
        except Exception:                                   # noqa: BLE001
            pass
    return info


def format_bot_status(info: Dict[str, Any]) -> str:
    lines = []
    if info["running"]:
        started = (" started %s" % info["holder_started"]) if info.get("holder_started") else ""
        lines.append("[STATUS] c2 bot RUNNING - pid %s%s holds %s" % (info["holder_pid"], started, info["pid_file"]))
        if info.get("holder_cmdline"):
            lines.append("[STATUS]   command: %s" % info["holder_cmdline"])
    elif info.get("stale_pid_file"):
        lines.append("[STATUS] c2 bot STOPPED - stale lock %s (swept at the next start)" % info["pid_file"])
    else:
        lines.append("[STATUS] c2 bot STOPPED - no lock at %s" % info["pid_file"])
    lines.append("[STATUS] token: %s · admins allowlisted: %d · stale window: %gs · next update id: %s"
                 % ("set" if info.get("token_set") else "unset", info.get("admins", 0), info.get("stale_seconds", 0),
                    info.get("next_update_id") if info.get("next_update_id") is not None else "none yet"))
    meta = info.get("halt_meta")
    if meta is None:
        lines.append("[STATUS] HALT.flag absent at %s" % info.get("halt_flag"))
    else:
        lines.append("[STATUS] HALT.flag PRESENT at %s since %s by %s" % (info.get("halt_flag"), meta.get("when", "?"), meta.get("who", "?")))
    return "\n".join(lines)


# ------------------------------------------------------------------ CLI

def main(argv: Optional[List[str]] = None, environ=None, registry=None, http=None,
         readers: Optional[Readers] = None) -> int:
    parser = argparse.ArgumentParser(description="Penta-Desk Telegram C2 bot (Item 10, Phase 1)")
    parser.add_argument("--status", action="store_true", help="lock holder, token set/unset, allowlist size, offset, HALT.flag; exit 0 running / %d stopped" % STATUS_EXIT_STOPPED)
    parser.add_argument("--json", action="store_true", help="with --status: JSON instead of lines")
    parser.add_argument("--once", action="store_true", help="one poll (of --interval seconds) then exit")
    parser.add_argument("--dry-run", action="store_true", help="answer into the log instead of Telegram")
    parser.add_argument("--interval", type=float, default=5.0, help="long-poll seconds per request (default 5)")
    parser.add_argument("--max-polls", type=int, default=None)
    parser.add_argument("--stale-seconds", type=float, default=STALE_UPDATE_SECONDS,
                        help="drop updates older than this (default %.0f) - a restart never replays an old /halt" % STALE_UPDATE_SECONDS)
    parser.add_argument("--log-file", type=Path, default=None, help="append every line to this file as well (the only output under pythonw)")
    parser.add_argument("--pid-file", type=Path, default=None, help="single-instance lock (default %s)" % DEFAULT_PID_FILE)
    parser.add_argument("--offset-file", type=Path, default=None)
    parser.add_argument("--halt-flag", type=Path, default=None, help="the sentinel /halt creates (default %s)" % DEFAULT_HALT_FLAG)
    args = parser.parse_args(argv)
    if args.log_file:
        from cross_market.console_log import tee_stdout
        tee_stdout(args.log_file)
    settings = Settings.from_env(environ, registry)
    settings.stale_seconds = float(args.stale_seconds)
    offset_path = Path(args.offset_file or DEFAULT_OFFSET_FILE)
    halt_path = Path(args.halt_flag or DEFAULT_HALT_FLAG)
    lock = Path(args.pid_file or DEFAULT_PID_FILE)

    def log(message: str) -> None:
        print(redact(message, settings.token))

    if args.status:
        info = bot_status(lock, offset_path, halt_path, settings)
        print(json.dumps(info, indent=2) if args.json else format_bot_status(info))
        return 0 if info["running"] else STATUS_EXIT_STOPPED
    refusal = settings.refusal()
    if refusal:
        log("[C2] " + refusal)
        return EXIT_REFUSED
    # One consumer per bot token: a second getUpdates client makes Telegram answer 409 to both.
    holder = pid_lock.acquire(lock, mark=C2_MARK)
    if holder is not None:
        who = "c2 bot pid %d" % holder if holder > 0 else "another starting bot"
        log("[LOCK] already_running: %s holds %s - this one exits" % (who, lock))
        return 0
    pid_lock.install_cleanup(lock)
    log("[LOCK] c2 bot pid %d -> %s" % (os.getpid(), lock))
    log("[C2] %d admin id(s) allowlisted, stale window %gs, halt flag %s, %s"
        % (len(settings.admins), settings.stale_seconds, halt_path, "DRY RUN" if args.dry_run else "live replies"))
    try:
        transport = TelegramTransport(settings.token or "", http=http)
        totals = run_loop(settings, readers or Readers(), transport, offset_path, halt_path, interval=args.interval,
                          max_polls=1 if args.once else args.max_polls, log=log, dry_run=args.dry_run)
        log("[C2] done: %s" % ", ".join("%s %d" % (k, v) for k, v in totals.items()))
    except KeyboardInterrupt:
        log("\n[STOP] c2 bot stopped.")
    finally:
        pid_lock.release(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
