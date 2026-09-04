"""
Unit tests for the Sports_Desk odds drop-folder watcher.

100% offline. The interesting cases are all REFUSALS - a watcher that imports
everything it is given is easy and useless, because the ways an odds file goes
wrong (a half-written export, a market with no sharp reference, a leg missing)
all produce output that looks perfectly healthy downstream.
"""
import time
import unittest
import tempfile
from pathlib import Path

from Sports_Desk.data.db import (already_imported, measure_clv, query_edges,
                                 query_latest_measurements)
from Sports_Desk.ingestors.odds_watcher import (MarketQuote, OddsImportError,
                                                OddsWatcher, content_hash,
                                                drop_stale_quotes, max_quote_age,
                                                parse_odds_csv, price_market)

SHARP_2WAY = (
    "event_id,sport,market_type,selection,book,odds,is_sharp\n"
    "NFL_KC_BAL,NFL,moneyline,Chiefs,Pinnacle,-140,1\n"
    "NFL_KC_BAL,NFL,moneyline,Ravens,Pinnacle,+120,1\n"
    "NFL_KC_BAL,NFL,moneyline,Chiefs,DraftKings,-130,0\n"
    "NFL_KC_BAL,NFL,moneyline,Ravens,DraftKings,+145,0\n"
)


class OddsWatcherTestBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.drop = self.root / "drops"
        self.drop.mkdir()
        self.db = self.root / "sports_market.db"

    def tearDown(self):
        self.temp.cleanup()

    def _drop(self, name, text):
        path = self.drop / name
        path.write_text(text, encoding="utf-8")
        return path

    def _watcher(self, **kwargs):
        return OddsWatcher(drop_folder=self.drop, db_path=self.db, **kwargs)

    def _run(self, watcher=None, **kwargs):
        """Primes the stability check, then scans for real."""
        watcher = watcher or self._watcher(**kwargs)
        watcher.scan_once()
        return watcher, watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)


