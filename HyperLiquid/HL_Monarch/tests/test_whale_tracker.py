"""
Unit tests for WhaleTracker (Auto-Discovery Whale Engine).
"""
import os
import tempfile
import unittest
from pathlib import Path
from analytics.whale_tracker import WhaleTracker
from storage.db import DatabaseManager
from storage.repository import MarketRepository

class TestWhaleTracker(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
        self.temp_file.write("0x0000000000000000000000000000000000000001\n")
        self.temp_file.close()

        # Isolate from the production database. This test used to write its
        # synthetic whale into data/hyperliquid_data.db and then assert it came
        # back from get_whale_wallets(), which ranks by position value and caps
        # at 50 rows - so it passed only while that table was near-empty, and
        # started failing as soon as the collector service discovered real
        # whales with real position values.
        self.temp_dir = tempfile.TemporaryDirectory()
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.temp_dir.name) / "whales.db")

        self.tracker = WhaleTracker(
            users_file_path=self.temp_file.name,
            min_whale_notional=10_000.0,
            auto_scan_portfolio=False
        )

    def tearDown(self):
        try:
            os.remove(self.temp_file.name)
        except OSError:
            pass
        self.db.close()
        DatabaseManager._instance = None
        try:
            self.temp_dir.cleanup()
        except (OSError, PermissionError):
            pass  # Windows can hold the sqlite file briefly after close

    def test_whale_discovery_from_trade(self):
        # Trade below threshold should NOT trigger discovery
        small_trade = {
            "coin": "xyz:TSLA",
            "px": "350.0",
            "sz": "5.0",  # $1,750
            "users": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
        }
        res = self.tracker.on_trade_fill(small_trade)
        self.assertEqual(len(res), 0)

        # Trade above $10,000 threshold with a new address should trigger discovery
        whale_addr = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        whale_trade = {
            "coin": "xyz:NVDA",
            "px": "200.0",
            "sz": "100.0",  # $20,000
            "users": [whale_addr]
        }
        discovered = self.tracker.on_trade_fill(whale_trade)
        self.assertEqual(discovered, [whale_addr])
        self.assertIn(whale_addr, self.tracker.known_addresses)

        # Check that address was written to file
        with open(self.temp_file.name, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn(whale_addr, content)

        # Check that address is queryable in SQLite repository
        repo = MarketRepository()
        whales = repo.get_whale_wallets()
        matching = [w for w in whales if w["address"] == whale_addr]
        self.assertTrue(len(matching) >= 1)
        self.assertEqual(matching[0]["first_coin"], "xyz:NVDA")

if __name__ == "__main__":
    unittest.main()
