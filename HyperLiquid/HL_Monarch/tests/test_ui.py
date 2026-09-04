"""
Unit tests for UI components and interactive TerminalDashboard state.
"""
import unittest
from ui.terminal_dashboard import TerminalDashboard, CYCLE_ASSETS
from ui.components import format_currency, format_coin_name

class TestUI(unittest.TestCase):
    def setUp(self):
        self.dashboard = TerminalDashboard(focus_asset="xyz:GOLD")

    def test_formatters(self):
        self.assertEqual(format_currency(1_500_000_000), "$1.50B")
        self.assertEqual(format_currency(25_400_000), "$25.4M")
        self.assertEqual(format_currency(5_200), "$5K")
        self.assertEqual(format_coin_name("xyz:TSLA"), "TSLA")
        self.assertEqual(format_coin_name("BTC"), "BTC")

    def test_category_tab_switching(self):
        self.dashboard.set_tab("STOCKS")
        self.assertEqual(self.dashboard.active_tab, "STOCKS")
        coins = self.dashboard._get_active_watchlist_coins()
        self.assertIn("xyz:TSLA", coins)

        self.dashboard.set_tab("COMMODITIES")
        self.assertEqual(self.dashboard.active_tab, "COMMODITIES")
        coins = self.dashboard._get_active_watchlist_coins()
        self.assertIn("xyz:GOLD", coins)

        self.dashboard.set_tab("CRYPTO")
        self.assertEqual(self.dashboard.active_tab, "CRYPTO")
        coins = self.dashboard._get_active_watchlist_coins()
        self.assertIn("BTC", coins)

    def test_focus_asset_cycling(self):
        initial = self.dashboard.focus_asset
        self.dashboard.cycle_focus_asset()
        next_asset = self.dashboard.focus_asset
        self.assertNotEqual(initial, next_asset)
        self.assertIn(next_asset, CYCLE_ASSETS)

    def test_generate_layout_rendering(self):
        layout = self.dashboard.generate_layout()
        self.assertIsNotNone(layout)
        self.assertIsNotNone(layout["header"])
        self.assertIsNotNone(layout["body"])
        self.assertIsNotNone(layout["footer"])

if __name__ == "__main__":
    unittest.main()
