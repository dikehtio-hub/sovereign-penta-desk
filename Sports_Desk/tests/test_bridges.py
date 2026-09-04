"""
Unit tests for the three operational bridges (Round 26k).

  A  tax-ledger reconciliation and export - is the escrow even aware?
  B  outcome settlement and realised performance - did we make money?
  C  correlated-event exposure - one game, one position's worth of risk.

Each closes a loop that was open, and each was open in a way that looked fine:
the escrow reported a number, the desk reported an edge, the sizer reported a
stake. None of them were wrong on their own.
"""
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from Sports_Desk.data.db import (desk_performance, init_market_db, mark_exported,
                                 open_desk_exposure, query_placed_bets,
                                 record_placed_bet, record_settled_result,
                                 settle_placed_bets, unsynced_placed_bets)
from Sports_Desk.ingestors.odds_watcher import OddsWatcher
from Sports_Desk.ingestors.results_watcher import ResultsWatcher
from Sports_Desk.interfaces.monarch_shark import Betslip, render_performance
from Tax_Reserve_Agent.database.db import init_db
from Tax_Reserve_Agent.engine.lot_engine import process_batch
from Tax_Reserve_Agent.ingestors.sports_betting import SportsBettingIngestor
from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook

QUOTED = "2026-09-03T18:00:00Z"
STARTS = "2026-09-03T23:00:00Z"
NOW = datetime(2026, 9, 3, 18, 2, 0)


class BridgeTestBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.odds_drop = self.root / "odds"
        self.results_drop = self.root / "results"
        self.tax_drop = self.root / "taxdrop"
        for folder in (self.odds_drop, self.results_drop, self.tax_drop):
            folder.mkdir()
        self.db = self.root / "sports_market.db"
        self.ledger = self.root / "tax.db"
        init_market_db(self.db)
        init_db(self.ledger)
        self.written = []

    def tearDown(self):
        self.temp.cleanup()

    def _hook(self, treatment="professional_schedule_c", cash=50000.0):
        return MonarchBankrollHook(db_path=self.ledger, config={
            "tax_rates": {"federal_ordinary_rate": 0.24,
                          "short_term_capital_gains": 0.24,
                          "long_term_capital_gains": 0.15,
                          "state_tax_rate": 0.05, "safety_buffer_pct": 0.02},
            "portfolio": {"default_cash_balance_usdc": cash, "tax_year": 2026},
            "gambling": {"tax_treatment": treatment, "loss_deduction_pct": 0.90},
            "bot_integration": {"assumed_round_trip_fee": 0.02,
                                "max_position_pct": 0.05, "min_order_usd": 1.0,
                                "strategies": {"sports_betting": 0.15,
                                               "sandbox": 0.85}}})

    def _one_game(self, markets=(("moneyline", ""),)):
        rows = ["event_id,sport,market_type,line,selection,book,odds,is_sharp,"
                "timestamp,start_time"]
        for index, (market, line) in enumerate(markets):
            rows += [f"G1,NFL,{market},{line},A{index},Pinnacle,-140,1,{QUOTED},{STARTS}",
                     f"G1,NFL,{market},{line},B{index},Pinnacle,+120,1,{QUOTED},{STARTS}",
                     f"G1,NFL,{market},{line},B{index},DraftKings,+185,0,{QUOTED},{STARTS}"]
        return "\n".join(rows) + "\n"

    def _ingest(self, text=None, hook=None):
        (self.odds_drop / "odds.csv").write_text(text or self._one_game(),
                                                 encoding="utf-8")
        hook = hook or self._hook()
        watcher = OddsWatcher(
            drop_folder=self.odds_drop, db_path=self.db,
            after_tax_hurdle=lambda odds: hook.breakeven_gross_edge(
                category="sports", decimal_odds=odds))
        watcher.scan_once()
        watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)

    def _slip(self, hook=None, answers=("y", "")):
        replies = list(answers)
        return Betslip(hook or self._hook(), db_path=self.db,
                       read=lambda prompt: replies.pop(0) if replies else "y",
                       write=self.written.append, bankroll=50000.0, now=NOW)

    def _said(self, fragment):
        return any(fragment in line for line in self.written)


