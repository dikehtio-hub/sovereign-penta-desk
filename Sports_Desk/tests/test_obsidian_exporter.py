"""
Round 33 Target 4: Sports_Desk -> Obsidian.

The one line on this note that can cost money is the un-exported warning: a
placed bet the tax ledger has never been handed cannot be reserved against, and
until Round 26k nothing checked. So the tests here are less about formatting
than about that warning appearing when it should, naming the bet, and going
away when the bet is exported.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from Sports_Desk.data.db import init_market_db, mark_exported, record_placed_bet
from Sports_Desk.interfaces.monarch_shark import SYNC_ALERT_DAYS
from Sports_Desk.interfaces.obsidian_exporter import (SPORTS_DESK_NOTE, collect,
                                                      content_hash, export_sports_desk,
                                                      render, resolve_vault,
                                                      unexported_placed_bets,
                                                      write_note_if_changed)
from Tax_Reserve_Agent.database.db import init_db
from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


class ExporterBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.db = self.root / "sports_market.db"
        self.ledger = self.root / "tax.db"
        init_market_db(self.db)
        init_db(self.ledger)

    def tearDown(self):
        self.temp.cleanup()

    def _hook(self, cash=50_000.0):
        return MonarchBankrollHook(db_path=self.ledger, config={
            "tax_rates": {"federal_ordinary_rate": 0.24, "short_term_capital_gains": 0.24,
                          "long_term_capital_gains": 0.15, "state_tax_rate": 0.0637,
                          "safety_buffer_pct": 0.02},
            "portfolio": {"default_cash_balance_usdc": cash, "tax_year": 2026},
            "gambling": {"tax_treatment": "professional_schedule_c"},
        })

    def _gated_hook(self):
        """An empty ledger with nothing declared: the fail-closed state."""
        return MonarchBankrollHook(db_path=self.ledger, config={
            "tax_rates": {"short_term_capital_gains": 0.24, "state_tax_rate": 0.0637,
                          "safety_buffer_pct": 0.02, "long_term_capital_gains": 0.15},
            "portfolio": {"default_cash_balance_usdc": None, "tax_year": 2026},
        })

    def _place(self, days_ago, selection="Ravens", stake=120.0):
        placed_at = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return record_placed_bet("G1", "NFL", "moneyline", "", selection, "draftkings",
                                 2.85, stake, ticket_id="T%d" % int(days_ago * 100),
                                 placed_at=placed_at, db_path=self.db)

    def _export(self, hook=None):
        return export_sports_desk(str(self.vault), hook=hook or self._hook(),
                                  db_path=self.db, now=NOW)


class TestNote(ExporterBase):

    def test_the_note_is_written_with_frontmatter_and_every_section(self):
        path, changed = self._export()
        self.assertTrue(changed)
        self.assertEqual(path.name, "%s.md" % SPORTS_DESK_NOTE)
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\ntitle:"))
        self.assertIn('last_synced: "2026-09-04 12:00:00 UTC"', text)
        for section in ("Active +EV Hotlist", "Realised Performance", "Execution CLV",
                        "Open Exposure", "Average Execution CLV", "Bankroll Gate",
                        "[[Monarch_Hub|"):
            self.assertIn(section, text)

    def test_an_unchanged_desk_does_not_rewrite_the_note(self):
        """Obsidian's file watcher stays quiet when nothing but the clock moved."""
        _, first = self._export()
        path, second = export_sports_desk(str(self.vault), hook=self._hook(), db_path=self.db,
                                          now=NOW + timedelta(seconds=15))
        self.assertTrue(first)
        self.assertFalse(second)

    def test_the_content_hash_ignores_only_the_timestamp_lines(self):
        a = "---\nlast_synced: \"1\"\n---\n> - **Last Synchronized**: `1`\nbody"
        b = "---\nlast_synced: \"2\"\n---\n> - **Last Synchronized**: `2`\nbody"
        c = "---\nlast_synced: \"2\"\n---\n> - **Last Synchronized**: `2`\nBODY CHANGED"
        self.assertEqual(content_hash(a), content_hash(b))
        self.assertNotEqual(content_hash(a), content_hash(c))

    def test_write_is_atomic_and_leaves_no_tmp_behind(self):
        path, _ = write_note_if_changed(self.vault / "x.md", "hello")
        self.assertEqual(path.read_text(encoding="utf-8"), "hello\n")
        self.assertFalse((self.vault / "x.tmp").exists())

    def test_vault_resolution_prefers_the_explicit_path(self):
        self.assertEqual(resolve_vault(str(self.vault)), self.vault.resolve())
        self.assertTrue(self.vault.exists())


