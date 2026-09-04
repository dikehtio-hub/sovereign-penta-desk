"""
Round 15 tests: the delta-neutral basis trade (long spot + short perp).

The point of this module is that it REFUSES things. A funding row that cannot be
built as an actually delta-neutral, actually costed position must not appear as
one, because a plausible-looking basis trade with an unhedgeable leg is worse
than no scanner at all. Most of what follows pins a rejection.

Fully offline - every opportunity is a synthetic dict.
"""

import unittest
from unittest import mock

from execution.strategies import basis_strategy as bs
from config.settings import (
    BASIS_MIN_FUNDING_APR,
    BASIS_MIN_NET_APR,
    MAKER_FEE_PCT,
    TAKER_FEE_PCT,
)


def opp(apr=50.0, spot="HYPE", spot_backed=True, mark=10.0, spread_bps=5.0, coin="HYPE"):
    return {
        "coin": coin,
        "mark_px": mark,
        "funding_apr": apr,
        "is_spot_backed": spot_backed,
        "spot_symbol": spot,
        "spread_bps": spread_bps,
        "holding_period_days": 7.0,
    }


class TestPositionConstruction(unittest.TestCase):
    def test_a_valid_opportunity_becomes_a_sized_two_leg_position(self):
        p = bs.build_position(opp(), notional_usd=10_000.0)
        self.assertEqual(p["structure"], "LONG_SPOT_SHORT_PERP")
        self.assertEqual(p["size"], 1_000.0)          # $10k / $10 mark
        self.assertEqual(p["total_capital_usd"], 20_000.0)
        self.assertEqual(p["notional_per_leg_usd"], 10_000.0)

    def test_the_legs_are_one_to_one_by_construction(self):
        """Unequal legs would leave residual delta, which is the whole thing this avoids."""
        p = bs.build_position(opp(mark=250.0), notional_usd=5_000.0)
        self.assertEqual(p["size"] * p["mark_px"], p["notional_per_leg_usd"])

    def test_return_on_capital_is_half_the_headline(self):
        """
        The APR is quoted against one leg but both legs tie up capital. Reporting
        the headline as the return would overstate it ~2x.
        """
        p = bs.build_position(opp())
        self.assertAlmostEqual(p["return_on_capital_pct"], p["projected_return_pct"] / 2.0, places=9)

    def test_fees_are_charged_on_both_legs(self):
        expected = (TAKER_FEE_PCT + MAKER_FEE_PCT) * 100.0 * 2
        self.assertAlmostEqual(bs.round_trip_fee_pct(), expected, places=12)
        p = bs.build_position(opp(), notional_usd=10_000.0)
        self.assertAlmostEqual(p["fees_usd"], expected / 100.0 * 10_000.0, places=9)

    def test_projected_pnl_is_funding_minus_fees(self):
        p = bs.build_position(opp(), notional_usd=10_000.0)
        self.assertAlmostEqual(p["projected_pnl_usd"], p["gross_funding_usd"] - p["fees_usd"],
                               places=9)

    def test_a_longer_hold_earns_more_funding_against_the_same_one_off_fee(self):
        short = bs.build_position(opp(), holding_days=1.0)
        long_ = bs.build_position(opp(), holding_days=30.0)
        self.assertGreater(long_["gross_funding_usd"], short["gross_funding_usd"])
        self.assertAlmostEqual(long_["fees_usd"], short["fees_usd"], places=9)


class TestDirectionConstraint(unittest.TestCase):
    """
    Hyperliquid spot has no borrow, so the mirror trade (long perp + SHORT spot)
    cannot be built. A negative-funding row is a directional bet on funding and
    must never be dressed up as delta-neutral.
    """

    def test_negative_funding_cannot_be_constructed(self):
        self.assertIsNone(bs.build_position(opp(apr=-80.0)))

    def test_zero_funding_cannot_be_constructed(self):
        self.assertIsNone(bs.build_position(opp(apr=0.0)))

    def test_a_market_with_no_spot_leg_is_rejected(self):
        self.assertIsNone(bs.build_position(opp(spot_backed=False, spot=None)))

    def test_spot_backed_flag_without_a_symbol_is_still_rejected(self):
        self.assertIsNone(bs.build_position(opp(spot=None)))

    def test_a_zero_mark_is_rejected_rather_than_dividing(self):
        self.assertIsNone(bs.build_position(opp(mark=0.0)))


