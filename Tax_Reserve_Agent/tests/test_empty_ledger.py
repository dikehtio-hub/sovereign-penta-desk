"""
Round 33 Ruling C: an empty ledger with nothing declared sizes to $0.00.

THE DEFECT. config.yaml shipped `default_cash_balance_usdc: 10000.00` and every
risk limit scaled off it - safe bankroll $10,000, the hl_basis_harvest bucket
$2,500, the per-order cap $125 - against a ledger holding ZERO transactions. The
gate worked exactly as designed and the number it protected had never been
measured. A test count of 2,190 said nothing about this because every test
declared its own balance.

So these tests pin three things: an empty ledger with nothing declared refuses
with a reason that says why; an explicit declaration (paper bankroll, live cash,
or a config number) still works, because tests and simulations need it; and a
DEPOSIT row makes the balance MEASURED, which is the state production should be
in from now on.
"""

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from Tax_Reserve_Agent.database.db import get_connection, init_db
from Tax_Reserve_Agent.engine.lot_engine import CASH_SIDES, process_batch
from Tax_Reserve_Agent.engine.tax_calculator import (CASH_ASSET_CLASS,
                                                     calculate_tax_summary)
from Tax_Reserve_Agent.ingestors.csv_watcher import (ClassificationError, CSVWatcher,
                                                     classify_csv, load_deposit_csv)
from Tax_Reserve_Agent.interfaces.monarch_hook import (EMPTY_LEDGER_REASON,
                                                       EmptyLedgerRefusal,
                                                       MonarchBankrollHook)

RATES = {"federal_ordinary_rate": 0.24, "short_term_capital_gains": 0.24,
         "long_term_capital_gains": 0.15, "state_tax_rate": 0.0637,
         "safety_buffer_pct": 0.02}

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "imports" / "samples"


def production_config(**portfolio):
    """What config.yaml now says: no balance, unless a test declares one."""
    return {"tax_rates": dict(RATES),
            "portfolio": {"default_cash_balance_usdc": None, "tax_year": 2026, **portfolio}}


class EmptyLedgerBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledger = self.root / "tax.db"
        self.drop = self.root / "imports"
        self.drop.mkdir()
        init_db(self.ledger)

    def tearDown(self):
        self.temp.cleanup()

    def _hook(self, **kwargs):
        return MonarchBankrollHook(db_path=self.ledger, config=production_config(), **kwargs)

    def _count(self, table):
        conn = get_connection(self.ledger)
        try:
            return conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        finally:
            conn.close()

    def _write(self, name, text):
        path = self.drop / name
        path.write_text(text, encoding="utf-8")
        return path

    def _ingest(self, name, text):
        self._write(name, text)
        watcher = CSVWatcher(imports_dir=self.drop, db_path=self.ledger, archive=False)
        return watcher.scan_once(require_stable=False)


# ---------------------------------------------------------------------------
# The refusal
# ---------------------------------------------------------------------------

class TestEmptyLedgerRefuses(EmptyLedgerBase):

    def test_an_empty_ledger_with_nothing_declared_is_zero_not_a_placeholder(self):
        summary = calculate_tax_summary(db_path=self.ledger, config=production_config())
        self.assertTrue(summary["empty_ledger"])
        self.assertEqual(summary["cash_source"], "none")
        self.assertEqual(summary["ledger_transactions"], 0)
        self.assertEqual(summary["liquid_cash_balance"], 0.0)
        self.assertEqual(summary["safe_deployable_bankroll"], 0.0)

    def test_the_hook_rejects_with_a_reason_that_names_the_cause(self):
        """
        Not "requested notional exceeds safe bankroll". That reads like a sizing
        bug and sends the operator looking for one that is not there.
        """
        decision = self._hook().check_order(100.0)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.approved_notional, 0.0)
        self.assertIn("EMPTY", decision.reason)
        self.assertIn("paper-bankroll", decision.reason)
        self.assertEqual(decision.reason, EMPTY_LEDGER_REASON)

    def test_is_funded_and_require_funded(self):
        hook = self._hook()
        self.assertFalse(hook.is_funded)
        with self.assertRaises(EmptyLedgerRefusal):
            hook.require_funded()

    def test_the_status_line_says_it_in_words(self):
        self.assertIn("EMPTY", self._hook().status_line())
        self.assertIn("FAIL-CLOSED", self._hook().status_line())

    def test_a_config_without_the_key_at_all_does_not_crash(self):
        """`float(None)` was the failure mode a nulled yaml would have caused."""
        config = {"tax_rates": dict(RATES), "portfolio": {"tax_year": 2026}}
        summary = calculate_tax_summary(db_path=self.ledger, config=config)
        self.assertEqual(summary["liquid_cash_balance"], 0.0)
        self.assertEqual(summary["cash_source"], "none")


