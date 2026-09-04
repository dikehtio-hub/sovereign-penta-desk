"""
Round 34 Target 1: incremental measurement persistence (option b).

Ruling D wants 720 hours of observation across two regimes; retention holds
192. These tests pin the contract that makes the two compatible: raw rows are
reduced to basis windows and cascade excursions BEFORE the pruner deletes them,
on a fixed grid that cannot duplicate, with NULL for anything unmeasurable and a
count for anything skipped. And the one property that matters most: if the
measurement pass fails, the rows it needed are NOT pruned that cycle.

Fully offline - synthetic series in a temp database throughout.
"""
import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from analytics.wick_benchmark import excursion
from storage import incremental_persistence as ip
from storage.db import DatabaseManager, SCHEMA_SQL
from storage.measurement_schema import MEASUREMENT_SCHEMA_SQL
from storage.repository import MarketRepository

H = 3_600_000
MIN = 60_000
STRIDE = 3 * H
# An epoch-aligned instant: multiples of the 3h stride land exactly on it.
T0 = 1_788_000_000_000 // STRIDE * STRIDE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "persist.db")
    c.executescript(SCHEMA_SQL)
    c.executescript(MEASUREMENT_SCHEMA_SQL)
    yield c
    c.close()


def add_series(conn, coin, start_ms, hours, step_min=5, rate=0.0001, px=100.0,
               px_fn=None, holes=()):
    """Snapshots every `step_min` from start for `hours` INCLUSIVE of the end instant."""
    rows = []
    t = int(start_ms)
    end = int(start_ms + hours * H)
    while t <= end:
        hole = any(lo <= t < hi for lo, hi in holes)
        if not hole:
            price = px_fn(t) if px_fn else px
            rows.append((t, coin, "main", price, price, price, 1.0, 1000.0, rate, 0.0, 0.0))
        t += step_min * MIN
    conn.executemany(
        "INSERT INTO asset_snapshots (timestamp, coin, dex, mark_px, mid_px, oracle_px, "
        "open_interest, notional_oi, funding_rate, premium, day_ntl_vlm) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows)
    last = rows[-1]
    conn.execute(
        "INSERT INTO latest_snapshots (coin, timestamp, dex, mark_px, mid_px, oracle_px, open_interest, "
        "notional_oi, funding_rate, premium, day_ntl_vlm) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(coin) DO UPDATE SET timestamp = excluded.timestamp",
        (coin, last[0], "main", last[3], last[4], last[5], 1.0, 1000.0, rate, 0.0, 0.0))
    conn.commit()
    return len(rows)


def add_event(conn, coin, ts, side="A", notional=100_000.0, source="trade_sweep", px=100.0):
    cur = conn.execute(
        "INSERT INTO liquidation_events (coin, side, px, sz, notional, time, source, note) "
        "VALUES (?,?,?,?,?,?,?,?)", (coin, side, px, 1.0, notional, int(ts), source, None))
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Grid and per-window measurement
# ---------------------------------------------------------------------------

def test_entry_grid_is_epoch_aligned_and_inclusive():
    assert ip.entry_grid(1_000, 3 * H, 1.0) == [H, 2 * H, 3 * H]
    assert ip.entry_grid(H, H, 1.0) == [H]
    assert ip.entry_grid(5 * H, 4 * H, 1.0) == []
    # Two runs that start at different moments land on the same instants.
    assert set(ip.entry_grid(T0 + 17, T0 + 30 * H, 3.0)) <= set(ip.entry_grid(T0 - 5 * H, T0 + 30 * H, 3.0))


def test_funding_window_integrates_by_time_and_drops_gaps(conn):
    add_series(conn, "AAA", T0, 24, rate=0.0001)
    s = ip.funding_window_stats(conn, "AAA", T0, T0 + 24 * H)
    assert s["observed_hours"] == pytest.approx(24.0)
    assert s["accrual_rate_hours"] == pytest.approx(0.0001 * 24.0)

    # A 3h hole is unobserved, not extrapolated across.
    add_series(conn, "BBB", T0, 24, rate=0.0001, holes=((T0 + 6 * H + MIN, T0 + 9 * H),))
    s = ip.funding_window_stats(conn, "BBB", T0, T0 + 24 * H)
    assert s["observed_hours"] == pytest.approx(21.0, abs=0.2)
    assert s["accrual_rate_hours"] == pytest.approx(0.0001 * s["observed_hours"])


def test_realised_window_annualises_and_reports_coverage(conn):
    add_series(conn, "AAA", T0, 24, rate=0.0001, px_fn=lambda t: 100.0 + (t - T0) / H)
    w = ip.realised_window(conn, "AAA", T0, 24.0)
    assert w["realised_apr"] == pytest.approx(0.0001 * 8760 * 100)      # 87.6%
    assert w["coverage"] == pytest.approx(1.0)
    assert w["funding_payments"] == 24
    assert w["entry_px"] == pytest.approx(100.0)
    assert w["exit_px"] == pytest.approx(124.0)


def test_a_thin_window_is_null_not_zero(conn):
    """The rule that keeps the table honest: under-covered means unmeasured."""
    add_series(conn, "AAA", T0, 8, rate=0.0001)         # 8h of a 24h hold = 33% coverage
    w = ip.realised_window(conn, "AAA", T0, 24.0)
    assert w["samples"] > 0
    assert w["coverage"] < ip.MEASUREMENT_MIN_COVERAGE
    assert w["realised_apr"] is None
    empty = ip.realised_window(conn, "NOPE", T0, 24.0)
    assert empty["samples"] == 0 and empty["realised_apr"] is None


def test_quote_at_entry_respects_the_gap_tolerance(conn):
    add_series(conn, "AAA", T0, 1, rate=0.0002)
    assert ip.quote_apr_at(conn, "AAA", T0 + 30 * MIN) == pytest.approx(0.0002 * 8760 * 100)
    assert ip.quote_apr_at(conn, "AAA", T0 + 10 * H) is None          # last quote 9h old
    assert ip.quote_apr_at(conn, "AAA", T0 - MIN) is None             # nothing before


def test_spread_is_only_ever_measured(conn):
    assert ip.spread_bps_at(conn, "AAA", T0) is None
    conn.execute("INSERT INTO orderbook_snapshots (timestamp, coin, best_bid, best_ask, spread, spread_bps, "
                 "bid_depth_1pct, ask_depth_1pct, bid_depth_total, ask_depth_total, imbalance_ratio) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (T0, "AAA", 99.97, 100.03, 0.06, 6.0, 1, 1, 1, 1, 1))
    assert ip.spread_bps_at(conn, "AAA", T0 + MIN) == pytest.approx(6.0)
    assert ip.spread_bps_at(conn, "AAA", T0 + 5 * H) is None


def test_spread_drag_is_the_round_33_two_leg_figure():
    """6bp, spot-backed: 6.26% amortised over 7 days, 43.80% over 1 day."""
    assert ip.spread_drag_apr(6.0, 168.0) == pytest.approx(6.257, abs=0.01)
    assert ip.spread_drag_apr(6.0, 24.0) == pytest.approx(43.80, abs=0.01)


# ---------------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------------

def test_regime_reads_the_reference_coin_and_caches(conn):
    add_series(conn, "BTC", T0 - 25 * H, 25, rate=0.0001, px=50_000.0)   # flat price, hot funding
    cache = {}
    r = ip.regime_at(conn, T0, cache=cache)
    assert r["tag"] == "VOL_LOW|FUND_HOT"
    assert r["vol_pct"] == pytest.approx(0.0)
    assert r["funding_apr"] == pytest.approx(87.6)
    assert cache and ip.regime_at(conn, T0 + 10 * MIN, cache=cache) is r      # same hour bucket

    thin = ip.regime_at(conn, T0 - 24 * H)
    assert thin["tag"] == "UNKNOWN"


def test_regime_buckets_volatility_and_negative_funding(conn):
    import math
    # +-5% alternating hourly closes -> a very volatile day; negative funding.
    add_series(conn, "BTC", T0 - 25 * H, 25, step_min=60, rate=-0.0001,
               px_fn=lambda t: 100.0 * (1.05 if ((t - T0) // H) % 2 else 0.95))
    r = ip.regime_at(conn, T0)
    assert r["tag"] == "VOL_HIGH|FUND_NEG"
    assert r["vol_pct"] > 3.5 and r["funding_apr"] < 0
    assert math.isfinite(r["vol_pct"])


# ---------------------------------------------------------------------------
# Basis window materialiser
# ---------------------------------------------------------------------------

def test_basis_windows_are_written_on_the_grid_and_never_duplicated(conn):
    add_series(conn, "AAA", T0, 48, rate=0.0001)
    add_series(conn, "BBB", T0, 48, rate=0.0002)
    now = T0 + 49 * H
    out = ip.persist_basis_windows(conn, now, 24.0, retention_hours=192, max_grid_points=100)
    # Entries with a quote in force: T0 ... T0+24h on the 3h grid = 9 per coin.
    # Grid instants before T0 had no quote - the coin was not there to enter.
    assert out["windows_written"] == 18
    assert out["windows_no_entry_quote"] > 0
    assert out["grid_pending"] == 0
    assert out["watermark"] == T0 + 24 * H

    rows = conn.execute("SELECT asset, window_start_utc, realised_apr, quote_apr_entry, regime_tag, fee_basis, "
                        "coverage FROM basis_realised_windows ORDER BY asset, window_start_utc").fetchall()
    assert len(rows) == 18
    assert all(r[1] % STRIDE == 0 and r[1] >= T0 for r in rows)
    assert all(r[6] == pytest.approx(1.0) for r in rows)
    aaa = [r for r in rows if r[0] == "AAA"]
    assert all(r[2] == pytest.approx(87.6) for r in aaa)
    assert all(r[3] == pytest.approx(87.6) for r in aaa)
    assert all(r[4] == "UNKNOWN" for r in rows)   # no BTC reference series
    assert all(r[5] == "unmeasured" for r in rows)

    again = ip.persist_basis_windows(conn, now, 24.0, retention_hours=192, max_grid_points=100)
    assert again["windows_written"] == 0 and again["grid_points"] == 0


def test_basis_watermark_resumes_where_a_capped_pass_stopped(conn):
    add_series(conn, "AAA", T0, 48, rate=0.0001)
    now = T0 + 49 * H
    first = ip.persist_basis_windows(conn, now, 24.0, retention_hours=48, max_grid_points=2)
    assert first["grid_points"] == 2 and first["grid_pending"] > 0
    total = first["windows_written"]
    for _ in range(20):
        r = ip.persist_basis_windows(conn, now, 24.0, retention_hours=48, max_grid_points=2)
        total += r["windows_written"]
        if r["grid_pending"] == 0:
            break
    # Retention 48h with now = T0+49h puts the cutoff at T0+1h, so T0 itself is
    # never claimed: T0+3h ... T0+24h = 8 windows, in four capped passes.
    assert total == 8
    assert conn.execute("SELECT COUNT(*) FROM basis_realised_windows").fetchone()[0] == 8


def test_a_window_whose_rows_are_about_to_be_pruned_is_never_claimed(conn):
    """Retention 30h, data 48h: entries older than now-30h have rows NOW but not after the prune."""
    add_series(conn, "AAA", T0, 48, rate=0.0001)
    now = T0 + 49 * H
    out = ip.persist_basis_windows(conn, now, 24.0, retention_hours=30, max_grid_points=100)
    starts = [r[0] for r in conn.execute("SELECT window_start_utc FROM basis_realised_windows")]
    assert starts and min(starts) >= now - 30 * H
    assert out["windows_written"] == len(starts)


def test_low_coverage_windows_are_recorded_with_a_null_rate(conn):
    add_series(conn, "AAA", T0, 30, rate=0.0001, holes=((T0 + 2 * H, T0 + 20 * H),))
    now = T0 + 31 * H
    ip.persist_basis_windows(conn, now, 24.0, retention_hours=192, max_grid_points=100)
    row = conn.execute("SELECT realised_apr, coverage, samples FROM basis_realised_windows "
                       "WHERE window_start_utc = ?", (T0,)).fetchone()
    assert row is not None
    assert row[0] is None and row[1] < 0.6 and row[2] > 0


def test_a_measured_spread_yields_a_net_figure(conn):
    add_series(conn, "AAA", T0, 30, rate=0.0001)
    conn.execute("INSERT INTO orderbook_snapshots (timestamp, coin, best_bid, best_ask, spread, spread_bps, "
                 "bid_depth_1pct, ask_depth_1pct, bid_depth_total, ask_depth_total, imbalance_ratio) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (T0 - MIN, "AAA", 99.97, 100.03, 0.06, 6.0, 1, 1, 1, 1, 1))
    ip.persist_basis_windows(conn, T0 + 31 * H, 24.0, retention_hours=192, max_grid_points=100)
    row = conn.execute("SELECT realised_apr, net_apr_after_fees, fee_basis, spread_bps_entry "
                       "FROM basis_realised_windows WHERE window_start_utc = ?", (T0,)).fetchone()
    assert row[2] == "measured" and row[3] == pytest.approx(6.0)
    assert row[1] == pytest.approx(87.6 - 43.80, abs=0.01)


# ---------------------------------------------------------------------------
# Cascade excursion materialiser
# ---------------------------------------------------------------------------

def _spiky(t0):
    """100 at the event, 103 at +2m, 98 at +8m, 110 at +40m, flat otherwise."""
    def px(t):
        m = (t - t0) / MIN
        if 1.5 <= m < 3:
            return 103.0
        if 7.5 <= m < 9:
            return 98.0
        if 39.5 <= m < 41:
            return 110.0
        return 100.0
    return px


def test_cascade_excursions_match_the_benchmark_function_and_persist_a_control(conn):
    add_series(conn, "AAA", T0 - 13 * H, 26, step_min=0.5, px_fn=_spiky(T0))
    eid = add_event(conn, "AAA", T0, side="A")
    now = T0 + 2 * H
    out = ip.persist_cascade_excursions(conn, now, retention_hours=192, max_events=100)
    assert out["events_seen"] == 1 and out["events_written"] == 1 and out["controls_written"] == 1
    assert out["watermark"] == eid

    row = conn.execute("SELECT fade_is_long, mfe_5m, mae_5m, mfe_15m, mae_15m, mfe_60m, mae_60m, entry_px "
                       "FROM cascade_excursions WHERE event_id = ?", (eid,)).fetchone()
    series = [(int(a), float(b)) for a, b in conn.execute(
        "SELECT timestamp, mark_px FROM asset_snapshots WHERE coin='AAA' AND timestamp >= ? "
        "ORDER BY timestamp", (T0,))]
    ref5 = excursion(series, T0, True, 5.0)
    ref60 = excursion(series, T0, True, 60.0)
    assert row[0] == 1
    assert row[1] == pytest.approx(ref5["mfe"]) and row[2] == pytest.approx(ref5["mae"])
    assert row[5] == pytest.approx(ref60["mfe"]) and row[6] == pytest.approx(ref60["mae"])
    assert row[1] == pytest.approx(3.0) and row[5] == pytest.approx(10.0) and row[6] == pytest.approx(2.0)

    control = conn.execute("SELECT event_id, source, coin FROM cascade_excursions WHERE event_id < 0").fetchall()
    assert control == [(-(eid * 10), "control:trade_sweep", "AAA")]

    again = ip.persist_cascade_excursions(conn, now, retention_hours=192, max_events=100)
    assert again["events_seen"] == 0


def test_cascade_skips_unretained_and_below_notional_events_and_counts_them(conn):
    add_series(conn, "AAA", T0 - 13 * H, 26, step_min=1)
    old = add_event(conn, "AAA", T0 - 12 * H)                        # older than retention
    small = add_event(conn, "AAA", T0, notional=10_000.0, source="trade_flow")
    kept = add_event(conn, "AAA", T0 + MIN, notional=500_000.0, source="trade_flow")
    out = ip.persist_cascade_excursions(conn, T0 + 3 * H, retention_hours=10, max_events=100)
    assert out["events_seen"] == 3
    assert out["events_unretained"] == 1
    assert out["events_below_notional"] == 1
    assert out["events_written"] == 1
    ids = [r[0] for r in conn.execute("SELECT event_id FROM cascade_excursions WHERE event_id > 0")]
    assert ids == [kept]
    assert old not in ids and small not in ids
    assert out["watermark"] == kept


def test_an_event_with_no_series_at_all_is_a_counted_gap_not_a_row(conn):
    """Its snapshots were pruned before this round existed: count it, write nothing."""
    eid = add_event(conn, "GHOST", T0)
    out = ip.persist_cascade_excursions(conn, T0 + 3 * H, retention_hours=192, max_events=100)
    assert out["events_no_series"] == 1 and out["events_written"] == 0
    assert conn.execute("SELECT COUNT(*) FROM cascade_excursions").fetchone()[0] == 0
    assert out["watermark"] == eid                       # but it is not revisited


def test_an_event_with_a_thin_series_is_persisted_with_null_horizons(conn):
    """Two forward samples: the window exists but cannot describe an excursion."""
    add_series(conn, "THIN", T0, 0.05, step_min=1.5)      # samples at +0, +1.5, +3 min
    eid = add_event(conn, "THIN", T0)
    out = ip.persist_cascade_excursions(conn, T0 + 3 * H, retention_hours=192, max_events=100)
    assert out["events_unmeasurable"] == 1 and out["events_written"] == 1
    row = conn.execute("SELECT mfe_5m, mfe_60m, samples_60m FROM cascade_excursions WHERE event_id = ?",
                       (eid,)).fetchone()
    assert row == (None, None, 2)


def test_a_horizon_with_no_column_is_refused(conn):
    with pytest.raises(ValueError):
        ip.persist_cascade_excursions(conn, T0, horizons=(5.0, 120.0))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def test_one_pass_runs_every_job_and_backfill_catches_up(conn):
    add_series(conn, "AAA", T0, 48, rate=0.0001, step_min=1)
    add_event(conn, "AAA", T0 + 10 * H)
    now = T0 + 49 * H
    r = ip.persist_completed_measurements(conn, now_ms=now, snapshot_retention_hours=192,
                                          trade_retention_hours=192, max_grid_points=1, max_events=1)
    jobs = {j["job"] for j in r["jobs"]}
    assert jobs == {"basis_windows_24h", "basis_windows_168h", "cascade_excursions"}
    assert r["pending"]                                   # capped at one grid point
    b = ip.backfill(conn, now_ms=now, snapshot_retention_hours=192, trade_retention_hours=192,
                    max_grid_points=1, max_events=1)
    assert b["caught_up"] and b["passes"] > 1
    assert conn.execute("SELECT COUNT(*) FROM basis_realised_windows WHERE hold_hours = 24").fetchone()[0] == 9
    # No 168h window can COMPLETE inside 48h of data from an entry that had a
    # quote, so nothing is written for that hold - and nothing is faked.
    assert conn.execute("SELECT COUNT(*) FROM basis_realised_windows WHERE hold_hours = 168").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM cascade_excursions WHERE event_id > 0").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Reads: the walk-forward consumes only the summary tables
# ---------------------------------------------------------------------------

def _window(conn, asset, start, hold=168.0, quote=30.0, realised=30.0, regime="VOL_MID|FUND_HOT"):
    conn.execute(
        "INSERT INTO basis_realised_windows (asset, window_start_utc, window_end_utc, hold_hours, "
        "quote_apr_entry, realised_apr, observed_hours, coverage, funding_payments_count, fee_basis, "
        "regime_tag, samples, persisted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (asset, int(start), int(start + hold * H), hold, quote, realised, hold, 1.0, int(hold),
         "unmeasured", regime, 100, 0))


def test_ruling_d_precondition_walks_from_no_data_to_met(conn):
    assert ip.ruling_d_status(conn, 168.0)["status"] == "NO_DATA"

    for k in range(20):                                    # 60h of grid, one regime
        _window(conn, "AAA", T0 + k * STRIDE)
    s = ip.ruling_d_status(conn, 168.0)
    assert s["status"] == "INSUFFICIENT_SPAN" and not s["eligible"]

    for k in range(20, 200):                               # 600h of grid, still one regime
        _window(conn, "AAA", T0 + k * STRIDE)
    s = ip.ruling_d_status(conn, 168.0)
    assert s["span_hours"] >= 720
    assert s["status"] == "INSUFFICIENT_REGIMES"

    for k in range(200, 220):                              # 60h of a SECOND regime
        _window(conn, "AAA", T0 + k * STRIDE, regime="VOL_HIGH|FUND_NEG")
    s = ip.ruling_d_status(conn, 168.0)
    assert s["status"] == "SPAN_AND_REGIMES_MET" and s["eligible"]
    assert s["qualifying_regimes"] == ["VOL_HIGH|FUND_NEG", "VOL_MID|FUND_HOT"]


def test_unknown_regime_never_counts_toward_the_two(conn):
    for k in range(250):
        _window(conn, "AAA", T0 + k * STRIDE, regime="VOL_MID|FUND_HOT" if k % 2 else "UNKNOWN")
    s = ip.ruling_d_status(conn, 168.0)
    assert s["status"] == "INSUFFICIENT_REGIMES"
    assert "UNKNOWN" in s["regimes"] and "UNKNOWN" not in s["qualifying_regimes"]


def test_entry_conditioned_summary_reads_signal_against_the_unconditional_grid(conn):
    for k in range(10):
        _window(conn, "HOT", T0 + k * STRIDE, hold=24.0, quote=40.0, realised=35.0)
        _window(conn, "COLD", T0 + k * STRIDE, hold=24.0, quote=5.0, realised=4.0)
        _window(conn, "WARM", T0 + k * STRIDE, hold=24.0, quote=22.0, realised=18.0)
    s = ip.entry_conditioned_summary(conn, 24.0, thresholds=(20.0, 30.0), resamples=200)
    assert s["windows"] == 30
    assert s["control"]["n"] == 30 and s["control"]["coins"] == 3
    rule20 = s["rules"][20.0]["summary"]
    assert rule20["n"] == 20 and rule20["coins"] == 2
    assert s["rules"][20.0]["edge_pp"] > 0
    assert 0.0 <= s["rules"][20.0]["p_median_ge_bar"] <= 1.0
    assert s["rules"][30.0]["summary"]["coins"] == 1
    assert ip.entry_conditioned_summary(conn, 168.0)["control"] is None


def test_excursion_summary_reads_signal_against_its_persisted_control(conn):
    add_series(conn, "AAA", T0 - 13 * H, 26, step_min=0.5, px_fn=_spiky(T0))
    add_event(conn, "AAA", T0)
    ip.persist_cascade_excursions(conn, T0 + 2 * H, retention_hours=192, max_events=100)
    s = ip.excursion_summary(conn, "trade_sweep", resamples=50)
    assert s["events"] == 1
    # At 5m the adverse move is zero, so the ratio is honestly None; at 60m it is 10/2.
    assert s["horizons"][5.0]["signal"]["n"] == 1 and s["horizons"][5.0]["signal"]["ratio"] is None
    h60 = s["horizons"][60.0]
    assert h60["signal"]["n"] == 1 and h60["signal"]["ratio"] == pytest.approx(5.0)
    assert h60["control"]["n"] == 1
    assert h60["coins_measured"] == 1 and h60["top_coin_share"] == 1.0
    assert "trade_sweep" in ip.format_excursions(s)


def test_status_and_formatting_do_not_need_data(conn):
    status = ip.persistence_status(conn, now_ms=T0)
    text = ip.format_status(status)
    assert "no passes recorded yet" in text
    assert "Ruling D: NO_DATA" in text
    assert "no measured windows yet" in ip.format_entry_conditioned(
        ip.entry_conditioned_summary(conn, 24.0))


# ---------------------------------------------------------------------------
# The repository hook: measure BEFORE prune, and fail closed
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager(tmp_path / "hook.db")
    r = MarketRepository(db)
    r.upsert_assets([{"coin": "AAA", "dex": "main", "sz_decimals": 4, "max_leverage": 25,
                      "only_isolated": False}])
    yield r
    db.close()
    DatabaseManager._instance = None


def _snap(coin, ts):
    return {"timestamp": ts, "coin": coin, "dex": "main", "mark_px": 100.0, "mid_px": 100.0,
            "oracle_px": 100.0, "open_interest": 10.0, "notional_oi": 1000.0,
            "funding_rate": 0.0001, "premium": 0.0, "day_ntl_vlm": 5000.0}


def test_database_manager_creates_the_measurement_tables(repo):
    names = {r[0] for r in repo.db.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"basis_realised_windows", "cascade_excursions", "measurement_watermarks"} <= names


def test_prune_measures_first_and_reports_it(repo):
    now = int(time.time() * 1000)
    repo.insert_snapshots([_snap("AAA", now - h * H) for h in range(40, 0, -1)])
    deleted = repo.prune_old_data(snapshot_retention_hours=192)
    assert deleted["asset_snapshots"] == 0
    assert repo.last_persistence and "jobs" in repo.last_persistence
    assert {j["job"] for j in repo.last_persistence["jobs"]} >= {"basis_windows_24h", "cascade_excursions"}
    stats = repo.run_maintenance()
    assert stats["persisted"] is not None and "jobs" in stats["persisted"]


def test_a_failed_measurement_pass_blocks_the_prune_of_what_it_needed(repo, monkeypatch):
    """The property that matters most: a pruned row can never be measured later."""
    now = int(time.time() * 1000)
    repo.insert_snapshots([_snap("AAA", now - 300 * H), _snap("AAA", now - 250 * H), _snap("AAA", now)])
    repo.insert_liquidation_events([{"coin": "AAA", "side": "A", "px": 100.0, "sz": 1.0,
                                     "notional": 100.0, "time": now - 300 * H,
                                     "source": "trade_sweep", "note": None}])

    def boom(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(ip, "persist_completed_measurements", boom)
    deleted = repo.prune_old_data(snapshot_retention_hours=192, trade_retention_hours=192)
    assert deleted["asset_snapshots"] == 0 and deleted["liquidation_events"] == 0
    assert repo.last_persistence["error"] == "disk on fire"
    assert repo.db.connection.execute("SELECT COUNT(*) FROM asset_snapshots").fetchone()[0] == 3

    monkeypatch.undo()
    deleted = repo.prune_old_data(snapshot_retention_hours=192, trade_retention_hours=192)
    assert deleted["asset_snapshots"] == 2 and deleted["liquidation_events"] == 1


def test_prune_can_be_asked_to_skip_measurement_explicitly(repo):
    now = int(time.time() * 1000)
    repo.insert_snapshots([_snap("AAA", now - 300 * H), _snap("AAA", now)])
    deleted = repo.prune_old_data(snapshot_retention_hours=192, persist_first=False)
    assert deleted["asset_snapshots"] == 1
    assert repo.last_persistence is None
