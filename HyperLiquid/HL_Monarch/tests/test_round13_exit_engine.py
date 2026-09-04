"""
Round 13 tests: the position exit engine.

Until this existed, stop_loss and take_profit were merely STORED on a filled
position and nothing ever acted on them - a fade sat open indefinitely and the
reported PnL measured entries only. These tests pin the semantics that make the
paper account an actual measure of the strategy.

Fully offline.
"""

import unittest

from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy
from config.settings import (
    FADE_LIMIT_OFFSET_PCT,
    FADE_POSITION_MAX_HOLD_SECONDS,
    FADE_STOP_LOSS_PCT,
    FADE_TAKE_PROFIT_PCT,
)


class ExitFixture(unittest.TestCase):
    """A filled fade on SKR, long from a forced-sell cascade at a $10.00 mark."""

    def setUp(self):
        self.t = PaperTrader(100_000.0)
        self.s = LiquidationFadeStrategy(self.t, regime_enabled=False)
        self.order = self.s.on_liquidation_sweep(
            {"coin": "SKR", "side": "A", "notional": 5_000.0}, 10.0, notional_oi=1e6
        )
        self.t.check_open_orders({"SKR": self.order["limit_price"]})
        self.assertIn("SKR", self.t.positions)

    def short_fixture(self):
        t = PaperTrader(100_000.0)
        s = LiquidationFadeStrategy(t, regime_enabled=False)
        o = s.on_liquidation_sweep(
            {"coin": "XMR", "side": "B", "notional": 5_000.0}, 100.0, notional_oi=1e6
        )
        t.check_open_orders({"XMR": o["limit_price"]})
        return t, s, o


class TestGeometry(unittest.TestCase):
    def test_configured_values(self):
        self.assertEqual(FADE_LIMIT_OFFSET_PCT, 0.5)
        self.assertEqual(FADE_STOP_LOSS_PCT, 0.65)
        self.assertEqual(FADE_TAKE_PROFIT_PCT, 0.65)
        # 600 -> 1800 in Round 15: at 600s a 1.0x ATR target was reached in
        # under 50% of cases in 35/35 markets (median time-to-target 1,224s),
        # so most exits resolved TIME_STOP at the mid instead of TP/SL.
        self.assertEqual(FADE_POSITION_MAX_HOLD_SECONDS, 1800.0)

    def test_symmetric_legs_break_even_at_fifty_percent(self):
        t = PaperTrader(100_000.0)
        s = LiquidationFadeStrategy(t, regime_enabled=False)
        r = s.on_liquidation_sweep({"coin": "SKR", "side": "A", "notional": 5_000.0},
                                   10.0, notional_oi=1e6)
        lim = r["limit_price"]
        self.assertAlmostEqual(r["take_profit"] - lim, lim - r["stop_loss"], places=9)


class TestLongExits(ExitFixture):
    def test_take_profit_closes_the_position_for_a_gain(self):
        closed = self.s.check_open_positions({"SKR": self.order["take_profit"]})
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["exit_reason"], "TAKE_PROFIT")
        self.assertNotIn("SKR", self.t.positions)
        self.assertGreater(self.t.realized_pnl, 0)
        self.assertEqual(self.t.closed_trades, 1)

    def test_stop_loss_closes_the_position_for_a_loss(self):
        closed = self.s.check_open_positions({"SKR": self.order["stop_loss"]})
        self.assertEqual(closed[0]["exit_reason"], "STOP_LOSS")
        self.assertLess(self.t.realized_pnl, 0)

    def test_win_and_loss_are_symmetric_gross_but_not_net(self):
        """
        The 1:1 geometry is symmetric in GROSS terms. Net, it is not: a win exits
        maker and a loss exits taker, so the loss costs 2.5bps more. That is why
        the pre-registered hurdle demands 54% rather than 50%.
        """
        self.s.check_open_positions({"SKR": self.order["take_profit"]})
        win_net, win_fees = self.t.realized_pnl, self.t.fees_paid

        t2 = PaperTrader(100_000.0)
        s2 = LiquidationFadeStrategy(t2, regime_enabled=False)
        o2 = s2.on_liquidation_sweep({"coin": "SKR", "side": "A", "notional": 5_000.0},
                                     10.0, notional_oi=1e6)
        t2.check_open_orders({"SKR": o2["limit_price"]})
        s2.check_open_positions({"SKR": o2["stop_loss"]})
        loss_net, loss_fees = t2.realized_pnl, t2.fees_paid

        self.assertAlmostEqual(win_net + win_fees, -(loss_net + loss_fees), places=4)
        self.assertLess(win_net, abs(loss_net))
        self.assertGreater(loss_fees, win_fees)

    def test_price_between_the_levels_leaves_it_open(self):
        self.assertEqual(self.s.check_open_positions({"SKR": self.order["limit_price"]}), [])
        self.assertIn("SKR", self.t.positions)

    def test_price_beyond_the_stop_still_exits_at_the_stop(self):
        """A gap through the level must not book a worse fill than the stop."""
        self.s.check_open_positions({"SKR": self.order["stop_loss"] * 0.5})
        exit_fill = self.t.trade_history[-1]
        self.assertAlmostEqual(exit_fill["price"], self.order["stop_loss"], places=9)