# ---------------------------------------------------------------------------
# Explicit declarations still work
# ---------------------------------------------------------------------------

class TestExplicitDeclarations(EmptyLedgerBase):

    def test_a_paper_bankroll_unlocks_sizing_and_is_labelled(self):
        hook = self._hook(paper_bankroll=10_000.0)
        snapshot = hook.snapshot()
        self.assertTrue(snapshot["paper_bankroll"])
        self.assertEqual(snapshot["cash_source"], "override")
        self.assertAlmostEqual(snapshot["liquid_cash_balance"], 10_000.0, places=2)
        self.assertTrue(hook.is_funded)
        decision = hook.check_order(100.0)
        self.assertTrue(decision.approved, decision.reason)

    def test_live_cash_unlocks_sizing_per_call(self):
        decision = self._hook().check_order(100.0, live_cash=5_000.0)
        self.assertTrue(decision.approved, decision.reason)
        self.assertAlmostEqual(decision.cash_balance, 5_000.0, places=2)

    def test_live_cash_beats_a_paper_bankroll(self):
        snapshot = self._hook(paper_bankroll=10_000.0).snapshot(live_cash=250.0)
        self.assertAlmostEqual(snapshot["liquid_cash_balance"], 250.0, places=2)
        self.assertFalse(snapshot["paper_bankroll"])

    def test_a_number_in_config_is_a_declaration_and_still_works(self):
        """
        Backward compatibility for every existing fixture. A config that carries
        a balance is a declared paper balance - fine for a test - and is labelled
        as such, so it cannot be mistaken for a measured one.
        """
        hook = MonarchBankrollHook(db_path=self.ledger,
                                   config=production_config(default_cash_balance_usdc=10_000.0))
        snapshot = hook.snapshot()
        self.assertEqual(snapshot["cash_source"], "declared")
        self.assertTrue(hook.check_order(100.0).approved)


# ---------------------------------------------------------------------------
# Deposits make it measured
# ---------------------------------------------------------------------------

DEPOSIT_CSV = ("timestamp,side,amount,symbol\n"
               "2026-09-04 00:00:00,DEPOSIT,10000.00,USDC\n")


