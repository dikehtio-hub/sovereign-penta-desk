"""
Tests for the delta-neutral basis harvester - the engine that replaced the fade.

The fade died because nobody measured its entry signal before building five rounds
of machinery on top of it. The lesson applied here is that the harvester's honesty
mechanisms are what get pinned hardest: it must accrue the CURRENT rate rather than
the entry rate, accrue NOTHING when a rate is missing, refuse uncosted rows, and
reconcile cash exactly once flat.

Fully offline - no network, no database, temp paths for state.
"""

import json
import tempfile
import unittest
from pathlib import Path

from execution.basis_harvester import BasisHarvester, HOURS_PER_YEAR
from config.settings import (
    BASIS_MAX_CONCURRENT, BASIS_MIN_HOLD_DAYS, MAKER_FEE_PCT, TAKER_FEE_PCT,
)


def opp(coin="MON", apr=56.0, spread=0.4, mark=10.0, hold=7.0, spot="MON"):
    return {"coin": coin, "spot_symbol": spot, "mark_px": mark, "funding_apr": apr,
            "net_apr": apr, "spread_bps": spread, "holding_days": hold,
            "is_spot_backed": True}


class HarvesterCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self._tmp.name) / "basis.json")
        self.h = BasisHarvester(starting_cash=100_000.0, state_path=self.path)

    def tearDown(self):
        self._tmp.cleanup()


class TestOpening(HarvesterCase):
    def test_a_qualifying_opportunity_opens_a_one_to_one_position(self):
        p = self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.assertEqual(p["structure"], "LONG_SPOT_SHORT_PERP")
        self.assertEqual(p["size"] * p["entry_mark"], p["notional_per_leg"])

    def test_both_legs_tie_up_capital(self):
        """The APR is quoted against ONE leg; reporting it as the return on the
        position would overstate it 2x."""
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.assertEqual(self.h.summary()["deployed_capital"], 20_000.0)

    def test_entry_fees_are_charged_on_both_legs_immediately(self):
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.assertAlmostEqual(self.h.fees_paid, TAKER_FEE_PCT * 10_000.0 * 2, places=9)
        self.assertAlmostEqual(self.h.cash, 100_000.0 - 20_000.0 - self.h.fees_paid, places=9)

    def test_an_uncosted_row_is_refused(self):
        """
        The trap that already caught this codebase once: net_apr_after_spread
        returns GROSS when no book was fetched, so an uncosted row would clear a
        net bar it was never measured against.
        """
        self.assertIsNone(self.h.open_position({**opp(), "spread_bps": None}))

    def test_negative_funding_is_refused(self):
        """Reversing the trade needs to short spot, and Hyperliquid has no borrow."""
        self.assertIsNone(self.h.open_position(opp(apr=-40.0)))

    def test_a_short_holding_period_is_refused(self):
        self.assertIsNone(self.h.open_position(opp(hold=BASIS_MIN_HOLD_DAYS - 1)))

    def test_the_same_coin_is_never_doubled_up(self):
        self.assertIsNotNone(self.h.open_position(opp()))
        self.assertIsNone(self.h.open_position(opp()))

    def test_concurrency_is_capped(self):
        from config.dynamic_config import get_dynamic_config
        expected_cap = get_dynamic_config().max_concurrent_positions or BASIS_MAX_CONCURRENT
        for i in range(expected_cap + 3):
            self.h.open_position(opp(coin=f"C{i}", spot=f"C{i}"), notional_per_leg=1_000.0)
        self.assertEqual(len(self.h.positions), expected_cap)

    def test_a_spread_over_the_ceiling_is_refused_with_the_reason(self):
        """
        Round 38. para:AVGO opened at 35.05 bps against a 25 bps ceiling: the scan
        probes only the head of its list and the net bar alone let it through.
        The harvester is the last gate before capital moves, so it checks too.
        """
        wide = opp(coin="para:AVGO", spot="AVGO", apr=77.9, spread=35.046)
        self.assertIsNone(self.h.open_position(wide, notional_per_leg=10_000.0, max_spread_bps=25.0))
        self.assertEqual(self.h.last_refusal, "spread 35.0bps > 25.0bps max")
        self.assertEqual(self.h.positions, {})
        # At the ceiling is inside it, and the refusal clears on success.
        at_ceiling = opp(coin="para:AVGO", spot="AVGO", spread=25.0)
        self.assertIsNotNone(self.h.open_position(at_ceiling, notional_per_leg=10_000.0, max_spread_bps=25.0))
        self.assertIsNone(self.h.last_refusal)

    def test_the_ceiling_defaults_to_the_hot_reloaded_config(self):
        from config.dynamic_config import get_dynamic_config
        ceiling = get_dynamic_config().max_spread_bps
        self.assertIsNone(self.h.open_position(opp(spread=ceiling + 1.0), notional_per_leg=10_000.0))
        self.assertIn("bps max", self.h.last_refusal)

    def test_one_position_per_spot_symbol(self):
        """
        Round 38. para:AVGO and xyz:AVGO were both opened against spot AVGO - two
        positions by coin, one concentration by risk: the same asset held twice,
        and both perps' funding moving with the same flow.
        """
        self.assertIsNotNone(self.h.open_position(opp(coin="para:AVGO", spot="AVGO"), notional_per_leg=10_000.0))
        self.assertIsNone(self.h.open_position(opp(coin="xyz:AVGO", spot="AVGO"), notional_per_leg=10_000.0))
        self.assertEqual(self.h.last_refusal, "spot AVGO already hedges para:AVGO")
        self.assertFalse(self.h.can_open("xyz:AVGO", 10_000.0, spot_symbol="AVGO"))
        self.assertTrue(self.h.can_open("xyz:AVGO", 10_000.0, spot_symbol="UAVGO"))
        self.assertTrue(self.h.can_open("xyz:AVGO", 10_000.0))            # no symbol given: nothing to compare
        self.assertEqual(self.h.holds_spot("AVGO"), "para:AVGO")
        self.assertIsNone(self.h.holds_spot(None))
        # Closing the first frees the underlying.
        self.h.close_position("para:AVGO")
        self.assertIsNotNone(self.h.open_position(opp(coin="xyz:AVGO", spot="AVGO"), notional_per_leg=10_000.0))

    def test_the_report_shows_the_cap_in_force_not_the_code_default(self):
        from execution.basis_harvester import format_report
        self.assertIn(f"Open 0/{self.h.effective_max_positions()}", format_report(self.h))

        class Seven:
            max_concurrent_positions = 7

        class Unset:
            max_concurrent_positions = 0

        self.assertEqual(BasisHarvester.effective_max_positions(Seven()), 7)
        self.assertEqual(BasisHarvester.effective_max_positions(Unset()), BASIS_MAX_CONCURRENT)

    def test_a_position_larger_than_cash_is_refused(self):
        self.assertIsNone(self.h.open_position(opp(), notional_per_leg=80_000.0))

    def test_a_zero_mark_is_refused_rather_than_dividing(self):
        self.assertIsNone(self.h.open_position(opp(mark=0.0)))


