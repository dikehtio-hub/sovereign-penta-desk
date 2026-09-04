"""
Unit tests for PaperTrader and LiquidationFadeStrategy.
"""
import unittest
from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy

class TestExecution(unittest.TestCase):
    def setUp(self):
        self.trader = PaperTrader(initial_balance_usd=50_000.0)

    def test_place_market_order_and_pnl(self):
        # Buy 1 BTC at $80,000 with 10x leverage
        res = self.trader.place_market_order(
            coin="BTC",
            side="BUY",
            size=1.0,
            current_price=80_000.0,
            leverage=10
        )
        self.assertEqual(res["status"], "FILLED")
        self.assertIn("BTC", self.trader.positions)
        self.assertEqual(self.trader.positions["BTC"]["size"], 1.0)

        # Mark price moves up to $82,000 (+$2,000 unrealized profit)
        summary = self.trader.get_account_summary({"BTC": 82_000.0})
        self.assertEqual(summary["total_unrealized_pnl"], 2_000.0)
        self.assertEqual(summary["equity"], 52_000.0)

        # Close position by selling 1.0 BTC at $82,000
        self.trader.place_market_order(
            coin="BTC",
            side="SELL",
            size=1.0,
            current_price=82_000.0
        )
        self.assertNotIn("BTC", self.trader.positions)
        self.assertEqual(self.trader.cash_balance, 52_000.0)

    def test_liquidation_fade_strategy(self):
        """
        Fades now rest as limit orders by default, so the position appears only
        once price trades through the limit - the strategy is paid to take the
        other side of a cascade rather than crossing the spread into it.
        """
        strat = LiquidationFadeStrategy(
            paper_trader=self.trader,
            fade_threshold_usd=25_000.0,
            position_size_usd=10_000.0,
            regime_enabled=False,
        )

        # Massive forced liquidation sell ($50,000 notional) on TSLA
        event = {
            "coin": "xyz:TSLA",
            "side": "A",
            "notional": 50_000.0,
            "notional_oi": 500_000_000.0,   # deep book -> judged on the major scale
        }
        order = strat.on_liquidation_event(event, mark_price=350.0)
        self.assertIsNotNone(order)
        self.assertEqual(order["side"], "BUY")
        self.assertEqual(order["status"], "OPEN")
        self.assertLess(order["limit_price"], 350.0)
        self.assertNotIn("xyz:TSLA", self.trader.positions)

        # It fills once the cascade overshoots through the resting limit.
        filled = self.trader.check_open_orders({"xyz:TSLA": order["limit_price"] - 0.5})
        self.assertEqual(len(filled), 1)
        self.assertIn("xyz:TSLA", self.trader.positions)

    def test_liquidation_fade_market_order_mode(self):
        """The immediate-fill path remains available for callers that want it."""
        strat = LiquidationFadeStrategy(
            paper_trader=self.trader,
            fade_threshold_usd=25_000.0,
            position_size_usd=10_000.0,
            regime_enabled=False,
            use_limit_orders=False,
        )
        order = strat.on_liquidation_event(
            {"coin": "xyz:TSLA", "side": "A", "notional": 50_000.0,
             "notional_oi": 500_000_000.0},
            mark_price=350.0,
        )
        self.assertEqual(order["status"], "FILLED")
        self.assertIn("xyz:TSLA", self.trader.positions)

if __name__ == "__main__":
    unittest.main()