class TestSharpReference(OddsWatcherTestBase):
    """Which book is the truth-teller, answered in code."""

    def test_sharp_book_is_devigged_and_retail_is_scored_against_it(self):
        """
        Pinnacle -140/+120 devigs to 0.5644 / 0.4356. DraftKings offering the
        Ravens at +145 (decimal 2.45) is therefore worth 0.4356*2.45 - 1 =
        +6.72%, and Pinnacle's own price is never scored against itself.
        """
        self._drop("week1.csv", SHARP_2WAY)
        _, reports = self._run()
        self.assertEqual(reports[0].markets_priced, 1)

        edges = query_edges(db_path=self.db)
        ravens = [e for e in edges if e["selection"] == "Ravens"][0]
        self.assertEqual(ravens["sharp_book"], "pinnacle")
        self.assertEqual(ravens["retail_book"], "draftkings")
        self.assertAlmostEqual(ravens["sharp_fair_prob"], 0.435606, places=5)
        self.assertAlmostEqual(ravens["retail_offered_odds"], 2.45, places=6)
        self.assertAlmostEqual(ravens["gross_edge"], 0.067235, places=5)
        # The sharp book is the reference, never a retail row.
        self.assertNotIn("pinnacle", {e["retail_book"] for e in edges})

    def test_a_market_with_no_sharp_book_is_refused_not_priced(self):
        """
        Devigging DraftKings yields DraftKings' opinion minus its margin, which
        is not a fair price. Pricing it anyway would report an edge against
        itself of exactly zero and look entirely reasonable.
        """
        self._drop("retail_only.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "NBA_LAL_BOS,NBA,moneyline,Lakers,DraftKings,-110,0\n"
                   "NBA_LAL_BOS,NBA,moneyline,Celtics,DraftKings,-110,0\n")
        _, reports = self._run()
        self.assertEqual(reports[0].markets_priced, 0)
        self.assertEqual(len(query_edges(db_path=self.db)), 0)
        self.assertTrue(any("no sharp book" in s for s in reports[0].skipped))

    def test_two_sharp_books_in_one_market_is_refused(self):
        """Otherwise the fair value depends on which row happened to come first."""
        quotes = [
            ("Pinnacle", "-140", True), ("Pinnacle", "+120", True),
        ]
        from Sports_Desk.ingestors.odds_watcher import MarketQuote
        market = [MarketQuote("pinnacle", "A", 1.714, True),
                  MarketQuote("pinnacle", "B", 2.20, True),
                  MarketQuote("circa", "A", 1.72, True),
                  MarketQuote("circa", "B", 2.22, True)]
        with self.assertRaises(OddsImportError) as ctx:
            price_market(market)
        self.assertIn("more than one sharp book", str(ctx.exception))

    def test_is_sharp_column_overrides_the_default_book_list(self):
        """A book not in SHARP_BOOKS can still be nominated per market."""
        self._drop("custom.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,A,MySharpBook,-140,1\n"
                   "X,NFL,moneyline,B,MySharpBook,+120,1\n"
                   "X,NFL,moneyline,B,DraftKings,+145,0\n")
        _, reports = self._run()
        self.assertEqual(reports[0].markets_priced, 1)
        self.assertEqual(query_edges(db_path=self.db)[0]["sharp_book"], "mysharpbook")

    def test_a_sharp_book_quoting_one_leg_is_refused(self):
        """
        A market missing a leg devigs cleanly and WRONGLY, and nothing in the
        numbers can reveal it - so the refusal has to happen here, where the
        market's shape is still visible.
        """
        self._drop("oneleg.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,A,Pinnacle,-140,1\n"
                   "X,NFL,moneyline,A,DraftKings,-130,0\n")
        _, reports = self._run()
        self.assertEqual(reports[0].markets_priced, 0)
        self.assertTrue(any("only 1 leg" in s for s in reports[0].skipped))

    def test_a_retail_selection_the_sharp_book_does_not_quote_is_skipped(self):
        """No fair price exists for it, so there is no edge to compute."""
        self._drop("extra.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,A,Pinnacle,-140,1\n"
                   "X,NFL,moneyline,B,Pinnacle,+120,1\n"
                   "X,NFL,moneyline,C,DraftKings,+900,0\n")
        _, reports = self._run()
        self.assertEqual(reports[0].markets_priced, 1)
        self.assertTrue(any("not in the devigged sharp set" in s
                            for s in reports[0].skipped))
        self.assertEqual(len(query_edges(db_path=self.db)), 0)


class TestWatcherMechanics(OddsWatcherTestBase):

    def test_a_file_is_not_touched_until_it_is_stable(self):
        """
        A large export is visible long before it is complete, and a truncated
        market is indistinguishable from a market with fewer legs.
        """
        self._drop("week1.csv", SHARP_2WAY)
        watcher = self._watcher()
        self.assertEqual(watcher.scan_once(), [])          # first sighting only
        self.assertEqual(watcher.scan_once(), [])          # too soon
        reports = watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)
        self.assertEqual(len(reports), 1)

    def test_a_file_that_changes_between_polls_restarts_the_clock(self):
        path = self._drop("growing.csv", SHARP_2WAY)
        watcher = self._watcher()
        watcher.scan_once()
        path.write_text(SHARP_2WAY + "NFL_KC_BAL,NFL,moneyline,Ravens,FanDuel,+112,0\n",
                        encoding="utf-8")
        # Content changed, so this is a first sighting again, not a stable one.
        self.assertEqual(watcher.scan_once(now=time.time() + 10), [])
        reports = watcher.scan_once(now=time.time() + 20)
        self.assertEqual(len(reports), 1)

    def test_reimporting_identical_bytes_is_a_no_op(self):
        """
        Identity is the file's BYTES. A name or an mtime can change without the
        content changing, and the content can change without either changing.
        """
        self._drop("week1.csv", SHARP_2WAY)
        watcher, reports = self._run()
        first = len(query_edges(db_path=self.db))
        self.assertGreater(first, 0)
        self.assertTrue(already_imported(reports[0].content_hash, db_path=self.db))

        # Same content, different filename.
        self._drop("week1_copy.csv", SHARP_2WAY)
        watcher.scan_once()
        again = watcher.scan_once(now=time.time() + 10)
        self.assertTrue(again[0].duplicate)
        self.assertEqual(len(query_edges(db_path=self.db)), first)

    def test_processed_files_are_moved_out_of_the_drop_folder(self):
        """The move is what makes the watcher re-runnable."""
        self._drop("week1.csv", SHARP_2WAY)
        self._run()
        self.assertEqual(list(self.drop.glob("*.csv")), [])
        self.assertEqual([p.name for p in (self.drop / "processed").glob("*.csv")],
                         ["week1.csv"])

    def test_a_file_that_explodes_lands_in_failed_and_does_not_stop_the_folder(self):
        self._drop("aaa_broken.csv", "not,a,valid\nodds,file,at,all,extra\n")
        self._drop("bbb_good.csv", SHARP_2WAY)
        _, reports = self._run()
        self.assertEqual(len(reports), 2)
        self.assertGreater(len(query_edges(db_path=self.db)), 0)   # the good one landed

    def test_content_hash_is_the_bytes(self):
        a = self._drop("a.csv", SHARP_2WAY)
        b = self._drop("b.csv", SHARP_2WAY)
        c = self._drop("c.csv", SHARP_2WAY + "# trailing\n")
        self.assertEqual(content_hash(a), content_hash(b))
        self.assertNotEqual(content_hash(a), content_hash(c))