class TestDeposits(EmptyLedgerBase):

    def test_a_deposit_csv_grounds_the_balance_in_the_ledger(self):
        results = self._ingest("seed_bankroll.csv", DEPOSIT_CSV)
        self.assertEqual(results[0]["status"], "ok", results[0]["reason"])
        self.assertEqual(results[0]["source"], "deposit")
        summary = calculate_tax_summary(db_path=self.ledger, config=production_config())
        self.assertFalse(summary["empty_ledger"])
        self.assertEqual(summary["cash_source"], "deposits")
        self.assertAlmostEqual(summary["liquid_cash_balance"], 10_000.0, places=2)
        self.assertAlmostEqual(summary["ledger_deposits"], 10_000.0, places=2)
        self.assertEqual(summary["ledger_transactions"], 1)
        self.assertTrue(self._hook().is_funded)
        self.assertTrue(self._hook().check_order(100.0).approved)

    def test_a_deposit_is_money_not_a_position(self):
        """No lot opens, nothing is realised, and no gain is ever summed from it."""
        self._ingest("seed_bankroll.csv", DEPOSIT_CSV)
        self.assertEqual(self._count("transactions"), 1)
        self.assertEqual(self._count("tax_lots"), 0)
        self.assertEqual(self._count("realized_pnl"), 0)
        summary = calculate_tax_summary(db_path=self.ledger, config=production_config())
        self.assertEqual(summary["net_capital_gains"], 0.0)
        self.assertEqual(summary["tax_escrow_reserve"], 0.0)
        self.assertAlmostEqual(summary["safe_deployable_bankroll"], 10_000.0, places=2)

    def test_a_withdrawal_reduces_the_measured_balance(self):
        self._ingest("seed_bankroll.csv", DEPOSIT_CSV)
        self._ingest("withdrawal.csv", "timestamp,side,amount\n"
                                       "2026-09-10 00:00:00,WITHDRAWAL,2500\n")
        summary = calculate_tax_summary(db_path=self.ledger, config=production_config())
        self.assertAlmostEqual(summary["liquid_cash_balance"], 7_500.0, places=2)
        self.assertEqual(summary["ledger_transactions"], 2)

    def test_measured_beats_declared_but_not_an_override(self):
        """Precedence: override > deposits > declared > none."""
        self._ingest("seed_bankroll.csv", DEPOSIT_CSV)
        declared = production_config(default_cash_balance_usdc=99_999.0)
        summary = calculate_tax_summary(db_path=self.ledger, config=declared)
        self.assertEqual(summary["cash_source"], "deposits")
        self.assertAlmostEqual(summary["liquid_cash_balance"], 10_000.0, places=2)
        hook = MonarchBankrollHook(db_path=self.ledger, config=declared)
        self.assertAlmostEqual(hook.snapshot(live_cash=42.0)["liquid_cash_balance"], 42.0)

    def test_re_dropping_the_seed_does_not_double_the_balance(self):
        self._ingest("seed_bankroll.csv", DEPOSIT_CSV)
        self._ingest("seed_bankroll_again.csv", DEPOSIT_CSV)
        summary = calculate_tax_summary(db_path=self.ledger, config=production_config())
        self.assertAlmostEqual(summary["liquid_cash_balance"], 10_000.0, places=2)

    def test_the_committed_sample_ingests(self):
        sample = SAMPLES / "seed_bankroll.csv"
        self.assertTrue(sample.exists(), sample)
        rows = load_deposit_csv(sample)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["side"], "DEPOSIT")
        self.assertEqual(rows[0]["asset_class"], CASH_ASSET_CLASS)
        self.assertAlmostEqual(rows[0]["total_value"], 10_000.0, places=2)
        process_batch(rows, db_path=self.ledger)
        self.assertEqual(self._count("transactions"), 1)
        self.assertEqual(self._count("tax_lots"), 0)

    def test_cash_sides_are_the_two_and_only_the_two(self):
        self.assertEqual(set(CASH_SIDES), {"DEPOSIT", "WITHDRAWAL"})


class TestDepositClassification(EmptyLedgerBase):

    def test_classified_by_filename(self):
        path = self._write("seed_bankroll.csv", DEPOSIT_CSV)
        source, reason = classify_csv(path, [{"timestamp": "x", "side": "DEPOSIT", "amount": "1"}])
        self.assertEqual(source, "deposit")
        self.assertIn("filename", reason)

    def test_classified_by_explicit_source_column(self):
        path = self._write("whatever.csv", "timestamp,side,amount,source\n2026-09-04,DEPOSIT,1,deposit\n")
        source, _ = classify_csv(path, [{"timestamp": "x", "side": "DEPOSIT", "amount": "1",
                                         "source": "deposit"}])
        self.assertEqual(source, "deposit")

    def test_classified_by_side_vocabulary(self):
        path = self._write("mystery.csv", "timestamp,side,amount\n2026-09-04,WITHDRAWAL,1\n")
        source, reason = classify_csv(path, [{"timestamp": "x", "side": "WITHDRAWAL", "amount": "1"}])
        self.assertEqual(source, "deposit")
        self.assertIn("side value", reason)

    def test_a_negative_deposit_is_refused_rather_than_read_as_a_withdrawal(self):
        path = self._write("deposit.csv", "timestamp,side,amount\n2026-09-04,DEPOSIT,-500\n")
        with self.assertRaises(ValueError):
            load_deposit_csv(path)

    def test_an_unknown_side_is_refused(self):
        path = self._write("deposit.csv", "timestamp,side,amount\n2026-09-04,TRANSFER,500\n")
        with self.assertRaises(ValueError):
            load_deposit_csv(path)

    def test_a_bad_file_lands_in_failed_not_in_the_ledger(self):
        results = self._ingest("deposit.csv", "timestamp,side,amount\n2026-09-04,DEPOSIT,abc\n")
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(self._count("transactions"), 0)


if __name__ == "__main__":
    unittest.main()
