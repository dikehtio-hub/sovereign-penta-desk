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
from datetime import datetime, timezone
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