class TestParsingAndSignals(OddsWatcherTestBase):

    def test_american_decimal_and_fractional_prices_all_parse(self):
        self._drop("mixed.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,A,Pinnacle,-140,1\n"
                   "X,NFL,moneyline,B,Pinnacle,+120,1\n"
                   "Y,SOCCER,1x2,A,Pinnacle,2.10,1\n"
                   "Y,SOCCER,1x2,D,Pinnacle,3.40,1\n"
                   "Y,SOCCER,1x2,B,Pinnacle,3.50,1\n"
                   "Z,GOLF,outright,A,Pinnacle,10/11,1\n"
                   "Z,GOLF,outright,B,Pinnacle,EVEN,1\n")
        markets, rows, skipped = parse_odds_csv(self.drop / "mixed.csv")
        self.assertEqual(rows, 7)
        self.assertEqual(skipped, [])
        self.assertEqual(len(markets), 3)

    def test_unreadable_rows_are_skipped_with_a_reason_not_dropped(self):
        self._drop("bad.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,A,Pinnacle,-140,1\n"
                   "X,NFL,moneyline,B,Pinnacle,chiefs,1\n")
        _, rows, skipped = parse_odds_csv(self.drop / "bad.csv")
        self.assertEqual(rows, 2)
        self.assertEqual(len(skipped), 1)
        self.assertIn("unreadable odds", skipped[0])

    def test_an_underround_sharp_market_is_reported_as_an_arbitrage(self):
        """
        Two books' best sides pasted into one sharp market sum below 1.0. That is
        the one signal a scanner most wants, and it must not be priced as if it
        were a normal market - doing so reports a positive edge on both sides.
        """
        self._drop("arb.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,A,Pinnacle,2.10,1\n"
                   "X,NFL,moneyline,B,Pinnacle,2.10,1\n")
        _, reports = self._run()
        self.assertEqual(reports[0].markets_priced, 0)
        self.assertEqual(len(reports[0].arbitrages), 1)
        self.assertIn("arbitrage", reports[0].arbitrages[0])
        self.assertEqual(len(query_edges(db_path=self.db)), 0)

    def test_book_names_are_canonicalised(self):
        """`DK` and `DraftKings` must not become two different retail books."""
        self._drop("alias.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,A,Pinnacle,-140,1\n"
                   "X,NFL,moneyline,B,Pinnacle,+120,1\n"
                   "X,NFL,moneyline,B,DK,+145,0\n")
        self._run()
        self.assertEqual(query_edges(db_path=self.db)[0]["retail_book"], "draftkings")


