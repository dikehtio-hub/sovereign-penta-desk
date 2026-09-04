"""
Unit tests for the Sports_Desk fair-value engine and its provenance store.

100% offline, and where possible ANALYTIC: a devigger is easy to write and hard
to check, because almost any monotone transform produces a plausible-looking
probability vector that sums to one. So the fixtures here are chosen to have
answers derivable by hand -

  * a symmetric market must devig to exactly 1/n by symmetry, whatever z is;
  * a market with no overround must come back unchanged;
  * the n=2 closed form must agree with the independent bisection solver;
  * the probabilities must sum to one and preserve the order of the raw prices;

- rather than to whatever the implementation happens to emit today. Tests that
only assert `sum(p) == 1` would pass against a badly wrong estimator.
"""
import json
import math
import tempfile
import unittest
from pathlib import Path

from Sports_Desk.data.db import (
    init_market_db,
    query_latest_measurements,
    record_fair_value_measurement,
)
from Sports_Desk.engine.fair_value import (
    ArbitrageError,
    DevigError,
    FairValueResult,
    calculate_edge,
    calculate_fair_value,
    kelly_fraction,
    power_devig,
    shin_devig,
)


def _bisection_shin(decimal_odds):
    """
    An INDEPENDENT Shin solver, written the slow obvious way, used as the oracle
    for the closed form. Deliberately not sharing code with the engine: a bug
    copied into both would agree with itself.
    """
    pi = [1.0 / o for o in decimal_odds]
    beta = sum(pi)

    def probs(z):
        u = 1.0 - z
        return [(math.sqrt(z * z + 4.0 * u * p * p / beta) - z) / (2.0 * u) for p in pi]

    low, high = 0.0, 1.0 - 1e-14
    for _ in range(400):
        mid = 0.5 * (low + high)
        if sum(probs(mid)) - 1.0 > 0:
            low = mid
        else:
            high = mid
    return probs(0.5 * (low + high))


# A realistic 8-team futures book, booksum 1.150. Real outright markets run
# 10-25% overround.
#
# The original fixture here was [3.5, 4.5, 6, 8, 15, 30, 50, 100], which sums to
# 0.9296 - a 7.6% UNDERROUND that no book offers, and that the arbitrage guard
# now rejects outright. It is the same odds ladder scaled onto a real margin, so
# the shape of the market is unchanged and only the impossible part is gone.
FUTURES_8 = [2.8292, 3.6376, 4.8501, 6.4668, 12.1253, 24.2505, 40.4175, 80.8351]


