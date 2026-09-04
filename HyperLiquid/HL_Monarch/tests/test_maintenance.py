"""
Unit tests for DB retention/WAL maintenance and the weight-aware rate limiter.
"""
import time
import tempfile
import unittest
from pathlib import Path

from storage.db import DatabaseManager
from storage.repository import MarketRepository
from api.rest_client import TokenBucketRateLimiter, weight_for


HOUR_MS = 3600 * 1000


def _snapshot(coin: str, ts: int) -> dict:
    return {
        "timestamp": ts,
        "coin": coin,
        "dex": "xyz",
        "mark_px": 100.0,
        "mid_px": 100.0,
        "oracle_px": 100.0,
        "open_interest": 10.0,
        "notional_oi": 1000.0,
        "funding_rate": 0.0001,
        "premium": 0.0,
        "day_ntl_vlm": 5000.0,
    }


class TestRetentionMaintenance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.temp_dir.name) / "maint.db")
        self.repo = MarketRepository(self.db)
        self.repo.upsert_assets([
            {"coin": "xyz:GOLD", "dex": "xyz", "sz_decimals": 4, "max_leverage": 25, "only_isolated": False}
        ])

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()
        DatabaseManager._instance = None

    def _count(self, table: str) -> int:
        return self.db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_prune_drops_expired_but_keeps_newest_per_coin(self):
        now = int(time.time() * 1000)
        self.repo.insert_snapshots([
            _snapshot("xyz:GOLD", now - 200 * HOUR_MS),   # expired
            _snapshot("xyz:GOLD", now - 150 * HOUR_MS),   # expired
            _snapshot("xyz:GOLD", now - 1 * HOUR_MS),     # fresh
        ])
        self.assertEqual(self._count("asset_snapshots"), 3)

        deleted = self.repo.prune_old_data(snapshot_retention_hours=72)
        self.assertEqual(deleted["asset_snapshots"], 2)
        self.assertEqual(self._count("asset_snapshots"), 1)

    def test_prune_never_empties_a_coin_entirely(self):
        """A stale collector must not leave the dashboard with zero rows."""
        now = int(time.time() * 1000)
        self.repo.insert_snapshots([
            _snapshot("xyz:GOLD", now - 500 * HOUR_MS),
            _snapshot("xyz:GOLD", now - 400 * HOUR_MS),
        ])
        self.repo.prune_old_data(snapshot_retention_hours=1)
        self.assertEqual(self._count("asset_snapshots"), 1)
        self.assertEqual(len(self.repo.get_latest_snapshots(coins=["xyz:GOLD"])), 1)

    def test_prune_trims_trades_and_liquidation_events(self):
        now = int(time.time() * 1000)
        self.repo.insert_trades([
            {"tid": 1, "coin": "xyz:GOLD", "side": "B", "px": 100.0, "sz": 1.0,
             "notional": 100.0, "time": now - 400 * HOUR_MS, "hash": "0x1", "is_liquidation": False},
            {"tid": 2, "coin": "xyz:GOLD", "side": "B", "px": 100.0, "sz": 1.0,
             "notional": 100.0, "time": now, "hash": "0x2", "is_liquidation": False},
        ])
        self.repo.insert_liquidation_events([
            {"coin": "xyz:GOLD", "side": "A", "px": 100.0, "sz": 1.0, "notional": 100.0,
             "time": now - 400 * HOUR_MS, "source": "trade_sweep", "note": "old"},
        ])
        deleted = self.repo.prune_old_data(trade_retention_hours=168)
        self.assertEqual(deleted["trades"], 1)
        self.assertEqual(deleted["liquidation_events"], 1)
        self.assertEqual(self._count("trades"), 1)

    def test_run_maintenance_checkpoints_wal_and_reports_size(self):
        now = int(time.time() * 1000)
        self.repo.insert_snapshots([_snapshot("xyz:GOLD", now - 500 * HOUR_MS) for _ in range(50)])
        stats = self.repo.run_maintenance()
        self.assertIn("deleted", stats)
        self.assertGreater(stats["db_bytes"], 0)
        self.assertGreaterEqual(stats["checkpointed_pages"], 0)
        # WAL is reclaimed, so the sidecar file must not be left holding pages.
        wal = Path(str(self.db._db_path) + "-wal")
        if wal.exists():
            self.assertLessEqual(wal.stat().st_size, 1024 * 1024)

    def test_latest_snapshots_served_from_current_state_table(self):
        """Reads come from latest_snapshots, and always reflect the newest write."""
        now = int(time.time() * 1000)
        self.repo.insert_snapshots([_snapshot("xyz:GOLD", now - 5 * HOUR_MS)])
        fresh = _snapshot("xyz:GOLD", now)
        fresh["mark_px"] = 4321.0
        self.repo.insert_snapshots([fresh])

        rows = self.repo.get_latest_snapshots()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mark_px"], 4321.0)
        self.assertEqual(self._count("latest_snapshots"), 1)

    def test_latest_snapshots_ignores_out_of_order_batch(self):
        """A replayed or late batch must not roll the current state backwards."""
        now = int(time.time() * 1000)
        current = _snapshot("xyz:GOLD", now)
        current["mark_px"] = 100.0
        self.repo.insert_snapshots([current])

        stale = _snapshot("xyz:GOLD", now - 10 * HOUR_MS)
        stale["mark_px"] = 1.0
        self.repo.insert_snapshots([stale])

        self.assertEqual(self.repo.get_latest_snapshots()[0]["mark_px"], 100.0)

    def test_prune_survives_current_state_table(self):
        """Pruning history must leave the dashboard's current state intact."""
        now = int(time.time() * 1000)
        self.repo.insert_snapshots([_snapshot("xyz:GOLD", now - 500 * HOUR_MS)])
        self.repo.run_maintenance()
        self.assertEqual(len(self.repo.get_latest_snapshots()), 1)

    def test_backfill_populates_current_state_from_history(self):
        """Databases written before latest_snapshots existed must migrate cleanly."""
        now = int(time.time() * 1000)
        self.repo.insert_snapshots([
            _snapshot("xyz:GOLD", now - 3 * HOUR_MS),
            _snapshot("xyz:GOLD", now),
        ])
        self.db.connection.execute("DELETE FROM latest_snapshots")
        self.db.connection.commit()
        self.assertEqual(self._count("latest_snapshots"), 0)

        self.repo.backfill_latest_snapshots()
        rows = self.repo.get_latest_snapshots()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["timestamp"], now)

    def test_total_oi_by_dex_uses_current_state(self):
        now = int(time.time() * 1000)
        self.repo.upsert_assets([
            {"coin": "BTC", "dex": "main", "sz_decimals": 4, "max_leverage": 40, "only_isolated": False}
        ])
        gold = _snapshot("xyz:GOLD", now)
        btc = _snapshot("BTC", now)
        btc["dex"] = "main"
        btc["notional_oi"] = 2500.0
        self.repo.insert_snapshots([gold, btc])

        totals = self.repo.get_total_oi_by_dex()
        self.assertAlmostEqual(totals["xyz"], 1000.0)
        self.assertAlmostEqual(totals["main"], 2500.0)

    def test_checkpoint_rejects_invalid_mode(self):
        with self.assertRaises(ValueError):
            self.db.checkpoint("DROP")


