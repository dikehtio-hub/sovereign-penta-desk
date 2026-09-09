"""
Round 33 Target 4: Cross-Market Arb -> Obsidian.

What must be true of this note: both characterisations of the Polymarket leg
are on every row, because Round 29 ruled capital the default and kept wagering
available - which is only useful if the operator sees what the adverse reading
costs at the moment of deciding. And it must render sanely when the bankroll is
$0, which after Round 33's fail-closed rule is the state a fresh install is in.
"""

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cross_market.interfaces.obsidian_exporter import main as ex_main
from cross_market.interfaces.obsidian_exporter import (CROSS_MARKET_ARB_NOTE,
                                                        HURDLE_CAPITAL_NO_CAPACITY,
                                                        HURDLE_WAGERING, NOMINAL_CAPITAL,
                                                        collect, export_cross_market_arb,
                                                        load_questions, render)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


class FakeHook:
    config = {"tax_rates": {"short_term_capital_gains": 0.24,
                            "state_tax_rate": 0.0637, "safety_buffer_pct": 0.02}}

    def __init__(self, safe=10_000.0):
        self._safe = safe

    def get_safe_bankroll(self, live_cash=None):
        return self._safe


class ExporterBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.db = self.root / "sports_market.db"
        self.questions = self.root / "polymarket_drops"
        self.questions.mkdir()
        # Round 103b: DEFAULT_VERDICT_PATH points at the REAL cross_market/data. Any test that builds a
        # LeadLagRefresher without an explicit verdict_path would otherwise write fixture output into the
        # repository - it did, and the file reached a commit. Redirect the default for every test here.
        from cross_market.interfaces import obsidian_exporter as _ex
        self._real_verdict_path = _ex.DEFAULT_VERDICT_PATH
        _ex.DEFAULT_VERDICT_PATH = self.root / "lead_lag_latest_verdict.json"
        self.addCleanup(setattr, _ex, "DEFAULT_VERDICT_PATH", self._real_verdict_path)
        # Round 104: the fixture clock must TRACK the real one. Subclasses used to pin
        # NOW = 2026-09-06T02:00Z and generate drop stamps relative to it. That is self-consistent for
        # tests that inject `now=self.NOW`, but two tests drive a CLI (exporter --once, maiden_protocol)
        # whose code calls datetime.now() itself - so once the wall clock passed 03:00 UTC the stamps
        # were >60 min old, the readiness gate rejected them, and both failed. Anchoring per test keeps
        # every stamp fresh at whatever time the suite runs. Any assertion that needs the anchor must
        # render it from self.NOW rather than hard-coding a date.
        self.NOW = datetime.now(timezone.utc).replace(microsecond=0)
        # Round 125 (Ruling R125-2.B item 3): the sentinel card, --status and the LeadLagRefresher now read the
        # PRICE stream too, through cross_market.lead_lag.DEFAULT_HL_DB - the real multi-GB database. Redirect it
        # for every test to a fixture with a continuous BTC series a day either side of NOW (tests that move
        # `now` a day forward still find fresh rows), so no test reads or depends on the live collector.
        from cross_market import lead_lag as _ll
        self.hl_db = self.root / "fixture_hl_snapshots.db"          # not "hl.db": the maiden-protocol tests build that one
        self._seed_hl_db(self.hl_db)
        self.addCleanup(setattr, _ll, "DEFAULT_HL_DB", _ll.DEFAULT_HL_DB)
        _ll.DEFAULT_HL_DB = self.hl_db
        conn = sqlite3.connect(self.db)
        conn.execute("""CREATE TABLE fair_odds_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            event_id TEXT NOT NULL, sport TEXT NOT NULL, market_type TEXT NOT NULL,
            line TEXT NOT NULL DEFAULT '', sportsbook TEXT NOT NULL,
            selection TEXT NOT NULL, offered_odds REAL NOT NULL)""")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def _seed_hl_db(self, path, start=None, end=None, every_seconds=60, coin="BTC"):
        """A HyperLiquid snapshot fixture: one BTC mark per minute, start..end (default NOW-26h..NOW+27h)."""
        start = start or (self.NOW - timedelta(hours=26))
        end = end or (self.NOW + timedelta(hours=27))
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE IF NOT EXISTS asset_snapshots (id INTEGER PRIMARY KEY, timestamp INTEGER, coin TEXT, "
                     "dex TEXT, mark_px REAL, mid_px REAL, oracle_px REAL, open_interest REAL, notional_oi REAL, "
                     "funding_rate REAL, premium REAL, day_ntl_vlm REAL)")
        t = start
        rows = []
        while t <= end:
            rows.append((int(t.timestamp() * 1000), coin, "main", 100.0))
            t += timedelta(seconds=every_seconds)
        conn.executemany("INSERT INTO asset_snapshots (timestamp, coin, dex, mark_px) VALUES (?,?,?,?)", rows)
        conn.commit()
        conn.close()

    def _quote(self, selection, odds, book="betmgm"):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO fair_odds_measurements (timestamp, event_id, sport, "
                     "market_type, line, sportsbook, selection, offered_odds) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     ("2026-09-04T11:00:00Z", "E1", "NFL", "moneyline", "", book, selection, odds))
        conn.commit()
        conn.close()

    def _question(self, name="q.json", price=0.455, odds_text="Will the Chiefs beat the Bills?"):
        (self.questions / name).write_text(json.dumps([
            {"question": odds_text, "yes_price": price, "token_id": "tok-1"}]), encoding="utf-8")

    def _export(self, hook=None, capital=None):
        return export_cross_market_arb(str(self.vault), hook=hook or FakeHook(),
                                       db_path=self.db, questions_dir=self.questions,
                                       capital=capital, now=NOW)


class TestEmptyState(ExporterBase):

    def test_no_questions_renders_the_normal_state(self):
        path, changed = self._export()
        self.assertTrue(changed)
        self.assertEqual(path.name, "%s.md" % CROSS_MARKET_ARB_NOTE)
        text = path.read_text(encoding="utf-8")
        self.assertIn("No matched cross-market pairs", text)
        self.assertIn("normal state", text)
        self.assertIn("16.75%", text)
        self.assertIn("23.93%", text)

    def test_the_reference_hurdles_are_the_round_27_figures(self):
        self.assertAlmostEqual(HURDLE_CAPITAL_NO_CAPACITY, 0.1675, places=4)
        self.assertAlmostEqual(HURDLE_WAGERING, 0.2393, places=4)

    def test_a_missing_questions_dir_yields_nothing_rather_than_raising(self):
        self.assertEqual(load_questions(self.root / "nope"), [])


class TestMatchedPair(ExporterBase):

    def test_a_matched_pair_shows_both_characterisations(self):
        self._quote("Buffalo Bills", 3.10)
        self._question(price=0.30)
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertIn("KC_CHIEFS / Buffalo Bills", text)
        self.assertIn("Hurdle (1234A)", text)
        self.assertIn("Hurdle (165(d))", text)
        self.assertIn("tok-1", text)
        self.assertIn("betmgm", text)
        self.assertIn("Matched pairs**: `1`", text)

    def test_a_rejected_pair_is_marked_and_flagged_against_the_hurdles(self):
        # 2.10 / 2.10 is a 4.76% book arb - far under either hurdle at no capacity.
        self._quote("Buffalo Bills", 2.10)
        self._question(price=1 / 2.10)
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertIn("❌ REJECT", text)
        self.assertIn("⛔", text)
        self.assertIn("Clearing after tax**: **`0`", text)

    def test_the_scan_rows_carry_the_live_per_pair_hurdles(self):
        self._quote("Buffalo Bills", 3.10)
        self._question(price=0.30)
        snapshot = collect(FakeHook(), load_questions(self.questions), db_path=self.db)
        row = snapshot["rows"][0]
        self.assertIsNotNone(row["hurdle_capital"])
        self.assertIsNotNone(row["hurdle_wagering"])
        # Losing the capital treatment can never make a pair easier to clear.
        self.assertGreaterEqual(row["hurdle_wagering"], row["hurdle_capital"] - 1e-9)


class TestZeroBankroll(ExporterBase):

    def test_a_zero_bankroll_prices_on_a_nominal_figure_and_says_so(self):
        """
        After Round 33 a fresh install has $0.00 safe bankroll. The verdict is a
        property of shape and tax, not of capital, so pricing on a nominal figure
        gives the same yes/no - and the note must SAY the stakes are notional.
        """
        self._quote("Buffalo Bills", 3.10)
        self._question(price=0.30)
        path, _ = self._export(hook=FakeHook(safe=0.0))
        text = path.read_text(encoding="utf-8")
        self.assertIn("nominal", text)
        self.assertIn("$%s" % format(NOMINAL_CAPITAL, ",.2f"), text)
        self.assertIn("KC_CHIEFS / Buffalo Bills", text)

    def test_an_unchanged_desk_does_not_rewrite(self):
        self._quote("Buffalo Bills", 3.10)
        self._question(price=0.30)
        _, first = self._export()
        _, second = export_cross_market_arb(str(self.vault), hook=FakeHook(), db_path=self.db,
                                            questions_dir=self.questions,
                                            now=datetime(2026, 9, 4, 12, 0, 15, tzinfo=timezone.utc))
        self.assertTrue(first)
        self.assertFalse(second)


if __name__ == "__main__":
    unittest.main()


class TestTitansSentinelRefresh(ExporterBase):
    """Round 57 (Directive 57-1): the Arb exporter keeps the Titans note's sentinel block current."""

    def test_refresh_updates_only_the_block_and_leaves_a_missing_note_missing(self):
        from datetime import timedelta
        from unittest import mock

        from cross_market import titan_correlator as tc
        from cross_market.ingestors.polymarket_fetcher import stamped_drop_name
        from cross_market.interfaces import obsidian_exporter as ex

        note = self.vault / ("%s.md" % tc.TITANS_NOTE)
        path, changed = ex.refresh_titans_sentinel(str(self.vault), drop_dirs=[self.questions], now=NOW)
        self.assertEqual((path, changed), (note, False))
        self.assertFalse(note.exists())                                    # never created here
        self.vault.mkdir(parents=True, exist_ok=True)
        note.write_text("# Titans\n\n%s\nold\n%s\n\n## 📝 Titan Investigation Notes\nkeep me\n"
                        % (tc.SENTINEL_START, tc.SENTINEL_END), encoding="utf-8")
        for i in range(6):
            (self.questions / stamped_drop_name(NOW - timedelta(minutes=5 * i), family="macro")).write_text("[]")
        path, changed = ex.refresh_titans_sentinel(str(self.vault), drop_dirs=[self.questions], now=NOW)
        self.assertTrue(changed)
        text = note.read_text(encoding="utf-8")
        self.assertIn("`6 points / 0.4h @ 12.0/h`", text)
        self.assertIn("[NOT READY]", text)
        self.assertIn("keep me", text)
        self.assertNotIn("\nold\n", text)
        # --once runs the export AND the refresh on the real clock, and reports both: fresh
        # stamps make a new segment (refreshed), and a second run with nothing new is unchanged.
        real_now = datetime.now(timezone.utc)
        for i in range(6):
            (self.questions / stamped_drop_name(real_now - timedelta(minutes=5 * i), family="macro")).write_text("[]")
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ex.main(["--once", "--vault", str(self.vault), "--db", str(self.db),
                                      "--questions", str(self.questions), "--risk-every", "0"]), 0)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("sentinel: %s refreshed" % note.name, printed)
        self.assertIn("risk: off", printed)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ex.main(["--once", "--vault", str(self.vault), "--db", str(self.db),
                                      "--questions", str(self.questions), "--risk-every", "0"]), 0)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("sentinel: %s unchanged" % note.name, printed)          # only the clock line moved


