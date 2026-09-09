"""Round 121 hardening (Ruling R119-1.B): one unknown coin degrades the stream by one coin, not to zero;
the universe re-syncs on a schedule and at once after a skip; the watchdog restarts on a stale stream only."""
from __future__ import annotations

import tempfile
import time
import types
import unittest
from pathlib import Path

from storage.db import DatabaseManager
from storage.repository import MarketRepository
import run_collector_service as svc


def snap(coin: str, ts: int) -> dict:
    return {"timestamp": ts, "coin": coin, "dex": "main", "mark_px": 1.0, "mid_px": 1.0, "oracle_px": 1.0,
            "open_interest": 10.0, "notional_oi": 10.0, "funding_rate": 0.0, "premium": 0.0, "day_ntl_vlm": 100.0}


class TestResilientSnapshots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.tmp.name) / "t.db")
        self.repo = MarketRepository(self.db)
        self.repo.upsert_assets([{"coin": "BTC", "dex": "main", "sz_decimals": 4, "max_leverage": 50, "only_isolated": False},
                                 {"coin": "ETH", "dex": "main", "sz_decimals": 4, "max_leverage": 50, "only_isolated": False}])

    def tearDown(self):
        # Windows: the temp db cannot be removed while a connection is open; close, drop the singleton, then remove
        for attr in ("close", "shutdown"):
            fn = getattr(self.db, attr, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
        DatabaseManager._instance = None
        import gc, shutil
        gc.collect()
        shutil.rmtree(self.tmp.name, ignore_errors=True)

    def test_a_clean_batch_is_one_transaction(self):
        r = self.repo.insert_snapshots([snap("BTC", 1000), snap("ETH", 1000)])
        self.assertEqual(r, {"written": 2, "skipped": []})

    def test_one_unknown_coin_costs_one_row_and_is_named(self):
        r = self.repo.insert_snapshots([snap("BTC", 2000), snap("para:CIFR", 2000), snap("ETH", 2000)])
        self.assertEqual(r, {"written": 2, "skipped": ["para:CIFR"]})
        with self.db.connection as conn:
            rows = conn.execute("SELECT coin FROM asset_snapshots WHERE timestamp = 2000 ORDER BY coin").fetchall()
            latest = conn.execute("SELECT coin, timestamp FROM latest_snapshots ORDER BY coin").fetchall()
        self.assertEqual([r[0] for r in rows], ["BTC", "ETH"])
        self.assertEqual([tuple(r) for r in latest], [("BTC", 2000), ("ETH", 2000)])

    def test_empty_batch_is_a_noop(self):
        self.assertEqual(self.repo.insert_snapshots([]), {"written": 0, "skipped": []})


class TestUniverseSyncCadence(unittest.TestCase):
    def test_due_every_n_polls_and_at_once_when_forced(self):
        from collectors.market_collector import MarketCollector, UNIVERSE_SYNC_EVERY_POLLS
        ns = types.SimpleNamespace()
        hits = [MarketCollector._universe_sync_due(ns) for _ in range(UNIVERSE_SYNC_EVERY_POLLS)]
        self.assertEqual(hits.count(True), 1)
        self.assertTrue(hits[-1])
        ns2 = types.SimpleNamespace(_force_universe_sync=True)
        self.assertTrue(MarketCollector._universe_sync_due(ns2))


class TestWatchdogDecision(unittest.TestCase):
    def test_healthy_is_nothing(self):
        self.assertEqual(svc.watchdog_decision(12.0, 98.0, 99.0, True, None)["action"], "none")

    def test_stale_stream_restarts_once_per_cooldown(self):
        d = svc.watchdog_decision(9 * 3600.0, 62.0, 63.0, True, None)
        self.assertEqual(d["action"], "restart")
        self.assertTrue(any("newest snapshot" in r for r in d["reasons"]))
        self.assertEqual(svc.watchdog_decision(9 * 3600.0, 62.0, 63.0, True, 120.0)["action"], "warn")
        self.assertEqual(svc.watchdog_decision(9 * 3600.0, 62.0, 63.0, True, svc.WATCHDOG_COOLDOWN_SECONDS)["action"], "restart")

    def test_coverage_decay_alone_only_warns(self):
        """After a 9 h gap, coverage sits under 60% for a day while the collector is healthy: not a restart."""
        d = svc.watchdog_decision(8.0, 55.0, 61.0, True, None)
        self.assertEqual(d["action"], "warn")
        self.assertEqual(len(d["reasons"]), 2)

    def test_a_dead_child_is_the_crash_policy_s_job(self):
        self.assertEqual(svc.watchdog_decision(9 * 3600.0, 10.0, 90.0, False, None)["action"], "none")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