class TestBridgeCEventExposure(BridgeTestBase):
    """One game gets one position's worth of risk, however many legs it is cut into."""

    FOUR_MARKETS = (("moneyline", ""), ("spread", "-3.5"),
                    ("total", "47.5"), ("spread", "-2.5"))

    def test_the_event_cap_is_scaled_to_the_strategy_bucket(self):
        """
        The obvious reading - 5% of the SAFE BANKROLL - is 6.7x looser than the
        per-order cap once bucketing is on, so it would take about seven legs on
        one game before it bound. Nearly inert, which is not a guard.
        """
        hook = self._hook()
        slip = self._slip(hook)
        safe = hook.get_safe_bankroll(50000.0)
        self.assertAlmostEqual(slip.event_cap(),
                               hook.strategy_budget("sports_betting", safe, 0.0).budget
                               * hook.max_position_pct, places=6)
        self.assertLess(slip.event_cap(), hook.max_position_size(50000.0))

    def test_legs_on_one_game_share_a_single_position_cap(self):
        self._ingest(self._one_game(self.FOUR_MARKETS))
        slip = self._slip()
        rows = slip.show_hotlist()
        self.assertGreaterEqual(len(rows), 4)
        for row in rows:
            slip.stake(row)
        staked = sum(b["stake"] for b in query_placed_bets(db_path=self.db))
        self.assertLessEqual(staked, slip.event_cap() + 1e-6)
        self.assertTrue(self._said("single-game cap"))

    def test_a_different_game_is_unaffected(self):
        two_games = self._one_game() + self._one_game().replace("G1", "G2").split("\n", 1)[1]
        self._ingest(two_games)
        slip = self._slip()
        for row in slip.show_hotlist():
            slip.stake(row)
        events = {b["event_id"] for b in query_placed_bets(db_path=self.db)}
        self.assertEqual(events, {"G1", "G2"})

    def test_a_settled_bet_releases_its_event_exposure(self):
        self._ingest()
        slip = self._slip()
        row = slip.show_hotlist()[0]
        slip.stake(row)
        self.assertGreater(slip.open_event_exposure("G1"), 0.0)
        record_settled_result("G1", "NFL", row["market_type"], row.get("line", ""),
                              row["selection"], 1, db_path=self.db)
        settle_placed_bets(db_path=self.db)
        self.assertEqual(slip.open_event_exposure("G1"), 0.0)


