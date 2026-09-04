"""
Round 5 refinement tests:
  Task 1 - squeeze exhaustion trigger (active unwind detection)
  Task 3 - dynamic backtester coverage thresholds
  Task 4 - persistent collector service supervisor

Fully offline: synthetic series, injected lookups, fake child processes.
"""

import json
import logging
import tempfile
import time
import unittest
from pathlib import Path

from analytics.squeeze_engine import analyse_coin, is_exhausting, is_regime_aligned
from analytics.funding_backtester import (
    backtest_funding_harvest,
    coverage_threshold_for,
    insufficient_history_label,
)
from storage.db import DatabaseManager
from storage.repository import MarketRepository
import run_collector_service as svc

H = 3_600_000
M = 60_000


def _series(rates, ois=None, pxs=None, step=M):
    n = len(rates)
    ois = ois or [1_000_000.0] * n
    pxs = pxs or [100.0] * n
    return [(i * step, rates[i], ois[i], pxs[i]) for i in range(n)]


# --------------------------------------------------------------------------
# Task 1: exhaustion trigger
# --------------------------------------------------------------------------

class TestExhaustionTrigger(unittest.TestCase):
    def test_committed_longs_collapsing_is_exhaustion(self):
        self.assertTrue(is_exhausting(20.0, mean_funding=0.001, persistence=0.9))

    def test_committed_shorts_covering_is_exhaustion(self):
        self.assertTrue(is_exhausting(80.0, mean_funding=-0.001, persistence=0.9))

    def test_drift_to_the_median_is_not_an_unwind(self):
        """Between the bands is indecisive; it has to break out of its own range."""
        self.assertFalse(is_exhausting(40.0, mean_funding=0.001, persistence=0.9))
        self.assertFalse(is_exhausting(60.0, mean_funding=-0.001, persistence=0.9))

    def test_uncommitted_crowd_cannot_exhaust(self):
        """Persistence must exceed 0.75 first - you cannot unwind what never crowded."""
        self.assertFalse(is_exhausting(10.0, mean_funding=0.001, persistence=0.5))
        self.assertFalse(is_exhausting(10.0, mean_funding=0.001, persistence=0.75))

    def test_still_crowded_is_not_exhausting(self):
        self.assertFalse(is_exhausting(95.0, mean_funding=0.001, persistence=0.95))

    def test_flat_regime_never_exhausts(self):
        self.assertFalse(is_exhausting(10.0, mean_funding=0.0, persistence=0.9))

    def test_bands_are_configurable(self):
        self.assertTrue(is_exhausting(45.0, 0.001, 0.9, low_band=50.0))
        self.assertFalse(is_exhausting(45.0, 0.001, 0.9, low_band=40.0))

    def test_exhaustion_and_alignment_are_mutually_exclusive(self):
        """A market cannot be both still-loading and actively unwinding."""
        for pct in (5.0, 20.0, 34.0, 66.0, 80.0, 95.0):
            for mean in (0.001, -0.001):
                if is_exhausting(pct, mean, 0.9):
                    self.assertFalse(is_regime_aligned(pct, mean))

    def test_analyse_coin_flags_an_active_unwind(self):
        # Long, committed positive regime, then funding collapses out of range.
        rates = [0.002] * 24 + [0.00001] * 3
        r = analyse_coin("T", series=_series(rates), min_samples=20)
        self.assertTrue(r["is_exhausting"])
        self.assertFalse(r["regime_aligned"])

    def test_analyse_coin_does_not_flag_a_still_crowded_market(self):
        rates = [0.0005] * 20 + [0.002] * 5
        r = analyse_coin("T", series=_series(rates), min_samples=20)
        self.assertFalse(r["is_exhausting"])
        self.assertTrue(r["regime_aligned"])