class TestFairValueEngine(unittest.TestCase):

    def test_symmetric_two_way_closed_form(self):
        """Standard -110/-110 line must yield exactly 50/50 under closed-form Shin."""
        odds = [1.909090909, 1.909090909]
        res = calculate_fair_value(odds)
        self.assertTrue(res.converged)
        self.assertEqual(res.method, "shin")
        self.assertAlmostEqual(res.outcomes[0].fair_prob, 0.50, places=4)
        self.assertAlmostEqual(res.outcomes[1].fair_prob, 0.50, places=4)
        self.assertAlmostEqual(res.outcomes[0].fair_odds, 2.00, places=4)
        self.assertAlmostEqual(sum(res.fair_probabilities), 1.0, places=6)
        self.assertFalse(res.divergent)
        self.assertLess(res.max_oracle_delta, 0.001)

    def test_two_way_skewed_shin(self):
        """Skewed 2-way market (-300 / +240 => 1.3333 / 3.4000)."""
        odds = [1.333333333, 3.400000000]
        res = calculate_fair_value(odds)
        self.assertTrue(res.converged)
        self.assertAlmostEqual(sum(res.fair_probabilities), 1.0, places=6)
        self.assertGreater(res.outcomes[0].fair_prob, 0.70)
        self.assertLess(res.outcomes[1].fair_prob, 0.30)
        self.assertGreater(res.shin_z, 0.0)

    def test_three_way_soccer_shin(self):
        """Soccer 1X2 (2.10, 3.40, 3.50). Iterative Shin sums to 1.0."""
        odds = [2.10, 3.40, 3.50]
        res = calculate_fair_value(odds)
        self.assertTrue(res.converged)
        self.assertAlmostEqual(sum(res.fair_probabilities), 1.0, places=6)
        self.assertFalse(res.divergent)

    def test_power_oracle_cross_check_and_divergence_flag(self):
        """Oracle divergence fires when Shin and Power differ by more than tolerance."""
        odds = [2.0, 3.0, 4.0]
        res_normal = calculate_fair_value(odds, oracle_tolerance=0.05)
        self.assertFalse(res_normal.divergent)

        res_tight = calculate_fair_value(odds, oracle_tolerance=0.001)
        self.assertTrue(res_tight.divergent)
        self.assertGreater(res_tight.max_oracle_delta, 0.001)

    def test_n_way_futures_convergence(self):
        """N-way futures market (8 teams) converges under both Shin and Power."""
        res = calculate_fair_value(FUTURES_8)
        self.assertTrue(res.converged)
        self.assertAlmostEqual(sum(res.fair_probabilities), 1.0, places=6)
        self.assertGreater(res.power_k, 1.0)
        for p in res.fair_probabilities:
            self.assertGreater(p, 0.0)

    def test_kelly_sizing_and_edge(self):
        """Validates gross edge and quarter-Kelly sizing."""
        ev = calculate_edge(fair_prob=0.55, offered_odds=2.00)
        self.assertAlmostEqual(ev, 0.10, places=4)
        qk = kelly_fraction(fair_prob=0.55, offered_odds=2.00, fraction=0.25)
        self.assertAlmostEqual(qk, 0.025, places=4)

        ev_neg = calculate_edge(fair_prob=0.45, offered_odds=2.00)
        self.assertAlmostEqual(ev_neg, -0.10, places=4)
        qk_neg = kelly_fraction(fair_prob=0.45, offered_odds=2.00, fraction=0.25)
        self.assertEqual(qk_neg, 0.0)

    def test_invalid_odds_errors(self):
        """Ensures invalid odds fail loudly."""
        with self.assertRaises(DevigError):
            calculate_fair_value([0.90, 1.90])
        with self.assertRaises(DevigError):
            calculate_fair_value([2.0])
        with self.assertRaises(DevigError):
            calculate_fair_value(["chiefs", 1.90])