class TestRiskRefresher(ExporterBase):
    """Round 59 (Directive 59-1): the exporter loop keeps Risk_Sentinel.md current without churn."""

    def test_refresh_is_due_on_start_every_n_cycles_and_when_the_book_moves(self):
        from unittest import mock

        from cross_market import risk_simulator as rs
        from cross_market.interfaces.obsidian_exporter import RiskRefresher

        book = self.root / "basis_paper_state.json"
        book.write_text(json.dumps({"cash": 60_000.0, "positions": {"XPL": {"capital": 20_000.0}}}), encoding="utf-8")
        r = RiskRefresher(every_cycles=3, iterations=60, grid_iterations=10, seed=5, paper_state=book,
                          loader=lambda: rs.RiskInputs(horizon_days=20))
        self.assertEqual(r.signature(), (80_000, 1, ("XPL",)))
        self.assertTrue(r.due(0))                                              # first cycle
        self.assertEqual(r.status(0), "risk: pending")
        status = r.run(str(self.vault), 0)
        self.assertEqual(status, "risk: Risk_Sentinel.md refreshed (60 paths)")
        self.assertTrue((self.vault / "Risk_Sentinel.md").exists())
        self.assertFalse(r.due(1))
        self.assertFalse(r.due(2))
        self.assertEqual(r.status(2), "risk: next in 1 cycle(s)")
        self.assertTrue(r.due(3))                                              # every 3 cycles
        self.assertEqual(r.run(str(self.vault), 3), "risk: Risk_Sentinel.md unchanged (60 paths)")
        book.write_text(json.dumps({"cash": 60_030.0, "positions": {"XPL": {"capital": 20_000.0}}}), encoding="utf-8")
        self.assertFalse(r.due(4))                                             # an hourly accrual is not a shift
        book.write_text(json.dumps({"cash": 61_500.0, "positions": {"XPL": {"capital": 20_000.0}}}), encoding="utf-8")
        self.assertTrue(r.due(4))                                              # the book moved: due at once
        self.assertEqual(r.runs, 2)
        # Off: never due; a broken loader is reported, never raised; a missing book is a None signature.
        self.assertFalse(RiskRefresher(every_cycles=0).due(0))
        self.assertEqual(RiskRefresher(every_cycles=0).status(0), "risk: off")

        def broken():
            raise RuntimeError("no book")

        self.assertTrue(RiskRefresher(every_cycles=1, iterations=5, grid_iterations=5, loader=broken)
                        .run(str(self.vault), 0).startswith("risk: skipped (RuntimeError: no book)"))
        self.assertIsNone(RiskRefresher(paper_state=self.root / "none.json").signature())
        # The --once path runs the refresh hermetically with --risk-assume-defaults.
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ex_main(["--once", "--vault", str(self.vault), "--db", str(self.db),
                                      "--questions", str(self.questions), "--risk-every", "1",
                                      "--risk-iterations", "40", "--risk-grid-iterations", "10",
                                      "--risk-assume-defaults", "--risk-stress", "0.5"]), 0)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("risk: Risk_Sentinel.md refreshed (40 paths)", printed)
        self.assertIn("## ⚡ Systemic Stress", (self.vault / "Risk_Sentinel.md").read_text(encoding="utf-8"))
        self.assertIn("| Recommended cash buffer |", (self.vault / "Risk_Sentinel.md").read_text(encoding="utf-8"))


