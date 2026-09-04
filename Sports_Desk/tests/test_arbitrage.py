"""
Unit tests for cross-book arbitrage detection.

The arithmetic here is checkable by hand, so the fixtures use prices with known
answers rather than whatever the implementation emits. The important assertions
are the ones about TAX: a gross arbitrage and an after-tax arbitrage are
different things, and the gap between them is the whole reason this module has a
hurdle at all.
"""
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from Sports_Desk.data.db import init_market_db, record_settled_result
from Sports_Desk.engine.arbitrage import (ArbitrageError, MIN_REPORTABLE_ARB,
                                          assess_after_tax, build_synthetic_market,
                                          find_arbitrage, render_arbitrage,
                                          scan_market_db)
from Sports_Desk.ingestors.odds_watcher import OddsWatcher
from Tax_Reserve_Agent.database.db import init_db
from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook

QUOTED = "2026-09-03T18:00:00Z"
STARTS = "2026-09-03T23:00:00Z"
NOW = datetime(2026, 9, 3, 18, 2, 0)

# Pinnacle A at -105 (1.952381), B at -115 (1.869565); DraftKings B at +130 (2.30).
# Best prices are 1.952381 and 2.30, summing to 0.946978 - a 5.5991% arbitrage.
# NOTE the pure tests below use a literal 1.9524, which is a hair different
# (5.5997%) - the exact American price and its rounded decimal are not the same
# number, and a test that conflates them fails for the right reason.
ARB_MARKET = (
    "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp,start_time\n"
    f"G2,NFL,moneyline,A,Pinnacle,-105,1,{QUOTED},{STARTS}\n"
    f"G2,NFL,moneyline,B,Pinnacle,-115,1,{QUOTED},{STARTS}\n"
    f"G2,NFL,moneyline,B,DraftKings,+130,0,{QUOTED},{STARTS}\n"
)


class ArbTestBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.drop = self.root / "odds"
        self.drop.mkdir()
        self.db = self.root / "sports_market.db"
        self.ledger = self.root / "tax.db"
        init_market_db(self.db)
        init_db(self.ledger)

    def tearDown(self):
        self.temp.cleanup()

    def _hook(self, treatment="professional_schedule_c"):
        return MonarchBankrollHook(db_path=self.ledger, config={
            "tax_rates": {"short_term_capital_gains": 0.28,
                          "long_term_capital_gains": 0.15,
                          "state_tax_rate": 0.05, "safety_buffer_pct": 0.02},
            "portfolio": {"default_cash_balance_usdc": 50000.0, "tax_year": 2026},
            "gambling": {"tax_treatment": treatment, "loss_deduction_pct": 0.90},
            "bot_integration": {"assumed_round_trip_fee": 0.02,
                                "max_position_pct": 0.05, "min_order_usd": 1.0,
                                "strategies": {"sports_betting": 0.15,
                                               "sandbox": 0.85}}})

    def _ingest(self, text=ARB_MARKET, name="odds.csv", hook=None):
        (self.drop / name).write_text(text, encoding="utf-8")
        hook = hook or self._hook()
        watcher = OddsWatcher(
            drop_folder=self.drop, db_path=self.db,
            after_tax_hurdle=lambda odds: hook.breakeven_gross_edge(
                category="sports", decimal_odds=odds))
        watcher.scan_once()
        watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)


