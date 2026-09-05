"""
Item 18 lead-lag correlator (Round 51, Directive 51-2). Offline: synthetic
timestamped drops and a temp snapshot database. The point of these tests is
that the module finds a lag that was PLANTED, in either direction, and refuses
to name one when the evidence is thin.
"""
import json
from datetime import datetime, timedelta, timezone
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


class TestReadiness(LeadLagCase):
    """
    Round 56 (Directive 56-2). The sentinel answers "is the stamped series
    enough for an honest first run?" from file names alone: only the latest
    continuous segment counts, a stalled watcher is not accumulating, and the
    ETA is the later of the span clock and the points clock.
    """
    NOW = datetime(2026, 9, 6, 3, 0, tzinfo=timezone.utc)

    def every_5_min(self, points, ending_minutes_ago=3):
        end = self.NOW - timedelta(minutes=ending_minutes_ago)
        return [end - timedelta(minutes=5 * i) for i in range(points)][::-1]

    def test_no_stamps_is_not_ready_with_no_eta(self):
        info = ll.data_readiness([], now=self.NOW)
        self.assertFalse(info["ready"])
        self.assertEqual(info["reasons"], ["no stamped drops"])
        self.assertIsNone(info["eta"])
        self.assertIn("NOT READY", ll.format_readiness(info, "macro"))

    def test_a_full_continuous_day_is_ready(self):
        stamps = self.every_5_min(300)                                      # 24.9h, 300 points, 5-min spacing
        info = ll.data_readiness(stamps, now=self.NOW)
        self.assertTrue(info["ready"])
        self.assertEqual((info["points"], info["points_total"], info["breaks"]), (300, 300, 0))
        self.assertAlmostEqual(info["span_hours"], 24.92, places=2)
        self.assertEqual(info["largest_gap_min"], 5.0)
        self.assertEqual(info["rate_per_hour"], 12.0)
        self.assertIsNone(info["eta"])
        self.assertIn("READY - the first live", ll.format_readiness(info, "macro"))

    def test_a_hole_restarts_the_segment_and_the_eta_is_the_later_clock(self):
        recent = self.every_5_min(49)                                       # 4h after the hole
        older = [recent[0] - timedelta(hours=3) - timedelta(minutes=5 * i) for i in range(200)]
        info = ll.data_readiness(sorted(older + recent), now=self.NOW)
        self.assertFalse(info["ready"])
        self.assertEqual((info["points"], info["points_total"], info["breaks"]), (49, 249, 1))
        self.assertEqual(info["largest_gap_min"], 180.0)
        self.assertEqual(info["segment_start"], recent[0].isoformat())
        self.assertEqual(info["reasons"], ["span 4.0h < 24h", "points 49 < 200"])
        # points clock: (200-49)/12 = 12.6h from now; span clock: segment start + 24h = 24h - 4h - 3min
        # from now -> later. The ETA is the span clock.
        self.assertEqual(info["eta"], (recent[0] + timedelta(hours=24)).isoformat())
        text = ll.format_readiness(info, "macro")
        self.assertIn("1 break(s) > 60 min", text)
        self.assertIn("ETA " + info["eta"], text)

    def test_the_points_clock_wins_when_stamps_are_sparse(self):
        stamps = [self.NOW - timedelta(hours=30) + timedelta(hours=i) for i in range(30)]   # hourly, 29h span
        info = ll.data_readiness(stamps, now=self.NOW, max_gap_minutes=90)
        self.assertEqual(info["reasons"], ["points 30 < 200"])
        self.assertEqual(info["rate_per_hour"], 1.0)
        self.assertEqual(info["eta"], (self.NOW + timedelta(hours=170)).isoformat())

    def test_a_stalled_watcher_is_not_ready_and_has_no_eta(self):
        stamps = self.every_5_min(300, ending_minutes_ago=150)              # enough data, but 2.5h silent
        info = ll.data_readiness(stamps, now=self.NOW)
        self.assertFalse(info["ready"])
        self.assertEqual(len(info["reasons"]), 1)
        self.assertIn("not adding", info["reasons"][0])
        self.assertIsNone(info["eta"])
        self.assertIn("restart the watcher", ll.format_readiness(info, "macro"))

    def test_stamped_moments_reads_names_per_family_and_the_cli_exit_codes(self):
        from unittest import mock
        from cross_market.ingestors.polymarket_fetcher import stamped_drop_name
        base = datetime.now(timezone.utc) - timedelta(minutes=30)
        for i in range(3):
            (self.drops / stamped_drop_name(base + timedelta(minutes=10 * i), family="macro")).write_text("[]")
        (self.drops / stamped_drop_name(base, family="sports")).write_text("[]")
        (self.drops / stamped_drop_name(base + timedelta(minutes=5))).write_text("[]")     # unprefixed = sports
        (self.drops / "polymarket_macro.json").write_text("[]")                              # canonical: not a stamp
        (self.drops / "polymarket_0001.json").write_text("[]")                               # Round 51 fixture name
        self.assertEqual(len(ll.stamped_moments([self.drops], "macro")), 3)
        self.assertEqual(len(ll.stamped_moments([self.drops], "sports")), 2)
        moments = ll.stamped_moments([self.drops, self.root / "missing"], "any")
        self.assertEqual(moments, sorted(moments))
        self.assertEqual(len(moments), 5)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ll.main(["--check-data", "--drops", str(self.drops)]), ll.EXIT_NOT_READY)
        self.assertIn("NOT READY", fake_print.call_args_list[0].args[0])
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ll.main(["--status", "--drops", str(self.drops), "--min-span-hours", "0.1",
                                      "--min-ready-points", "3"]), 0)
        self.assertIn("READY - the first live", fake_print.call_args_list[0].args[0])
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ll.main(["--check-data", "--json", "--family", "sports", "--drops", str(self.drops)]),
                             ll.EXIT_NOT_READY)
        parsed = json.loads(fake_print.call_args_list[0].args[0])
        self.assertEqual((parsed["points"], parsed["ready"]), (2, False))


