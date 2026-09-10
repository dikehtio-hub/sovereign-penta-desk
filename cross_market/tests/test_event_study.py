"""
Item 18 Phase 2 event study (Round 126). Offline: a registration, synthetic stamped books
and a temp snapshot database with `trades` and `asset_snapshots`. The point of these tests is
that a PLANTED lead comes back exactly, that a print under either bar is uninformative and
never counted, and that every sufficiency rule in the registration refuses for the reason it
names - not for a different one.
"""
import json
import random
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cross_market import event_study as es
from cross_market.latency_sniper import stamp_name

T = datetime(2026, 9, 16, 18, 0, 0, tzinfo=timezone.utc)          # the print
T_S = int(T.timestamp())
TOKENS = [("1" * 70 + "01", "FOMC: no change"), ("1" * 70 + "02", "FOMC: hike 25 bps"), ("1" * 70 + "03", "FOMC: hike 50+ bps")]


def load_real_registration():
    reg = json.loads((Path(__file__).resolve().parents[1] / "experiments" / "lead_lag_phase2_fomc.meta.json").read_text(encoding="utf-8"))
    return reg


class EventStudyCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.books = self.root / "books"
        self.books.mkdir()
        self.db = self.root / "hl.db"
        con = sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, tid INTEGER, coin TEXT, side TEXT, px REAL, sz REAL, notional REAL, "
                    "time INTEGER, hash TEXT, is_liquidation INTEGER)")
        con.execute("CREATE TABLE asset_snapshots (id INTEGER PRIMARY KEY, timestamp INTEGER, coin TEXT, dex TEXT, mark_px REAL)")
        con.commit()
        con.close()
        self.reg = load_real_registration()                     # the REAL registration drives every test
        rules = self.root / "rules.json"
        rules.write_text(json.dumps({"rules": [{"market": t, "label": l} for t, l in TOKENS]}), encoding="utf-8")
        self.event = {"id": "fomc_test", "kind": "fed_rate", "label": "test print", "release_utc": T.isoformat(),
                      "rules_file": str(rules), "books_dir": str(self.books)}
        self.after = T + timedelta(seconds=600)                   # a wall clock past T+300 s

    def tearDown(self):
        try:
            self.temp.cleanup()
        except (OSError, PermissionError):
            pass

    # ---- builders
    def stamps(self, token, step_at_s=None, before=0.50, after=0.80, start_s=-58, end_s=300, skip=()):
        """One two-sided stamp per second from T+start_s to T+end_s; the mid steps from `before` to `after` at T+step_at_s."""
        for k in range(start_s, end_s + 1):
            if k in skip:
                continue
            when = T + timedelta(seconds=k, microseconds=250_000)
            mid = after if (step_at_s is not None and k >= step_at_s) else before
            payload = {"observed_at": when.isoformat(), "bids": [{"price": "%.3f" % (mid - 0.01), "size": "100"}],
                       "asks": [{"price": "%.3f" % (mid + 0.01), "size": "100"}]}
            (self.books / stamp_name(token, when)).write_text(json.dumps(payload), encoding="utf-8")

    def trades(self, step_at_s=None, before=100_000.0, after=100_500.0, start_s=-90, end_s=300, every_s=0.5, coin="BTC",
               skip_ranges=(), other_coin="ETH", other_every_s=0.5):
        con = sqlite3.connect(str(self.db))
        rows = []
        t = float(start_s)
        while t <= end_s:
            if not any(lo <= t <= hi for lo, hi in skip_ranges):
                px = after if (step_at_s is not None and t >= step_at_s) else before
                rows.append((coin, px, int(round((T_S + t) * 1000))))
            t += every_s
        if other_coin:
            t = float(start_s)
            while t <= end_s:
                if not any(lo <= t <= hi for lo, hi in skip_ranges):
                    rows.append((other_coin, 4000.0, int(round((T_S + t) * 1000)) + 7))
                t += other_every_s
        con.executemany("INSERT INTO trades (coin, px, time, side, sz, notional) VALUES (?,?,?,?,?,?)",
                        [(c, p, tm, "A", 0.01, p * 0.01) for c, p, tm in rows])
        con.commit()
        con.close()

    def marks(self, n=360, every_s=10, noise_bps=2.0, seed=3, base=100_000.0):
        """asset_snapshots marks for BTC ending at T-5 s: n marks every `every_s`, a random walk of `noise_bps` per step."""
        rng = random.Random(seed)
        con = sqlite3.connect(str(self.db))
        px = base
        rows = []
        for i in range(n, 0, -1):
            px *= 1.0 + rng.uniform(-noise_bps, noise_bps) / 1e4
            rows.append(((T_S - 5 - i * every_s) * 1000, "BTC", "main", px))
        con.executemany("INSERT INTO asset_snapshots (timestamp, coin, dex, mark_px) VALUES (?,?,?,?)", rows)
        con.commit()
        con.close()

    def run_study(self, **kw):
        return es.evaluate(self.reg, self.event, books_dir=self.books, db_path=self.db, now=kw.pop("now", self.after), **kw)