class TestSyntheticMarket(unittest.TestCase):
    """Pure arithmetic - no database, no tax."""

    def _quotes(self, *pairs):
        return [{"selection": s, "book": b, "decimal_odds": o} for s, b, o in pairs]

    def test_the_best_price_per_outcome_wins(self):
        legs = build_synthetic_market(self._quotes(
            ("A", "pinnacle", 1.95), ("A", "draftkings", 2.05),
            ("B", "pinnacle", 1.87), ("B", "fanduel", 2.30)))
        best = {leg.selection: (leg.book, leg.decimal_odds) for leg in legs}
        self.assertEqual(best["A"], ("draftkings", 2.05))
        self.assertEqual(best["B"], ("fanduel", 2.30))

    def test_stakes_equalise_the_return_and_sum_to_one(self):
        legs = build_synthetic_market(self._quotes(
            ("A", "x", 1.9524), ("B", "y", 2.30)))
        self.assertAlmostEqual(sum(leg.stake_fraction for leg in legs), 1.0, places=12)
        returns = [leg.stake_fraction * leg.decimal_odds for leg in legs]
        self.assertAlmostEqual(returns[0], returns[1], places=12)

    def test_a_one_sided_market_is_refused(self):
        """An arbitrage on one leg is a missing leg, not an arbitrage."""
        with self.assertRaises(ArbitrageError):
            build_synthetic_market(self._quotes(("A", "x", 2.0), ("A", "y", 2.1)))

    def test_no_arbitrage_when_the_best_prices_still_carry_margin(self):
        self.assertIsNone(find_arbitrage(self._quotes(
            ("A", "x", 1.90), ("B", "y", 1.90))))

    def test_an_arbitrage_is_found_and_priced(self):
        """Literal 1.9524 and 2.30 sum to 0.946973 -> 5.5997% gross."""
        opportunity = find_arbitrage(self._quotes(("A", "x", 1.9524), ("B", "y", 2.30)))
        self.assertIsNotNone(opportunity)
        self.assertAlmostEqual(opportunity.booksum, 0.946973, places=6)
        self.assertAlmostEqual(opportunity.gross_arb, 0.055997, places=6)
        self.assertTrue(opportunity.is_cross_book)

    def test_a_single_book_arbing_itself_is_flagged(self):
        """A book does not offer an arbitrage against itself - that is bad data."""
        opportunity = find_arbitrage(self._quotes(
            ("A", "pinnacle", 1.9524), ("B", "pinnacle", 2.30)))
        self.assertFalse(opportunity.is_cross_book)
        self.assertTrue(any("against itself" in w for w in opportunity.warnings))

    def test_a_hair_thin_arbitrage_is_ignored(self):
        """Inside rounding and half-point noise, and slippage eats it."""
        booksum = 1.0 - MIN_REPORTABLE_ARB / 2.0
        odds = 2.0 / booksum
        self.assertIsNone(find_arbitrage(self._quotes(("A", "x", odds), ("B", "y", odds))))

    def test_three_way_markets_work(self):
        legs = build_synthetic_market(self._quotes(
            ("H", "x", 3.10), ("D", "y", 3.60), ("A", "z", 3.60)))
        self.assertEqual(len(legs), 3)
        self.assertAlmostEqual(sum(leg.stake_fraction for leg in legs), 1.0, places=12)


class TestAfterTaxVerdict(ArbTestBase):

    def test_the_same_arb_is_profit_for_a_pro_and_loss_for_a_casual_filer(self):
        """
        THE WHOLE POINT. A 5.60% cross-book arbitrage on $1,000:
          professional (delta 0.90) -> hurdle  2.91%, worst branch  +1.75%
          casual standard deduction -> hurdle 29.12%, worst branch -15.29%
        Identical position. Different filer. $170 apart.
        """
        quotes = [{"selection": "A", "book": "x", "decimal_odds": 1.9524},
                  {"selection": "B", "book": "y", "decimal_odds": 2.30}]

        professional = assess_after_tax(find_arbitrage(quotes),
                                        self._hook("professional_schedule_c"))
        self.assertTrue(professional.clears_hurdle)
        self.assertGreater(professional.worst_case_after_tax, 0.0)

        casual = assess_after_tax(find_arbitrage(quotes),
                                  self._hook("casual_standard_deduction"))
        self.assertFalse(casual.clears_hurdle)
        self.assertLess(casual.worst_case_after_tax, -0.10)
        self.assertTrue(any("after-tax hurdle" in w for w in casual.warnings))

    def test_the_worst_branch_is_the_longest_odds_leg(self):
        """
        Smallest stake, so the largest non-deductible loss. Verified by evaluating
        every branch rather than trusting the formula that picks one.
        """
        hook = self._hook("casual_standard_deduction")
        quotes = [{"selection": "F", "book": "x", "decimal_odds": 1.05},
                  {"selection": "L", "book": "y", "decimal_odds": 30.0}]
        opportunity = assess_after_tax(find_arbitrage(quotes), hook)
        tax = hook._composite_tax_rate()
        total_return = 1.0 + opportunity.gross_arb
        branches = {leg.selection:
                    (total_return - 1.0) - tax * (total_return - leg.stake_fraction)
                    for leg in opportunity.legs}
        self.assertAlmostEqual(min(branches.values()),
                               opportunity.worst_case_after_tax, places=12)
        self.assertEqual(min(branches, key=branches.get), "L")

    def test_at_the_hurdle_the_worst_branch_is_exactly_zero(self):
        """The hurdle and the worst-branch return are the same statement."""
        hook = self._hook("casual_standard_deduction")
        for legs in ([2.0, 2.0], [1.5, 3.2], [1.05, 25.0], [2.5, 3.5, 4.5]):
            with self.subTest(legs=legs):
                hurdle = hook.after_tax_arbitrage_hurdle(odds=legs)
                booksum = sum(1.0 / o for o in legs)
                stakes = [(1.0 / o) / booksum for o in legs]
                total_return = 1.0 + hurdle
                tax = hook._composite_tax_rate()
                worst = min((total_return - 1.0) - tax * (total_return - s)
                            for s in stakes)
                self.assertAlmostEqual(worst, 0.0, places=12)


