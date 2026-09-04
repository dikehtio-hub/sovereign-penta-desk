"""
Historical Funding Harvest Backtester.

Replays the funding a delta-neutral (or directional) perp position would actually
have collected, using the funding_rate / mark_px series already retained in
`asset_snapshots`. This answers the question the live arb matrix cannot: an
extreme *instantaneous* APR says nothing about whether that rate persisted long
enough to be harvested.

METHOD
------
Snapshots are irregular - roughly every 8s while the collector runs, with gaps
whenever it is stopped. Funding is therefore integrated by *time*, not averaged
over samples, so a burst of dense sampling cannot outvote a long quiet stretch:

    funding_pnl% = SUM( rate_i x dt_hours_i ) x 100        (rate is a 1h rate)

Intervals longer than `max_gap_hours` are treated as unobserved: they are
excluded from the accrual and subtracted from coverage, rather than silently
extrapolating the last seen rate across a collector outage. `coverage_pct`
reports how much of the requested window was actually observed, so a result
computed from half a window is never mistaken for a full one.

Price PnL is tracked separately. A spot-hedged basis trade is close to delta
neutral, so funding is the whole return; an unhedged position also carries the
mark-price move, which routinely dwarfs the funding. Both are reported so the
difference is visible instead of assumed.
"""

import math
import time
from typing import Any, Dict, List, Optional, Tuple

from storage.repository import MarketRepository
from config.settings import ARB_FUNDING_INTERVAL_HOURS

# An interval longer than this is a collector outage, not an observation.
DEFAULT_MAX_GAP_HOURS = 0.5

# Below a coverage floor, annualising the observed window produces a number that is
# more misleading than useful: a 1.7%-covered window extrapolates a couple of
# minutes of funding into a four-digit APR. `realised_apr` is suppressed rather
# than shown with a caveat, because a printed number gets read and a caveat does not.
#
# The floor scales with the window, because a fixed percentage is not a fixed
# amount of evidence: 70% of 24h is 17 observed hours, while 70% of a week is 118 -
# a far harsher demand for the same nominal bar. Longer windows are allowed a lower
# percentage because even a reduced share of them still contains more real data.
# Anchors for the interpolated curve. Stepped tiers put a cliff between adjacent
# windows - a 72h ask demanded 60% while a 73h ask demanded 50%, so asking for one
# extra hour of history made the bar easier. The threshold now moves continuously.
COVERAGE_ANCHOR_SHORT_HOURS = 24.0
COVERAGE_ANCHOR_SHORT_PCT = 75.0
COVERAGE_ANCHOR_LONG_HOURS = 168.0
COVERAGE_ANCHOR_LONG_PCT = 50.0

# Kept for reference/back-compat; the curve is authoritative.
COVERAGE_THRESHOLDS = (
    (COVERAGE_ANCHOR_SHORT_HOURS, COVERAGE_ANCHOR_SHORT_PCT),
    (72.0, 62.5),
    (COVERAGE_ANCHOR_LONG_HOURS, COVERAGE_ANCHOR_LONG_PCT),
)
DEFAULT_COVERAGE_THRESHOLD_PCT = COVERAGE_ANCHOR_LONG_PCT
MIN_COVERAGE_FOR_APR_PCT = 70.0


def coverage_threshold_for(hours: float) -> float:
    """
    Minimum coverage that makes annualising a window of this length defensible.

    Linearly interpolated between 24h -> 75% and 168h -> 50%, then flat outside
    that range. Longer windows are allowed a lower percentage because even a
    reduced share of a week is more absolute evidence than most of a day; the
    interpolation removes the discontinuity a tiered version had at each boundary.
    """
    lo_h, lo_pct = COVERAGE_ANCHOR_SHORT_HOURS, COVERAGE_ANCHOR_SHORT_PCT
    hi_h, hi_pct = COVERAGE_ANCHOR_LONG_HOURS, COVERAGE_ANCHOR_LONG_PCT

    # Guard before the log: hours <= 0 has no logarithm, and both ends are clamped
    # so the curve never extrapolates past its anchors.
    if hours <= lo_h:
        return lo_pct
    if hours >= hi_h:
        return hi_pct

    # Logarithmic in the window length, not linear. Evidence grows multiplicatively:
    # 24h -> 48h is a doubling and should move the bar as much as 84h -> 168h does.
    # Linear interpolation under-rewarded the first doublings (24h -> 48h moved the
    # threshold only 4.2pp) and over-rewarded the last ones.
    span = math.log(hi_h / lo_h)
    fraction = math.log(float(hours) / lo_h) / span
    return round(lo_pct + (hi_pct - lo_pct) * fraction, 4)