class TestAnalyticProperties(unittest.TestCase):
    """Properties that hold by construction, so a wrong estimator cannot pass."""

    def test_two_way_closed_form_matches_the_iterative_solver(self):
        """
        The n=2 fast path claims to be exact. It is checked against an
        independently written bisection solver across the whole price range -
        from a symmetric -110 line out to a 1.001 / 501.0 market.
        """
        markets = [(1.909090909, 1.909090909), (1.6667, 2.30), (1.3333, 3.40),
                   (1.20, 4.75), (1.10, 7.50), (1.05, 12.0), (1.02, 26.0),
                   (1.01, 51.0), (2.5, 1.6), (1.005, 101.0), (1.001, 501.0)]
        for odds in markets:
            with self.subTest(odds=odds):
                fast, _, _, _ = shin_devig(list(odds))
                oracle = _bisection_shin(odds)
                for a, b in zip(fast, oracle):
                    self.assertAlmostEqual(a, b, places=12)

    def test_two_way_shin_is_an_equal_absolute_deduction(self):
        """
        The identity the closed form rests on, asserted directly: at n=2 Shin
        subtracts the SAME absolute margin from both sides. Not obvious - the
        general Shin correction is larger on longshots - and the whole n=2 fast
        path is wrong if it ever stops holding.
        """
        odds = [1.20, 4.75]
        raw = [1.0 / o for o in odds]
        margin = (sum(raw) - 1.0) / 2.0
        probs, _, _, _ = shin_devig(odds)
        for p, pi in zip(probs, raw):
            self.assertAlmostEqual(p, pi - margin, places=12)

    def test_symmetric_markets_devig_to_exactly_one_over_n(self):
        """True by symmetry for any correct estimator, whatever z or k comes out."""
        for n, price in ((2, 1.909090909), (3, 2.9), (4, 3.8), (8, 7.5)):
            with self.subTest(n=n):
                res = calculate_fair_value([price] * n)
                for p in res.fair_probabilities:
                    self.assertAlmostEqual(p, 1.0 / n, places=10)

    def test_a_market_with_no_overround_is_returned_unchanged(self):
        """Nothing to strip. The estimator must be the identity here, not a no-op
        that happens to look like one."""
        odds = [1.25, 5.0]                      # implied 0.80 + 0.20 = exactly 1.0
        res = calculate_fair_value(odds)
        self.assertAlmostEqual(res.overround, 0.0, places=12)
        self.assertAlmostEqual(res.fair_probabilities[0], 0.80, places=12)
        self.assertAlmostEqual(res.fair_probabilities[1], 0.20, places=12)
        self.assertAlmostEqual(res.shin_z, 0.0, places=12)

    def test_probabilities_sum_to_one_and_preserve_order(self):
        """A shorter price must never devig to a lower probability than a longer one."""
        markets = [[1.9091, 1.9091], [1.3333, 3.4], [2.10, 3.40, 3.50],
                   [1.5, 4.0, 9.0], FUTURES_8]
        for odds in markets:
            with self.subTest(odds=odds):
                res = calculate_fair_value(odds)
                self.assertAlmostEqual(sum(res.fair_probabilities), 1.0, places=10)
                ranked = sorted(zip(odds, res.fair_probabilities), key=lambda t: t[0])
                probs = [p for _, p in ranked]
                self.assertEqual(probs, sorted(probs, reverse=True))

    def test_shin_corrects_longshots_harder_than_multiplicative(self):
        """
        The reason Shin is the default. Against a proportional devig it must give
        the FAVOURITE more probability and the LONGSHOT less - that gap is the
        favourite-longshot bias, and getting its sign wrong manufactures value on
        exactly the bets that do not have any.
        """
        odds = [1.20, 4.75]
        res = calculate_fair_value(odds)
        raw = [1.0 / o for o in odds]
        booksum = sum(raw)
        multiplicative = [p / booksum for p in raw]
        self.assertGreater(res.fair_probabilities[0], multiplicative[0])
        self.assertLess(res.fair_probabilities[1], multiplicative[1])

    def test_vig_pct_is_hold_not_overround(self):
        """A 4.76% overround is a 4.55% hold; conflating them overstates the cost."""
        res = calculate_fair_value([1.909090909, 1.909090909])
        self.assertAlmostEqual(res.overround, 0.047619, places=6)
        self.assertAlmostEqual(res.vig_pct, 4.5455, places=3)

    def test_power_oracle_agrees_across_every_well_formed_market(self):
        """
        The tolerance is calibrated, so this asserts the calibration still holds:
        no realistic market may trip the divergence flag at the 0.03 default.
        """
        markets = [[1.9091, 1.9091], [1.6667, 2.30], [1.3333, 3.40], [1.20, 4.75],
                   [1.10, 7.50], [1.05, 12.0], [1.8333, 3.40, 3.80],
                   [1.25, 6.0, 11.0], FUTURES_8]
        for odds in markets:
            with self.subTest(odds=odds):
                res = calculate_fair_value(odds)
                self.assertFalse(res.divergent,
                                 f"well-formed market flagged: delta={res.max_oracle_delta}")
                self.assertLessEqual(res.max_oracle_delta, 0.011)

    def test_oracle_catches_a_leg_mistyped_by_ten_times(self):
        """The other half of the calibration: a corrupt leg must trip the flag."""
        res = calculate_fair_value([1.909090909, 1.0909090909])
        self.assertTrue(res.divergent)
        self.assertGreater(res.max_oracle_delta, 0.10)
        self.assertFalse(res.trustworthy)