class TestPlantedLead(EventStudyCase):
    def test_polymarket_first_by_two_seconds_is_polymarket_leads_event(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=5)
        self.marks()
        r = self.run_study()
        self.assertTrue(r["sufficient"], r["reasons"])
        self.assertEqual(r["hyperliquid"]["t_star_rel_s"], 5)
        self.assertEqual(r["markets"][0]["t_star_rel_s"], 3)
        self.assertEqual(r["lead_s"], 2.0)
        self.assertEqual(r["class"], es.CLASS_PM_LEADS)
        self.assertTrue(r["informative"])
        self.assertEqual(r["bars"]["hl_bar_source"], "trailing_60m_relative")
        self.assertGreaterEqual(r["bars"]["hl_bar_bps"], 10.0)
        self.assertEqual(r["T0_utc"], "2026-09-16T17:59:02Z")
        self.assertEqual(r["baseline_utc"], "2026-09-16T17:59:55Z")

    def test_hyperliquid_first_is_hyperliquid_leads_and_the_same_second_is_contemporaneous(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=6)
        self.trades(step_at_s=2)
        self.marks()
        r = self.run_study()
        self.assertEqual((r["class"], r["lead_s"]), (es.CLASS_HL_LEADS, -4.0))
        # the +-1 s band: one second apart is still contemporaneous
        self.assertEqual(es.classify(1.0, 1.0), es.CLASS_CONTEMPORANEOUS)
        self.assertEqual(es.classify(-1.0, 1.0), es.CLASS_CONTEMPORANEOUS)
        self.assertEqual(es.classify(1.5, 1.0), es.CLASS_PM_LEADS)
        self.assertEqual(es.classify(-1.5, 1.0), es.CLASS_HL_LEADS)
        self.assertEqual(es.classify(None, 1.0), es.CLASS_UNINFORMATIVE)

    def test_the_primary_market_is_the_largest_displacement(self):
        self.stamps(TOKENS[0][0], step_at_s=4, after=0.55)          # +0.05
        self.stamps(TOKENS[1][0], step_at_s=2, after=0.90)          # +0.40 -> primary
        self.stamps(TOKENS[2][0], step_at_s=9, after=0.20)          # -0.30
        self.trades(step_at_s=4)
        self.marks()
        r = self.run_study()
        self.assertEqual(r["primary_market"]["token"], TOKENS[1][0])
        self.assertEqual(r["lead_s"], 2.0)                          # HL at +4, primary PM at +2