def insufficient_history_label(hours: float) -> str:
    """Explain the bar this particular window failed, not a generic one."""
    return f"Insufficient History (<{coverage_threshold_for(hours):.1f}%)"


INSUFFICIENT_HISTORY_LABEL = "Insufficient History (<70%)"
MS_PER_HOUR = 3_600_000.0


def load_funding_series(
    coin: str,
    hours: float = 72.0,
    repo: Optional[MarketRepository] = None,
    now_ms: Optional[int] = None,
) -> List[Tuple[int, float, float]]:
    """
    (timestamp_ms, funding_rate, mark_px) for one coin, oldest first.

    Reads `asset_snapshots` directly: this is the one consumer that wants history
    rather than current state, so it deliberately does not use latest_snapshots.
    """
    repo = repo or MarketRepository()
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    cutoff = now_ms - int(hours * MS_PER_HOUR)
    sql = """
        SELECT timestamp, funding_rate, mark_px
        FROM asset_snapshots
        WHERE coin = ? AND timestamp >= ?
        ORDER BY timestamp ASC;
    """
    with repo.db.connection as conn:
        rows = conn.execute(sql, (coin, cutoff)).fetchall()
    return [
        (int(r["timestamp"]), float(r["funding_rate"] or 0.0), float(r["mark_px"] or 0.0))
        for r in rows
    ]