class TestUnexportedWarning(ExporterBase):

    def test_a_fresh_bet_does_not_warn(self):
        self._place(days_ago=1.0)
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertNotIn("[!WARNING]", text)

    def test_a_bet_older_than_the_alert_window_warns_and_names_itself(self):
        self._place(days_ago=SYNC_ALERT_DAYS + 2, selection="Ravens", stake=120.0)
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertIn("[!WARNING]", text)
        self.assertIn("un-exported for more than %.0f days" % SYNC_ALERT_DAYS, text)
        self.assertIn("Ravens", text)
        self.assertIn("$120.00", text)
        self.assertIn("--export-to-tax-agent", text)

    def test_the_warning_clears_once_the_bet_is_exported(self):
        bet_id = self._place(days_ago=SYNC_ALERT_DAYS + 2)
        self.assertIn("[!WARNING]", self._export()[0].read_text(encoding="utf-8"))
        mark_exported([bet_id], db_path=self.db)
        self.assertNotIn("[!WARNING]", self._export()[0].read_text(encoding="utf-8"))

    def test_unexported_placed_bets_is_the_narrow_question(self):
        """Exported-to-drop-folder, not present-in-ledger. It needs no ledger at all."""
        old = self._place(days_ago=5.0)
        self._place(days_ago=0.5)
        stale = unexported_placed_bets(self.db, SYNC_ALERT_DAYS, NOW)
        self.assertEqual([b["id"] for b in stale], [old])
        self.assertGreaterEqual(stale[0]["age_days"], 5.0)


class TestGatedState(ExporterBase):

    def test_a_gated_hook_still_renders_and_says_so(self):
        """
        Round 33 fails closed on an empty ledger. The note must survive that and
        say FAIL-CLOSED rather than crash or show an unexplained empty hotlist.
        """
        path, _ = self._export(hook=self._gated_hook())
        text = path.read_text(encoding="utf-8")
        self.assertIn("FAIL-CLOSED", text)
        self.assertIn("Sports Desk", text)

    def test_no_hook_at_all_still_renders(self):
        snapshot = collect(None, db_path=self.db, now=NOW)
        self.assertIn("no bankroll hook", snapshot["hotlist_error"])
        text = render(snapshot, "2026-09-04 12:00:00 UTC", self.vault)
        self.assertIn("No hotlist", text)


if __name__ == "__main__":
    unittest.main()


