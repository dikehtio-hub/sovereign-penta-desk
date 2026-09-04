"""
Incremental measurement persistence: unbounded statistical history at flat disk cost.

THE PROBLEM. Raw snapshots run ~12M rows/day and are pruned at 192h (Round 33).
Ruling D asks for 720 hours of observation across at least two market regimes
before the basis edge is called enduring. 720h cannot be held in a 192h window
at any disk size, so the measurements have to outlive the rows they are made
from. This module reduces the raw rows to the two things the walk-forward
actually consumes - BEFORE the pruner deletes them - and never prunes the result:

    basis_realised_windows   what a delta-neutral basis position entered at a
                             given instant realised over a given hold
    cascade_excursions       how far a liquidation cascade moved for and against
                             a fade over 5/15/30/60 minutes, plus a matched
                             random-entry control per event

RULES THAT KEEP THE TABLES HONEST.
  * A window that could not be measured is NULL, never zero. A zero excursion or
    a zero realised rate is a real measurement and must not be confused with a
    missing one - the same rule wick_benchmark and the funding backtester apply.
  * Entries sit on a fixed epoch-aligned grid, and the table is UNIQUE on
    (asset, hold, entry). Re-running lands on the same instants; a duplicate is
    impossible rather than merely unlikely.
  * Anything whose forward window reaches into rows that are already gone is
    SKIPPED AND COUNTED, not reconstructed. A gap in the persisted history is a
    visible gap - `windows_unobserved` / `events_unretained` in every report.
  * The two liquidation sources are never pooled. `source` is a column, and the
    control rows carry `control:<source>` so a signal is only ever read against
    its own matched control.
  * Watermarks advance only over work that was actually done, so a pass that is
    capped (the collector gives maintenance a few seconds every five minutes)
    resumes exactly where it stopped. `python main.py persist --backfill` loops
    until caught up.

WHAT `regime_tag` IS. Ruling D's "two regimes" needs a definition that is cheap
to compute at every entry instant and does not depend on the coin being
measured. It is read off the reference coin (BTC) over the trailing 24h:
realised daily volatility bucketed LOW / MID / HIGH and time-weighted funding
bucketed NEG / FLAT / HOT, joined as e.g. `VOL_MID|FUND_HOT`. The thresholds are
engineering estimates recorded in settings; the underlying numbers are stored
on every row so a future re-bucketing needs no raw data. `UNKNOWN` when the
reference series is too thin, and UNKNOWN never counts toward the two.

WHAT THIS DOES NOT DO. It does not fabricate an execution cost. `orderbook_
snapshots` is the only measured spread in the repo, and `net_apr_after_fees` is
filled only from it (`fee_basis = 'measured'`); otherwise it is NULL and the row
says `unmeasured`. A default spread would turn every window into a number nobody
measured, which is the exact placeholder failure Round 33 removed elsewhere.
"""

from __future__ import annotations

import logging
import math
import random
import statistics
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from config.settings import (
    ARB_FUNDING_INTERVAL_HOURS,
    EXCURSION_CONTROL_MULTIPLE,
    EXCURSION_PERSIST_HORIZONS_MINUTES,
    EXCURSION_PERSIST_MIN_NOTIONAL,
    EXCURSION_PERSIST_SOURCES,
    MEASUREMENT_ENTRY_STRIDE_HOURS,
    MEASUREMENT_HOLD_HOURS,
    MEASUREMENT_MAX_EVENTS_PER_PASS,
    MEASUREMENT_MAX_GAP_HOURS,
    MEASUREMENT_MAX_GRID_POINTS_PER_PASS,
    MEASUREMENT_MIN_COVERAGE,
    REGIME_FUNDING_BUCKETS,
    REGIME_LOOKBACK_HOURS,
    REGIME_MIN_HOURLY_BUCKETS,
    REGIME_REFERENCE_COIN,
    REGIME_VOL_BUCKETS,
    RULING_D_MIN_HOURS_PER_REGIME,
    RULING_D_MIN_REGIMES,
    RULING_D_REQUIRED_HOURS,
    SNAPSHOT_RETENTION_HOURS,
    TRADE_RETENTION_HOURS,
)
from storage.measurement_schema import MEASUREMENT_SCHEMA_SQL

logger = logging.getLogger("Persistence")

MS_H = 3_600_000.0
MS_MIN = 60_000.0
HOURS_PER_YEAR = 8760.0
JOB_CASCADES = "cascade_excursions"
# The columns the schema carries. A horizon outside this set has nowhere to go
# and is refused loudly rather than silently dropped.
SCHEMA_HORIZONS: Tuple[float, ...] = (5.0, 15.0, 30.0, 60.0)
CONTROL_PREFIX = "control:"
# A spot-backed basis trade pays the spread on BOTH legs - see
# FundingArbitrageEngine.net_apr_after_spread and the Round 33 correction.
BASIS_HEDGE_LEGS = 2


def basis_job(hold_hours: float) -> str:
    return "basis_windows_%gh" % float(hold_hours)


def control_source(source: str) -> str:
    return CONTROL_PREFIX + source


# ---------------------------------------------------------------------------
# Schema and watermarks
# ---------------------------------------------------------------------------

def ensure_schema(conn) -> None:
    conn.executescript(MEASUREMENT_SCHEMA_SQL)


def get_watermark(conn, job: str) -> Optional[int]:
    row = conn.execute("SELECT watermark FROM measurement_watermarks WHERE job = ?",
                       (job,)).fetchone()
    return int(row[0]) if row is not None else None