class TestLiveGate(LeadLagCase):
    """Round 57 (Directive 57-2): the live drop dirs are gated behind the sentinel; --force opens it."""

    def test_unforced_live_runs_refuse_until_the_sentinel_is_ready(self):
        from unittest import mock
        with mock.patch.object(ll, "DEFAULT_DROP_DIRS", [self.drops]), mock.patch("builtins.print") as fake_print:
            self.assertEqual(ll.main(["--db", str(self.db)]), ll.EXIT_NOT_READY)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("[GATE]", printed)
        self.assertIn("NOT READY", printed)
        with mock.patch.object(ll, "DEFAULT_DROP_DIRS", [self.drops]), mock.patch("builtins.print") as fake_print:
            self.assertEqual(ll.main(["--db", str(self.db), "--force"]), 0)     # forced: runs (and finds nothing)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertNotIn("[GATE]", printed)
        # Explicit --drops is research data and is never gated (the Round 51 tests rely on it).
        with mock.patch.object(ll, "DEFAULT_DROP_DIRS", [self.drops]), mock.patch("builtins.print") as fake_print:
            self.assertEqual(ll.main(["--db", str(self.db), "--drops", str(self.drops)]), 0)
        self.assertNotIn("[GATE]", " ".join(str(c.args[0]) for c in fake_print.call_args_list))