class TestStaleSection(ExporterBase):
    """Round 66 (Ruling 65-4): Sports_Desk.md carries the stale-quote scan with feed liveness."""

    def _measure(self, book, odds, minutes_ago, selection="Ravens"):
        import sqlite3
        stamp = (NOW - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
        con = sqlite3.connect(str(self.db))
        con.execute("INSERT INTO fair_odds_measurements (timestamp, event_id, sport, market_type, line, sportsbook, "
                    "raw_quotes_json, selection, offered_odds, implied_prob_raw, fair_prob, fair_odds, expected_value, "
                    "quarter_kelly, overround, shin_z, power_k, divergent, max_oracle_delta, quoted_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (stamp, "G1", "NFL", "moneyline", "", book, "[]", selection, odds, 1 / odds, 0.5, 2.0, 0.0, 0.0,
                     0.04, 0.0, 1.0, 0, 0.0, stamp))
        con.commit()
        con.close()

    def test_an_empty_feed_says_so_and_a_planted_move_is_rendered(self):
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertIn("## 🕒 Stale Quotes & Market Consensus Latency", text)
        self.assertIn("> [!INFO] **Feed:** feed stale / no quotes in the database", text)
        self.assertIn("No sharp moves detected in last 180m (newest quote none).", text)
        self.assertNotIn("[!WARNING]", text)                                     # WARNING stays for un-exported bets
        self._measure("Pinnacle", 2.00, 9)
        self._measure("Pinnacle", 1.80, 5)
        self._measure("DraftKings", 2.05, 10)
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertIn("**Sharp moves (last 180m): 1** · stale retail quotes: **1** · newest quote 5m ago", text)
        self.assertIn("`Pinnacle` G1 moneyline **Ravens**: shortened `2.000 -> 1.800` (+5.6 pts in 4.0 min)", text)
        self.assertIn("🐌 `DraftKings` still `2.050` on **Ravens**: edge `+6.8 pts` vs sharp `1.800`", text)
        self.assertIn("Display only: a price to check at the book right now, not an order.", text)
        self.assertIn("> [!TIP] **Sharp moves", text)
        self.assertNotIn("**Feed:** feed stale", text)
        # A feed that stopped 20 minutes ago is flagged even when the window still holds its quotes.
        from Sports_Desk.interfaces.obsidian_exporter import collect, render
        snapshot = collect(self._hook(), db_path=self.db, now=NOW + timedelta(minutes=16))
        section = "\n".join(render(snapshot, "x", self.vault).splitlines())
        self.assertIn("[!INFO] **Feed:** feed stale / newest quote 21.0 min ago (> 15 min)", section)
        # A snapshot without the scan renders the section as unavailable rather than crashing.
        self.assertIn("_Stale-quote scan unavailable: boom._", "\n".join(
            render({**snapshot, "stale": None, "stale_error": "boom"}, "x", self.vault).splitlines()))

    def test_the_section_caps_at_eight_with_an_overflow_notice(self):
        for i in range(10):                                                      # ten sharp moves, ten stale books
            self._measure("Pinnacle", 2.00, 9, selection="Sel%d" % i)
            self._measure("Pinnacle", 1.80, 5, selection="Sel%d" % i)
            self._measure("DraftKings", 2.05, 10, selection="Sel%d" % i)
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertIn("**Sharp moves (last 180m): 10** · stale retail quotes: **10**", text)
        self.assertEqual(text.count("> - `Pinnacle` G1 moneyline"), 8)
        self.assertEqual(text.count("> - 🐌 `DraftKings` still"), 8)
        self.assertIn("> *(and 2 more sharp move(s) / 2 more stale hit(s)... run `monarch_shark --stale` for the full list)*", text)
        # Exactly eight: no overflow line.
        import sqlite3
        con = sqlite3.connect(str(self.db))
        con.execute("DELETE FROM fair_odds_measurements WHERE selection IN ('Sel8', 'Sel9')")
        con.commit()
        con.close()
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertNotIn("more sharp move", text)
        self.assertEqual(text.count("> - 🐌 `DraftKings` still"), 8)

    def test_the_header_says_whether_the_feed_is_alive(self):
        from Sports_Desk.interfaces.obsidian_exporter import collect, feed_liveness_line, render
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertIn("> - **Feed Liveness**: `none` [NO QUOTES]", text)
        self._measure("Pinnacle", 2.00, 5)
        text = self._export()[0].read_text(encoding="utf-8")
        self.assertIn("> - **Feed Liveness**: `5.0m ago` [ACTIVE]", text)
        snapshot = collect(self._hook(), db_path=self.db, now=NOW + timedelta(minutes=16))
        self.assertIn("> - **Feed Liveness**: `21.0m ago` [STALE]", render(snapshot, "x", self.vault))
        snapshot = collect(self._hook(), db_path=self.db, now=NOW + timedelta(hours=15, minutes=25))
        self.assertIn("> - **Feed Liveness**: `15.5h ago` [STALE]", render(snapshot, "x", self.vault))
        self.assertEqual(feed_liveness_line(None), "> - **Feed Liveness**: `unavailable`")
        # The header line sits inside the Desk Snapshot callout, before the un-exported count.
        text = render(snapshot, "x", self.vault)
        self.assertLess(text.index("**Feed Liveness**"), text.index("**Un-exported > "))
        self.assertGreater(text.index("**Feed Liveness**"), text.index("**Desk Snapshot**"))
