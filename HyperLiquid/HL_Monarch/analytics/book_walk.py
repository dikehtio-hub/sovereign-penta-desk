"""
Walking an L2 book: what a basis round trip COSTS AT A SIZE, not at the touch.

WHY (Antigravity Sections 100-101, 2026-09-21). The cost model behind the basis desk used
one number per coin - the top-of-book spread of the PERP leg, applied to both legs
(collectors/orderbook_sampler.py says so itself). Two things were wrong with that, and both
only showed up when someone walked the books:

  * the spot leg is a different, usually thinner book. XMR: perp ~1 bp, spot 30-49 bps.
  * the touch is the price of the first dollar. At $2,500 a leg FARTCOIN went from 6 bps to
    35, at $5,000 to 97, and PURR's perp - 41 % of the replayed desk's gross - showed $1,265
    of visible depth, so $2,500 could not be filled from it at all.

On the touch spreads the desk PASSED its viability hurdle by +3.21 %. On the walked costs,
without the name it cannot enter, it nets -5.53 %. Same policy, same 180 days.

This module is the arithmetic only: pure functions over an l2Book payload, no I/O, nothing
imported by the live collector. The sampler that feeds it (WP3) and the standalone script
that can run beside the collector both call these, so there is one definition of "cost".

CONVENTIONS. A book is Hyperliquid's l2Book payload: {"levels": [bids, asks]}, each level
{"px": str, "sz": str}, bids descending, asks ascending. Costs are in basis points of
notional against the MID. `None` always means "the visible book could not absorb this size"
- never zero, never a guess: an unfillable size is a different fact from a cheap one.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

Level = Tuple[float, float]                      # (price, size in base units)
SIZES_USD: Tuple[int, ...] = (1_000, 2_500, 5_000, 10_000)      # Section 101 s3.3


def parse_book(book: Dict[str, Any]) -> Tuple[List[Level], List[Level]]:
    """(bids, asks) as floats. Raises ValueError on a payload with no two-sided book."""
    levels = (book or {}).get("levels") or []
    if len(levels) != 2 or not levels[0] or not levels[1]:
        raise ValueError("no two-sided book")
    side = lambda raw: [(float(x["px"]), float(x["sz"])) for x in raw]          # noqa: E731
    return side(levels[0]), side(levels[1])


def mid_price(bids: Sequence[Level], asks: Sequence[Level]) -> float:
    return (bids[0][0] + asks[0][0]) / 2.0


def touch_spread_bps(bids: Sequence[Level], asks: Sequence[Level]) -> float:
    return (asks[0][0] - bids[0][0]) / mid_price(bids, asks) * 1e4


def visible_depth_usd(levels: Sequence[Level]) -> float:
    return sum(px * sz for px, sz in levels)


def walk_slippage_bps(levels: Sequence[Level], mid: float, usd: float) -> Optional[float]:
    """
    Distance, in bps of the mid, between the mid and the VWAP of spending `usd` into this
    side of the book. None when the visible levels run out first.
    """
    if usd <= 0:
        return 0.0
    left, spent, qty = float(usd), 0.0, 0.0
    for px, sz in levels:
        take = min(left, px * sz)
        spent += take
        qty += take / px
        left -= take
        if left <= 1e-9:
            break
    if left > 1e-9 or qty <= 0:
        return None
    return abs(spent / qty - mid) / mid * 1e4


def leg_round_trip_bps(bids: Sequence[Level], asks: Sequence[Level], usd: float) -> Optional[float]:
    """In and out of ONE leg at this size: walk the asks to buy, the bids to sell."""
    mid = mid_price(bids, asks)
    buy, sell = walk_slippage_bps(asks, mid, usd), walk_slippage_bps(bids, mid, usd)
    return None if buy is None or sell is None else buy + sell


def basis_round_trip_bps(perp_book: Dict[str, Any], spot_book: Dict[str, Any], usd: float) -> Dict[str, Optional[float]]:
    """
    A full basis round trip at `usd` a leg: open (buy spot, sell perp) and close (sell spot,
    buy perp). Each leg is crossed twice, once on each side, so the cost is symmetric in
    which side opens. {"perp", "spot", "total"}; any of them None when that leg cannot fill.
    """
    (pb, pa), (sb, sa) = parse_book(perp_book), parse_book(spot_book)
    perp, spot = leg_round_trip_bps(pb, pa, usd), leg_round_trip_bps(sb, sa, usd)
    return {"perp": perp, "spot": spot, "total": None if perp is None or spot is None else perp + spot}


def thinner_side_usd(book: Dict[str, Any]) -> float:
    bids, asks = parse_book(book)
    return min(visible_depth_usd(bids), visible_depth_usd(asks))


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile of an ALREADY SORTED sequence. q in [0, 1]."""
    if not sorted_values:
        return float("nan")
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]