class TestShortExits(ExitFixture):
    def test_short_take_profit_is_below_entry(self):
        t, s, o = self.short_fixture()
        closed = s.check_open_positions({"XMR": o["take_profit"]})
        self.assertEqual(closed[0]["exit_reason"], "TAKE_PROFIT")
        self.assertGreater(t.realized_pnl, 0)

    def test_short_stop_loss_is_above_entry(self):
        t, s, o = self.short_fixture()
        closed = s.check_open_positions({"XMR": o["stop_loss"]})
        self.assertEqual(closed[0]["exit_reason"], "STOP_LOSS")
        self.assertLess(t.realized_pnl, 0)

    def test_short_between_levels_stays_open(self):
        t, s, o = self.short_fixture()
        self.assertEqual(s.check_open_positions({"XMR": o["limit_price"]}), [])


class TestAmbiguousTick(ExitFixture):
    def test_stop_wins_when_both_levels_are_hit(self):
        """
        A single tick cannot tell us which level traded first, so we assume the
        loss. A paper account that resolves its own ambiguity favourably is
        worthless.
        """
        self.t.positions["SKR"]["stop_loss"] = self.order["take_profit"] + 1.0
        closed = self.s.check_open_positions({"SKR": self.order["take_profit"]})
        self.assertEqual(closed[0]["exit_reason"], "STOP_LOSS")


class TestTimeStop(ExitFixture):
    def test_position_older_than_max_hold_is_closed_at_the_mid(self):
        self.t.positions["SKR"]["opened_at"] -= FADE_POSITION_MAX_HOLD_SECONDS + 1
        closed = self.s.check_open_positions({"SKR": 9.97})
        self.assertEqual(closed[0]["exit_reason"], "TIME_STOP")
        self.assertAlmostEqual(closed[0]["price"], 9.97, places=9)

    def test_young_position_is_not_time_stopped(self):
        self.t.positions["SKR"]["opened_at"] -= FADE_POSITION_MAX_HOLD_SECONDS - 10
        self.assertEqual(self.s.check_open_positions({"SKR": 9.97}), [])

    def test_levels_take_precedence_over_the_time_stop(self):
        self.t.positions["SKR"]["opened_at"] -= FADE_POSITION_MAX_HOLD_SECONDS + 1
        closed = self.s.check_open_positions({"SKR": self.order["take_profit"]})
        self.assertEqual(closed[0]["exit_reason"], "TAKE_PROFIT")

    def test_time_stop_can_be_disabled(self):
        s = LiquidationFadeStrategy(self.t, max_hold_seconds=0, regime_enabled=False)
        self.t.positions["SKR"]["opened_at"] -= 99_999
        self.assertEqual(s.check_open_positions({"SKR": 9.97}), [])


class TestExitBookkeeping(ExitFixture):
    def test_exit_is_appended_to_trade_history(self):
        before = len(self.t.trade_history)
        self.s.check_open_positions({"SKR": self.order["take_profit"]})
        self.assertEqual(len(self.t.trade_history), before + 1)
        self.assertEqual(self.t.trade_history[-1]["side"], "SELL")

    def test_cash_reconciles_with_realised_pnl_once_flat(self):
        """
        Measured from the STARTING balance, not from after the entry: the entry
        fee is already out of cash by then, while realised PnL attributes both
        legs' fees at close. Only the full round trip reconciles.
        """
        self.s.check_open_positions({"SKR": self.order["take_profit"]})
        self.assertEqual(self.t.positions, {})
        self.assertAlmostEqual(self.t.cash_balance - 100_000.0, self.t.realized_pnl, places=9)

    def test_exit_reports_the_entry_price(self):
        closed = self.s.check_open_positions({"SKR": self.order["take_profit"]})
        self.assertAlmostEqual(closed[0]["entry_price"], self.order["limit_price"], places=9)

    def test_unpriced_coin_is_skipped_not_closed(self):
        self.assertEqual(self.s.check_open_positions({"OTHER": 1.0}), [])
        self.assertIn("SKR", self.t.positions)

    def test_zero_or_negative_mid_is_ignored(self):
        self.assertEqual(self.s.check_open_positions({"SKR": 0.0}), [])
        self.assertIn("SKR", self.t.positions)

    def test_no_positions_is_a_cheap_noop(self):
        t = PaperTrader(100_000.0)
        self.assertEqual(LiquidationFadeStrategy(t, regime_enabled=False).check_open_positions({"SKR": 10.0}), [])


