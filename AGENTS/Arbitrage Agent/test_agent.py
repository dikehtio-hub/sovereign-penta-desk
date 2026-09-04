"""
Unit Tests and Verification Suite for Base L2 DEX Arbitrage Agent
"""

import unittest
import config
from strategies.dex_arb import DEXArbitrageStrategy
from risk_manager import RiskManager
from data_stream import BaseDataStream
from execution import ExecutionEngine

class TestArbitrageAgent(unittest.TestCase):
    def setUp(self):
        self.strategy = DEXArbitrageStrategy(working_capital=2950.0, min_profit_usd=6.0)
        self.risk_manager = RiskManager(starting_usdc=2950.0, offramp_trigger=3273.0)
        self.data_stream = BaseDataStream()
        self.execution = ExecutionEngine(mode="paper")

    def test_config_products(self):
        """Verify that top 10 target products are properly configured."""
        self.assertEqual(len(config.TARGET_PRODUCTS), 10)
        symbols = [p["symbol"] for p in config.TARGET_PRODUCTS]
        self.assertIn("WETH/USDC", symbols)
        self.assertIn("AERO/USDC", symbols)
        self.assertIn("cbBTC/USDC", symbols)

    def test_spread_evaluation_profitable(self):
        """Test spread calculation when gross spread > fee hurdle (1.20% spread)."""
        product = {"symbol": "WETH/USDC", "base": "WETH", "quote": "USDC", "min_spread": 0.80}
        # Uniswap = $3000, Aerodrome = $3036 -> Gross Spread = 1.20%
        result = self.strategy.evaluate_spread(product, price_uniswap=3000.0, price_aerodrome=3036.0)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["buy_venue"], "Uniswap v3")
        self.assertEqual(result["sell_venue"], "Aerodrome")
        self.assertAlmostEqual(result["gross_spread_pct"], 1.20, places=2)
        self.assertAlmostEqual(result["net_spread_pct"], 0.60, places=2)
        self.assertAlmostEqual(result["gross_profit_usd"], 35.40, places=2)
        self.assertAlmostEqual(result["fee_cost_usd"], 17.70, places=2)
        self.assertAlmostEqual(result["net_profit_usd"], 17.70, places=2)
        self.assertTrue(result["is_viable"])

    def test_spread_evaluation_unprofitable(self):
        """Test spread calculation when spread < 0.60% fee hurdle."""
        product = {"symbol": "WETH/USDC", "base": "WETH", "quote": "USDC", "min_spread": 0.80}
        # Uniswap = $3000, Aerodrome = $3009 -> Gross Spread = 0.30%
        result = self.strategy.evaluate_spread(product, price_uniswap=3000.0, price_aerodrome=3009.0)
        
        self.assertIsNotNone(result)
        self.assertFalse(result["is_viable"])

    def test_risk_manager_milestone_trigger(self):
        """Test off-ramp milestone alert when working balance reaches $3,273 USDC."""
        result_success = {
            "status": "SUCCESS",
            "net_profit_usd": 325.0,  # $2950 + $325 = $3275 (crosses $3273 threshold)
            "gas_used_eth": 0.00008,
        }
        status = self.risk_manager.record_trade_result(result_success)
        self.assertTrue(status["offramp_triggered"])
        self.assertGreater(status["harvest_amount"], 0)

    def test_execution_engine_paper(self):
        """Test paper execution result format."""
        opportunity = {
            "symbol": "WETH/USDC",
            "working_capital_usd": 2950.0,
            "net_profit_usd": 17.70,
            "buy_venue": "Uniswap v3",
            "sell_venue": "Aerodrome",
            "gross_spread_pct": 1.20,
        }
        res = self.execution.execute_arbitrage(opportunity)
        self.assertIn(res["status"], ["SUCCESS", "REVERTED"])
        self.assertEqual(res["mode"], "PAPER")

    def test_circuit_breaker_resets_after_tripping(self):
        """
        After the circuit breaker trips on 3 consecutive reverts, the streak
        counter must reset to 0 so a single subsequent revert doesn't
        immediately re-trip it (regression test for the reset-on-trip fix).
        """
        reverted = {"status": "REVERTED", "gas_used_eth": 0.00002}

        status = None
        for _ in range(3):
            status = self.risk_manager.record_trade_result(reverted)
        self.assertTrue(status["circuit_breaker"])
        self.assertEqual(self.risk_manager.consecutive_reverts, 0)

        # One more revert right after the trip should NOT immediately re-trip.
        status = self.risk_manager.record_trade_result(reverted)
        self.assertFalse(status["circuit_breaker"])

    def test_gas_reserve_uses_configured_threshold(self):
        """check_gas_reserve() should honor CAPITAL_CONFIG['MIN_GAS_RESERVE_ETH']."""
        rm = RiskManager(gas_reserve_eth=0.0025)
        self.assertEqual(rm.min_gas_reserve_eth, config.CAPITAL_CONFIG["MIN_GAS_RESERVE_ETH"])
        self.assertFalse(rm.check_gas_reserve())

    def test_live_mode_without_credentials_raises(self):
        """LIVE mode must fail fast with a clear error if dontshare.py is missing,
        instead of silently proceeding as if execution will actually happen."""
        with self.assertRaises(RuntimeError):
            ExecutionEngine(mode="live")

if __name__ == "__main__":
    unittest.main()