class TestProvenanceAndHurdle(OddsWatcherTestBase):

    def test_every_edge_row_carries_both_prices_and_the_whole_sharp_market(self):
        """An edge stored without the prices behind it cannot be audited later."""
        self._drop("week1.csv", SHARP_2WAY)
        _, reports = self._run()
        row = query_edges(db_path=self.db)[0]
        for column in ("sharp_book", "sharp_offered_odds", "sharp_fair_prob",
                       "sharp_fair_odds", "sharp_overround", "sharp_quotes_json",
                       "retail_book", "retail_offered_odds", "gross_edge",
                       "source_file", "content_hash"):
            self.assertIsNotNone(row[column], column)
        import json
        self.assertEqual(set(json.loads(row["sharp_quotes_json"])), {"Chiefs", "Ravens"})
        self.assertEqual(row["source_file"], "week1.csv")
        self.assertEqual(row["content_hash"], reports[0].content_hash)

    def test_the_sharp_market_is_also_recorded_as_a_fair_value_measurement(self):
        self._drop("week1.csv", SHARP_2WAY)
        self._run()
        measurements = query_latest_measurements("NFL_KC_BAL", db_path=self.db)
        self.assertEqual(len(measurements), 2)
        self.assertEqual(measurements[0]["sportsbook"], "pinnacle")

    def test_negative_edges_are_recorded_by_default(self):
        """
        A losing price today is the closing-line comparison tomorrow. A table
        that only kept the winners cannot answer whether the model beat the close.
        """
        self._drop("week1.csv", SHARP_2WAY)
        self._run()
        all_rows = query_edges(min_edge=-1.0, db_path=self.db)
        self.assertEqual(len(all_rows), 2)
        self.assertTrue(any(r["gross_edge"] < 0 for r in all_rows))
        self.assertEqual(len(query_edges(db_path=self.db)), 1)   # default filters to >= 0

    def test_min_edge_filters_at_write_time_when_asked(self):
        self._drop("week1.csv", SHARP_2WAY)
        self._run(self._watcher(min_edge=0.05))
        self.assertEqual(len(query_edges(min_edge=-1.0, db_path=self.db)), 1)

    def test_the_after_tax_hurdle_is_stored_and_decides_clears_hurdle(self):
        """
        THE POINT OF THE WHOLE EXERCISE. A +6.72% edge is a real edge and an
        after-tax LOSER under a casual standard deduction, where the hurdle at
        even money is 21.21%. Storing the hurdle beside the edge means nobody has
        to reconstruct which tax rules applied on the day.
        """
        self._drop("week1.csv", SHARP_2WAY)
        self._run(self._watcher(after_tax_hurdle=0.2429))
        row = query_edges(db_path=self.db)[0]
        self.assertAlmostEqual(row["gross_edge"], 0.067235, places=5)
        self.assertAlmostEqual(row["after_tax_hurdle"], 0.2429, places=6)
        self.assertEqual(row["clears_hurdle"], 0)
        self.assertEqual(query_edges(clears_hurdle_only=True, db_path=self.db), [])

        # The same edge clears once losses are deductible (professional / repeal).
        self._drop("week2.csv", SHARP_2WAY.replace("NFL_KC_BAL", "NFL_KC_BAL_2"))
        self._run(self._watcher(after_tax_hurdle=0.0308))
        cleared = query_edges(event_id="NFL_KC_BAL_2", clears_hurdle_only=True,
                              db_path=self.db)
        self.assertEqual(len(cleared), 1)

    def test_the_hurdle_is_computed_per_row_from_that_rows_odds(self):
        """
        REGRESSION. The hurdle is a FUNCTION of the odds - 16.3% at 1.50 rising to
        49.7% at +1000 - because the tax is charged on a bigger win while the loss
        still relieves nothing. Passing one number computed at even money marked
        longshots as tradeable when they were after-tax losses, and made this
        table disagree with the order gate, which always computed it per-odds.

        Reproduced: a +1600 dog with a 41.67% edge stored `clears_hurdle=1`
        against a flat 24.29%, when the true hurdle at 17.00 is 52.20%.
        """
        self._drop("longshot.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,Dog,Pinnacle,+900,1\n"
                   "X,NFL,moneyline,Fav,Pinnacle,-1400,1\n"
                   "X,NFL,moneyline,Dog,DraftKings,+1600,0\n")
        # A hurdle that rises with the odds, as the real one does.
        self._run(self._watcher(after_tax_hurdle=lambda odds: 0.10 + 0.03 * odds))
        row = query_edges(min_edge=-1.0, db_path=self.db)[0]
        self.assertAlmostEqual(row["retail_offered_odds"], 17.0, places=6)
        self.assertAlmostEqual(row["after_tax_hurdle"], 0.10 + 0.03 * 17.0, places=6)
        self.assertEqual(row["clears_hurdle"], 0)

    def test_a_flat_float_hurdle_is_still_accepted(self):
        """Back-compatible for a caller that genuinely wants one threshold."""
        self._drop("week1.csv", SHARP_2WAY)
        watcher = self._watcher(after_tax_hurdle=0.05)
        self.assertTrue(watcher._hurdle_is_flat)
        self._run(watcher)
        self.assertAlmostEqual(query_edges(db_path=self.db)[0]["after_tax_hurdle"],
                               0.05, places=6)

    def test_a_failing_hurdle_callable_records_no_hurdle_not_a_wrong_one(self):
        def broken(odds):
            raise RuntimeError("ledger unavailable")
        self._drop("week1.csv", SHARP_2WAY)
        self._run(self._watcher(after_tax_hurdle=broken))
        row = query_edges(db_path=self.db)[0]
        self.assertIsNone(row["after_tax_hurdle"])
        self.assertIsNone(row["clears_hurdle"])

    def test_no_hurdle_supplied_leaves_the_verdict_null_rather_than_guessing(self):
        self._drop("week1.csv", SHARP_2WAY)
        self._run()
        row = query_edges(db_path=self.db)[0]
        self.assertIsNone(row["after_tax_hurdle"])
        self.assertIsNone(row["clears_hurdle"])


