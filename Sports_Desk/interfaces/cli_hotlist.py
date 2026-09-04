"""
Actionable edges - the terminal hotlist.

The last link in the chain. `odds_watcher` finds edges and `monarch_hook` decides
whether any of them are worth staking after tax; this puts the two together and
prints what a human should actually do, with a dollar figure attached.

EVERY FILTER HERE IS A REASON AN EDGE IS NOT ACTIONABLE, and each one exists
because the alternative is a shortlist that looks tradeable and is not:

  SETTLED     the event already has a recorded outcome. An edge on a finished
              game is a data lag, not an opportunity.
  STALE       the quote is older than its sport allows, measured against now.
              A stale sharp price against a live retail price is a clock
              difference - and the most flattering possible error, because the
              market has already moved to where the phantom edge points.
  STARTED     the scheduled start has passed. Pre-game prices do not survive
              first contact with the game.
  LIVE        an in-play quote, which is not comparable to the pre-game fair
              value it was scored against.
  UNTRUSTED   the sharp market was flagged divergent by the Power oracle - two
              independent estimators disagreeing usually means a mistyped leg.
  SUB-HURDLE  `monarch_hook.check_order` refused it. Under a standard deduction
              that will be most things, and that is the correct answer, not a
              bug: the hurdle at even money is 21.21% and rises with the odds.

WHAT IT DOES NOT DO. It does not place a bet, and it does not rank by edge alone
- it ranks by APPROVED DOLLARS, because a 40% edge the bankroll gate sizes to $12
is worth less attention than a 30% edge it sizes to $300. Nothing here writes to
the ledger; the tax record is made when the wager is actually placed and imported
through `Tax_Reserve_Agent`.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from Sports_Desk.data.db import DEFAULT_DB_PATH, query_edges, settled_event_ids
from Sports_Desk.ingestors.odds_watcher import max_quote_age
from Tax_Reserve_Agent.engine.lot_engine import as_naive_utc, parse_iso_date

# Why an edge did not make the list. Ordered as they are applied.
REASON_SETTLED = "settled"
REASON_STARTED = "started"
REASON_LIVE = "live"
REASON_STALE = "stale"
REASON_UNTRUSTED = "untrusted"
REASON_REJECTED = "rejected"


def _moment(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return as_naive_utc(parse_iso_date(text))
    except (ValueError, TypeError):
        return None


def _american(decimal_odds: float) -> str:
    if decimal_odds >= 2.0:
        return f"+{round((decimal_odds - 1) * 100):d}"
    return f"{round(-100 / (decimal_odds - 1)):d}"


def build_hotlist(hook: Any,
                  db_path: Path = DEFAULT_DB_PATH,
                  now: Optional[datetime] = None,
                  min_edge: float = 0.0,
                  bankroll: Optional[float] = None,
                  strategy: str = "sports_betting",
                  desired_notional: Optional[float] = None,
                  already_deployed: float = 0.0,
                  include_rejected: bool = False) -> List[Dict[str, Any]]:
    """
    Live, unexpired edges run through the bankroll gate.

    `hook` is a `MonarchBankrollHook`. Passed in rather than constructed here so
    the caller owns the ledger connection and the tax configuration - and so this
    module stays testable without one.

    Returns rows sorted by APPROVED DOLLARS descending. Rows that failed a filter
    carry `actionable=False` and a `reason`; they are omitted unless
    `include_rejected` is set, because a hotlist that lists everything is not a
    hotlist.
    """
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    settled = settled_event_ids(db_path=db_path)
    rows: List[Dict[str, Any]] = []

    # Newest quote per (event, market, line, selection, retail book): an edge
    # table keeps history on purpose, and history is not a shortlist.
    latest: Dict[tuple, Dict[str, Any]] = {}
    for edge in query_edges(min_edge=min_edge, db_path=db_path):
        key = (edge["event_id"], edge["market_type"], edge["line"],
               edge["selection"], edge["retail_book"])
        seen = latest.get(key)
        if seen is None or str(edge["timestamp"]) > str(seen["timestamp"]):
            latest[key] = edge

    for edge in latest.values():
        row = dict(edge)
        row["actionable"] = False
        row["reason"] = ""
        row["approved_notional"] = 0.0

        quoted_at = _moment(edge.get("quoted_at")) or _moment(edge.get("timestamp"))
        start_time = _moment(edge.get("start_time"))
        odds = float(edge["retail_offered_odds"])

        if edge["event_id"] in settled:
            row["reason"] = REASON_SETTLED
        elif edge.get("is_live"):
            row["reason"] = REASON_LIVE
        elif start_time is not None and start_time <= now:
            row["reason"] = REASON_STARTED
        elif quoted_at is not None:
            seconds_to_start = ((start_time - quoted_at).total_seconds()
                                if start_time else None)
            limit = max_quote_age(edge["sport"], edge["market_type"], seconds_to_start)
            age = (now - quoted_at).total_seconds()
            row["quote_age_seconds"] = age
            row["staleness_limit"] = limit
            if age > limit:
                row["reason"] = REASON_STALE

        if not row["reason"] and not edge.get("sharp_trustworthy", 1):
            row["reason"] = REASON_UNTRUSTED

        if not row["reason"]:
            decision = hook.check_order(
                float(desired_notional) if desired_notional
                else float(bankroll or hook.get_safe_bankroll()),
                live_cash=bankroll, category="sports", strategy=strategy,
                already_deployed=float(already_deployed),
                expected_edge=float(edge["gross_edge"]), decimal_odds=odds)
            row["approved_notional"] = decision.approved_notional
            row["decision_reason"] = decision.reason
            row["after_tax_hurdle"] = decision.detail.get("after_tax_hurdle")
            row["after_tax_kelly"] = decision.detail.get("after_tax_kelly")
            if decision.approved and decision.approved_notional > 0:
                row["actionable"] = True
            else:
                row["reason"] = REASON_REJECTED

        rows.append(row)

    rows.sort(key=lambda r: (r["actionable"], r["approved_notional"], r["gross_edge"]),
              reverse=True)
    return rows if include_rejected else [r for r in rows if r["actionable"]]


def render_hotlist(rows: List[Dict[str, Any]], bankroll: Optional[float] = None,
                   include_rejected: bool = False) -> str:
    """ASCII HUD in the shape of the other desks' cards."""
    lines = ["=" * 96,
             "          SPORTS DESK - ACTIONABLE EDGES (after-tax)",
             "=" * 96]
    if bankroll is not None:
        lines.append(f"  Safe bankroll: ${bankroll:,.2f}")
        lines.append("-" * 96)

    actionable = [r for r in rows if r["actionable"]]
    if not actionable:
        lines.append("  No actionable edges.")
        lines.append("")
        lines.append("  That is the expected answer under a casual standard deduction:")
        lines.append("  IRC 165(d) disallows losses entirely, so an even-money wager needs")
        lines.append("  a 21.21% gross edge to break even after tax, and more as the odds")
        lines.append("  lengthen. An empty hotlist is the system working, not failing.")
    else:
        lines.append(f"  {'STAKE':>9}  {'EDGE':>7}  {'HURDLE':>7}  {'KELLY':>7}  "
                     f"{'BOOK':<12}{'PRICE':>8}  {'FAIR':>8}  SELECTION")
        lines.append("-" * 96)
        for row in actionable:
            lines.append(
                f"  ${row['approved_notional']:>8,.2f}  "
                f"{row['gross_edge'] * 100:>6.2f}%  "
                f"{(row.get('after_tax_hurdle') or 0) * 100:>6.2f}%  "
                f"{(row.get('after_tax_kelly') or 0) * 100:>6.2f}%  "
                f"{row['retail_book'][:11]:<12}"
                f"{_american(float(row['retail_offered_odds'])):>8}  "
                f"{_american(float(row['sharp_fair_odds'])):>8}  "
                f"{row['selection']} "
                f"({row['event_id']}/{row['market_type']}"
                f"{'@' + row['line'] if row['line'] else ''})")
        total = sum(r["approved_notional"] for r in actionable)
        lines.append("-" * 96)
        lines.append(f"  {len(actionable)} actionable | total stake ${total:,.2f}")

    rejected = [r for r in rows if not r["actionable"]]
    if include_rejected and rejected:
        lines.append("-" * 96)
        lines.append("  NOT ACTIONABLE:")
        counts: Dict[str, int] = {}
        for row in rejected:
            counts[row["reason"]] = counts.get(row["reason"], 0) + 1
        for reason, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"    {count:>4} {reason}")
    lines.append("=" * 96)
    lines.append("  Sizing is AFTER-TAX and already clamped to the strategy bucket.")
    lines.append("  Placing a wager does not record it - import the book's export")
    lines.append("  through Tax_Reserve_Agent or the escrow will not know about it.")
    lines.append("=" * 96)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sports_Desk actionable-edge hotlist")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--min-edge", type=float, default=0.0)
    parser.add_argument("--bankroll", type=float, default=None,
                        help="live cash override; defaults to the ledger snapshot")
    parser.add_argument("--strategy", default="sports_betting")
    parser.add_argument("--stake", type=float, default=None,
                        help="notional to request per bet; defaults to the bankroll")
    parser.add_argument("--show-rejected", action="store_true")
    args = parser.parse_args(argv)

    from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
    hook = get_hook()
    rows = build_hotlist(hook, db_path=args.db or DEFAULT_DB_PATH,
                         min_edge=args.min_edge, bankroll=args.bankroll,
                         strategy=args.strategy, desired_notional=args.stake,
                         include_rejected=True)
    print(render_hotlist(rows, bankroll=hook.get_safe_bankroll(args.bankroll),
                         include_rejected=args.show_rejected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
