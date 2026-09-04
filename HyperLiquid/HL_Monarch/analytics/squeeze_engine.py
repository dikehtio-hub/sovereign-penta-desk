"""
Squeeze & Funding Exhaustion Engine.

Targets the 86% of Hyperliquid perps that have **no spot leg**, where a funding
harvest is not a basis arbitrage but a directional bet. For those markets the
interesting question is not "what yield can I lock in" but "is this positioning
about to break".

The setup this looks for is crowding plus exhaustion:

  * **Funding percentile** - where the current rate sits within this asset's own
    recent history. An absolute rate says nothing; +0.05%/h is unremarkable for a
    perpetually hot memecoin and extraordinary for an index perp. Ranking each
    asset against itself removes that cross-sectional noise.
  * **OI expansion** - open interest growing while funding stays extreme means
    fresh money is still piling into the crowded side, not capitulating.
  * **Persistence** - how long the rate has held its sign. A single extreme print
    is noise; hours of sustained payment is a crowd paying to stay wrong.

A crowded, well-paid, still-expanding position is what unwinds violently:

  * Persistently **positive** funding = longs paying shorts = crowded long, which
    breaks *downward* as longs are forced out -> `LONG CASCADE WATCH`.
  * Persistently **negative** funding = shorts paying longs = crowded short, which
    breaks *upward* -> `SHORT SQUEEZE WATCH`.

This is a directional-risk radar, not a signal to trade. It scores how stretched
positioning is; it says nothing about timing.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from storage.repository import MarketRepository
from config.settings import (
    SQUEEZE_LOOKBACK_HOURS,
    SQUEEZE_MIN_SAMPLES,
    SQUEEZE_MIN_NOTIONAL_OI,
    SQUEEZE_WATCH_THRESHOLD,
    SQUEEZE_EXHAUSTION_PERSISTENCE,
    SQUEEZE_EXHAUSTION_LOW_PCT,
    SQUEEZE_EXHAUSTION_HIGH_PCT,
)

MS_PER_HOUR = 3_600_000.0

CLASS_SHORT_SQUEEZE = "🔥 SHORT SQUEEZE WATCH"
CLASS_LONG_CASCADE = "💧 LONG CASCADE WATCH"
CLASS_NEUTRAL = "— NEUTRAL"


def load_squeeze_series(
    coin: str,
    hours: float = SQUEEZE_LOOKBACK_HOURS,
    repo: Optional[MarketRepository] = None,
    now_ms: Optional[int] = None,
) -> List[Tuple[int, float, float, float]]:
    """(timestamp_ms, funding_rate, notional_oi, mark_px) for one coin, oldest first."""
    repo = repo or MarketRepository()
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    cutoff = now_ms - int(hours * MS_PER_HOUR)
    sql = """
        SELECT timestamp, funding_rate, notional_oi, mark_px
        FROM asset_snapshots
        WHERE coin = ? AND timestamp >= ?
        ORDER BY timestamp ASC;
    """
    with repo.db.connection as conn:
        rows = conn.execute(sql, (coin, cutoff)).fetchall()
    return [
        (
            int(r["timestamp"]),
            float(r["funding_rate"] or 0.0),
            float(r["notional_oi"] or 0.0),
            float(r["mark_px"] or 0.0),
        )
        for r in rows
    ]


def percentile_rank(values: List[float], target: float) -> float:
    """
    Where `target` sits within `values`, as 0-100.

    Uses the midpoint convention (ties count half), so a series of identical
    readings ranks at 50 rather than 0 or 100 - a flat rate is neither extreme.
    """
    if not values:
        return 50.0
    below = sum(1 for v in values if v < target)
    equal = sum(1 for v in values if v == target)
    return (below + 0.5 * equal) / len(values) * 100.0


def compute_oi_expansion(series: List[Tuple[int, float, float, float]]) -> float:
    """
    Percent change in open interest from the start of the window to now.

    Positive means positioning is still being added - the crowd has not started
    unwinding yet, which is what keeps a squeeze loaded.
    """
    ois = [oi for _, _, oi, _ in series if oi > 0]
    if len(ois) < 2 or ois[0] <= 0:
        return 0.0
    return (ois[-1] - ois[0]) / ois[0] * 100.0


def compute_funding_persistence(series: List[Tuple[int, float, float, float]]) -> float:
    """
    Fraction (0-1) of the observed window the funding rate held its current sign.

    A crowd that has been paying continuously is far more stretched than one that
    flipped sign an hour ago.
    """
    rates = [fr for _, fr, _, _ in series]
    if not rates:
        return 0.0
    current_sign = 1 if rates[-1] > 0 else (-1 if rates[-1] < 0 else 0)
    if current_sign == 0:
        return 0.0
    same = sum(1 for r in rates if (r > 0) == (current_sign > 0) and r != 0)
    return same / len(rates)


def is_exhausting(
    funding_percentile: float,
    mean_funding: float,
    persistence: float,
    min_persistence: float = SQUEEZE_EXHAUSTION_PERSISTENCE,
    low_band: float = SQUEEZE_EXHAUSTION_LOW_PCT,
    high_band: float = SQUEEZE_EXHAUSTION_HIGH_PCT,
) -> bool:
    """
    Detect an *active unwind*: a long-sustained regime whose funding has just broken.

    Distinct from a low squeeze score. A low score means "never crowded"; exhaustion
    means "was heavily crowded and the crowd is now paying up to leave". The crowd
    must first have been committed (`persistence > 0.75`), then the rate must have
    collapsed out of its regime:

      * mean funding positive (crowded longs) and the current rate has fallen below
        the 35th percentile - longs have stopped paying, i.e. they are exiting.
      * mean funding negative (crowded shorts) and the rate has risen above the
        65th percentile - shorts are covering.

    Bands are asymmetric on purpose relative to the 50th: a rate merely drifting to
    the median is not an unwind, it has to break decisively out of its own range.
    """
    if persistence <= min_persistence:
        return False
    if mean_funding > 0:
        return funding_percentile < low_band
    if mean_funding < 0:
        return funding_percentile > high_band
    return False


def is_regime_aligned(funding_percentile: float, mean_funding: float) -> bool:
    """
    True when the current rate is extreme in the SAME direction as the regime.

    An asset whose mean funding is positive but whose current rate sits at its
    24h *low* is not a crowded long - it is a crowded long that has already
    started paying less, i.e. unwinding. Folding percentile to a bare distance
    from 50 would score those two opposite situations identically.
    """
    if mean_funding > 0:
        return funding_percentile >= 50.0
    if mean_funding < 0:
        return funding_percentile <= 50.0
    return False


def compute_squeeze_score(
    funding_percentile: float,
    oi_expansion_pct: float,
    persistence: float,
    abs_funding_apr: float,
    mean_funding: float = 0.0,
) -> float:
    """
    Blend the components into a 0-100 stretch score.

    Weighting reflects how much each says about *fragility* rather than mere
    activity:
      * 40% extremity of funding vs this asset's own history - the crowding signal
      * 25% persistence - a crowd that has paid for hours, not minutes
      * 20% OI expansion - fresh money still entering the crowded side
      * 15% absolute funding cost - saturating at 200% APR, since beyond that the
        pain is already extraordinary and more does not add information

    Extremity counts only when it points the same way as the sustained regime
    (see `is_regime_aligned`). A rate that has retreated toward neutral is
    exhaustion, not crowding, and contributes no extremity - which is what stops
    a decaying market from scoring as a loaded one.
    """
    aligned = is_regime_aligned(funding_percentile, mean_funding)
    extremity = (abs(funding_percentile - 50.0) / 50.0) if aligned else 0.0
    expansion = max(0.0, min(1.0, oi_expansion_pct / 50.0))       # +50% OI -> 1.0
    persistence = max(0.0, min(1.0, persistence))
    magnitude = max(0.0, min(1.0, abs_funding_apr / 200.0))       # 200% APR -> 1.0

    score = (
        extremity * 40.0
        + persistence * 25.0
        + expansion * 20.0
        + magnitude * 15.0
    )
    return round(max(0.0, min(100.0, score)), 2)


def classify_squeeze(mean_funding: float, score: float,
                     threshold: float = SQUEEZE_WATCH_THRESHOLD) -> str:
    """
    Name the direction the crowded side would break.

    Positive funding means longs are paying, so longs are the crowded side and the
    unwind is downward (a cascade). Negative funding means shorts are paying, and
    that unwind is upward (a squeeze).
    """
    if score < threshold or mean_funding == 0.0:
        return CLASS_NEUTRAL
    return CLASS_LONG_CASCADE if mean_funding > 0 else CLASS_SHORT_SQUEEZE


def analyse_coin(
    coin: str,
    hours: float = SQUEEZE_LOOKBACK_HOURS,
    repo: Optional[MarketRepository] = None,
    series: Optional[List[Tuple[int, float, float, float]]] = None,
    now_ms: Optional[int] = None,
    is_spot_backed: Optional[bool] = None,
    min_samples: int = SQUEEZE_MIN_SAMPLES,
) -> Dict[str, Any]:
    """Score one asset's positioning stretch over the lookback window."""
    series = series if series is not None else load_squeeze_series(coin, hours, repo, now_ms)

    result: Dict[str, Any] = {
        "coin": coin,
        "samples": len(series),
        "squeeze_score": 0.0,
        "classification": CLASS_NEUTRAL,
        "funding_percentile": 50.0,
        "oi_expansion_pct": 0.0,
        "persistence": 0.0,
        "regime_aligned": False,
        "is_exhausting": False,
        "current_funding_1h": 0.0,
        "current_funding_apr": 0.0,
        "notional_oi": 0.0,
        "mark_px": 0.0,
        "is_spot_backed": is_spot_backed,
        "sufficient_data": False,
    }
    if len(series) < min_samples:
        return result

    rates = [fr for _, fr, _, _ in series]
    current = rates[-1]
    mean_rate = sum(rates) / len(rates)
    pct = percentile_rank(rates, current)
    expansion = compute_oi_expansion(series)
    persistence = compute_funding_persistence(series)
    apr = current * 24 * 365 * 100.0

    score = compute_squeeze_score(pct, expansion, persistence, abs(apr), mean_funding=mean_rate)
    aligned = is_regime_aligned(pct, mean_rate)
    exhausting = is_exhausting(pct, mean_rate, persistence)
    # Direction comes from the mean, not the last tick: one print against a
    # sustained regime should not flip the label.
    classification = classify_squeeze(mean_rate, score)

    result.update({
        "squeeze_score": score,
        "classification": classification,
        "funding_percentile": round(pct, 2),
        "oi_expansion_pct": round(expansion, 2),
        "persistence": round(persistence, 4),
        "regime_aligned": aligned,
        # A committed crowd whose funding has broken out of its own regime -
        # an unwind in progress, not merely an uncrowded market.
        "is_exhausting": exhausting,
        "current_funding_1h": current,
        "current_funding_apr": round(apr, 2),
        "mean_funding_1h": mean_rate,
        "notional_oi": series[-1][2],
        "mark_px": series[-1][3],
        "sufficient_data": True,
    })
    return result