class TestScanBars(unittest.TestCase):
    def scanner_returning(self, rows):
        s = mock.Mock()
        s.scan_funding_opportunities.return_value = {"short_harvest": rows,
                                                     "long_harvest": [], "rejected": []}
        s.fetch_spread_bps.return_value = None
        return s

    def test_a_row_clearing_both_bars_is_accepted(self):
        r = bs.scan_basis_opportunities(scanner=self.scanner_returning([opp(apr=60.0)]),
                                        check_spreads=False)
        self.assertEqual(len(r["accepted"]), 1)
        self.assertEqual(r["accepted"][0]["coin"], "HYPE")

    def test_a_row_failing_the_net_bar_is_rejected_with_a_reason(self):
        """Wide spread on both legs eats the yield: gross passes, net does not."""
        r = bs.scan_basis_opportunities(
            scanner=self.scanner_returning([opp(apr=30.0, spread_bps=200.0)]),
            check_spreads=False,
        )
        self.assertEqual(r["accepted"], [])
        self.assertIn("net APR", r["rejected"][0]["basis_reject"])

    def test_a_directional_row_is_rejected_as_not_neutral(self):
        r = bs.scan_basis_opportunities(
            scanner=self.scanner_returning([opp(spot_backed=False, spot=None)]),
            check_spreads=False,
        )
        self.assertEqual(r["accepted"], [])
        self.assertIn("directional", r["rejected"][0]["basis_reject"])

    def test_results_are_ranked_by_net_apr(self):
        rows = [opp(apr=30.0, coin="LOW"), opp(apr=90.0, coin="HIGH")]
        r = bs.scan_basis_opportunities(scanner=self.scanner_returning(rows), check_spreads=False)
        self.assertEqual([p["coin"] for p in r["accepted"]], ["HIGH", "LOW"])

    def test_total_pnl_sums_only_the_accepted(self):
        rows = [opp(apr=60.0, coin="A"), opp(apr=30.0, spread_bps=200.0, coin="B")]
        r = bs.scan_basis_opportunities(scanner=self.scanner_returning(rows), check_spreads=False)
        self.assertAlmostEqual(r["total_projected_pnl_usd"],
                               sum(p["projected_pnl_usd"] for p in r["accepted"]), places=9)


class TestUncostedRowsAreNotAccepted(unittest.TestCase):
    """
    Found by running it. `net_apr_after_spread` returns the GROSS APR untouched
    when no book was fetched, so an uncosted row would sail through the net bar
    it was never tested against. The first live run accepted two rows showing
    'SPRD n/a' - passing a bar they had not been measured against.

    The upstream spread filter only probes the head of the ranked list, and
    spot-backed rows are a small minority usually below that cap, so this path
    is the normal case rather than an edge case.
    """

    def scanner(self, measured):
        s = mock.Mock()
        s.scan_funding_opportunities.return_value = {
            "short_harvest": [opp(apr=60.0, spread_bps=None)],
            "long_harvest": [], "rejected": [],
        }
        s.fetch_spread_bps.return_value = measured
        return s

    def test_an_uncosted_row_is_costed_on_demand_then_judged(self):
        s = self.scanner(measured=5.0)
        r = bs.scan_basis_opportunities(scanner=s, check_spreads=True)
        s.fetch_spread_bps.assert_called_once()
        self.assertEqual(len(r["accepted"]), 1)
        self.assertEqual(r["accepted"][0]["spread_bps"], 5.0)

    def test_a_row_whose_spread_cannot_be_measured_is_rejected(self):
        r = bs.scan_basis_opportunities(scanner=self.scanner(measured=None), check_spreads=True)
        self.assertEqual(r["accepted"], [])
        self.assertIn("cost unknown", r["rejected"][0]["basis_reject"])

    def test_on_demand_costing_can_push_a_row_below_the_net_bar(self):
        r = bs.scan_basis_opportunities(scanner=self.scanner(measured=400.0), check_spreads=True)
        self.assertEqual(r["accepted"], [])
        self.assertIn("net APR", r["rejected"][0]["basis_reject"])


