"""
Unit tests for Tradovate / CME futures receipt ingestion in Tax Reserve Agent
"""
import unittest
from pathlib import Path
import tempfile
from Tax_Reserve_Agent.database.db import get_connection, init_db
from Tax_Reserve_Agent.ingestors.csv_watcher import CSVWatcher
from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt
from Tax_Reserve_Agent.engine.tax_calculator import calculate_tax_summary


class TestTradovateReceipts(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        self.imports_dir = self.root / "imports"
        self.imports_dir.mkdir(parents=True)
        self.db_path = self.root / "tax_ledger.db"
        init_db(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_tradovate_fill_receipt_ingestion(self):
        # 1. Log a Tradovate fill receipt
        path = log_execution_receipt(
            symbol="NQ",
            side="BUY",
            quantity=1.0,
            price=18500.0,
            strategy="STACK_0_HYBRID_TIMELINE",
            venue="tradovate",
            fee=4.50,
            tx_hash="tradovate_order_998877",
            imports_dir=self.imports_dir
        )
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

        # 2. Process via CSVWatcher (two scans for stability check)
        watcher = CSVWatcher(imports_dir=self.imports_dir, db_path=self.db_path)
        watcher.scan_once()
        results = watcher.scan_once()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ok")

        # 3. Verify ledger record
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT source, asset_class, symbol, side, quantity, price, fee, notes FROM transactions")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 1)
        row = dict(rows[0])
        self.assertEqual(row["source"], "tradovate")
        self.assertEqual(row["asset_class"], "futures")
        self.assertEqual(row["symbol"], "NQ")
        self.assertEqual(row["side"], "BUY")
        self.assertEqual(row["quantity"], 1.0)
        self.assertEqual(row["price"], 18500.0)
        self.assertEqual(row["fee"], 4.50)
        self.assertIn("strategy:STACK_0_HYBRID_TIMELINE;", row["notes"])
        conn.close()


class TestSection1256Treatment(unittest.TestCase):
    """
    IRC 1256(a)(3): a regulated futures contract is taxed 60% long-term / 40%
    short-term regardless of holding period. Day-traded CME contracts therefore
    do not book at the full short-term rate.

    This LOWERS the reserve, which is the one direction a tax reserve should
    never move by accident - so these tests pin the rate, pin that futures are
    carved out of the term buckets rather than taxed twice, and pin that a 1256
    loss releases nothing.
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "tax_ledger.db"
        init_db(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _pnl(self, asset_class, term, net, symbol="ES"):
        conn = get_connection(self.db_path)
        conn.execute(
            """INSERT INTO realized_pnl
               (tax_year, asset_class, symbol, term, net_gain_loss, proceeds,
                cost_basis, quantity, holding_period_days, opened_at, closed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (2026, asset_class, symbol, term, net, abs(net), 0.0, 1.0, 30,
             "2026-01-01T00:00:00", "2026-02-01T00:00:00"))
        conn.commit()
        conn.close()

    def _summary(self):
        return calculate_tax_summary(tax_year=2026, db_path=self.db_path)

    def test_the_blended_rate_is_sixty_forty(self):
        """
        IRC 1256(a)(3): 60% long-term / 40% short-term regardless of holding.

        The state rate is READ FROM CONFIG rather than hardcoded. It used to be a
        literal 0.05, which silently stopped matching when the rates were
        unbundled in 26k and the NJ rate went in - the blend was right and the
        test was wrong.
        """
        from ..config import load_config
        rates = load_config().get("tax_rates", {})
        long_term = (rates.get("long_term_capital_gains", 0.15)
                     + rates.get("state_tax_rate", 0.05))
        s = self._summary()
        self.assertAlmostEqual(
            s["futures_rate"],
            0.60 * long_term + 0.40 * s["effective_tax_rate"], places=9)

    def test_the_blended_rate_is_below_the_short_term_rate(self):
        s = self._summary()
        self.assertLess(s["futures_rate"], s["effective_tax_rate"])

    def test_futures_gains_are_escrowed_at_the_blended_rate(self):
        self._pnl("futures", "SHORT_TERM", 10_000.0)
        s = self._summary()
        self.assertAlmostEqual(s["futures_net"], 10_000.0, places=6)
        self.assertAlmostEqual(s["escrow_futures"],
                               10_000.0 * s["futures_rate"], places=6)

    def test_futures_are_not_also_taxed_as_short_term(self):
        """Carved out of the term buckets - leaving them in would tax them twice."""
        self._pnl("futures", "SHORT_TERM", 10_000.0)
        s = self._summary()
        self.assertEqual(s["escrow_short_term"], 0.0)
        self.assertEqual(s["escrow_long_term"], 0.0)
        self.assertAlmostEqual(s["tax_escrow_reserve"], s["escrow_futures"],
                               places=6)

    def test_a_long_held_futures_contract_gets_the_same_treatment(self):
        """1256 ignores holding period entirely."""
        self._pnl("futures", "LONG_TERM", 10_000.0)
        s = self._summary()
        self.assertAlmostEqual(s["escrow_futures"],
                               10_000.0 * s["futures_rate"], places=6)
        self.assertEqual(s["escrow_long_term"], 0.0)

    def test_crypto_is_untouched_by_the_1256_carve_out(self):
        self._pnl("crypto", "SHORT_TERM", 10_000.0, symbol="ETH")
        s = self._summary()
        self.assertEqual(s["futures_net"], 0.0)
        self.assertEqual(s["escrow_futures"], 0.0)
        self.assertAlmostEqual(s["escrow_short_term"],
                               10_000.0 * s["effective_tax_rate"], places=6)

    def test_the_two_buckets_are_escrowed_independently(self):
        self._pnl("crypto", "SHORT_TERM", 10_000.0, symbol="ETH")
        self._pnl("futures", "SHORT_TERM", 10_000.0)
        s = self._summary()
        expected = (10_000.0 * s["effective_tax_rate"]
                    + 10_000.0 * s["futures_rate"])
        self.assertAlmostEqual(s["tax_escrow_reserve"], expected, places=6)

    def test_1256_lowers_the_reserve_versus_short_term_treatment(self):
        """The whole point, stated as the cash it frees."""
        self._pnl("futures", "SHORT_TERM", 10_000.0)
        s = self._summary()
        as_short_term = 10_000.0 * s["effective_tax_rate"]
        self.assertLess(s["escrow_futures"], as_short_term)

    def test_a_net_1256_loss_reserves_nothing_and_releases_nothing(self):
        """
        Floored at zero. 1256 losses carry BACK three years against prior 1256
        gains - a filing election, not a reason to release cash today.
        """
        self._pnl("futures", "SHORT_TERM", -10_000.0)
        s = self._summary()
        self.assertEqual(s["escrow_futures"], 0.0)
        self.assertEqual(s["tax_escrow_reserve"], 0.0)

    def test_a_futures_loss_does_not_offset_a_crypto_gain(self):
        """Separate buckets; crediting one against the other lowers the reserve."""
        self._pnl("crypto", "SHORT_TERM", 10_000.0, symbol="ETH")
        self._pnl("futures", "SHORT_TERM", -10_000.0)
        s = self._summary()
        self.assertAlmostEqual(s["tax_escrow_reserve"],
                               10_000.0 * s["effective_tax_rate"], places=6)

    def test_futures_still_appear_in_the_asset_breakdown(self):
        """Carved out of the RATE, not out of the reporting."""
        self._pnl("futures", "SHORT_TERM", 10_000.0)
        self.assertIn("futures", self._summary()["breakdown_by_asset"])

    def test_the_escrow_total_is_the_sum_of_its_parts(self):
        self._pnl("crypto", "SHORT_TERM", 5_000.0, symbol="ETH")
        self._pnl("futures", "SHORT_TERM", 5_000.0)
        s = self._summary()
        self.assertAlmostEqual(
            s["tax_escrow_reserve"],
            s["escrow_short_term"] + s["escrow_long_term"]
            + s["escrow_futures"] + s["escrow_ordinary"], places=6)


if __name__ == "__main__":
    unittest.main()