class TestAccrual(HarvesterCase):
    def setUp(self):
        super().setUp()
        self.h.open_position(opp(), notional_per_leg=10_000.0)

    def test_funding_accrues_on_the_perp_notional(self):
        credited = self.h.accrue({"MON": 0.0001}, hours=1.0)
        self.assertAlmostEqual(credited["MON"], 1.0, places=9)   # 10k * 1bp
        self.assertAlmostEqual(self.h.funding_collected, 1.0, places=9)

    def test_the_current_rate_is_used_not_the_entry_rate(self):
        """
        The single most important property. Entry APR was 56%; if the rate
        collapses to a tenth of that, the book must show the tenth. A harvester
        that projected its entry rate forward would report a fantasy.
        """
        entry_apr = self.h.positions["MON"]["entry_funding_apr"]
        self.h.accrue({"MON": 0.000001}, hours=1.0)
        realised = (self.h.positions["MON"]["funding_accrued"] / 10_000.0
                    * HOURS_PER_YEAR * 100.0)
        self.assertLess(realised, entry_apr / 10.0)

    def test_a_missing_rate_accrues_nothing(self):
        """A stale rate carried forward would manufacture yield during an outage."""
        self.assertEqual(self.h.accrue({}, hours=1.0), {})
        self.assertEqual(self.h.positions["MON"]["funding_accrued"], 0.0)
        self.assertEqual(self.h.positions["MON"]["hours_held"], 0.0)

    def test_negative_funding_is_a_real_cost_not_a_floor_at_zero(self):
        self.h.accrue({"MON": -0.0001}, hours=1.0)
        self.assertLess(self.h.funding_collected, 0)
        self.assertLess(self.h.cash, 100_000.0 - 20_000.0)

    def test_accrual_credits_cash_and_realised_pnl_together(self):
        """
        Both move by the same amount. Absolute realised PnL is already negative
        here by the entry fee, which is booked at open so the flat-state
        invariant (cash - starting == realised_pnl) holds at close.
        """
        cash_before, pnl_before = self.h.cash, self.h.realized_pnl
        self.h.accrue({"MON": 0.0001}, hours=1.0)
        self.assertAlmostEqual(self.h.cash - cash_before, 1.0, places=9)
        self.assertAlmostEqual(self.h.realized_pnl - pnl_before, 1.0, places=9)

    def test_hours_held_tracks_the_accrual_period(self):
        self.h.accrue({"MON": 0.0001}, hours=0.5)
        self.h.accrue({"MON": 0.0001}, hours=0.5)
        self.assertAlmostEqual(self.h.positions["MON"]["hours_held"], 1.0, places=9)

    def test_only_open_positions_accrue(self):
        self.h.accrue({"MON": 0.0001, "GHOST": 0.9}, hours=1.0)
        self.assertAlmostEqual(self.h.funding_collected, 1.0, places=9)