class TestFailureModes(unittest.TestCase):
    """Every one of these was a real defect in an earlier draft of this engine."""

    def test_an_underround_market_is_an_arbitrage_signal_not_a_price(self):
        """
        Two books' best sides pasted together sum to 0.9524. Devigging it anyway
        reported a +5.00% edge on BOTH sides at once - arithmetically impossible,
        and the one result a scanner most needs surfaced.
        """
        with self.assertRaises(ArbitrageError) as ctx:
            calculate_fair_value([2.10, 2.10])
        self.assertAlmostEqual(ctx.exception.booksum, 0.952381, places=6)
        self.assertAlmostEqual(ctx.exception.edge_pct, 5.0, places=2)
        # It stays a DevigError, so existing catch sites still work.
        self.assertIsInstance(ctx.exception, DevigError)

    def test_the_arbitrage_guard_also_fires_on_the_solvers(self):
        for solver in (shin_devig, power_devig):
            with self.subTest(solver=solver.__name__):
                with self.assertRaises(ArbitrageError):
                    solver([2.10, 2.10])

    def test_a_non_converged_solve_is_not_renormalised_into_looking_valid(self):
        """
        THE MOST DANGEROUS DEFECT THIS ENGINE HAD. Rescaling the output so it
        sums to one made a failed solve indistinguishable from a good one: on
        1.20/4.75 an early stop gave [0.9058, 0.0942] against a true
        [0.8114, 0.1886] - 9.4 percentage points out - and still summed to
        exactly 1.0. Nothing about the vector looked wrong.
        """
        # n=2 is a closed form and cannot be starved - it reports converged
        # because it genuinely is, whatever the iteration budget.
        _, _, two_way_converged, _ = shin_devig([1.20, 4.75], max_iter=1)
        self.assertTrue(two_way_converged)

        # n>=3 runs the solver, and a starved solve must SAY so rather than be
        # rescaled into a plausible-looking vector.
        probs3, _, converged3, _ = shin_devig([2.10, 3.40, 3.50], max_iter=1)
        self.assertFalse(converged3)
        self.assertNotAlmostEqual(sum(probs3), 1.0, places=6)

        full = calculate_fair_value([2.10, 3.40, 3.50])
        self.assertTrue(full.converged)
        self.assertTrue(full.trustworthy)

    def test_american_and_fractional_prices_are_accepted(self):
        """
        The shared `OddsQuote` seam is the reason the tax ledger and this engine
        cannot disagree about what -110 means. A market quoted the way books
        actually quote it must devig without the caller converting first.
        """
        res = calculate_fair_value(["-110", "-110"])
        self.assertAlmostEqual(res.fair_probabilities[0], 0.5, places=10)

        res2 = calculate_fair_value(["-300", "+240"])
        direct = calculate_fair_value([1.333333333, 3.400000000])
        for a, b in zip(res2.fair_probabilities, direct.fair_probabilities):
            self.assertAlmostEqual(a, b, places=6)

        res3 = calculate_fair_value(["10/11", "EVEN"])
        self.assertAlmostEqual(sum(res3.fair_probabilities), 1.0, places=10)

    def test_a_bare_number_is_decimal_odds_by_contract(self):
        """
        100.0 is a legitimate decimal price in an outright field. The tax
        ledger's sniffer refuses it as ambiguous; here the signature settles it,
        so a futures book does not have to be tagged leg by leg.
        """
        res = calculate_fair_value([1.01, 100.0, 100.0])
        self.assertAlmostEqual(res.outcomes[1].offered_odds, 100.0, places=10)
        # The same value as a bare STRING is still ambiguous and still refused.
        with self.assertRaises(DevigError):
            calculate_fair_value(["1.01", "100.0", "100.0"])

    def test_trustworthy_requires_more_than_converged(self):
        """`converged` alone is not a green light - the oracle can still object."""
        good = calculate_fair_value([1.909090909, 1.909090909])
        self.assertTrue(good.trustworthy)
        flagged = calculate_fair_value([2.0, 3.0, 4.0], oracle_tolerance=0.001)
        self.assertTrue(flagged.converged)
        self.assertFalse(flagged.trustworthy)
        self.assertTrue(flagged.warnings)

    def test_a_dropped_leg_is_caught_only_when_it_breaks_the_booksum(self):
        """
        The limitation, pinned honestly in both directions.

        A dropped leg often DOES get caught, because removing its probability
        usually pushes the booksum under one and trips the arbitrage guard - a
        1X2 book at 1.056 loses its draw and lands at 0.77.

        But that is luck, not detection. When the remaining legs still carry
        margin the market devigs happily and WRONGLY, and nothing in the numbers
        can reveal it: a market missing a leg just looks like a market with less
        margin. Only the caller knows how many outcomes the event has.

        Measured on the 4-way below - a 1.0889 book less its 30.0 longshot,
        leaving 1.0556 - the favourite drifts from 0.5249 to 0.5343, and the EV
        on a 1.8 bet moves from -5.53% to -3.83%. Not enough to look wrong, and
        1.7 points is the entire margin most of these decisions turn on.
        """
        # Caught, incidentally: a 1X2 book less its draw falls to 0.77.
        with self.assertRaises(ArbitrageError):
            calculate_fair_value([2.10, 3.40])

        full = calculate_fair_value([1.8, 3.0, 6.0, 30.0])
        partial = calculate_fair_value([1.8, 3.0, 6.0])
        self.assertTrue(partial.trustworthy)          # looks perfectly healthy
        self.assertEqual(len(partial.fair_probabilities), 3)

        # Every surviving leg absorbs the dropped outcome's probability.
        for shared_partial, shared_full in zip(partial.fair_probabilities,
                                               full.fair_probabilities):
            self.assertGreater(shared_partial, shared_full)
        self.assertAlmostEqual(partial.fair_probabilities[0] - full.fair_probabilities[0],
                               0.0094, places=4)
        # And the edge it reports is 1.7 points too generous.
        self.assertAlmostEqual(partial.outcomes[0].expected_value
                               - full.outcomes[0].expected_value, 0.0169, places=4)