class TestLeadLagRefresher(ExporterBase):
    """
    Round 73 (Ruling 72-1). The maiden Item 18 run happens by itself, only when
    the sentinel says READY, at most once per cooldown, and lands in its own
    block of the Titans note without touching the sentinel card or user notes.
    """

    # NOW is set per test in ExporterBase.setUp (Round 104): it tracks the real clock.

    def _stamps(self, count, spacing_min=5, ending_min_ago=3, family="macro"):
        from cross_market.ingestors.polymarket_fetcher import stamped_drop_name
        for i in range(count):
            when = self.NOW - timedelta(minutes=ending_min_ago + spacing_min * i)
            (self.questions / stamped_drop_name(when, family=family)).write_text("[]", encoding="utf-8")

    def _note(self):
        from cross_market import titan_correlator as tc
        self.vault.mkdir(parents=True, exist_ok=True)
        note = self.vault / ("%s.md" % tc.TITANS_NOTE)
        note.write_text("# Titans\n\n%s\nsentinel body\n%s\n\n---\n\n## 🧭 Intelligence Architecture & "
                        "Correlation Vectors\n\ntext\n\n---\n\n%s\nkeep me\n"
                        % (tc.SENTINEL_START, tc.SENTINEL_END, tc.USER_NOTES_HEADER), encoding="utf-8")
        return note

    def _runner(self, calls, sufficient=True):
        def run(coin):
            calls.append(coin)
            if sufficient:
                return ({"events": 14, "price_points": 5000, "max_lag": 60, "sufficient": True, "reason": "",
                         "best_lag_minutes": 12, "correlation": 0.41, "n": 900,
                         "interpretation": "Polymarket leads HyperLiquid by 12 min (corr +0.41, n=900)",
                         "curve": [{"lag_minutes": 12, "correlation": 0.41, "n": 900},
                                   {"lag_minutes": 11, "correlation": 0.38, "n": 900}]}, 7)
            return ({"events": 2, "price_points": 0, "max_lag": 60, "sufficient": False,
                     "reason": "2 probability shifts < 5 required", "best_lag_minutes": None, "correlation": None,
                     "n": 0, "interpretation": "", "curve": []}, 3)
        return run

    def test_a_dead_price_collector_gates_the_run_even_when_the_stamps_are_ready(self):
        """Ruling R125-2.B item 3 (Round 125). Rounds 119 and 125 both had READY stamps over a collector that
        had written nothing for hours; the loop would have auto-run a verdict on a holed price series, and the
        sentinel card would have shown READY. Now the loop refuses, names the stream, and the card agrees."""
        from unittest import mock
        from cross_market import lead_lag as _ll
        from cross_market import titan_correlator as tc
        from cross_market.interfaces.obsidian_exporter import LeadLagRefresher
        self._stamps(300)
        self._note()
        stale = self.root / "stale_hl.db"                                    # the Round 125 shape: rows stop 26 h ago
        self._seed_hl_db(stale, start=self.NOW - timedelta(hours=40), end=self.NOW - timedelta(hours=26))
        calls = []
        r = LeadLagRefresher(drop_dirs=[self.questions], db_path=stale, runner=self._runner(calls))
        status = r.run(str(self.vault), now=self.NOW)
        self.assertTrue(status.startswith("lead-lag: gated (NOT READY: price stream stale"), status)
        self.assertEqual(calls, [])                                          # never ran
        info = r.readiness(now=self.NOW)
        self.assertGreaterEqual(info["points"], 200)                         # the event bar alone is met
        self.assertFalse(info["price"]["ready"])
        with mock.patch.object(_ll, "DEFAULT_HL_DB", stale):
            block = tc.lead_lag_sentinel_block([self.questions], "macro", now=self.NOW)
        self.assertIn("**Verdict: `[NOT READY]`**", block)
        self.assertIn("**Price stream**: `BTC`", block)
        self.assertIn("price stream stale", block)
        # With the fixture's live series (the default for every test) the same loop is READY and runs.
        r2 = LeadLagRefresher(drop_dirs=[self.questions], runner=self._runner(calls))
        status = r2.run(str(self.vault), now=self.NOW)
        self.assertTrue(status.startswith("lead-lag: RAN BTC"), status)        # READY -> it ran at once
        self.assertEqual(calls, ["BTC"])
        block = tc.lead_lag_sentinel_block([self.questions], "macro", now=self.NOW)
        self.assertIn("**Price stream**: `BTC`", block)
        self.assertIn("- OK", block)

    def test_the_run_that_writes_the_note_also_writes_the_verdict_artifact(self):
        """Ruling R102-2 (Round 103). The dashboard and the wiki must describe ONE run. Before this the
        ingest re-ran the correlation seconds later against a series the watcher had already grown, so
        the note said n=1495 and the wiki page said n=1497 for the same verdict."""
        import json as _json
        from cross_market.interfaces.obsidian_exporter import DEFAULT_VERDICT_PATH, LeadLagRefresher
        self._stamps(300)
        self._note()
        artifact = self.root / "lead_lag_latest_verdict.json"
        calls = []
        r = LeadLagRefresher(drop_dirs=[self.questions], runner=self._runner(calls), verdict_path=artifact)
        self.assertFalse(artifact.exists())
        status = r.run(str(self.vault), now=self.NOW)
        self.assertIn("lead-lag: RAN", status)
        self.assertTrue(artifact.exists(), "the artifact must be written by the same cycle that wrote the note")
        payload = _json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(payload["best_lag_minutes"], r.last_result["best_lag_minutes"])   # same run, same numbers
        self.assertEqual(payload["correlation"], r.last_result["correlation"])
        env = payload["_artifact"]
        self.assertEqual(env["written_at"], self.NOW.isoformat())
        self.assertEqual((env["coin"], env["family"]), ("BTC", "macro"))
        self.assertEqual(env["writer"], "process:cross_market.interfaces.obsidian_exporter")
        self.assertFalse(artifact.with_suffix(".json.tmp").exists())            # written atomically, temp removed
        self.assertEqual(Path(DEFAULT_VERDICT_PATH).name, "lead_lag_latest_verdict.json")

    def test_stop_exporter_terminates_only_a_live_holder_and_sweeps_the_lock(self):
        """Ruling R103-F2 (Round 104). The exporter had no --stop while the fetcher has had one since
        Round 79, and stop_all_ecosystem_sync.bat matches window titles a detached pythonw has not - so
        the only way to stop this loop was a kill by pid typed by hand."""
        from cross_market.ingestors import pid_lock
        from cross_market.interfaces import obsidian_exporter as ex
        lock = self.root / "exporter.pid"

        # nothing running: nothing to stop, nothing killed
        killed = []
        info = ex.stop_exporter(pid_file=lock, terminate=killed.append, alive=lambda p: False)
        self.assertEqual((info["terminated"], info["holder_pid"], killed), (False, None, []))
        self.assertIn("nothing to stop", ex.format_stop(info))

        # a LIVE holder: terminated, waited for, lock swept
        pid_lock.acquire(lock, mark=ex.EXPORTER_MARK)
        holder = pid_lock.read_pid_file(lock)
        state = {"alive": True}
        # probe returns the holder's COMMAND LINE; is_stale checks EXPORTER_MARK appears in it, which is
        # what stops this ever terminating a process that is not this exporter.
        probe = lambda p: "pythonw -m cross_market.interfaces.obsidian_exporter --watch"   # noqa: E731
        info = ex.stop_exporter(pid_file=lock, terminate=lambda p: (killed.append(p), state.__setitem__("alive", False)),
                                alive=lambda p: state["alive"], probe=probe, sleep=lambda s: None)
        self.assertEqual((info["terminated"], info["still_alive"], killed), (True, False, [holder]))
        self.assertTrue(info["swept"])
        self.assertFalse(lock.exists())
        self.assertIn("terminated", ex.format_stop(info))

        # a lock held by something that is NOT an exporter is stale: swept, never killed
        pid_lock.acquire(lock, mark=ex.EXPORTER_MARK)
        killed.clear()
        info = ex.stop_exporter(pid_file=lock, terminate=killed.append, alive=lambda p: True,
                                probe=lambda p: "pythonw -m some.other.daemon --watch")
        self.assertEqual((info["terminated"], killed), (False, []))

    def test_stop_exporter_cli_exit_codes(self):
        from cross_market.interfaces import obsidian_exporter as ex
        lock = self.root / "exporter.pid"
        self.assertEqual(ex.main(["--stop", "--pid-file", str(lock), "--json"]), ex.STATUS_EXIT_STOPPED)

    def test_the_default_artifact_path_is_never_the_real_repo_during_tests(self):
        """Round 103b regression: a refresher built WITHOUT verdict_path must not write into
        cross_market/data. It did, and the fixture output reached a commit."""
        from cross_market.interfaces import obsidian_exporter as ex
        r = ex.LeadLagRefresher(drop_dirs=[self.questions], runner=self._runner([]))
        self.assertEqual(r.verdict_path.parent, self.root)                      # redirected by ExporterBase.setUp
        self.assertNotIn("cross_market", str(r.verdict_path.parent))
        self._stamps(300)
        self._note()
        existed_before = self._real_verdict_path.exists()
        r.run(str(self.vault), now=self.NOW)
        self.assertTrue(r.verdict_path.exists())                                 # written to the temp dir
        # and the run created nothing in the repo: if the file was absent before, it is absent after
        self.assertEqual(self._real_verdict_path.exists(), existed_before)

    def test_a_failed_artifact_write_never_breaks_the_export(self):
        """The artifact is a convenience; the dashboard is the product. A write failure returns None and
        the cycle still reports RAN."""
        from cross_market.interfaces.obsidian_exporter import LeadLagRefresher
        self._stamps(300)
        self._note()
        blocked = self.root / "no_such_dir" / "x"           # a directory path where a file must go
        blocked.mkdir(parents=True)
        r = LeadLagRefresher(drop_dirs=[self.questions], runner=self._runner([]), verdict_path=blocked)
        status = r.run(str(self.vault), now=self.NOW)
        self.assertIn("lead-lag: RAN", status)
        self.assertIsNone(r._write_verdict_artifact({"a": 1}, 3, self.NOW))

    def test_not_ready_gates_the_run_and_leaves_the_note_alone(self):
        from cross_market.interfaces.obsidian_exporter import LeadLagRefresher
        self._stamps(6)
        note = self._note()
        before = note.read_text(encoding="utf-8")
        calls = []
        r = LeadLagRefresher(drop_dirs=[self.questions], runner=self._runner(calls))
        status = r.run(str(self.vault), now=self.NOW)
        self.assertTrue(status.startswith("lead-lag: gated (NOT READY: span"), status)
        self.assertEqual(calls, [])
        self.assertEqual(note.read_text(encoding="utf-8"), before)
        self.assertEqual(r.runs, 0)

    def test_ready_runs_once_writes_the_block_and_then_waits_out_the_cooldown(self):
        from cross_market import titan_correlator as tc
        from cross_market.interfaces.obsidian_exporter import LeadLagRefresher
        self._stamps(300)                                                     # 24.9 h, 300 points, 5-min spacing
        note = self._note()
        calls = []
        r = LeadLagRefresher(coin="btc", drop_dirs=[self.questions], runner=self._runner(calls))
        status = r.run(str(self.vault), now=self.NOW)
        self.assertTrue(status.startswith("lead-lag: RAN BTC -> Cross_Market_Titans.md written (Polymarket leads"), status)
        self.assertEqual(calls, ["BTC"])
        text = note.read_text(encoding="utf-8")
        self.assertIn(tc.LEADLAG_HEADER, text)
        self.assertIn("[!SUCCESS] **Polymarket leads HyperLiquid by 12 min", text)
        self.assertIn("**Best lag**: `+12 min` · **correlation** `+0.410` · **n** `900`", text)
        self.assertIn("`7` markets · `14` probability shifts · `5000` BTC price points", text)
        self.assertIn("%s %s -->" % (tc.LEADLAG_RUN_TAG, self.NOW.isoformat()), text)   # follows the fixture clock
        self.assertLess(text.index(tc.SENTINEL_END), text.index(tc.LEADLAG_START))         # after the sentinel
        self.assertLess(text.index(tc.LEADLAG_END), text.index("Intelligence Architecture"))
        self.assertIn("sentinel body", text)
        self.assertIn("keep me", text)
        self.assertEqual(tc.lead_lag_last_run(note), self.NOW)
        # Consecutive cycles inside the cooldown do not rerun. The series keeps accumulating, as a
        # live watcher's would: a static fixture would go "stalled" after 60 min and be GATED, not
        # cooled down - which the engine correctly did before this line was added.
        for minutes in (0.25, 60, 23 * 60):
            self._stamps(300, ending_min_ago=3 - minutes)
            status = r.run(str(self.vault), now=self.NOW + timedelta(minutes=minutes))
            self.assertTrue(status.startswith("lead-lag: READY, next run in"), status)
        self.assertEqual(calls, ["BTC"])
        # Past the cooldown it runs again and the run-at moves; the block is replaced, not duplicated.
        later = self.NOW + timedelta(hours=25)
        self._stamps(300, ending_min_ago=3 - 25 * 60)                        # keep the series READY at `later`
        status = r.run(str(self.vault), now=later)
        self.assertTrue(status.startswith("lead-lag: RAN BTC"), status)
        self.assertEqual(calls, ["BTC", "BTC"])
        text = note.read_text(encoding="utf-8")
        self.assertEqual(text.count(tc.LEADLAG_START), 1)
        self.assertEqual(tc.lead_lag_last_run(note), later)
        # An insufficient result is still a run (the cooldown applies) and says why.
        r2 = LeadLagRefresher(drop_dirs=[self.questions], runner=self._runner(calls, sufficient=False))
        note.write_text(note.read_text(encoding="utf-8").replace(
            "%s %s -->" % (tc.LEADLAG_RUN_TAG, later.isoformat()), "%s 2026-09-01T00:00:00+00:00 -->" % tc.LEADLAG_RUN_TAG),
            encoding="utf-8")
        status = r2.run(str(self.vault), now=later)
        self.assertIn("(insufficient: 2 probability shifts < 5 required)", status)
        self.assertIn("[!NOTE] **Insufficient data**: 2 probability shifts < 5 required", note.read_text(encoding="utf-8"))

    def test_ready_without_a_titans_note_and_the_once_cli_line(self):
        from unittest import mock
        from cross_market.interfaces import obsidian_exporter as ex
        self._stamps(300)
        calls = []
        r = ex.LeadLagRefresher(drop_dirs=[self.questions], runner=self._runner(calls))
        self.assertTrue(r.run(str(self.vault), now=self.NOW).startswith("lead-lag: READY but no Cross_Market_Titans.md yet"))
        self.assertEqual(calls, [])
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ex.main(["--once", "--vault", str(self.vault), "--db", str(self.db),
                                      "--questions", str(self.questions), "--risk-every", "0"]), 0)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("lead-lag: READY but no Cross_Market_Titans.md yet", printed)
        with mock.patch("builtins.print") as fake_print:
            ex.main(["--once", "--vault", str(self.vault), "--db", str(self.db), "--questions", str(self.questions),
                     "--risk-every", "0", "--no-lead-lag"])
        self.assertIn("lead-lag: off", " ".join(str(c.args[0]) for c in fake_print.call_args_list))