class TestUninformative(EventStudyCase):
    def test_a_flat_polymarket_book_is_uninformative_and_names_the_venue(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=None)
        self.trades(step_at_s=3)
        self.marks()
        r = self.run_study()
        self.assertTrue(r["sufficient"])
        self.assertEqual(r["class"], es.CLASS_UNINFORMATIVE)
        self.assertFalse(r["informative"])
        self.assertIsNone(r["lead_s"])
        self.assertIn("polymarket |dP| 0.0000 < 0.02", r["markets"][0]["reasons"][0])

    def test_a_flat_btc_print_is_uninformative_even_when_polymarket_moved(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=None)
        self.marks()
        r = self.run_study()
        self.assertEqual(r["class"], es.CLASS_UNINFORMATIVE)
        self.assertIn("hyperliquid |dP| 0.00 bps < bar", r["markets"][0]["reasons"][0])
        self.assertEqual(r["hyperliquid"]["displaced"], False)

    def test_the_relative_bar_rises_with_noise_and_a_small_move_falls_under_it(self):
        # noisy hour: 2 bps per 10-second step -> 5-minute moves of order 30 x 2 bps -> median ~10+ bps -> bar > 10
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=3, after=100_012.0)                   # a 1.2 bps move
        self.marks(noise_bps=8.0)
        r = self.run_study()
        self.assertEqual(r["bars"]["hl_bar_source"], "trailing_60m_relative")
        self.assertGreater(r["bars"]["hl_bar_bps"], 10.0)
        self.assertEqual(r["class"], es.CLASS_UNINFORMATIVE)

    def test_fewer_than_sixty_marks_falls_back_to_the_floor(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=3, after=100_050.0)                    # a 5 bps move, under the 10 bps floor
        self.marks(n=20)
        r = self.run_study()
        self.assertEqual((r["bars"]["hl_bar_bps"], r["bars"]["hl_bar_source"]), (10.0, "floor_fallback"))
        self.assertEqual(r["class"], es.CLASS_UNINFORMATIVE)


class TestSufficiency(EventStudyCase):
    def test_a_polymarket_hole_over_five_seconds_voids_that_token_only(self):
        self.stamps(TOKENS[0][0], step_at_s=3, skip=range(30, 40))   # a 10 s hole
        self.stamps(TOKENS[1][0], step_at_s=3)
        self.stamps(TOKENS[2][0], step_at_s=3)
        self.trades(step_at_s=5)
        self.marks()
        r = self.run_study()
        self.assertTrue(r["sufficient"])
        self.assertFalse(r["markets"][0]["sufficient"])
        self.assertIn("polymarket hole 11 s > 5 s", r["markets"][0]["reasons"][0])
        self.assertEqual(r["primary_market"]["token"], TOKENS[1][0])

    def test_every_token_holed_is_insufficient_exit_2(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3, skip=range(30, 40))
        self.trades(step_at_s=5)
        self.marks()
        r = self.run_study()
        self.assertFalse(r["sufficient"])
        self.assertIn("no registered token passed the polymarket sufficiency bar", r["reasons"])

    def test_too_few_stamps_is_insufficient_by_count(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3, end_s=200)               # 259 stamps < 300 ... and a trailing hole
        self.trades(step_at_s=5)
        self.marks()
        r = self.run_study()
        self.assertIn("polymarket stamps 259 < 300", r["markets"][0]["reasons"][0])

    def test_a_trade_feed_gap_over_five_seconds_is_insufficient(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=5, skip_ranges=((40.0, 47.0),))        # every coin silent for 7 s
        self.marks()
        r = self.run_study()
        self.assertFalse(r["sufficient"])
        self.assertTrue(any("hyperliquid feed gap" in x for x in r["reasons"]), r["reasons"])

    def test_a_stale_baseline_print_is_insufficient(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=5, skip_ranges=((-30.0, -5.0),), other_coin=None)   # no BTC print in [T-30, T-5]
        # keep the feed alive with another coin so only the baseline rule fires
        con = sqlite3.connect(str(self.db))
        con.executemany("INSERT INTO trades (coin, px, time) VALUES (?,?,?)",
                        [("ETH", 4000.0, int((T_S + k) * 1000)) for k in range(-30, 301)])
        con.commit()
        con.close()
        self.marks()
        r = self.run_study()
        self.assertFalse(r["sufficient"])
        self.assertTrue(any("baseline print is" in x and "old" in x for x in r["reasons"]), r["reasons"])

    def test_quiet_btc_seconds_forward_fill_and_never_void(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=5, every_s=3.0, other_every_s=0.5)     # BTC prints every 3 s, ETH keeps the feed live
        self.marks()
        r = self.run_study()
        self.assertTrue(r["sufficient"], r["reasons"])
        self.assertEqual(r["class"], es.CLASS_PM_LEADS)
        self.assertLessEqual(r["hyperliquid"]["baseline_age_s"], 15.0)

    def test_a_late_recorder_start_is_insufficient(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3, start_s=-20)
        self.trades(step_at_s=5)
        self.marks()
        r = self.run_study()
        self.assertFalse(r["sufficient"])
        self.assertTrue(any("recorder started late" in x for x in r["reasons"]), r["reasons"])

    def test_before_the_window_closes_it_refuses_unless_forced(self):
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=5)
        self.marks()
        early = self.run_study(now=T + timedelta(seconds=100))
        self.assertFalse(early["sufficient"])
        self.assertIn("window not complete", early["reasons"][0])
        forced = self.run_study(now=T + timedelta(seconds=100), force=True)
        self.assertTrue(forced["sufficient"], forced["reasons"])


