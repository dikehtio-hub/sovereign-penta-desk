"""The reopening runner (Round 114): one source, the engine's own gate, a verdict that is INSUFFICIENT
unless every gate passes, and an artifact envelope. Small fixture, few resamples - the shape and the
decisions, not the statistics."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from analytics.fade_rebenchmark import DECISION_HORIZON, REGISTERED_HORIZONS, run

COLS = ("event_id", "coin", "timestamp_utc", "source", "mfe_5m", "mae_5m", "mfe_15m", "mae_15m",
        "mfe_30m", "mae_30m", "mfe_60m", "mae_60m")
NOW = datetime(2026, 9, 6, 19, 0, tzinfo=timezone.utc)


def seed(db: Path, rows):
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE cascade_excursions (%s)" % ", ".join(COLS))
    conn.executemany("INSERT INTO cascade_excursions VALUES (%s)" % ",".join("?" * len(COLS)), rows)
    conn.commit()
    conn.close()


def rows(source, n, coins, span_days, mfe, mae, dominant=None, start_id=1):
    """n treatment rows plus n matched controls (source control:<src>), spread across coins and time."""
    start = int((NOW - timedelta(days=span_days)).timestamp() * 1000)
    step = int(span_days * 86_400_000 // n)
    out = []
    for i in range(n):
        coin = dominant if (dominant and i < n // 3) else f"C{i % coins}"
        ts = start + i * step
        out.append((start_id + i, coin, ts, source, mfe, mae, mfe, mae, mfe, mae, mfe, mae))
        out.append((-(start_id + i), coin, ts, "control:" + source, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0))
    return out


class TestFadeRebenchmark(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "hl.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_broad_favourable_sample_passes_the_bar(self):
        seed(self.db, rows("trade_sweep", 600, 25, 8.0, mfe=2.0, mae=1.0))
        r = run(self.db, source="trade_sweep", resamples=300)
        self.assertEqual(r["verdict"], "PASS", r["verdict_reasons"])
        self.assertEqual(r["source"], "trade_sweep")
        self.assertEqual(r["decision_horizon_minutes"], DECISION_HORIZON)
        self.assertEqual(r["registered_horizons_minutes"], list(REGISTERED_HORIZONS))
        pm = r["primary_metric"]
        self.assertAlmostEqual(pm["value"], 2.0, places=6)
        self.assertGreater(pm["cluster_p_ge_1_25"], 0.9)
        self.assertTrue(r["sample_gates"]["engine"]["eligible"])
        self.assertTrue(r["sample_gates"]["metrics"]["window_covered"])
        self.assertEqual(set(r["horizons"]), {"5m", "15m", "30m", "60m"})
        self.assertFalse(r["horizons"]["60m"]["registered"])
        for k in ("written_at", "writer", "rows_in_table", "seed", "resamples"):
            self.assertIn(k, r["_artifact"])

    def test_one_dominant_coin_is_insufficient_not_a_fail(self):
        seed(self.db, rows("trade_sweep", 600, 25, 8.0, mfe=2.0, mae=1.0, dominant="WHALE"))   # WHALE at 33%
        r = run(self.db, source="trade_sweep", resamples=100)
        self.assertEqual(r["verdict"], "INSUFFICIENT")
        self.assertTrue(any("SAMPLE_TOO_NARROW" in x for x in r["verdict_reasons"]))
        self.assertEqual(r["sample_gates"]["metrics"]["top_coin"], "WHALE")
        self.assertGreater(r["primary_metric"]["cluster_p_ge_1_25"], 0.9)    # the number is there; it is not a verdict

    def test_a_short_window_is_insufficient_and_the_engine_gate_says_so(self):
        """Round 115 (R114-1.F): the engine gate checks the covered span; runner and page can no longer disagree."""
        seed(self.db, rows("trade_sweep", 600, 25, 5.0, mfe=2.0, mae=1.0))
        r = run(self.db, source="trade_sweep", resamples=100)
        self.assertEqual(r["verdict"], "INSUFFICIENT")
        self.assertFalse(r["sample_gates"]["engine"]["eligible"])             # n, coins, share fine; span is not
        self.assertIn("span", r["sample_gates"]["engine"]["detail"])
        self.assertFalse(r["sample_gates"]["metrics"]["window_covered"])
        self.assertTrue(any("span" in x for x in r["verdict_reasons"]))

    def test_an_adverse_sample_fails_the_bar(self):
        seed(self.db, rows("trade_sweep", 600, 25, 8.0, mfe=0.8, mae=1.0))
        r = run(self.db, source="trade_sweep", resamples=100)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertEqual(r["primary_metric"]["cluster_p_ge_1_25"], 0.0)

    def test_the_other_source_is_never_pooled_in(self):
        seed(self.db, rows("trade_sweep", 300, 25, 8.0, mfe=2.0, mae=1.0)
             + rows("trade_flow", 600, 25, 8.0, mfe=2.0, mae=1.0, start_id=10_000))
        r = run(self.db, source="trade_sweep", resamples=50)
        self.assertEqual(r["sample_gates"]["metrics"]["events"], 300)
        self.assertEqual(r["data_audit"]["treatment_rows"], 300)
        self.assertEqual(r["data_audit"]["total_in_table"], 1800)             # both sources and both controls
        self.assertEqual(r["verdict"], "INSUFFICIENT")                        # 300 < 500 over the registered source


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
