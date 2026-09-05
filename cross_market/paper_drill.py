"""
Cross-market paper arb end-to-end drill (Round 64, Directive 64-1).

Proves the closed loop without touching anything live: synthetic priced pairs
-> Betslip.stake_cross_market(paper=True) -> two paper receipts per dutch under
cross_market/data/paper_receipts (or a folder of your choice) -> the risk
simulator's receipt reader measures the desk -> load_live_inputs reports the
arb desk as "measured (paper_receipts receipts, N fills / E arbs ...)" instead
of "assumed (< 10 arb fills)".

Every receipt the drill writes carries `drill:1;` in its notes, and the drill
REMOVES them afterwards unless --keep is passed: ten synthetic dutches left in a
measurable folder would make the simulator "measure" a desk that never traded.

    python -m cross_market.paper_drill [--count 10] [--folder DIR] [--keep] [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple

from cross_market.execution_log import PAPER_RECEIPTS_DIR

DRILL_TAG = "drill:1;"
DEFAULT_COUNT = 10


def synthetic_pairs(count: int, start: datetime, capital: float = 1_000.0) -> List[Tuple[Any, Any, datetime]]:
    """
    `count` equal-payout dutches a day apart: a Polymarket YES at a price and a book
    line whose combined booksum is under 1, so every pair clears the worse-branch
    check the Shark applies. Deterministic, no randomness.
    """
    pairs = []
    for i in range(count):
        price = 0.45 + 0.005 * (i % 6)                      # 0.45 .. 0.475
        odds = 2.05 + 0.03 * (i % 5)                        # 2.05 .. 2.17
        payout = capital / (price + 1.0 / odds)             # equal-payout dutch on `capital`
        stake_pm, stake_book = payout * price, payout / odds
        gross = payout / capital - 1.0
        result = SimpleNamespace(
            leg_a=SimpleNamespace(venue="polymarket", selection="YES", decimal_odds=1.0 / price, token_id="drill-tok-%d" % i,
                                  raw_price=price),
            leg_b=SimpleNamespace(venue="draftkings" if i % 2 else "betmgm", selection="Home %d" % i, decimal_odds=odds,
                                  token_id="", raw_price=None),
            capital=capital, stake_a=stake_pm, stake_b=stake_book, booksum=price + 1.0 / odds, gross_arb=gross,
            worst_after_tax=capital * (1.0 + gross * 0.5))  # synthetic: half the edge survives tax
        pair = SimpleNamespace(
            market=SimpleNamespace(token_id="drill-tok-%d" % i, question="Drill question %d?" % i, market_type="moneyline",
                                   line="", sport="NFL"),
            book=result.leg_b.venue, book_selection=result.leg_b.selection, book_decimal_odds=odds,
            event_id="DRILL-%d" % i, quoted_at=None)
        pairs.append((result, pair, start + timedelta(days=i)))
    return pairs


def _receipt_notes(path: Path) -> str:
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            return str(next(csv.DictReader(handle)).get("notes") or "")
    except Exception:                                       # noqa: BLE001
        return ""


def clean_drill_receipts(folder: Path) -> int:
    """Remove every receipt in `folder` whose notes carry the drill tag. Returns the count."""
    removed = 0
    for path in sorted(Path(folder).glob("fills_*_dutched_arb_*.csv")):
        if DRILL_TAG in _receipt_notes(path):
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
    return removed


def run_drill(count: int = DEFAULT_COUNT, folder: Optional[Path] = None, start: Optional[datetime] = None,
              keep: bool = False, write: Callable[[str], None] = lambda line: None) -> Dict[str, Any]:
    """The whole loop; returns what changed. Never touches the Tax imports or placed_bets (paper mode)."""
    from Sports_Desk.interfaces.monarch_shark import Betslip
    from cross_market import risk_simulator as rs

    folder = Path(folder or PAPER_RECEIPTS_DIR)
    start = start or (datetime.now(timezone.utc) - timedelta(days=count)).replace(microsecond=0)
    before_arbs = rs._measure_arb_history(folder)
    before = rs.load_live_inputs(imports_dir=folder).provenance.get("arb_per_day")
    write("[DRILL] before: arb desk %s" % before)

    scratch = Path(tempfile.mkdtemp(prefix="drill_")) / "unused_sports.db"     # paper mode never opens it
    slip = Betslip(hook=None, db_path=scratch, read=lambda prompt: "y", write=write)
    records = []
    for result, pair, when in synthetic_pairs(count, start):
        slip.now = when
        record = slip.stake_cross_market(result, pair, confirm=False, paper=True, imports_dir=folder,
                                         extra_notes=DRILL_TAG)
        records.append(record)
    complete = sum(1 for r in records if r and r.get("complete"))

    after_arbs = rs._measure_arb_history(folder)
    after = rs.load_live_inputs(imports_dir=folder).provenance.get("arb_per_day")
    report = rs.format_calibration_report(rs.calibration_report(imports_dir=folder))
    arb_line = next((l for l in report.splitlines() if "arb receipts" in l), "")
    write("[DRILL] after:  arb desk %s" % after)
    write(arb_line)
    cleaned = 0 if keep else clean_drill_receipts(folder)
    if cleaned:
        write("[DRILL] cleaned %d drill receipt(s) from %s (pass --keep to leave them)" % (cleaned, folder))
    return {
        "count": count, "complete": complete, "folder": str(folder), "start": start.isoformat(),
        "before": {"provenance": before, "fills": (before_arbs or {}).get("fills", 0)},
        "after": {"provenance": after, "fills": (after_arbs or {}).get("fills", 0),
                  "executions": (after_arbs or {}).get("executions", 0),
                  "gross_return_mean": (after_arbs or {}).get("gross_return_mean"),
                  "arb_per_day": (after_arbs or {}).get("arb_per_day")},
        "calibration_line": arb_line, "cleaned": cleaned, "kept": keep,
        "closed_loop": bool(after and str(after).startswith("measured") and (not before or str(before).startswith("assumed"))),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-market paper arb end-to-end drill (paper receipts only)")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--folder", type=Path, default=None, help="paper receipts folder (default cross_market/data/paper_receipts)")
    parser.add_argument("--keep", action="store_true", help="leave the drill receipts in place")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    lines: List[str] = []
    result = run_drill(count=args.count, folder=args.folder, keep=args.keep, write=lines.append)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for line in lines:
            if line.startswith("[DRILL]") or line.startswith("[CAL]"):
                print(line)
        print("[DRILL] closed loop: %s (%d/%d dutches recorded, %d fills -> %d, %s)"
              % ("PROVEN" if result["closed_loop"] else "NOT proven", result["complete"], result["count"],
                 result["before"]["fills"], result["after"]["fills"],
                 "receipts kept" if result["kept"] else "receipts cleaned"))
    return 0 if result["closed_loop"] else 1


if __name__ == "__main__":
    sys.exit(main())
