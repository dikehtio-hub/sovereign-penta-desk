"""
Sports_Desk -> Obsidian. Writes `<vault>/Sports_Desk.md` every cycle.

What the note carries, and why each line is on it:

  ACTIVE +EV HOTLIST     what could be staked right now, already run through the
                         bankroll gate - so a row here is one the tax ledger has
                         approved a size for, not merely a price that looks good.
  REALISED P&L / ROI     the only line that can be spent. Everything else is a
                         leading indicator.
  AVERAGE EXECUTION CLV  did the prices taken beat the prices the market closed
                         at. Positive CLV with negative P&L means the sample is
                         small; the reverse is worse.
  OPEN EXPOSURE          stake at risk on unsettled events - the number the tax
                         ledger cannot see until the book's export is imported.
  UN-EXPORTED WARNING    a placed bet that has sat more than SYNC_ALERT_DAYS
                         without being handed to the tax drop folder. The escrow
                         is only as good as the import, and this is the line that
                         says the import is late.

The write is content-hashed with the timestamp lines stripped, so a cycle that
changed nothing touches nothing and Obsidian's file watcher stays quiet.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Sports_Desk.data.db import (DEFAULT_DB_PATH, _age_days, desk_performance,
                                 execution_clv, open_desk_exposure,
                                 query_placed_bets)
from Sports_Desk.interfaces.cli_hotlist import build_hotlist
from Sports_Desk.interfaces.monarch_shark import SYNC_ALERT_DAYS

SPORTS_DESK_NOTE = "Sports_Desk"
HUB_NOTE = "Monarch_Hub"
DEFAULT_VAULT_DIR = Path(__file__).resolve().parents[2] / "obsidian_vault"

_VOLATILE = (
    re.compile(r"^last_synced:.*$", re.MULTILINE),
    re.compile(r"^\s*>\s*-\s*\*\*Last (?:Updated|Synchronized|Refreshed)\*\*:.*$",
               re.MULTILINE),
)
# Round 68 (Ruling 67-3): elapsed ages tick every minute; a note that changed nothing but its
# clocks must not be rewritten. Each pattern replaces ONLY the age and keeps the verdict beside
# it, so [ACTIVE] -> [STALE], a new move, or a hit ageing out still changes the hash.
_VOLATILE_AGES = (
    (re.compile(r"(\*\*Feed Liveness\*\*: `)[0-9.]+[mh] ago(`)"), r"\1<VOLATILE_TIME>\2"),
    (re.compile(r"(newest quote )[0-9.]+ ?(?:m|h|min) ago"), r"\1<VOLATILE_TIME>"),
    (re.compile(r"(newest )[0-9.]+ min ago(, lookback)"), r"\1<VOLATILE_TIME>\2"),
    (re.compile(r"(, )[0-9]+s old\)"), r"\1<VOLATILE_TIME> old)"),
)


# ---------------------------------------------------------------------------
# Vault plumbing (shared with the cross-market exporter)
# ---------------------------------------------------------------------------

def resolve_vault(custom: Optional[str] = None) -> Path:
    """`--vault`, then $OBSIDIAN_VAULT_PATH, then the repo's own vault."""
    if custom:
        path = Path(custom).expanduser().resolve()
    elif os.environ.get("OBSIDIAN_VAULT_PATH"):
        path = Path(os.environ["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()
    else:
        path = DEFAULT_VAULT_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise(content: str) -> str:
    out = content
    for pattern in _VOLATILE:
        out = pattern.sub("", out)
    for pattern, replacement in _VOLATILE_AGES:
        out = pattern.sub(replacement, out)
    return "\n".join(line.rstrip() for line in out.splitlines()).strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(_normalise(content).encode("utf-8")).hexdigest()


def write_note_if_changed(path: Path, content: str) -> Tuple[Path, bool]:
    """Atomic write, skipped when only the timestamps differ."""
    path = Path(path)
    payload = content if content.endswith("\n") else content + "\n"
    if path.exists():
        try:
            if content_hash(path.read_text(encoding="utf-8")) == content_hash(payload):
                return path, False
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return path, True


def fmt_usd(value: float) -> str:
    sign = "-" if value < 0 else ""
    return "%s$%s" % (sign, format(abs(float(value)), ",.2f"))


def american(decimal_odds: float) -> str:
    if decimal_odds >= 2.0:
        return "+%d" % round((decimal_odds - 1.0) * 100.0)
    return "%d" % round(-100.0 / (decimal_odds - 1.0))


# ---------------------------------------------------------------------------
# Collecting the desk's state
# ---------------------------------------------------------------------------

def _naive_utc(moment: Optional[datetime]) -> datetime:
    """
    The desk's clock is NAIVE UTC, and `_age_days` subtracts a naive parse from it.

    A tz-aware `now` raises TypeError inside that subtraction, which `_age_days`
    swallows into None - so every bet reads as ageless and the un-exported
    warning never fires. Caught by the test that asked for the warning by name,
    not by inspection. Normalised once here so callers may pass either kind.
    """
    moment = moment or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def unexported_placed_bets(db_path: Path = DEFAULT_DB_PATH,
                           older_than_days: float = SYNC_ALERT_DAYS,
                           now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Placed bets never handed to the tax drop folder, older than the alert window.

    `exported_at` is the desk's own record of having written the bet into
    `Tax_Reserve_Agent/data/imports`. It is a narrower question than
    `unsynced_placed_bets` - which asks whether the LEDGER has the wager - and
    it is the one this note can answer without opening the ledger at all.
    """
    now = _naive_utc(now)
    stale: List[Dict[str, Any]] = []
    for bet in query_placed_bets(db_path=db_path):
        if bet.get("exported_at"):
            continue
        age = _age_days(bet.get("placed_at"), now)
        if age is None or age < older_than_days:
            continue
        record = dict(bet)
        record["age_days"] = age
        stale.append(record)
    stale.sort(key=lambda r: -(r["age_days"] or 0.0))
    return stale


def collect(hook: Any, db_path: Path = DEFAULT_DB_PATH,
            now: Optional[datetime] = None) -> Dict[str, Any]:
    """Everything the note needs, in one dict, with failures recorded not raised."""
    now = _naive_utc(now)
    snapshot: Dict[str, Any] = {"now": now, "db_path": str(db_path)}

    try:
        snapshot["performance"] = desk_performance(db_path=db_path)
    except Exception as exc:                                    # noqa: BLE001
        snapshot["performance"] = None
        snapshot["performance_error"] = "%s: %s" % (type(exc).__name__, exc)

    try:
        rows = execution_clv(db_path=db_path)
        measured = [r for r in rows if r.get("clv_prob_delta") is not None]
        snapshot["clv_measured"] = len(measured)
        snapshot["avg_clv"] = (sum(float(r["clv_prob_delta"]) for r in measured)
                               / len(measured)) if measured else None
        snapshot["beat_close"] = sum(1 for r in measured if r.get("beat_close"))
    except Exception as exc:                                    # noqa: BLE001
        snapshot["clv_measured"], snapshot["avg_clv"], snapshot["beat_close"] = 0, None, 0
        snapshot["clv_error"] = "%s: %s" % (type(exc).__name__, exc)

    try:
        snapshot["open_exposure"] = open_desk_exposure(db_path=db_path)
    except Exception as exc:                                    # noqa: BLE001
        snapshot["open_exposure"] = 0.0
        snapshot["exposure_error"] = "%s: %s" % (type(exc).__name__, exc)

    snapshot["stale_unexported"] = unexported_placed_bets(db_path, SYNC_ALERT_DAYS, now)

    # Round 66 (Ruling 65-4): the stale-quote scan, display only, with feed liveness.
    snapshot["stale"] = None
    snapshot["stale_error"] = ""
    try:
        from Sports_Desk.engine.stale_quotes import scan_market_db, scan_to_dict
        snapshot["stale"] = scan_to_dict(scan_market_db(db_path, now=now))
    except Exception as exc:                                # noqa: BLE001
        snapshot["stale_error"] = "%s: %s" % (type(exc).__name__, exc)

    # The hotlist runs every live edge through the bankroll gate, so it needs a
    # hook. A gated hook - empty ledger, no bankroll declared - approves nothing,
    # and the note says that in words rather than showing an empty table.
    snapshot["hotlist"] = []
    snapshot["hotlist_error"] = ""
    snapshot["hook_status"] = ""
    if hook is None:
        snapshot["hotlist_error"] = "no bankroll hook available"
    else:
        try:
            snapshot["hook_status"] = hook.status_line()
        except Exception as exc:                                # noqa: BLE001
            snapshot["hook_status"] = "[TAX] status unavailable (%s)" % exc
        try:
            snapshot["hotlist"] = build_hotlist(hook, db_path=db_path, now=now)
        except Exception as exc:                                # noqa: BLE001
            snapshot["hotlist_error"] = "%s: %s" % (type(exc).__name__, exc)
    return snapshot


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render(snapshot: Dict[str, Any], synced_at: str, vault_path: Path) -> str:
    perf = snapshot.get("performance") or {}
    stale = snapshot.get("stale_unexported") or []
    hotlist = snapshot.get("hotlist") or []
    lines: List[str] = []

    lines += ["---", "title: Sports Desk - Fair Value, Execution & Tax Bridge",
              "tags:", "  - monarch", "  - sports-desk", "  - execution-telemetry",
              "  - tax-bridge", 'last_synced: "%s"' % synced_at, "---", "",
              "# 🏈 Sports Desk - Fair Value, Execution & Tax Bridge", ""]

    if stale:
        lines += ["> [!WARNING] **%d placed bet(s) un-exported for more than %.0f days**"
                  % (len(stale), SYNC_ALERT_DAYS),
                  "> The tax ledger cannot reserve against a wager it has never seen. "
                  "Run `python -m Sports_Desk.interfaces.monarch_shark --export-to-tax-agent`.",
                  ">"]
        for bet in stale[:10]:
            lines.append("> - `%s` %s @ %s on **%s** - %s staked, %.1f days ago"
                         % (bet.get("event_id"), bet.get("selection"),
                            american(float(bet.get("decimal_odds") or 2.0)),
                            bet.get("book"), fmt_usd(float(bet.get("stake") or 0.0)),
                            float(bet.get("age_days") or 0.0)))
        lines.append("")

    lines += ["> [!INFO] **Desk Snapshot**",
              "> - **Realized P&L**: **`%s`**" % fmt_usd(float(perf.get("realized_pnl", 0.0) or 0.0)),
              "> - **ROI**: `%s`" % ("%.2f%%" % (perf["roi"] * 100.0)
                                     if perf.get("roi") is not None else "n/a"),
              "> - **Settled / Pending**: `%d` / `%d`"
              % (int(perf.get("bets_settled", 0) or 0), int(perf.get("bets_pending", 0) or 0)),
              "> - **Average Execution CLV**: `%s` over `%d` measured bet(s)"
              % ("%+.2f pts" % (snapshot["avg_clv"] * 100.0)
                 if snapshot.get("avg_clv") is not None else "n/a",
                 int(snapshot.get("clv_measured", 0))),
              "> - **Open Exposure**: **`%s`**" % fmt_usd(float(snapshot.get("open_exposure", 0.0))),
              feed_liveness_line(snapshot.get("stale")),
              "> - **Un-exported > %.0fd**: `%d`" % (SYNC_ALERT_DAYS, len(stale)),
              "> - **Bankroll Gate**: `%s`" % (snapshot.get("hook_status") or "n/a"),
              "> - **Last Synchronized**: `%s`" % synced_at, "",
              "> **Cockpit Navigation**: [[%s|👑 Master Hub]] • [[Cross_Market_Arb|⚖️ Cross-Market Arb]] "
              "• [[HyperLiquid_Monarch|🏛 HyperLiquid]] • [[Polymarket_Monarch|🌐 Polymarket]]" % HUB_NOTE,
              # Round 101 (F1, Ruling 98-2): the wiki Desk page and the command that reproduces this card.
              "> **Desk**: [[Desk_02_Sports_Desk|Desk 2: Sports Desk]] · "
              "Shell twin: `python -m Sports_Desk.interfaces.obsidian_exporter --once`",
              "", "---", "", "## 🎯 Active +EV Hotlist (bankroll-approved)", ""]

    if hotlist:
        lines += ["| Event | Market | Selection | Book | Odds | Edge | Approved | Hurdle |",
                  "| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: |"]
        for row in hotlist[:25]:
            odds = float(row.get("retail_offered_odds") or 0.0)
            hurdle = row.get("after_tax_hurdle")
            lines.append("| `%s` | %s%s | %s | %s | %s | `%+.2f%%` | **%s** | %s |" % (
                row.get("event_id"), row.get("market_type"),
                (" %s" % row["line"]) if row.get("line") else "",
                row.get("selection"), row.get("retail_book") or row.get("sportsbook") or "",
                american(odds) if odds > 1.0 else "n/a",
                float(row.get("gross_edge") or 0.0) * 100.0,
                fmt_usd(float(row.get("approved_notional") or 0.0)),
                ("%.2f%%" % (float(hurdle) * 100.0)) if hurdle is not None else "n/a"))
    elif snapshot.get("hotlist_error"):
        lines.append("_No hotlist: %s._" % snapshot["hotlist_error"])
    else:
        lines.append("_No live, unexpired, bankroll-approved edges right now._")

    lines += ["", "---", "", "## 📊 Realised Performance", ""]
    if perf and perf.get("bets_settled"):
        lines += ["| Metric | Value |", "| :--- | ---: |",
                  "| Turnover | `%s` |" % fmt_usd(float(perf.get("turnover", 0.0) or 0.0)),
                  "| Realized P&L | **`%s`** |" % fmt_usd(float(perf.get("realized_pnl", 0.0) or 0.0)),
                  "| ROI | `%s` |" % ("%.2f%%" % (perf["roi"] * 100.0) if perf.get("roi") is not None else "n/a"),
                  "| Win rate | `%s` |" % ("%.2f%%" % (perf["win_rate"] * 100.0)
                                          if perf.get("win_rate") is not None else "n/a"),
                  "| Model expected | `%s` |" % ("%.2f%%" % (perf["expected_win_rate"] * 100.0)
                                                if perf.get("expected_win_rate") is not None else "n/a"),
                  "| Decided / Pushes | `%d` / `%d` |" % (int(perf.get("bets_decided", 0) or 0),
                                                          int(perf.get("pushes", 0) or 0))]
    else:
        lines.append("_Nothing settled yet (%d bet(s) pending)._"
                     % int(perf.get("bets_pending", 0) or 0))

    lines += ["", "---", "", "## 📈 Execution CLV", "",
              "- Measured bets: `%d`" % int(snapshot.get("clv_measured", 0)),
              "- Beat the close: `%d`" % int(snapshot.get("beat_close", 0)),
              "- Average CLV: `%s`" % ("%+.2f pts" % (snapshot["avg_clv"] * 100.0)
                                       if snapshot.get("avg_clv") is not None else "n/a"),
              "", "> A positive CLV with a negative P&L means the prices were right and the",
              "> sample is small. The reverse means the opposite, and is worse.", ""]
    lines += render_stale_section(snapshot.get("stale"), snapshot.get("stale_error", ""))
    lines += ["",
              "---", "", "- Database: `%s`" % snapshot.get("db_path", ""),
              "- Vault: `%s`" % vault_path, "",
              "*Generated by `Sports_Desk.interfaces.obsidian_exporter`.*"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

STALE_SECTION_CAP = 8


def feed_liveness_line(stale: Optional[Dict[str, Any]]) -> str:
    """
    Round 67 (Directive 67-2): the snapshot header's one-line answer to "is the
    quote feed alive?": age of the newest quote in the table and a verdict -
    ACTIVE within FEED_STALE_SECONDS, STALE beyond it, NO QUOTES on an empty
    table, unavailable when the scan failed.
    """
    if not stale:
        return "> - **Feed Liveness**: `unavailable`"
    age = stale.get("newest_quote_age_seconds")
    if age is None:
        return "> - **Feed Liveness**: `none` [NO QUOTES]"
    limit = float((stale.get("thresholds") or {}).get("feed_stale_seconds") or 900)
    text = ("%.1fm ago" % (age / 60.0)) if age < 3600 else ("%.1fh ago" % (age / 3600.0))
    return "> - **Feed Liveness**: `%s` [%s]" % (text, "ACTIVE" if age <= limit else "STALE")


def render_stale_section(stale: Optional[Dict[str, Any]], error: str = "") -> List[str]:
    """
    Round 66 (Ruling 65-4): sharp-book moves and the retail quotes still priced
    off the old consensus, as a callout. Display only - the panel says so in the
    Shark and the note says so here. An empty result names the feed's newest
    quote age so a quiet market and a paused feed read differently.
    """
    lines = ["---", "", "## 🕒 Stale Quotes & Market Consensus Latency", ""]
    if not stale:
        lines.append("_Stale-quote scan unavailable%s._" % ((": " + error) if error else ""))
        return lines
    counts = stale.get("counts") or {}
    age = stale.get("newest_quote_age_seconds")
    newest = ("%.0fm ago" % (age / 60.0)) if age is not None else "none"
    lookback = int(stale.get("lookback_minutes") or 0)
    if stale.get("feed_warning"):
        # INFO, not WARNING: the note's WARNING callout is reserved for un-exported bets (a tax
        # matter); a quiet feed is context for reading the panel, not an action item.
        lines.append("> [!INFO] **Feed:** %s" % stale["feed_warning"])
        lines.append(">")
    if not stale.get("moves"):
        lines.append("> [!NOTE] No sharp moves detected in last %dm (newest quote %s)." % (lookback, newest))
        lines.append("> Display only. Sharp books: Pinnacle, Circa, Bookmaker, Betcris; a move is >= 2 pts at "
                     ">= 0.5 pt/min; a stale retail quote is >= 60 s behind it, <= 15 min old and >= 2 pts cheap.")
        return lines
    kind = "TIP" if stale.get("hits") else "NOTE"          # a stale quote is an opportunity to check, not a warning
    lines.append("> [!%s] **Sharp moves (last %dm): %d** · stale retail quotes: **%d** · newest quote %s"
                 % (kind, lookback, counts.get("moves", 0), counts.get("hits", 0), newest))
    moves, hits = stale.get("moves", []), stale.get("hits", [])
    for move in moves[:STALE_SECTION_CAP]:
        lines.append("> - `%s` %s %s **%s**: %s `%.3f -> %.3f` (%+.1f pts in %.1f min)"
                     % (move["book"], move["event_id"], move["market_type"], move["selection"], move["direction"],
                        move["from_odds"], move["to_odds"], move["delta_prob"] * 100, move["minutes"]))
    for hit in hits[:STALE_SECTION_CAP]:
        lines.append("> - 🐌 `%s` still `%.3f` on **%s**: edge `%+.1f pts` vs sharp `%.3f` (quoted %ds before the move ended, %ds old)"
                     % (hit["retail_book"], hit["retail_odds"], hit["selection"], hit["edge_prob"] * 100,
                        hit["sharp_to_odds"], int(hit["lag_seconds"]), int(hit["age_seconds"])))
    if len(moves) > STALE_SECTION_CAP or len(hits) > STALE_SECTION_CAP:      # Ruling 66-4: cap with an overflow notice
        lines.append("> *(and %d more sharp move(s) / %d more stale hit(s)... run `monarch_shark --stale` for the full list)*"
                     % (max(0, len(moves) - STALE_SECTION_CAP), max(0, len(hits) - STALE_SECTION_CAP)))
    lines.append("> Display only: a price to check at the book right now, not an order. Edges are before vig and tax "
                 "(overpriced %d, re-quoted %d, too old %d, thin edge %d)."
                 % (counts.get("overpriced", 0), counts.get("not_stale", 0), counts.get("too_old", 0),
                    counts.get("thin_edge", 0)))
    return lines


def default_hook() -> Any:
    """The process-wide bankroll hook, or None if the tax agent cannot start."""
    try:
        from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
        return get_hook()
    except Exception:                                           # noqa: BLE001
        return None


def export_sports_desk(vault: Optional[str] = None, hook: Any = None,
                       db_path: Path = DEFAULT_DB_PATH,
                       now: Optional[datetime] = None) -> Tuple[Path, bool]:
    vault_path = resolve_vault(vault)
    now = now or datetime.now(timezone.utc)
    synced_at = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    hook = hook if hook is not None else default_hook()
    snapshot = collect(hook, db_path=db_path, now=now)
    return write_note_if_changed(vault_path / ("%s.md" % SPORTS_DESK_NOTE),
                                 render(snapshot, synced_at, vault_path))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sports Desk -> Obsidian exporter")
    parser.add_argument("--vault", type=str, default=None, help="Obsidian vault path")
    parser.add_argument("--db", type=Path, default=None, help="sports_market.db path")
    parser.add_argument("--once", action="store_true", help="one export, then exit")
    parser.add_argument("--watch", action="store_true", help="export continuously")
    parser.add_argument("--interval", type=float, default=15.0, help="seconds between exports")
    args = parser.parse_args(argv)
    db_path = Path(args.db or DEFAULT_DB_PATH)

    if not args.watch:
        path, changed = export_sports_desk(args.vault, db_path=db_path)
        print("[OK] %s %s" % (path, "written" if changed else "unchanged"))
        return 0
    print("[SYNC] Sports Desk -> %s every %gs. Ctrl-C to stop." % (resolve_vault(args.vault),
                                                                      args.interval))
    try:
        while True:
            path, changed = export_sports_desk(args.vault, db_path=db_path)
            print("[%s] %s %s" % (datetime.now().strftime("%H:%M:%S"), path.name,
                                  "written" if changed else "unchanged"))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[STOP] Sports Desk exporter stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