class TestFamilyFilter(LeadLagCase):
    """Round 73 review: the correlation can read one tag family, the series the sentinel gates on."""

    def test_family_selects_drops_by_name_and_the_default_reads_everything(self):
        from unittest import mock
        rec = json.dumps([{"question": "Q?", "token_id": "tok-m", "yes_price": "0.50", "fetched_at": T0 // 1000}])
        (self.drops / "polymarket_macro.json").write_text(rec, encoding="utf-8")
        (self.drops / "polymarket_macro_20260905T010000_000000Z.json").write_text(rec, encoding="utf-8")
        (self.drops / "polymarket_sports.json").write_text(rec.replace("tok-m", "tok-s"), encoding="utf-8")
        (self.drops / "polymarket_20260905T010000_000000Z.json").write_text(rec.replace("tok-m", "tok-u"), encoding="utf-8")
        (self.drops / "polymarket_0001.json").write_text(rec.replace("tok-m", "tok-r"), encoding="utf-8")
        self.assertEqual(sorted({r["key"] for r in ll.load_drop_records([self.drops], family="macro")}), ["tok-m"])
        self.assertEqual(sorted({r["key"] for r in ll.load_drop_records([self.drops], family="sports")}), ["tok-s", "tok-u"])
        self.assertEqual(sorted({r["key"] for r in ll.load_drop_records([self.drops])}), ["tok-m", "tok-r", "tok-s", "tok-u"])
        self.assertEqual(sorted({r["key"] for r in ll.load_drop_records([self.drops], family="any")}), ["tok-m", "tok-r", "tok-s", "tok-u"])
        self.assertTrue(ll._file_matches_family("polymarket_macro_x.json", "macro"))
        self.assertFalse(ll._file_matches_family("polymarket_sports.json", "macro"))
        # run() and the CLI pass the family through; the default stays "every drop" for research fixtures.
        with mock.patch.object(ll, "load_drop_records", wraps=ll.load_drop_records) as loader:
            ll.run("BTC", [self.drops], self.db, 60, 0.02, 5, 60, family="macro")
            self.assertEqual(loader.call_args.kwargs.get("family"), "macro")
            ll.run("BTC", [self.drops], self.db, 60, 0.02, 5, 60)
            self.assertIsNone(loader.call_args.kwargs.get("family"))
        with mock.patch("builtins.print"), mock.patch.object(ll, "run", wraps=ll.run) as runner:
            ll.main(["--coin", "btc", "--drops", str(self.drops), "--db", str(self.db), "--family", "macro"])
            self.assertEqual(runner.call_args.kwargs.get("family"), "macro")


class TestTier2Subfamily(LeadLagCase):
    """Round 74 (Ruling 74-2, Tier 2): a pre-registered split inside the macro family, with the latency rule."""

    def _labelled_drops(self):
        for i in range(4):
            (self.drops / f"polymarket_macro_2026090{5}T0{i}0000_000000Z.json").write_text(json.dumps([
                {"question": "Will the Fed cut?", "token_id": "tok-fed", "yes_price": f"{0.40 + 0.05 * i:.2f}",
                 "fetched_at": (T0 + i * 60 * MIN) // 1000, "sport": "FED-RATES"},
                {"question": "Will BTC be above $80k?", "token_id": "tok-btc", "yes_price": f"{0.60 - 0.05 * i:.2f}",
                 "fetched_at": (T0 + i * 60 * MIN) // 1000, "sport": "CRYPTO"},
                {"question": "Unlabelled?", "token_id": "tok-none", "yes_price": "0.50",
                 "fetched_at": (T0 + i * 60 * MIN) // 1000}]), encoding="utf-8")

    def test_subfamily_reads_the_sport_label_inside_the_family(self):
        from unittest import mock
        self._labelled_drops()
        keys = lambda **kw: sorted({r["key"] for r in ll.load_drop_records([self.drops], **kw)})
        self.assertEqual(keys(family="macro"), ["tok-btc", "tok-fed", "tok-none"])
        self.assertEqual(keys(family="macro", subfamily="fed-rates"), ["tok-fed"])
        self.assertEqual(keys(family="macro", subfamily="CRYPTO"), ["tok-btc"])       # case-insensitive
        self.assertEqual(keys(family="macro", subfamily="sports"), [])
        self.assertEqual({r["label"] for r in ll.load_drop_records([self.drops], subfamily="crypto")}, {"crypto"})
        self.assertEqual(ll.record_subfamily({"sport": " Fed-Rates "}), "fed-rates")
        self.assertEqual(ll.record_subfamily({}), "")
        # run() labels its report and the CLI passes both knobs through
        result, n = ll.run("BTC", [self.drops], self.db, 60, 0.02, 5, 60, family="macro", subfamily="fed-rates")
        self.assertEqual((result["family"], result["subfamily"], n), ("macro", "fed-rates", 1))
        with mock.patch("builtins.print") as fake_print, mock.patch.object(ll, "run", wraps=ll.run) as runner:
            ll.main(["--coin", "btc", "--drops", str(self.drops), "--db", str(self.db), "--family", "macro",
                     "--subfamily", "crypto", "--latency-minutes", "5"])
        self.assertEqual(runner.call_args.kwargs.get("subfamily"), "crypto")
        self.assertEqual(runner.call_args.kwargs.get("latency_minutes"), 5.0)
        self.assertIn("[macro / crypto]", " ".join(str(c.args[0]) for c in fake_print.call_args_list))

    def test_the_latency_rule_reads_a_peak_inside_the_poll_interval_as_repricing_not_a_lead(self):
        # A planted 3-minute lag is a "lead" under Tier 1 and "contemporaneous repricing" under the crypto rule;
        # a 20-minute lag stays a lead under both. Tier 1 itself is untouched: latency 0 keeps the old reading.
        self.plant(lag_minutes=3)
        tier1, _ = ll.run("BTC", [self.drops], self.db, 60, 0.02, 5, 60)
        self.assertTrue(tier1["sufficient"]) ; self.assertEqual(tier1["best_lag_minutes"], 3)
        self.assertIn("Polymarket leads HyperLiquid by 3 min", tier1["interpretation"])
        self.assertEqual(tier1["latency_minutes"], 0.0)
        tier2, _ = ll.run("BTC", [self.drops], self.db, 60, 0.02, 5, 60, latency_minutes=ll.POLL_INTERVAL_MINUTES)
        self.assertEqual(tier2["best_lag_minutes"], 3)
        self.assertIn("contemporaneous repricing within the 5-min poll interval", tier2["interpretation"])
        self.assertIn("latency, not a lead", tier2["interpretation"])
        for f in self.drops.glob("*.json"):
            f.unlink()
        con = sqlite3.connect(str(self.db)) ; con.execute("DELETE FROM asset_snapshots") ; con.commit() ; con.close()
        self.plant(lag_minutes=20)
        far, _ = ll.run("BTC", [self.drops], self.db, 60, 0.02, 5, 60, latency_minutes=5)
        self.assertEqual(far["best_lag_minutes"], 20)
        self.assertIn("Polymarket leads HyperLiquid by 20 min", far["interpretation"])
        # the registration file exists, names the same bars as Tier 1, and never touches them
        meta = json.loads((Path(__file__).resolve().parents[1] / "experiments" / "lead_lag_tier2.meta.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(meta["tier1_unchanged"]["min_abs_corr"], 0.2)
        self.assertEqual(meta["bars"]["min_abs_corr"], 0.2)
        self.assertEqual(meta["bars"]["latency_minutes_crypto"], ll.POLL_INTERVAL_MINUTES)
        self.assertEqual(sorted(meta["subfamilies"]), ["crypto", "fed-rates"])
        self.assertIn("counts only", meta["state_at_registration"]["note"])
