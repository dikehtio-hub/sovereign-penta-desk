"""
===============================================================================
UNIT TEST TEMPLATE FOR CUSTOM STRATEGIES
===============================================================================
Location: DEV/strategies/test_template_strategy.py

DESCRIPTION OF THIS MODULE:
---------------------------
This test suite uses Python's built-in `unittest` framework to verify that the
strategy calculations, hurdle logic, and signal generation remain 100% accurate.

WHY UNIT TESTING IS CRITICAL FOR QUANT STRATEGIES:
1. PREVENT REGRESSIONS: Ensures future code edits don't break existing math.
2. VERIFY EDGE CASES: Checks zero prices, negative spreads, and threshold boundaries.
3. NO API COST / ZERO RISK: Runs in milliseconds without using live exchange connections.

HOW TO RUN THIS TEST SUITE:
---------------------------
Run the following command in your terminal:
    python -m unittest test_template_strategy.py
===============================================================================
"""

import unittest
from strategy_template import BaseStrategyTemplate


class TestBaseStrategyTemplate(unittest.TestCase):
    """
    Test Case Suite for BaseStrategyTemplate.
    Inherits from unittest.TestCase.
    """

    def setUp(self):
        """
        SETUP METHOD (Runs automatically before EACH test method):
        ---------------------------------------------------------
        Instantiates a fresh `BaseStrategyTemplate` instance with standard test parameters:
          - Minimum Spread Threshold: 0.80%
          - Minimum Profit Floor:     $6.00 USD
          - Protocol Fee Percentage:  0.60% (0.30% * 2 legs)
        """
        self.strategy = BaseStrategyTemplate(
            min_spread_pct=0.80,
            min_profit_usd=6.00,
            fee_pct=0.60
        )

    def test_profitable_spread_generates_buy_signal(self):
        """
        TEST CASE 1: Profitable Spread Scenario
        ---------------------------------------
        Inputs: Buy @ $3,000.00, Sell @ $3,036.00 with $2,950 Working Capital.
        Expected Math:
          - Gross Spread: ((3036 - 3000) / 3000) * 100 = 1.20%
          - Net Spread:   1.20% - 0.60% fees = 0.60%
          - Gross Profit: $2,950 * 1.20% = $35.40
          - Fee Cost:     $2,950 * 0.60% = $17.70
          - Net Profit:   $35.40 - $17.70 = +$17.70 USDC
        Assertions:
          - Action MUST be "BUY"
          - is_viable MUST be True
          - Net Profit MUST equal $17.70
        """
        result = self.strategy.generate_signal(
            symbol="WETH/USDC",
            buy_price=3000.0,
            sell_price=3036.0,
            capital_usd=2950.0
        )
        self.assertEqual(result["action"], "BUY")
        self.assertTrue(result["is_viable"])
        self.assertAlmostEqual(result["gross_spread_pct"], 1.20, places=2)
        self.assertAlmostEqual(result["net_profit_usd"], 17.70, places=2)

    def test_unprofitable_spread_generates_hold_signal(self):
        """
        TEST CASE 2: Unprofitable Spread Scenario (Below Fee Hurdle)
        ------------------------------------------------------------
        Inputs: Buy @ $3,000.00, Sell @ $3,009.00 with $2,950 Working Capital.
        Expected Math:
          - Gross Spread: 0.30%
          - Net Spread:   0.30% - 0.60% fees = -0.30% (Negative return!)
        Assertions:
          - Action MUST be "HOLD"
          - is_viable MUST be False
          - Net Profit MUST be negative (< 0)
        """
        result = self.strategy.generate_signal(
            symbol="WETH/USDC",
            buy_price=3000.0,
            sell_price=3009.0,
            capital_usd=2950.0
        )
        self.assertEqual(result["action"], "HOLD")
        self.assertFalse(result["is_viable"])
        self.assertLess(result["net_profit_usd"], 0)

    def test_invalid_prices_handling(self):
        """
        TEST CASE 3: Edge Case / Corrupted Price Input
        ----------------------------------------------
        Inputs: Buy Price = 0.0, Sell Price = $3,000.00.
        Assertions:
          - Action MUST safely default to "HOLD"
          - is_viable MUST be False
          - Should NOT crash or throw ZeroDivisionError
        """
        result = self.strategy.generate_signal(
            symbol="WETH/USDC",
            buy_price=0.0,
            sell_price=3000.0
        )
        self.assertEqual(result["action"], "HOLD")
        self.assertFalse(result["is_viable"])


# =============================================================================
# EXECUTABLE SCRIPT RUNNER
# =============================================================================
if __name__ == "__main__":
    unittest.main()
