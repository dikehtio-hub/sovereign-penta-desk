"""
Unit tests for LiquidationEngine and MarketIntelligence.
"""
import unittest
from analytics.liquidation_engine import LiquidationEngine
from analytics.market_intelligence import MarketIntelligence

class TestAnalytics(unittest.TestCase):
    def test_calculate_liquidation_clusters(self):
        coin = "xyz:TSLA"
        mark_px = 350.0
        open_interest = 1000.0  # 1000 contracts = $350k OI
        max_leverage = 20

        clusters = LiquidationEngine.calculate_liquidation_clusters(
            coin=coin,
            mark_px=mark_px,
            open_interest=open_interest,
            max_leverage=max_leverage,
            leverage_tiers=[10, 20]
        )

        self.assertTrue(len(clusters) > 0)
        long_clusters = [c for c in clusters if c["side"] == "LONG_LIQ"]
        short_clusters = [c for c in clusters if c["side"] == "SHORT_LIQ"]

        self.assertEqual(len(long_clusters), 2)
        self.assertEqual(len(short_clusters), 2)

        # Long liquidation price must be below mark price
        for lc in long_clusters:
            self.assertLess(lc["estimated_px"], mark_px)
            self.assertGreater(lc["distance_pct"], 0)

        # Short liquidation price must be above mark price
        for sc in short_clusters:
            self.assertGreater(sc["estimated_px"], mark_px)
            self.assertGreater(sc["distance_pct"], 0)

    def test_market_intelligence_summary(self):
        snapshots = [
            {"coin": "xyz:TSLA", "mark_px": 350.0, "notional_oi": 500000.0, "day_ntl_vlm": 200000.0, "funding_rate": 0.0001},
            {"coin": "xyz:GOLD", "mark_px": 4450.0, "notional_oi": 1000000.0, "day_ntl_vlm": 800000.0, "funding_rate": 0.00005},
            {"coin": "BTC", "mark_px": 100000.0, "notional_oi": 2000000.0, "day_ntl_vlm": 1500000.0, "funding_rate": 0.0002}
        ]

        summary = MarketIntelligence.summarize_tradfi_metrics(snapshots)
        self.assertEqual(summary["total_oi"], 3500000.0)
        self.assertEqual(summary["total_volume_24h"], 2500000.0)
        self.assertEqual(summary["category_oi"]["STOCKS"], 500000.0)
        self.assertEqual(summary["category_oi"]["COMMODITIES"], 1000000.0)
        self.assertEqual(summary["category_oi"]["CRYPTO"], 2000000.0)

if __name__ == "__main__":
    unittest.main()
