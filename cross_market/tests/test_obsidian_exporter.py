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
