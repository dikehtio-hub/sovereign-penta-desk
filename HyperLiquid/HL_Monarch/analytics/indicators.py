"""
Technical indicators computed from the retained mark-price snapshot series.

WHAT THIS DATA ACTUALLY IS - read before trusting a number out of here.
`asset_snapshots` stores point samples of `mark_px` (~370/hour), not OHLC candles.
There is no true high or low for any interval, so:

  * ATR here is a *close-to-close* range proxy. It systematically UNDERSTATES a
    real ATR, which includes intra-interval extremes. Anything sized off it is
    sized off a floor, not a true volatility estimate.
  * RSI is computed on resampled marks rather than candle closes. It is directionally
    the same measure but will not tie out against a charting package's RSI.

Both are usable as *regime filters* - "is this market trending, is it stretched" -
which is what they are used for. Neither should be presented as an exchange-grade
indicator value.

Sampling is irregular (the collector has gaps), so every series is resampled onto a
fixed grid before any period-based maths. Otherwise "14 periods" would mean a
different amount of wall-clock time for every coin and every window.
"""

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from storage.repository import MarketRepository

MS_PER_MINUTE = 60_000.0


def load_mark_series(
    coin: str,
    minutes: float,
    repo: Optional[MarketRepository] = None,
    now_ms: Optional[int] = None,
) -> List[Tuple[int, float]]:
    """(timestamp_ms, mark_px) for one coin over the trailing window, oldest first."""
    repo = repo or MarketRepository()
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    cutoff = now_ms - int(minutes * MS_PER_MINUTE)
    sql = """
        SELECT timestamp, mark_px
        FROM asset_snapshots
        WHERE coin = ? AND timestamp >= ? AND mark_px > 0
        ORDER BY timestamp ASC;
    """
    with repo.db.connection as conn:
        rows = conn.execute(sql, (coin, cutoff)).fetchall()
    return [(int(r["timestamp"]), float(r["mark_px"])) for r in rows]