class TestReviewResilience(ExporterBase):
    """Round 73 review: the maiden run reads the macro family; loops can log to a file; launchers are detached."""

    def test_the_default_runner_reads_the_macro_family(self):
        from unittest import mock
        from cross_market.interfaces.obsidian_exporter import LeadLagRefresher
        from cross_market.ingestors.polymarket_fetcher import stamped_drop_name
        from cross_market import titan_correlator as tc
        now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
        for i in range(300):
            (self.questions / stamped_drop_name(now - timedelta(minutes=3 + 5 * i), family="macro")).write_text("[]")
        self.vault.mkdir(parents=True, exist_ok=True)
        (self.vault / ("%s.md" % tc.TITANS_NOTE)).write_text("# T\n%s\nx\n%s\n" % (tc.SENTINEL_START, tc.SENTINEL_END))
        fake = mock.Mock(return_value=({"events": 0, "price_points": 0, "max_lag": 60, "sufficient": False,
                                        "reason": "0 probability shifts < 5 required", "curve": []}, 0))
        # Round 125: the gate reads the price stream from db_path before the runner is reached, so the fixture
        # database must carry a live BTC series around this test's own `now` (the runner itself stays mocked).
        prices = self.root / "macro_family_hl.db"
        self._seed_hl_db(prices, start=now - timedelta(hours=26), end=now + timedelta(minutes=1))
        with mock.patch("cross_market.lead_lag.run", fake):
            status = LeadLagRefresher(drop_dirs=[self.questions], db_path=prices).run(str(self.vault), now=now)
        self.assertTrue(status.startswith("lead-lag: RAN BTC"), status)
        self.assertEqual(fake.call_args.kwargs.get("family"), "macro")

    def test_log_file_tees_the_loop_output_and_launchers_are_detached(self):
        from unittest import mock
        from cross_market.console_log import Tee, tee_stdout
        from cross_market.ingestors import polymarket_fetcher as pf
        log = self.root / "logs" / "watcher.log"
        import sys
        original = sys.stdout, sys.stderr
        try:
            with mock.patch("builtins.print"):                                  # the tee is below print
                pass
            self.assertEqual(tee_stdout(log), log)
            self.assertIsInstance(sys.stdout, Tee)
            print("hello from the loop")
            sys.stdout.flush()
        finally:
            sys.stdout, sys.stderr = original
        self.assertIn("hello from the loop", log.read_text(encoding="utf-8"))
        # A fetcher run with --log-file lands its lines in the file.
        log2 = self.root / "logs" / "fetcher.log"
        try:
            pf.main(["--watch", "--max-polls", "1", "--interval", "0", "--folder", str(self.questions),
                     "--log-file", str(log2)])
        finally:
            sys.stdout, sys.stderr = original
        self.assertIn("[DROP]", log2.read_text(encoding="utf-8"))
        self.assertIsNone(tee_stdout(Path("?:/nowhere/x.log")))                # never raises
        # Launchers: detached (Start-Process + pythonw), logging, and the watcher guarded by --status.
        dev = Path(__file__).resolve().parents[2]
        watcher = (dev / "start_polymarket_watcher.bat").read_text(encoding="utf-8", errors="replace")
        exporter = (dev / "start_cross_market_exporter.bat").read_text(encoding="utf-8", errors="replace")
        for text, log_name in ((watcher, "polymarket_watcher.log"), (exporter, "cross_market_exporter.log")):
            self.assertIn("Start-Process", text)
            self.assertIn("pythonw", text)
            self.assertIn("--log-file", text)
            self.assertIn(log_name, text)
        self.assertIn("polymarket_fetcher --status", watcher)
        self.assertIn("errorlevel 3", watcher)
        # Two cmd traps found live (rc 255): %PYW% is expanded when the whole if-block is parsed, so the
        # lookup must precede the block; and a bare ")" in an echo inside the block closes it early.
        self.assertLess(watcher.index('set "PYW='), watcher.index("if errorlevel 3 ("))
        block = watcher[watcher.index("if errorlevel 3 ("):watcher.index(") else (")]
        for line in block.splitlines():
            if line.strip().startswith("echo"):
                self.assertNotIn(")", line)
                self.assertNotIn("(", line)
        # The doubled-quote form '""a b""' reached the child with a trailing space; \" is exact.
        self.assertIn('\\"fed,rate cut,bitcoin,btc\\"', watcher)
        sync = (dev / "start_all_ecosystem_sync.bat").read_text(encoding="utf-8", errors="replace")
        self.assertIn('call "%~dp0start_polymarket_watcher.bat"', sync)
        self.assertNotIn('start "Polymarket Watcher" python', sync)