class TestBridgeAReconciliation(BridgeTestBase):
    """The escrow is only as good as the import, and nothing used to check."""

    def _place(self, ticket_id=None, stake=100.0, placed_at="2026-09-01T12:00:00Z"):
        return record_placed_bet("G1", "NFL", "moneyline", "", "Ravens", "draftkings",
                                 2.85, stake, ticket_id=ticket_id,
                                 placed_at=placed_at, db_path=self.db)

    def test_a_bet_the_ledger_has_never_seen_is_reported(self):
        self._place(ticket_id="TKT1")
        stale = unsynced_placed_bets(tax_db_path=self.ledger, now=NOW, db_path=self.db)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["match_confidence"], "ticket")

    def test_a_bet_present_in_the_ledger_is_not_reported(self):
        self._place(ticket_id="TKT1")
        process_batch([SportsBettingIngestor.create_bet_placed(
            "TKT1", "draftkings", "NFL", "Ravens", 100.0, "+185",
            "2026-09-01 12:00:00")], db_path=self.ledger)
        self.assertEqual(
            unsynced_placed_bets(tax_db_path=self.ledger, now=NOW, db_path=self.db), [])

    def test_the_aging_window_suppresses_recent_bets(self):
        self._place(ticket_id="NEW", placed_at="2026-09-03T12:00:00Z")   # hours old
        self.assertEqual(
            unsynced_placed_bets(tax_db_path=self.ledger, older_than_days=3.0,
                                 now=NOW, db_path=self.db), [])
        self.assertEqual(len(unsynced_placed_bets(
            tax_db_path=self.ledger, older_than_days=0.0, now=NOW, db_path=self.db)), 1)

    def test_the_alert_names_the_money_at_risk(self):
        self._place(ticket_id="TKT1", stake=250.0)
        slip = self._slip()
        slip.check_sync(older_than_days=0.0, tax_db_path=self.ledger)
        self.assertTrue(self._said("DO NOT appear in the tax ledger"))
        self.assertTrue(self._said("250.00"))

    def test_an_unreadable_ledger_reports_everything_rather_than_a_clean_slate(self):
        """Failing open here would say "all synced" when nothing was checked."""
        self._place(ticket_id="TKT1")
        stale = unsynced_placed_bets(tax_db_path=self.root / "does-not-exist.db",
                                     now=NOW, db_path=self.db)
        self.assertEqual(len(stale), 1)

    def test_the_export_writes_a_csv_the_ingestor_can_read(self):
        self._place(ticket_id="TKT1")
        slip = self._slip()
        target = slip.export_to_tax_agent(tax_db_path=self.ledger,
                                          drop_dir=self.tax_drop, older_than_days=0.0)
        self.assertIsNotNone(target)
        trades = SportsBettingIngestor.load_from_csv(target)
        self.assertEqual([t["side"] for t in trades], ["BET"])
        self.assertAlmostEqual(trades[0]["price"], 100.0, places=2)
        self.assertAlmostEqual(trades[0]["total_value"], 100.0, places=2)

    def test_an_exported_bet_with_a_ticket_id_is_idempotent_against_the_book(self):
        """
        The whole reason the ticket id is captured. The ingestor builds
        `{book}_{ticket}_bet`, so the book's own export collides and is ignored -
        one wager, one lot. Without it the wager is booked twice.
        """
        self._place(ticket_id="TKT1")
        slip = self._slip()
        target = slip.export_to_tax_agent(tax_db_path=self.ledger,
                                          drop_dir=self.tax_drop, older_than_days=0.0)
        process_batch(SportsBettingIngestor.load_from_csv(target), db_path=self.ledger)
        # Now the book's own export arrives for the same ticket.
        process_batch([SportsBettingIngestor.create_bet_placed(
            "TKT1", "draftkings", "NFL", "Ravens", 100.0, "+185",
            "2026-09-01 12:00:00")], db_path=self.ledger)
        from Tax_Reserve_Agent.database.db import get_connection
        conn = get_connection(self.ledger)
        try:
            lots = conn.execute("SELECT COUNT(*) n, COALESCE(SUM(total_cost_basis),0) b "
                                "FROM tax_lots").fetchone()
        finally:
            conn.close()
        self.assertEqual(lots["n"], 1)
        self.assertAlmostEqual(lots["b"], 100.0, places=2)

    def test_a_bet_with_no_ticket_id_is_exported_but_flagged(self):
        """
        It cannot collide with the book's export, so importing both would double
        the wager. Still written - leaving it out understates the escrow - but
        called out loudly.
        """
        self._place(ticket_id=None)
        slip = self._slip()
        slip.export_to_tax_agent(tax_db_path=self.ledger, drop_dir=self.tax_drop,
                                 older_than_days=0.0)
        self.assertTrue(self._said("NO book ticket id"))
        text = (self.tax_drop / "monarch_shark_bets.csv").read_text(encoding="utf-8")
        self.assertIn("no_book_ticket_id:true", text)

    def test_exporting_nothing_says_so(self):
        slip = self._slip()
        self.assertIsNone(slip.export_to_tax_agent(tax_db_path=self.ledger,
                                                   drop_dir=self.tax_drop))
        self.assertTrue(self._said("already in the tax ledger"))

    def test_export_stamps_the_rows(self):
        self._place(ticket_id="TKT1")
        slip = self._slip()
        slip.export_to_tax_agent(tax_db_path=self.ledger, drop_dir=self.tax_drop,
                                 older_than_days=0.0)
        self.assertIsNotNone(query_placed_bets(db_path=self.db)[0]["exported_at"])


