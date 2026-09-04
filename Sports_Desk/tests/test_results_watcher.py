"""
Unit tests for the Sports_Desk results watcher and Brier calibration.

100% offline. The scoring tests use fixtures with an ANALYTIC answer - a forecast
of 1.0 on an event that happened scores exactly 0, a forecast of 0.5 scores
exactly 0.25 - rather than whatever the implementation emits, because a
calibration metric is easy to write and almost impossible to eyeball.
"""
import tempfile
import time
import unittest
from pathlib import Path

from Sports_Desk.data.db import (already_imported_result, brier_score,
                                 init_market_db, query_brier_snapshots,
                                 query_results, record_settled_result,
                                 scored_forecasts, settled_event_ids)
from Sports_Desk.ingestors.odds_watcher import OddsWatcher
from Sports_Desk.ingestors.results_watcher import (ResultImportError, ResultsWatcher,
                                                   parse_outcome, parse_results_csv)

ODDS = (
    "event_id,sport,market_type,selection,book,odds,is_sharp\n"
    "G1,NFL,moneyline,Chiefs,Pinnacle,-140,1\n"
    "G1,NFL,moneyline,Ravens,Pinnacle,+120,1\n"
)
RESULTS = (
    "event_id,sport,market_type,selection,result,settled_at\n"
    "G1,NFL,moneyline,Chiefs,win,2026-09-04T02:00:00Z\n"
    "G1,NFL,moneyline,Ravens,loss,2026-09-04T02:00:00Z\n"
)


class ResultsTestBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.odds_drop = self.root / "odds"
        self.results_drop = self.root / "results"
        self.odds_drop.mkdir()
        self.results_drop.mkdir()
        self.db = self.root / "sports_market.db"
        init_market_db(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def _drop(self, folder, name, text):
        path = folder / name
        path.write_text(text, encoding="utf-8")
        return path

    def _run_odds(self, text=ODDS, name="odds.csv"):
        self._drop(self.odds_drop, name, text)
        watcher = OddsWatcher(drop_folder=self.odds_drop, db_path=self.db)
        watcher.scan_once()
        return watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)

    def _run_results(self, text=RESULTS, name="results.csv", watcher=None, **kwargs):
        self._drop(self.results_drop, name, text)
        watcher = watcher or ResultsWatcher(drop_folder=self.results_drop,
                                            db_path=self.db, **kwargs)
        watcher.scan_once()
        return watcher, watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)


class TestOutcomeParsing(unittest.TestCase):

    def test_the_three_settlement_classes(self):
        for word in ("win", "WON", "w", "1", "hit"):
            self.assertEqual(parse_outcome(word), (1, False))
        for word in ("loss", "LOST", "l", "0", "miss"):
            self.assertEqual(parse_outcome(word), (0, False))
        for word in ("push", "VOID", "tie", "no action", "postponed"):
            self.assertEqual(parse_outcome(word), (0, True))

    def test_an_unknown_result_is_refused_not_guessed(self):
        """
        A misread result is worse than an absent one: it scores a forecast against
        something that did not happen, and the error is invisible afterwards.
        """
        for word in ("maybe", "", "pending", "half"):
            with self.subTest(word=word):
                with self.assertRaises(ResultImportError):
                    parse_outcome(word)


