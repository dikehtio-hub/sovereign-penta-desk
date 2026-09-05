"""
Round 62 (Directive 62-1): the cross-market dutch recorder. Offline: a temp
imports folder and a temp sports_market.db. What must be true: both legs land
where each belongs under ONE arb_group and ONE timestamp, the receipt's notes
carry what the risk simulator needs to price the dutch, a bookkeeping failure
on one side never raises, and the simulator's reader measures the desk from
what was written.
"""
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cross_market import execution_log as xl
from cross_market import risk_simulator as rs


class TestDutchEconomics(unittest.TestCase):

    def test_the_worse_branch_prices_the_dutch(self):
        econ = xl.dutch_economics(pm_shares=100.0, pm_price=0.48, stake=47.62, decimal_odds=2.10)
        self.assertAlmostEqual(econ.cost, 95.62, places=6)
        self.assertAlmostEqual(econ.payout, 100.0, places=2)                  # min(100 shares x $1, 47.62 x 2.10)
        self.assertAlmostEqual(econ.gross, 100.0 / 95.62 - 1.0, places=6)
        lopsided = xl.dutch_economics(100.0, 0.48, 20.0, 2.10)                 # book leg too small: its branch binds
        self.assertAlmostEqual(lopsided.payout, 42.0, places=6)
        self.assertLess(lopsided.gross, 0.0)
        for bad in ((0, 0.5, 10, 2.0), (10, 0, 10, 2.0), (10, 0.5, -1, 2.0), (10, 0.5, 10, 1.0)):
            with self.assertRaises(ValueError):
                xl.dutch_economics(*bad)


