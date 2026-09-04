"""
Round 14 tests: the maker/taker fee model and the pre-registered 50-trade hurdle.

The hurdle was agreed 2026-08-31 BEFORE any trade closed. These tests make the
thresholds tamper-evident: if a later edit relaxes one to make a disappointing
result look acceptable, they fail loudly rather than letting it pass quietly.

Fully offline.
"""

import tempfile
import unittest
from pathlib import Path

from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy
from config.settings import (
    HURDLE_MIN_TRADES,
    HURDLE_PASS_PROFIT_FACTOR,
    HURDLE_PASS_WIN_RATE,
    HURDLE_RETUNE_WIN_RATE,
    MAKER_FEE_PCT,
    TAKER_FEE_PCT,
)


def faded(exit_key=None, notional=5_000.0, mark=10.0):
    """Open a fade, fill it, and optionally exit at one of its levels."""
    t = PaperTrader(100_000.0)
    s = LiquidationFadeStrategy(t, regime_enabled=False)
    o = s.on_liquidation_sweep({"coin": "SKR", "side": "A", "notional": notional},
                               mark, notional_oi=1e6)
    t.check_open_orders({"SKR": o["limit_price"]})
    if exit_key:
        s.check_open_positions({"SKR": o[exit_key]})
    return t, s, o


# --------------------------------------------------------------------------
# Fee schedule
# --------------------------------------------------------------------------

class TestFeeSchedule(unittest.TestCase):
    def test_configured_rates(self):
        self.assertEqual(MAKER_FEE_PCT, 0.00010)   # 1.0 bps
        self.assertEqual(TAKER_FEE_PCT, 0.00035)   # 3.5 bps

    def test_taker_costs_more_than_maker(self):
        self.assertGreater(TAKER_FEE_PCT, MAKER_FEE_PCT)


class TestEntryFee(unittest.TestCase):
    def test_limit_fill_charges_the_maker_rate(self):
        t, _, o = faded()
        notional = o["size"] * o["limit_price"]
        self.assertAlmostEqual(t.fees_paid, notional * MAKER_FEE_PCT, places=9)

    def test_entry_fee_leaves_cash_short_before_any_exit(self):
        t, _, _ = faded()
        self.assertLess(t.cash_balance, 100_000.0)
        self.assertEqual(t.realized_pnl, 0.0)   # nothing closed yet

    def test_entry_fee_is_recorded_on_the_position(self):
        t, _, _ = faded()
        self.assertGreater(t.positions["SKR"]["entry_fee"], 0.0)

    def test_unfilled_order_pays_nothing(self):
        t = PaperTrader(100_000.0)
        s = LiquidationFadeStrategy(t, regime_enabled=False)
        s.on_liquidation_sweep({"coin": "SKR", "side": "A", "notional": 5_000.0},
                               10.0, notional_oi=1e6)
        self.assertEqual(t.fees_paid, 0.0)
        self.assertEqual(t.cash_balance, 100_000.0)


class TestExitFees(unittest.TestCase):
    def test_take_profit_exit_pays_maker(self):
        """A take-profit rests as a limit, so it earns the maker rate."""
        t, _, o = faded("take_profit")
        notional_in = o["size"] * o["limit_price"]
        notional_out = o["size"] * o["take_profit"]
        expected = notional_in * MAKER_FEE_PCT + notional_out * MAKER_FEE_PCT
        self.assertAlmostEqual(t.fees_paid, expected, places=9)

    def test_stop_loss_exit_pays_taker(self):
        """A stop has to cross the book to get out."""
        t, _, o = faded("stop_loss")
        notional_in = o["size"] * o["limit_price"]
        notional_out = o["size"] * o["stop_loss"]
        expected = notional_in * MAKER_FEE_PCT + notional_out * TAKER_FEE_PCT
        self.assertAlmostEqual(t.fees_paid, expected, places=9)

    def test_time_stop_exit_pays_taker(self):
        t, s, o = faded()
        t.positions["SKR"]["opened_at"] -= 99_999
        s.check_open_positions({"SKR": 10.0})
        notional_in = o["size"] * o["limit_price"]
        expected_entry = notional_in * MAKER_FEE_PCT
        self.assertGreater(t.fees_paid - expected_entry, 0.0)
        # Taker on the way out, so total exceeds two maker legs.
        self.assertGreater(t.fees_paid, expected_entry * 2)

    def test_losing_exit_costs_more_in_fees_than_a_winning_one(self):
        win, _, _ = faded("take_profit")
        loss, _, _ = faded("stop_loss")
        self.assertGreater(loss.fees_paid, win.fees_paid)