class TestLineDimension(OddsWatcherTestBase):
    """Defect 3: the line is part of the market identity, not an attribute."""

    SPREADS = (
        "event_id,sport,market_type,line,selection,book,odds,is_sharp\n"
        "NFL_KC_BAL,NFL,spread,-3.5,Chiefs,Pinnacle,-110,1\n"
        "NFL_KC_BAL,NFL,spread,-3.5,Ravens,Pinnacle,-110,1\n"
        "NFL_KC_BAL,NFL,spread,-2.5,Chiefs,Pinnacle,+105,1\n"
        "NFL_KC_BAL,NFL,spread,-2.5,Ravens,Pinnacle,-125,1\n"
        "NFL_KC_BAL,NFL,spread,-3.5,Chiefs,DraftKings,-105,0\n"
    )

    def test_two_lines_on_one_event_are_two_markets(self):
        """
        REGRESSION. Grouping on (event, market_type) alone put Chiefs -3.5 and
        Chiefs -2.5 in one basket. That devigs a book against another book
        quoting a DIFFERENT number, and the "edge" that falls out is the
        half-point - a phantom that is largest exactly where line shopping looks
        most attractive.
        """
        self._drop("spreads.csv", self.SPREADS)
        _, reports = self._run()
        self.assertEqual(reports[0].markets_seen, 2)
        self.assertEqual(reports[0].markets_priced, 2)

        edges = query_edges(min_edge=-1.0, db_path=self.db)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["line"], "-3.5")
        # Scored against the -3.5 sharp price (1.909), not the -2.5 one.
        self.assertAlmostEqual(edges[0]["sharp_offered_odds"], 1.909090909, places=6)

    def test_the_line_column_is_not_mistaken_for_the_price(self):
        """`line` used to be an odds alias, so a -3.5 handicap parsed as odds."""
        markets, _rows, skipped = parse_odds_csv(self._drop("spreads2.csv", self.SPREADS))
        self.assertEqual(skipped, [])
        for (_event, _sport, _market, line), quotes in markets.items():
            for quote in quotes:
                self.assertGreater(quote.decimal_odds, 1.0)
                self.assertIn(line, ("-3.5", "-2.5"))

    def test_a_moneyline_has_a_blank_line_and_still_groups(self):
        self._drop("ml.csv", SHARP_2WAY)
        self._run()
        self.assertEqual(query_edges(min_edge=-1.0, db_path=self.db)[0]["line"], "")

    def test_selection_matching_tolerates_spelling_whitespace_and_case(self):
        """
        Books disagree on capitalisation and padding. Matching raw strings made a
        retail quote fail to find its sharp counterpart, which looks like a market
        nobody else quoted rather than like a bug.
        """
        self._drop("spelling.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,Chiefs,Pinnacle,-140,1\n"
                   "X,NFL,moneyline,Ravens,Pinnacle,+120,1\n"
                   "X,NFL,moneyline,  chiefs ,DraftKings,-130,0\n")
        _, reports = self._run()
        edges = query_edges(min_edge=-1.0, db_path=self.db)
        self.assertEqual(len(edges), 1)
        # The only note is the staleness one - this export carries no timestamps.
        # What matters is that nothing was rejected for selection membership.
        self.assertFalse(any("sharp set" in note for note in reports[0].skipped))

    def test_a_retail_selection_outside_the_sharp_set_names_the_set(self):
        self._drop("outsider.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp\n"
                   "X,NFL,moneyline,A,Pinnacle,-140,1\n"
                   "X,NFL,moneyline,B,Pinnacle,+120,1\n"
                   "X,NFL,moneyline,C,DraftKings,+900,0\n")
        _, reports = self._run()
        self.assertEqual(len(query_edges(min_edge=-1.0, db_path=self.db)), 0)
        self.assertTrue(any("not in the devigged sharp set" in s
                            for s in reports[0].skipped))