def scan_squeeze_candidates(
    snapshots: Optional[List[Dict[str, Any]]] = None,
    hours: float = SQUEEZE_LOOKBACK_HOURS,
    repo: Optional[MarketRepository] = None,
    top_n: int = 15,
    min_notional_oi: float = SQUEEZE_MIN_NOTIONAL_OI,
    exotic_only: bool = True,
    spot_universe: Optional[set] = None,
    now_ms: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Rank assets by squeeze score.

    Args:
        exotic_only: restrict to perps with no spot leg. Those are exactly the
            markets the funding-arb matrix cannot serve, since without a hedge
            the trade is directional - which is what this engine is about.
        spot_universe: pass a pre-fetched spot token set to avoid a network call;
            when omitted and `exotic_only` is set, it is fetched once.
    """
    repo = repo or MarketRepository()
    if snapshots is None:
        snapshots = repo.get_latest_snapshots()

    if exotic_only and spot_universe is None:
        try:
            from analytics.funding_arbitrage import FundingArbitrageEngine
            spot_universe = FundingArbitrageEngine().get_spot_universe()
        except Exception:
            spot_universe = set()
    spot_universe = spot_universe or set()

    from analytics.funding_arbitrage import spot_symbol_for

    out: List[Dict[str, Any]] = []
    for snap in snapshots:
        coin = snap.get("coin", "")
        if float(snap.get("notional_oi") or 0.0) < min_notional_oi:
            continue
        backed = spot_symbol_for(coin, spot_universe) is not None
        if exotic_only and backed:
            continue
        res = analyse_coin(coin, hours=hours, repo=repo, now_ms=now_ms, is_spot_backed=backed)
        if not res["sufficient_data"]:
            continue
        out.append(res)

    out.sort(key=lambda r: r["squeeze_score"], reverse=True)
    return out[:top_n]


def summarise_squeeze(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts by classification, for a headline line above the matrix."""
    return {
        "scanned": len(results),
        "short_squeeze": sum(1 for r in results if r["classification"] == CLASS_SHORT_SQUEEZE),
        "long_cascade": sum(1 for r in results if r["classification"] == CLASS_LONG_CASCADE),
        "neutral": sum(1 for r in results if r["classification"] == CLASS_NEUTRAL),
        "max_score": max((r["squeeze_score"] for r in results), default=0.0),
    }