class TestClosing(HarvesterCase):
    def test_cash_reconciles_with_realised_pnl_once_flat(self):
        """The invariant that makes the book trustworthy at all."""
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.h.accrue({"MON": 0.0001}, hours=10.0)
        self.h.close_position("MON")
        self.assertEqual(self.h.positions, {})
        self.assertAlmostEqual(self.h.cash - 100_000.0, self.h.realized_pnl, places=9)

    def test_exit_fees_are_charged_on_both_legs(self):
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        before = self.h.fees_paid
        self.h.close_position("MON")
        self.assertAlmostEqual(self.h.fees_paid - before,
                               MAKER_FEE_PCT * 10_000.0 * 2, places=9)

    def test_realised_apr_reflects_what_was_actually_paid(self):
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.h.accrue({"MON": 0.0001}, hours=24.0)   # 1bp/h -> ~87.6% APR
        closed = self.h.close_position("MON")
        self.assertAlmostEqual(closed["realised_apr"], 0.0001 * HOURS_PER_YEAR * 100.0,
                               places=6)

    def test_net_pnl_is_funding_minus_both_fee_legs(self):
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.h.accrue({"MON": 0.0001}, hours=10.0)
        c = self.h.close_position("MON")
        self.assertAlmostEqual(c["net_pnl"],
                               c["funding_accrued"] - c["entry_fee"] - c["exit_fee"],
                               places=9)

    def test_a_position_never_opened_closes_to_none(self):
        self.assertIsNone(self.h.close_position("NOPE"))

    def test_capital_returns_to_cash_on_close(self):
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.h.close_position("MON")
        self.assertEqual(self.h.summary()["deployed_capital"], 0.0)

    def test_a_position_closed_before_any_accrual_has_no_realised_apr(self):
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.assertIsNone(self.h.close_position("MON")["realised_apr"])


class TestPersistence(HarvesterCase):
    def test_state_round_trips(self):
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.h.accrue({"MON": 0.0001}, hours=5.0)
        self.h.save()

        h2 = BasisHarvester(state_path=self.path)
        self.assertTrue(h2.load())
        self.assertAlmostEqual(h2.cash, self.h.cash, places=9)
        self.assertAlmostEqual(h2.funding_collected, self.h.funding_collected, places=9)
        self.assertIn("MON", h2.positions)
        self.assertAlmostEqual(h2.positions["MON"]["hours_held"], 5.0, places=9)

    def test_loading_a_missing_file_is_false_not_an_error(self):
        self.assertFalse(BasisHarvester(state_path=self.path + ".nope").load())

    def test_a_corrupt_file_does_not_crash_the_engine(self):
        Path(self.path).write_text("{not json", encoding="utf-8")
        self.assertFalse(BasisHarvester(state_path=self.path).load())

    def test_the_save_is_atomic(self):
        """A crash mid-write must not leave a truncated book."""
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        self.h.save()
        self.assertFalse(Path(self.path).with_suffix(".tmp").exists())
        json.loads(Path(self.path).read_text(encoding="utf-8"))


class TestSummary(HarvesterCase):
    def test_equity_counts_deployed_capital_as_still_ours(self):
        self.h.open_position(opp(), notional_per_leg=10_000.0)
        s = self.h.summary()
        self.assertAlmostEqual(s["equity"], s["cash"] + s["deployed_capital"], places=9)
        self.assertAlmostEqual(s["equity"], 100_000.0 - self.h.fees_paid, places=9)

    def test_an_empty_book_summarises_cleanly(self):
        s = self.h.summary()
        self.assertEqual((s["open_positions"], s["closed_positions"]), (0, 0))
        self.assertEqual(s["equity"], 100_000.0)


if __name__ == "__main__":
    unittest.main()