class TestStalenessGuard(OddsWatcherTestBase):
    """
    Item 4 P1. A stale sharp price against a live retail price is a clock
    difference, and it is the most FLATTERING possible error - the market has
    already moved to where the phantom edge says it should go.
    """

    def test_thresholds_take_the_strictest_applicable(self):
        self.assertEqual(max_quote_age("NBA", "moneyline"), 180.0)
        self.assertEqual(max_quote_age("GOLF", "outright"), 3600.0)
        # In-play on a slow sport still gets the in-play limit.
        self.assertEqual(max_quote_age("GOLF", "live"), 30.0)
        self.assertEqual(max_quote_age("CRICKET", "moneyline"), 600.0)

    def _quote(self, book, selection, odds, sharp, minutes_old):
        from datetime import datetime, timedelta
        base = datetime(2026, 9, 3, 18, 0, 0)
        return MarketQuote(book=book, selection=selection, decimal_odds=odds,
                           is_sharp=sharp, quoted_at=base - timedelta(minutes=minutes_old))

    def test_a_stale_quote_is_dropped_relative_to_the_newest_not_the_clock(self):
        """
        Relative, so a file imported the morning after a scrape is still valid as
        long as its quotes are contemporaneous with each other.
        """
        quotes = [self._quote("pinnacle", "A", 1.71, True, 0),
                  self._quote("pinnacle", "B", 2.20, True, 0),
                  self._quote("draftkings", "B", 2.30, False, 60)]     # an hour late
        fresh, notes = drop_stale_quotes(quotes, "NBA", "moneyline")
        self.assertEqual(len(fresh), 2)
        self.assertTrue(any("stale" in n for n in notes))

    def test_a_slow_sport_keeps_a_quote_a_fast_one_would_drop(self):
        quotes = [self._quote("pinnacle", "A", 1.71, True, 0),
                  self._quote("pinnacle", "B", 2.20, True, 0),
                  self._quote("draftkings", "B", 2.30, False, 20)]
        self.assertEqual(len(drop_stale_quotes(quotes, "GOLF", "outright")[0]), 3)
        self.assertEqual(len(drop_stale_quotes(quotes, "NBA", "moneyline")[0]), 2)

    def test_an_export_with_no_timestamps_is_passed_through_with_a_note(self):
        quotes = [MarketQuote("pinnacle", "A", 1.71, True),
                  MarketQuote("pinnacle", "B", 2.20, True)]
        fresh, notes = drop_stale_quotes(quotes, "NBA", "moneyline")
        self.assertEqual(len(fresh), 2)
        self.assertTrue(any("staleness unchecked" in n for n in notes))

    def test_a_market_that_loses_a_sharp_leg_to_staleness_is_unpriceable(self):
        """Not priceable-with-fewer-legs - a market missing a leg devigs wrongly."""
        self._drop("stale.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp\n"
                   "X,NBA,moneyline,A,Pinnacle,-140,1,2026-09-03T18:00:00Z\n"
                   "X,NBA,moneyline,B,Pinnacle,+120,1,2026-09-03T17:00:00Z\n"
                   "X,NBA,moneyline,B,DraftKings,+145,0,2026-09-03T18:00:00Z\n")
        _, reports = self._run()
        self.assertEqual(reports[0].markets_priced, 0)
        self.assertEqual(reports[0].stale_dropped, 1)
        self.assertTrue(any("only 1 leg" in s for s in reports[0].skipped))

    def test_contemporaneous_quotes_price_normally(self):
        self._drop("fresh.csv",
                   "event_id,sport,market_type,selection,book,odds,is_sharp,timestamp\n"
                   "X,NBA,moneyline,A,Pinnacle,-140,1,2026-09-03T18:00:00Z\n"
                   "X,NBA,moneyline,B,Pinnacle,+120,1,2026-09-03T18:00:10Z\n"
                   "X,NBA,moneyline,B,DraftKings,+145,0,2026-09-03T18:00:20Z\n")
        _, reports = self._run()
        self.assertEqual(reports[0].markets_priced, 1)
        self.assertEqual(reports[0].stale_dropped, 0)