# --------------------------------------------------------------------------
# Task 2: gating + conviction
# --------------------------------------------------------------------------
class TestDynamicCoverage(unittest.TestCase):
    def test_anchor_points(self):
        """Tiers became a continuous curve; only the anchors are exact now."""
        self.assertEqual(coverage_threshold_for(24.0), 75.0)
        self.assertEqual(coverage_threshold_for(168.0), 50.0)
        self.assertAlmostEqual(coverage_threshold_for(72.0), 60.8856, places=3)

    def test_short_windows_use_the_strictest_tier(self):
        self.assertEqual(coverage_threshold_for(1.0), 75.0)

    def test_interpolates_between_the_anchors(self):
        """Interpolation is logarithmic in window length, not linear."""
        mid = coverage_threshold_for(96.0)
        self.assertLess(mid, 75.0)
        self.assertGreater(mid, 50.0)
        # Equal doublings move the bar equally: 24->48 == 48->96.
        self.assertAlmostEqual(
            coverage_threshold_for(24.0) - coverage_threshold_for(48.0),
            coverage_threshold_for(48.0) - coverage_threshold_for(96.0),
            places=6,
        )

    def test_beyond_a_week_does_not_relax_further(self):
        self.assertEqual(coverage_threshold_for(1000.0), 50.0)

    def test_curve_is_monotonically_decreasing(self):
        values = [coverage_threshold_for(h) for h in (1, 24, 48, 72, 120, 168, 500)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_label_names_the_bar_that_was_missed(self):
        self.assertIn("75", insufficient_history_label(24.0))
        self.assertIn("60", insufficient_history_label(72.0))
        self.assertIn("50", insufficient_history_label(168.0))

    def test_same_observed_data_passes_short_window_and_fails_long_one(self):
        """20 observed hours is 83% of a day but only 28% of three days."""
        series = [(i * H, 0.001, 100.0) for i in range(21)]
        short = backtest_funding_harvest("T", hours=24, series=series,
                                         now_ms=24 * H, max_gap_hours=1.5)
        long = backtest_funding_harvest("T", hours=72, series=series,
                                        now_ms=72 * H, max_gap_hours=1.5)
        self.assertIsNotNone(short["realised_apr"])
        self.assertIsNone(long["realised_apr"])
        self.assertEqual(short["coverage_threshold_pct"], 75.0)
        self.assertAlmostEqual(long["coverage_threshold_pct"], 60.8856, places=3)

    def test_measured_return_survives_even_when_apr_is_withheld(self):
        series = [(i * H, 0.001, 100.0) for i in range(21)]
        r = backtest_funding_harvest("T", hours=72, series=series,
                                     now_ms=72 * H, max_gap_hours=1.5)
        self.assertIsNone(r["realised_apr"])
        self.assertGreater(r["funding_pnl_pct"], 0.0)


# --------------------------------------------------------------------------
# Task 4: collector service supervisor
# --------------------------------------------------------------------------

class FakeProcess:
    """Stands in for a collector child that exits after `poll_calls` polls."""

    def __init__(self, pid=999, returncode=1, poll_calls=1):
        self.pid = pid
        self.returncode = returncode
        self._remaining = poll_calls
        self.terminated = False
        self.killed = False

    def poll(self):
        if self._remaining > 0:
            self._remaining -= 1
            return None
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode


class TestCollectorService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "svc.jsonl"
        # Own lockfile per test: the default is the production one, which a real
        # running service holds - the supervisor would correctly refuse to start
        # and every assertion below would be testing that refusal instead.
        self.pid_file = Path(self.tmp.name) / "svc.pid"

    def tearDown(self):
        for h in list(logging.getLogger("CollectorService").handlers):
            h.close()
        logging.getLogger("CollectorService").handlers.clear()
        try:
            self.tmp.cleanup()
        except (OSError, PermissionError):
            pass

    def _read_events(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_logs_are_valid_json_lines(self):
        logger = svc.build_logger(self.log, quiet=True)
        svc.log_event(logger, "unit_test", answer=42, note="hello")
        events = self._read_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "unit_test")
        self.assertEqual(events[0]["answer"], 42)
        self.assertIn("ts", events[0])
        self.assertIn("level", events[0])

    def test_supervisor_restarts_after_a_crash(self):
        sup = svc.CollectorSupervisor(log_file=self.log, max_restarts=3, quiet=True, pid_file=self.pid_file)
        spawned = []

        def fake_spawn():
            p = FakeProcess(pid=100 + len(spawned), returncode=1, poll_calls=0)
            spawned.append(p)
            return p

        sup._spawn = fake_spawn
        # Collapse the backoff so the test does not actually wait.
        svc.INITIAL_BACKOFF_SECONDS, orig = 0.0, svc.INITIAL_BACKOFF_SECONDS
        try:
            summary = sup.run()
        finally:
            svc.INITIAL_BACKOFF_SECONDS = orig

        self.assertEqual(len(spawned), 3)
        self.assertEqual(summary["restarts"], 3)
        events = {e["event"] for e in self._read_events()}
        self.assertIn("collector_crashed_early", events)
        self.assertIn("restart_budget_exhausted", events)

    def test_early_crash_is_logged_at_error_level(self):
        sup = svc.CollectorSupervisor(log_file=self.log, max_restarts=1, quiet=True, pid_file=self.pid_file)
        sup._spawn = lambda: FakeProcess(returncode=1, poll_calls=0)
        svc.INITIAL_BACKOFF_SECONDS, orig = 0.0, svc.INITIAL_BACKOFF_SECONDS
        try:
            sup.run()
        finally:
            svc.INITIAL_BACKOFF_SECONDS = orig
        crash = [e for e in self._read_events() if e["event"] == "collector_crashed_early"]
        self.assertTrue(crash)
        self.assertEqual(crash[0]["level"], "ERROR")
        self.assertEqual(crash[0]["exit_code"], 1)

    def test_spawn_failure_does_not_kill_the_supervisor(self):
        sup = svc.CollectorSupervisor(log_file=self.log, max_restarts=1, quiet=True, pid_file=self.pid_file)
        calls = {"n": 0}

        def failing_spawn():
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("cannot fork")
            return FakeProcess(returncode=0, poll_calls=0)

        sup._spawn = failing_spawn
        svc.INITIAL_BACKOFF_SECONDS, orig = 0.0, svc.INITIAL_BACKOFF_SECONDS
        try:
            sup.run()
        finally:
            svc.INITIAL_BACKOFF_SECONDS = orig
        events = {e["event"] for e in self._read_events()}
        self.assertIn("spawn_failed", events)

    def test_stop_terminates_the_child(self):
        sup = svc.CollectorSupervisor(log_file=self.log, quiet=True, pid_file=self.pid_file)
        proc = FakeProcess(poll_calls=100)
        sup.process = proc
        sup.running = True
        sup.stop()
        self.assertFalse(sup.running)
        self.assertTrue(proc.terminated)

    def test_service_start_and_stop_are_both_recorded(self):
        sup = svc.CollectorSupervisor(log_file=self.log, max_restarts=1, quiet=True, pid_file=self.pid_file)
        sup._spawn = lambda: FakeProcess(returncode=0, poll_calls=0)
        svc.INITIAL_BACKOFF_SECONDS, orig = 0.0, svc.INITIAL_BACKOFF_SECONDS
        try:
            sup.run()
        finally:
            svc.INITIAL_BACKOFF_SECONDS = orig
        events = [e["event"] for e in self._read_events()]
        self.assertEqual(events[0], "service_start")
        self.assertEqual(events[-1], "service_stop")


class TestCoverageMeasurement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.tmp.name) / "cov.db")
        self.repo = MarketRepository(self.db)
        self.repo.upsert_assets([
            {"coin": "BTC", "dex": "main", "sz_decimals": 4, "max_leverage": 40, "only_isolated": False}
        ])

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
        DatabaseManager._instance = None

    def _snap(self, ts):
        return {"timestamp": ts, "coin": "BTC", "dex": "main", "mark_px": 100.0,
                "mid_px": 100.0, "oracle_px": 100.0, "open_interest": 1.0,
                "notional_oi": 100.0, "funding_rate": 0.0001, "premium": 0.0,
                "day_ntl_vlm": 10.0}

    def test_continuous_history_reports_high_coverage(self):
        now = int(time.time() * 1000)
        # Dense sampling across the last hour.
        self.repo.insert_snapshots([self._snap(now - i * 10_000) for i in range(360)])
        stats = svc.measure_coverage(hours=1.0)
        self.assertGreater(stats["coverage_pct"], 90.0)

    def test_bursty_history_reports_low_coverage(self):
        """The exact failure mode the service exists to prevent."""
        now = int(time.time() * 1000)
        burst = [self._snap(now - i * 10_000) for i in range(30)]      # 5 min
        old = [self._snap(now - 23 * H - i * 10_000) for i in range(30)]
        self.repo.insert_snapshots(burst + old)
        stats = svc.measure_coverage(hours=24.0)
        self.assertLess(stats["coverage_pct"], 10.0)
        self.assertGreater(stats["gap_hours"], 1.0)

    def test_empty_history_is_zero_not_an_error(self):
        stats = svc.measure_coverage(hours=24.0)
        self.assertEqual(stats["coverage_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
