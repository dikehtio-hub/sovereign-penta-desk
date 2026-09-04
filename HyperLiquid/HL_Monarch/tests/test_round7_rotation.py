"""
Round 7 tests:
  Task 1 - dynamic exotic squeeze WS subscription rotation
  Task 2 - PID lockfile supervision + logarithmic coverage interpolation
  Task 3 - production DB isolation (asserted structurally)

Fully offline: fake websockets, temp lockfiles, no network.
"""

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path

from api.ws_client import HyperliquidWsClient
from analytics.funding_backtester import (
    COVERAGE_ANCHOR_LONG_HOURS,
    COVERAGE_ANCHOR_LONG_PCT,
    COVERAGE_ANCHOR_SHORT_HOURS,
    COVERAGE_ANCHOR_SHORT_PCT,
    coverage_threshold_for,
)
import run_collector_service as svc


class FakeWs:
    """Records frames sent by the client."""

    def __init__(self):
        self.sent = []

    async def send(self, msg):
        self.sent.append(json.loads(msg))

    async def close(self):
        pass

    def methods(self, method):
        return [m for m in self.sent if m.get("method") == method]


# --------------------------------------------------------------------------
# Task 1: subscribe / unsubscribe plumbing
# --------------------------------------------------------------------------

class TestSubscriptionPlumbing(unittest.TestCase):
    def test_generic_subscribe_builds_the_right_frame(self):
        async def run():
            c = HyperliquidWsClient()
            ws = FakeWs()
            c.ws = ws
            await c.subscribe("trades", {"coin": "SKR"})
            return ws.sent

        sent = asyncio.run(run())
        self.assertEqual(sent[0]["method"], "subscribe")
        self.assertEqual(sent[0]["subscription"], {"type": "trades", "coin": "SKR"})

    def test_unsubscribe_sends_and_forgets(self):
        async def run():
            c = HyperliquidWsClient()
            ws = FakeWs()
            c.ws = ws
            await c.subscribe("trades", {"coin": "SKR"})
            removed = await c.unsubscribe_trades("SKR")
            return removed, c.subscribed_trade_coins(), ws.methods("unsubscribe")

        removed, coins, unsubs = asyncio.run(run())
        self.assertTrue(removed)
        self.assertNotIn("SKR", coins)
        self.assertEqual(unsubs[0]["subscription"], {"type": "trades", "coin": "SKR"})

    def test_unsubscribing_something_not_held_is_false(self):
        async def run():
            c = HyperliquidWsClient()
            c.ws = FakeWs()
            return await c.unsubscribe_trades("NOPE")

        self.assertFalse(asyncio.run(run()))

    def test_unsubscribed_coin_is_not_replayed_on_reconnect(self):
        """
        The critical part: if a rotated-out coin stayed in _subscriptions it would
        silently return on the next reconnect and the set would only ever grow.
        """
        async def run():
            c = HyperliquidWsClient()
            c.ws = FakeWs()
            await c.subscribe_trades("KEEP")
            await c.subscribe_trades("DROP")
            await c.unsubscribe_trades("DROP")

            fresh = FakeWs()
            await c._resubscribe_all(fresh)
            return [m["subscription"].get("coin") for m in fresh.methods("subscribe")]

        replayed = asyncio.run(run())
        self.assertIn("KEEP", replayed)
        self.assertNotIn("DROP", replayed)

    def test_unsubscribe_without_a_socket_still_forgets(self):
        """Rotation must work even while the socket is down mid-reconnect."""
        async def run():
            c = HyperliquidWsClient()
            await c.subscribe_trades("SKR")   # queued, no ws
            removed = await c.unsubscribe_trades("SKR")
            return removed, c.subscribed_trade_coins()

        removed, coins = asyncio.run(run())
        self.assertTrue(removed)
        self.assertEqual(coins, set())

    def test_introspection_ignores_non_trade_channels(self):
        async def run():
            c = HyperliquidWsClient()
            c.ws = FakeWs()
            await c.subscribe_all_mids()
            await c.subscribe_trades("BTC")
            return c.subscribed_trade_coins(), len(c.active_subscriptions())

        coins, total = asyncio.run(run())
        self.assertEqual(coins, {"BTC"})
        self.assertEqual(total, 2)