class TestFeeAccountingIntegrity(unittest.TestCase):
    def test_cash_reconciles_with_realised_pnl_when_flat(self):
        """
        The invariant that makes the account trustworthy: once flat,
        cash - initial must equal realised PnL exactly. If fees were charged in
        one place and not attributed in the other, this drifts.
        """
        for key in ("take_profit", "stop_loss"):
            t, _, _ = faded(key)
            self.assertAlmostEqual(t.cash_balance - 100_000.0, t.realized_pnl, places=9)

    def test_realised_pnl_is_net_and_gross_is_recoverable(self):
        t, _, _ = faded("take_profit")
        summary = t.get_account_summary()
        self.assertAlmostEqual(summary["gross_pnl"], t.realized_pnl + t.fees_paid, places=9)
        self.assertLess(summary["realized_pnl"], summary["gross_pnl"])

    def test_fees_make_the_one_to_one_geometry_slightly_negative(self):
        """
        Worth pinning: the levels are symmetric, but the fees are not. A loss
        exits taker and a win exits maker, so break-even needs a win rate above
        50% - which is why the hurdle is set at 54%, not 50%.
        """
        win, _, _ = faded("take_profit")
        loss, _, _ = faded("stop_loss")
        self.assertLess(win.realized_pnl, abs(loss.realized_pnl))

    def test_win_and_loss_counters_track_net_not_gross(self):
        win, _, _ = faded("take_profit")
        loss, _, _ = faded("stop_loss")
        self.assertEqual((win.wins, win.losses), (1, 0))
        self.assertEqual((loss.wins, loss.losses), (0, 1))


# --------------------------------------------------------------------------
# Pre-registered hurdle
# --------------------------------------------------------------------------

class TestHurdleThresholds(unittest.TestCase):
    """Tamper-evidence for the agreed numbers."""

    def test_configured_thresholds(self):
        self.assertEqual(HURDLE_MIN_TRADES, 50)
        self.assertEqual(HURDLE_PASS_WIN_RATE, 54.0)
        self.assertEqual(HURDLE_PASS_PROFIT_FACTOR, 1.25)
        self.assertEqual(HURDLE_RETUNE_WIN_RATE, 48.0)

    def test_bands_do_not_overlap(self):
        self.assertGreater(HURDLE_PASS_WIN_RATE, HURDLE_RETUNE_WIN_RATE)


