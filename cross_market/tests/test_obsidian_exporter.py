"""
Round 33 Target 4: Cross-Market Arb -> Obsidian.

What must be true of this note: both characterisations of the Polymarket leg
are on every row, because Round 29 ruled capital the default and kept wagering
available - which is only useful if the operator sees what the adverse reading
costs at the moment of deciding. And it must render sanely when the bankroll is
$0, which after Round 33's fail-closed rule is the state a fresh install is in.
"""

import json
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

    NOW = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)

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
        self.assertIn("%s 2026-09-06T02:00:00+00:00 -->" % tc.LEADLAG_RUN_TAG, text)
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
        with mock.patch("cross_market.lead_lag.run", fake):
            status = LeadLagRefresher(drop_dirs=[self.questions], db_path=self.root / "none.db").run(str(self.vault), now=now)
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
        info = ex.exporter_status(lock, str(self.vault), [self.questions], now=now, alive=lambda pid: True,
                                  probe=lambda pid: "pythonw -m cross_market.interfaces.obsidian_exporter --watch")
        self.assertTrue(info["running"]) ; self.assertEqual(info["holder_pid"], os.getpid() + 40_000)
        self.assertTrue(info["lead_lag_ready"]) ; self.assertEqual(info["lead_lag_last_run"], "2026-09-06T01:40:00+00:00")
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
