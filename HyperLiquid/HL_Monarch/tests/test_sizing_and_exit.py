"""
Tests for leg-size precision matching and the dynamic yield exit.

Both exist because a plausible-sounding fix would have made things worse:

  * Independent per-leg rounding (the obvious answer to a szDecimals mismatch)
    prevents the REJECTED leg but reintroduces the naked delta it was meant to
    remove. Matching to the coarser precision is what actually hedges.
  * A 12% APR exit floor sounds like good capital discipline, but measured on live
    funding history a short hold LOSES money: 6h nets -0.0612% after the 0.0900%
    round trip and is profitable only 16% of the time.

Fully offline.
"""

import tempfile
import unittest
from pathlib import Path

from execution.sizing import floor_to_decimals, matched_leg_size
from execution.basis_harvester import BasisHarvester
from config.settings import BASIS_EXIT_APR_FLOOR


class TestFlooring(unittest.TestCase):
    def test_it_rounds_down_never_up(self):
        self.assertEqual(floor_to_decimals(1.999, 0), 1.0)
        self.assertEqual(floor_to_decimals(1.9999, 2), 1.99)

    def test_zero_decimals_gives_whole_units(self):
        self.assertEqual(floor_to_decimals(2967.35, 0), 2967.0)

    def test_an_exact_value_is_unchanged(self):
        self.assertEqual(floor_to_decimals(5.25, 2), 5.25)

    def test_negative_decimals_is_rejected(self):
        with self.assertRaises(ValueError):
            floor_to_decimals(1.0, -1)


class TestMatchedLegSize(unittest.TestCase):
    def test_the_coarser_leg_governs_both(self):
        """
        MON is the live case: perp szDecimals=0, spot=2. Sizing to the spot's 2dp
        would hand the perp a fractional order it cannot accept.
        """
        r = matched_leg_size(10_000.0, 3.37, perp_decimals=0, spot_decimals=2)
        self.assertEqual(r["decimals"], 0)
        self.assertEqual(r["size"], 2967.0)
        self.assertTrue(r["tradeable"])

    def test_residual_delta_is_zero_by_construction(self):
        """
        The reason independent rounding was rejected. Flooring each leg to its own
        precision would leave 1000.56 spot against a 1000 perp - 0.56 units naked
        in a position whose entire premise is zero delta.
        """
        r = matched_leg_size(10_000.0, 3.37, perp_decimals=0, spot_decimals=2)
        self.assertEqual(r["residual"], 0.0)

    def test_deployed_notional_never_exceeds_the_request(self):
        r = matched_leg_size(10_000.0, 3.37, 0, 2)
        self.assertLessEqual(r["notional_usd"], 10_000.0)
        self.assertGreaterEqual(r["shortfall_usd"], 0.0)

    def test_one_known_precision_is_enough_and_is_used(self):
        """Alt-dex perps sometimes report no szDecimals; size off the known leg."""
        r = matched_leg_size(10_000.0, 3.37, perp_decimals=None, spot_decimals=0)
        self.assertEqual(r["decimals"], 0)
        self.assertTrue(r["tradeable"])

    def test_both_unknown_is_not_tradeable(self):
        r = matched_leg_size(10_000.0, 3.37, None, None)
        self.assertFalse(r["tradeable"])
        self.assertIn("unknown", r["reason"])

    def test_a_notional_too_small_for_the_precision_is_refused(self):
        """A zero size is not a small position; it is a naked leg waiting to happen."""
        r = matched_leg_size(2.0, 3.37, 0, 2)
        self.assertFalse(r["tradeable"])
        self.assertEqual(r["size"], 0.0)

    def test_a_zero_price_is_refused_rather_than_dividing(self):
        self.assertFalse(matched_leg_size(10_000.0, 0.0, 0, 2)["tradeable"])

    def test_equal_precisions_behave_normally(self):
        r = matched_leg_size(10_000.0, 100.0, 4, 4)
        self.assertEqual(r["decimals"], 4)
        self.assertEqual(r["size"], 100.0)