def backtest_funding_harvest(
    coin: str,
    hours: float = 72.0,
    side: str = "auto",
    max_gap_hours: float = DEFAULT_MAX_GAP_HOURS,
    is_spot_backed: bool = False,
    repo: Optional[MarketRepository] = None,
    series: Optional[List[Tuple[int, float, float]]] = None,
    now_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Replay a funding harvest over the retained history for one coin.

    Args:
        side: 'short' (collect positive funding), 'long' (collect negative
            funding), or 'auto' to pick whichever the mean rate favours.
        is_spot_backed: when True the price leg is assumed hedged and excluded
            from net PnL; when False the unhedged mark move is included.
        max_gap_hours: intervals longer than this count as unobserved.

    Returns a dict whose `net_pnl_pct` is the return on notional over the
    observed window - not annualised, because annualising a partial window is
    how a 30-hour sample becomes a fictitious yearly number.
    """
    series = series if series is not None else load_funding_series(coin, hours, repo, now_ms)

    result: Dict[str, Any] = {
        "coin": coin,
        "requested_hours": hours,
        "samples": len(series),
        "observed_hours": 0.0,
        "gap_hours": 0.0,
        "coverage_pct": 0.0,
        "funding_pnl_pct": 0.0,
        "price_pnl_pct": 0.0,
        "net_pnl_pct": 0.0,
        "side": None,
        "mean_funding_1h": 0.0,
        "realised_apr": None,
        "realised_apr_label": insufficient_history_label(hours),
        "coverage_threshold_pct": coverage_threshold_for(hours),
        "funding_payments": 0,
        "start_px": None,
        "end_px": None,
        "is_spot_backed": is_spot_backed,
        "sufficient_data": False,
    }
    if len(series) < 2:
        return result

    # Time-weighted funding accrual, in "rate x hours" units.
    accrual = 0.0
    observed_h = 0.0
    gap_h = 0.0
    weighted_rate_sum = 0.0

    for (t0, r0, _), (t1, _, _) in zip(series, series[1:]):
        dt_h = (t1 - t0) / MS_PER_HOUR
        if dt_h <= 0:
            continue
        if dt_h > max_gap_hours:
            gap_h += dt_h
            continue
        # r0 is the rate in force over [t0, t1); a 1h rate held for dt hours.
        accrual += r0 * (dt_h / ARB_FUNDING_INTERVAL_HOURS)
        weighted_rate_sum += r0 * dt_h
        observed_h += dt_h

    if observed_h <= 0:
        result["gap_hours"] = round(gap_h, 4)
        return result

    mean_rate = weighted_rate_sum / observed_h

    chosen = side.lower()
    if chosen == "auto":
        chosen = "short" if mean_rate >= 0 else "long"

    # A short collects positive funding; a long collects negative funding.
    funding_pnl_pct = (accrual if chosen == "short" else -accrual) * 100.0

    start_px = next((px for _, _, px in series if px > 0), 0.0)
    end_px = next((px for _, _, px in reversed(series) if px > 0), 0.0)
    price_move_pct = ((end_px - start_px) / start_px * 100.0) if start_px > 0 else 0.0
    # Short profits when price falls.
    price_pnl_pct = -price_move_pct if chosen == "short" else price_move_pct

    net_pnl_pct = funding_pnl_pct if is_spot_backed else funding_pnl_pct + price_pnl_pct

    coverage_pct = round(min(100.0, observed_h / hours * 100.0), 2) if hours > 0 else 0.0
    threshold = coverage_threshold_for(hours)

    result.update({
        "observed_hours": round(observed_h, 4),
        "gap_hours": round(gap_h, 4),
        "coverage_pct": coverage_pct,
        "funding_pnl_pct": round(funding_pnl_pct, 6),
        "price_pnl_pct": round(price_pnl_pct, 6),
        "net_pnl_pct": round(net_pnl_pct, 6),
        "side": chosen,
        "mean_funding_1h": mean_rate,
        # Extrapolating the observed window to a year, but only when enough of the
        # window was actually observed to make that extrapolation defensible.
        "realised_apr": (
            round(funding_pnl_pct * (8760.0 / observed_h), 4)
            if coverage_pct >= threshold else None
        ),
        "realised_apr_label": (
            None if coverage_pct >= threshold else insufficient_history_label(hours)
        ),
        "coverage_threshold_pct": threshold,
        "funding_payments": int(observed_h / ARB_FUNDING_INTERVAL_HOURS),
        "start_px": start_px,
        "end_px": end_px,
        "sufficient_data": observed_h >= min(1.0, hours * 0.1),
    })
    return result


def rank_funding_backtests(
    coins: Optional[List[str]] = None,
    hours: float = 72.0,
    top_n: int = 20,
    min_coverage_pct: float = 25.0,
    repo: Optional[MarketRepository] = None,
    is_spot_backed: bool = False,
    now_ms: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Backtest many coins and rank by realised funding PnL.

    Ranks on `funding_pnl_pct` - the harvest itself - rather than net, so a coin
    is not promoted for a lucky directional move it would not repeat. Results
    below `min_coverage_pct` are dropped: too little observed time to trust.
    """
    repo = repo or MarketRepository()
    if coins is None:
        coins = [s["coin"] for s in repo.get_latest_snapshots()]

    out = []
    for coin in coins:
        res = backtest_funding_harvest(
            coin, hours=hours, repo=repo, is_spot_backed=is_spot_backed, now_ms=now_ms
        )
        if not res["sufficient_data"] or res["coverage_pct"] < min_coverage_pct:
            continue
        out.append(res)

    out.sort(key=lambda r: abs(r["funding_pnl_pct"]), reverse=True)
    return out[:top_n]


def summarise_coverage(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate data-quality view over a batch of backtests."""
    if not results:
        return {"coins": 0, "mean_coverage_pct": 0.0, "total_gap_hours": 0.0, "observed_hours": 0.0}
    return {
        "coins": len(results),
        "mean_coverage_pct": round(sum(r["coverage_pct"] for r in results) / len(results), 2),
        "total_gap_hours": round(sum(r["gap_hours"] for r in results), 2),
        "observed_hours": round(max(r["observed_hours"] for r in results), 2),
    }
