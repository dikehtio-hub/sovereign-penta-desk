"""
Item 18 lead-lag correlator (Round 51, Directive 51-2). Offline: synthetic
timestamped drops and a temp snapshot database. The point of these tests is
that the module finds a lag that was PLANTED, in either direction, and refuses
to name one when the evidence is thin.
"""
import json
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cross_market import lead_lag as ll

MIN = 60_000
T0 = 1_788_000_000_000 - (1_788_000_000_000 % MIN)


class LeadLagCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.drops = self.root / "drops"
        self.drops.mkdir()
        self.db = self.root / "hl.db"
        con = sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE asset_snapshots (id INTEGER PRIMARY KEY, timestamp INTEGER, coin TEXT, dex TEXT, "
                    "mark_px REAL, mid_px REAL, oracle_px REAL, open_interest REAL, notional_oi REAL, funding_rate REAL, "
                    "premium REAL, day_ntl_vlm REAL)")
        con.commit()
        con.close()

    def tearDown(self):
        try:
            self.temp.cleanup()
        except (OSError, PermissionError):
            pass

    # ---- builders: six probability jumps every 90 minutes, price steps `lag` minutes after each
    def plant(self, lag_minutes: int, price_reacts: bool = True, jumps: int = 6):
        event_minutes = [40 + 90 * i for i in range(jumps)]
        prob = 0.50
        drop_index = 0
        for minute in range(0, 90 * jumps + 120, 10):                  # a drop every 10 minutes
            if minute in event_minutes:
                prob += 0.10
            (self.drops / f"polymarket_{drop_index:04d}.json").write_text(json.dumps([
                {"question": "Will X happen?", "token_id": "tok-x", "yes_price": f"{prob:.2f}",
                 "fetched_at": (T0 + minute * MIN) // 1000}]), encoding="utf-8")
            drop_index += 1
        con = sqlite3.connect(str(self.db))
        px = 100.0
        rng = random.Random(7)
        for minute in range(-80, 90 * jumps + 200):
            react = price_reacts and (minute - lag_minutes) in event_minutes
            px *= 1.02 if react else 1.0 + rng.uniform(-0.0002, 0.0002)     # a 2% step vs 2 bps noise
            for second in (0, 30):
                con.execute("INSERT INTO asset_snapshots (timestamp, coin, dex, mark_px) VALUES (?,?,?,?)",
                            (T0 + minute * MIN + second * 1000, "BTC", "main", px))
        con.commit()
        con.close()
        return event_minutes


class TestInputs(LeadLagCase):
    def test_drops_become_a_probability_series_and_shifts(self):
        self.plant(lag_minutes=10)
        records = ll.load_drop_records([self.drops])
        self.assertEqual(len(records), 66)                                 # 660 minutes / 10 + 1
        series = ll.probability_series(records)
        self.assertEqual(list(series), ["tok-x"])
        shifts = ll.probability_shifts(series, min_shift=0.02)
        self.assertEqual(len(shifts), 6)
        self.assertTrue(all(abs(s["delta"] - 0.10) < 1e-9 for s in shifts))
        self.assertEqual([s["ts_ms"] for s in shifts][:2], [T0 + 40 * MIN, T0 + 130 * MIN])
        self.assertEqual(ll.probability_shifts(series, min_shift=0.5), [])
        # Unreadable files and unpriced questions are skipped, not fatal.
        (self.drops / "junk.json").write_text("{not json", encoding="utf-8")
        (self.drops / "unpriced.json").write_text(json.dumps([{"question": "?", "fetched_at": "2026-09-04T00:00:00Z"}]),
                                                  encoding="utf-8")
        self.assertEqual(len(ll.load_drop_records([self.drops])), 66)
        self.assertEqual(ll.load_drop_records([self.root / "absent"]), [])

    def test_a_flat_csv_is_an_alternative_event_source(self):
        path = self.root / "events.csv"
        path.write_text("ts,key,probability\n2026-09-04T10:00:00Z,m1,0.5\n2026-09-04T10:10:00Z,m1,0.6\nbad,m1,x\n",
                        encoding="utf-8")
        records = ll.load_event_csv(path)
        self.assertEqual(len(records), 2)
        self.assertEqual(len(ll.probability_shifts(ll.probability_series(records))), 1)

    def test_minute_maths(self):
        marks = ll.minute_bins([(T0 + 5_000, 100.0), (T0 + 50_000, 101.0), (T0 + 3 * MIN, 102.0)])
        self.assertEqual(marks, {T0 // MIN: 101.0, T0 // MIN + 3: 102.0})     # last mark in the minute wins
        returns = ll.minute_log_returns(marks)
        self.assertEqual(list(returns), [T0 // MIN + 3])
        self.assertAlmostEqual(returns[T0 // MIN + 3], __import__("math").log(102.0 / 101.0))
        binned = ll.shift_bins([{"ts_ms": T0, "delta": 0.1}, {"ts_ms": T0 + 1, "delta": 0.05}])
        self.assertEqual(list(binned), [T0 // MIN])
        self.assertAlmostEqual(binned[T0 // MIN], 0.15)


class TestLeadLag(LeadLagCase):
    def test_a_planted_ten_minute_lag_is_found(self):
        """Price steps 10 minutes AFTER each probability jump: Polymarket leads by 10."""
        self.plant(lag_minutes=10)
        result, keys = ll.run("BTC", [self.drops], self.db, max_lag=30, min_shift=0.02, min_events=5, min_points=60)
        self.assertEqual(keys, 1)
        self.assertTrue(result["sufficient"], result["reason"])
        self.assertEqual(result["best_lag_minutes"], 10)
        self.assertGreater(result["correlation"], 0.9)
        self.assertIn("Polymarket leads HyperLiquid by 10 min", result["interpretation"])

    def test_a_planted_negative_lag_means_hyperliquid_led(self):
        """Price steps 15 minutes BEFORE each jump: the perp moved first."""
        self.plant(lag_minutes=-15)
        result, _ = ll.run("BTC", [self.drops], self.db, max_lag=30, min_shift=0.02, min_events=5, min_points=60)
        self.assertTrue(result["sufficient"], result["reason"])
        self.assertEqual(result["best_lag_minutes"], -15)
        self.assertIn("HyperLiquid leads Polymarket by 15 min", result["interpretation"])

    def test_noise_yields_no_measurable_lead_lag(self):
        self.plant(lag_minutes=10, price_reacts=False)
        result, _ = ll.run("BTC", [self.drops], self.db, max_lag=30, min_shift=0.02, min_events=5, min_points=60)
        self.assertTrue(result["sufficient"])
        self.assertLess(abs(result["correlation"]), 0.5)
        self.assertIn("no measurable lead-lag", result["interpretation"])

    def test_thin_evidence_is_refused_with_a_reason(self):
        self.plant(lag_minutes=10, jumps=2)
        result, _ = ll.run("BTC", [self.drops], self.db, max_lag=30, min_shift=0.02, min_events=5, min_points=60)
        self.assertFalse(result["sufficient"])
        self.assertIn("2 probability shifts < 5", result["reason"])
        self.assertIsNone(result["best_lag_minutes"])
        # Enough shifts but no prices at all: refused on overlap, and a missing database is "no prices".
        self.plant(lag_minutes=10)
        result, _ = ll.run("BTC", [self.drops], self.root / "absent.db", max_lag=30, min_shift=0.02,
                           min_events=5, min_points=60)
        self.assertFalse(result["sufficient"])
        self.assertIn("overlapping minutes", result["reason"])

    def test_cli_prints_a_report_and_places_nothing(self):
        import contextlib
        import io
        self.plant(lag_minutes=10)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ll.main(["--coin", "btc", "--drops", str(self.drops), "--db", str(self.db),
                                      "--max-lag", "30"]), 0)
        text = out.getvalue()
        self.assertIn("LEAD-LAG: Polymarket probability shifts vs HyperLiquid BTC returns", text)
        self.assertIn("best lag: +10 min", text)
        self.assertIn("offline research only", text)
        self.assertIn("Polymarket leads HyperLiquid by 10 min", text)


if __name__ == "__main__":
    unittest.main()