class TestExporterLock(ExporterBase):
    """Round 74 (Directive 74-1): one exporter loop per vault; --status is the operator's read-only view."""

    def _args(self, *extra):
        return ["--vault", str(self.vault), "--db", str(self.db), "--questions", str(self.questions),
                "--risk-every", "0", "--no-lead-lag", "--pid-file", str(self.root / "exporter.pid")] + list(extra)

    def test_status_reads_the_lock_and_the_item_18_state_without_writing(self):
        import os
        from unittest import mock
        from cross_market.interfaces import obsidian_exporter as ex
        from cross_market import titan_correlator as tc
        lock = self.root / "exporter.pid"
        now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
        info = ex.exporter_status(lock, str(self.vault), [self.questions], now=now)
        self.assertFalse(info["running"]) ; self.assertFalse(info["stale_pid_file"])
        self.assertIsNone(info["lead_lag_last_run"]) ; self.assertFalse(info["lead_lag_ready"])
        self.assertIn("no stamped drops", info["lead_lag_reasons"])
        text = ex.format_exporter_status(info)
        self.assertIn("exporter STOPPED - no lock", text) ; self.assertIn("last run never", text)
        self.assertIn("no Titans note yet", text)
        # a dead holder is a stale lock; a live process that is not this exporter is stale too
        lock.write_text("%d\n" % (os.getpid() + 40_000), encoding="utf-8")
        info = ex.exporter_status(lock, str(self.vault), [self.questions], now=now, alive=lambda pid: False)
        self.assertFalse(info["running"]) ; self.assertTrue(info["stale_pid_file"])
        self.assertIn("stale lock", ex.format_exporter_status(info))
        info = ex.exporter_status(lock, str(self.vault), [self.questions], now=now, alive=lambda pid: True,
                                  probe=lambda pid: "python -m Sports_Desk.interfaces.obsidian_exporter --watch")
        self.assertFalse(info["running"], "the Sports Desk exporter must not pass as the holder")
        # a live exporter: running, and the Item 18 clocks come from the note and the stamps
        self.vault.mkdir(parents=True, exist_ok=True)
        note = self.vault / ("%s.md" % tc.TITANS_NOTE)
        note.write_text("# T\n%s\n<!-- lead-lag-run-at: 2026-09-06T01:40:00+00:00 -->\nx\n%s\n"
                        % (tc.LEADLAG_START, tc.LEADLAG_END), encoding="utf-8")
        from cross_market.ingestors.polymarket_fetcher import stamped_drop_name
        for i in range(300):
            (self.questions / stamped_drop_name(now - timedelta(minutes=3 + 5 * i), family="macro")).write_text("[]")
        # Round 125: --status judges the price stream too, so this test's fixed `now` needs a BTC series of its own.
        from cross_market import lead_lag as _ll
        prices = self.root / "status_hl.db"
        self._seed_hl_db(prices, start=now - timedelta(hours=26), end=now + timedelta(minutes=1))
        with mock.patch.object(_ll, "DEFAULT_HL_DB", prices):
            info = ex.exporter_status(lock, str(self.vault), [self.questions], now=now, alive=lambda pid: True,
                                      probe=lambda pid: "pythonw -m cross_market.interfaces.obsidian_exporter --watch")
        self.assertTrue(info["running"]) ; self.assertEqual(info["holder_pid"], os.getpid() + 40_000)
        self.assertTrue(info["lead_lag_ready"], info["lead_lag_reasons"]) ; self.assertEqual(info["lead_lag_last_run"], "2026-09-06T01:40:00+00:00")
        self.assertTrue(info["lead_lag_price_ready"])
        text = ex.format_exporter_status(info)
        self.assertIn("exporter RUNNING - pid", text) ; self.assertIn("macro series READY", text)
        # the CLI: exit codes, JSON, and never a note written
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ex.main(self._args("--status")), ex.STATUS_EXIT_STOPPED)   # real probe: pid is not alive
        self.assertIn("exporter STOPPED", " ".join(str(c.args[0]) for c in fake_print.call_args_list))
        lock.unlink()
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(ex.main(self._args("--status", "--json")), ex.STATUS_EXIT_STOPPED)
        payload = json.loads(fake_print.call_args_list[0].args[0])
        self.assertFalse(payload["running"]) ; self.assertEqual(payload["pid_file"], str(lock))
        self.assertFalse((self.vault / ("%s.md" % CROSS_MARKET_ARB_NOTE)).exists())      # --status never writes

    def test_watch_claims_the_lock_releases_it_and_yields_to_a_live_holder(self):
        import os
        from unittest import mock
        from cross_market.interfaces import obsidian_exporter as ex
        from cross_market.ingestors import pid_lock
        lock = self.root / "exporter.pid"
        seen = {}

        def sleep_then_stop(_seconds):
            seen["held"] = pid_lock.read_pid_file(lock)
            raise KeyboardInterrupt
        with mock.patch.object(ex.time, "sleep", side_effect=sleep_then_stop), \
                mock.patch.object(pid_lock, "install_cleanup") as installed, \
                mock.patch("builtins.print") as fake_print:
            self.assertEqual(ex.main(self._args("--watch", "--interval", "0")), 0)
        self.assertEqual(seen["held"], os.getpid())                                     # claimed for the loop
        self.assertFalse(lock.exists(), "released in finally")
        self.assertEqual(installed.call_args.args[0], lock)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("[LOCK] exporter pid %d" % os.getpid(), printed)
        self.assertIn("Cross_Market_Arb.md", printed)
        # a live holder (another exporter) makes a newcomer print already_running and exit 0 without a cycle
        lock.write_text("%d\n" % (os.getpid() + 40_000), encoding="utf-8")
        with mock.patch.object(pid_lock, "pid_is_alive", return_value=True), \
                mock.patch.object(pid_lock, "process_cmdline",
                                  return_value="pythonw -m cross_market.interfaces.obsidian_exporter --watch"), \
                mock.patch.object(ex, "export_cross_market_arb") as exported, \
                mock.patch("builtins.print") as fake_print:
            self.assertEqual(ex.main(self._args("--watch")), 0)
        self.assertIn("already_running: exporter pid %d" % (os.getpid() + 40_000),
                      " ".join(str(c.args[0]) for c in fake_print.call_args_list))
        exported.assert_not_called()
        self.assertTrue(lock.exists(), "a live holder's lock is left alone")
        # launchers: the exporter launcher is guarded like the watcher's, and the sync bat calls it behind the guard
        dev = Path(__file__).resolve().parents[2]
        launcher = (dev / "start_cross_market_exporter.bat").read_text(encoding="utf-8", errors="replace")
        self.assertIn("obsidian_exporter --status", launcher)
        self.assertLess(launcher.index('set "PYW='), launcher.index("if errorlevel 3 ("))
        block = launcher[launcher.index("if errorlevel 3 ("):launcher.index(") else (")]
        for line in block.splitlines():
            if line.strip().startswith("echo"):
                self.assertNotIn(")", line) ; self.assertNotIn("(", line)
        sync = (dev / "start_all_ecosystem_sync.bat").read_text(encoding="utf-8", errors="replace")
        self.assertIn('call "%~dp0start_cross_market_exporter.bat"', sync)
        self.assertNotIn('start "Cross-Market Arb Obsidian Sync"', sync)
        self.assertLess(sync.index("obsidian_exporter --status"), sync.index('call "%~dp0start_cross_market_exporter.bat"'))


