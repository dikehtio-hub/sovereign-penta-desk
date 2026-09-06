"""Pre-flight for the FOMC drill: every piece checked against every other, nothing written.

    python -m knowledge.drills.fomc_rehearsal [--event fomc-2026-09-16] [--now ISO]
                                               [--no-task] [--task-json FILE]

Round 113, Deliverable 4. The live drill on 2026-09-16 is five things that have to agree:

  1. the Event page       - release_utc and the T-2..T+5 window the pages freeze in
  2. the rules registration - a vault page compiled from cross_market/experiments/*.rules.json
  3. the drill card       - what the operator reads at T-2 (under 60 lines, whole token ids, no writes)
  4. the batch file       - what the scheduled task actually runs: three HARD-CODED token ids, a
                            duration, a books directory, a python path. It is git-ignored, so a fresh
                            clone has no drill at all; that is reported, not hidden.
  5. the scheduled task   - Monarch_FOMC_Drill: when it fires, what it runs, whether battery settings
                            or an interactive-only logon can stop it

Rounds 93b and 102/103 each found a piece that looked right and was not (a drill dated to the wrong
day; a --json flag documented for four rounds that never worked). This module exists so the next
such piece is found on the 13th, not at 13:58 on the 16th. Read-only: the vault is hashed before and
after and any difference is itself a FAIL. The Task Scheduler query is the ONE external tool, and it
is injectable (--task-json, or `task=` in run_checks) so the tests never touch the scheduler.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .. import DEV_ROOT, EXIT_FINDINGS, EXIT_OK, VAULT
from ..frontmatter import parse_iso8601
from ..query import MAX_LINES, books_dir, countdown, drill_card, find_event, rules_for

TASK_NAME = "Monarch_FOMC_Drill"
BAT = Path("cross_market") / "data" / "fomc_drill_2026-09-16.bat"      # git-ignored (.gitignore:137)
RECORDER = Path("cross_market") / "latency_sniper.py"
LEAD = timedelta(minutes=2)          # the task fires at T-2; the window opens at T-2
TAIL = timedelta(minutes=5)          # and closes at T+5
MIN_FREE_GB = 1.0
AC_STATES = {2, 3, 6, 7, 8, 9}       # Win32_Battery.BatteryStatus values meaning "mains present"
NEVER_RAN = 267011                   # SCHED_S_TASK_HAS_NOT_RUN

# Read by PowerShell via -EncodedCommand so no quoting survives the trip through argv. Probed live
# in Round 113 against the real task before being trusted.
PS_SCRIPT = r"""
$t = Get-ScheduledTask -TaskName '__TASK__' -ErrorAction Stop
$i = Get-ScheduledTaskInfo -TaskName '__TASK__'
$b = Get-CimInstance Win32_Battery | Select-Object -First 1
$d = Get-PSDrive -Name C
[pscustomobject]@{
  exists = $true; state = [string]$t.State; enabled = [bool]$t.Settings.Enabled
  triggers = @($t.Triggers | ForEach-Object { [string]$_.StartBoundary })
  actions = @($t.Actions | ForEach-Object { ([string]$_.Execute + ' ' + [string]$_.Arguments).Trim() })
  disallow_start_on_batteries = [bool]$t.Settings.DisallowStartIfOnBatteries
  stop_if_going_on_batteries = [bool]$t.Settings.StopIfGoingOnBatteries
  wake_to_run = [bool]$t.Settings.WakeToRun
  logon_type = [string]$t.Principal.LogonType
  next_run = [string]$i.NextRunTime; last_result = $i.LastTaskResult
  battery_status = $(if ($b) { [int]$b.BatteryStatus } else { $null })
  battery_pct = $(if ($b) { [int]$b.EstimatedChargeRemaining } else { $null })
  free_gb = [math]::Round($d.Free / 1GB, 1)
} | ConvertTo-Json -Compress
"""


@dataclass
class Check:
    name: str
    level: str          # PASS | WARN | FAIL
    detail: str


def collect_task(name: str = TASK_NAME, runner: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    """Ask Task Scheduler about the drill task. Never raises: a failure to ask is `exists: False`."""
    script = PS_SCRIPT.replace("__TASK__", name)
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        r = runner(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                   capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exists": False, "error": f"powershell did not answer: {exc}"}
    if r.returncode != 0 or not (r.stdout or "").strip():
        return {"exists": False, "error": (r.stderr or r.stdout or "").strip()[:300] or "no output"}
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return {"exists": False, "error": r.stdout[:300]}


def hash_vault(vault: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(vault.rglob("*.md")):
        h.update(p.relative_to(vault).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip().strip('"').lower()


def _iso(value: Any) -> datetime | None:
    try:
        return parse_iso8601(str(value))
    except (ValueError, TypeError):
        return None


def run_checks(vault: Path, dev_root: Path, event_name: str, now: datetime, *,
               task: dict[str, Any] | None, bat_text: str | None, bat_path: Path | None = None,
               recorder_text: str | None = None) -> list[Check]:
    out: list[Check] = []
    ok = lambda name, cond, detail: out.append(Check(name, "PASS" if cond else "FAIL", detail))  # noqa: E731
    bat_path = bat_path or (dev_root / BAT)
    before = hash_vault(vault)

    # 1. the Event page
    event = find_event(vault, event_name)
    if event is None:
        out.append(Check("event page", "FAIL", f"no Event page matches {event_name!r}"))
        return out
    dev = event.meta.get("dev") or {}
    release = _iso(dev.get("release_utc"))
    ok("event release instant", release is not None, f"[[{event.path.stem}]] release_utc {dev.get('release_utc', '-')}")
    w = dev.get("window") if isinstance(dev.get("window"), dict) else {}
    start, end = _iso(w.get("start")), _iso(w.get("end"))
    if release is not None:
        ok("window is T-2..T+5", start == release - LEAD and end == release + TAIL,
           f"window {w.get('start', '-')} .. {w.get('end', '-')} against release {dev.get('release_utc')}")

    # 2. the rules registration and its raw file
    rules = rules_for(vault, event)
    page_tokens: list[str] = []
    if rules is None:
        out.append(Check("rules registration", "FAIL", "no Experiment page is bound to this event"))
    else:
        rdev = rules.meta.get("dev") or {}
        page_tokens = [str(r.get("market")) for r in rdev.get("rules") or [] if isinstance(r, dict) and r.get("market")]
        ok("rules registration", bool(page_tokens), f"[[{rules.path.stem}]] carries {len(page_tokens)} rule(s)")
        reg = rdev.get("registration")
        raw_path = (dev_root / reg) if reg else None
        if raw_path is None or not raw_path.is_file():
            out.append(Check("rules.json present", "FAIL", f"dev.registration {reg!r} is not a file under {dev_root}"))
        else:
            try:
                raw = json.loads(raw_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raw = {}
                out.append(Check("rules.json present", "FAIL", f"{reg}: {exc}"))
            raw_tokens = [str(r.get("market")) for r in raw.get("rules") or [] if isinstance(r, dict) and r.get("market")]
            ok("rules.json tokens == page tokens", sorted(raw_tokens) == sorted(page_tokens) and bool(raw_tokens),
               f"{len(raw_tokens)} in {reg}, {len(page_tokens)} on the page")
            raw_release = _iso(raw.get("release_utc"))
            ok("rules.json release == event release", raw_release is not None and raw_release == release,
               f"{raw.get('release_utc', '-')} vs {dev.get('release_utc', '-')}")

    # 3. the drill card, exactly as the operator will run it
    lines = drill_card(vault, event, now)
    text = "\n".join(lines)
    ok(f"card under {MAX_LINES} lines", len(lines) < MAX_LINES, f"{len(lines)} lines at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    if page_tokens:
        ok("card carries whole token ids", all(t in text for t in page_tokens),
           f"{sum(t in text for t in page_tokens)}/{len(page_tokens)} present verbatim")
    if release is not None:
        expect = countdown(release, now)
        ok("card countdown independently recomputed", expect in lines[0], f"expected {expect!r} in {lines[0]!r}")
    ok("card wrote nothing", hash_vault(vault) == before, "vault sha256 identical before and after the card")

    # 4. the batch file the task runs
    if bat_text is None:
        out.append(Check("drill batch file", "FAIL",
                         f"{bat_path} missing. It is git-ignored: a fresh clone has NO drill until it is recreated"))
    else:
        m = re.search(r"--tokens\s+(\S+)", bat_text)
        bat_tokens = m.group(1).split(",") if m else []
        ok("batch tokens == registered tokens", sorted(bat_tokens) == sorted(page_tokens) and bool(bat_tokens),
           f"{len(bat_tokens)} hard-coded in the batch, {len(page_tokens)} registered")
        m = re.search(r"set DUR=(?!%)(\d+)", bat_text)
        dur = int(m.group(1)) if m else None
        want = int((end - start).total_seconds()) if (start and end) else None
        ok("batch default duration == window length", dur is not None and dur == want, f"batch {dur}s, window {want}s")
        m = re.search(r"set BOOKS=(?!%)(\S+)", bat_text)      # the DEFAULT line, not `set BOOKS=%2`
        books = m.group(1) if m else ""
        ok("batch books dir == event books_dir", _norm(books) == _norm(books_dir(event)), f"{books} vs {books_dir(event)}")
        m = re.search(r"^\s*\"?([A-Za-z]:[^\s\"]*python[w]?\.exe)", bat_text, re.M)
        exe = Path(m.group(1)) if m else None
        ok("batch python exe exists", exe is not None and exe.is_file(), str(exe or "no python path found in the batch"))
        if recorder_text is None and (dev_root / RECORDER).is_file():
            recorder_text = (dev_root / RECORDER).read_text(encoding="utf-8", errors="replace")
        ok("recorder has --record-loop", recorder_text is not None and '"--record-loop"' in recorder_text,
           f"{RECORDER.as_posix()} {'defines' if recorder_text and '--record-loop' in recorder_text else 'LACKS'} the flag the batch passes")

    # 5. the scheduled task
    if task is None:
        out.append(Check("scheduled task", "WARN", "not queried (--no-task)"))
    elif not task.get("exists"):
        out.append(Check("scheduled task", "FAIL", f"{TASK_NAME} not found: {task.get('error', '')}"))
    else:
        last = task.get("last_result")
        ok("task enabled and ready", bool(task.get("enabled")) and task.get("state") in ("Ready", "Running"),
           f"state {task.get('state')}, enabled {task.get('enabled')}, last result {last}"
           + (" (has not run yet - correct)" if last == NEVER_RAN else ""))
        trig = [t for t in task.get("triggers") or [] if t]
        parsed = []
        for t in trig:
            try:
                parsed.append(datetime.fromisoformat(t))
            except ValueError:
                pass
        if release is not None:
            expected_local = (release - LEAD).astimezone().replace(tzinfo=None)
            ok("task fires at T-2 local time", expected_local in parsed,
               f"trigger {trig} vs expected {expected_local.isoformat()} (release {release.isoformat()} = T-0)")
        acts = " ".join(task.get("actions") or [])
        ok("task action is the drill batch", _norm(bat_path.name) in _norm(acts), acts or "no action")
        dis, stop = bool(task.get("disallow_start_on_batteries")), bool(task.get("stop_if_going_on_batteries"))
        out.append(Check("battery flags", "WARN" if (dis or stop) else "PASS",
                         f"DisallowStartIfOnBatteries={dis} StopIfGoingOnBatteries={stop}"
                         + (": AC power REQUIRED at fire time, or clear the flags (HOMEWORK decision)" if (dis or stop) else "")))
        out.append(Check("logon type", "WARN" if task.get("logon_type") == "Interactive" else "PASS",
                         f"{task.get('logon_type')}: runs only in a logged-in session (screen lock is fine, sign-out is not)"))
        bs = task.get("battery_status")
        out.append(Check("on mains now", "PASS" if (bs is None or bs in AC_STATES) else "WARN",
                         f"Win32_Battery status {bs}, charge {task.get('battery_pct')}%"))
        free = task.get("free_gb")
        ok("disk space for the books", isinstance(free, (int, float)) and free >= MIN_FREE_GB, f"{free} GB free on C:")
        if release is not None:
            local_day = (release - LEAD).astimezone().strftime("%Y-%m-%d")
            nr = str(task.get("next_run") or "")
            us_day = (release - LEAD).astimezone().strftime("%m/%d/%Y")
            out.append(Check("next run is the release day", "PASS" if (local_day in nr or us_day in nr) else "WARN",
                             f"scheduler says next run {nr or '-'}"))
    return out


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.drills.fomc_rehearsal", description=__doc__.split("\n\n")[0])
    ap.add_argument("--event", default="fomc_2026-09-16")
    ap.add_argument("--now", default=None, help="ISO instant to evaluate the card at (default: the real clock)")
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--no-task", action="store_true", help="skip the Task Scheduler query")
    ap.add_argument("--task-json", type=Path, default=None, help="use this JSON instead of querying the scheduler")
    a = ap.parse_args(argv)
    now = parse_iso8601(a.now) if a.now else datetime.now(timezone.utc)
    bat_path = a.dev_root / BAT
    bat_text = bat_path.read_text(encoding="utf-8", errors="replace") if bat_path.is_file() else None
    if a.no_task:
        task = None
    elif a.task_json:
        task = json.loads(a.task_json.read_text(encoding="utf-8"))
    else:
        task = collect_task()
    checks = run_checks(a.vault, a.dev_root, a.event, now, task=task, bat_text=bat_text, bat_path=bat_path)
    print(f"FOMC DRILL REHEARSAL - {a.event}    evaluated at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}", file=out)
    print("=" * 72, file=out)
    for c in checks:
        print(f"[{c.level}] {c.name}: {c.detail}", file=out)
    fails = sum(c.level == "FAIL" for c in checks)
    warns = sum(c.level == "WARN" for c in checks)
    print("-" * 72, file=out)
    print(f"{len(checks)} check(s): {fails} FAIL, {warns} WARN. Read-only: nothing above was written.", file=out)
    return EXIT_OK if fails == 0 else EXIT_FINDINGS


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