class TestClosingLineValue(OddsWatcherTestBase):
    """Item 4 P2. CLV measured on fair probabilities, not on prices."""

    def _market(self, chiefs, ravens, closing, stamp):
        return ("event_id,sport,market_type,selection,book,odds,is_sharp,"
                "timestamp,is_closing\n"
                f"NFL_KC_BAL,NFL,moneyline,Chiefs,Pinnacle,{chiefs},1,{stamp},{closing}\n"
                f"NFL_KC_BAL,NFL,moneyline,Ravens,Pinnacle,{ravens},1,{stamp},{closing}\n")

    def test_clv_is_positive_when_the_market_moves_toward_the_selection(self):
        """
        Entry Pinnacle -140/+120; close -170/+145. The Chiefs shortened, so the
        closing market thinks they are MORE likely than it did at entry - taking
        the Chiefs beat the close.
        """
        self._drop("entry.csv", self._market("-140", "+120", 0, "2026-09-03T18:00:00Z"))
        self._run()
        self._drop("close.csv", self._market("-170", "+145", 1, "2026-09-03T20:00:00Z"))
        self._run()

        clv = {row["selection"]: row for row in measure_clv("NFL_KC_BAL", db_path=self.db)}
        chiefs = clv["Chiefs"]
        self.assertGreater(chiefs["clv_prob_delta"], 0.0)
        self.assertTrue(chiefs["beat_close"])
        self.assertAlmostEqual(chiefs["entry_fair_prob"], 0.564394, places=5)
        self.assertAlmostEqual(chiefs["closing_fair_prob"], 0.610733, places=5)
        # The other side of the same market must have moved the other way.
        self.assertLess(clv["Ravens"]["clv_prob_delta"], 0.0)
        self.assertFalse(clv["Ravens"]["beat_close"])

    def test_a_market_with_no_close_recorded_reports_rather_than_vanishes(self):
        """A caller needs to see WHICH markets are still missing a close."""
        self._drop("entry_only.csv", self._market("-140", "+120", 0, "2026-09-03T18:00:00Z"))
        self._run()
        rows = measure_clv("NFL_KC_BAL", db_path=self.db)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIsNone(row["clv_prob_delta"])
            self.assertIsNone(row["beat_close"])
            self.assertIsNotNone(row["entry_fair_prob"])

    def test_clv_pairs_by_line_so_spreads_do_not_cross_contaminate(self):
        self._drop("sp_entry.csv",
                   "event_id,sport,market_type,line,selection,book,odds,is_sharp,"
                   "timestamp,is_closing\n"
                   "E,NFL,spread,-3.5,A,Pinnacle,-110,1,2026-09-03T18:00:00Z,0\n"
                   "E,NFL,spread,-3.5,B,Pinnacle,-110,1,2026-09-03T18:00:00Z,0\n"
                   "E,NFL,spread,-2.5,A,Pinnacle,+105,1,2026-09-03T18:00:00Z,0\n"
                   "E,NFL,spread,-2.5,B,Pinnacle,-125,1,2026-09-03T18:00:00Z,0\n")
        self._run()
        lines = {(r["line"], r["selection"]) for r in measure_clv("E", db_path=self.db)}
        self.assertEqual(lines, {("-3.5", "A"), ("-3.5", "B"),
                                 ("-2.5", "A"), ("-2.5", "B")})

    def test_the_closing_flag_reaches_both_tables(self):
        self._drop("close_only.csv", self._market("-140", "+120", 1, "2026-09-03T20:00:00Z"))
        self._run()
        measurements = query_latest_measurements("NFL_KC_BAL", db_path=self.db)
        self.assertTrue(all(m["is_closing"] == 1 for m in measurements))


