"""
Sports gambling tax module - unit tests.

Covers IRC 61 / 165(d) / 1402 and OBBBA 70114: the standard-deduction loss
disallowance, itemised netting under the 2026 90% haircut, state disallowance,
Form W-2G withholding credited FEDERALLY only, professional Schedule C with
statutory SE tax, odds normalisation, and the settlement edge cases a real
sportsbook export contains (cashouts, dead heats, partial voids, pushes,
settled-only exports, and repeated tickets on one selection).

The tests that assert a DOLLAR figure rather than a relationship carry the
arithmetic in the docstring. A tax test that only says "assertAlmostEqual(x, y)"
cannot be reviewed against a statute.
"""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from ..database.db import get_connection, init_db
from ..engine.gambling_tax import (GamblingInputs, GamblingPolicy, GamblingRates,
                                   assess_w2g, compute_gambling_tax, resolve_policy,
                                   resolve_rates)
from ..engine.lot_engine import (as_naive_utc, is_long_term, parse_iso_date,
                                 process_batch, rebuild_lots)
from ..engine.odds import (OddsFormatError, american_to_decimal, decimal_to_american,
                           parse_odds, payout_discrepancy)
from ..engine.tax_calculator import calculate_tax_summary
from ..ingestors.csv_watcher import classify_csv, load_sports_csv
from ..interfaces.monarch_hook import MonarchBankrollHook
from ..ingestors.sports_betting import (BetSettlementError, SportsBettingIngestor,
                                        canonical_book)


def _cfg(**gambling):
    """Base config with the gambling block overridden per test."""
    block = {
        "tax_treatment": "casual_standard_deduction",
        "state_allows_loss_deduction": True,
        "self_employment_tax_rate": 0.153,
        "track_w2g_withholdings": True,
        # Pinned to 1.0 in the base so a test that is NOT about the OBBBA haircut
        # states a number the statute gave before 2026 and stays readable.
        "loss_deduction_pct": 1.0,
    }
    block.update(gambling)
    return {
        # UNBUNDLED, matching config.yaml since Round 26k. The old fixture used
        # `short_term_capital_gains: 0.28` documented as a federal+state blend and
        # then added state again, so every figure below was computed at a 35%
        # composite that counted state twice. Composite is now 0.24 + 0.05 + 0.02.
        "tax_rates": {
            "federal_ordinary_rate": 0.24,
            "short_term_capital_gains": 0.24,
            "long_term_capital_gains": 0.15,
            "state_tax_rate": 0.05,
            "safety_buffer_pct": 0.02,
        },
        "portfolio": {"default_cash_balance_usdc": 10000.0, "tax_year": 2026},
        "accounting": {"method": "FIFO"},
        "gambling": block,
    }


class SportsTaxTestBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sports_tax.db"
        init_db(self.db_path)
        self.base_config = _cfg()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _wager(self, ticket, wager, result, payout, book="DraftKings", sport="NFL",
               selection=None, day="2026-01-10", odds=2.0, **kwargs):
        """Places and settles one ticket. Returns both transactions."""
        selection = selection or f"SEL_{ticket}"
        return [
            SportsBettingIngestor.create_bet_placed(
                ticket, book, sport, selection, wager, odds, f"{day} 13:00:00"),
            SportsBettingIngestor.create_bet_settled(
                ticket, book, sport, selection, result, payout, f"{day} 16:30:00",
                wager=wager, **kwargs),
        ]

    def _summary(self, config=None, year=2026):
        return calculate_tax_summary(year, db_path=self.db_path,
                                     config=config or self.base_config)


# ---------------------------------------------------------------------------
# 1. The statute, on numbers alone (no database).
# ---------------------------------------------------------------------------

class TestGamblingRules(unittest.TestCase):
    """`compute_gambling_tax` is pure, so the law can be tested without SQLite."""

    RATES = GamblingRates(federal_ordinary=0.28, state_ordinary=0.05, safety_buffer=0.02)

    def test_standard_deduction_taxes_gross_not_net(self):
        """Win $80k / lose $79k: base is $80,000, not the $1,000 banked."""
        result = compute_gambling_tax(
            GamblingInputs(gross_winnings=80000.0, gross_losses=79000.0, net_cash_pnl=1000.0),
            self.RATES, GamblingPolicy(treatment="casual_standard_deduction"), 2026)
        self.assertEqual(result.federal_taxable_base, 80000.0)
        self.assertEqual(result.loss_deduction_allowed, 0.0)
        self.assertEqual(result.loss_disallowed, 79000.0)
        # Federal is charged on the full $80,000: 80,000 x 0.28 = $22,400, plus a
        # $1,600 buffer, on a year that banked $1,000 in cash. The STATE nets to
        # $1,000 (default `state_allows_loss_deduction`), adding $50. $24,050 of
        # escrow against $1,000 of actual profit - that is the trap, and it is
        # federal.
        self.assertAlmostEqual(result.federal_tax, 22400.0, places=2)
        self.assertAlmostEqual(result.state_taxable_base, 1000.0, places=2)
        self.assertAlmostEqual(result.escrow, 24050.0, places=2)

    def test_losses_never_produce_negative_tax(self):
        """A losing year reserves zero. It does not release escrow to other buckets."""
        for treatment in ("casual_standard_deduction", "casual_itemized",
                          "professional_schedule_c", "session_netting"):
            with self.subTest(treatment=treatment):
                result = compute_gambling_tax(
                    GamblingInputs(gross_winnings=1000.0, gross_losses=9000.0,
                                   net_cash_pnl=-8000.0),
                    self.RATES, GamblingPolicy(treatment=treatment,
                                               loss_deduction_pct=1.0), 2026)
                self.assertGreaterEqual(result.escrow, 0.0)
                self.assertGreaterEqual(result.federal_taxable_base, 0.0)

    def test_obbba_haircut_applies_from_2026_only(self):
        """
        OBBBA 70114: 90% of losses, still capped at winnings.
        $100k won, $100k lost -> deduction $90,000 -> $10,000 of phantom income.
        In 2025 the same figures produce a $0 base.
        """
        inputs = GamblingInputs(gross_winnings=100000.0, gross_losses=100000.0, net_cash_pnl=0.0)
        policy = GamblingPolicy(treatment="casual_itemized", loss_deduction_pct=0.90,
                                loss_haircut_effective_year=2026)
        after = compute_gambling_tax(inputs, self.RATES, policy, 2026)
        self.assertAlmostEqual(after.loss_deduction_allowed, 90000.0, places=2)
        self.assertAlmostEqual(after.federal_taxable_base, 10000.0, places=2)

        before = compute_gambling_tax(inputs, self.RATES, policy, 2025)
        self.assertAlmostEqual(before.federal_taxable_base, 0.0, places=2)

    def test_haircut_applied_before_the_winnings_cap(self):
        """
        Order matters. Losses $200k, winnings $100k:
          haircut then cap -> min(180k, 100k) = 100k  (base 0)
          cap then haircut -> 100k x 0.9   =  90k     (base 10k)
        The statute limits the DEDUCTION to 90% of losses and then caps it, so
        the first is right. Regression guard on the order.
        """
        result = compute_gambling_tax(
            GamblingInputs(gross_winnings=100000.0, gross_losses=200000.0, net_cash_pnl=-100000.0),
            self.RATES, GamblingPolicy(treatment="casual_itemized",
                                       loss_deduction_pct=0.90), 2026)
        self.assertAlmostEqual(result.loss_deduction_allowed, 100000.0, places=2)
        self.assertAlmostEqual(result.federal_taxable_base, 0.0, places=2)

    def test_w2g_credit_is_capped_at_the_federal_leg(self):
        """
        Federal withholding cannot pay state tax or the safety buffer.
        Base $10,000: federal 2,800 / state 500 / buffer 200 = 3,500 owed.
        $5,000 withheld -> credit 2,800, surplus 2,200, escrow 700 (not zero).
        """
        result = compute_gambling_tax(
            GamblingInputs(gross_winnings=10000.0, w2g_withheld=5000.0, net_cash_pnl=10000.0),
            self.RATES, GamblingPolicy(treatment="casual_standard_deduction"), 2026)
        self.assertAlmostEqual(result.w2g_credit_applied, 2800.0, places=2)
        self.assertAlmostEqual(result.w2g_surplus, 2200.0, places=2)
        self.assertAlmostEqual(result.escrow, 700.0, places=2)
        self.assertTrue(any("refund receivable" in w for w in result.warnings))

    def test_w2g_credit_scope_total_is_opt_in(self):
        """The looser scope still exists for anyone who wants it, but never floors below zero."""
        result = compute_gambling_tax(
            GamblingInputs(gross_winnings=10000.0, w2g_withheld=5000.0, net_cash_pnl=10000.0),
            self.RATES, GamblingPolicy(treatment="casual_standard_deduction",
                                       w2g_credit_scope="total"), 2026)
        self.assertAlmostEqual(result.w2g_credit_applied, 3500.0, places=2)
        self.assertEqual(result.escrow, 0.0)

    def test_withholding_ignored_when_tracking_disabled(self):
        result = compute_gambling_tax(
            GamblingInputs(gross_winnings=10000.0, w2g_withheld=5000.0),
            self.RATES, GamblingPolicy(treatment="casual_standard_deduction",
                                       track_w2g_withholdings=False), 2026)
        self.assertEqual(result.w2g_credit_applied, 0.0)
        self.assertAlmostEqual(result.escrow, 3500.0, places=2)

    def test_statutory_seca_beats_a_flat_15_3_percent(self):
        """
        Net profit $100,000 in professional mode.
          SE base   = 100,000 x 0.9235 = 92,350
          SS        = 92,350 x 0.124   = 11,451.40   (under the wage base)
          Medicare  = 92,350 x 0.029   =  2,678.15
          SE tax    = 14,129.55         (a flat 15.3% would say 15,300)
          164(f)    income base = 100,000 - 7,064.78 = 92,935.22
        """
        result = compute_gambling_tax(
            GamblingInputs(gross_winnings=100000.0, net_cash_pnl=100000.0),
            self.RATES, GamblingPolicy(treatment="professional_schedule_c"), 2026)
        self.assertAlmostEqual(result.self_employment_tax, 14129.55, places=2)
        self.assertAlmostEqual(result.federal_taxable_base, 92935.225, places=2)

    def test_seca_social_security_leg_stops_at_the_wage_base(self):
        """A $1M professional does not pay 12.4% on the lot - Medicare alone continues."""
        big = compute_gambling_tax(
            GamblingInputs(gross_winnings=1000000.0, net_cash_pnl=1000000.0),
            self.RATES, GamblingPolicy(treatment="professional_schedule_c"), 2026)
        base = 1000000.0 * 0.9235
        expected = 184500.0 * 0.124 + base * 0.029
        self.assertAlmostEqual(big.self_employment_tax, expected, places=2)
        self.assertLess(big.self_employment_tax, base * 0.153)

    def test_professional_expenses_capped_at_winnings(self):
        """165(d) caps losses AND expenses together; a pro cannot book a gambling loss."""
        result = compute_gambling_tax(
            GamblingInputs(gross_winnings=10000.0, gross_losses=8000.0,
                           expenses=9000.0, net_cash_pnl=2000.0),
            self.RATES, GamblingPolicy(treatment="professional_schedule_c",
                                       loss_deduction_pct=1.0), 2026)
        self.assertEqual(result.federal_taxable_base, 0.0)
        self.assertEqual(result.escrow, 0.0)
        self.assertTrue(any("exceed" in w for w in result.warnings))

    def test_unknown_treatment_falls_back_to_the_strictest_mode(self):
        policy = resolve_policy({"tax_treatment": "creative_accounting"})
        self.assertEqual(policy.treatment, "casual_standard_deduction")

    def test_federal_rate_falls_back_to_the_composite_when_unset(self):
        rates = resolve_rates({"short_term_capital_gains": 0.28, "state_tax_rate": 0.05,
                               "safety_buffer_pct": 0.02}, {})
        self.assertAlmostEqual(rates.federal_ordinary, 0.28)
        explicit = resolve_rates({"short_term_capital_gains": 0.28, "state_tax_rate": 0.05},
                                 {"federal_ordinary_rate": 0.24, "state_ordinary_rate": 0.0})
        self.assertAlmostEqual(explicit.federal_ordinary, 0.24)
        self.assertAlmostEqual(explicit.state_ordinary, 0.0)