class TestOnMidsTick(unittest.TestCase):
    def test_fills_then_manages_in_one_tick(self):
        """
        An order filling on a tick becomes a position the same tick can stop out -
        which is what a real market does during a fast cascade.
        """
        t = PaperTrader(100_000.0)
        s = LiquidationFadeStrategy(t, regime_enabled=False)
        o = s.on_liquidation_sweep({"coin": "SKR", "side": "A", "notional": 5_000.0},
                                   10.0, notional_oi=1e6)
        out = s.on_mids({"SKR": o["stop_loss"]})
        self.assertEqual(len(out["filled"]), 1)
        self.assertEqual(len(out["closed"]), 1)
        self.assertEqual(out["closed"][0]["exit_reason"], "STOP_LOSS")

    def test_quiet_tick_does_nothing(self):
        t = PaperTrader(100_000.0)
        out = LiquidationFadeStrategy(t, regime_enabled=False).on_mids({"SKR": 10.0})
        self.assertEqual(out["filled"], [])
        self.assertEqual(out["closed"], [])

    def test_round_trip_leaves_a_flat_book(self):
        t = PaperTrader(100_000.0)
        s = LiquidationFadeStrategy(t, regime_enabled=False)
        o = s.on_liquidation_sweep({"coin": "SKR", "side": "A", "notional": 5_000.0},
                                   10.0, notional_oi=1e6)
        s.on_mids({"SKR": o["limit_price"]})
        s.on_mids({"SKR": o["take_profit"]})
        self.assertEqual(t.positions, {})
        self.assertEqual(t.open_orders, [])
        self.assertEqual(t.closed_trades, 1)


class TestPrunedModulesAreGone(unittest.TestCase):
    """Post-pivot cut list: these must not come back by accident."""

    def test_retired_modules_are_deleted(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        for rel in ("analytics/cross_market_scanner.py",
                    "analytics/titan_pipeline.py",
                    "analytics/squeeze_validator.py"):
            self.assertFalse((root / rel).exists(), f"{rel} should have been deleted")

    def test_retired_subcommands_are_unregistered(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        self.assertNotIn('"titans"', src)
        self.assertNotIn('"validate"', src)

    def test_squeeze_is_retained_as_informational(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        self.assertIn('"squeeze"', src)


if __name__ == "__main__":
    unittest.main()


class TestRetiredStrategyWindsDown(unittest.TestCase):
    """
    Disabling PLACEMENT alone was not enough. `on_mids` still ran whenever orders
    existed, and `check_open_orders` would FILL resting limits - so the retired
    strategy could still take real directional positions from orders placed before
    it was switched off. Two live BTC/ETH limits were resting when this was found.
    """

    def setUp(self):
        self.t = PaperTrader(100_000.0)
        self.s = LiquidationFadeStrategy(self.t, regime_enabled=False)
        self.order = self.s.on_liquidation_sweep(
            {"coin": "SKR", "side": "A", "notional": 5_000.0}, 10.0, notional_oi=1e6)

    def test_resting_orders_are_cancelled_not_filled_when_retired(self):
        out = self.s.on_mids({"SKR": self.order["limit_price"]}, allow_fills=False)
        self.assertEqual(out["filled"], [])
        self.assertEqual(out["cancelled"], 1)
        self.assertEqual(self.t.open_orders, [])
        self.assertEqual(self.t.positions, {})

    def test_the_same_tick_would_have_filled_when_enabled(self):
        """Proves the guard is what prevents the fill, not the price."""
        out = self.s.on_mids({"SKR": self.order["limit_price"]}, allow_fills=True)
        self.assertEqual(len(out["filled"]), 1)

    def test_open_positions_are_still_managed_to_their_exits(self):
        """
        Freezing exits would strand real exposure with nothing watching it. A
        retired strategy must wind down, not stop mid-position.
        """
        self.t.check_open_orders({"SKR": self.order["limit_price"]})
        self.assertIn("SKR", self.t.positions)
        out = self.s.on_mids({"SKR": self.order["take_profit"]}, allow_fills=False)
        self.assertEqual(len(out["closed"]), 1)
        self.assertEqual(self.t.positions, {})

    def test_wind_down_reports_what_it_cancelled(self):
        self.assertEqual(self.s.wind_down(), 1)
        self.assertEqual(self.s.wind_down(), 0)

    def test_the_kill_switch_is_off(self):
        from config.settings import FADE_STRATEGY_ENABLED
        self.assertFalse(FADE_STRATEGY_ENABLED)