def resample(series: Sequence[Tuple[int, float]], bucket_minutes: float) -> List[float]:
    """
    Collapse an irregular series onto fixed buckets, taking the last value in each.

    Without this, "14 periods" would mean whatever wall-clock span the sampler
    happened to cover - which differs per coin and per outage.
    """
    if not series:
        return []
    bucket_ms = bucket_minutes * MS_PER_MINUTE
    out: List[float] = []
    current_bucket = None
    last_value = None
    for ts, px in series:
        b = int(ts // bucket_ms)
        if current_bucket is None:
            current_bucket = b
        elif b != current_bucket:
            out.append(last_value)
            current_bucket = b
        last_value = px
    if last_value is not None:
        out.append(last_value)
    return out


def resample_ohlc(series: Sequence[Tuple[int, float]],
                  bucket_minutes: float) -> List[Tuple[float, float, float]]:
    """
    Collapse an irregular series into (high, low, close) per fixed bucket.

    The samples inside a bucket ARE the intra-bar extremes, to the resolution the
    collector achieved (~67 samples per 15m bucket in practice). That is a far
    better high/low estimate than pretending each bucket is a single point, and
    unlike a global fudge factor it adapts per market: the measured
    true-range/close-to-close ratio across the watchlist spans 1.39 (xyz:CRWD) to
    1.98 (INJ), so no one constant is right for both.

    It still UNDERSTATES the true continuous range - sampling misses extremes
    between samples - so ATR built on it remains a floor, not a ceiling.
    """
    if not series:
        return []
    bucket_ms = bucket_minutes * MS_PER_MINUTE
    out: List[Tuple[float, float, float]] = []
    current = None
    hi = lo = last = None
    for ts, px in series:
        b = int(ts // bucket_ms)
        if current is None:
            current = b
            hi = lo = px
        elif b != current:
            out.append((hi, lo, last))
            current = b
            hi = lo = px
        else:
            hi = px if px > hi else hi
            lo = px if px < lo else lo
        last = px
    if last is not None:
        out.append((hi, lo, last))
    return out


def atr_pct_true_range(bars: Sequence[Tuple[float, float, float]],
                       period: int = 14) -> Optional[float]:
    """
    ATR as a PERCENT of the last close, using sampled true range.

        TR = max(high - low, |high - prev_close|, |low - prev_close|)

    This is the standard definition, so it captures gaps between buckets as well
    as intra-bucket travel. Prefer it over `atr_pct`: the close-to-close proxy
    understates measured true range by ~1.6x on this watchlist, which sizes every
    offset and target off a number that is known to be too small.
    """
    if period <= 0 or len(bars) < period + 1:
        return None
    trs: List[float] = []
    for (hi, lo, _c), (_ph, _pl, pc) in zip(bars[1:], bars[:-1]):
        trs.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
    window = trs[-period:]
    if not window:
        return None
    last = bars[-1][2]
    if last <= 0:
        return None
    return sum(window) / len(window) / last * 100.0


def ema(values: Sequence[float], period: int) -> Optional[float]:
    """
    Exponential moving average, seeded with the SMA of the first `period` values.

    Returns None when there is not a full period of data - a partial EMA reads as
    a real number while carrying almost none of the smoothing it implies.
    """
    if period <= 0 or len(values) < period:
        return None
    seed = sum(values[:period]) / period
    k = 2.0 / (period + 1.0)
    out = seed
    for v in values[period:]:
        out = v * k + out * (1.0 - k)
    return out


def rsi(values: Sequence[float], period: int = 14) -> Optional[float]:
    """
    Wilder's RSI. Returns None without `period + 1` values to difference.

    A market that only rose over the window has no losses to divide by; that is
    reported as 100.0 rather than as a division error.
    """
    if period <= 0 or len(values) < period + 1:
        return None
    gains, losses = [], []
    for prev, cur in zip(values, values[1:]):
        change = cur - prev
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period

    if avg_loss <= 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr_pct(values: Sequence[float], period: int = 14) -> Optional[float]:
    """
    Average true range as a PERCENT of the latest price (e.g. 1.5 == 1.5%).

    Close-to-close only - see the module docstring. Returned as a percent rather
    than a fraction because every other threshold in this codebase is a percent,
    and mixing the two is how an offset ends up 100x wrong.
    """
    if period <= 0 or len(values) < period + 1:
        return None
    ranges = [abs(cur - prev) for prev, cur in zip(values, values[1:])]
    window = ranges[-period:]
    if not window:
        return None
    atr = sum(window) / len(window)
    last = values[-1]
    if last <= 0:
        return None
    return atr / last * 100.0


def compute_regime(
    coin: str,
    repo: Optional[MarketRepository] = None,
    now_ms: Optional[int] = None,
    ema_period: int = 50,
    rsi_period: int = 14,
    atr_period: int = 14,
    bucket_minutes: float = 1.0,
    lookback_minutes: float = 240.0,
    series: Optional[Sequence[Tuple[int, float]]] = None,
    use_true_range: bool = True,
) -> Dict[str, Any]:
    """
    Trend/stretch/volatility snapshot for one market.

    `sufficient` is the caller's gate: with a thin or gappy series the indicators
    come back None and the filter must fall back to a documented default rather
    than silently treating "unknown" as "permitted".
    """
    raw = series if series is not None else load_mark_series(coin, lookback_minutes, repo, now_ms)
    closes = resample(raw, bucket_minutes)

    price = closes[-1] if closes else None
    e = ema(closes, ema_period)
    r = rsi(closes, rsi_period)
    # True range by default. Trend and stretch read off closes (that is what EMA
    # and RSI are defined on); only volatility needs the intra-bar extremes.
    if use_true_range:
        a = atr_pct_true_range(resample_ohlc(raw, bucket_minutes), atr_period)
    else:
        a = atr_pct(closes, atr_period)

    return {
        "coin": coin,
        "samples": len(raw),
        "buckets": len(closes),
        "price": price,
        "ema": e,
        "rsi": r,
        "atr_pct": a,
        "atr_method": "true_range" if use_true_range else "close_to_close",
        "above_ema": (price >= e) if (price is not None and e is not None) else None,
        "sufficient": all(v is not None for v in (price, e, r, a)),
    }