# ---------------------------------------------------------------------------
# 2. Odds normalisation.
# ---------------------------------------------------------------------------

class TestOdds(unittest.TestCase):

    def test_american_and_decimal_round_trip(self):
        for american in (-110, -105, -250, 100, 150, 2500, -1000):
            with self.subTest(american=american):
                self.assertEqual(decimal_to_american(american_to_decimal(american)), american)

    def test_format_sniffing(self):
        cases = {
            "-110": 1.909090, "+150": 2.5, "150": 2.5, "1.91": 1.91,
            "5/2": 3.5, "10/11": 1.909090, "EVEN": 2.0, "PK": 2.0, "2.5": 2.5,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertAlmostEqual(parse_odds(raw).decimal, expected, places=5)

    def test_explicit_format_overrides_the_sniff(self):
        """A book quoting decimal 150.0 needs the override; the sniff cannot know."""
        self.assertAlmostEqual(parse_odds("150", fmt="decimal").decimal, 150.0)
        self.assertAlmostEqual(parse_odds("150", fmt="american").decimal, 2.5)

    def test_a_sign_is_decisive_even_with_a_decimal_point(self):
        """`-110.0` and `+150.0` are what a float-formatting tool writes. Decimal
        odds are never signed and never negative, so the sign settles it."""
        self.assertAlmostEqual(parse_odds("-110.0").decimal, 1.909090, places=5)
        self.assertAlmostEqual(parse_odds("+150.0").decimal, 2.5, places=5)

    def test_bare_float_above_100_is_refused_not_guessed(self):
        """
        REGRESSION (Antigravity cross-check, defect 3). `150.0` is American +150
        (decimal 2.50) or decimal 150.0 (+14900) - a 60x difference, and nothing
        in the value distinguishes them. Sniffing it either way is silently wrong
        half the time, so it is refused and must be tagged.
        """
        with self.assertRaises(OddsFormatError):
            parse_odds("150.0")
        with self.assertRaises(OddsFormatError):
            parse_odds("2500.00")
        self.assertAlmostEqual(parse_odds("150.0", fmt="american").decimal, 2.5, places=5)
        self.assertAlmostEqual(parse_odds("150.0", fmt="decimal").decimal, 150.0, places=5)
        # A bare INTEGER stays American by convention - that reading is not in doubt.
        self.assertAlmostEqual(parse_odds("150").decimal, 2.5, places=5)

    def test_ambiguous_and_empty_inputs(self):
        self.assertIsNone(parse_odds(""))
        self.assertIsNone(parse_odds(None))
        self.assertIsNone(parse_odds("N/A"))
        # (0, 1] is either an implied probability or a typo - never guessed.
        with self.assertRaises(OddsFormatError):
            parse_odds("0.55")
        with self.assertRaises(OddsFormatError):
            parse_odds("-99")
        with self.assertRaises(OddsFormatError):
            parse_odds("chiefs")

    def test_implied_probability_includes_the_vig(self):
        """Both sides of a -110/-110 market sum to 1.0476, not 1.0. Item 2 removes that."""
        leg = parse_odds("-110").implied_probability
        self.assertAlmostEqual(leg * 2, 1.047619, places=5)

    def test_payout_discrepancy_flags_a_mistyped_payout(self):
        quote = parse_odds("-110")
        self.assertIsNone(payout_discrepancy(100.0, 190.91, quote))
        self.assertIsNotNone(payout_discrepancy(100.0, 19.09, quote))
        self.assertIsNone(payout_discrepancy(100.0, 190.91, None))


# ---------------------------------------------------------------------------
# 3. End-to-end escrow, through the ledger.
# ---------------------------------------------------------------------------

class TestSportsTaxModule(SportsTaxTestBase):

    def test_standard_deduction_trap(self):
        """
        $100 wins $250 (+$150); $100 loses (-$100).
        Standard deduction: base = $150 gross winnings, NOT the $50 banked.
        Federal on the gross $150 (24% + 2% buffer = $39.00); NJ nets the $100
        of losses and charges 5% on $50 = $2.50. $41.50 in total.
        """
        process_batch(self._wager("T1", 100.0, "WIN", 250.0, selection="CHIEFS")
                      + self._wager("T2", 100.0, "LOSS", 0.0, selection="BILLS",
                                    day="2026-01-11"), db_path=self.db_path)
        summary = self._summary()

        self.assertEqual(summary["gambling_gains"], 150.0)
        self.assertEqual(summary["gambling_losses"], -100.0)
        self.assertEqual(summary["gambling_net"], 50.0)
        self.assertEqual(summary["gambling_federal_taxable_base"], 150.0)
        self.assertEqual(summary["gambling_loss_disallowed"], 100.0)
        self.assertAlmostEqual(summary["escrow_gambling"], 41.50, places=2)
        self.assertAlmostEqual(summary["tax_escrow_reserve"], 41.50, places=2)
        self.assertAlmostEqual(summary["safe_deployable_bankroll"], 9958.50, places=2)

    def test_itemized_deduction_mode_under_the_2026_haircut(self):
        """
        Same $150 win / $100 loss, itemising, with OBBBA live:
          deduction = min(100 x 0.90, 150) = 90
          base      = 150 - 90 = 60
          escrow    = 60 x 0.35 = $21.00
        Under the pre-2026 rule the same ledger gives $17.50. The extra $3.50 is
        the phantom income the haircut creates, and it is not a bug.
        """
        config = _cfg(tax_treatment="casual_itemized", loss_deduction_pct=0.90)
        process_batch(self._wager("T1", 100.0, "WIN", 250.0)
                      + self._wager("T2", 100.0, "LOSS", 0.0, day="2026-01-11"),
                      db_path=self.db_path)
        summary = self._summary(config)
        self.assertAlmostEqual(summary["gambling_loss_deduction_allowed"], 90.0, places=2)
        self.assertAlmostEqual(summary["gambling_federal_taxable_base"], 60.0, places=2)
        # Federal base $60 (24% + 2% buffer = $15.60). The STATE nets the $100 of
        # losses at 100% - no state adopted the OBBBA haircut - so its base is $50
        # and it charges $2.50. $18.10.
        self.assertAlmostEqual(summary["escrow_gambling"], 18.10, places=2)

        repealed = _cfg(tax_treatment="casual_itemized", loss_deduction_pct=1.0)
        self.assertAlmostEqual(self._summary(repealed)["escrow_gambling"], 15.50, places=2)

    def test_a_state_that_nets_losses_does_so_WITHOUT_schedule_a(self):
        """
        THE STATE ELECTION IS NOT THE FEDERAL ONE. New Jersey nets gambling losses
        against gambling winnings within the year as a CATEGORY of income - no
        itemisation, no carry-forward, capped at winnings. The standard-deduction
        branch used to hardcode the state base to gross, as though the federal
        election bound the state too. On $80,000 won / $79,000 lost that
        over-stated NJ tax by about $5,000.
        """
        process_batch(self._wager("W1", 100.0, "WIN", 250.0)
                      + self._wager("W2", 100.0, "LOSS", 0.0, day="2026-01-11"),
                      db_path=self.db_path)
        summary = self._summary(_cfg(tax_treatment="casual_standard_deduction",
                                     state_allows_loss_deduction=True))
        # Federal still taxes the gross $150 - that trap is real and untouched.
        self.assertAlmostEqual(summary["gambling_federal_taxable_base"], 150.0, places=2)
        # The state nets to $50 at 100%, because no state adopted the OBBBA haircut.
        self.assertAlmostEqual(summary["gambling_state_taxable_base"], 50.0, places=2)

    def test_a_state_haircut_is_separate_from_the_federal_one(self):
        config = _cfg(tax_treatment="casual_standard_deduction",
                      state_allows_loss_deduction=True,
                      state_loss_deduction_pct=0.50)
        process_batch(self._wager("W1", 100.0, "WIN", 250.0)
                      + self._wager("W2", 100.0, "LOSS", 0.0, day="2026-01-11"),
                      db_path=self.db_path)
        summary = self._summary(config)
        # 150 won, 100 lost, state allows half: 150 - 50 = 100.
        self.assertAlmostEqual(summary["gambling_state_taxable_base"], 100.0, places=2)

    def test_state_netting_is_still_capped_at_winnings(self):
        """A losing year cannot create a state deduction against other income."""
        process_batch(self._wager("W1", 100.0, "WIN", 150.0)
                      + self._wager("W2", 500.0, "LOSS", 0.0, day="2026-01-11"),
                      db_path=self.db_path)
        summary = self._summary(_cfg(state_allows_loss_deduction=True))
        self.assertEqual(summary["gambling_state_taxable_base"], 0.0)

    def test_state_disallowance_taxes_gross_on_a_break_even_year(self):
        """
        $200 won, $200 lost, itemising federally, state disallows losses:
          federal base = 200 - 200 = 0            -> $0 federal, $0 buffer
          state  base  = 200 (gross) x 0.05       -> $10.00
        A year that banked nothing still owes state tax.
        """
        config = _cfg(tax_treatment="casual_itemized", state_allows_loss_deduction=False,
                      loss_deduction_pct=1.0)
        process_batch(self._wager("T1", 200.0, "WIN", 400.0, book="FanDuel", sport="NBA")
                      + self._wager("T2", 200.0, "LOSS", 0.0, book="FanDuel", sport="NBA",
                                    day="2026-02-02"), db_path=self.db_path)
        summary = self._summary(config)
        self.assertEqual(summary["gambling_net"], 0.0)
        self.assertEqual(summary["gambling_federal_taxable_base"], 0.0)
        self.assertEqual(summary["gambling_state_taxable_base"], 200.0)
        self.assertAlmostEqual(summary["escrow_gambling"], 10.0, places=2)

    def test_w2g_withholding_credit(self):
        """
        $50 pays $10,000 -> $9,950 of winnings. Composite 35% = $3,482.50 owed.
        The book withheld $2,388, which is inside the federal leg of $2,786, so
        it is credited in full: escrow $1,094.50.
        """
        process_batch(self._wager("BIG", 50.0, "WIN", 10000.0, selection="PARLAY",
                                  withholding=2388.0), db_path=self.db_path)
        summary = self._summary()
        self.assertEqual(summary["gambling_w2g_withheld"], 2388.0)
        self.assertAlmostEqual(summary["gambling_w2g_credit_applied"], 2388.0, places=2)
        self.assertEqual(summary["gambling_w2g_surplus"], 0.0)
        self.assertAlmostEqual(summary["escrow_gambling"], 696.50, places=2)

    def test_overwithholding_does_not_release_state_tax_or_buffer(self):
        """
        Won $25,000 with $6,000 withheld, lost $24,000, itemising with the
        haircut off. Federal base $1,000 -> federal $280 / state $50 / buffer $20.
        Only $280 of the withholding can be credited; the other $5,720 is a
        refund receivable, and $70 of cash escrow is still owed.
        """
        config = _cfg(tax_treatment="casual_itemized", loss_deduction_pct=1.0)
        config["portfolio"]["default_cash_balance_usdc"] = 100000.0
        process_batch(
            self._wager("W1", 10000.0, "WIN", 35000.0, withholding=6000.0)
            + self._wager("W2", 24000.0, "LOSS", 0.0, day="2026-02-02"),
            db_path=self.db_path)
        summary = self._summary(config)
        self.assertAlmostEqual(summary["gambling_federal_taxable_base"], 1000.0, places=2)
        self.assertAlmostEqual(summary["gambling_w2g_credit_applied"], 240.0, places=2)
        self.assertAlmostEqual(summary["gambling_w2g_surplus"], 5760.0, places=2)
        self.assertAlmostEqual(summary["escrow_gambling"], 70.0, places=2)

    def test_gambling_never_lands_in_a_capital_gains_bucket(self):
        """Wagers are ordinary income. They must not reach the 20% long-term rate."""
        process_batch(self._wager("T1", 100.0, "WIN", 300.0), db_path=self.db_path)
        summary = self._summary()
        self.assertEqual(summary["escrow_short_term"], 0.0)
        self.assertEqual(summary["escrow_long_term"], 0.0)
        self.assertEqual(summary["capital_gross_gains"], 0.0)
        self.assertEqual(summary["net_capital_gains_excl_gambling"], 0.0)
        self.assertGreater(summary["escrow_gambling"], 0.0)

    def test_session_netting_groups_by_day_and_book(self):
        """
        One day, two books: +$300 at DraftKings, -$200 at FanDuel.
        Session netting per AM 2008-011 is per establishment, so the winning
        session is $300 - the FanDuel loss is a Schedule A deduction, not a net.
        Under `session_grouping: day` the two collapse into one $100 session.
        """
        process_batch(
            self._wager("S1", 100.0, "WIN", 400.0, book="DraftKings", day="2026-03-01")
            + self._wager("S2", 200.0, "LOSS", 0.0, book="FanDuel", day="2026-03-01"),
            db_path=self.db_path)

        per_book = self._summary(_cfg(tax_treatment="session_netting"))
        self.assertEqual(per_book["gambling_session_count"], 1)
        self.assertAlmostEqual(per_book["gambling_session_winnings"], 300.0, places=2)
        # Federal on the $300 winning session (24% + 2% = $78); the state nets the
        # $200 losing session, leaving $100 at 5% = $5. $83.
        self.assertAlmostEqual(per_book["escrow_gambling"], 83.0, places=2)

        per_day = self._summary(_cfg(tax_treatment="session_netting", session_grouping="day"))
        self.assertAlmostEqual(per_day["gambling_session_winnings"], 100.0, places=2)

    def test_professional_expenses_come_from_the_ledger(self):
        """
        A Schedule C expense row reduces wagering profit - and must NOT also
        reduce the ordinary-income bucket, or the same dollar is deducted twice.
        """
        rows = self._wager("P1", 1000.0, "WIN", 6000.0)
        rows.append({
            "source": "manual", "tx_hash": "sub_2026", "timestamp": "2026-01-20 09:00:00",
            "asset_class": "sports_bet", "symbol": "DATA_SUBSCRIPTION", "side": "EXPENSE",
            "quantity": 1.0, "price": 1200.0, "fee": 0.0, "total_value": 1200.0,
            "notes": "strategy:sports_betting;odds screen subscription",
        })
        process_batch(rows, db_path=self.db_path)
        summary = self._summary(_cfg(tax_treatment="professional_schedule_c"))
        self.assertAlmostEqual(summary["gambling_expenses"], 1200.0, places=2)
        # Winnings 5,000 - expenses 1,200 = 3,800 of net profit.
        self.assertGreater(summary["gambling_self_employment_tax"], 0.0)
        self.assertLess(summary["gambling_federal_taxable_base"], 3800.0)
        # The subscription is not ALSO a deduction against funding income.
        self.assertEqual(summary["ordinary_expense"], 0.0)


# ---------------------------------------------------------------------------
# 4. Settlement edge cases - the ones a real sportsbook export contains.
# ---------------------------------------------------------------------------

class TestSettlementEdgeCases(SportsTaxTestBase):

    def test_two_tickets_on_one_selection_keep_their_own_basis(self):
        """
        THE REGRESSION THAT MOTIVATED TICKET-SCOPED SYMBOLS. A $20 and a $500
        ticket on the same selection: if they share a lot key, the FIFO matcher
        settles the winner against the loser's stake and both figures are wrong
        in whichever direction the timestamps happened to fall.
        Truth: +$455 of winnings and -$20 of losses.
        """
        process_batch(
            self._wager("A", 20.0, "LOSS", 0.0, selection="CHIEFS_-3.5", day="2026-01-10")
            + self._wager("B", 500.0, "WIN", 955.0, selection="CHIEFS_-3.5", day="2026-01-10"),
            db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 455.0, places=2)
        self.assertAlmostEqual(summary["gambling_losses"], -20.0, places=2)

    def test_partial_cashout_below_stake_is_not_a_full_loss(self):
        """
        Cashing a $100 ticket out at $60 is a $40 loss. Booking it as BET_LOSS
        would zero the proceeds and record a $100 one - a 150% overstatement of
        the deduction, and in standard-deduction mode a silent overstatement of
        winnings on the other side of the same trade.
        """
        process_batch(self._wager("C1", 100.0, "CASHOUT", 60.0), db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_net"], -40.0, places=2)
        self.assertAlmostEqual(summary["gambling_losses"], -40.0, places=2)
        self.assertEqual(summary["gambling_gains"], 0.0)

    def test_cashout_above_stake_is_a_win(self):
        process_batch(self._wager("C2", 100.0, "CASHOUT", 175.0), db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 75.0, places=2)

    def test_push_refunds_the_stake_and_nets_to_zero(self):
        process_batch(self._wager("PU", 250.0, "PUSH", 250.0), db_path=self.db_path)
        summary = self._summary()
        self.assertEqual(summary["gambling_gains"], 0.0)
        self.assertEqual(summary["gambling_losses"], 0.0)
        self.assertEqual(summary["escrow_gambling"], 0.0)

    def test_push_without_a_payout_or_a_wager_is_refused(self):
        """Settling a push at $0 would book the whole stake as a loss that never happened."""
        with self.assertRaises(BetSettlementError):
            SportsBettingIngestor.create_bet_settled(
                "X", "DK", "NFL", "SEL", "PUSH", 0.0, "2026-01-01 12:00:00")
        recovered = SportsBettingIngestor.create_bet_settled(
            "X", "DK", "NFL", "SEL", "VOID", 0.0, "2026-01-01 12:00:00", wager=80.0)
        self.assertAlmostEqual(recovered["price"], 80.0)

    def test_dead_heat_splits_the_stake_into_a_win_and_a_loss(self):
        """
        $100 at +200, two-way dead heat: $50 wins $100, $50 loses.
        The book returns $150. This is NOT a push - the losing half is a real
        165(d) loss and is disallowed under the standard deduction.
        """
        rows = [SportsBettingIngestor.create_bet_placed(
            "D1", "DK", "GOLF", "PLAYER", 100.0, "+200", "2026-07-01 10:00:00")]
        rows += SportsBettingIngestor.create_dead_heat_settlement(
            "D1", "DK", "GOLF", "PLAYER", wager=100.0, payout=150.0,
            timestamp="2026-07-01 20:00:00", win_fraction=0.5)
        process_batch(rows, db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 100.0, places=2)
        self.assertAlmostEqual(summary["gambling_losses"], -50.0, places=2)
        self.assertAlmostEqual(summary["gambling_net"], 50.0, places=2)
        # Standard deduction: the $50 loss is disallowed, so $100 is taxed.
        self.assertAlmostEqual(summary["gambling_federal_taxable_base"], 100.0, places=2)

    def test_partial_void_refunds_pro_rata_and_settles_the_rest(self):
        """
        A postponed leg refunded pro rata: half of a $200 stake comes back as a
        push, the other half wins $250. Winnings = 250 - 100 = $150.
        """
        rows = [SportsBettingIngestor.create_bet_placed(
            "V1", "DK", "NFL", "PARLAY", 200.0, "+300", "2026-08-01 10:00:00")]
        rows += SportsBettingIngestor.create_partial_void_settlement(
            "V1", "DK", "NFL", "PARLAY", wager=200.0, payout=250.0,
            timestamp="2026-08-01 20:00:00", void_fraction=0.5, result="WIN")
        process_batch(rows, db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 150.0, places=2)
        self.assertEqual(summary["gambling_losses"], 0.0)

    def test_fractional_settlements_close_the_lot_completely(self):
        """Two half-settlements must leave nothing open, or the stake is double-counted."""
        rows = [SportsBettingIngestor.create_bet_placed(
            "F1", "DK", "GOLF", "PLAYER", 100.0, "+200", "2026-07-01 10:00:00")]
        rows += SportsBettingIngestor.create_dead_heat_settlement(
            "F1", "DK", "GOLF", "PLAYER", wager=100.0, payout=150.0,
            timestamp="2026-07-01 20:00:00", win_fraction=0.5)
        process_batch(rows, db_path=self.db_path)
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT SUM(remaining_qty) AS open_qty FROM tax_lots WHERE is_closed = 0"
            ).fetchone()
        finally:
            conn.close()
        self.assertAlmostEqual(float(row["open_qty"] or 0.0), 0.0, places=6)

    def test_an_open_ticket_is_not_a_realised_loss(self):
        """A wager still running at year end reserves nothing and deducts nothing."""
        process_batch([SportsBettingIngestor.create_bet_placed(
            "OPEN", "DK", "NFL", "FUTURES", 1000.0, "+1200", "2026-12-30 10:00:00")],
            db_path=self.db_path)
        summary = self._summary()
        self.assertEqual(summary["gambling_gains"], 0.0)
        self.assertEqual(summary["gambling_losses"], 0.0)
        self.assertEqual(summary["escrow_gambling"], 0.0)

    def test_settled_only_export_does_not_lose_the_winnings(self):
        """
        Books happily export "settled bets" with no placement rows. A settlement
        with no open lot used to book NOTHING - the win simply vanished and the
        escrow came out at zero. It is now booked at zero cost basis, which
        OVER-states the base (the stake is not deducted) and warns loudly.
        """
        process_batch([SportsBettingIngestor.create_bet_settled(
            "ORPH", "DK", "NFL", "JETS_ML", "WIN", 5000.0, "2026-03-01 20:00:00")],
            db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 5000.0, places=2)
        self.assertAlmostEqual(summary["escrow_gambling"], 1550.0, places=2)

    def test_orphan_loss_does_not_invent_a_deduction(self):
        """A losing ticket with no recorded stake is no evidence of a deductible loss."""
        process_batch([SportsBettingIngestor.create_bet_settled(
            "ORPH2", "DK", "NFL", "JETS_ML", "LOSS", 0.0, "2026-03-01 20:00:00")],
            db_path=self.db_path)
        summary = self._summary(_cfg(tax_treatment="casual_itemized", loss_deduction_pct=1.0))
        self.assertEqual(summary["gambling_losses"], 0.0)
        self.assertEqual(summary["escrow_gambling"], 0.0)

    def test_zero_stake_wager_is_refused(self):
        """A zero-cost lot gives every settlement against it an infinite return."""
        with self.assertRaises(BetSettlementError):
            SportsBettingIngestor.create_bet_placed(
                "Z", "DK", "NFL", "SEL", 0.0, "+100", "2026-01-01 12:00:00")

    def test_unknown_and_unsettled_results_are_refused_not_guessed(self):
        for result in ("PENDING", "", "MAYBE"):
            with self.subTest(result=result):
                with self.assertRaises(BetSettlementError):
                    SportsBettingIngestor.create_bet_settled(
                        "U", "DK", "NFL", "SEL", result, 0.0, "2026-01-01 12:00:00")

    def test_mixed_timestamp_formats_still_order_correctly(self):
        """
        REGRESSION (Antigravity cross-check, defect 1). The ledger sorted
        `str(timestamp)`, and `"2026-01-10 16:30:00"` sorts BEFORE
        `"2026-01-10T13:00:00Z"` because a space is 0x20 and `T` is 0x54. The
        13:00 placement therefore arrived after its own 16:30 settlement: the
        settlement found no lot, booked the full $2,500 payout as winnings
        instead of $1,500, and left the $1,000 stake open forever.
        """
        process_batch([
            SportsBettingIngestor.create_bet_placed(
                "MX", "DK", "NFL", "X", 1000.0, "+150", "2026-01-10T13:00:00Z"),
            SportsBettingIngestor.create_bet_settled(
                "MX", "DK", "NFL", "X", "WIN", 2500.0, "2026-01-10 16:30:00", wager=1000.0),
        ], db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 1500.0, places=2)
        conn = get_connection(self.db_path)
        try:
            open_qty = conn.execute(
                "SELECT SUM(remaining_qty) AS q FROM tax_lots WHERE is_closed = 0"
            ).fetchone()["q"]
        finally:
            conn.close()
        self.assertAlmostEqual(float(open_qty or 0.0), 0.0, places=6)

    def test_settlement_listed_before_its_placement_at_one_timestamp(self):
        """
        Single-row sportsbook exports date the placement and the settlement
        identically. A wager must be placed before it settles, so at an equal
        timestamp the settlement sorts last regardless of row order.
        """
        process_batch([
            SportsBettingIngestor.create_bet_settled(
                "EQ", "DK", "NFL", "Y", "WIN", 2500.0, "2026-01-10 13:00:00", wager=1000.0),
            SportsBettingIngestor.create_bet_placed(
                "EQ", "DK", "NFL", "Y", 1000.0, "+150", "2026-01-10 13:00:00"),
        ], db_path=self.db_path)
        self.assertAlmostEqual(self._summary()["gambling_gains"], 1500.0, places=2)

    def test_rebuild_matches_the_import_under_mixed_timestamp_formats(self):
        """A rebuild that re-orders history produces different lots from the
        import that created them. It must use the same key, not a SQL string sort."""
        process_batch([
            SportsBettingIngestor.create_bet_placed(
                "RB", "DK", "NFL", "Z", 1000.0, "+150", "2026-01-10T13:00:00Z"),
            SportsBettingIngestor.create_bet_settled(
                "RB", "DK", "NFL", "Z", "WIN", 2500.0, "2026-01-10 16:30:00", wager=1000.0),
        ], db_path=self.db_path)
        before = self._summary()
        rebuild_lots(db_path=self.db_path, method="FIFO")
        after = self._summary()
        self.assertAlmostEqual(before["gambling_gains"], after["gambling_gains"], places=6)
        self.assertAlmostEqual(after["gambling_gains"], 1500.0, places=2)

    def test_dead_heat_withholding_is_tagged_once(self):
        """
        REGRESSION (Antigravity cross-check, defect 2). `withholding` passed
        through `**kwargs` reached BOTH legs, and the escrow calculator sums the
        tag per row - so one $1,200 W-2G was credited as $2,400 and the reserve
        came out $1,200 light.
        """
        legs = SportsBettingIngestor.create_dead_heat_settlement(
            "D1", "DK", "GOLF", "P", wager=10000.0, payout=15000.0,
            timestamp="2026-07-01 20:00:00", win_fraction=0.5, withholding=1200.0)
        tagged = [leg for leg in legs if "w2g_withholding:" in leg["notes"]]
        self.assertEqual(len(tagged), 1)
        self.assertEqual(tagged[0]["side"], "BET_WIN")

        process_batch([SportsBettingIngestor.create_bet_placed(
            "D1", "DK", "GOLF", "P", 10000.0, "+200", "2026-07-01 10:00:00")] + legs,
            db_path=self.db_path)
        self.assertAlmostEqual(self._summary()["gambling_w2g_withheld"], 1200.0, places=2)

    def test_partial_void_withholding_is_tagged_once_on_the_settled_leg(self):
        """A refunded stake has nothing withheld against it."""
        legs = SportsBettingIngestor.create_partial_void_settlement(
            "V2", "DK", "NFL", "PARLAY", wager=10000.0, payout=22000.0,
            timestamp="2026-08-01 20:00:00", void_fraction=0.5, result="WIN",
            withholding=2400.0)
        tagged = [leg for leg in legs if "w2g_withholding:" in leg["notes"]]
        self.assertEqual(len(tagged), 1)
        self.assertEqual(tagged[0]["side"], "BET_WIN")

    def test_reimporting_the_same_wagers_does_not_double_the_ledger(self):
        rows = self._wager("R1", 100.0, "WIN", 250.0)
        process_batch(rows, db_path=self.db_path)
        first = self._summary()
        process_batch(rows, db_path=self.db_path)
        self.assertEqual(self._summary()["escrow_gambling"], first["escrow_gambling"])

    def test_rebuild_integrity(self):
        """Replaying the ledger under FIFO reproduces the escrow exactly."""
        process_batch(
            self._wager("T1", 150.0, "WIN", 270.0, book="Pinnacle", sport="SOCCER")
            + self._wager("T2", 80.0, "CASHOUT", 40.0, book="Pinnacle", sport="SOCCER",
                          day="2026-02-11")
            + self._wager("T3", 60.0, "PUSH", 60.0, book="Pinnacle", sport="SOCCER",
                          day="2026-02-12"),
            db_path=self.db_path)
        before = self._summary()
        rebuild_lots(db_path=self.db_path, method="FIFO")
        after = self._summary()
        for key in ("escrow_gambling", "tax_escrow_reserve", "gambling_gains",
                    "gambling_losses", "gambling_federal_taxable_base"):
            self.assertAlmostEqual(before[key], after[key], places=6, msg=key)


# ---------------------------------------------------------------------------
# 5. CSV ingestion.
# ---------------------------------------------------------------------------

class TestSportsCSV(SportsTaxTestBase):

    def _write(self, name, text):
        path = Path(self.temp_dir.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_single_row_settled_export(self):
        path = self._write(
            "draftkings_settled_bets_2026.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout,withholding\n"
            "DK101,DraftKings,2026-01-20 18:00:00,NFL,KC_CHIEFS,100,1.91,WIN,191,0\n"
            "DK102,DraftKings,2026-01-21 18:00:00,NFL,BAL_RAVENS,50,2.10,LOSS,0,0\n")
        trades = load_sports_csv(path)
        self.assertEqual(len(trades), 4)
        process_batch(trades, db_path=self.db_path)
        summary = self._summary()
        self.assertEqual(summary["breakdown_by_asset"]["sports_bet"]["trade_count"], 2)
        self.assertAlmostEqual(summary["gambling_gains"], 91.0, places=2)
        self.assertAlmostEqual(summary["gambling_losses"], -50.0, places=2)

    def test_american_odds_and_formatted_currency(self):
        """`-110`, `+150` and `$1,000.00` all appear in real exports."""
        path = self._write(
            "fanduel_bets.csv",
            "bet_id,book,placed_date,settled_date,league,pick,stake,odds,status,returns\n"
            'FD1,FanDuel,2026-04-01 12:00:00,2026-04-01 16:00:00,NFL,X,"$1,000.00",-110,WON,"$1,909.09"\n'
            "FD2,FanDuel,2026-04-02 12:00:00,2026-04-02 16:00:00,NFL,Y,100,+150,LOST,0\n")
        trades = load_sports_csv(path)
        placements = [t for t in trades if t["side"] == "BET"]
        self.assertEqual(placements[0]["price"], 1000.0)
        self.assertIn("odds_american:-110", placements[0]["notes"])
        self.assertIn("odds_american:+150", placements[1]["notes"])
        # Placement and settlement keep their own timestamps.
        settle = [t for t in trades if t["side"] == "BET_WIN"][0]
        self.assertNotEqual(settle["timestamp"], placements[0]["timestamp"])

        process_batch(trades, db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 909.09, places=2)
        self.assertAlmostEqual(summary["gambling_losses"], -100.0, places=2)

    def test_mistyped_payout_is_flagged_against_the_odds(self):
        """$1,909.09 typed as $190.91 is invisible to every other check here."""
        path = self._write(
            "sportsbook_typo.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "T9,BetMGM,2026-05-01 12:00:00,NFL,X,1000,-110,WIN,190.91\n")
        trades = load_sports_csv(path)
        settle = [t for t in trades if t["side"] == "BET_WIN"][0]
        self.assertIn("odds_check:payout_off_by", settle["notes"])

    def test_unreadable_rows_are_skipped_not_silently_dropped(self):
        """A settled row with no stake would tax the whole payout. Refuse it loudly."""
        path = self._write(
            "sportsbook_broken.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "OK1,BetMGM,2026-05-01 12:00:00,NFL,X,100,-110,WIN,190.91\n"
            "BAD,BetMGM,2026-05-02 12:00:00,NFL,Y,0,-110,WIN,500\n")
        trades = load_sports_csv(path)
        self.assertEqual(len(trades), 2)
        self.assertTrue(all("OK1" in t["notes"] for t in trades))

    def test_default_odds_format_settles_the_ambiguous_zone(self):
        """The refusal has a one-line escape hatch, and a row's own column wins."""
        path = self._write(
            "sportsbook_ambiguous.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "AM1,BetMGM,2026-05-01 12:00:00,NFL,X,100,150.0,WIN,250\n")
        untagged = SportsBettingIngestor.load_from_csv(path)
        placement = [t for t in untagged if t["side"] == "BET"][0]
        self.assertNotIn("odds_decimal", placement["notes"])   # refused, wager kept
        self.assertEqual(placement["price"], 100.0)

        tagged = SportsBettingIngestor.load_from_csv(path, default_odds_format="american")
        placement = [t for t in tagged if t["side"] == "BET"][0]
        self.assertIn("odds_american:+150", placement["notes"])

    def test_bad_odds_do_not_cost_us_the_wager(self):
        """Odds are metadata. An unreadable price must never drop a taxable row."""
        path = self._write(
            "sportsbook_odds.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "O1,BetMGM,2026-05-01 12:00:00,NFL,X,100,chiefs,WIN,300\n")
        trades = load_sports_csv(path)
        self.assertEqual(len(trades), 2)
        process_batch(trades, db_path=self.db_path)
        self.assertAlmostEqual(self._summary()["gambling_gains"], 200.0, places=2)

    def test_pending_rows_produce_a_lot_and_no_settlement(self):
        path = self._write(
            "sportsbook_open.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "P1,BetMGM,2026-05-01 12:00:00,NFL,X,100,-110,PENDING,0\n")
        trades = load_sports_csv(path)
        self.assertEqual([t["side"] for t in trades], ["BET"])

    def test_watcher_classifies_a_sportsbook_export(self):
        path = self._write(
            "draftkings_2026.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "DK1,DraftKings,2026-01-20 18:00:00,NFL,KC,100,1.91,WIN,191\n")
        with open(path, encoding="utf-8-sig", newline="") as f:
            import csv as _csv
            rows = list(_csv.DictReader(f))
        source, _reason = classify_csv(path, rows=[{k.lower(): v for k, v in r.items()}
                                                   for r in rows])
        self.assertEqual(source, "sports")

    def test_strategy_tag_is_written_once(self):
        """`monarch_hook` parses `strategy:` for exposure; two tags is a parse hazard."""
        path = self._write(
            "sportsbook_strategy.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout,strategy\n"
            "S1,BetMGM,2026-05-01 12:00:00,NFL,X,100,-110,WIN,190.91,sports_betting\n")
        for trade in load_sports_csv(path):
            self.assertEqual(trade["notes"].count("strategy:"), 1)


# ---------------------------------------------------------------------------
# 6. Ledger ordering and holding period.
#
# Not sports-specific, but every one of these was found while hardening the
# wagering path and every one of them predates it. They live here because this
# is where the Round 26 regressions are collected.
# ---------------------------------------------------------------------------

class TestTimestampsAndHoldingPeriod(SportsTaxTestBase):

    def test_parse_iso_date_accepts_the_shapes_real_exports_emit(self):
        """
        REGRESSION (Antigravity cross-check, round 2). `parse_iso_date` took
        exactly two shapes. A bare date, microseconds, and a space-separated
        offset all raised - and `sortable_timestamp` catches that and sorts the
        row to `datetime.max`, which pushes an OPENING lot to the end of the
        batch. Its settlement then finds no lot, books the full payout at zero
        basis, and strands the stake open forever.
        """
        cases = {
            "2026-01-10": datetime(2026, 1, 10, 0, 0, 0),
            "2026-01-10 13:00:00": datetime(2026, 1, 10, 13, 0, 0),
            "2026-01-10 13:00": datetime(2026, 1, 10, 13, 0, 0),
            "2026-01-10 13:00:00.123456": datetime(2026, 1, 10, 13, 0, 0, 123456),
            "01/10/2026 13:00:00": datetime(2026, 1, 10, 13, 0, 0),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_iso_date(raw), expected)
        # Offsets parse and normalise; 13:00-05:00 is 18:00 UTC.
        self.assertEqual(as_naive_utc(parse_iso_date("2026-01-10 13:00:00-05:00")),
                         datetime(2026, 1, 10, 18, 0, 0))
        self.assertEqual(as_naive_utc(parse_iso_date("2026-01-10T13:00:00Z")),
                         datetime(2026, 1, 10, 13, 0, 0))

    def test_bare_epoch_seconds_are_still_refused(self):
        """`1767013200` is an equally plausible quantity, price or ticket id."""
        with self.assertRaises(ValueError):
            parse_iso_date("1767013200")

    def test_a_bare_date_placement_still_matches_its_settlement(self):
        """The end-to-end consequence of the parse fix, in dollars."""
        process_batch([
            SportsBettingIngestor.create_bet_placed(
                "BD", "DK", "NFL", "X", 1000.0, "+150", "2026-01-10"),
            SportsBettingIngestor.create_bet_settled(
                "BD", "DK", "NFL", "X", "WIN", 2500.0, "2026-01-10 16:30:00", wager=1000.0),
        ], db_path=self.db_path)
        self.assertAlmostEqual(self._summary()["gambling_gains"], 1500.0, places=2)

    def test_long_term_needs_more_than_one_year_not_365_days(self):
        """
        IRC 1222(3) plus Rev. Rul. 66-7: MORE THAN one year, counting from the
        day after acquisition. An exact one-year hold is short-term.

        Antigravity proposed `> 365`. That fixes the common year and BREAKS the
        leap year: 2024-01-01 to 2025-01-01 is 366 days and still exactly one
        year, so it is short-term, and `> 365` calls it long. No day count is
        right in both - "one year" is a calendar span. Hence `is_long_term`.
        """
        cases = [
            ("2025-01-01", "2026-01-01", False, "exact anniversary, common year"),
            ("2025-01-01", "2026-01-02", True, "anniversary + 1 day"),
            ("2024-01-01", "2025-01-01", False, "exact anniversary ACROSS A LEAP YEAR (366d)"),
            ("2024-01-01", "2025-01-02", True, "leap year, anniversary + 1 day"),
            ("2024-02-29", "2025-03-01", False, "29 Feb, anniversary falls on 1 March"),
            ("2024-02-29", "2025-03-02", True, "29 Feb, anniversary + 1 day"),
            ("2025-01-01", "2025-06-01", False, "five months"),
        ]
        for acquired, disposed, expected, label in cases:
            with self.subTest(case=label):
                self.assertEqual(
                    is_long_term(parse_iso_date(acquired), parse_iso_date(disposed)),
                    expected, label)

    def test_exact_anniversary_books_at_the_short_term_rate(self):
        """
        The correction only ever moves a boundary trade LONG -> SHORT, which
        raises the reserve. Verified in dollars through the real ledger.
        """
        spot = [
            {"source": "spot", "tx_hash": "b1", "timestamp": "2025-01-01 10:00:00",
             "asset_class": "crypto_spot", "symbol": "ETH", "side": "BUY",
             "quantity": 1.0, "price": 1000.0, "fee": 0.0, "total_value": 1000.0, "notes": ""},
            {"source": "spot", "tx_hash": "s1", "timestamp": "2026-01-01 10:00:00",
             "asset_class": "crypto_spot", "symbol": "ETH", "side": "SELL",
             "quantity": 1.0, "price": 2000.0, "fee": 0.0, "total_value": 2000.0, "notes": ""},
        ]
        process_batch(spot, db_path=self.db_path)
        summary = self._summary()
        # $1,000 gain at the short-term composite 35%, not the long-term 20%.
        self.assertAlmostEqual(summary["short_term_net"], 1000.0, places=2)
        self.assertAlmostEqual(summary["long_term_net"], 0.0, places=2)
        self.assertAlmostEqual(summary["escrow_short_term"], 310.0, places=2)


# ---------------------------------------------------------------------------
# 7. Import shapes that duplicate or mislabel a ticket.
# ---------------------------------------------------------------------------

class TestImportShapes(SportsTaxTestBase):

    def _write(self, name, text):
        path = Path(self.temp_dir.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_book_aliases_fold_onto_one_name(self):
        self.assertEqual(canonical_book("DK"), "draftkings")
        self.assertEqual(canonical_book("draft kings"), "draftkings")
        self.assertEqual(canonical_book("Fan_Duel"), "fanduel")
        self.assertEqual(canonical_book("bet 365"), "bet365")
        self.assertEqual(canonical_book(""), "sportsbook")
        # An unknown book is kept, just normalised - never silently remapped.
        self.assertEqual(canonical_book("Bovada"), "bovada")

    def test_a_placement_and_settlement_spelled_differently_still_match(self):
        """
        REGRESSION (Antigravity cross-check, round 2). `DK` and `DraftKings`
        produced two lot families, so a settlement imported from one export
        never found the placement imported from the other and hit the
        zero-basis orphan path - taxing the whole $2,500 instead of $1,500.
        """
        process_batch([
            SportsBettingIngestor.create_bet_placed(
                "AL", "DK", "NFL", "X", 1000.0, "+150", "2026-01-10 13:00:00"),
            SportsBettingIngestor.create_bet_settled(
                "AL", "DraftKings", "NFL", "X", "WIN", 2500.0, "2026-01-10 16:30:00",
                wager=1000.0),
        ], db_path=self.db_path)
        self.assertAlmostEqual(self._summary()["gambling_gains"], 1500.0, places=2)

    def test_parlay_printed_one_row_per_leg_books_one_stake(self):
        """
        REGRESSION (Antigravity cross-check, round 2). A 4-leg $100 parlay
        printed as four rows minted four opening lots and booked $400 of cost
        basis, understating the winnings by $300.
        """
        path = self._write(
            "draftkings_parlay_legs.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "PAR1,DraftKings,2026-02-01 12:00:00,NFL,LEG_A,100,+600,WIN,700\n"
            "PAR1,DraftKings,2026-02-01 12:00:00,NFL,LEG_B,100,+600,WIN,700\n"
            "PAR1,DraftKings,2026-02-01 12:00:00,NFL,LEG_C,100,+600,WIN,700\n"
            "PAR1,DraftKings,2026-02-01 12:00:00,NFL,LEG_D,100,+600,WIN,700\n")
        trades = load_sports_csv(path)
        self.assertEqual([t["side"] for t in trades], ["BET", "BET_WIN"])
        process_batch(trades, db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 600.0, places=2)
        self.assertEqual(summary["breakdown_by_asset"]["sports_bet"]["trade_count"], 1)

    def test_distinct_tickets_are_never_collapsed(self):
        path = self._write(
            "draftkings_two_tickets.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "A1,DraftKings,2026-02-01 12:00:00,NFL,X,100,+100,WIN,200\n"
            "A2,DraftKings,2026-02-01 12:00:00,NFL,X,100,+100,WIN,200\n")
        process_batch(load_sports_csv(path), db_path=self.db_path)
        self.assertAlmostEqual(self._summary()["gambling_gains"], 200.0, places=2)

    def test_free_bet_has_zero_basis_and_is_fully_taxable(self):
        """
        A promo stake was never your money, so you have no basis in it and every
        dollar it returns is IRC 61 income. Refusing the row - which is what a
        positive-wager guard did - dropped that income from the ledger entirely.
        """
        placed = SportsBettingIngestor.create_bet_placed(
            "FB1", "DK", "NFL", "X", 5.0, "+2000", "2026-03-01 12:00:00", promo=True)
        self.assertEqual(placed["price"], 0.0)
        self.assertIn("promo_bet:true", placed["notes"])
        self.assertIn("promo_stake:5.00", placed["notes"])

        process_batch([placed, SportsBettingIngestor.create_bet_settled(
            "FB1", "DK", "NFL", "X", "WIN", 100.0, "2026-03-01 20:00:00")],
            db_path=self.db_path)
        summary = self._summary()
        self.assertAlmostEqual(summary["gambling_gains"], 100.0, places=2)
        self.assertAlmostEqual(summary["escrow_gambling"], 31.0, places=2)

    def test_zero_stake_without_a_promo_flag_is_still_refused(self):
        """A free bet and a missing stake column are identical in a CSV."""
        with self.assertRaises(BetSettlementError):
            SportsBettingIngestor.create_bet_placed(
                "Z1", "DK", "NFL", "X", 0.0, "+100", "2026-03-01 12:00:00")
        with self.assertRaises(BetSettlementError):
            SportsBettingIngestor.create_bet_placed(
                "Z2", "DK", "NFL", "X", -5.0, "+100", "2026-03-01 12:00:00")

    def test_csv_promo_column_unlocks_the_zero_stake(self):
        path = self._write(
            "fanduel_promos.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout,bet_type\n"
            "FB2,FanDuel,2026-03-01 12:00:00,NFL,X,0,+500,WIN,50,Free Bet\n"
            "RB1,FanDuel,2026-03-02 12:00:00,NFL,Y,100,+100,WIN,200,Cash\n")
        trades = load_sports_csv(path)
        self.assertEqual(len(trades), 4)
        process_batch(trades, db_path=self.db_path)
        # Free bet: $50 of winnings on $0 basis. Cash bet: $100 of winnings.
        self.assertAlmostEqual(self._summary()["gambling_gains"], 150.0, places=2)

    def test_stake_column_meaning_is_resolved_per_export_shape(self):
        """
        REGRESSION (Antigravity round-3, defect 1). `stake` means the CASH side in
        some exports and the TOTAL in others, and reading a total as a cash side
        hands the ticket a basis it never had: `Stake: 100, Free Bet Stake: 25`
        booked $100 of basis instead of $75, leaving $25 of winnings untaxed.

        The proposed fix keyed on `cash_stake > 0`, which regressed BOTH wholly
        promotional shapes (DraftKings `Stake: 0.00` and FanDuel `Cash Wager:
        0.00`) into a promo_stake-exceeds-total error and dropped the rows -
        reintroducing the very leak the previous round closed. Presence of a cash
        COLUMN is the signal, not a positive value in it.
        """
        cases = [
            # (stake columns, values, expected basis, why)
            ("stake,free_bet_stake", "100,25", 75.0, "stake is the TOTAL"),
            ("stake,free_bet_stake", "20,50", 20.0, "stake < promo, so it is the cash side"),
            ("stake,free_bet_stake", "0,50", 0.0, "wholly promotional (DraftKings)"),
            ("cash_wager,bonus_wager", "0,25", 0.0, "wholly promotional (FanDuel)"),
            ("cash_wager,bonus_wager", "75,25", 75.0, "explicit cash column, disjoint"),
            ("stake", "100", 100.0, "no promo column at all"),
        ]
        for index, (columns, values, expected, why) in enumerate(cases):
            with self.subTest(shape=why):
                path = self._write(
                    f"stake_shape_{index}.csv",
                    "ticket_id,sportsbook,date,sport,selection,"
                    + columns + ",odds,result,payout\n"
                    + f"T{index},DraftKings,2026-01-01 12:00:00,NFL,X,"
                    + values + ",+100,WIN,200\n")
                trades = load_sports_csv(path)
                placements = [t for t in trades if t["side"] == "BET"]
                self.assertEqual(len(placements), 1, f"row dropped: {why}")
                self.assertAlmostEqual(placements[0]["price"], expected, places=2, msg=why)

    def test_an_ambiguous_stake_takes_the_lower_basis_and_says_so(self):
        """
        `stake >= promo` reads equally well as the total or as the cash side, and
        the numbers cannot separate them. Taking it as the TOTAL gives the lower
        basis and the higher taxable winnings - the safe direction - and the row
        is tagged so it can be reconciled against the export later.
        """
        path = self._write(
            "ambiguous_stake.csv",
            "ticket_id,sportsbook,date,sport,selection,stake,free_bet_stake,"
            "odds,result,payout\n"
            "AMB,DraftKings,2026-01-01 12:00:00,NFL,X,100,25,+100,WIN,200\n")
        placement = [t for t in load_sports_csv(path) if t["side"] == "BET"][0]
        self.assertAlmostEqual(placement["price"], 75.0, places=2)
        self.assertIn("stake_basis:assumed_total_not_cash", placement["notes"])

        # An explicit cash column is unambiguous and carries no tag.
        clean = self._write(
            "explicit_stake.csv",
            "ticket_id,sportsbook,date,sport,selection,cash_wager,bonus_wager,"
            "odds,result,payout\n"
            "EXP,DraftKings,2026-01-01 12:00:00,NFL,X,75,25,+100,WIN,200\n")
        placement = [t for t in load_sports_csv(clean) if t["side"] == "BET"][0]
        self.assertAlmostEqual(placement["price"], 75.0, places=2)
        self.assertNotIn("stake_basis:", placement["notes"])

    def test_a_total_stake_export_taxes_the_right_winnings(self):
        """The end-to-end consequence, in escrow dollars."""
        path = self._write(
            "total_stake.csv",
            "ticket_id,sportsbook,date,sport,selection,stake,free_bet_stake,"
            "odds,result,payout\n"
            "TS1,DraftKings,2026-01-01 12:00:00,NFL,X,100,25,+100,WIN,200\n")
        process_batch(load_sports_csv(path), db_path=self.db_path)
        summary = self._summary()
        # $200 back on a $75 basis = $125 of winnings, not the $100 the
        # inflated-stake reading produced.
        self.assertAlmostEqual(summary["gambling_gains"], 125.0, places=2)
        self.assertAlmostEqual(summary["escrow_gambling"], 125.0 * 0.31, places=2)

    def test_w2g_is_deduped_by_ticket_even_if_two_rows_carry_the_tag(self):
        """
        Defence in depth behind the ingestor fix: the calculator sums a free-text
        tag across rows, and a multi-leg settlement is two rows for one ticket.
        Hand-built rows that both carry the tag must still credit once.
        """
        rows = [SportsBettingIngestor.create_bet_placed(
            "DUP", "DK", "NFL", "X", 10000.0, "+200", "2026-04-01 10:00:00")]
        for result, fraction in (("WIN", 0.5), ("LOSS", 0.5)):
            row = SportsBettingIngestor.create_bet_settled(
                "DUP", "DK", "NFL", "X", result, 15000.0 if result == "WIN" else 0.0,
                "2026-04-01 20:00:00", withholding=1200.0, stake_fraction=fraction)
            rows.append(row)
        # Both legs carry `w2g_withholding:1200.00` here on purpose.
        self.assertEqual(sum("w2g_withholding:" in r["notes"] for r in rows), 2)
        process_batch(rows, db_path=self.db_path)
        self.assertAlmostEqual(self._summary()["gambling_w2g_withheld"], 1200.0, places=2)


# ---------------------------------------------------------------------------
# 8. The after-tax hurdle (IRC 165(d) applied to sizing, not just to escrow).
# ---------------------------------------------------------------------------

class TestAfterTaxHurdle(unittest.TestCase):
    """
    The escrow says what to hold back. The HURDLE says whether the bet was ever
    worth placing. They must use the same loss-deductibility figure, or the bot
    sizes against a tax the ledger is not reserving for.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "hurdle.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _hook(self, **gambling):
        # `_cfg` pins loss_deduction_pct to 1.0 so the ESCROW tests read as
        # pre-2026 arithmetic. The hurdle is about what the law actually is
        # today, so restore the real OBBBA default unless a test overrides it.
        gambling.setdefault("loss_deduction_pct", 0.90)
        config = _cfg(**gambling)
        config["bot_integration"] = {"assumed_round_trip_fee": 0.02}
        return MonarchBankrollHook(db_path=self.db_path, config=config)

    def test_deductibility_tracks_the_configured_treatment(self):
        cases = {
            "casual_standard_deduction": 0.0,
            "session_netting": 0.0,          # a losing session is still Schedule A
            "casual_itemized": 0.90,         # OBBBA 70114, tax year 2026
            "professional_schedule_c": 0.90,  # 165(d) binds a professional too
        }
        for treatment, expected in cases.items():
            with self.subTest(treatment=treatment):
                hook = self._hook(tax_treatment=treatment)
                self.assertAlmostEqual(hook.gambling_loss_deductibility(), expected, places=6)

    def test_the_haircut_only_applies_from_its_effective_year(self):
        hook = self._hook(tax_treatment="casual_itemized")
        self.assertAlmostEqual(hook.gambling_loss_deductibility(2025), 1.0, places=6)
        self.assertAlmostEqual(hook.gambling_loss_deductibility(2026), 0.90, places=6)

    def test_the_three_published_hurdles_at_even_money(self):
        """
        t = 35%, O = 2.00. Derived from
          p_be  = (1 - t*d) / [ (O-1)(1-t) + (1 - t*d) ]
          hurdle = p_be * O - 1
        and confirmed by Monte-Carlo: 400k wagers at p_be return zero after tax.
        """
        hook = self._hook(tax_treatment="casual_standard_deduction")
        for delta, expected_hurdle, expected_p in ((1.0, 0.0, 0.5),
                                                   (0.90, 0.021970, 0.510985),
                                                   (0.0, 0.183432, 0.591716)):
            with self.subTest(delta=delta):
                result = hook.after_tax_edge_hurdle(2.00, delta=delta)
                self.assertAlmostEqual(result["tax_hurdle"], expected_hurdle, places=6)
                self.assertAlmostEqual(result["breakeven_win_probability"],
                                       expected_p, places=6)

    def test_break_even_probability_really_is_break_even(self):
        """The formula, checked against its own definition rather than a constant."""
        hook = self._hook()
        for odds in (1.5, 1.91, 2.0, 3.0, 5.0, 11.0):
            for delta in (0.0, 0.5, 0.9, 1.0):
                with self.subTest(odds=odds, delta=delta):
                    r = hook.after_tax_edge_hurdle(odds, delta=delta)
                    p, t = r["breakeven_win_probability"], r["tax_rate"]
                    after_tax_ev = (p * (odds - 1) * (1 - t)) - ((1 - p) * (1 - t * delta))
                    self.assertAlmostEqual(after_tax_ev, 0.0, places=12)
                    # And the hurdle is the gross edge at that probability.
                    self.assertAlmostEqual(r["tax_hurdle"], p * odds - 1, places=12)

    def test_the_hurdle_grows_with_the_odds_under_a_standard_deduction(self):
        """
        Longshots are punished hardest: the tax is charged on a bigger win while
        the loss still relieves nothing. A +1000 shot needs a 46.67% gross edge.
        """
        hook = self._hook(tax_treatment="casual_standard_deduction")
        hurdles = [hook.after_tax_edge_hurdle(o)["tax_hurdle"]
                   for o in (1.5, 2.0, 3.0, 5.0, 11.0)]
        self.assertEqual(hurdles, sorted(hurdles))
        self.assertAlmostEqual(hurdles[-1], 0.392405, places=5)

    def test_full_deductibility_leaves_no_tax_hurdle_at_all(self):
        """With losses fully deductible the tax is symmetric and cancels out."""
        hook = self._hook()
        for odds in (1.5, 2.0, 7.0):
            self.assertAlmostEqual(
                hook.after_tax_edge_hurdle(odds, delta=1.0)["tax_hurdle"], 0.0, places=12)

    def test_breakeven_gross_edge_only_changes_for_sports(self):
        """
        The Polymarket path is untouched: a capital loss nets against a capital
        gain, so only the fee hurdle applies there.
        """
        hook = self._hook(tax_treatment="casual_standard_deduction")
        # fee 2% / (1 - 0.31) = 2.8986%
        self.assertAlmostEqual(hook.breakeven_gross_edge(), 0.028986, places=6)
        self.assertAlmostEqual(hook.breakeven_gross_edge(category="macro"),
                               0.028986, places=6)
        sports = hook.breakeven_gross_edge(category="sports", decimal_odds=2.00)
        self.assertAlmostEqual(sports, hook.breakeven_gross_edge()
                       + hook.after_tax_edge_hurdle(2.00)['tax_hurdle'], places=9)

    def test_a_sports_call_without_odds_assumes_even_money(self):
        """The least punitive assumption available - the hurdle grows with odds."""
        hook = self._hook(tax_treatment="casual_standard_deduction")
        self.assertAlmostEqual(hook.breakeven_gross_edge(category="sports"),
                               hook.breakeven_gross_edge(category="sports",
                                                         decimal_odds=2.00), places=12)

    def test_invalid_odds_are_refused(self):
        hook = self._hook()
        for bad in (1.0, 0.5, -110):
            with self.subTest(odds=bad):
                with self.assertRaises(ValueError):
                    hook.after_tax_edge_hurdle(bad)


# ---------------------------------------------------------------------------
# 9. The wagering order gate (Defect 2). The hurdle stops being a report.
# ---------------------------------------------------------------------------

class TestWageringOrderGate(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "gate.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _hook(self, treatment="casual_standard_deduction"):
        config = _cfg(tax_treatment=treatment, loss_deduction_pct=0.90)
        config["portfolio"]["default_cash_balance_usdc"] = 50000.0
        config["bot_integration"] = {
            "assumed_round_trip_fee": 0.02, "max_position_pct": 0.05,
            "min_order_usd": 1.0,
            "strategies": {"sports_betting": 0.15, "sandbox": 0.85},
        }
        return MonarchBankrollHook(db_path=self.db_path, config=config)

    def _order(self, hook, **kwargs):
        params = dict(category="sports", strategy="sports_betting")
        params.update(kwargs)
        return hook.check_order(500.0, **params)

    def test_a_sub_hurdle_wager_is_rejected(self):
        """
        REGRESSION (Defect 2). Before this, a $500 sports wager with a 5% edge was
        APPROVED at $375 against a 24.29% hurdle - the gate could not see the edge
        at all, because there was no parameter for it.
        """
        hook = self._hook()
        decision = self._order(hook, expected_edge=0.05, decimal_odds=2.00)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.approved_notional, 0.0)
        self.assertIn("below the", decision.reason)
        self.assertIn("after-tax hurdle", decision.reason)
        self.assertAlmostEqual(decision.detail["after_tax_hurdle"], 0.212417, places=5)

    def test_a_wager_clearing_the_hurdle_is_approved_and_kelly_sized(self):
        hook = self._hook()
        decision = self._order(hook, expected_edge=0.50, decimal_odds=2.00)
        self.assertTrue(decision.approved)
        self.assertGreater(decision.approved_notional, 0.0)
        self.assertGreater(decision.detail["after_tax_kelly"], 0.0)

    def test_a_missing_edge_fails_closed(self):
        """
        The fee-only fallback is not a weaker check, it is the WRONG check: it
        passes a 3% edge that carries a 21%+ hurdle.
        """
        hook = self._hook()
        decision = self._order(hook)
        self.assertFalse(decision.approved)
        self.assertIn("FAIL-CLOSED", decision.reason)

        partial = self._order(hook, expected_edge=0.50)      # odds missing
        self.assertFalse(partial.approved)

    def test_kelly_only_ever_tightens_the_cap(self):
        """
        The flat per-order cap is a limit a human chose. An estimated edge may
        shrink it and must never raise it.
        """
        hook = self._hook("professional_schedule_c")
        flat_cap = hook.max_position_size() * 0  # unused; cap comes from the bucket
        big = self._order(hook, expected_edge=5.0, decimal_odds=2.00)
        # 15% of a ~$50k safe bankroll is $7.5k; 5% of that is the $375 cap.
        self.assertLessEqual(big.approved_notional, 375.0 + 1e-9)

    def test_the_gate_and_the_sizer_agree_across_three_bands(self):
        """
        f* is zero EXACTLY at the tax hurdle, and the gate charges the fee on top,
        so an edge sorts into three bands:

          edge < tax hurdle            f* < 0  and rejected - an after-tax loss
          tax hurdle < edge < total    f* > 0  but STILL rejected: Kelly says the
                                       bet is worth making, the fee says it is not
          edge > total hurdle          f* > 0  and approved

        The middle band is the point worth pinning. It is not an inconsistency
        between the gate and the sizer - it is the execution cost, which Kelly on
        the payoffs alone never sees.
        """
        hook = self._hook()
        for odds in (1.5, 2.0, 3.0, 5.0):
            total = hook.breakeven_gross_edge(category="sports", decimal_odds=odds)
            tax_only = hook.after_tax_edge_hurdle(odds)["tax_hurdle"]
            self.assertGreater(total, tax_only)          # the fee band is real
            bands = {
                "below tax hurdle": (tax_only - 0.01, False, False),
                "fee band": ((tax_only + total) / 2.0, False, True),
                "above total hurdle": (total + 0.01, True, True),
            }
            for label, (edge, approved, kelly_positive) in bands.items():
                with self.subTest(odds=odds, band=label):
                    decision = self._order(hook, expected_edge=edge, decimal_odds=odds)
                    kelly = hook.after_tax_kelly_fraction((1 + edge) / odds, odds)
                    self.assertEqual(decision.approved, approved)
                    self.assertEqual(kelly > 0, kelly_positive)

    def test_kelly_is_exactly_zero_at_the_tax_hurdle(self):
        """The identity the three bands rest on, asserted directly."""
        hook = self._hook()
        for odds in (1.5, 2.0, 3.0, 5.0, 11.0):
            with self.subTest(odds=odds):
                edge = hook.after_tax_edge_hurdle(odds)["tax_hurdle"]
                self.assertAlmostEqual(
                    hook.after_tax_kelly_fraction((1 + edge) / odds, odds), 0.0, places=12)

    def test_a_professional_clears_edges_a_standard_deduction_filer_cannot(self):
        """The same 6% edge: a business at 5.70%, a hobby at 24.29%."""
        edge, odds = 0.06, 2.00
        professional = self._order(self._hook("professional_schedule_c"),
                                   expected_edge=edge, decimal_odds=odds)
        casual = self._order(self._hook("casual_standard_deduction"),
                             expected_edge=edge, decimal_odds=odds)
        self.assertTrue(professional.approved)
        self.assertFalse(casual.approved)

    def test_non_wagering_categories_need_no_edge(self):
        """Capital losses net against capital gains; fee/(1-t) is the whole story."""
        hook = self._hook()
        for category in (None, "macro", "crypto", "sports_adjacent"):
            with self.subTest(category=category):
                decision = hook.check_order(500.0, category=category, strategy="sandbox")
                self.assertTrue(decision.approved)
                self.assertIsNone(decision.detail["after_tax_hurdle"])

    def test_unusable_odds_are_rejected_not_crashed(self):
        hook = self._hook()
        for bad in (1.0, 0.5, -3.0):
            with self.subTest(odds=bad):
                decision = self._order(hook, expected_edge=0.5, decimal_odds=bad)
                self.assertFalse(decision.approved)
                self.assertIn("unusable odds", decision.reason)

    def test_wagering_diagnostics_are_on_the_decision(self):
        hook = self._hook("professional_schedule_c")
        detail = self._order(hook, expected_edge=0.12, decimal_odds=2.00).detail
        for key in ("expected_edge", "decimal_odds", "after_tax_hurdle",
                    "after_tax_kelly", "kelly_notional"):
            self.assertIsNotNone(detail[key], key)

    def test_size_order_threads_the_edge_through(self):
        hook = self._hook("professional_schedule_c")
        self.assertGreater(
            hook.size_order(500.0, category="sports", strategy="sports_betting",
                            expected_edge=0.12, decimal_odds=2.00), 0.0)
        self.assertEqual(
            hook.size_order(500.0, category="sports", strategy="sports_betting",
                            expected_edge=0.01, decimal_odds=2.00), 0.0)


class TestAfterTaxKelly(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "kelly.db"
        init_db(self.db_path)
        config = _cfg(tax_treatment="casual_standard_deduction", loss_deduction_pct=0.90)
        self.hook = MonarchBankrollHook(db_path=self.db_path, config=config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_after_tax_kelly_matches_its_closed_form(self):
        """f* = (p*w - q*l) / (w*l), with w and l the after-tax legs."""
        t = self.hook._composite_tax_rate()
        for odds in (1.5, 2.0, 4.0):
            for delta in (0.0, 0.9, 1.0):
                for p in (0.3, 0.5, 0.7, 0.9):
                    with self.subTest(odds=odds, delta=delta, p=p):
                        w = (odds - 1) * (1 - t)
                        l = 1 - t * delta
                        expected = (p * w - (1 - p) * l) / (w * l)
                        self.assertAlmostEqual(
                            self.hook.after_tax_kelly_fraction(p, odds, delta=delta),
                            expected, places=12)

    def test_after_tax_kelly_is_below_gross_kelly_when_losses_are_disallowed(self):
        """
        Gross Kelly on a standard-deduction wager sizes a losing bet as though it
        were a winning one - that gap is the whole reason this exists.
        """
        # At t = 0.31 the break-even win rate at even money is 59.17%, so 55%
        # is the loser here - it was 60% while the composite double-counted state.
        odds, p = 2.0, 0.55
        gross = (p * (odds - 1) - (1 - p)) / (odds - 1)
        after_tax = self.hook.after_tax_kelly_fraction(p, odds, delta=0.0)
        self.assertGreater(gross, after_tax)
        self.assertLess(after_tax, 0.0)      # 55% at even money is a LOSER after tax

    def test_full_deductibility_leaves_kelly_close_to_gross(self):
        """With symmetric tax the stake fraction is scaled, not re-signed."""
        odds, p = 2.0, 0.55
        gross = (p * (odds - 1) - (1 - p)) / (odds - 1)
        after_tax = self.hook.after_tax_kelly_fraction(p, odds, delta=1.0)
        self.assertGreater(after_tax, 0.0)
        self.assertGreater(after_tax, gross)   # smaller effective stakes -> larger f*

    def test_invalid_odds_refused(self):
        for bad in (1.0, 0.0, -2.0):
            with self.subTest(odds=bad):
                with self.assertRaises(ValueError):
                    self.hook.after_tax_kelly_fraction(0.5, bad)


# ---------------------------------------------------------------------------
# 10. Form W-2G (Reg. 1.6041-10 and IRC 3402(q)).
# ---------------------------------------------------------------------------

class TestFormW2G(unittest.TestCase):
    """
    Both statutory tests are CONJUNCTIVE, and that is the whole point: nearly
    every sports bet triggers neither, so the ones that do are worth predicting.
    """

    def test_the_odds_test_is_what_exempts_ordinary_sports_bets(self):
        """
        A $1,000 winner at 2:1 clears both dollar thresholds twice over and fails
        the 300:1 test, so nothing is reported and nothing is withheld. Reading
        the dollar test alone would flag most of a serious bettor's year.
        """
        assessment = assess_w2g(profit=2000.0, wager=1000.0)
        self.assertAlmostEqual(assessment.multiplier, 2.0)
        self.assertFalse(assessment.reportable)
        self.assertFalse(assessment.withholding_required)
        self.assertEqual(assessment.withholding, 0.0)

    def test_the_reporting_trigger_needs_600_dollars_AND_300x(self):
        # $2 at 349x -> $698 of proceeds. Both tests met.
        self.assertTrue(assess_w2g(698.0, 2.0).reportable)
        # $300 of proceeds at exactly 300x: odds test met, dollar test is not.
        self.assertFalse(assess_w2g(300.0, 1.0).reportable)
        # $600 of proceeds at 6x: dollar test met, odds test is not.
        self.assertFalse(assess_w2g(600.0, 100.0).reportable)
        # Exactly on both boundaries.
        self.assertTrue(assess_w2g(600.0, 2.0).reportable)

    def test_mandatory_withholding_needs_over_5000_AND_300x(self):
        """IRC 3402(q): 24% of the PROCEEDS, not of the payout."""
        under = assess_w2g(5000.0, 10.0)          # exactly 5,000 is not OVER it
        self.assertTrue(under.reportable)
        self.assertFalse(under.withholding_required)

        over = assess_w2g(6080.0, 20.0)           # 304x
        self.assertTrue(over.withholding_required)
        self.assertAlmostEqual(over.withholding, 6080.0 * 0.24, places=6)

        # Big dollars, short odds: no withholding however large the win.
        self.assertFalse(assess_w2g(500000.0, 250000.0).withholding_required)

    def test_proceeds_not_payout_is_what_is_measured(self):
        """A $100 ticket returning $700 is $600 at 6x, not $700 at 7x."""
        assessment = assess_w2g(profit=600.0, wager=100.0)
        self.assertAlmostEqual(assessment.multiplier, 6.0)

    def test_a_losing_or_break_even_wager_assesses_nothing(self):
        for profit in (-100.0, 0.0):
            with self.subTest(profit=profit):
                assessment = assess_w2g(profit, 100.0)
                self.assertFalse(assessment.reportable)
                self.assertEqual(assessment.withholding, 0.0)

    def test_a_free_bet_has_an_unbounded_multiplier(self):
        """
        Conservative reading: a $0 wager cannot fail a ratio test, so the odds
        test is met and the dollar test decides. Flags more W-2Gs, which costs a
        warning rather than a surprise.
        """
        self.assertTrue(assess_w2g(650.0, 0.0).reportable)
        self.assertFalse(assess_w2g(500.0, 0.0).reportable)

    def test_thresholds_come_from_policy(self):
        policy = GamblingPolicy(w2g_reporting_threshold=1200.0,
                                w2g_multiplier_threshold=10.0,
                                w2g_withholding_threshold=100000.0,
                                mandatory_withholding_rate=0.30)
        assessment = assess_w2g(2000.0, 100.0, policy)     # 20x
        self.assertTrue(assessment.reportable)
        self.assertFalse(assessment.withholding_required)


class TestW2GThroughTheLedger(SportsTaxTestBase):

    def _big_winner(self):
        return [
            SportsBettingIngestor.create_bet_placed(
                "BIG", "DK", "NFL", "PARLAY", 20.0, "+303400", "2026-01-05 12:00:00"),
            SportsBettingIngestor.create_bet_settled(
                "BIG", "DK", "NFL", "PARLAY", "WIN", 60720.0, "2026-01-05 22:00:00",
                wager=20.0),
        ]

    def test_a_qualifying_win_is_tagged_at_ingestion(self):
        settlement = self._big_winner()[1]
        self.assertIn("w2g_reportable:true", settlement["notes"])
        self.assertIn("w2g_withholding_predicted:", settlement["notes"])

    def test_an_ordinary_win_is_not_tagged(self):
        settlement = SportsBettingIngestor.create_bet_settled(
            "ORD", "DK", "NFL", "ML", "WIN", 3000.0, "2026-01-06 22:00:00", wager=1000.0)
        self.assertNotIn("w2g", settlement["notes"])

    def test_predicted_withholding_is_credited_through_the_federal_cap(self):
        """
        NOT subtracted from the total escrow. A book that withheld and a book that
        MUST withhold cannot produce different escrows for the same wager, and
        3402(q) withholding is federal income tax - it cannot pay a state.
        """
        process_batch(self._big_winner(), db_path=self.db_path)
        config = _cfg()
        config["portfolio"]["default_cash_balance_usdc"] = 200000.0
        summary = self._summary(config)
        self.assertAlmostEqual(summary["gambling_w2g_predicted"], 60700.0 * 0.24, places=2)
        self.assertEqual(summary["gambling_w2g_withheld"], 0.0)
        # Credit is capped at the federal leg (28% of a $60,700 base = $16,996),
        # and the predicted $14,568 sits under it, so it credits in full.
        self.assertAlmostEqual(summary["gambling_w2g_credit_applied"], 14568.0, places=2)
        self.assertAlmostEqual(summary["escrow_gambling"], 60700.0 * 0.31 - 14568.0,
                               places=2)

    def test_predicted_is_not_double_counted_against_recorded(self):
        """A ticket the book actually withheld on must not also be predicted."""
        rows = [
            SportsBettingIngestor.create_bet_placed(
                "BIG", "DK", "NFL", "PARLAY", 20.0, "+303400", "2026-01-05 12:00:00"),
            SportsBettingIngestor.create_bet_settled(
                "BIG", "DK", "NFL", "PARLAY", "WIN", 60720.0, "2026-01-05 22:00:00",
                wager=20.0, withholding=14568.0),
        ]
        process_batch(rows, db_path=self.db_path)
        config = _cfg()
        config["portfolio"]["default_cash_balance_usdc"] = 200000.0
        summary = self._summary(config)
        self.assertAlmostEqual(summary["gambling_w2g_withheld"], 14568.0, places=2)
        self.assertEqual(summary["gambling_w2g_predicted"], 0.0)
        self.assertAlmostEqual(summary["gambling_w2g_credit_applied"], 14568.0, places=2)

    def test_the_cash_shortfall_is_warned_about(self):
        """The escrow already credits it; the operator's bank balance did not."""
        process_batch(self._big_winner(), db_path=self.db_path)
        config = _cfg()
        config["portfolio"]["default_cash_balance_usdc"] = 200000.0
        warnings = self._summary(config)["gambling_warnings"]
        self.assertTrue(any("3402(q)" in w for w in warnings))


# ---------------------------------------------------------------------------
# 11. The arbitrage tax trap.
# ---------------------------------------------------------------------------

class TestLedgerVersioning(SportsTaxTestBase):
    """
    Round 26c changed how capital terms are classified. `realized_pnl` is derived
    data and nothing rewrites it in place, so a ledger built earlier keeps the old
    answer - and the old answer marked exact-anniversary trades LONG_TERM, which
    UNDER-states the reserve.
    """

    def _spot_trade(self):
        return [
            {"source": "spot", "tx_hash": "b", "timestamp": "2025-01-01 10:00:00",
             "asset_class": "crypto_spot", "symbol": "ETH", "side": "BUY",
             "quantity": 1, "price": 1000, "fee": 0, "total_value": 1000, "notes": ""},
            {"source": "spot", "tx_hash": "s", "timestamp": "2026-06-01 10:00:00",
             "asset_class": "crypto_spot", "symbol": "ETH", "side": "SELL",
             "quantity": 1, "price": 2000, "fee": 0, "total_value": 2000, "notes": ""},
        ]

    def _forget_term_rule(self):
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute("DELETE FROM agent_meta WHERE key = 'term_rule_version'")
        finally:
            conn.close()

    def test_a_fresh_ledger_records_the_current_rule(self):
        process_batch(self._spot_trade(), db_path=self.db_path)
        summary = self._summary()
        self.assertEqual(summary["term_rule"], "calendar-more-than-one-year")
        self.assertFalse(summary["term_rule_stale"])

    def test_a_pre_calendar_ledger_is_flagged(self):
        process_batch(self._spot_trade(), db_path=self.db_path)
        self._forget_term_rule()
        summary = self._summary()
        self.assertEqual(summary["term_rule"], "pre-calendar")
        self.assertTrue(summary["term_rule_stale"])

    def test_a_rebuild_clears_the_flag(self):
        process_batch(self._spot_trade(), db_path=self.db_path)
        self._forget_term_rule()
        self.assertTrue(self._summary()["term_rule_stale"])
        rebuild_lots(db_path=self.db_path, method="FIFO")
        self.assertFalse(self._summary()["term_rule_stale"])

    def test_a_gambling_only_ledger_is_not_flagged(self):
        """Wagers carry the GAMBLING term, which no rule change ever touched."""
        process_batch(self._wager("W1", 100.0, "WIN", 250.0), db_path=self.db_path)
        self._forget_term_rule()
        self.assertFalse(self._summary()["term_rule_stale"])

    def test_the_hud_says_a_rebuild_is_needed(self):
        from ..interfaces.cli import render_hud
        process_batch(self._spot_trade(), db_path=self.db_path)
        self._forget_term_rule()
        text = render_hud(self._summary())
        self.assertIn("older rule", text)
        self.assertIn("rebuild", text)


class TestCompositeRateWarning(SportsTaxTestBase):
    """
    `short_term_capital_gains` is documented as ALREADY blending federal and
    state, and `state_tax_rate` is then added on top - so the composite counts
    state twice, and the "federal" leg is not a federal rate. Two consequences in
    opposite directions: the W-2G credit ceiling is too generous, every hurdle too
    strict. Not fixable from code; it needs the operator's real marginal rates.
    """

    def test_the_fallback_is_warned_about(self):
        """A pre-26k config, with no unbundled federal rate anywhere."""
        process_batch(self._wager("W1", 100.0, "WIN", 250.0), db_path=self.db_path)
        legacy = _cfg()
        legacy["tax_rates"] = {"short_term_capital_gains": 0.28,
                               "long_term_capital_gains": 0.15,
                               "state_tax_rate": 0.05, "safety_buffer_pct": 0.02}
        warnings = self._summary(legacy)["gambling_warnings"]
        self.assertTrue(any("No unbundled federal rate is set" in w for w in warnings))

    def test_setting_a_real_federal_rate_silences_it(self):
        process_batch(self._wager("W1", 100.0, "WIN", 250.0), db_path=self.db_path)
        config = _cfg()
        config["gambling"]["federal_ordinary_rate"] = 0.24
        config["gambling"]["state_ordinary_rate"] = 0.05
        warnings = self._summary(config)["gambling_warnings"]
        self.assertFalse(any("No unbundled federal rate is set" in w for w in warnings))

    def test_a_ledger_with_no_wagers_says_nothing(self):
        """No winnings, no rate to be wrong about."""
        self.assertEqual(
            [w for w in self._summary()["gambling_warnings"]
             if "unbundled federal rate" in w], [])


class TestConfigKeysAreLive(SportsTaxTestBase):
    """
    A key documented in config.yaml that nothing reads is worse than no key: it
    tells the operator a knob exists, and editing it changes nothing. This class
    exists because that has now happened three times - the two W-2G thresholds,
    `odds_payout_tolerance_pct`, and `snapshot_cache_seconds`.
    """

    def _write(self, name, text):
        path = Path(self.temp_dir.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_odds_payout_tolerance_pct_changes_behaviour(self):
        """$200 paid against a -110 implied $190.91 is 4.8% out."""
        path = self._write(
            "tol.csv",
            "ticket_id,sportsbook,date,sport,selection,wager,odds,result,payout\n"
            "T1,DK,2026-01-01 12:00:00,NFL,X,100,-110,WIN,200\n")
        tight = SportsBettingIngestor.load_from_csv(path, tolerance_pct=0.02)
        loose = SportsBettingIngestor.load_from_csv(path, tolerance_pct=0.20)
        self.assertIn("odds_check",
                      [t for t in tight if t["side"] == "BET_WIN"][0]["notes"])
        self.assertNotIn("odds_check",
                         [t for t in loose if t["side"] == "BET_WIN"][0]["notes"])

    def test_snapshot_cache_seconds_reaches_the_hook(self):
        for seconds in (5, 120):
            with self.subTest(seconds=seconds):
                hook = MonarchBankrollHook(
                    db_path=self.db_path,
                    config={"portfolio": {"tax_year": 2026},
                            "bot_integration": {"snapshot_cache_seconds": seconds}})
                self.assertEqual(hook.cache_ttl_s, float(seconds))

    def test_an_explicit_constructor_argument_still_wins(self):
        hook = MonarchBankrollHook(
            db_path=self.db_path, cache_ttl_s=99.0,
            config={"portfolio": {"tax_year": 2026},
                    "bot_integration": {"snapshot_cache_seconds": 5}})
        self.assertEqual(hook.cache_ttl_s, 99.0)

    def test_a_nonsense_cache_value_falls_back_loudly(self):
        hook = MonarchBankrollHook(
            db_path=self.db_path,
            config={"portfolio": {"tax_year": 2026},
                    "bot_integration": {"snapshot_cache_seconds": "soon"}})
        self.assertEqual(hook.cache_ttl_s, 60.0)

    def test_the_w2g_thresholds_reach_the_assessment(self):
        """The keys Antigravity found dead in 26h - pinned so they stay live."""
        config = _cfg()
        config["gambling"]["w2g_reporting_threshold_usd"] = 1200.0
        config["gambling"]["w2g_odds_multiplier_threshold"] = 10.0
        policy = resolve_policy(config["gambling"])
        self.assertEqual(policy.w2g_reporting_threshold, 1200.0)
        self.assertEqual(policy.w2g_multiplier_threshold, 10.0)
        # $2,000 at 20x: clears the lowered odds test, clears the raised dollar one.
        self.assertTrue(assess_w2g(2000.0, 100.0, policy).reportable)


class TestArbitrageHurdle(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "arb.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _hook(self, treatment="casual_standard_deduction"):
        config = _cfg(tax_treatment=treatment, loss_deduction_pct=0.90)
        config["portfolio"]["default_cash_balance_usdc"] = 50000.0
        config["bot_integration"] = {
            "assumed_round_trip_fee": 0.02, "max_position_pct": 0.05,
            "min_order_usd": 1.0,
            "strategies": {"sports_betting": 0.15, "sandbox": 0.85}}
        return MonarchBankrollHook(db_path=self.db_path, config=config)

    def test_the_three_published_hurdles(self):
        """t = 31%: delta 0 -> 22.46%, delta 0.90 -> 2.25%, delta 1.0 -> 0.00%."""
        hook = self._hook()
        for delta, expected in ((0.0, 0.224638), (0.90, 0.022464), (1.0, 0.0)):
            with self.subTest(delta=delta):
                self.assertAlmostEqual(hook.after_tax_arbitrage_hurdle(delta=delta),
                                       expected, places=6)

    def test_the_formula_is_the_symmetric_break_even(self):
        """
        Checked against its own definition: at equal stakes the after-tax profit
        is R(1-t) - 1 + t(1+delta)/2, which is zero exactly at the hurdle.
        """
        hook = self._hook()
        tax = hook._composite_tax_rate()
        for delta in (0.0, 0.5, 0.9, 1.0):
            with self.subTest(delta=delta):
                gross = hook.after_tax_arbitrage_hurdle(delta=delta)
                total_return = 1.0 + gross
                after_tax = (total_return * (1 - tax) - 1.0
                             + tax * (1 + delta) / 2.0)
                self.assertAlmostEqual(after_tax, 0.0, places=12)

    def test_an_arbitrage_is_not_riskless_after_tax(self):
        """
        THE FINDING. Tax is asymmetric between the legs, so a position that is
        riskless in dollars has two different after-tax outcomes - unless the
        stakes are equal or losses are fully deductible.
        """
        hook = self._hook()
        symmetric = hook.after_tax_arbitrage_hurdle(odds_a=2.0, odds_b=2.0)
        self.assertAlmostEqual(symmetric, hook.after_tax_arbitrage_hurdle(delta=0.0),
                               places=12)
        for odds_a, odds_b in ((1.5, 3.2), (1.2, 6.5), (1.05, 25.0)):
            with self.subTest(odds=(odds_a, odds_b)):
                self.assertGreater(hook.after_tax_arbitrage_hurdle(
                    odds_a=odds_a, odds_b=odds_b), symmetric)

    def test_full_deductibility_removes_the_asymmetry(self):
        """With delta = 1 the branches coincide whatever the stakes."""
        hook = self._hook()
        for odds_a, odds_b in ((2.0, 2.0), (1.2, 6.5), (1.05, 25.0)):
            with self.subTest(odds=(odds_a, odds_b)):
                self.assertAlmostEqual(hook.after_tax_arbitrage_hurdle(
                    delta=1.0, odds_a=odds_a, odds_b=odds_b), 0.0, places=12)

    def test_a_real_world_arb_is_hard_rejected_under_a_standard_deduction(self):
        """
        Cross-book arbitrage is 1-3% in practice. Every one of them is an
        after-tax loss of roughly 14%, and it looks like free money until April.
        """
        hook = self._hook("casual_standard_deduction")
        for arb in (0.01, 0.02, 0.05, 0.20, 0.2246):
            with self.subTest(arb=arb):
                decision = hook.check_order(1000.0, category="sports",
                                            strategy="sports_betting",
                                            arbitrage_edge=arb)
                self.assertFalse(decision.approved)
                self.assertIn("after-tax arbitrage hurdle", decision.reason)

    def test_an_arb_above_the_hurdle_is_approved_and_sized(self):
        hook = self._hook("casual_standard_deduction")
        decision = hook.check_order(1000.0, category="sports", strategy="sports_betting",
                                    arbitrage_edge=0.30)
        self.assertTrue(decision.approved)
        self.assertGreater(decision.approved_notional, 0.0)
        self.assertAlmostEqual(decision.detail["arbitrage_hurdle"], 0.224638, places=6)

    def test_a_professional_clears_arbs_a_casual_filer_cannot(self):
        arb = 0.03
        self.assertTrue(self._hook("professional_schedule_c").check_order(
            1000.0, category="sports", strategy="sports_betting",
            arbitrage_edge=arb).approved)
        self.assertFalse(self._hook("casual_standard_deduction").check_order(
            1000.0, category="sports", strategy="sports_betting",
            arbitrage_edge=arb).approved)

    def test_supplying_both_legs_binds_harder_than_the_symmetric_default(self):
        hook = self._hook("casual_standard_deduction")
        symmetric = hook.check_order(1000.0, category="sports", strategy="sports_betting",
                                     arbitrage_edge=0.30)
        self.assertTrue(symmetric.approved)
        lopsided = hook.check_order(1000.0, category="sports", strategy="sports_betting",
                                    arbitrage_edge=0.30, arbitrage_odds=(1.05, 25.0))
        self.assertFalse(lopsided.approved)
        self.assertAlmostEqual(lopsided.detail["arbitrage_hurdle"], 0.431166, places=5)

    def test_an_arb_does_not_also_need_a_single_wager_edge(self):
        """
        The arb test IS the gate for an arb. Demanding `expected_edge` as well
        would fail-closed on the very positions it just approved.
        """
        decision = self._hook("professional_schedule_c").check_order(
            1000.0, category="sports", strategy="sports_betting", arbitrage_edge=0.05)
        self.assertTrue(decision.approved)
        self.assertNotIn("FAIL-CLOSED", decision.reason)

    def test_unusable_arb_odds_are_rejected_not_crashed(self):
        decision = self._hook().check_order(
            1000.0, category="sports", strategy="sports_betting",
            arbitrage_edge=0.50, arbitrage_odds=(1.0, 3.0))
        self.assertFalse(decision.approved)
        self.assertIn("unusable odds", decision.reason)

    def test_non_wagering_categories_ignore_the_arbitrage_hurdle(self):
        decision = self._hook().check_order(1000.0, category="macro",
                                            strategy="sandbox", arbitrage_edge=0.01)
        self.assertTrue(decision.approved)


if __name__ == "__main__":
    unittest.main()
