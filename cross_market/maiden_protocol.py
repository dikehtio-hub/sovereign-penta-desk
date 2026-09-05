"""
Round 75 (Directives 75-1 and 75-2): the Item 18 maiden-run verification protocol
as ONE command. Read-only on the loop, the log and the note; Tier 2 runs only once
Tier 1 has written its verdict, under the bars registered in
cross_market/experiments/lead_lag_tier2.meta.json.

    python -m cross_market.maiden_protocol            exit 0 = every Tier 1 check passed
                                                      exit 3 = the maiden run has not happened yet (ETA shown)
                                                      exit 1 = it ran, but a check failed

Checks (Directive 75-1): the loop holds its lock; the sentinel reads READY; --status
shows a last run; the exporter log holds the `lead-lag: RAN` line; the Titans note
carries the run-at marker inside the Item 18 block under its header; the cycles after
the run log the cooldown (`lead-lag: READY, next run in`).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

DEV_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = DEV_ROOT / "cross_market" / "data" / "cross_market_exporter.log"
DEFAULT_META = DEV_ROOT / "cross_market" / "experiments" / "lead_lag_tier2.meta.json"
RAN_MARK = "lead-lag: RAN"
COOLDOWN_MARK = "lead-lag: READY, next run in"
FAILED_MARK = "lead-lag: run failed"
GATED_MARK = "lead-lag: gated"
EXIT_NOT_YET = 3
CHECK_ORDER = ("loop_running", "series_ready", "status_last_run", "log_ran_line", "note_run_at_inside_block",
               "cooldown_observed")


def read_log_lines(path) -> List[str]:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:                                       # noqa: BLE001 - missing log = no lines
        return []


def log_findings(lines: Sequence[str]) -> Dict[str, Any]:
    """The last `lead-lag: RAN` line, its verdict, and what the cycles after it logged."""
    ran_idx = [i for i, line in enumerate(lines) if RAN_MARK in line]
    last = lines[ran_idx[-1]] if ran_idx else None
    verdict = None
    if last is not None:
        tail = last.split(RAN_MARK, 1)[1]
        if "(" in tail and ")" in tail:
            verdict = tail[tail.index("(") + 1:tail.rindex(")")]
    after = lines[ran_idx[-1] + 1:] if ran_idx else []
    return {
        "ran_line": last, "verdict": verdict, "runs": len(ran_idx),
        "cooldown_lines_after_run": sum(1 for line in after if COOLDOWN_MARK in line),
        "failed_lines": sum(1 for line in lines if FAILED_MARK in line),
        "gated_lines": sum(1 for line in lines if GATED_MARK in line),
        "lines": len(lines),
    }


def note_findings(note: Path) -> Dict[str, Any]:
    """Whether the Item 18 block exists and carries the run-at marker under its header."""
    from cross_market.titan_correlator import LEADLAG_END, LEADLAG_HEADER, LEADLAG_RUN_TAG, LEADLAG_START, lead_lag_last_run
    try:
        content = Path(note).read_text(encoding="utf-8")
    except Exception:                                       # noqa: BLE001
        content = ""
    has_block = LEADLAG_START in content and LEADLAG_END in content
    block = content.split(LEADLAG_START, 1)[1].split(LEADLAG_END, 1)[0] if has_block else ""
    verdict_line = next((line.strip() for line in block.splitlines() if line.strip().startswith("> [!")), None)
    last = lead_lag_last_run(note) if content else None
    return {"path": str(note), "exists": bool(content), "has_block": has_block,
            "tag_inside": LEADLAG_RUN_TAG in block, "header_inside": LEADLAG_HEADER in block,
            "run_at": last.isoformat() if last else None, "verdict_line": verdict_line}


def run_tier2(coin: str, drop_dirs: Sequence[Path], db_path: Path, meta_path: Path = DEFAULT_META) -> Dict[str, Any]:
    """Directive 75-2: both subfamilies under the registered bars; the registration is read, never written."""
    from cross_market import lead_lag
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    bars = meta["bars"]
    out: Dict[str, Any] = {}
    for name in sorted(meta["subfamilies"]):
        latency = float(bars.get("latency_minutes_%s" % name.replace("-", "_"), 0.0))
        result, keys = lead_lag.run(coin, [Path(d) for d in drop_dirs], Path(db_path), 60, 0.02,
                                    int(bars["min_events"]), int(bars["min_points"]), family="macro",
                                    subfamily=name, latency_minutes=latency)
        out[name] = {"markets": keys, "latency_minutes": latency, "reading": meta["subfamilies"][name].get("reading"),
                     "report": lead_lag.format_report(result, coin, keys),
                     "result": {k: v for k, v in result.items() if k != "curve"}}
    return out


def check(vault: Optional[str] = None, log_path=None, drop_dirs=None, db_path=None, pid_file=None,
          now: Optional[datetime] = None, coin: str = "BTC", tier2: bool = True, meta_path=None) -> Dict[str, Any]:
    from Sports_Desk.interfaces.obsidian_exporter import resolve_vault
    from cross_market.interfaces.obsidian_exporter import exporter_status
    from cross_market.lead_lag import DEFAULT_DROP_DIRS, DEFAULT_HL_DB
    from cross_market.titan_correlator import TITANS_NOTE
    now = now or datetime.now(timezone.utc)
    status = exporter_status(pid_file, vault, drop_dirs, now=now)
    note = resolve_vault(vault) / ("%s.md" % TITANS_NOTE)
    log = log_findings(read_log_lines(log_path or DEFAULT_LOG))
    nf = note_findings(note)
    checks = {
        "loop_running": bool(status.get("running")),
        "series_ready": bool(status.get("lead_lag_ready")),
        "status_last_run": status.get("lead_lag_last_run") is not None,
        "log_ran_line": log["ran_line"] is not None,
        "note_run_at_inside_block": bool(nf["tag_inside"] and nf["header_inside"]),
        "cooldown_observed": log["cooldown_lines_after_run"] > 0,
    }
    done = checks["status_last_run"] or checks["note_run_at_inside_block"]
    info: Dict[str, Any] = {"checked_at": now.isoformat(), "status": status, "log": log, "note": nf,
                            "checks": checks, "maiden_run_done": done, "ok": bool(done and all(checks.values())),
                            "tier2": None, "tier2_skipped": None}
    if not done:
        info["tier2_skipped"] = "Tier 1 has not run yet (ETA %s)" % (status.get("lead_lag_eta") or "unknown")
    elif not tier2:
        info["tier2_skipped"] = "--no-tier2"
    else:
        try:
            info["tier2"] = run_tier2(coin, drop_dirs or DEFAULT_DROP_DIRS, db_path or DEFAULT_HL_DB,
                                      meta_path or DEFAULT_META)
        except Exception as exc:                            # noqa: BLE001 - Tier 1 checks still print
            info["tier2_skipped"] = "%s: %s" % (type(exc).__name__, exc)
    return info


def format_check(info: Dict[str, Any]) -> str:
    checks, log, nf, status = info["checks"], info["log"], info["note"], info["status"]
    lines = ["ITEM 18 MAIDEN RUN - VERIFICATION PROTOCOL (Directive 75-1) at %s" % info["checked_at"]]
    for name in CHECK_ORDER:
        mark = "PASS" if checks[name] else ("WAIT" if not info["maiden_run_done"] else "FAIL")
        lines.append("  [%s] %s" % (mark, name))
    lines.append("  loop: %s" % ("pid %s" % status.get("holder_pid") if status.get("running") else "no holder"))
    lines.append("  series: %s" % ("READY" if status.get("lead_lag_ready") else
                                   "NOT READY - " + "; ".join(status.get("lead_lag_reasons") or [])))
    if status.get("lead_lag_eta") and not status.get("lead_lag_ready"):
        lines.append("  ETA: %s" % status["lead_lag_eta"])
    lines.append("  last run (note): %s" % (nf.get("run_at") or "never"))
    if log["ran_line"]:
        lines.append("  log: %s" % log["ran_line"].strip())
        lines.append("  verdict: %s" % (log["verdict"] or "?"))
        lines.append("  cooldown lines after the run: %d" % log["cooldown_lines_after_run"])
    lines.append("  log lines %d · gated %d · failed %d · runs %d" % (log["lines"], log["gated_lines"],
                                                                     log["failed_lines"], log["runs"]))
    if nf.get("verdict_line"):
        lines.append("  note: %s" % nf["verdict_line"])
    if info.get("tier2"):
        lines.append("")
        lines.append("TIER 2 DIAGNOSTIC SUBFAMILIES (Directive 75-2, registered bars)")
        for name, part in info["tier2"].items():
            lines.append("--- %s (latency rule %g min) ---" % (name, part["latency_minutes"]))
            lines.append(part["report"].rstrip())
            if part.get("reading"):
                lines.append("  registered reading: %s" % part["reading"])
    elif info.get("tier2_skipped"):
        lines.append("  tier 2: skipped - %s" % info["tier2_skipped"])
    lines.append("RESULT: %s" % ("ALL CHECKS PASSED" if info["ok"] else
                                 ("NOT YET - come back after the ETA" if not info["maiden_run_done"] else "A CHECK FAILED")))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Item 18 maiden-run verification protocol (Round 75)")
    parser.add_argument("--vault", default=None)
    parser.add_argument("--log", default=None, help="exporter log (default %s)" % DEFAULT_LOG)
    parser.add_argument("--drops", nargs="*", default=None, help="drop directories (default: the Polymarket drop dirs)")
    parser.add_argument("--db", default=None, help="hyperliquid_data.db (read-only)")
    parser.add_argument("--pid-file", default=None)
    parser.add_argument("--coin", default="BTC")
    parser.add_argument("--meta", default=None, help="Tier 2 registration file (read only)")
    parser.add_argument("--no-tier2", action="store_true", help="Tier 1 checks only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    info = check(args.vault, args.log, [Path(d) for d in args.drops] if args.drops else None,
                 Path(args.db) if args.db else None, args.pid_file, coin=args.coin.upper(),
                 tier2=not args.no_tier2, meta_path=Path(args.meta) if args.meta else None)
    print(json.dumps(info, indent=2, default=str) if args.json else format_check(info))
    if not info["maiden_run_done"]:
        return EXIT_NOT_YET
    return 0 if info["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