class TestResultsIngestion(ResultsTestBase):

    def test_settling_records_outcomes_and_leaves_forecasts_alone(self):
        self._run_odds()
        _, reports = self._run_results()
        self.assertEqual(reports[0].settled, 2)
        self.assertEqual(reports[0].voided, 0)

        results = query_results("G1", db_path=self.db)
        self.assertEqual({r["selection"]: r["outcome"] for r in results},
                         {"Chiefs": 1, "Ravens": 0})
        # The forecast is untouched - a score against an edited forecast is worthless.
        forecasts = scored_forecasts(db_path=self.db)
        self.assertEqual(len(forecasts), 2)

    def test_a_push_is_recorded_but_never_scored(self):
        """
        Squaring a forecast against a push is not a small error, it is a category
        error - there was no outcome, so there is nothing to be right or wrong
        about, and including it drags a real score toward the mean.
        """
        self._run_odds()
        _, reports = self._run_results(
            "event_id,sport,market_type,selection,result\n"
            "G1,NFL,moneyline,Chiefs,push\n"
            "G1,NFL,moneyline,Ravens,loss\n")
        self.assertEqual(reports[0].voided, 1)
        self.assertEqual(reports[0].settled, 1)
        scored = scored_forecasts(db_path=self.db)
        self.assertEqual([f["selection"] for f in scored], ["Ravens"])

    def test_re_settling_replaces_rather_than_duplicates(self):
        """Books correct results. One selection has one outcome."""
        self._run_odds()
        record_settled_result("G1", "NFL", "moneyline", "", "Chiefs", 1, db_path=self.db)
        record_settled_result("G1", "NFL", "moneyline", "", "Chiefs", 0, db_path=self.db)
        rows = query_results("G1", db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], 0)

    def test_reimporting_identical_bytes_is_a_no_op(self):
        self._run_odds()
        watcher, reports = self._run_results()
        self.assertTrue(already_imported_result(reports[0].content_hash, db_path=self.db))
        self._drop(self.results_drop, "copy.csv", RESULTS)
        watcher.scan_once()
        again = watcher.scan_once(now=time.time() + 10)
        self.assertTrue(again[0].duplicate)

    def test_unreadable_rows_are_skipped_with_a_reason(self):
        self._run_odds()
        _, reports = self._run_results(
            "event_id,sport,market_type,selection,result\n"
            "G1,NFL,moneyline,Chiefs,win\n"
            "G1,NFL,moneyline,Ravens,maybe\n")
        self.assertEqual(reports[0].settled, 1)
        self.assertEqual(len(reports[0].skipped), 1)
        self.assertIn("unknown result", reports[0].skipped[0])

    def test_a_file_is_not_touched_until_it_is_stable(self):
        self._drop(self.results_drop, "r.csv", RESULTS)
        watcher = ResultsWatcher(drop_folder=self.results_drop, db_path=self.db)
        self.assertEqual(watcher.scan_once(), [])
        reports = watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)
        self.assertEqual(len(reports), 1)

    def test_processed_files_are_archived(self):
        self._run_odds()
        self._run_results()
        self.assertEqual(list(self.results_drop.glob("*.csv")), [])
        self.assertEqual([p.name for p in (self.results_drop / "processed").glob("*.csv")],
                         ["results.csv"])

    def test_settled_event_ids_feeds_the_hotlist_filter(self):
        self._run_odds()
        self.assertEqual(settled_event_ids(db_path=self.db), set())
        self._run_results()
        self.assertEqual(settled_event_ids(db_path=self.db), {"G1"})

    def test_a_result_whose_key_does_not_match_a_forecast_scores_nothing(self):
        """
        The join is on (event, market_type, line, selection). A mismatch is not an
        error - results arrive for markets the desk never priced - but it must
        score nothing rather than score something adjacent.
        """
        self._run_odds()
        self._run_results(
            "event_id,sport,market_type,line,selection,result\n"
            "G1,NFL,spread,-3.5,Chiefs,win\n")
        self.assertEqual(scored_forecasts(db_path=self.db), [])