class TestHarvesterUsesMatchedSizing(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.h = BasisHarvester(100_000.0, str(Path(self._tmp.name) / "b.json"))

    def tearDown(self):
        self._tmp.cleanup()

    def opp(self, perp_dec=0, spot_dec=2, mark=3.37):
        return {"coin": "MON", "spot_symbol": "MON", "mark_px": mark,
                "funding_apr": 56.0, "net_apr": 56.0, "spread_bps": 0.4,
                "holding_days": 7.0, "is_spot_backed": True,
                "perp_sz_decimals": perp_dec, "spot_sz_decimals": spot_dec}

    def test_the_opened_size_respects_the_coarser_precision(self):
        p = self.h.open_position(self.opp(), notional_per_leg=10_000.0)
        self.assertEqual(p["size"], 2967.0)
        self.assertEqual(p["sz_decimals"], 0)
        self.assertEqual(p["size_residual"], 0.0)

    def test_a_position_too_small_for_the_precision_is_refused(self):
        self.assertIsNone(self.h.open_position(self.opp(), notional_per_leg=2.0))

    def test_unknown_precision_still_opens_on_the_legacy_path(self):
        """Absent szDecimals we do not block the paper book, but nothing is rounded."""
        o = self.opp(perp_dec=None, spot_dec=None)
        self.assertIsNotNone(self.h.open_position(o, notional_per_leg=10_000.0))


class TestDynamicYieldExit(unittest.TestCase):
    """
    Holds through DECAY, exits on REVERSAL. A 12% floor was rejected on measurement:
    63.6% of >=25% readings fall under 12% within 24h, so it churns nearly every
    position inside a day and pays 0.09% each time - about three days of yield at
    the very rate it is exiting for being too low.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.h = BasisHarvester(100_000.0, str(Path(self._tmp.name) / "b.json"))
        self.h.open_position(
            {"coin": "MON", "spot_symbol": "MON", "mark_px": 10.0, "funding_apr": 56.0,
             "net_apr": 56.0, "spread_bps": 0.4, "holding_days": 7.0,
             "is_spot_backed": True, "perp_sz_decimals": 2, "spot_sz_decimals": 2},
            notional_per_leg=10_000.0)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_decayed_but_positive_yield_is_held(self):
        """8% APR still pays. An exit always costs."""
        self.assertIsNone(self.h.should_exit("MON", 8.0))

    def test_a_yield_that_turns_negative_is_exited(self):
        self.assertIsNotNone(self.h.should_exit("MON", -5.0))

    def test_the_configured_floor_is_zero_not_twelve(self):
        self.assertEqual(BASIS_EXIT_APR_FLOOR, 0.0)
        self.assertIsNone(self.h.should_exit("MON", 11.0))

    def test_an_unknown_rate_is_not_an_exit_signal(self):
        """A data gap is not a reversal."""
        self.assertIsNone(self.h.should_exit("MON", None))

    def test_a_position_we_do_not_hold_yields_no_signal(self):
        self.assertIsNone(self.h.should_exit("GHOST", -9.0))

    def test_sweep_closes_only_the_adverse_positions(self):
        self.h.open_position(
            {"coin": "AAA", "spot_symbol": "AAA", "mark_px": 5.0, "funding_apr": 40.0,
             "net_apr": 40.0, "spread_bps": 1.0, "holding_days": 7.0,
             "is_spot_backed": True, "perp_sz_decimals": 2, "spot_sz_decimals": 2},
            notional_per_leg=10_000.0)
        closed = self.h.sweep_exits({"MON": -3.0, "AAA": 9.0})
        self.assertEqual([c["coin"] for c in closed], ["MON"])
        self.assertIn("AAA", self.h.positions)

    def test_the_exit_reason_is_recorded(self):
        closed = self.h.sweep_exits({"MON": -3.0})
        self.assertIn("adverse", closed[0]["exit_reason"])

    def test_an_overriding_floor_is_honoured(self):
        """The mechanism supports a higher floor; the DEFAULT is what was measured."""
        self.assertIsNotNone(self.h.should_exit("MON", 11.0, floor_apr=12.0))