class TestCli(EventStudyCase):
    def test_json_and_text_report_and_exit_codes(self):
        import contextlib
        import io
        for token, _ in TOKENS:
            self.stamps(token, step_at_s=3)
        self.trades(step_at_s=5)
        self.marks()
        reg_path = self.root / "phase2.meta.json"
        reg = dict(self.reg, events=[self.event])
        reg_path.write_text(json.dumps(reg), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = es.main(["--registration", str(reg_path), "--event", "fomc_test", "--db", str(self.db),
                            "--now", self.after.isoformat(), "--json"])
        self.assertEqual(code, es.EXIT_OK)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["class"], es.CLASS_PM_LEADS)
        self.assertEqual(payload["_artifact"]["writer"], "cross_market.event_study")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = es.main(["--registration", str(reg_path), "--db", str(self.db), "--now", self.after.isoformat()])
        self.assertEqual(code, es.EXIT_OK)
        self.assertIn("VERDICT: polymarket-leads-event  lead 2.0 s", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):                       # window not complete -> exit 2
            code = es.main(["--registration", str(reg_path), "--db", str(self.db), "--now", (T + timedelta(seconds=10)).isoformat()])
        self.assertEqual(code, es.EXIT_INSUFFICIENT)
        self.assertIn("INSUFFICIENT: window not complete", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):             # unknown event -> refused
            self.assertEqual(es.main(["--registration", str(reg_path), "--event", "nope", "--db", str(self.db)]), es.EXIT_REFUSED)

    def test_the_real_registration_is_self_consistent(self):
        reg = self.reg
        self.assertEqual(reg["protocol"], "event_study")
        self.assertEqual([e["id"] for e in reg["events"]], ["fomc_2026-09-16", "cpi_2026-10-14", "fomc_2026-10-28"])
        self.assertEqual(reg["events"][0]["release_utc"], "2026-09-16T18:00:00Z")
        self.assertEqual(reg["events"][1]["release_utc"], "2026-10-14T12:30:00Z")
        self.assertEqual(reg["bars"]["pm_min_displacement"], 0.02)
        self.assertEqual(reg["bars"]["hl_min_displacement_bps_floor"], 10.0)
        self.assertEqual(reg["bars"]["lead_tolerance_s"], 1.0)
        self.assertEqual(reg["bars"]["panel_min_informative_events"], 3)
        self.assertEqual(reg["sufficiency"]["polymarket"]["min_stamps"], 300)
        self.assertEqual(reg["sufficiency"]["hyperliquid"]["baseline_max_age_s"], 15.0)
        real_rules = Path(__file__).resolve().parents[1] / "experiments" / "fomc_2026-09-16.rules.json"
        tokens = es.tokens_for(reg["events"][0], dev_root=Path(__file__).resolve().parents[2])
        self.assertEqual(len(tokens), 3)
        self.assertTrue(real_rules.is_file())
        self.assertTrue(all(t.isdigit() for t, _ in tokens))


if __name__ == "__main__":
    unittest.main()