class TestBrierCalibration(ResultsTestBase):
    """Fixtures with answers derivable by hand."""

    def _forecast(self, event, selection, fair_prob, outcome):
        """Writes one measurement and its outcome directly, bypassing devigging."""
        from Sports_Desk.data.db import record_fair_value_measurement
        from Sports_Desk.engine.fair_value import calculate_fair_value
        other = 1.0 - fair_prob
        result = calculate_fair_value([1.0 / fair_prob, 1.0 / other])
        # calculate_fair_value refuses a zero-vig book, so nudge the other leg.
        record_fair_value_measurement(
            event_id=event, sport="NFL", selections=[selection, "OTHER"],
            market_type="moneyline", sportsbook="testbook", result=result,
            db_path=self.db)
        record_settled_result(event, "NFL", "moneyline", "", selection, outcome,
                              db_path=self.db)

    def test_a_perfect_forecast_scores_zero(self):
        """Brier is mean squared error; certainty that was right costs nothing."""
        record_settled_result("E1", "NFL", "moneyline", "", "A", 1, db_path=self.db)
        self._raw_measurement("E1", "A", 1.0)
        score = brier_score(db_path=self.db)
        self.assertAlmostEqual(score["brier"], 0.0, places=12)

    def test_a_coin_flip_forecast_scores_a_quarter(self):
        for index, outcome in enumerate((1, 0, 1, 0)):
            record_settled_result(f"E{index}", "NFL", "moneyline", "", "A", outcome,
                                  db_path=self.db)
            self._raw_measurement(f"E{index}", "A", 0.5)
        score = brier_score(db_path=self.db)
        self.assertAlmostEqual(score["brier"], 0.25, places=12)

    def test_skill_is_measured_against_the_base_rate_not_against_zero(self):
        """
        A raw Brier flatters anyone forecasting lopsided markets - predicting a
        field of heavy favourites scores well by saying nothing. The skill score
        is what makes it mean something.
        """
        # Four events, three of which happened. Base rate 0.75.
        for index, outcome in enumerate((1, 1, 1, 0)):
            record_settled_result(f"B{index}", "NFL", "moneyline", "", "A", outcome,
                                  db_path=self.db)
            self._raw_measurement(f"B{index}", "A", 0.75)
        score = brier_score(db_path=self.db)
        # Forecasting exactly the base rate has, by construction, zero skill.
        self.assertAlmostEqual(score["base_rate"], 0.75, places=12)
        self.assertAlmostEqual(score["brier"], score["baseline_brier"], places=12)
        self.assertAlmostEqual(score["skill_score"], 0.0, places=12)

    def test_a_better_than_base_rate_forecaster_has_positive_skill(self):
        for index, outcome in enumerate((1, 1, 1, 0)):
            record_settled_result(f"C{index}", "NFL", "moneyline", "", "A", outcome,
                                  db_path=self.db)
            self._raw_measurement(f"C{index}", "A", 0.95 if outcome else 0.05)
        score = brier_score(db_path=self.db)
        self.assertGreater(score["skill_score"], 0.9)

    def test_no_settled_forecasts_reports_none_rather_than_zero(self):
        """Zero would read as a perfect score. There is simply nothing to say."""
        score = brier_score(db_path=self.db)
        self.assertEqual(score["forecasts"], 0)
        self.assertIsNone(score["brier"])
        self.assertIsNone(score["skill_score"])

    def test_the_window_limits_the_score_to_recent_history(self):
        for index in range(10):
            record_settled_result(f"W{index}", "NFL", "moneyline", "", "A", 1,
                                  settled_at=f"2026-09-{index + 1:02d}T00:00:00Z",
                                  db_path=self.db)
            self._raw_measurement(f"W{index}", "A", 1.0)
        self.assertEqual(brier_score(db_path=self.db)["forecasts"], 10)
        self.assertEqual(brier_score(window=3, db_path=self.db)["forecasts"], 3)

    def test_a_snapshot_is_only_frozen_with_enough_history(self):
        """Below the floor a Brier is noise wearing a decimal point."""
        self._run_odds()
        _, reports = self._run_results(watcher=ResultsWatcher(
            drop_folder=self.results_drop, db_path=self.db, min_forecasts=50))
        self.assertEqual(query_brier_snapshots(db_path=self.db), [])

        watcher = ResultsWatcher(drop_folder=self.results_drop, db_path=self.db,
                                 min_forecasts=1)
        watcher.rescore()
        self.assertGreater(len(query_brier_snapshots(db_path=self.db)), 0)

    def test_the_closing_forecast_is_the_one_scored(self):
        """
        The close is the market's final word. Scoring an early price measures how
        much the line moved, not how good the book is.
        """
        from Sports_Desk.data.db import record_fair_value_measurement
        from Sports_Desk.engine.fair_value import calculate_fair_value
        early = calculate_fair_value([1.60, 2.60])
        late = calculate_fair_value([1.20, 5.20])
        for result, closing, stamp in ((early, False, "2026-09-01T00:00:00Z"),
                                       (late, True, "2026-09-02T00:00:00Z")):
            record_fair_value_measurement(
                event_id="CL", sport="NFL", selections=["A", "B"],
                market_type="moneyline", sportsbook="testbook", result=result,
                timestamp=stamp, is_closing=closing, db_path=self.db)
        record_settled_result("CL", "NFL", "moneyline", "", "A", 1, db_path=self.db)
        scored = scored_forecasts(db_path=self.db)
        self.assertEqual(len(scored), 1)
        self.assertAlmostEqual(scored[0]["fair_prob"], late.fair_probabilities[0],
                               places=10)

    def _raw_measurement(self, event, selection, fair_prob):
        """Writes one measurement at an exact fair probability, bypassing devigging."""
        import sqlite3
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("""
                INSERT INTO fair_odds_measurements
                (timestamp, event_id, sport, market_type, line, sportsbook,
                 raw_quotes_json, selection, offered_odds, implied_prob_raw,
                 fair_prob, fair_odds, expected_value, quarter_kelly, overround,
                 shin_z, power_k, divergent, max_oracle_delta, is_closing, is_live)
                VALUES (?, ?, 'NFL', 'moneyline', '', 'testbook', '{}', ?, 2.0, ?,
                        ?, ?, 0.0, 0.0, 0.05, 0.0, 1.0, 0, 0.0, 1, 0)
            """, (f"2026-09-01T00:00:00Z", event, selection, fair_prob, fair_prob,
                  1.0 / fair_prob if fair_prob else 0.0))
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