class TestBridgeBSettlement(BridgeTestBase):
    """Realised P&L is the only number here that can be spent."""

    def _place(self, selection="Ravens", odds=2.85, stake=100.0, fair=0.4356):
        return record_placed_bet("G1", "NFL", "moneyline", "", selection, "draftkings",
                                 odds, stake, fair_prob_at_placement=fair,
                                 placed_at="2026-09-01T12:00:00Z", db_path=self.db)

    def test_a_winner_books_its_profit_not_its_payout(self):
        self._place()
        record_settled_result("G1", "NFL", "moneyline", "", "Ravens", 1, db_path=self.db)
        self.assertEqual(settle_placed_bets(db_path=self.db), 1)
        bet = query_placed_bets(db_path=self.db)[0]
        self.assertEqual(bet["outcome"], "WIN")
        self.assertAlmostEqual(bet["realized_pnl"], 100.0 * 1.85, places=6)

    def test_a_loser_books_the_stake(self):
        self._place()
        record_settled_result("G1", "NFL", "moneyline", "", "Ravens", 0, db_path=self.db)
        settle_placed_bets(db_path=self.db)
        bet = query_placed_bets(db_path=self.db)[0]
        self.assertEqual(bet["outcome"], "LOSS")
        self.assertAlmostEqual(bet["realized_pnl"], -100.0, places=6)

    def test_a_push_books_zero_and_leaves_the_ratios_alone(self):
        """A returned stake is not a bet that was won or lost."""
        self._place()
        record_settled_result("G1", "NFL", "moneyline", "", "Ravens", 0, voided=True,
                              db_path=self.db)
        settle_placed_bets(db_path=self.db)
        bet = query_placed_bets(db_path=self.db)[0]
        self.assertEqual(bet["outcome"], "PUSH")
        self.assertEqual(bet["realized_pnl"], 0.0)
        stats = desk_performance(db_path=self.db)
        self.assertEqual(stats["bets_decided"], 0)
        self.assertEqual(stats["turnover"], 0.0)
        self.assertIsNone(stats["win_rate"])

    def test_settlement_is_idempotent(self):
        self._place()
        record_settled_result("G1", "NFL", "moneyline", "", "Ravens", 1, db_path=self.db)
        self.assertEqual(settle_placed_bets(db_path=self.db), 1)
        self.assertEqual(settle_placed_bets(db_path=self.db), 0)

    def test_the_results_watcher_closes_placed_bets_out(self):
        self._place()
        (self.results_drop / "r.csv").write_text(
            "event_id,sport,market_type,line,selection,result\n"
            "G1,NFL,moneyline,,Ravens,win\n", encoding="utf-8")
        watcher = ResultsWatcher(drop_folder=self.results_drop, db_path=self.db,
                                 min_forecasts=1)
        watcher.scan_once()
        reports = watcher.scan_once(now=time.time() + watcher.stability_seconds + 1)
        self.assertEqual(reports[0].bets_settled, 1)

    def test_performance_reports_pnl_roi_and_calibration(self):
        self._place(selection="Ravens", fair=0.50)
        self._place(selection="Chiefs", odds=1.71, fair=0.50)
        record_settled_result("G1", "NFL", "moneyline", "", "Ravens", 1, db_path=self.db)
        record_settled_result("G1", "NFL", "moneyline", "", "Chiefs", 0, db_path=self.db)
        settle_placed_bets(db_path=self.db)
        stats = desk_performance(db_path=self.db)
        self.assertEqual(stats["bets_decided"], 2)
        self.assertAlmostEqual(stats["turnover"], 200.0, places=6)
        self.assertAlmostEqual(stats["realized_pnl"], 85.0, places=6)
        self.assertAlmostEqual(stats["roi"], 0.425, places=6)
        self.assertAlmostEqual(stats["win_rate"], 0.5, places=6)
        self.assertAlmostEqual(stats["expected_win_rate"], 0.5, places=6)

    def test_an_unsettled_desk_says_so_rather_than_reporting_zeros(self):
        self._place()
        stats = desk_performance(db_path=self.db)
        self.assertEqual(stats["bets_settled"], 0)
        self.assertEqual(stats["bets_pending"], 1)
        self.assertIn("Nothing settled yet", render_performance(stats))

    def test_the_render_names_miscalibration_rather_than_bad_luck(self):
        for index in range(20):
            record_placed_bet("E%d" % index, "NFL", "moneyline", "", "X", "dk",
                              2.0, 100.0, fair_prob_at_placement=0.60,
                              placed_at="2026-09-01T12:00:00Z", db_path=self.db)
            record_settled_result("E%d" % index, "NFL", "moneyline", "", "X",
                                  1 if index < 5 else 0, db_path=self.db)
        settle_placed_bets(db_path=self.db)
        text = render_performance(desk_performance(db_path=self.db))
        self.assertIn("MISCALIBRATED", text)

    def test_settled_bets_stop_counting_toward_open_exposure(self):
        self._place()
        self.assertGreater(open_desk_exposure(db_path=self.db), 0.0)
        record_settled_result("G1", "NFL", "moneyline", "", "Ravens", 1, db_path=self.db)
        settle_placed_bets(db_path=self.db)
        self.assertEqual(open_desk_exposure(db_path=self.db), 0.0)