class TestDatabaseScan(ArbTestBase):

    def test_an_arb_split_across_two_tables_is_found(self):
        """
        REGRESSION. `edge_opportunities` holds one row per RETAIL quote, so a
        selection only the sharp book priced has no row there at all. Scanning
        that table alone found nothing on exactly the shape that matters - one
        side best at the sharp book, the other best at a retail book.
        """
        self._ingest()
        found = scan_market_db(self._hook(), db_path=self.db, now=NOW,
                               include_rejected=True)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0].gross_arb, 0.055991, places=6)
        self.assertEqual(found[0].books, ["draftkings", "pinnacle"])

    def test_a_sub_hurdle_arb_is_hidden_unless_asked_for(self):
        self._ingest(hook=self._hook("casual_standard_deduction"))
        casual = self._hook("casual_standard_deduction")
        self.assertEqual(scan_market_db(casual, db_path=self.db, now=NOW), [])
        self.assertEqual(len(scan_market_db(casual, db_path=self.db, now=NOW,
                                            include_rejected=True)), 1)

    def test_a_settled_event_is_skipped(self):
        self._ingest()
        self.assertEqual(len(scan_market_db(self._hook(), db_path=self.db, now=NOW)), 1)
        record_settled_result("G2", "NFL", "moneyline", "", "A", 1, db_path=self.db)
        self.assertEqual(scan_market_db(self._hook(), db_path=self.db, now=NOW), [])

    def test_stale_quotes_are_dropped_before_anything_is_compared(self):
        """
        Most apparent cross-book arbs are two prices captured minutes apart, and
        the edge is the market having moved in between.
        """
        self._ingest()
        late = datetime(2026, 9, 3, 19, 0, 0)      # an hour past a 300s NFL limit
        self.assertEqual(scan_market_db(self._hook(), db_path=self.db, now=late,
                                        include_rejected=True), [])

    def test_a_market_with_no_arbitrage_reports_nothing(self):
        self._ingest(
            "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp,start_time\n"
            f"G9,NFL,moneyline,A,Pinnacle,-140,1,{QUOTED},{STARTS}\n"
            f"G9,NFL,moneyline,B,Pinnacle,+120,1,{QUOTED},{STARTS}\n"
            f"G9,NFL,moneyline,B,DraftKings,+125,0,{QUOTED},{STARTS}\n")
        self.assertEqual(scan_market_db(self._hook(), db_path=self.db, now=NOW,
                                        include_rejected=True), [])


class TestRendering(ArbTestBase):

    def test_a_cleared_arb_shows_its_stakes(self):
        self._ingest()
        text = render_arbitrage(scan_market_db(self._hook(), db_path=self.db, now=NOW),
                                bankroll=1000.0)
        self.assertIn("CLEARS", text)
        self.assertIn("pinnacle", text)
        self.assertIn("draftkings", text)
        self.assertIn("worst-branch after tax", text)

    def test_a_rejected_arb_says_what_it_would_lose(self):
        casual = self._hook("casual_standard_deduction")
        self._ingest(hook=casual)
        text = render_arbitrage(
            scan_market_db(casual, db_path=self.db, now=NOW, include_rejected=True),
            bankroll=1000.0)
        self.assertIn("BELOW HURDLE", text)
        self.assertIn("loses", text)

    def test_an_empty_scan_renders_cleanly(self):
        self.assertIn("None found.", render_arbitrage([]))


if __name__ == "__main__":
    unittest.main()
