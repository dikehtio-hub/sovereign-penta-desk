"""
Cross-market dutch execution recorder (Round 62, Directive 62-1).

The cross-market arb desk is scanner-only: nothing places orders yet. What it
needs before the first execution is the bookkeeping seam that execution will
call, so that the moment an operator (today) or an executor (later) dutches a
Polymarket outcome against a sportsbook line, both legs are recorded where each
belongs and the risk simulator can measure the desk from its own history:

  * the Polymarket leg -> an execution receipt in Tax_Reserve_Agent/data/imports
    (Tax_Reserve_Agent.interfaces.receipts.log_execution_receipt, strategy
    `dutched_arb`, venue `polymarket`), which csv_watcher ingests TAGGED so the
    fill counts against the dutched_arb bucket; its `notes` carry the dutch's
    arb_group, gross return, cost and leg count, because a receipt alone cannot
    price a dutch whose other leg is a wager;
  * the sportsbook leg -> Sports_Desk placed_bets with bet_kind "arbitrage" and
    the same arb_group (the desk's execution record; the tax record comes from
    the book's own export, as record_placed_bet says).

Both legs carry ONE shared timestamp (Ruling 62-1). risk_simulator's
_measure_arb_history groups receipts by arb_group first and by a 60 s
timestamp window second, and reads the gross return from the notes when it is
there.

Never raises on bookkeeping failure: a receipt problem must not take down an
execution path. The result says what was and was not written.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ARB_STRATEGY = "dutched_arb"
STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
# Round 63: paper fills never reach the Tax agent's imports (Ruling 34-D keeps the live
# ledger at $0.00 until real fills exist) nor placed_bets (the desk's live exposure).
# Both legs go here as receipts instead, so _measure_arb_history can still read them.
PAPER_RECEIPTS_DIR = Path(__file__).resolve().parent / "data" / "paper_receipts"


@dataclass
class DutchEconomics:
    cost: float
    payout: float
    gross: float                  # payout / cost - 1 on the equal-payout dutch (before tax)


def dutch_economics(pm_shares: float, pm_price: float, stake: float, decimal_odds: float) -> DutchEconomics:
    """
    A two-leg dutch: `pm_shares` Polymarket shares at `pm_price` (each pays $1 if
    that outcome wins) against `stake` at `decimal_odds` on the book. Cost is
    both outlays; the payout is the SMALLER branch, because a dutch is only as
    good as its worse side.
    """
    shares, price, stake, odds = float(pm_shares), float(pm_price), float(stake), float(decimal_odds)
    if shares <= 0 or price <= 0 or stake < 0 or odds <= 1.0:
        raise ValueError("a dutch needs positive shares and price, a non-negative stake and odds above 1.0")
    cost = shares * price + stake
    payout = min(shares * 1.0, stake * odds) if stake > 0 else 0.0
    return DutchEconomics(cost=cost, payout=payout, gross=(payout / cost - 1.0) if cost > 0 else 0.0)


def new_arb_group(stamp: str) -> str:
    return "xm-%s-%s" % (stamp.replace("-", "").replace(":", "").replace(" ", "T"), uuid.uuid4().hex[:8])


def record_dutch(pm_market: str, pm_price: float, pm_shares: float,
                 book: str, selection: str, decimal_odds: float, stake: float,
                 event_id: str, sport: str, market_type: str, line: str = "",
                 pm_side: str = "BUY", pm_tx_hash: Optional[str] = None, pm_fee: float = 0.0,
                 timestamp: Optional[str] = None, arb_group: Optional[str] = None,
                 fair_prob_at_placement: Optional[float] = None, edge_at_placement: Optional[float] = None,
                 imports_dir: Optional[Path] = None, sports_db: Optional[Path] = None,
                 receipt_writer=None, bet_writer=None, paper: bool = False) -> Dict[str, Any]:
    """
    Record one executed cross-market dutch: the Polymarket receipt and the
    sportsbook wager, both under one arb_group and one timestamp. Returns a
    record with what was written; `receipt` is None or `placed_bet_error` is set
    when a side could not be recorded. Never raises for bookkeeping reasons.

    `paper=True` (Round 63): NOTHING reaches the Tax agent's imports or the
    desk's placed_bets. Both legs are written as receipts into
    `imports_dir or PAPER_RECEIPTS_DIR` with a `paper:1;` note, so paper
    history is measurable by the risk simulator and invisible to the ledger.
    """
    stamp = timestamp or datetime.now(timezone.utc).strftime(STAMP_FORMAT)
    group = arb_group or new_arb_group(stamp)
    econ = dutch_economics(pm_shares, pm_price, stake, decimal_odds)
    extra = "arb_group:%s; gross:%.6f; cost:%.2f; legs:2; book_leg:%s@%.4f;%s" % (
        group, econ.gross, econ.cost, str(book).strip().lower().replace(" ", "_"), float(decimal_odds),
        " paper:1;" if paper else "")
    receipts_dir = (Path(imports_dir) if imports_dir else PAPER_RECEIPTS_DIR) if paper else imports_dir

    if receipt_writer is None:
        from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt as receipt_writer
    receipt = None
    try:
        receipt = receipt_writer(symbol=pm_market, side=pm_side, quantity=pm_shares, price=pm_price,
                                 strategy=ARB_STRATEGY, venue="polymarket", fee=pm_fee, tx_hash=pm_tx_hash,
                                 timestamp=stamp, imports_dir=receipts_dir, extra_notes=extra)
    except Exception as exc:                                # noqa: BLE001 - the writer itself never raises; belt and braces
        print("[WARN] dutch receipt not written (%s: %s)" % (type(exc).__name__, exc))

    placed_bet_id: Optional[int] = None
    placed_bet_error: Optional[str] = None
    book_receipt = None
    if paper:
        try:
            book_receipt = receipt_writer(symbol="%s:%s" % (str(book).strip().lower().replace(" ", "_"),
                                                            str(selection).strip().replace(" ", "_")),
                                          side="BUY", quantity=stake, price=decimal_odds, strategy=ARB_STRATEGY,
                                          venue="sportsbook", timestamp=stamp, imports_dir=receipts_dir,
                                          extra_notes="arb_group:%s; legs:2; leg:sportsbook; paper:1;" % group)
        except Exception as exc:                            # noqa: BLE001
            print("[WARN] paper book-leg receipt not written (%s: %s)" % (type(exc).__name__, exc))
        return {
            "arb_group": group, "timestamp": stamp, "strategy": ARB_STRATEGY, "paper": True,
            "receipts_dir": str(receipts_dir),
            "polymarket": {"market": pm_market, "side": str(pm_side).upper(), "shares": float(pm_shares),
                           "price": float(pm_price), "receipt": str(receipt) if receipt else None},
            "sportsbook": {"book": book, "selection": selection, "decimal_odds": float(decimal_odds),
                           "stake": float(stake), "placed_bet_id": None, "error": None,
                           "receipt": str(book_receipt) if book_receipt else None},
            "economics": asdict(econ),
            "complete": bool(receipt) and bool(book_receipt),
        }
    try:
        if bet_writer is None:
            from Sports_Desk.data.db import DEFAULT_DB_PATH, record_placed_bet as bet_writer
            sports_db = sports_db or DEFAULT_DB_PATH
        placed_at = datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=timezone.utc).isoformat()
        kwargs = dict(event_id=event_id, sport=sport, market_type=market_type, line=line, selection=selection,
                      book=book, decimal_odds=decimal_odds, stake=stake,
                      fair_prob_at_placement=fair_prob_at_placement, edge_at_placement=edge_at_placement,
                      bet_kind="arbitrage", arb_group=group,
                      notes="strategy:%s; arb_group:%s; gross:%.6f;" % (ARB_STRATEGY, group, econ.gross),
                      placed_at=placed_at)
        if sports_db is not None:
            kwargs["db_path"] = Path(sports_db)
        placed_bet_id = int(bet_writer(**kwargs))
    except Exception as exc:                                # noqa: BLE001
        placed_bet_error = "%s: %s" % (type(exc).__name__, exc)
        print("[WARN] dutch book leg not recorded in placed_bets (%s)" % placed_bet_error)

    return {
        "arb_group": group, "timestamp": stamp, "strategy": ARB_STRATEGY, "paper": False,
        "receipts_dir": str(imports_dir) if imports_dir else None,
        "polymarket": {"market": pm_market, "side": str(pm_side).upper(), "shares": float(pm_shares),
                       "price": float(pm_price), "receipt": str(receipt) if receipt else None},
        "sportsbook": {"book": book, "selection": selection, "decimal_odds": float(decimal_odds),
                       "stake": float(stake), "placed_bet_id": placed_bet_id, "error": placed_bet_error,
                       "receipt": None},
        "economics": asdict(econ),
        "complete": bool(receipt) and placed_bet_id is not None,
    }


def format_record(record: Dict[str, Any]) -> str:
    pm, sb, econ = record["polymarket"], record["sportsbook"], record["economics"]
    if record.get("paper"):
        book_line = "[DUTCH]   %s %s @ %.3f stake $%.2f -> PAPER receipt %s" % (
            sb["book"], sb["selection"], sb["decimal_odds"], sb["stake"], sb.get("receipt") or "NOT written")
    else:
        book_line = "[DUTCH]   %s %s @ %.3f stake $%.2f -> placed_bets id %s" % (
            sb["book"], sb["selection"], sb["decimal_odds"], sb["stake"],
            sb["placed_bet_id"] if sb["placed_bet_id"] is not None else ("NOT recorded: %s" % sb["error"]))
    lines = [
        "[DUTCH] %s at %s UTC%s%s" % (record["arb_group"], record["timestamp"],
                                      "  PAPER (no ledger, no placed_bets)" if record.get("paper") else "",
                                      "" if record["complete"] else "  (INCOMPLETE)"),
        "[DUTCH]   polymarket %s %.4f x %s @ %.4f -> %s" % (pm["side"], pm["shares"], pm["market"], pm["price"],
                                                            pm["receipt"] or "receipt NOT written"),
        book_line,
        "[DUTCH]   cost $%.2f, worse-branch payout $%.2f, gross %+.4f" % (econ["cost"], econ["payout"], econ["gross"]),
    ]
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Record an executed cross-market dutch (both legs, one arb_group)")
    parser.add_argument("--pm-market", required=True, help="Polymarket market / outcome symbol as the ledger knows it")
    parser.add_argument("--pm-price", type=float, required=True)
    parser.add_argument("--pm-shares", type=float, required=True)
    parser.add_argument("--pm-side", default="BUY")
    parser.add_argument("--pm-tx-hash", default=None, help="the CLOB fill id (dedupe key) when known")
    parser.add_argument("--book", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--odds", type=float, required=True, help="decimal odds taken on the book")
    parser.add_argument("--stake", type=float, required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--sport", required=True)
    parser.add_argument("--market-type", default="moneyline")
    parser.add_argument("--line", default="")
    parser.add_argument("--timestamp", default=None, help="shared UTC stamp 'YYYY-MM-DD HH:MM:SS' (default now)")
    parser.add_argument("--arb-group", default=None)
    parser.add_argument("--imports-dir", type=Path, default=None)
    parser.add_argument("--sports-db", type=Path, default=None)
    parser.add_argument("--paper", action="store_true",
                        help="paper fill: both legs as receipts under cross_market/data/paper_receipts (or --imports-dir); "
                             "nothing reaches the tax imports or placed_bets")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    # Ruling 63-4: an explicit path that does not exist is a typo, not a request to create a ledger.
    if args.sports_db is not None and not Path(args.sports_db).exists():
        print("[DUTCH] refused: --sports-db %s does not exist (refusing to create a ledger at a typo'd path)"
              % args.sports_db)
        return 2
    if args.imports_dir is not None and not Path(args.imports_dir).is_dir():
        print("[DUTCH] refused: --imports-dir %s is not an existing folder" % args.imports_dir)
        return 2
    try:
        record = record_dutch(args.pm_market, args.pm_price, args.pm_shares, args.book, args.selection, args.odds,
                              args.stake, args.event_id, args.sport, args.market_type, args.line, pm_side=args.pm_side,
                              pm_tx_hash=args.pm_tx_hash, timestamp=args.timestamp, arb_group=args.arb_group,
                              imports_dir=args.imports_dir, sports_db=args.sports_db, paper=args.paper)
    except ValueError as exc:
        print("[DUTCH] refused: %s" % exc)
        return 2
    print(json.dumps(record, indent=2) if args.json else format_record(record))
    return 0 if record["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
