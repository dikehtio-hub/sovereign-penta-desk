"""
Tests for the cross-market hybrid arbitrage engine, matcher and HUD.

Two things are being defended here, and they fail in different ways.

THE TAX ENGINE fails quietly and expensively: a wrong delta reports a position
as riskless when it loses money, and nothing downstream contradicts it. So the
engine is pinned against CLOSED FORMS wherever one exists - the known
single-venue arbitrage hurdle, and the trivially-zero fully-relieved case - and
against monotonicity properties everywhere else.

THE MATCHER fails catastrophically: pair a YES with a bet on the same side and
the desk has double exposure booked as an arbitrage. Those tests are about
REFUSAL, and most of them assert that something returns None.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from cross_market.hybrid_arb import (CAPITAL_LOSS_ORDINARY_CAP, HybridArbError,
                                     HybridLeg, LegTax, branch_returns,
                                     breakeven_gross_arb, build_legs,
                                     evaluate_hybrid_arb, optimal_split,
                                     polymarket_leg_tax, polymarket_odds,
                                     prediction_as_wagering_tax, resolve_rates,
                                     sportsbook_leg_tax)
from cross_market.hud import render_cross_market, scan_cross_market
from cross_market.matcher import (MONEYLINE, SPREAD, TOTALS, hedge_leg_for,
                                  lines_match, load_book_quotes, match_markets,
                                  normalise, normalise_question,
                                  parse_polymarket_question, resolve_team)

ORD, ST = 0.3237, 0.0637      # NJ composite and the bare state rate
BIG = 1e12                    # "capacity is not the binding constraint"


class Hook:
    """The tax hook reduced to what these modules read from it."""

    config = {"tax_rates": {"short_term_capital_gains": 0.24,
                            "state_tax_rate": 0.0637,
                            "safety_buffer_pct": 0.02}}


def _legs(tax_a, tax_b, odds_a=2.10, odds_b=2.10):
    return (HybridLeg("polymarket", "KC_CHIEFS", odds_a, tax_a, token_id="tok1",
                      limit_price=1.0 / odds_a),
            HybridLeg("draftkings", "BUF_BILLS", odds_b, tax_b))


def _hurdle(tax_a, tax_b, odds_a=2.10, odds_b=2.10):
    return breakeven_gross_arb(*_legs(tax_a, tax_b, odds_a, odds_b))


# ---------------------------------------------------------------------------
# The engine, against closed forms
# ---------------------------------------------------------------------------

class TestAgainstClosedForms(unittest.TestCase):
    """Where a formula exists, the engine must reproduce it, not approximate it."""

    def test_two_gambling_legs_reproduce_the_single_venue_hurdle(self):
        """
        The control that makes everything else believable.

        With both legs taxed as gambling and NO deduction at all, a cross-market
        pair is just a two-way arbitrage at delta = 0, whose hurdle is known in
        closed form: (1 - t/2)/(1 - t) - 1. If the general solver disagrees with
        that, its answers in the asymmetric cases mean nothing either.
        """
        no_relief = sportsbook_leg_tax(ORD, 0.0, 0.0)
        closed_form = (1.0 - ORD * 0.5) / (1.0 - ORD) - 1.0
        self.assertAlmostEqual(_hurdle(no_relief, no_relief), closed_form, places=6)
        self.assertAlmostEqual(closed_form, 0.239317, places=6)

    def test_full_relief_on_both_legs_has_a_zero_hurdle(self):
        """
        Tax that is symmetric and fully refunded on losses cannot create a hurdle.

        This is the case that caught a real bug: the breakeven search was capped
        at the book as quoted, so for a position that already cleared it returned
        the CURRENT arbitrage and called it the hurdle. A position with room to
        spare was reported as scraping through.
        """
        full = LegTax("full", ORD, ORD, BIG)
        self.assertAlmostEqual(_hurdle(full, full), 0.0, places=6)

    def test_the_hurdle_is_a_property_of_shape_not_of_the_live_book(self):
        """Widening the book must not move the threshold the book is judged against."""
        a = polymarket_leg_tax(ORD, ORD, BIG)
        b = sportsbook_leg_tax(ORD, ST, BIG)
        hurdles = [_hurdle(a, b, o, o) for o in (1.90, 2.10, 2.50, 4.00)]
        for value in hurdles[1:]:
            self.assertAlmostEqual(value, hurdles[0], places=6)

    def test_prediction_read_as_wagering_collapses_to_the_gambling_hurdle(self):
        """
        The adverse characterisation is worth roughly seven points of hurdle.

        If a Polymarket contract is a wager under IRC 165(d) rather than property
        under 1234A, the capital relief disappears and the pair is no better than
        staying inside the sportsbook. That is the downside of an assumption the
        IRS has never ruled on, and it must be priceable rather than assumed away.
        """
        adverse = _hurdle(prediction_as_wagering_tax(ORD, ST, 0.0),
                          sportsbook_leg_tax(ORD, ST, 0.0))
        capital = _hurdle(polymarket_leg_tax(ORD, ORD, 0.0),
                          sportsbook_leg_tax(ORD, ST, 0.0))
        self.assertAlmostEqual(adverse, 0.239317, places=5)
        self.assertLess(capital, adverse)
        self.assertGreater(adverse - capital, 0.05)


# ---------------------------------------------------------------------------
# The asymmetry itself
# ---------------------------------------------------------------------------

class TestReliefCapacity(unittest.TestCase):
    """
    A delta is not a property of a leg. It is a property of the leg AND the rest
    of the year's income, which is exactly what the cross-market case exposes.
    """

    def test_capacity_strictly_lowers_the_hurdle(self):
        pm = lambda cap: polymarket_leg_tax(ORD, ORD, cap)
        sb = lambda cap: sportsbook_leg_tax(ORD, ST, cap)
        none = _hurdle(pm(0.0), sb(0.0))
        gambling = _hurdle(pm(0.0), sb(50000.0))
        capital = _hurdle(pm(50000.0), sb(0.0))
        both = _hurdle(pm(BIG), sb(BIG))
        self.assertGreater(none, gambling)
        self.assertGreater(none, capital)
        self.assertGreater(gambling, both)
        self.assertGreater(capital, both)
        # The realistic case is roughly double the best case, and the gap is the
        # whole reason the defaults are zero.
        self.assertGreater(none, 0.16)
        self.assertLess(both, 0.09)

    def test_capital_gains_are_worth_more_than_gambling_winnings(self):
        """
        Not symmetric, and the direction matters for which capacity to chase.

        A capital loss is relieved at the FULL composite rate; a sportsbook loss
        is relieved only at the bare state rate, because the federal deduction is
        worth nothing to a standard-deduction filer. So a dollar of capital-gain
        capacity buys about five times the relief of a dollar of gambling-win
        capacity, and the hurdle reflects that.
        """
        with_capital = _hurdle(polymarket_leg_tax(ORD, ORD, 50000.0),
                               sportsbook_leg_tax(ORD, ST, 0.0))
        with_gambling = _hurdle(polymarket_leg_tax(ORD, ORD, 0.0),
                                sportsbook_leg_tax(ORD, ST, 50000.0))
        self.assertLess(with_capital, with_gambling)

    def test_the_sportsbook_effective_delta_is_not_one(self):
        """
        `delta_state = 1.0` reads as full relief and is not.

        Full NJ netting on a leg with no federal deduction relieves the loss at
        6.37%, against a 32.37% rate on the win - an effective delta near 0.20.
        Feeding 1.0 into a single-delta model overstates the relief fivefold.
        """
        leg = sportsbook_leg_tax(ORD, ST, 50000.0)
        self.assertAlmostEqual(leg.effective_delta, ST / ORD, places=6)
        self.assertLess(leg.effective_delta, 0.20)

    def test_the_1211b_tranche_is_capped_and_the_rest_is_not_credited(self):
        """
        Beyond $3,000, a capital loss with no gains to absorb it is worth zero
        THIS year. The carryforward under 1212(b) is real but undatable at the
        moment of placing the bet, so crediting it would be assuming next year's
        gains.
        """
        leg = polymarket_leg_tax(ORD, ORD, capital_gain_capacity=0.0)
        self.assertAlmostEqual(leg.relief_on(1000.0), 1000.0 * ORD, places=6)
        self.assertAlmostEqual(leg.relief_on(CAPITAL_LOSS_ORDINARY_CAP),
                               CAPITAL_LOSS_ORDINARY_CAP * ORD, places=6)
        # A $50,000 loss is relieved on the first $3,000 only - not on $50,000.
        self.assertAlmostEqual(leg.relief_on(50000.0),
                               CAPITAL_LOSS_ORDINARY_CAP * ORD, places=6)

    def test_a_gambling_loss_is_relieved_only_up_to_available_winnings(self):
        """NJ nets against winnings and cannot exceed them; there is no carryover."""
        leg = sportsbook_leg_tax(ORD, ST, gambling_win_capacity=400.0)
        self.assertAlmostEqual(leg.relief_on(400.0), 400.0 * ST, places=6)
        self.assertAlmostEqual(leg.relief_on(10000.0), 400.0 * ST, places=6)
        self.assertEqual(sportsbook_leg_tax(ORD, ST, 0.0).relief_on(10000.0), 0.0)


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------

class TestSizing(unittest.TestCase):

    def test_the_optimal_split_equalises_the_branches(self):
        a, b = _legs(polymarket_leg_tax(ORD, ORD, BIG), sportsbook_leg_tax(ORD, ST, BIG))
        f = optimal_split(a, b, 10000.0)
        one, two = branch_returns(a, b, f * 10000.0, (1 - f) * 10000.0)
        self.assertAlmostEqual(one, two, places=4)

    def test_no_other_split_beats_the_optimum(self):
        """A grid search must not find a better worst case than the solver did."""
        a, b = _legs(polymarket_leg_tax(ORD, ORD, BIG), sportsbook_leg_tax(ORD, ST, BIG),
                     odds_a=2.60, odds_b=2.40)
        capital = 10000.0
        best = optimal_split(a, b, capital)
        theirs = min(branch_returns(a, b, best * capital, (1 - best) * capital))
        for i in range(1, 500):
            f = i / 500.0
            mine = min(branch_returns(a, b, f * capital, (1 - f) * capital))
            self.assertLessEqual(mine, theirs + 1e-6)

    def test_stakes_exhaust_the_capital(self):
        result = evaluate_hybrid_arb(
            *_legs(polymarket_leg_tax(ORD, ORD, BIG), sportsbook_leg_tax(ORD, ST, BIG)),
            capital=2500.0)
        self.assertAlmostEqual(result.stake_a + result.stake_b, 2500.0, places=6)

    def test_the_split_survives_the_kink_in_the_relief_curve(self):
        """
        The reason the solver bisects instead of using a closed form.

        Relief is piecewise linear: it kinks where the loss exhausts capacity and
        again at the 1211(b) ceiling. A dutch derived on the uncapped branch is
        wrong past the first kink and wrong optimistically. Here capacity is small
        enough that the optimum sits beyond it, and the branches must still meet.
        """
        a, b = _legs(polymarket_leg_tax(ORD, ORD, 500.0),
                     sportsbook_leg_tax(ORD, ST, 200.0))
        capital = 10000.0
        f = optimal_split(a, b, capital)
        one, two = branch_returns(a, b, f * capital, (1 - f) * capital)
        self.assertAlmostEqual(one, two, places=4)


# ---------------------------------------------------------------------------
# Verdicts and warnings
# ---------------------------------------------------------------------------

class TestVerdicts(unittest.TestCase):

    def test_a_real_two_percent_arb_is_an_after_tax_loss(self):
        """
        The headline finding, stated as a test.

        Cross-book arbitrage pays 1-3%. At the realistic zero-capacity setting the
        hurdle is about 17%. So the ordinary case is a gross arbitrage that loses
        money, and the engine must say so rather than report a small positive.
        """
        odds = 2.0 / 0.99          # book sum 0.99: a fat 1.01% arbitrage
        result = evaluate_hybrid_arb(
            *_legs(polymarket_leg_tax(ORD, ORD, 0.0),
                   sportsbook_leg_tax(ORD, ST, 0.0), odds, odds),
            capital=10000.0)
        self.assertGreater(result.gross_arb, 0.0)
        self.assertFalse(result.viable)
        self.assertLess(result.worst_after_tax, 0.0)
        self.assertTrue(any("AFTER-TAX LOSS ON A GROSS ARBITRAGE" in w
                            for w in result.warnings))

    def test_tax_manufactures_variance_from_a_riskless_position(self):
        """
        A gross arbitrage pays the same either way. After tax it does not, because
        one branch books a taxable win against a non-deductible loss.

        THE METRIC MUST BE MEASURED AT THE NAIVE STAKE, not at ours. An earlier
        version measured the spread on the split this module chooses - a split
        found by equalising the branches - so it reported 0.00% for every position
        ever priced, and the warning that reads it could never fire. Both are
        pinned here: our own split is flat, the pre-tax split is not.
        """
        result = evaluate_hybrid_arb(
            *_legs(polymarket_leg_tax(ORD, ORD, 0.0), sportsbook_leg_tax(ORD, ST, 0.0),
                   2.60, 1.72),
            capital=10000.0)
        self.assertAlmostEqual(result.branch_a, result.branch_b, places=4)
        self.assertGreater(result.tax_manufactured_variance, 0.005 * result.capital)
        self.assertTrue(any("BRANCHES LAND" in w for w in result.warnings))

    def test_a_symmetric_pair_manufactures_no_variance(self):
        """Equal odds and equal treatment: the naive stake is already correct."""
        full = LegTax("full", ORD, ORD, BIG)
        result = evaluate_hybrid_arb(*_legs(full, full, 2.10, 2.10), capital=10000.0)
        self.assertAlmostEqual(result.tax_manufactured_variance, 0.0, places=6)

    def test_zero_capacity_on_both_legs_is_called_out(self):
        result = evaluate_hybrid_arb(
            *_legs(polymarket_leg_tax(ORD, ORD, 0.0), sportsbook_leg_tax(ORD, ST, 0.0)),
            capital=1000.0)
        self.assertTrue(any("NEITHER LEG HAS RELIEF CAPACITY" in w
                            for w in result.warnings))

    def test_a_book_that_is_not_an_arbitrage_says_so(self):
        result = evaluate_hybrid_arb(
            *_legs(polymarket_leg_tax(ORD, ORD, BIG), sportsbook_leg_tax(ORD, ST, BIG),
                   1.80, 1.80), capital=1000.0)
        self.assertGreater(result.booksum, 1.0)
        self.assertTrue(any("NOT AN ARBITRAGE GROSS" in w for w in result.warnings))

    def test_degenerate_inputs_are_refused(self):
        legs = _legs(polymarket_leg_tax(ORD, ORD, BIG), sportsbook_leg_tax(ORD, ST, BIG))
        with self.assertRaises(HybridArbError):
            evaluate_hybrid_arb(*legs, capital=0.0)
        with self.assertRaises(HybridArbError):
            polymarket_odds(0.0)
        with self.assertRaises(HybridArbError):
            polymarket_odds(1.0)
        with self.assertRaises(HybridArbError):
            evaluate_hybrid_arb(HybridLeg("pm", "X", 1.0, legs[0].tax), legs[1])


class TestVenuePricing(unittest.TestCase):

    def test_polymarket_odds_are_the_inverse_price(self):
        self.assertAlmostEqual(polymarket_odds(0.40), 2.5, places=9)
        self.assertAlmostEqual(polymarket_odds(0.50), 2.0, places=9)

    def test_the_fee_lands_on_proceeds_not_on_the_returned_stake(self):
        """
        Polymarket charges on PROCEEDS. Applying the fee to the whole payout would
        tax the returned stake as though it were profit, which overstates the
        charge badly at short odds - at 0.90 the stake is nine tenths of the
        payout.
        """
        gross = polymarket_odds(0.90)
        netted = polymarket_odds(0.90, fee_rate=0.02)
        self.assertAlmostEqual(netted - 1.0, (gross - 1.0) * 0.98, places=9)
        self.assertGreater(netted, 1.0)

    def test_rates_come_from_config_not_from_constants(self):
        ordinary, capital, state = resolve_rates(Hook())
        self.assertAlmostEqual(state, 0.0637, places=6)
        self.assertAlmostEqual(ordinary, 0.3237, places=6)
        self.assertAlmostEqual(capital, ordinary, places=6)

    def test_build_legs_reads_the_hook(self):
        a, b = build_legs(Hook(), 0.45, "KC_CHIEFS", "draftkings", 2.30, "BUF_BILLS",
                          token_id="tok9")
        self.assertEqual(a.token_id, "tok9")
        self.assertAlmostEqual(a.decimal_odds, 1 / 0.45, places=9)
        self.assertAlmostEqual(b.tax.relief_rate, 0.0637, places=6)
        self.assertAlmostEqual(a.tax.relief_rate, 0.3237, places=6)

    def test_the_adverse_reading_is_selectable_from_build_legs(self):
        a, _ = build_legs(Hook(), 0.45, "KC_CHIEFS", "dk", 2.30, "BUF_BILLS",
                          prediction_is_wagering=True)
        self.assertAlmostEqual(a.tax.relief_rate, 0.0637, places=6)


# ---------------------------------------------------------------------------
# The matcher: these tests are about refusal
# ---------------------------------------------------------------------------

class TestTeamResolution(unittest.TestCase):

    def test_the_aliases_in_the_specification_resolve(self):
        for text in ("KC Chiefs", "Kansas City Chiefs", "Chiefs", "kansas city chiefs"):
            self.assertEqual(resolve_team(text).canonical, "KC_CHIEFS", text)

    def test_a_shared_city_is_not_a_match(self):
        """
        Kansas City fields the Chiefs and the Royals. Matching on city would pair
        an NFL market with an MLB one and book it as a hedge.
        """
        self.assertIsNone(resolve_team("Kansas City"))
        self.assertIsNone(resolve_team("New York"))
        self.assertIsNone(resolve_team("Los Angeles"))

    def test_an_ambiguous_nickname_returns_nothing_until_a_sport_is_given(self):
        for nickname, nfl, mlb in (("Cardinals", "ARI_CARDINALS", "STL_CARDINALS"),
                                   ("Giants", "NYG_GIANTS", "SF_GIANTS")):
            self.assertIsNone(resolve_team(nickname), nickname)
            self.assertEqual(resolve_team(nickname, "NFL").canonical, nfl)
            self.assertEqual(resolve_team(nickname, "MLB").canonical, mlb)
        self.assertIsNone(resolve_team("Panthers"))
        self.assertIsNone(resolve_team("Kings"))
        self.assertEqual(resolve_team("Kings", "NHL").canonical, "LAK_KINGS")
        self.assertEqual(resolve_team("Kings", "NBA").canonical, "SAC_KINGS")

    def test_an_unknown_team_is_not_forced_onto_a_known_one(self):
        self.assertIsNone(resolve_team("Seattle Kraken"))
        self.assertIsNone(resolve_team(""))
        self.assertIsNone(resolve_team("the winner of the game"))

    def test_the_longest_alias_wins_inside_a_longer_string(self):
        """`Kansas City Chiefs` must beat the bare `Chiefs` so the city is used."""
        self.assertEqual(
            resolve_team("bet on the Kansas City Chiefs tonight").canonical,
            "KC_CHIEFS")


class TestQuestionParsing(unittest.TestCase):

    def test_moneyline_shapes(self):
        for question in ("Will the Kansas City Chiefs beat the Buffalo Bills?",
                         "Will the Chiefs defeat the Bills?",
                         "Will the Chiefs win against the Bills?"):
            market = parse_polymarket_question(question)
            self.assertIsNotNone(market, question)
            self.assertEqual(market.market_type, MONEYLINE)
            self.assertEqual(market.yes_team.canonical, "KC_CHIEFS")
            self.assertEqual(market.opponent.canonical, "BUF_BILLS")

    def test_the_question_normaliser_keeps_the_decimal_point(self):
        """
        The bug this pins: the team normaliser strips punctuation, so a question
        run through it turned "by more than 3.5 points" into "3 5 POINTS". The
        spread pattern stopped matching and the market fell through to the
        MONEYLINE branch - which would then have been hedged against the
        opponent's moneyline. That is not a hedge: when the favourite wins by less
        than the handicap, both legs lose together.
        """
        self.assertEqual(normalise("by 3.5 points"), "BY 3 5 POINTS")
        self.assertEqual(normalise_question("by 3.5 points"), "BY 3.5 POINTS")
        market = parse_polymarket_question(
            "Will the Chiefs beat the Bills by more than 3.5 points?")
        self.assertEqual(market.market_type, SPREAD)
        self.assertEqual(market.line, "-3.5")

    def test_totals_carry_their_side_and_line(self):
        over = parse_polymarket_question(
            "Will the Chiefs vs Bills total go over 45.5 points?")
        self.assertEqual(over.market_type, TOTALS)
        self.assertEqual(over.yes_side, "OVER")
        self.assertEqual(over.line, "45.5")
        under = parse_polymarket_question(
            "Will the Chiefs vs Bills total go under 45.5 points?")
        self.assertEqual(under.yes_side, "UNDER")

    def test_a_fixture_with_no_direction_is_refused(self):
        """
        "Chiefs vs Bills" names the game but not which side the YES share is on.
        Guessing that is guessing the direction of the hedge, and getting it
        backwards doubles the exposure instead of cancelling it.
        """
        self.assertIsNone(parse_polymarket_question("Chiefs vs Bills"))
        self.assertIsNone(parse_polymarket_question("Chiefs vs Bills Winner"))

    def test_a_cross_sport_fixture_cannot_exist_and_is_refused(self):
        """
        Each half of "Will the Chiefs beat the Royals?" resolves perfectly well.
        Only the PAIR is nonsense, and every check downstream is about price and
        would pass it.
        """
        self.assertIsNone(parse_polymarket_question("Will the Chiefs beat the Royals?"))
        self.assertIsNone(parse_polymarket_question("Will the Lakers beat the Bills?"))

    def test_a_team_against_itself_is_refused(self):
        self.assertIsNone(parse_polymarket_question("Will the Chiefs beat the Chiefs?"))

    def test_unrecognised_shapes_are_refused_rather_than_approximated(self):
        for question in ("Will the Yankees dominate the Dodgers?",
                         "Who wins the Super Bowl?", "", "Will it rain?"):
            self.assertIsNone(parse_polymarket_question(question), question)


class TestHedgeDirection(unittest.TestCase):
    """The safety-critical relation: the second leg must be provably opposite."""

    def test_a_moneyline_yes_is_hedged_by_the_opponent(self):
        market = parse_polymarket_question("Will the Chiefs beat the Bills?")
        self.assertEqual(hedge_leg_for(market).selection, "BUF_BILLS")

    def test_a_spread_is_hedged_by_the_mirrored_handicap(self):
        market = parse_polymarket_question(
            "Will the Chiefs beat the Bills by more than 3.5 points?")
        target = hedge_leg_for(market)
        self.assertEqual(target.selection, "BUF_BILLS")
        self.assertTrue(lines_match(target.line, "+3.5"))

    def test_over_is_hedged_by_under_at_the_same_total(self):
        over = parse_polymarket_question(
            "Will the Chiefs vs Bills total go over 45.5 points?")
        target = hedge_leg_for(over)
        self.assertEqual(target.selection, "UNDER")
        self.assertEqual(target.line, "45.5")

    def test_a_half_point_apart_is_a_middle_and_not_a_hedge(self):
        """
        -3.5 against -3.0 leaves an outcome where BOTH legs lose. Treating it as a
        hedge reports the risk as zero when it is not.
        """
        self.assertFalse(lines_match("-3.5", "-3.0"))
        self.assertFalse(lines_match("45.5", "44.5"))
        self.assertTrue(lines_match("-3.5", "-3.50"))
        self.assertTrue(lines_match("3", "3.0"))


class TestMatchingAgainstTheBook(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.db = Path(self.dir.name) / "sports_market.db"
        conn = sqlite3.connect(self.db)
        conn.execute("""CREATE TABLE fair_odds_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            event_id TEXT NOT NULL, sport TEXT NOT NULL, market_type TEXT NOT NULL,
            line TEXT NOT NULL DEFAULT '', sportsbook TEXT NOT NULL,
            selection TEXT NOT NULL, offered_odds REAL NOT NULL)""")
        conn.commit()
        conn.close()

    def _quote(self, selection, odds, book="draftkings", market="moneyline",
               line="", when="2026-09-01T12:00:00Z"):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO fair_odds_measurements (timestamp, event_id, sport, "
                     "market_type, line, sportsbook, selection, offered_odds) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (when, "KC_BUF_2026", "NFL", market, line, book, selection, odds))
        conn.commit()
        conn.close()

    def test_the_opposite_side_is_matched_and_the_same_side_is_not(self):
        """
        THE CATASTROPHIC CASE. A YES on the Chiefs paired with a sportsbook bet ON
        the Chiefs is not a hedge - it is the same bet twice, booked as riskless.
        """
        self._quote("Kansas City Chiefs", 2.20)
        market = parse_polymarket_question("Will the Chiefs beat the Bills?",
                                           yes_price=0.45, token_id="tok1")
        self.assertEqual(match_markets([market], load_book_quotes(self.db)), [])
        self._quote("Buffalo Bills", 2.30)
        pairs = match_markets([market], load_book_quotes(self.db))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].book_selection, "Buffalo Bills")

    def test_the_best_price_on_the_hedge_side_wins(self):
        self._quote("Buffalo Bills", 2.10, book="fanduel")
        self._quote("Buffalo Bills", 2.45, book="betmgm")
        self._quote("Buffalo Bills", 2.30, book="draftkings")
        market = parse_polymarket_question("Will the Chiefs beat the Bills?",
                                           yes_price=0.45)
        pairs = match_markets([market], load_book_quotes(self.db))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].book, "betmgm")
        self.assertAlmostEqual(pairs[0].book_decimal_odds, 2.45, places=6)

    def test_a_spread_quote_at_a_different_number_is_not_matched(self):
        self._quote("Buffalo Bills", 1.95, market="spread", line="+7.5")
        market = parse_polymarket_question(
            "Will the Chiefs beat the Bills by more than 3.5 points?", yes_price=0.45)
        self.assertEqual(match_markets([market], load_book_quotes(self.db)), [])
        self._quote("Buffalo Bills", 1.91, market="spread", line="+3.5")
        pairs = match_markets([market], load_book_quotes(self.db))
        self.assertEqual(len(pairs), 1)
        self.assertAlmostEqual(pairs[0].book_decimal_odds, 1.91, places=6)

    def test_a_totals_quote_matches_the_opposite_side_at_the_same_total(self):
        self._quote("Under 45.5", 1.95, market="totals", line="45.5")
        market = parse_polymarket_question(
            "Will the Chiefs vs Bills total go over 45.5 points?", yes_price=0.48)
        pairs = match_markets([market], load_book_quotes(self.db))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].target.selection, "UNDER")

    def test_a_missing_database_yields_no_quotes_rather_than_raising(self):
        self.assertEqual(load_book_quotes(Path(self.dir.name) / "nope.db"), [])

    def test_only_the_latest_quote_per_book_and_side_survives(self):
        self._quote("Buffalo Bills", 2.10, when="2026-09-01T10:00:00Z")
        self._quote("Buffalo Bills", 2.40, when="2026-09-01T18:00:00Z")
        quotes = load_book_quotes(self.db)
        self.assertEqual(len(quotes), 1)
        self.assertAlmostEqual(quotes[0]["offered_odds"], 2.40, places=6)


# ---------------------------------------------------------------------------
# The HUD
# ---------------------------------------------------------------------------

class TestHud(unittest.TestCase):

    def _result(self, odds_a=2.10, odds_b=2.10, cap=BIG):
        return evaluate_hybrid_arb(
            *_legs(polymarket_leg_tax(ORD, ORD, cap), sportsbook_leg_tax(ORD, ST, cap),
                   odds_a, odds_b), capital=10000.0)

    def test_an_empty_panel_explains_itself(self):
        text = render_cross_market([])
        self.assertIn("No matched cross-market pairs", text)
        self.assertIn("SAME line", text)

    def test_a_clearing_pair_shows_both_legs_in_full(self):
        text = render_cross_market([self._result(3.0, 3.0)])
        self.assertIn("CLEARS", text)
        self.assertIn("LEG A  POLYMARKET", text)
        self.assertIn("LEG B  SPORTSBOOK", text)
        self.assertIn("token id", text)
        self.assertIn("limit price", text)
        self.assertIn("shares", text)
        self.assertIn("american", text)

    def test_a_rejected_pair_shows_the_number_it_needed_and_no_execution_detail(self):
        """
        A losing pair must not be rendered as an opportunity with a caveat. It gets
        one line, the hurdle it missed, and no token id or stake to act on.
        """
        text = render_cross_market([self._result(2.02, 2.02, cap=0.0)])
        self.assertIn("REJECTED", text)
        self.assertIn("needs", text)
        self.assertNotIn("LEG A  POLYMARKET", text)
        self.assertIn("NOTHING IS ACTIONABLE", text)

    def test_both_characterisations_are_shown_on_every_clearing_pair(self):
        """
        Round 29 ruled IRC 1234A capital the default and kept the wagering reading
        available. That is only useful if the operator sees what the adverse
        reading costs AT THE MOMENT OF DECIDING - showing one number turns a live
        legal question the IRS has not answered into a settled one.
        """
        text = render_cross_market([self._result(3.0, 3.0)])
        self.assertIn("IRC 1234A capital", text)
        self.assertIn("WAGERING", text)
        self.assertIn("165(d)", text)
        self.assertIn("has not ruled", text)

    def test_the_adverse_hurdle_is_never_better_than_the_capital_one(self):
        """Losing the capital treatment cannot make a position easier to clear."""
        from cross_market.hud import _adverse_hurdle
        for cap in (0.0, BIG):
            result = self._result(3.0, 3.0, cap=cap)
            self.assertGreaterEqual(_adverse_hurdle(result),
                                    result.breakeven_gross_arb - 1e-9)

    def test_no_stray_double_percent_reaches_the_screen(self):
        for text in (render_cross_market([]),
                     render_cross_market([self._result(3.0, 3.0)]),
                     render_cross_market([self._result(2.02, 2.02, cap=0.0)])):
            self.assertNotIn("%%", text)

    def test_the_scan_is_offline_and_survives_a_missing_database(self):
        results, pairs = scan_cross_market(
            Hook(), [{"question": "Will the Chiefs beat the Bills?",
                      "yes_price": 0.45, "token_id": "tok1"}],
            db_path=Path(tempfile.gettempdir()) / "definitely-not-here.db")
        self.assertEqual(results, [])
        self.assertEqual(pairs, [])

    def test_unparseable_questions_drop_out_of_the_scan(self):
        results, pairs = scan_cross_market(
            Hook(), [{"question": "Who wins the Super Bowl?", "yes_price": 0.2},
                     {"question": "Chiefs vs Bills", "yes_price": 0.5}])
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