def set_watermark(conn, job: str, value: int, now_ms: Optional[int] = None,
                  note: Optional[str] = None) -> None:
    """
    Monotonic: a watermark never moves backwards. The collector's bounded pass
    and a CLI backfill can run at once; whichever finishes an older instant last
    must not undo the other's progress (the inserts are OR IGNORE, so the only
    cost of a race is repeated work, never a duplicate row).
    """
    conn.execute(
        "INSERT INTO measurement_watermarks (job, watermark, updated_at, note) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(job) DO UPDATE SET watermark = MAX(watermark, excluded.watermark), "
        "updated_at = excluded.updated_at, note = COALESCE(excluded.note, note)",
        (job, int(value), int(now_ms or time.time() * 1000), note))


def entry_grid(start_ms: int, end_ms: int, stride_hours: float) -> List[int]:
    """
    Entry instants on a fixed epoch-aligned grid: every multiple of the stride
    in [start, end]. Aligned to the epoch, not to `start`, so two runs that
    begin at different moments still land on the same instants.
    """
    stride = int(stride_hours * MS_H)
    if stride <= 0 or end_ms < start_ms:
        return []
    first = ((int(start_ms) + stride - 1) // stride) * stride
    if first > end_ms:
        return []
    return list(range(first, int(end_ms) + 1, stride))


# ---------------------------------------------------------------------------
# Per-window measurement
# ---------------------------------------------------------------------------

def funding_window_stats(conn, coin: str, start_ms: int, end_ms: int,
                         max_gap_hours: float = MEASUREMENT_MAX_GAP_HOURS) -> Dict[str, Any]:
    """
    Time-integrated funding over [start, end], aggregated INSIDE SQLite.

    Integrated by time, not averaged over samples, so a burst of dense sampling
    cannot outvote a long quiet stretch; intervals longer than the gap tolerance
    are dropped from both the accrual and the coverage rather than extrapolated
    across. Identical semantics to funding_backtester and the Round 32 script,
    pushed into the engine because a 7-day window is ~190k rows per coin and a
    Python loop over 440 coins would not fit inside a maintenance pass.
    """
    gap_ms = int(max_gap_hours * MS_H)
    row = conn.execute(
        """
        WITH s AS (
            SELECT timestamp, funding_rate,
                   LEAD(timestamp) OVER (ORDER BY timestamp) AS next_ts
            FROM asset_snapshots
            WHERE coin = ? AND timestamp >= ? AND timestamp <= ? AND funding_rate IS NOT NULL
        )
        SELECT COUNT(*),
               COALESCE(SUM(CASE WHEN next_ts IS NOT NULL AND next_ts - timestamp <= ?
                                 THEN funding_rate * (next_ts - timestamp) END), 0.0),
               COALESCE(SUM(CASE WHEN next_ts IS NOT NULL AND next_ts - timestamp <= ?
                                 THEN next_ts - timestamp END), 0),
               MIN(timestamp), MAX(timestamp)
        FROM s
        """,
        (coin, int(start_ms), int(end_ms), gap_ms, gap_ms),
    ).fetchone()
    samples = int(row[0] or 0)
    return {
        "samples": samples,
        # sum(rate x dt) in rate-hours: the funding fraction actually accrued.
        "accrual_rate_hours": float(row[1] or 0.0) / MS_H,
        "observed_hours": float(row[2] or 0) / MS_H,
        "first_ts": int(row[3]) if row[3] is not None else None,
        "last_ts": int(row[4]) if row[4] is not None else None,
    }


def _mark_at_or_after(conn, coin: str, ts_ms: int, limit_ms: int) -> Optional[Tuple[int, float]]:
    row = conn.execute(
        "SELECT timestamp, mark_px FROM asset_snapshots WHERE coin = ? AND timestamp >= ? "
        "AND timestamp <= ? AND mark_px > 0 ORDER BY timestamp ASC LIMIT 1",
        (coin, int(ts_ms), int(limit_ms))).fetchone()
    return (int(row[0]), float(row[1])) if row else None


def _mark_at_or_before(conn, coin: str, ts_ms: int, floor_ms: int) -> Optional[Tuple[int, float]]:
    row = conn.execute(
        "SELECT timestamp, mark_px FROM asset_snapshots WHERE coin = ? AND timestamp <= ? "
        "AND timestamp >= ? AND mark_px > 0 ORDER BY timestamp DESC LIMIT 1",
        (coin, int(ts_ms), int(floor_ms))).fetchone()
    return (int(row[0]), float(row[1])) if row else None


def quote_apr_at(conn, coin: str, ts_ms: int,
                 max_gap_hours: float = MEASUREMENT_MAX_GAP_HOURS) -> Optional[float]:
    """The funding quote in force at `ts`, annualised - or None if the last quote is too old."""
    row = conn.execute(
        "SELECT timestamp, funding_rate FROM asset_snapshots WHERE coin = ? AND timestamp <= ? "
        "AND funding_rate IS NOT NULL ORDER BY timestamp DESC LIMIT 1",
        (coin, int(ts_ms))).fetchone()
    if row is None or (int(ts_ms) - int(row[0])) > max_gap_hours * MS_H:
        return None
    return float(row[1]) * HOURS_PER_YEAR * 100.0


def spread_bps_at(conn, coin: str, ts_ms: int,
                  max_gap_hours: float = MEASUREMENT_MAX_GAP_HOURS) -> Optional[float]:
    """The last MEASURED spread at or before `ts`, or None. Never a default."""
    row = conn.execute(
        "SELECT timestamp, spread_bps FROM orderbook_snapshots WHERE coin = ? AND timestamp <= ? "
        "ORDER BY timestamp DESC LIMIT 1", (coin, int(ts_ms))).fetchone()
    if row is None or row[1] is None or (int(ts_ms) - int(row[0])) > max_gap_hours * MS_H:
        return None
    return float(row[1])


def realised_window(conn, coin: str, start_ms: int, hold_hours: float,
                    max_gap_hours: float = MEASUREMENT_MAX_GAP_HOURS,
                    min_coverage: float = MEASUREMENT_MIN_COVERAGE) -> Dict[str, Any]:
    """
    One delta-neutral basis window: what funding paid from `start` for `hold`.

    `realised_apr` scales the observed accrual to the full window and annualises
    it, and is None when coverage is below the minimum - a 40%-observed week is
    not a week's result. Price is deliberately absent: the position is hedged.
    """
    end_ms = int(start_ms + hold_hours * MS_H)
    stats = funding_window_stats(conn, coin, start_ms, end_ms, max_gap_hours)
    observed = stats["observed_hours"]
    coverage = (observed / hold_hours) if hold_hours > 0 else 0.0
    realised = None
    if observed > 0 and coverage >= min_coverage:
        realised = (stats["accrual_rate_hours"] / observed) * HOURS_PER_YEAR * 100.0
    entry = _mark_at_or_after(conn, coin, start_ms, end_ms) if stats["samples"] else None
    exit_ = _mark_at_or_before(conn, coin, end_ms, start_ms) if stats["samples"] else None
    return {
        "coin": coin,
        "start_ms": int(start_ms),
        "end_ms": end_ms,
        "hold_hours": float(hold_hours),
        "samples": stats["samples"],
        "observed_hours": observed,
        "coverage": min(1.0, coverage),
        "realised_apr": realised,
        "funding_payments": int(observed / ARB_FUNDING_INTERVAL_HOURS),
        "entry_px": entry[1] if entry else None,
        "exit_px": exit_[1] if exit_ else None,
    }


def spread_drag_apr(spread_bps: float, hold_hours: float, legs: int = BASIS_HEDGE_LEGS) -> float:
    """spread% x legs x (365 / holding days) - the Round 33-corrected two-leg drag."""
    days = max(hold_hours / 24.0, 1e-6)
    return (float(spread_bps) / 100.0) * legs * (365.0 / days)


# ---------------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------------

def _bucket(value: float, edges: Sequence[float], labels: Sequence[str]) -> str:
    for edge, label in zip(edges, labels):
        if value < edge:
            return label
    return labels[-1]


def regime_at(conn, ts_ms: int, cache: Optional[Dict[int, Dict[str, Any]]] = None,
              coin: str = REGIME_REFERENCE_COIN,
              lookback_hours: float = REGIME_LOOKBACK_HOURS,
              vol_buckets: Sequence[float] = REGIME_VOL_BUCKETS,
              funding_buckets: Sequence[float] = REGIME_FUNDING_BUCKETS,
              max_gap_hours: float = MEASUREMENT_MAX_GAP_HOURS,
              min_hourly_buckets: int = REGIME_MIN_HOURLY_BUCKETS) -> Dict[str, Any]:
    """
    The market regime at `ts`, read off the reference coin's trailing window.

    Cached per hour bucket because every coin's window at the same grid instant
    shares one regime, and the reference series is ~27k rows per day.
    """
    key = int(ts_ms // MS_H)
    if cache is not None and key in cache:
        return cache[key]
    lo = int(ts_ms - lookback_hours * MS_H)
    rows = conn.execute(
        "SELECT timestamp, mark_px, funding_rate FROM asset_snapshots "
        "WHERE coin = ? AND timestamp > ? AND timestamp <= ? ORDER BY timestamp ASC",
        (coin, lo, int(ts_ms))).fetchall()

    closes: Dict[int, float] = {}
    accrual = observed = 0.0
    prev_ts: Optional[int] = None
    prev_rate: Optional[float] = None
    for row in rows:
        t = int(row[0])
        px = row[1]
        rate = row[2]
        if px is not None and float(px) > 0:
            closes[int(t // MS_H)] = float(px)          # last mark in the hour
        if rate is not None:
            if prev_ts is not None and t > prev_ts:
                dt = (t - prev_ts) / MS_H
                if dt <= max_gap_hours:
                    accrual += float(prev_rate) * dt
                    observed += dt
            prev_ts, prev_rate = t, float(rate)

    out: Dict[str, Any] = {"tag": "UNKNOWN", "vol_pct": None, "funding_apr": None,
                           "hourly_buckets": len(closes), "reference": coin}
    prices = [closes[k] for k in sorted(closes)]
    if len(prices) >= min_hourly_buckets and observed > 0:
        rets = [math.log(b / a) for a, b in zip(prices, prices[1:]) if a > 0 and b > 0]
        if len(rets) >= 2:
            vol = statistics.pstdev(rets) * math.sqrt(24.0) * 100.0
            fund = (accrual / observed) * HOURS_PER_YEAR * 100.0
            out.update({
                "tag": "VOL_%s|FUND_%s" % (_bucket(vol, vol_buckets, ("LOW", "MID", "HIGH")),
                                            _bucket(fund, funding_buckets, ("NEG", "FLAT", "HOT"))),
                "vol_pct": vol,
                "funding_apr": fund,
            })
    if cache is not None:
        cache[key] = out
    return out


# ---------------------------------------------------------------------------
# Materialisers
# ---------------------------------------------------------------------------

def active_coins(conn, since_ms: int) -> List[str]:
    """Coins with a current-state row at or after `since` - the live universe, ~440 names."""
    return [str(r[0]) for r in conn.execute(
        "SELECT coin FROM latest_snapshots WHERE timestamp >= ? ORDER BY coin", (int(since_ms),))]


_BASIS_INSERT = """
INSERT OR IGNORE INTO basis_realised_windows (
    asset, window_start_utc, window_end_utc, hold_hours, quote_apr_entry, realised_apr,
    observed_hours, coverage, funding_payments_count, spread_bps_entry, net_apr_after_fees,
    fee_basis, regime_tag, regime_vol_pct, regime_funding_apr, entry_px, exit_px, samples,
    persisted_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def persist_basis_windows(conn, now_ms: int, hold_hours: float,
                          retention_hours: float = SNAPSHOT_RETENTION_HOURS,
                          stride_hours: float = MEASUREMENT_ENTRY_STRIDE_HOURS,
                          max_grid_points: int = MEASUREMENT_MAX_GRID_POINTS_PER_PASS,
                          max_gap_hours: float = MEASUREMENT_MAX_GAP_HOURS,
                          min_coverage: float = MEASUREMENT_MIN_COVERAGE,
                          regime_cache: Optional[Dict[int, Dict[str, Any]]] = None,
                          coins: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """
    Materialise every (coin, entry) window of one hold whose window has completed.

    An entry qualifies when `entry + hold <= now` (complete) and `entry >= now -
    retention` (its rows still exist). Grid instants are processed whole - every
    coin at one instant - so the watermark never lands in the middle of one.
    """
    job = basis_job(hold_hours)
    stride_ms = int(stride_hours * MS_H)
    hold_ms = int(hold_hours * MS_H)
    cutoff = int(now_ms - retention_hours * MS_H)
    latest_entry = int(now_ms) - hold_ms
    watermark = get_watermark(conn, job)
    start = (watermark + stride_ms) if watermark is not None else cutoff
    start = max(start, cutoff)
    grid = entry_grid(start, latest_entry, stride_hours)
    out: Dict[str, Any] = {
        "job": job, "hold_hours": float(hold_hours), "grid_points": 0,
        "grid_pending": len(grid), "windows_written": 0, "windows_no_entry_quote": 0,
        "windows_unobserved": 0, "windows_low_coverage": 0, "fees_measured": 0,
        "watermark": watermark,
    }
    if not grid:
        return out
    grid = grid[: max(1, int(max_grid_points))]
    universe = list(coins) if coins is not None else active_coins(conn, since_ms=grid[0])
    persisted_at = int(now_ms)

    for entry in grid:
        regime = regime_at(conn, entry, cache=regime_cache)
        rows: List[Tuple[Any, ...]] = []
        for coin in universe:
            # NO QUOTE, NO ENTRY. The harvester acts on the funding quote in force
            # at the instant it opens; an instant with no quote (the coin was not
            # listed yet, or the collector was down) is not a decision anyone
            # could have taken, and measuring a window from it would record an
            # entry that never existed. Asked FIRST because it is one indexed
            # lookup, where the window scan behind it is up to ~70k rows.
            quote = quote_apr_at(conn, coin, entry, max_gap_hours)
            if quote is None:
                out["windows_no_entry_quote"] += 1
                continue
            window = realised_window(conn, coin, entry, hold_hours, max_gap_hours, min_coverage)
            # Unobserved means no measurable INTERVAL - a lone sample sitting on the
            # window's far edge is not an observation of the window.
            if window["samples"] == 0 or window["observed_hours"] <= 0:
                out["windows_unobserved"] += 1
                continue
            spread = spread_bps_at(conn, coin, entry, max_gap_hours)
            realised = window["realised_apr"]
            net, fee_basis = None, "unmeasured"
            if spread is not None and realised is not None:
                drag = spread_drag_apr(spread, hold_hours)
                net = realised - drag if realised > 0 else realised + drag
                fee_basis = "measured"
                out["fees_measured"] += 1
            if realised is None:
                out["windows_low_coverage"] += 1
            rows.append((coin, entry, entry + hold_ms, float(hold_hours), quote, realised,
                         window["observed_hours"], window["coverage"], window["funding_payments"],
                         spread, net, fee_basis, regime["tag"], regime["vol_pct"],
                         regime["funding_apr"], window["entry_px"], window["exit_px"],
                         window["samples"], persisted_at))
        if rows:
            cursor = conn.executemany(_BASIS_INSERT, rows)
            out["windows_written"] += max(0, cursor.rowcount or 0)
        set_watermark(conn, job, entry, now_ms=now_ms)
        out["grid_points"] += 1
        out["watermark"] = entry
        conn.commit()
    out["grid_pending"] -= out["grid_points"]
    return out


_CASCADE_INSERT = """
INSERT OR IGNORE INTO cascade_excursions (
    event_id, coin, timestamp_utc, source, cascade_side, fade_is_long, notional_usd, event_px,
    entry_px, mfe_5m, mae_5m, mfe_15m, mae_15m, mfe_30m, mae_30m, mfe_60m, mae_60m,
    samples_60m, regime_tag, persisted_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _measure_event(conn, excursion: Callable[..., Optional[Dict[str, float]]],
                   coin: str, ts_ms: int, is_long: bool,
                   horizons: Sequence[float], longest_ms: int) -> Dict[str, Any]:
    series = [(int(r[0]), float(r[1])) for r in conn.execute(
        "SELECT timestamp, mark_px FROM asset_snapshots WHERE coin = ? AND mark_px > 0 "
        "AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC",
        (coin, int(ts_ms), int(ts_ms) + longest_ms))]
    values: Dict[float, Tuple[Optional[float], Optional[float]]] = {}
    entry_px: Optional[float] = None
    samples_longest = 0
    measured = False
    for h in horizons:
        result = excursion(series, int(ts_ms), is_long, h) if series else None
        if result is None:
            values[h] = (None, None)
            continue
        values[h] = (result["mfe"], result["mae"])
        entry_px = result["entry_px"]
        measured = True
        if h == max(horizons):
            samples_longest = int(result["samples"])
    if samples_longest == 0:
        samples_longest = max(0, len(series) - 1)
    return {"values": values, "entry_px": entry_px, "samples": samples_longest,
            "measured": measured}


def persist_cascade_excursions(conn, now_ms: int,
                               retention_hours: float = min(SNAPSHOT_RETENTION_HOURS,
                                                            TRADE_RETENTION_HOURS),
                               horizons: Sequence[float] = EXCURSION_PERSIST_HORIZONS_MINUTES,
                               max_events: int = MEASUREMENT_MAX_EVENTS_PER_PASS,
                               sources: Sequence[str] = EXCURSION_PERSIST_SOURCES,
                               min_notional: Optional[Dict[str, float]] = None,
                               control_multiple: int = EXCURSION_CONTROL_MULTIPLE,
                               regime_cache: Optional[Dict[int, Dict[str, Any]]] = None
                               ) -> Dict[str, Any]:
    """
    Materialise forward excursions for every liquidation event whose longest
    window has completed, plus `control_multiple` matched random entries each.

    THE CONTROL IS PERSISTED TOO. wick_benchmark's whole doctrine is that a
    ratio means nothing without a random-entry control on the same coins over
    the same tape, and a control that needs the raw series would evaporate with
    it. So each event draws its controls on the SAME coin within +/-12h of the
    event (clipped to what is retained and complete), seeded by the event id so
    the draw is reproducible, and stores them under `control:<source>` with a
    negative event_id (-(id * 10 + k)) that cannot collide with a real one.
    """
    from analytics.wick_benchmark import excursion  # lazy: wick_benchmark imports the repository

    horizons = tuple(float(h) for h in horizons)
    unknown = set(horizons) - set(SCHEMA_HORIZONS)
    if unknown:
        raise ValueError("horizons %s have no column in cascade_excursions; schema carries %s"
                         % (sorted(unknown), SCHEMA_HORIZONS))
    min_notional = dict(EXCURSION_PERSIST_MIN_NOTIONAL if min_notional is None else min_notional)
    longest_ms = int(max(horizons) * MS_MIN)
    complete_before = int(now_ms) - longest_ms
    cutoff = int(now_ms - retention_hours * MS_H)
    watermark = get_watermark(conn, JOB_CASCADES) or 0

    placeholders = ",".join("?" for _ in sources)
    rows = conn.execute(
        "SELECT id, coin, side, px, notional, time, source FROM liquidation_events "
        "WHERE id > ? AND time <= ? AND source IN (%s) ORDER BY id ASC LIMIT ?" % placeholders,
        (watermark, complete_before, *sources, int(max_events))).fetchall()

    out: Dict[str, Any] = {
        "job": JOB_CASCADES, "events_seen": len(rows), "events_written": 0,
        "controls_written": 0, "events_unretained": 0, "events_below_notional": 0,
        "events_no_series": 0, "events_unmeasurable": 0, "watermark": watermark,
        "capped": len(rows) >= int(max_events),
    }
    if not rows:
        return out

    persisted_at = int(now_ms)
    batch: List[Tuple[Any, ...]] = []
    for row in rows:
        event_id, coin, side, px, notional, ts, source = (
            int(row[0]), str(row[1]), str(row[2] or ""), float(row[3] or 0.0),
            float(row[4] or 0.0), int(row[5]), str(row[6]))
        if ts < cutoff:
            out["events_unretained"] += 1
            continue
        if notional < float(min_notional.get(source, 0.0)):
            out["events_below_notional"] += 1
            continue
        is_long = side.upper() == "A"          # forced SELL hits bids -> the fade BUYS
        measured = _measure_event(conn, excursion, coin, ts, is_long, horizons, longest_ms)
        if measured["samples"] == 0 and measured["entry_px"] is None:
            # No price series at all behind this event: its snapshots were pruned
            # before this round existed (events were kept 168h, snapshots 72h).
            # That is a gap to count, not a row to write.
            out["events_no_series"] += 1
            continue
        if not measured["measured"]:
            out["events_unmeasurable"] += 1
        regime = regime_at(conn, ts, cache=regime_cache)
        flat = [v for h in SCHEMA_HORIZONS for v in measured["values"].get(h, (None, None))]
        batch.append((event_id, coin, ts, source, side, int(is_long), notional, px,
                      measured["entry_px"], *flat, measured["samples"], regime["tag"], persisted_at))

        # Matched controls: same coin, same neighbourhood of the tape.
        rng = random.Random(event_id)
        lo = max(cutoff, ts - int(12 * MS_H))
        hi = min(complete_before, ts + int(12 * MS_H))
        for k in range(max(0, int(control_multiple))):
            if hi <= lo:
                break
            draw = rng.randint(lo, hi)
            control = _measure_event(conn, excursion, coin, draw, is_long, horizons, longest_ms)
            c_regime = regime_at(conn, draw, cache=regime_cache)
            c_flat = [v for h in SCHEMA_HORIZONS for v in control["values"].get(h, (None, None))]
            batch.append((-(event_id * 10 + k), coin, draw, control_source(source), side,
                          int(is_long), notional, px, control["entry_px"], *c_flat,
                          control["samples"], c_regime["tag"], persisted_at))
            out["controls_written"] += 1

    if batch:
        cursor = conn.executemany(_CASCADE_INSERT, batch)
        written = max(0, cursor.rowcount or 0)
        out["events_written"] = max(0, written - out["controls_written"])
    last_id = int(rows[-1][0])
    set_watermark(conn, JOB_CASCADES, last_id, now_ms=now_ms)
    out["watermark"] = last_id
    conn.commit()
    return out


def persist_completed_measurements(conn, now_ms: Optional[int] = None,
                                   snapshot_retention_hours: float = SNAPSHOT_RETENTION_HOURS,
                                   trade_retention_hours: float = TRADE_RETENTION_HOURS,
                                   holds: Sequence[float] = MEASUREMENT_HOLD_HOURS,
                                   max_grid_points: int = MEASUREMENT_MAX_GRID_POINTS_PER_PASS,
                                   max_events: int = MEASUREMENT_MAX_EVENTS_PER_PASS,
                                   sources: Sequence[str] = EXCURSION_PERSIST_SOURCES
                                   ) -> Dict[str, Any]:
    """
    One bounded pass over every materialiser. Called by the repository BEFORE it
    prunes, so nothing a window needs is deleted before the window is measured.
    """
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    started = time.perf_counter()
    ensure_schema(conn)
    cache: Dict[int, Dict[str, Any]] = {}
    jobs: List[Dict[str, Any]] = []
    for hold in holds:
        jobs.append(persist_basis_windows(conn, now_ms, float(hold),
                                          retention_hours=snapshot_retention_hours,
                                          max_grid_points=max_grid_points, regime_cache=cache))
    jobs.append(persist_cascade_excursions(
        conn, now_ms, retention_hours=min(snapshot_retention_hours, trade_retention_hours),
        max_events=max_events, sources=sources, regime_cache=cache))
    pending = any(j.get("grid_pending", 0) > 0 or j.get("capped", False) for j in jobs)
    return {
        "now_ms": now_ms,
        "jobs": jobs,
        "windows_written": sum(j.get("windows_written", 0) for j in jobs),
        "events_written": sum(j.get("events_written", 0) for j in jobs),
        "controls_written": sum(j.get("controls_written", 0) for j in jobs),
        "pending": pending,
        "elapsed_s": time.perf_counter() - started,
    }


def backfill(conn, now_ms: Optional[int] = None, max_passes: int = 500,
             progress: Optional[Callable[[Dict[str, Any]], None]] = None,
             **kwargs: Any) -> Dict[str, Any]:
    """Run passes until nothing is pending. For the CLI; the collector takes one pass per cycle."""
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    passes: List[Dict[str, Any]] = []
    for _ in range(max(1, int(max_passes))):
        result = persist_completed_measurements(conn, now_ms=now_ms, **kwargs)
        passes.append(result)
        if progress is not None:
            progress(result)
        if not result["pending"]:
            break
    return {
        "passes": len(passes),
        "windows_written": sum(p["windows_written"] for p in passes),
        "events_written": sum(p["events_written"] for p in passes),
        "controls_written": sum(p["controls_written"] for p in passes),
        "caught_up": not passes[-1]["pending"],
        "elapsed_s": sum(p["elapsed_s"] for p in passes),
    }


# ---------------------------------------------------------------------------
# Walk-forward reads - these consume ONLY the summary tables
# ---------------------------------------------------------------------------

def observation_span(conn, hold_hours: float) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(realised_apr IS NOT NULL), 0), COUNT(DISTINCT asset), "
        "MIN(window_start_utc), MAX(window_end_utc), COUNT(DISTINCT window_start_utc) "
        "FROM basis_realised_windows WHERE hold_hours = ?", (float(hold_hours),)).fetchone()
    first, last = row[3], row[4]
    return {
        "hold_hours": float(hold_hours),
        "windows": int(row[0] or 0),
        "measured_windows": int(row[1] or 0),
        "assets": int(row[2] or 0),
        "grid_points": int(row[5] or 0),
        "first_start_ms": int(first) if first is not None else None,
        "last_end_ms": int(last) if last is not None else None,
        "span_hours": ((int(last) - int(first)) / MS_H) if first is not None and last is not None else 0.0,
    }


def regimes_observed(conn, hold_hours: float,
                     stride_hours: float = MEASUREMENT_ENTRY_STRIDE_HOURS) -> Dict[str, Dict[str, Any]]:
    """Measured windows per regime tag, with the hours of grid that regime covered."""
    out: Dict[str, Dict[str, Any]] = {}
    for tag, windows, points in conn.execute(
            "SELECT regime_tag, COUNT(*), COUNT(DISTINCT window_start_utc) FROM basis_realised_windows "
            "WHERE hold_hours = ? AND realised_apr IS NOT NULL GROUP BY regime_tag ORDER BY 2 DESC",
            (float(hold_hours),)):
        out[str(tag)] = {"windows": int(windows), "grid_points": int(points),
                         "hours": float(points) * float(stride_hours)}
    return out


def ruling_d_status(conn, hold_hours: float = 168.0,
                    required_hours: float = RULING_D_REQUIRED_HOURS,
                    min_regimes: int = RULING_D_MIN_REGIMES,
                    min_hours_per_regime: float = RULING_D_MIN_HOURS_PER_REGIME) -> Dict[str, Any]:
    """
    The DATA precondition of Ruling D: 720h of observation across >= 2 regimes.

    This says whether the question CAN be asked, not what the answer is - the
    answer is `entry_conditioned_summary` read against its control. UNKNOWN
    regimes never count toward the two.
    """
    span = observation_span(conn, hold_hours)
    regimes = regimes_observed(conn, hold_hours)
    qualifying = {t: v for t, v in regimes.items()
                  if t != "UNKNOWN" and v["hours"] >= min_hours_per_regime}
    if span["measured_windows"] == 0:
        status = "NO_DATA"
    elif span["span_hours"] < required_hours:
        status = "INSUFFICIENT_SPAN"
    elif len(qualifying) < min_regimes:
        status = "INSUFFICIENT_REGIMES"
    else:
        status = "SPAN_AND_REGIMES_MET"
    return {
        "status": status,
        "eligible": status == "SPAN_AND_REGIMES_MET",
        "hold_hours": float(hold_hours),
        "required_hours": float(required_hours),
        "span_hours": span["span_hours"],
        "measured_windows": span["measured_windows"],
        "regimes": regimes,
        "qualifying_regimes": sorted(qualifying),
        "min_regimes": int(min_regimes),
        "min_hours_per_regime": float(min_hours_per_regime),
        "detail": ("%.0fh observed of %.0fh required; %d qualifying regime(s) of %d needed"
                   % (span["span_hours"], required_hours, len(qualifying), min_regimes)),
    }


def _summarise(by_coin: Dict[str, List[float]], bar_apr: float) -> Optional[Dict[str, Any]]:
    flat = sorted(v for vals in by_coin.values() for v in vals)
    if not flat:
        return None
    n = len(flat)
    return {"n": n, "coins": len(by_coin), "median": flat[n // 2],
            "mean": statistics.fmean(flat),
            "pct_ge_bar": sum(1 for v in flat if v >= bar_apr) / n * 100.0,
            "pct_negative": sum(1 for v in flat if v < 0) / n * 100.0}


def cluster_bootstrap_median(by_coin: Dict[str, List[float]], bar_apr: float,
                             resamples: int = 2000, seed: int = 7) -> Optional[float]:
    """P(median realised >= bar) resampling COINS - funding is correlated across the universe."""
    coins = list(by_coin)
    if not coins:
        return None
    rng = random.Random(seed)
    hits = 0
    for _ in range(resamples):
        picked = [coins[rng.randrange(len(coins))] for _ in coins]
        vals = [v for c in picked for v in by_coin[c]]
        if vals and statistics.median(vals) >= bar_apr:
            hits += 1
    return hits / resamples


def entry_conditioned_summary(conn, hold_hours: float,
                              thresholds: Sequence[float] = (20.0, 25.0, 40.0),
                              bar_apr: float = 20.0, resamples: int = 2000,
                              seed: int = 7) -> Dict[str, Any]:
    """
    The Round 32 walk-forward, read from the persisted windows instead of raw rows.

    Conditional on the quote at entry clearing a threshold, what did the hold
    realise - and how does that compare with the UNCONDITIONAL grid on the same
    coins, which is the matched random-entry control. Confidence is a coin-level
    bootstrap for the same reason as everywhere else in this repo.
    """
    rows = conn.execute(
        "SELECT asset, quote_apr_entry, realised_apr FROM basis_realised_windows "
        "WHERE hold_hours = ? AND realised_apr IS NOT NULL AND quote_apr_entry IS NOT NULL",
        (float(hold_hours),)).fetchall()
    control: Dict[str, List[float]] = defaultdict(list)
    signal: Dict[float, Dict[str, List[float]]] = {float(t): defaultdict(list) for t in thresholds}
    for asset, quote, realised in rows:
        control[str(asset)].append(float(realised))
        for t in signal:
            if float(quote) >= t:
                signal[t][str(asset)].append(float(realised))
    ctl = _summarise(control, bar_apr)
    out: Dict[str, Any] = {"hold_hours": float(hold_hours), "windows": len(rows),
                           "bar_apr": float(bar_apr), "control": ctl, "rules": {}}
    for t in sorted(signal):
        s = _summarise(signal[t], bar_apr)
        entry = {"threshold": t, "summary": s, "edge_pp": None, "p_median_ge_bar": None}
        if s and ctl:
            entry["edge_pp"] = s["median"] - ctl["median"]
            entry["p_median_ge_bar"] = cluster_bootstrap_median(signal[t], bar_apr, resamples, seed)
        out["rules"][t] = entry
    return out


def excursion_summary(conn, source: str = "trade_sweep",
                      horizons: Sequence[float] = SCHEMA_HORIZONS,
                      resamples: int = 2000, seed: int = 7) -> Dict[str, Any]:
    """MFE/MAE per horizon from the persisted rows, signal against its persisted control."""
    from analytics.wick_benchmark import _aggregate, cluster_bootstrap, concentration_hhi

    def load(src: str, h: float) -> Dict[str, List[Dict[str, float]]]:
        col_m, col_a = "mfe_%dm" % int(h), "mae_%dm" % int(h)
        by_coin: Dict[str, List[Dict[str, float]]] = defaultdict(list)
        for coin, mfe, mae in conn.execute(
                "SELECT coin, %s, %s FROM cascade_excursions WHERE source = ? "
                "AND %s IS NOT NULL AND %s IS NOT NULL" % (col_m, col_a, col_m, col_a), (src,)):
            by_coin[str(coin)].append({"mfe": float(mfe), "mae": float(mae)})
        return by_coin

    total = conn.execute("SELECT COUNT(*) FROM cascade_excursions WHERE source = ?",
                         (source,)).fetchone()[0]
    out: Dict[str, Any] = {"source": source, "events": int(total or 0), "horizons": {}}
    for h in horizons:
        sig = load(source, h)
        ctl = load(control_source(source), h)
        sig_agg = _aggregate([r for rows in sig.values() for r in rows])
        ctl_agg = _aggregate([r for rows in ctl.values() for r in rows])
        counts = [len(v) for v in sig.values()]
        edge = None
        if sig_agg["ratio"] is not None and ctl_agg.get("ratio"):
            edge = sig_agg["ratio"] - ctl_agg["ratio"]
        out["horizons"][float(h)] = {
            "signal": sig_agg, "control": ctl_agg, "edge_vs_control": edge,
            "coins_measured": len(sig), "hhi": concentration_hhi(counts),
            "top_coin_share": (max(counts) / sum(counts)) if counts else 0.0,
            "cluster_p_ge_1": cluster_bootstrap(sig, threshold=1.0, resamples=resamples, seed=seed)
            if sig else None,
        }
    return out


def persistence_status(conn, now_ms: Optional[int] = None) -> Dict[str, Any]:
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    ensure_schema(conn)
    watermarks = {str(r[0]): {"watermark": int(r[1]), "updated_at": int(r[2])}
                  for r in conn.execute("SELECT job, watermark, updated_at FROM measurement_watermarks")}
    holds = {}
    for hold in MEASUREMENT_HOLD_HOURS:
        holds[float(hold)] = {"span": observation_span(conn, hold),
                              "regimes": regimes_observed(conn, hold),
                              "ruling_d": ruling_d_status(conn, hold)}
    cascades = {}
    for src, n in conn.execute("SELECT source, COUNT(*) FROM cascade_excursions GROUP BY source"):
        cascades[str(src)] = int(n)
    return {"now_ms": now_ms, "watermarks": watermarks, "holds": holds, "cascades": cascades}


def format_status(status: Dict[str, Any]) -> str:
    lines = ["MEASUREMENT PERSISTENCE"]
    if not status["watermarks"]:
        lines.append("  no passes recorded yet - run `python main.py persist --backfill`")
    for job, wm in sorted(status["watermarks"].items()):
        lines.append("  %-22s watermark %d" % (job, wm["watermark"]))
    for hold, info in sorted(status["holds"].items()):
        span = info["span"]
        lines.append("  basis %4.0fh: %6d windows (%d measured) on %d assets over %.1fh"
                     % (hold, span["windows"], span["measured_windows"], span["assets"],
                        span["span_hours"]))
        for tag, v in info["regimes"].items():
            lines.append("      %-22s %6d windows %6.0fh" % (tag, v["windows"], v["hours"]))
        lines.append("      Ruling D: %s - %s" % (info["ruling_d"]["status"], info["ruling_d"]["detail"]))
    if status["cascades"]:
        lines.append("  cascades: " + ", ".join("%s=%d" % kv for kv in sorted(status["cascades"].items())))
    else:
        lines.append("  cascades: none persisted")
    return "\n".join(lines)


def format_entry_conditioned(summary: Dict[str, Any]) -> str:
    lines = ["ENTRY-CONDITIONED %.0fh REALISED APR (persisted windows) vs unconditional grid"
             % summary["hold_hours"],
             "  %-22s %7s %6s %9s %9s %8s %9s" % ("entry rule", "n", "coins", "median",
                                                  "mean", ">=%.0f%%" % summary["bar_apr"], "negative")]
    ctl = summary["control"]
    if ctl is None:
        lines.append("  no measured windows yet")
        return "\n".join(lines)
    lines.append("  %-22s %7d %6d %8.1f%% %8.1f%% %7.1f%% %8.1f%%" % (
        "UNCONDITIONAL (control)", ctl["n"], ctl["coins"], ctl["median"], ctl["mean"],
        ctl["pct_ge_bar"], ctl["pct_negative"]))
    for t, rule in sorted(summary["rules"].items()):
        s = rule["summary"]
        if not s:
            lines.append("  quote >= %-13.0f no qualifying entries" % t)
            continue
        lines.append("  %-22s %7d %6d %8.1f%% %8.1f%% %7.1f%% %8.1f%%   edge %+6.1fpp  P(median>=bar) %s" % (
            "quote >= %.0f%%" % t, s["n"], s["coins"], s["median"], s["mean"], s["pct_ge_bar"],
            s["pct_negative"], rule["edge_pp"],
            "%.3f" % rule["p_median_ge_bar"] if rule["p_median_ge_bar"] is not None else "n/a"))
    return "\n".join(lines)


def format_excursions(summary: Dict[str, Any]) -> str:
    lines = ["CASCADE EXCURSIONS - %s (%d persisted events), signal vs persisted control"
             % (summary["source"], summary["events"]),
             "  %7s %7s %8s %8s %7s %8s %7s %6s %8s" % ("horizon", "n", "MFE", "MAE", "ratio",
                                                       "control", "edge", "coins", "P(>=1)")]
    for h, d in sorted(summary["horizons"].items()):
        sig, ctl = d["signal"], d["control"]
        if not sig["n"]:
            lines.append("  %6.0fm       0  (nothing measurable)" % h)
            continue
        lines.append("  %6.0fm %7d %7.3f%% %7.3f%% %7.3f %8s %7s %6d %8s" % (
            h, sig["n"], sig["mean_mfe"], sig["mean_mae"], sig["ratio"] or 0.0,
            "%.3f" % ctl["ratio"] if ctl.get("ratio") else "n/a",
            "%+.3f" % d["edge_vs_control"] if d["edge_vs_control"] is not None else "n/a",
            d["coins_measured"],
            "%.3f" % d["cluster_p_ge_1"] if d["cluster_p_ge_1"] is not None else "n/a"))
    return "\n".join(lines)