class TestWeightedRateLimiter(unittest.TestCase):
    def test_endpoint_weights(self):
        # metaAndAssetCtxs is a heavy call; l2Book is a cheap one.
        self.assertEqual(weight_for("metaAndAssetCtxs"), 20)
        self.assertEqual(weight_for("l2Book"), 2)
        self.assertEqual(weight_for("clearinghouseState"), 2)

    def test_budget_is_weight_not_request_count(self):
        # 1200 weight/min at safety 1.0 => exactly 60 heavy calls, not 1200.
        limiter = TokenBucketRateLimiter(weight_per_minute=1200, safety_factor=1.0)
        self.assertEqual(limiter.capacity, 1200.0)
        for _ in range(60):
            limiter.acquire(20)
        self.assertLess(limiter.tokens, 20.0)

    def test_acquire_blocks_once_budget_is_spent(self):
        limiter = TokenBucketRateLimiter(weight_per_minute=60, safety_factor=1.0)
        limiter.acquire(60)  # drain
        started = time.monotonic()
        limiter.acquire(1)   # refills at 1 weight/sec, so this must wait ~1s
        self.assertGreaterEqual(time.monotonic() - started, 0.5)

    def test_oversized_request_cannot_deadlock(self):
        limiter = TokenBucketRateLimiter(weight_per_minute=60, safety_factor=1.0)
        limiter.acquire(10_000)  # clamped to capacity instead of blocking forever
        self.assertLessEqual(limiter.tokens, 60.0)


if __name__ == "__main__":
    unittest.main()
