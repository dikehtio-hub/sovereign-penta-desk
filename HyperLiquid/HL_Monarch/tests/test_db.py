"""
Unit tests for DatabaseManager and MarketRepository.
"""
import unittest
import tempfile
from pathlib import Path
from storage.db import DatabaseManager
from storage.repository import MarketRepository

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_data.db"
        # Reset singleton instance for test
        DatabaseManager._instance = None
        self.db = DatabaseManager(self.test_db_path)
        self.repo = MarketRepository(self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()
        DatabaseManager._instance = None

    def test_upsert_assets_and_insert_snapshots(self):
        assets = [
            {"coin": "xyz:TSLA", "dex": "xyz", "sz_decimals": 3, "max_leverage": 20, "only_isolated": False},
            {"coin": "xyz:GOLD", "dex": "xyz", "sz_decimals": 4, "max_leverage": 25, "only_isolated": False}
        ]
        self.repo.upsert_assets(assets)

        snapshots = [
            {
                "timestamp": 1788000000000,
                "coin": "xyz:TSLA",
                "dex": "xyz",
                "mark_px": 350.0,
                "mid_px": 350.1,
                "oracle_px": 350.0,
                "open_interest": 1000.0,
                "notional_oi": 350000.0,
                "funding_rate": 0.0001,
                "premium": 0.0,
                "day_ntl_vlm": 1500000.0
            }
        ]
        self.repo.insert_snapshots(snapshots)

        latest = self.repo.get_latest_snapshots(coins=["xyz:TSLA"])
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["coin"], "xyz:TSLA")
        self.assertEqual(latest[0]["notional_oi"], 350000.0)

    def test_insert_trades_and_liquidations(self):
        trades = [
            {
                "tid": 123456,
                "coin": "xyz:TSLA",
                "side": "B",
                "px": 351.0,
                "sz": 10.0,
                "notional": 3510.0,
                "time": 1788000000000,
                "hash": "0xabc",
                "is_liquidation": True
            }
        ]
        count = self.repo.insert_trades(trades)
        self.assertEqual(count, 1)

        liqs = [
            {
                "coin": "xyz:TSLA",
                "side": "B",
                "px": 351.0,
                "sz": 10.0,
                "notional": 3510.0,
                "time": 1788000000000,
                "source": "trade_sweep",
                "note": "Test liq note"
            }
        ]
        self.repo.insert_liquidation_events(liqs)

        recent = self.repo.get_recent_liquidations(limit=10)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["coin"], "xyz:TSLA")
        self.assertEqual(recent[0]["source"], "trade_sweep")

if __name__ == "__main__":
    unittest.main()
