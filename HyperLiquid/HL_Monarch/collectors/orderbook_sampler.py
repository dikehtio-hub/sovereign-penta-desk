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
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from analytics.funding_arbitrage import FundingArbitrageEngine, spot_symbol_for
from analytics.liquidation_engine import LiquidationEngine
from analytics.market_intelligence import MarketIntelligence
from config.settings import ARB_MIN_DAY_VOLUME, ARB_MIN_NOTIONAL_OI, BASIS_HOLDING_DAYS


def top_funding_candidates(snapshots: Iterable[Dict[str, Any]], n: int = 5,
                           spot_backed_only: bool = True,
                           spot_universe: Optional[Set[str]] = None,
                           min_notional_oi: float = ARB_MIN_NOTIONAL_OI,
                           min_day_volume: float = ARB_MIN_DAY_VOLUME,
                           spreads: Optional[Dict[str, float]] = None,
                           holding_days: float = BASIS_HOLDING_DAYS) -> List[str]:
    """
    The coins quoting the highest POSITIVE funding right now that the
    spot-backed harvester could actually open next (Round 37, cross-check 3.3).
    Sampling them BEFORE the entry means a measured spread exists at the instant
    a grid window opens, not only after the position is held.

    ROUND 38 - SPOT BACKING IS LOOKED UP, NOT GUESSED (cross-check 3.2). The
    Round 37 rule "no ':' in the coin" was wrong both ways on live markets: four
    of the five candidates it sampled (CHIP, PONS, XMR, FARTCOIN) have no spot
    token and can never be a basis leg, while `para:ANSEM` - which the harvester
    holds against spot ANSEM - was excluded. Eligibility is now decided by
    `spot_symbol_for` against the live spot universe, the same function the
    harvester's scan uses. With no universe supplied (`None`) the prefix rule
    remains as a fallback; an EMPTY universe means the lookup failed and yields
    no candidates rather than a guess.

    LIQUIDITY FLOORS (cross-check 3.3). The scan rejects a market under the OI
    or 24h-volume floor before it reads any spread, so a sampling slot spent on
    one measures nothing that can be traded. The spread itself stays ungated:
    sampling is what produces it. Ties break on the coin name so the list is
    deterministic.

    ROUND 39 - RANK BY WHAT THE TRADE WOULD NET (cross-check 3.4). A coin with a
    spread on record (`spreads`: the latest orderbook_snapshots reading per coin)
    ranks on its APR net of that spread on both legs amortised over
    `holding_days`, so a wide market sinks once it has been measured. A coin
    with no reading ranks on its gross APR - an upper bound on its net, which
    buys it exactly one sample, after which its measured net decides. Measured
    and unmeasured share ONE ordering deliberately: ranking every unmeasured
    coin behind every measured one would leave a new hot market unsampled for as
    long as five measured ones stayed positive, which defeats sampling-before-
    entry (the reason candidates exist).
    """
    ranked: List[Tuple[float, str]] = []
    for s in snapshots or ():
        if not isinstance(s, dict):
            continue
        coin = str(s.get("coin") or "")
        if not coin:
            continue
        if spot_backed_only:
            if spot_universe is not None:
                if spot_symbol_for(coin, spot_universe) is None:
                    continue
            elif ":" in coin:
                continue
        try:
            rate = float(s.get("funding_rate"))
            notional_oi = float(s.get("notional_oi") or 0.0)
            day_volume = float(s.get("day_ntl_vlm") or 0.0)
        except (TypeError, ValueError):
            continue
        if rate <= 0.0 or notional_oi < min_notional_oi or day_volume < min_day_volume:
            continue
        apr = MarketIntelligence.calculate_annualized_funding_apr(rate)
        spread = (spreads or {}).get(coin)
        if spread is not None:
            apr = FundingArbitrageEngine.net_apr_after_spread(
                {"funding_apr": apr, "spread_bps": float(spread), "is_spot_backed": True},
                holding_period_days=holding_days, hedge_legs=2)
        ranked.append((apr, coin))
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
