"""
Unit tests for FundingArbitrageEngine.
"""
import unittest
from analytics.funding_arbitrage import FundingArbitrageEngine

class TestFundingArbitrage(unittest.TestCase):
    def setUp(self):
        self.engine = FundingArbitrageEngine()

    def test_scan_funding_opportunities(self):
        sample_snapshots = [
            {
                "coin": "xyz:NVDA",
                "dex": "xyz",
                "mark_px": 200.0,
                "notional_oi": 150_000_000.0,
                "day_ntl_vlm": 10_000_000.0,
                "funding_rate": 0.0005  # +0.05% per hour -> +43.8% APR
            },
            {
                "coin": "xyz:AAPL",
                "dex": "xyz",
                "mark_px": 300.0,
                "notional_oi": 80_000_000.0,
                "day_ntl_vlm": 5_000_000.0,
                "funding_rate": -0.0003  # -0.03% per hour -> -26.28% APR
            },
            {
                "coin": "xyz:LOW_OI",
                "dex": "xyz",
                "mark_px": 10.0,
                "notional_oi": 1_000.0,  # Below threshold
                "day_ntl_vlm": 100.0,
                "funding_rate": 0.0010
            }
        ]

        res = self.engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=sample_snapshots)
        self.assertIn("short_harvest", res)
        self.assertIn("long_harvest", res)

        # NVDA should be in short harvest (positive funding)
        self.assertEqual(len(res["short_harvest"]), 1)
        self.assertEqual(res["short_harvest"][0]["coin"], "xyz:NVDA")
        self.assertGreater(res["short_harvest"][0]["funding_apr"], 40.0)

        # AAPL should be in long harvest (negative funding)
        self.assertEqual(len(res["long_harvest"]), 1)
        self.assertEqual(res["long_harvest"][0]["coin"], "xyz:AAPL")
        self.assertLess(res["long_harvest"][0]["funding_apr"], -20.0)

if __name__ == "__main__":
    unittest.main()