# --------------------------------------------------------------------------
# Task 1: rotation policy
# --------------------------------------------------------------------------

class RotationHarness:
    """
    Exercises the rotation policy without constructing a real MarketCollector
    (which would open the production database and a REST client).
    """

    def __init__(self, core, candidates):
        self.core = set(core)
        self.candidates = candidates
        self.client = HyperliquidWsClient()
        self.rotated = set()

    async def prime_core(self):
        self.client.ws = FakeWs()
        for c in self.core:
            await self.client.subscribe_trades(c)

    async def rotate(self, candidates=None):
        cands = self.candidates if candidates is None else candidates
        wanted = {c for c in cands if c not in self.core}
        for coin in self.rotated - wanted:
            await self.client.unsubscribe_trades(coin)
        for coin in wanted - self.rotated:
            await self.client.subscribe("trades", {"coin": coin})
        self.rotated = wanted
        return wanted


class TestRotationPolicy(unittest.TestCase):
    def test_core_watchlist_is_never_rotated_out(self):
        async def run():
            h = RotationHarness(core={"BTC", "ETH"}, candidates=["SKR", "0G"])
            await h.prime_core()
            await h.rotate()
            await h.rotate(candidates=[])   # everything drops out
            return h.client.subscribed_trade_coins()

        coins = asyncio.run(run())
        self.assertEqual(coins, {"BTC", "ETH"})

    def test_core_coin_appearing_as_a_candidate_is_not_double_subscribed(self):
        async def run():
            h = RotationHarness(core={"BTC"}, candidates=["BTC", "SKR"])
            await h.prime_core()
            wanted = await h.rotate()
            return wanted, h.client.subscribed_trade_coins()

        wanted, coins = asyncio.run(run())
        self.assertEqual(wanted, {"SKR"})
        self.assertEqual(coins, {"BTC", "SKR"})

    def test_rotation_adds_and_drops_incrementally(self):
        async def run():
            h = RotationHarness(core=set(), candidates=["A", "B", "C"])
            await h.prime_core()
            await h.rotate()
            first = set(h.client.subscribed_trade_coins())
            await h.rotate(candidates=["B", "C", "D"])
            return first, h.client.subscribed_trade_coins()

        first, second = asyncio.run(run())
        self.assertEqual(first, {"A", "B", "C"})
        self.assertEqual(second, {"B", "C", "D"})

    def test_unchanged_candidates_produce_no_traffic(self):
        """A stable candidate set must not re-send frames every 60s."""
        async def run():
            h = RotationHarness(core=set(), candidates=["A", "B"])
            await h.prime_core()
            await h.rotate()
            before = len(h.client.ws.sent)
            await h.rotate()
            return before, len(h.client.ws.sent)

        before, after = asyncio.run(run())
        self.assertEqual(before, after)

    def test_subscription_count_stays_bounded(self):
        async def run():
            h = RotationHarness(core=set(), candidates=[])
            await h.prime_core()
            for cycle in range(10):
                await h.rotate(candidates=[f"C{cycle}_{i}" for i in range(20)])
            return h.client.subscribed_trade_coins()

        coins = asyncio.run(run())
        self.assertEqual(len(coins), 20)


# --------------------------------------------------------------------------
# Task 2: PID lockfile
# --------------------------------------------------------------------------

class TestPidLockfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pid_file = Path(self.tmp.name) / "svc.pid"

    def tearDown(self):
        # The supervisor's FileHandler keeps the JSONL log open, and Windows
        # refuses to delete a file that still has an open handle.
        import logging as _logging
        for h in list(_logging.getLogger("CollectorService").handlers):
            h.close()
        _logging.getLogger("CollectorService").handlers.clear()
        try:
            self.tmp.cleanup()
        except (OSError, PermissionError):
            pass

    def test_no_lockfile_means_not_running(self):
        self.assertIsNone(svc.running_supervisor_pid(self.pid_file))

    def test_acquire_writes_our_pid(self):
        self.assertTrue(svc.acquire_pid_lock(self.pid_file))
        self.assertEqual(svc.read_pid_file(self.pid_file), os.getpid())
        self.assertEqual(svc.running_supervisor_pid(self.pid_file), os.getpid())

    def test_reacquiring_our_own_lock_succeeds(self):
        svc.acquire_pid_lock(self.pid_file)
        self.assertTrue(svc.acquire_pid_lock(self.pid_file))

    def test_stale_lockfile_is_taken_over(self):
        """A machine that lost power must not need manual cleanup to restart."""
        self.pid_file.write_text("999999", encoding="utf-8")
        self.assertIsNone(svc.running_supervisor_pid(self.pid_file))
        self.assertTrue(svc.acquire_pid_lock(self.pid_file))
        self.assertEqual(svc.read_pid_file(self.pid_file), os.getpid())

    def test_corrupt_lockfile_is_treated_as_absent(self):
        self.pid_file.write_text("not-a-pid", encoding="utf-8")
        self.assertIsNone(svc.read_pid_file(self.pid_file))
        self.assertTrue(svc.acquire_pid_lock(self.pid_file))

    def test_live_foreign_lock_blocks_acquisition(self):
        # Our parent shell is a live pid that is not us.
        foreign = os.getppid()
        if foreign == os.getpid() or not svc.pid_is_alive(foreign):
            self.skipTest("no usable foreign live pid")
        self.pid_file.write_text(str(foreign), encoding="utf-8")
        self.assertFalse(svc.acquire_pid_lock(self.pid_file))

    def test_release_removes_our_lock(self):
        svc.acquire_pid_lock(self.pid_file)
        svc.release_pid_lock(self.pid_file)
        self.assertFalse(self.pid_file.exists())

    def test_release_leaves_someone_elses_lock_alone(self):
        self.pid_file.write_text("999999", encoding="utf-8")
        svc.release_pid_lock(self.pid_file)
        self.assertTrue(self.pid_file.exists())

    def test_pid_liveness_probe(self):
        self.assertTrue(svc.pid_is_alive(os.getpid()))
        self.assertFalse(svc.pid_is_alive(999999))
        self.assertFalse(svc.pid_is_alive(0))
        self.assertFalse(svc.pid_is_alive(-1))

    def test_liveness_probe_does_not_kill_what_it_inspects(self):
        """
        Regression. On Windows, CPython maps os.kill(pid, 0) onto
        TerminateProcess, so the usual POSIX liveness idiom KILLS the target with
        exit code 0. Using it here meant `--status` terminated the supervisor it
        was asked to report on, orphaning the collector child.
        """
        import subprocess
        import sys as _sys
        import time as _time

        proc = subprocess.Popen([_sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            _time.sleep(0.7)
            for _ in range(3):
                self.assertTrue(svc.pid_is_alive(proc.pid))
            self.assertIsNone(proc.poll(), "liveness probe terminated the process")
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        self.assertFalse(svc.pid_is_alive(proc.pid))

    def test_supervisor_refuses_to_double_start(self):
        foreign = os.getppid()
        if foreign == os.getpid() or not svc.pid_is_alive(foreign):
            self.skipTest("no usable foreign live pid")
        self.pid_file.write_text(str(foreign), encoding="utf-8")
        sup = svc.CollectorSupervisor(
            log_file=Path(self.tmp.name) / "svc.jsonl",
            pid_file=self.pid_file, quiet=True, max_restarts=1,
        )
        summary = sup.run()
        self.assertTrue(summary.get("already_running"))
        self.assertEqual(summary["restarts"], 0)

    def test_backoff_ceiling_exceeds_the_healthy_window(self):
        self.assertEqual(svc.MAX_BACKOFF_SECONDS, 600.0)
        self.assertGreater(svc.MAX_BACKOFF_SECONDS, svc.HEALTHY_RUNTIME_SECONDS)


# --------------------------------------------------------------------------
# Task 2: logarithmic coverage curve
# --------------------------------------------------------------------------

class TestLogarithmicCoverage(unittest.TestCase):
    def test_anchors_are_exact(self):
        self.assertEqual(coverage_threshold_for(COVERAGE_ANCHOR_SHORT_HOURS), COVERAGE_ANCHOR_SHORT_PCT)
        self.assertEqual(coverage_threshold_for(COVERAGE_ANCHOR_LONG_HOURS), COVERAGE_ANCHOR_LONG_PCT)

    def test_equal_doublings_move_the_bar_equally(self):
        """The point of going logarithmic: evidence grows multiplicatively."""
        d1 = coverage_threshold_for(24) - coverage_threshold_for(48)
        d2 = coverage_threshold_for(48) - coverage_threshold_for(96)
        self.assertAlmostEqual(d1, d2, places=6)

    def test_log_curve_is_stricter_than_linear_early_on(self):
        """A 48h window now demands more coverage than linear interpolation did."""
        linear_48 = 75.0 + (50.0 - 75.0) * ((48.0 - 24.0) / (168.0 - 24.0))
        self.assertLess(coverage_threshold_for(48), linear_48)

    def test_clamped_outside_the_anchor_range(self):
        self.assertEqual(coverage_threshold_for(1.0), 75.0)
        self.assertEqual(coverage_threshold_for(1000.0), 50.0)

    def test_zero_and_negative_hours_do_not_explode(self):
        """log(0) is undefined; the guard must return the clamp, not raise."""
        self.assertEqual(coverage_threshold_for(0.0), 75.0)
        self.assertEqual(coverage_threshold_for(-5.0), 75.0)

    def test_curve_is_monotonically_decreasing(self):
        values = [coverage_threshold_for(h) for h in (1, 24, 36, 48, 72, 120, 168, 500)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_longer_window_still_demands_more_absolute_hours(self):
        short_h = 24.0 * coverage_threshold_for(24.0) / 100.0
        long_h = 168.0 * coverage_threshold_for(168.0) / 100.0
        self.assertGreater(long_h, short_h)


# --------------------------------------------------------------------------
# Task 3: production DB isolation
# --------------------------------------------------------------------------

class TestProductionDbIsolation(unittest.TestCase):
    """
    Structural guard. These tests previously constructed a bare
    MarketRepository(), which resolves to the live hyperliquid_data.db - so they
    passed or failed depending on what the collector had written, and wrote test
    rows into production. Each must now bind DatabaseManager to a temp path.
    """

    ISOLATED = ("tests/test_whale_tracker.py", "tests/test_obsidian_exporter.py")

    def _source(self, rel):
        return (Path(__file__).resolve().parent.parent / rel).read_text(encoding="utf-8")

    def test_isolated_tests_bind_a_temp_database(self):
        for rel in self.ISOLATED:
            src = self._source(rel)
            self.assertIn("DatabaseManager._instance = None", src, f"{rel} does not reset the singleton")
            self.assertIn("TemporaryDirectory", src, f"{rel} does not use a temp directory")

    def test_isolated_tests_restore_the_singleton_afterwards(self):
        """
        A bare MarketRepository() inside a test body is fine once setUp has
        rebound the singleton - what matters is that the binding is established
        before use and torn down after, so it cannot leak into other tests.
        """
        for rel in self.ISOLATED:
            src = self._source(rel)
            self.assertGreaterEqual(
                src.count("DatabaseManager._instance = None"), 2,
                f"{rel} must reset the singleton in both setUp and tearDown",
            )


if __name__ == "__main__":
    unittest.main()
