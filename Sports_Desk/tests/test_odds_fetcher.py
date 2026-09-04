"""
Round 33 Target 3: the collector that gives Sports_Desk its first real row.

Sports_Desk had 680 passing tests and no database - every one built a temp
fixture, `data/odds_drops/` was empty, `sports_market.db` did not exist. These
tests pin that the fetcher's output is exactly the shape the watcher accepts,
that running the two together CREATES the database and lands priced edges in
it, and that the live path never touches the network unless asked.
"""

import csv
import io
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from Sports_Desk.data.db import query_edges
from Sports_Desk.ingestors.odds_fetcher import (COLUMNS, RETAIL_BOOKS, SHARP_BOOK,
                                                FetchError, fetch_json_rows, main,
                                                rows_to_csv, run_watcher,
                                                sample_rows, validate_rows,
                                                write_drop)
from Sports_Desk.ingestors.odds_watcher import parse_odds_csv


class FetcherBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.drop = self.root / "odds_drops"
        self.db = self.root / "sports_market.db"

    def tearDown(self):
        self.temp.cleanup()


class TestSampleShape(FetcherBase):

    def test_every_row_carries_every_column_the_watcher_reads(self):
        rows = sample_rows()
        self.assertGreater(len(rows), 20)
        for row in rows:
            for column in COLUMNS:
                self.assertIn(column, row)
            self.assertTrue(row["event_id"] and row["selection"] and row["book"] and row["odds"])

    def test_the_sample_has_a_sharp_book_on_every_market(self):
        """The watcher REFUSES a market with no sharp reference - so one must exist."""
        rows = sample_rows()
        markets = {}
        for row in rows:
            markets.setdefault((row["event_id"], row["market_type"], row["line"]), set()).add(row["book"])
        for key, books in markets.items():
            self.assertIn(SHARP_BOOK, books, key)
            self.assertTrue(books & set(RETAIL_BOOKS), key)

    def test_the_sample_is_stamped_now_so_it_is_not_stale_on_arrival(self):
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        rows = sample_rows(now=now)
        self.assertTrue(all(r["timestamp"] == "2026-09-04T12:00:00Z" for r in rows))
        self.assertTrue(all(r["start_time"] == "2026-09-04T15:00:00Z" for r in rows))

    def test_the_csv_round_trips_through_the_watchers_own_parser(self):
        path = write_drop(sample_rows(), self.drop, name="sample.csv")
        markets, rows_read, skipped = parse_odds_csv(path)
        self.assertEqual(skipped, [], skipped)
        self.assertEqual(rows_read, len(sample_rows()))
        self.assertGreaterEqual(len(markets), 6)       # 2 fixtures x 3 market types

    def test_rows_to_csv_uses_the_watchers_column_order(self):
        text = rows_to_csv(sample_rows())
        header = next(csv.reader(io.StringIO(text)))
        self.assertEqual(tuple(header), COLUMNS)


class TestEndToEnd(FetcherBase):

    def test_fetch_then_watch_creates_the_database_and_lands_edges(self):
        """
        THE POINT OF THE ROUND. Before this, `sports_market.db` did not exist.
        """
        self.assertFalse(self.db.exists())
        write_drop(sample_rows(), self.drop, name="sample.csv")
        reports = run_watcher(self.drop, self.db, archive=False)
        self.assertTrue(self.db.exists())
        self.assertEqual(len(reports), 1)
        self.assertGreater(reports[0].markets_seen, 0)
        edges = query_edges(db_path=self.db)
        self.assertGreater(len(edges), 0)
        # At least one retail quote is DELIBERATELY better than the sharp price.
        self.assertTrue(any(float(e.get("gross_edge") or 0.0) > 0 for e in edges))

    def test_the_cli_runs_offline_end_to_end(self):
        code = main(["--sample", "--folder", str(self.drop), "--db", str(self.db),
                     "--run-watcher", "--no-archive", "--name", "cli.csv"])
        self.assertEqual(code, 0)
        self.assertTrue(self.db.exists())
        self.assertTrue((self.drop / "cli.csv").exists())
        self.assertGreater(len(query_edges(db_path=self.db)), 0)

    def test_a_second_identical_drop_is_a_duplicate_not_a_double_count(self):
        write_drop(sample_rows(now=datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)),
                   self.drop, name="a.csv")
        run_watcher(self.drop, self.db, archive=False)
        before = len(query_edges(db_path=self.db))
        write_drop(sample_rows(now=datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)),
                   self.drop, name="b.csv")
        reports = run_watcher(self.drop, self.db, archive=False)
        self.assertTrue(any(r.duplicate for r in reports))
        self.assertEqual(len(query_edges(db_path=self.db)), before)


class TestLivePathIsAContract(FetcherBase):

    def test_the_offline_path_never_imports_requests(self):
        """A collector that fetched silently would tie the desk to connectivity."""
        import sys
        before = "requests" in sys.modules
        sample_rows()
        write_drop(sample_rows(), self.drop)
        if not before:
            self.assertNotIn("requests", sys.modules)

    def test_a_payload_in_the_wrong_shape_is_refused_before_anything_is_written(self):
        with self.assertRaises(FetchError):
            validate_rows({"not": "a list"})
        with self.assertRaises(FetchError):
            validate_rows([])
        with self.assertRaises(FetchError):
            validate_rows([{"event_id": "X", "selection": "A"}])     # no book, no odds

    def test_fetch_uses_the_injected_getter_and_validates(self):
        rows = fetch_json_rows("http://example.invalid", getter=lambda url, t: sample_rows())
        self.assertEqual(len(rows), len(sample_rows()))
        with self.assertRaises(FetchError):
            fetch_json_rows("http://example.invalid", getter=lambda url, t: [{"junk": 1}])


if __name__ == "__main__":
    unittest.main()