class TestSingleClosingLineInvariant(OddsWatcherTestBase):
    """
    Round 26h. `measure_clv` takes the LAST closing row it finds, so two
    competing closes never error - they silently pick a winner, and the CLV of
    every bet on that selection depends on which file was imported second.
    """

    def _close(self, odds, stamp, closing=True):
        from Sports_Desk.data.db import record_fair_value_measurement
        from Sports_Desk.engine.fair_value import calculate_fair_value
        record_fair_value_measurement(
            event_id="E", sport="NFL", selections=["A", "B"], market_type="moneyline",
            sportsbook="pinnacle", result=calculate_fair_value(odds),
            timestamp=stamp, is_closing=closing, db_path=self.db)

    def test_a_re_close_demotes_the_previous_one(self):
        """Books genuinely re-close a market; that must update, not collide."""
        self._close(["-140", "+120"], "2026-09-01T00:00:00Z", closing=False)
        self._close(["-150", "+130"], "2026-09-02T00:00:00Z")
        self._close(["-170", "+145"], "2026-09-03T00:00:00Z")
        import sqlite3
        conn = sqlite3.connect(self.db)
        try:
            closes = conn.execute(
                "SELECT COUNT(*) FROM fair_odds_measurements "
                "WHERE selection = 'A' AND is_closing = 1").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(closes, 1)

    def test_the_database_physically_forbids_two_closes(self):
        """The invariant is an index, not a convention."""
        import sqlite3
        self._close(["-140", "+120"], "2026-09-01T00:00:00Z", closing=False)
        self._close(["-170", "+145"], "2026-09-02T00:00:00Z")
        conn = sqlite3.connect(self.db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE fair_odds_measurements SET is_closing = 1 "
                             "WHERE timestamp = '2026-09-01T00:00:00Z'")
        finally:
            conn.close()

    def test_clv_uses_the_surviving_close(self):
        from Sports_Desk.data.db import measure_clv
        self._close(["-140", "+120"], "2026-09-01T00:00:00Z", closing=False)
        self._close(["-150", "+130"], "2026-09-02T00:00:00Z")
        self._close(["-170", "+145"], "2026-09-03T00:00:00Z")
        row = [r for r in measure_clv("E", db_path=self.db) if r["selection"] == "A"][0]
        self.assertAlmostEqual(row["entry_fair_prob"], 0.564394, places=5)
        self.assertAlmostEqual(row["closing_fair_prob"], 0.610733, places=5)

    def test_different_lines_may_each_have_their_own_close(self):
        """The invariant is per (event, market, LINE, selection), not per event."""
        from Sports_Desk.data.db import record_fair_value_measurement
        from Sports_Desk.engine.fair_value import calculate_fair_value
        for line in ("-3.5", "-2.5"):
            record_fair_value_measurement(
                event_id="S", sport="NFL", selections=["A", "B"], market_type="spread",
                sportsbook="pinnacle", result=calculate_fair_value(["-110", "-110"]),
                timestamp="2026-09-02T00:00:00Z", line=line, is_closing=True,
                db_path=self.db)
        import sqlite3
        conn = sqlite3.connect(self.db)
        try:
            closes = conn.execute(
                "SELECT COUNT(*) FROM fair_odds_measurements "
                "WHERE event_id = 'S' AND is_closing = 1").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(closes, 4)      # two lines x two selections


if __name__ == "__main__":
    unittest.main()