class TestSpreadCeilingReachesEveryCostedRow(unittest.TestCase):
    """
    Round 38. The scanner's max-spread filter probes only the head of its ranked
    list; a row costed on demand below that head was judged against the net bar
    alone. para:AVGO entered the paper book at 35.05 bps against a 25 bps ceiling
    because 77.9% gross amortised over 7 days still nets 41%.
    """

    def scanner(self, rows, measured=None):
        s = mock.Mock()
        s.scan_funding_opportunities.return_value = {"short_harvest": rows,
                                                     "long_harvest": [], "rejected": []}
        s.fetch_spread_bps.return_value = measured
        return s

    def test_the_para_avgo_case_is_rejected_by_the_ceiling_not_the_net_bar(self):
        row = opp(apr=77.928, spread_bps=None, coin="para:AVGO", spot="AVGO")
        r = bs.scan_basis_opportunities(scanner=self.scanner([row], measured=35.046),
                                        check_spreads=True, max_spread_bps=25.0)
        self.assertEqual(r["accepted"], [])
        self.assertEqual(r["rejected"][0]["basis_reject"], "spread 35.0bps > 25.0bps max")
        # It clears the net bar comfortably - which is exactly why the ceiling must be its own gate.
        costed = bs.build_position({**row, "spread_bps": 35.046})
        self.assertGreater(costed["net_apr"], BASIS_MIN_NET_APR)

    def test_a_pre_costed_row_over_the_ceiling_is_rejected_even_without_live_checks(self):
        r = bs.scan_basis_opportunities(scanner=self.scanner([opp(apr=60.0, spread_bps=30.0)]),
                                        check_spreads=False)
        self.assertEqual(r["accepted"], [])
        self.assertEqual(r["rejected"][0]["basis_reject"], "spread 30.0bps > 25.0bps max")

    def test_the_ceiling_is_configurable_and_reaches_the_scanner_too(self):
        s = self.scanner([opp(apr=60.0, spread_bps=30.0)])
        r = bs.scan_basis_opportunities(scanner=s, check_spreads=False, max_spread_bps=40.0)
        self.assertEqual(len(r["accepted"]), 1)
        self.assertEqual(r["max_spread_bps"], 40.0)
        self.assertEqual(s.scan_funding_opportunities.call_args.kwargs["max_spread_bps"], 40.0)

    def test_the_default_ceiling_is_the_arb_gate_and_is_inclusive(self):
        from config.settings import ARB_MAX_SPREAD_BPS
        self.assertEqual(ARB_MAX_SPREAD_BPS, 25.0)
        r = bs.scan_basis_opportunities(scanner=self.scanner([opp(spread_bps=25.0)]), check_spreads=False)
        self.assertEqual(len(r["accepted"]), 1)


class TestConfiguredBars(unittest.TestCase):
    def test_the_directive_bars_are_what_is_configured(self):
        """Net bar raised 15 -> 20 when the basis harvester became a primary
        engine rather than a scanner: it now commits capital, so it should
        require more than the reporting-only version did."""
        self.assertEqual(BASIS_MIN_FUNDING_APR, 25.0)
        self.assertEqual(BASIS_MIN_NET_APR, 20.0)


class TestReport(unittest.TestCase):
    def test_an_empty_scan_reports_a_finding_not_a_blank(self):
        text = bs.format_report(bs.scan_basis_opportunities(
            scanner=self.__class__._empty_scanner(), check_spreads=False))
        self.assertIn("No constructible basis trade", text)

    @staticmethod
    def _empty_scanner():
        s = mock.Mock()
        s.scan_funding_opportunities.return_value = {"short_harvest": [], "long_harvest": [],
                                                     "rejected": []}
        return s

    def test_an_accepted_row_is_rendered_with_its_persistence_caveat(self):
        s = mock.Mock()
        s.scan_funding_opportunities.return_value = {"short_harvest": [opp(apr=60.0)],
                                                    "long_harvest": [], "rejected": []}
        text = bs.format_report(bs.scan_basis_opportunities(scanner=s, check_spreads=False))
        self.assertIn("HYPE", text)
        self.assertIn("persists", text)


if __name__ == "__main__":
    unittest.main()
