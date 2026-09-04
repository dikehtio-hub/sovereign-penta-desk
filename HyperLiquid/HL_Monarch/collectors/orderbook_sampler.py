"""
Top-of-book spread sampling into orderbook_snapshots (Round 35, Ruling 5.C).

WHAT THIS CLOSES. The cost model behind the 7-day basis hold amortises a spread
that nothing in the repository measured: orderbook_snapshots existed, the
repository could write it, and no caller ever did. Every persisted basis window
therefore carried fee_basis='unmeasured' and a NULL net rate. This module is the
caller.

BOUNDED BY DESIGN. One l2Book request per coin per pass, for a capped list of
coins, on a slow cadence - the REST budget is nearly consumed by context polling
(see settings.ORDERBOOK_SAMPLE_INTERVAL). The pass never raises: a coin that
fails is recorded by name and the rest are written, because one 429 must not
cost the other twenty-three spreads.

The depth figures come from the same payload at no extra cost; the spread is
what the persistence module reads (spread_bps_at), and it is the PERP leg's
spread. The spot leg of a spot-backed basis trade is a different book that is
not sampled here; the drag formula's two legs use the perp figure for both.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from analytics.liquidation_engine import LiquidationEngine


def top_funding_candidates(snapshots: Iterable[Dict[str, Any]], n: int = 5,
                           spot_backed_only: bool = True) -> List[str]:
    """
    The coins quoting the highest POSITIVE funding right now - what the
    spot-backed harvester would open next (Round 37, cross-check 3.3). Sampling
    them BEFORE the entry means a measured spread exists at the instant a grid
    window opens, not only after the position is held.

    Main-dex perps only by default: a HIP-3 perp (`xyz:TSLA`) has no spot leg
    to hedge with, so its funding is not a candidate for this strategy however
    high it prints. Ties break on the coin name so the list is deterministic.
    """
    ranked: List[Tuple[float, str]] = []
    for s in snapshots or ():
        coin = str((s.get("coin") if isinstance(s, dict) else "") or "")
        if not coin or (spot_backed_only and ":" in coin):
            continue
        try:
            rate = float(s.get("funding_rate"))
        except (TypeError, ValueError):
            continue
        if rate <= 0.0:
            continue
        ranked.append((rate, coin))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [coin for _, coin in ranked[: max(0, int(n))]]


def select_sample_coins(core: Sequence[str], rotated: Iterable[str], cap: int,
                        extra: Sequence[str] = (), candidates: Sequence[str] = ()) -> List[str]:
    """
    Which coins to sample this pass, in priority order, deduplicated, capped:

        held positions (extra) > funding candidates > volume-rotated > core

    A held position must never lose its spread series to a rank change; a
    candidate must have a spread on record before its entry instant; the
    rotated set is where volume lives; the core watchlist takes what is left.
    """
    ordered: List[str] = []
    for coin in list(extra) + list(candidates) + sorted(set(rotated)) + list(core):
        if coin and coin not in ordered:
            ordered.append(coin)
    return ordered[: max(0, int(cap))]


def sample_orderbooks(client: Any, repo: Any, coins: Sequence[str],
                      now_ms: Optional[int] = None,
                      analyze: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None
                      ) -> Dict[str, Any]:
    """
    Fetch each coin's L2 book, reduce it to spread and depth, write one row each.

    Returns what happened - requested, written, per-coin failures, and the
    median spread - so the caller can log a pass in one line and a test can
    assert on it.
    """
    analyze = analyze or LiquidationEngine.analyze_orderbook_depth
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    rows: List[Dict[str, Any]] = []
    failures: Dict[str, str] = {}
    for coin in coins:
        try:
            book = client.get_l2_book(coin)
            depth = analyze(coin, book)
        except Exception as exc:                            # noqa: BLE001 - isolate per coin
            failures[coin] = "%s: %s" % (type(exc).__name__, exc)
            continue
        if not depth:
            failures[coin] = "empty book"
            continue
        depth = dict(depth)
        depth["timestamp"] = now_ms
        rows.append(depth)
    if rows:
        repo.insert_orderbook_snapshots(rows)
    spreads = sorted(float(r["spread_bps"]) for r in rows)
    return {
        "requested": len(coins),
        "written": len(rows),
        "failed": failures,
        "median_spread_bps": spreads[len(spreads) // 2] if spreads else None,
        "timestamp": now_ms,
    }