class TestReconcileSpelling(unittest.TestCase):
    """--reconcile and --check-sync are one switch.

    The desk calls this operation reconciliation; the flag was built as
    --check-sync. Rather than rename it and break the existing spelling, both
    land on the same dest. A test guards that, because an argparse alias is
    silent when it regresses - the second spelling simply becomes an
    unrecognised argument at the moment somebody needs it.
    """

    def _parser_dest(self, flag):
        import argparse
        from Sports_Desk.interfaces import monarch_shark
        captured = {}
        real = argparse.ArgumentParser.parse_args

        def spy(self_, argv=None, namespace=None):
            captured["ns"] = real(self_, argv, namespace)
            raise SystemExit(0)

        argparse.ArgumentParser.parse_args = spy
        try:
            with self.assertRaises(SystemExit):
                monarch_shark.main([flag])
        finally:
            argparse.ArgumentParser.parse_args = real
        return captured["ns"]

    def test_both_spellings_set_check_sync(self):
        for flag in ("--check-sync", "--reconcile"):
            with self.subTest(flag=flag):
                self.assertTrue(self._parser_dest(flag).check_sync)

    def test_the_export_targets_the_folder_the_watcher_reads(self):
        """The drop path is not a free choice.

        Tax_Reserve_Agent/config.yaml sets imports.drop_folder to data/imports
        and csv_watcher's DEFAULT_IMPORTS_DIR resolves to the same place. An
        export written anywhere else - data/drop/, say - is a file nothing ever
        picks up: the bridge would appear to work and silently import nothing.
        """
        from Sports_Desk.interfaces.monarch_shark import TAX_DROP_DIR
        from Tax_Reserve_Agent.ingestors.csv_watcher import DEFAULT_IMPORTS_DIR
        self.assertEqual(TAX_DROP_DIR.resolve(), DEFAULT_IMPORTS_DIR.resolve())


if __name__ == "__main__":
    unittest.main()