class TestMaidenRunSafety(ExporterBase):
    """Round 75: the maiden run must not be buried by a transient failure or a data hole."""

    # NOW is set per test in ExporterBase.setUp (Round 104): it tracks the real clock.

    def _stamps(self, count, spacing_min=5, ending_min_ago=3):
        from cross_market.ingestors.polymarket_fetcher import stamped_drop_name
        for i in range(count):
            when = self.NOW - timedelta(minutes=ending_min_ago + spacing_min * i)
            (self.questions / stamped_drop_name(when, family="macro")).write_text("[]", encoding="utf-8")

    def _note(self):
        from cross_market import titan_correlator as tc
        self.vault.mkdir(parents=True, exist_ok=True)
        note = self.vault / ("%s.md" % tc.TITANS_NOTE)
        note.write_text("# Titans\n\n%s\nsentinel body\n%s\n\n---\n\n## 🧭 Intelligence Architecture & "
                        "Correlation Vectors\n\ntext\n" % (tc.SENTINEL_START, tc.SENTINEL_END), encoding="utf-8")
        return note

    @staticmethod
    def _result(sufficient, price_error=""):
        if sufficient:
            return {"events": 14, "price_points": 5000, "max_lag": 60, "sufficient": True, "reason": "",
                    "best_lag_minutes": 12, "correlation": 0.41, "n": 900, "price_error": "",
                    "interpretation": "Polymarket leads HyperLiquid by 12 min (corr +0.41, n=900)", "curve": []}
        return {"events": 9, "price_points": 0, "max_lag": 60, "sufficient": False, "price_error": price_error,
                "reason": ("price series unreadable (%s)" % price_error) if price_error
                else "fewer than 60 overlapping minutes at every lag",
                "best_lag_minutes": None, "correlation": None, "n": 0, "interpretation": "", "curve": []}

    def test_a_price_read_failure_is_not_recorded_and_the_next_cycle_retries(self):
        from cross_market import titan_correlator as tc
        from cross_market.interfaces.obsidian_exporter import LeadLagRefresher
        self._stamps(300)
        note = self._note()
        before = note.read_text(encoding="utf-8")
        outcomes = [self._result(False, "OperationalError: database is locked"), self._result(True)]
        calls = []

        def runner(coin):
            calls.append(coin)
            return outcomes[len(calls) - 1], 7
        r = LeadLagRefresher(drop_dirs=[self.questions], runner=runner)
        status = r.run(str(self.vault), now=self.NOW)
        self.assertTrue(status.startswith("lead-lag: run failed (prices unreadable: OperationalError"), status)
        self.assertIn("retrying next cycle", status)
        self.assertEqual(note.read_text(encoding="utf-8"), before)                # nothing recorded
        self.assertIsNone(tc.lead_lag_last_run(note)) ; self.assertEqual(r.runs, 0)
        status = r.run(str(self.vault), now=self.NOW + timedelta(seconds=15))     # the next cycle succeeds
        self.assertTrue(status.startswith("lead-lag: RAN BTC -> Cross_Market_Titans.md written (Polymarket leads"), status)
        self.assertEqual(calls, ["BTC", "BTC"]) ; self.assertEqual(r.runs, 1)
        self.assertIn("next run after `24 h`", note.read_text(encoding="utf-8"))
        self.assertEqual(tc.lead_lag_next_run_hours(note), 24.0)

    def test_an_insufficient_result_is_recorded_but_retried_after_an_hour_not_a_day(self):
        from cross_market import titan_correlator as tc
        from cross_market.interfaces.obsidian_exporter import LeadLagRefresher
        self._stamps(300)
        note = self._note()
        outcomes = [self._result(False), self._result(True)]
        calls = []

        def runner(coin):
            calls.append(coin)
            return outcomes[min(len(calls), len(outcomes)) - 1], 7
        r = LeadLagRefresher(drop_dirs=[self.questions], runner=runner)
        status = r.run(str(self.vault), now=self.NOW)
        self.assertIn("(insufficient: fewer than 60 overlapping minutes at every lag) · retry in 1 h", status)
        text = note.read_text(encoding="utf-8")
        self.assertIn("[!NOTE] **Insufficient data**: fewer than 60 overlapping minutes", text)
        self.assertIn("next run after `1 h`", text)
        self.assertEqual(tc.lead_lag_next_run_hours(note), 1.0)
        self.assertAlmostEqual(r.cooldown_remaining_hours(note, self.NOW + timedelta(minutes=30)), 0.5, places=3)
        # inside the hour: waits; after it: runs again and, with a verdict now, states the full cooldown
        self._stamps(300, ending_min_ago=3 - 30)
        self.assertTrue(r.run(str(self.vault), now=self.NOW + timedelta(minutes=30)).startswith("lead-lag: READY, next run in 0.5 h"))
        self._stamps(300, ending_min_ago=3 - 61)
        status = r.run(str(self.vault), now=self.NOW + timedelta(minutes=61))
        self.assertTrue(status.startswith("lead-lag: RAN BTC"), status) ; self.assertEqual(len(calls), 2)
        self.assertIn("next run after `24 h`", note.read_text(encoding="utf-8"))
        self._stamps(300, ending_min_ago=3 - 120)
        self.assertTrue(r.run(str(self.vault), now=self.NOW + timedelta(minutes=120)).startswith("lead-lag: READY, next run in 23.0 h"))
        # a note written before Round 75 states no hours: the refresher's own cooldown applies
        stripped = note.read_text(encoding="utf-8").replace("next run after `24 h`", "next run after a day")
        note.write_text(stripped, encoding="utf-8")
        self.assertIsNone(tc.lead_lag_next_run_hours(note))
        self.assertAlmostEqual(r.cooldown_remaining_hours(note, self.NOW + timedelta(minutes=61 + 60)), 23.0, places=3)
        # the retry length is a flag on the loop
        from cross_market.interfaces import obsidian_exporter as ex
        from unittest import mock
        with mock.patch.object(ex, "LeadLagRefresher", wraps=ex.LeadLagRefresher) as ctor, mock.patch("builtins.print"):
            ex.main(["--once", "--vault", str(self.vault), "--db", str(self.db), "--questions", str(self.questions),
                     "--risk-every", "0", "--lead-lag-retry-hours", "2.5"])
        self.assertEqual(ctor.call_args.kwargs.get("retry_hours"), 2.5)