class TestHurdleVerdict(unittest.TestCase):
    @staticmethod
    def account(wins, losses, gross_profit=100.0, gross_loss=50.0):
        t = PaperTrader(100_000.0)
        t.wins, t.losses = wins, losses
        t.gross_profit, t.gross_loss = gross_profit, gross_loss
        return t

    def test_below_the_trade_floor_is_pending(self):
        v = self.account(30, 10).hurdle_verdict()
        self.assertEqual(v["verdict"], "PENDING")
        self.assertEqual(v["trades_required"], 50)

    def test_pass_requires_both_win_rate_and_profit_factor(self):
        v = self.account(30, 20, gross_profit=200.0, gross_loss=100.0).hurdle_verdict()
        self.assertEqual(v["verdict"], "PASS")   # 60% win rate, PF 2.0

    def test_high_win_rate_with_poor_payoff_is_inconclusive_not_pass(self):
        """
        Not covered by the matrix, and resolved explicitly rather than silently:
        many small wins against a few large losses is not the edge we specified.
        """
        v = self.account(30, 20, gross_profit=100.0, gross_loss=99.0).hurdle_verdict()
        self.assertEqual(v["verdict"], "INCONCLUSIVE")

    def test_retune_band(self):
        self.assertEqual(self.account(25, 25).hurdle_verdict()["verdict"], "RETUNE")   # 50%
        self.assertEqual(self.account(24, 26).hurdle_verdict()["verdict"], "RETUNE")   # 48%

    def test_fail_band(self):
        self.assertEqual(self.account(23, 27).hurdle_verdict()["verdict"], "FAIL")     # 46%

    def test_boundaries_are_inclusive(self):
        at_pass = self.account(54, 46, gross_profit=200.0, gross_loss=100.0)
        self.assertEqual(at_pass.hurdle_verdict()["verdict"], "PASS")
        at_retune = self.account(48, 52)
        self.assertEqual(at_retune.hurdle_verdict()["verdict"], "RETUNE")

    def test_profit_factor_is_none_before_any_loss(self):
        """Reporting infinity off two winning trades would read as a triumph."""
        t = self.account(3, 0, gross_profit=30.0, gross_loss=0.0)
        self.assertIsNone(t.profit_factor())

    def test_win_rate_of_an_empty_account(self):
        self.assertEqual(PaperTrader(100_000.0).win_rate_pct(), 0.0)

    def test_every_verdict_is_reachable(self):
        outcomes = {
            self.account(30, 20, 200.0, 100.0).hurdle_verdict()["verdict"],
            self.account(30, 20, 100.0, 99.0).hurdle_verdict()["verdict"],
            self.account(25, 25).hurdle_verdict()["verdict"],
            self.account(23, 27).hurdle_verdict()["verdict"],
            self.account(3, 1).hurdle_verdict()["verdict"],
        }
        self.assertEqual(outcomes, {"PASS", "INCONCLUSIVE", "RETUNE", "FAIL", "PENDING"})


class TestFeePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "paper.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_fee_and_performance_state_round_trips(self):
        t, _, _ = faded("take_profit")
        t.save(self.path)
        r = PaperTrader.load(self.path)
        self.assertAlmostEqual(r.fees_paid, t.fees_paid, places=9)
        self.assertEqual((r.wins, r.losses), (t.wins, t.losses))
        self.assertAlmostEqual(r.gross_profit, t.gross_profit, places=9)
        self.assertAlmostEqual(r.gross_loss, t.gross_loss, places=9)

    def test_profit_factor_survives_a_round_trip(self):
        t = PaperTrader(100_000.0)
        t.wins, t.losses = 6, 4
        t.gross_profit, t.gross_loss = 120.0, 60.0
        t.save(self.path)
        self.assertAlmostEqual(PaperTrader.load(self.path).profit_factor(), 2.0, places=9)

    def test_derived_ratios_are_not_persisted(self):
        """
        Only raw totals are stored; the ratios are recomputed. A stored copy could
        only go stale against the counters it was derived from.
        """
        import json
        t, _, _ = faded("take_profit")
        t.save(self.path)
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertNotIn("profit_factor", stored)
        self.assertNotIn("win_rate_pct", stored)
        self.assertNotIn("hurdle", stored)
        self.assertIn("gross_profit", stored)

    def test_summary_exposes_fees_for_the_dashboard(self):
        t, _, _ = faded("take_profit")
        s = t.get_account_summary()
        for key in ("fees_paid", "gross_pnl", "wins", "losses",
                    "win_rate_pct", "profit_factor", "hurdle"):
            self.assertIn(key, s)


if __name__ == "__main__":
    unittest.main()