class TestRecordDutch(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.imports = self.root / "imports"
        self.sports_db = self.root / "sports_market.db"

    def tearDown(self):
        self.temp.cleanup()

    def record(self, i=0, **overrides):
        kwargs = dict(pm_market="BILLS_ML_YES", pm_price=0.48, pm_shares=100.0, book="betmgm", selection="Buffalo Bills",
                      decimal_odds=2.10, stake=47.62, event_id="E%d" % i, sport="NFL", market_type="moneyline",
                      timestamp="2026-09-0%d 14:00:00" % (1 + i % 9), imports_dir=self.imports, sports_db=self.sports_db)
        kwargs.update(overrides)
        return xl.record_dutch(**kwargs)

    def test_both_legs_are_written_under_one_group_and_one_stamp(self):
        record = self.record(pm_tx_hash="0xabc")
        self.assertTrue(record["complete"])
        self.assertTrue(record["arb_group"].startswith("xm-20260901T140000-"))
        receipt = Path(record["polymarket"]["receipt"])
        self.assertTrue(receipt.exists())
        self.assertTrue(receipt.name.startswith("fills_polymarket_dutched_arb_"))
        with open(receipt, newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual((row["timestamp"], row["symbol"], row["side"], row["source"]),
                         ("2026-09-01 14:00:00", "BILLS_ML_YES", "BUY", "polymarket"))
        self.assertEqual(row["tx_hash"], "0xabc")
        self.assertIn("strategy:dutched_arb;", row["notes"])
        self.assertIn("arb_group:%s;" % record["arb_group"], row["notes"])
        self.assertIn("gross:%.6f;" % record["economics"]["gross"], row["notes"])
        self.assertIn("cost:95.62;", row["notes"])
        self.assertIn("book_leg:betmgm@2.1000;", row["notes"])
        con = sqlite3.connect(str(self.sports_db))
        bet = con.execute("SELECT placed_at, book, selection, decimal_odds, stake, bet_kind, arb_group, notes "
                          "FROM placed_bets WHERE id=?", (record["sportsbook"]["placed_bet_id"],)).fetchone()
        con.close()
        self.assertEqual(bet[0], "2026-09-01T14:00:00+00:00")
        self.assertEqual((bet[1], bet[2], bet[3], bet[4], bet[5], bet[6]),
                         ("betmgm", "Buffalo Bills", 2.10, 47.62, "arbitrage", record["arb_group"]))
        self.assertIn("strategy:dutched_arb;", bet[7])
        text = xl.format_record(record)
        self.assertIn("[DUTCH] xm-", text)
        self.assertIn("placed_bets id %d" % record["sportsbook"]["placed_bet_id"], text)
        self.assertNotIn("INCOMPLETE", text)

    def test_a_failing_side_is_reported_never_raised(self):
        record = self.record(bet_writer=mock.Mock(side_effect=RuntimeError("db locked")))
        self.assertFalse(record["complete"])
        self.assertIsNotNone(record["polymarket"]["receipt"])
        self.assertEqual(record["sportsbook"]["error"], "RuntimeError: db locked")
        self.assertIn("INCOMPLETE", xl.format_record(record))
        record = self.record(i=1, receipt_writer=mock.Mock(return_value=None))
        self.assertFalse(record["complete"])
        self.assertIsNone(record["polymarket"]["receipt"])
        self.assertIsNotNone(record["sportsbook"]["placed_bet_id"])
        self.assertIn("receipt NOT written", xl.format_record(record))

    def test_the_simulator_measures_the_desk_from_the_recorded_dutches(self):
        for i in range(10):                                                  # 10 receipts over 2026-09-01 .. 09-09 (+1 wrap)
            self.record(i=i, pm_price=0.48 + 0.001 * i)
        arbs = rs._measure_arb_history(self.imports)
        self.assertEqual((arbs["fills"], arbs["executions"], arbs["priced_executions"]), (10, 10, 10))
        self.assertEqual(arbs["span_days"], 9)
        self.assertAlmostEqual(arbs["arb_per_day"], 10 / 9, places=6)
        self.assertAlmostEqual(arbs["gross_return_mean"], 100.0 / 95.62 - 1.0, delta=0.01)   # from the notes
        self.assertAlmostEqual(arbs["capital_mean"], 95.62, delta=0.6)                        # cost from the notes
        inputs = rs.load_live_inputs(self.root / "none.json", self.root / "none.db", self.sports_db,
                                     use_tax_config=False, imports_dir=self.imports)
        self.assertAlmostEqual(inputs.arb_per_day, 10 / 9, places=6)
        self.assertTrue(inputs.provenance["arb_per_day"].startswith("measured (imports receipts, 10 fills / 10 arbs"))
        # The book legs are wagers in placed_bets too, but < 20 settled: sports stays assumed.
        self.assertEqual(inputs.provenance["sports_bets_per_day"], "assumed (< 20 settled wagers)")

    def test_paper_fills_never_touch_the_ledger_or_placed_bets(self):
        paper_dir = self.root / "paper"
        record = self.record(paper=True, imports_dir=paper_dir)
        self.assertTrue(record["paper"] and record["complete"])
        self.assertIsNone(record["sportsbook"]["placed_bet_id"])
        self.assertFalse(self.sports_db.exists())                             # no desk DB was even created
        self.assertEqual(len(list(self.imports.glob("*.csv"))) if self.imports.exists() else 0, 0)
        receipts = sorted(paper_dir.glob("fills_*_dutched_arb_*.csv"))
        self.assertEqual(len(receipts), 2)
        self.assertTrue(any(r.name.startswith("fills_polymarket_") for r in receipts))
        self.assertTrue(any(r.name.startswith("fills_sportsbook_") for r in receipts))
        for path in receipts:
            with open(path, newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertIn("paper:1;", row["notes"])
            self.assertIn("arb_group:%s;" % record["arb_group"], row["notes"])
            self.assertEqual(row["timestamp"], "2026-09-01 14:00:00")
        text = xl.format_record(record)
        self.assertIn("PAPER (no ledger, no placed_bets)", text)
        self.assertIn("PAPER receipt", text)
        # Paper history is measurable from its own folder, priced from the notes, not from the leg prices.
        for i in range(1, 10):
            self.record(i=i, paper=True, imports_dir=paper_dir)
        arbs = rs._measure_arb_history(paper_dir)
        self.assertEqual((arbs["fills"], arbs["executions"], arbs["priced_executions"]), (20, 10, 10))
        self.assertAlmostEqual(arbs["gross_return_mean"], 100.0 / 95.62 - 1.0, places=6)

    def test_cli_refuses_explicit_paths_that_do_not_exist(self):
        base = ["--pm-market", "M", "--pm-price", "0.48", "--pm-shares", "100", "--book", "b", "--selection", "s",
                "--odds", "2.10", "--stake", "47.62", "--event-id", "E", "--sport", "NFL", "--json"]
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(xl.main(base + ["--sports-db", str(self.root / "typo.db")]), 2)
        self.assertIn("refused: --sports-db", fake_print.call_args_list[0].args[0])
        self.assertFalse((self.root / "typo.db").exists())
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(xl.main(base + ["--imports-dir", str(self.root / "nowhere")]), 2)
        self.assertIn("refused: --imports-dir", fake_print.call_args_list[0].args[0])
        self.assertFalse((self.root / "nowhere").exists())
        self.assertFalse(list(self.root.rglob("fills_*.csv")))                # nothing written anywhere
        # Existing explicit paths are accepted (paper mode, so no ledger involved).
        (self.root / "paper").mkdir()
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(xl.main(base + ["--paper", "--imports-dir", str(self.root / "paper")]), 0)
        self.assertTrue(json.loads(fake_print.call_args_list[0].args[0])["paper"])

    def test_cli_records_and_reports(self):
        from Sports_Desk.data.db import init_market_db
        self.imports.mkdir()
        init_market_db(self.sports_db)                                         # explicit paths must exist (Ruling 63-4)
        argv = ["--pm-market", "BILLS_ML_YES", "--pm-price", "0.48", "--pm-shares", "100", "--book", "betmgm",
                "--selection", "Buffalo Bills", "--odds", "2.10", "--stake", "47.62", "--event-id", "E9", "--sport", "NFL",
                "--timestamp", "2026-09-05 12:00:00", "--imports-dir", str(self.imports), "--sports-db", str(self.sports_db)]
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(xl.main(argv + ["--json"]), 0)
        record = json.loads(fake_print.call_args_list[0].args[0])
        self.assertTrue(record["complete"])
        self.assertEqual(record["timestamp"], "2026-09-05 12:00:00")
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(xl.main(argv), 0)
        self.assertIn("[DUTCH]", fake_print.call_args_list[0].args[0])
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(xl.main(argv[:10] + ["--odds", "1.0"] + argv[12:]), 2)  # refused economics
        self.assertIn("refused", fake_print.call_args_list[0].args[0])
        self.assertEqual(len(list(self.imports.glob("fills_polymarket_dutched_arb_*.csv"))), 2)


if __name__ == "__main__":
    unittest.main()