class TestMaidenProtocol(ExporterBase):
    """Round 75 (Directives 75-1/75-2): the verification protocol as one command, Tier 2 only after Tier 1."""

    # NOW is set per test in ExporterBase.setUp (Round 104): it tracks the real clock.

    def _stamps(self, count=300, spacing_min=5, ending_min_ago=3):
        from cross_market.ingestors.polymarket_fetcher import stamped_drop_name
        for i in range(count):
            when = self.NOW - timedelta(minutes=ending_min_ago + spacing_min * i)
            (self.questions / stamped_drop_name(when, family="macro")).write_text("[]", encoding="utf-8")

    def _hl_db(self):
        db = self.root / "hl.db"
        con = sqlite3.connect(str(db))
        con.execute("CREATE TABLE asset_snapshots (id INTEGER PRIMARY KEY, timestamp INTEGER, coin TEXT, mark_px REAL)")
        con.commit() ; con.close()
        return db

    def test_before_the_run_it_waits_and_after_it_verifies_and_runs_tier_2(self):
        from unittest import mock
        from cross_market import maiden_protocol as mp
        from cross_market import titan_correlator as tc
        from cross_market.ingestors import pid_lock
        log = self.root / "exporter.log"
        lock = self.root / "exporter.pid"
        db = self._hl_db()
        self.vault.mkdir(parents=True, exist_ok=True)
        note = self.vault / ("%s.md" % tc.TITANS_NOTE)
        common = dict(vault=str(self.vault), log_path=log, drop_dirs=[self.questions], db_path=db, pid_file=lock, now=self.NOW)
        # 1. before: no log, no note, series short -> WAIT, exit 3, Tier 2 refused
        self._stamps(6)
        info = mp.check(**common)
        self.assertFalse(info["maiden_run_done"]) ; self.assertFalse(info["ok"])
        self.assertTrue(info["tier2_skipped"].startswith("Tier 1 has not run yet"))
        self.assertIsNone(info["tier2"])
        text = mp.format_check(info)
        self.assertIn("[WAIT] log_ran_line", text) ; self.assertIn("NOT YET", text)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(mp.main(["--vault", str(self.vault), "--log", str(log), "--drops", str(self.questions),
                                      "--db", str(db), "--pid-file", str(lock)]), mp.EXIT_NOT_YET)
        self.assertIn("RESULT: NOT YET", " ".join(str(c.args[0]) for c in fake_print.call_args_list))
        # 2. after: the loop ran once, wrote the block, and has been counting down
        self._stamps(300)
        note.write_text("# T\n%s\nx\n%s\n\n%s\n" % (tc.SENTINEL_START, tc.SENTINEL_END, tc.render_lead_lag_block(
            {"events": 400, "price_points": 3000, "max_lag": 60, "sufficient": True, "best_lag_minutes": -33,
             "correlation": -0.195, "n": 1400, "interpretation": "no measurable lead-lag (peak |corr| 0.19 < 0.2)",
             "curve": []}, "BTC", 413, ran_at=self.NOW - timedelta(minutes=20))), encoding="utf-8")
        log.write_text("\n".join([
            "[01:39:35] Cross_Market_Arb.md unchanged · risk: next in 3 cycle(s) · lead-lag: gated (NOT READY: span 23.9h < 24h)",
            "[01:40:05] Cross_Market_Arb.md unchanged · risk: next in 2 cycle(s) · lead-lag: RAN BTC -> Cross_Market_Titans.md written (no measurable lead-lag (peak |corr| 0.19 < 0.2))",
            "[01:40:20] Cross_Market_Arb.md unchanged · risk: next in 1 cycle(s) · lead-lag: READY, next run in 24.0 h",
            "[01:40:35] Cross_Market_Arb.md unchanged · risk: next in 0 cycle(s) · lead-lag: READY, next run in 24.0 h",
        ]), encoding="utf-8")
        # labelled questions for Tier 2 (too few shifts: insufficient). Dated days BEFORE the 24 h segment so
        # these stamps do not join it (a stamp after `now` would end the segment and read NOT READY).
        for i in range(3):
            (self.questions / ("polymarket_macro_2026090%dT000000_000000Z.json" % (1 + i))).write_text(json.dumps([
                {"question": "Fed?", "token_id": "tok-fed", "yes_price": "0.5%d" % i, "fetched_at": "2026-09-0%dT00:00:00Z" % (1 + i), "sport": "FED-RATES"},
                {"question": "BTC?", "token_id": "tok-btc", "yes_price": "0.6%d" % i, "fetched_at": "2026-09-0%dT00:00:00Z" % (1 + i), "sport": "CRYPTO"}]),
                encoding="utf-8")
        lock.write_text("%d\n" % (os.getpid() + 40_000), encoding="utf-8")
        with mock.patch.object(pid_lock, "pid_is_alive", return_value=True), \
                mock.patch.object(pid_lock, "process_cmdline", return_value="pythonw -m cross_market.interfaces.obsidian_exporter --watch"):
            info = mp.check(**common)
        self.assertTrue(info["maiden_run_done"]) ; self.assertTrue(info["ok"], info["checks"])
        self.assertEqual(info["log"]["verdict"], "no measurable lead-lag (peak |corr| 0.19 < 0.2)")
        self.assertEqual(info["log"]["cooldown_lines_after_run"], 2) ; self.assertEqual(info["log"]["gated_lines"], 1)
        self.assertTrue(info["note"]["tag_inside"] and info["note"]["header_inside"])
        self.assertEqual(sorted(info["tier2"]), ["crypto", "fed-rates"])
        self.assertEqual(info["tier2"]["crypto"]["latency_minutes"], 5.0)
        self.assertEqual(info["tier2"]["fed-rates"]["latency_minutes"], 0.0)
        self.assertEqual(info["tier2"]["crypto"]["markets"], 1)
        self.assertFalse(info["tier2"]["crypto"]["result"]["sufficient"])
        text = mp.format_check(info)
        for expect in ("[PASS] loop_running", "[PASS] cooldown_observed", "verdict: no measurable lead-lag",
                       "TIER 2 DIAGNOSTIC SUBFAMILIES", "[macro / crypto]", "[macro / fed-rates]", "latency rule 5 min",
                       "RESULT: ALL CHECKS PASSED"):
            self.assertIn(expect, text)
        # the registration file is read, never written
        meta = Path(mp.DEFAULT_META)
        before = meta.read_bytes()
        with mock.patch.object(pid_lock, "pid_is_alive", return_value=True), \
                mock.patch.object(pid_lock, "process_cmdline", return_value="pythonw -m cross_market.interfaces.obsidian_exporter --watch"), \
                mock.patch("builtins.print") as fake_print:
            self.assertEqual(mp.main(["--vault", str(self.vault), "--log", str(log), "--drops", str(self.questions),
                                      "--db", str(db), "--pid-file", str(lock), "--json"]), 0)
        self.assertEqual(meta.read_bytes(), before)
        payload = json.loads(fake_print.call_args_list[0].args[0])
        self.assertTrue(payload["ok"])
        # 3. the loop died after the run: the run is done but a check fails -> exit 1
        lock.unlink()
        with mock.patch("builtins.print"):
            self.assertEqual(mp.main(["--vault", str(self.vault), "--log", str(log), "--drops", str(self.questions),
                                      "--db", str(db), "--pid-file", str(lock), "--no-tier2"]), 1)
