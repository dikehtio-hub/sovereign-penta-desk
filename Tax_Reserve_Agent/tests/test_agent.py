"""
Unit tests for Tax Reserve Agent.
"""
import unittest
import tempfile
from pathlib import Path

from Tax_Reserve_Agent.database.db import init_db, get_connection
from Tax_Reserve_Agent.engine.lot_engine import process_batch
from Tax_Reserve_Agent.engine.tax_calculator import calculate_tax_summary
from Tax_Reserve_Agent.ingestors.polymarket import PolymarketIngestor
from Tax_Reserve_Agent.ingestors.spot import SpotIngestor
from Tax_Reserve_Agent.ingestors.options import OptionsIngestor

class TestTaxReserveAgent(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tax.db"
        init_db(self.db_path)
        
        self.test_config = {
            "tax_rates": {
                "short_term_capital_gains": 0.28,
                "state_tax_rate": 0.05,
                "safety_buffer_pct": 0.02, # Composite = 35%
                "long_term_capital_gains": 0.15
            },
            "portfolio": {
                "default_cash_balance_usdc": 10000.0,
                "tax_year": 2026
            }
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_polymarket_redemption_gain(self):
        """Buy 1,000 shares at $0.40 ($400) and redeem at $1.00 ($1,000) -> Net Gain = +$600."""
        txs = [
            PolymarketIngestor.create_manual_trade("MARKET_A_YES", "BUY", 1000, 0.40, "2026-01-10 12:00:00"),
            PolymarketIngestor.create_redemption_trade("MARKET_A_YES", 1000, "2026-01-20 12:00:00")
        ]
        process_batch(txs, db_path=self.db_path)
        
        summary = calculate_tax_summary(tax_year=2026, db_path=self.db_path, config=self.test_config)
        self.assertAlmostEqual(summary["total_gross_gains"], 600.0)
        self.assertAlmostEqual(summary["net_capital_gains"], 600.0)
        # Tax Escrow = 600 * 0.35 = $210
        self.assertAlmostEqual(summary["tax_escrow_reserve"], 210.0)
        # Safe bankroll = $10,000 - $210 = $9,790
        self.assertAlmostEqual(summary["safe_deployable_bankroll"], 9790.0)

    def test_options_loss_offset(self):
        """
        Spot gain of +$1,000 and Options loss of -$400.
        Net capital gain should be +$600.
        """
        txs = [
            # Spot trade: Buy 1 ETH at $2,000, Sell at $3,000 -> +$1,000
            SpotIngestor.create_trade("ETH/USDC", "BUY", 1.0, 2000.0, "2026-01-01 10:00:00"),
            SpotIngestor.create_trade("ETH/USDC", "SELL", 1.0, 3000.0, "2026-01-15 10:00:00"),
            
            # Options trade: Buy call for $400, expires worthless -> -$400
            OptionsIngestor.create_long_option_buy("ETH-3500-CALL", 1.0, 400.0, "2026-01-05 10:00:00"),
            OptionsIngestor.create_option_expiration("ETH-3500-CALL", 1.0, "2026-01-30 10:00:00")
        ]
        process_batch(txs, db_path=self.db_path)
        
        summary = calculate_tax_summary(tax_year=2026, db_path=self.db_path, config=self.test_config)
        self.assertAlmostEqual(summary["total_gross_gains"], 1000.0)
        self.assertAlmostEqual(summary["total_gross_losses"], -400.0)
        self.assertAlmostEqual(summary["net_capital_gains"], 600.0)
        # Tax Escrow at 35% on $600 net = $210
        self.assertAlmostEqual(summary["tax_escrow_reserve"], 210.0)
        self.assertAlmostEqual(summary["safe_deployable_bankroll"], 9790.0)

if __name__ == "__main__":
    unittest.main()
