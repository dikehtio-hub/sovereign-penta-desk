"""
DEFECT-COL-001: the collector must not lose trade batches to "database is locked".

On 2026-09-16 the collector logged 393 "database is locked" errors and dropped
~2,794 trades in the three minutes around the FOMC print. Three causes, one test
class each:

  1. prune_old_data ran all five DELETEs in ONE transaction, holding SQLite's
     single writer for the length of a retention backlog on an 8.5 GB file.
  2. _flush_buffers_sync logged the failure and returned - and _flush_loop had
     already swapped the buffers out, so the rows were gone. "database is locked"
     is transient by definition; dropping on it is never right.
  3. run_maintenance followed the prune with a blocking TRUNCATE checkpoint.

The regression that matters is test_failed_flush_rows_are_not_lost: it fails
against the old code, which is the whole point.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from storage.db import DatabaseManager
from storage.repository import MarketRepository
from config import settings


HOUR_MS = 3600 * 1000


def _trade(coin: str, t: int) -> Dict[str, Any]:
    return {"tid": t, "coin": coin, "side": "B", "px": 100.0, "sz": 1.0, "notional": 100.0,
            "time": t, "hash": f"0x{t:064x}", "is_liquidation": 0}


def _liq(coin: str, t: int) -> Dict[str, Any]:
    return {"coin": coin, "side": "B", "px": 1.0, "sz": 1.0, "notional": 1.0,
            "time": t, "source": "test", "note": ""}


class TestChunkedPrune(unittest.TestCase):
    """Cause 1: the prune must release the write lock between chunks."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.temp_dir.name) / "col001.db")
        self.repo = MarketRepository(self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def _insert_expired(self, n: int, now_ms: int) -> None:
        old = now_ms - int((settings.TRADE_RETENTION_HOURS + 24) * HOUR_MS)
        self.repo.insert_trades([_trade("BTC", old + i) for i in range(n)])

    def test_delete_limit_is_not_available_so_the_rowid_form_is_required(self):
        """The reason _prune_chunked is written the way it is. If this ever starts
        passing, the simpler `DELETE ... LIMIT` becomes available - but the rowid
        form stays correct either way."""
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE t(a)")
        with self.assertRaises(sqlite3.OperationalError):
            con.execute("DELETE FROM t WHERE a < 1 LIMIT 5")

    def test_prune_deletes_everything_expired_across_many_chunks(self):
        import time
        now_ms = int(time.time() * 1000)
        self._insert_expired(1200, now_ms)
        self.assertEqual(self._count(), 1200)
        settings.DB_PRUNE_CHUNK_ROWS = 100          # 12 chunks
        settings.DB_PRUNE_CHUNK_PAUSE = 0.0
        import storage.repository as R
        R.DB_PRUNE_CHUNK_ROWS, R.DB_PRUNE_CHUNK_PAUSE = 100, 0.0
        deleted = self.repo.prune_old_data(persist_first=False)
        self.assertEqual(self._count(), 0)
        self.assertEqual(deleted["trades"], 1200)
        self.assertEqual(self.repo.last_prune_truncated, [])

    def test_prune_stops_at_the_ceiling_and_says_so(self):
        """A bounded prune is better than a blocked writer: the remainder ages out
        next pass, and the caller is told which tables were cut short."""
        import time
        import storage.repository as R
        now_ms = int(time.time() * 1000)
        self._insert_expired(500, now_ms)
        R.DB_PRUNE_CHUNK_ROWS, R.DB_PRUNE_MAX_CHUNKS, R.DB_PRUNE_CHUNK_PAUSE = 100, 2, 0.0
        deleted = self.repo.prune_old_data(persist_first=False)
        self.assertEqual(deleted["trades"], 200)              # 2 chunks x 100
        self.assertEqual(self._count(), 300)                  # remainder survives
        self.assertIn("trades", self.repo.last_prune_truncated)

    def test_a_writer_can_take_the_lock_between_chunks(self):
        """The point of the whole change. A second connection writes while the
        prune is running; under the old single-transaction prune it could not."""
        import time
        import storage.repository as R
        now_ms = int(time.time() * 1000)
        self._insert_expired(400, now_ms)
        R.DB_PRUNE_CHUNK_ROWS, R.DB_PRUNE_MAX_CHUNKS, R.DB_PRUNE_CHUNK_PAUSE = 100, 100, 0.0

        other = sqlite3.connect(str(self.db._db_path), timeout=2.0)
        other.execute("PRAGMA busy_timeout = 2000;")
        wrote: List[int] = []
        real_sleep_hook = self.repo._prune_chunked

        def chunked_then_write(table, sql, cutoff):
            result = real_sleep_hook(table, sql, cutoff)
            with other:                                        # between chunks
                other.execute(
                    "INSERT OR IGNORE INTO trades "
                    "(tid, coin, side, px, sz, notional, time, hash, is_liquidation) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (999999, "ETH", "B", 1.0, 1.0, 1.0, now_ms, "0xlive", 0))
            wrote.append(1)
            return result

        self.repo._prune_chunked = chunked_then_write
        self.repo.prune_old_data(persist_first=False)
        other.close()
        self.assertTrue(wrote, "the concurrent writer never ran")
        row = self.db.connection.execute(
            "SELECT COUNT(*) FROM trades WHERE coin = 'ETH'").fetchone()[0]
        self.assertEqual(row, 1, "a writer could not land a row around the prune")

    def _count(self) -> int:
        return self.db.connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0]


class TestFlushRetry(unittest.TestCase):
    """Cause 2: a failed flush must re-buffer, never drop. THE regression test."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.temp_dir.name) / "flush.db")
        self.repo = MarketRepository(self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def _collector(self):
        """A MarketCollector shell with only what the flush path touches."""
        from collectors.market_collector import MarketCollector
        c = MarketCollector.__new__(MarketCollector)
        c.repo = self.repo
        c._trade_buffer = []
        c._liq_buffer = []
        c._dropped_rows = 0
        return c

    def test_failed_flush_rows_are_not_lost(self):
        """Against the old code this fails: _flush_buffers_sync returned None and
        the caller had already emptied the buffer, so the rows were gone."""
        c = self._collector()
        rows = [_trade("BTC", 1_000 + i) for i in range(50)]

        def locked(_rows):
            raise sqlite3.OperationalError("database is locked")

        c.repo.insert_trades = locked
        failed_trades, failed_liqs = c._flush_buffers_sync(rows, [])
        self.assertEqual(len(failed_trades), 50, "the rows must come back for re-buffering")
        self.assertEqual(failed_liqs, [])

    def test_a_lock_on_one_table_does_not_discard_the_other(self):
        c = self._collector()
        trades = [_trade("BTC", 2_000 + i) for i in range(10)]
        liqs = [_liq("BTC", 2_000)]

        def locked(_rows):
            raise sqlite3.OperationalError("database is locked")

        c.repo.insert_trades = locked                       # only trades fail
        failed_trades, failed_liqs = c._flush_buffers_sync(trades, liqs)
        self.assertEqual(len(failed_trades), 10)
        self.assertEqual(failed_liqs, [], "liq events landed and must not be re-queued")

    def test_a_successful_flush_returns_nothing_to_retry(self):
        c = self._collector()
        rows = [_trade("BTC", 3_000 + i) for i in range(5)]
        failed_trades, failed_liqs = c._flush_buffers_sync(rows, [])
        self.assertEqual((failed_trades, failed_liqs), ([], []))
        n = self.db.connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        self.assertEqual(n, 5)


class TestCheckpointMode(unittest.TestCase):
    """Cause 3: the periodic checkpoint must not block writers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        DatabaseManager._instance = None
        self.db = DatabaseManager(Path(self.temp_dir.name) / "wal.db")
        self.repo = MarketRepository(self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_small_wal_uses_passive(self):
        stats = self.repo.run_maintenance()
        self.assertEqual(stats["checkpoint_mode"], "PASSIVE")

    def test_large_wal_escalates_to_truncate(self):
        """So the WAL cannot grow without bound when a reader pins it."""
        import storage.repository as R
        original = R.WAL_TRUNCATE_ABOVE_BYTES
        try:
            R.WAL_TRUNCATE_ABOVE_BYTES = 0                  # everything is "large"
            stats = self.repo.run_maintenance()
            self.assertEqual(stats["checkpoint_mode"], "TRUNCATE")
        finally:
            R.WAL_TRUNCATE_ABOVE_BYTES = original

    def test_wal_bytes_is_reported_and_non_negative(self):
        self.assertGreaterEqual(self.db.wal_bytes(), 0)
        stats = self.repo.run_maintenance()
        self.assertGreaterEqual(stats["wal_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