class TestProvenanceStore(unittest.TestCase):

    def test_provenance_database_persistence(self):
        """Full quote provenance is stored, not just the resulting probability."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "sports_market.db"
            init_market_db(test_db)

            odds = [1.909090909, 1.909090909]
            selections = ["Chiefs -3.5", "Ravens +3.5"]
            res = calculate_fair_value(odds)

            ids = record_fair_value_measurement(
                event_id="NFL_2026_WK1_KC_BAL",
                sport="NFL",
                selections=selections,
                market_type="spread",
                sportsbook="Pinnacle",
                result=res,
                db_path=test_db,
            )
            self.assertEqual(len(ids), 2)

            records = query_latest_measurements("NFL_2026_WK1_KC_BAL", db_path=test_db)
            self.assertEqual(len(records), 2)

            row0 = records[0]
            self.assertEqual(row0["sportsbook"], "Pinnacle")
            self.assertEqual(row0["selection"], "Chiefs -3.5")
            self.assertEqual(row0["divergent"], 0)
            self.assertAlmostEqual(row0["fair_prob"], 0.50, places=3)
            self.assertAlmostEqual(row0["fair_odds"], 2.00, places=3)

            raw_quotes = json.loads(row0["raw_quotes_json"])
            self.assertIn("Chiefs -3.5", raw_quotes)
            self.assertIn("Ravens +3.5", raw_quotes)
            self.assertAlmostEqual(raw_quotes["Chiefs -3.5"], 1.909090909, places=6)

    def test_every_leg_is_recoverable_from_any_single_row(self):
        """
        The point of storing the raw quotes as JSON on each row: a bet placed on
        a stale or one-legged market has to be diagnosable from the row alone,
        without reassembling the market from siblings.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "sports_market.db"
            init_market_db(test_db)
            res = calculate_fair_value([2.10, 3.40, 3.50])
            record_fair_value_measurement(
                event_id="EPL_ARS_CHE", sport="SOCCER",
                selections=["Arsenal", "Draw", "Chelsea"],
                market_type="1x2", sportsbook="Pinnacle",
                result=res, db_path=test_db)
            for row in query_latest_measurements("EPL_ARS_CHE", db_path=test_db):
                quotes = json.loads(row["raw_quotes_json"])
                self.assertEqual(len(quotes), 3)


if __name__ == "__main__":
    unittest.main()
