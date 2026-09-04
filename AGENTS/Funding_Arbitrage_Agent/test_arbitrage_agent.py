"""
Automated Unit and Integration Test Suite for Arbitrage Trading Agent.
Tests funding rate calculations, spread detection, delta-neutral sizing, execution, and risk sentinels.
"""

import asyncio
import unittest
import time

from config import Config
from market_data import MarketDataStreamer, MarketRate
from arbitrage_engine import ArbitrageEngine, StrategyType
from execution_manager import ExecutionManager
from risk_sentinel import RiskSentinel

class TestArbitrageAgent(unittest.TestCase):
    def setUp(self):
        self.config = Config(
            MIN_SINGLE_EXCHANGE_APR=20.0,
            MIN_CROSS_EXCHANGE_SPREAD_APR=12.0,
            DEFAULT_LEVERAGE=3,
            MAX_EQUITY_PERCENT=95.0
        )
        self.streamer = MarketDataStreamer(self.config.SYMBOLS, self.config.EXCHANGES)
        self.engine = ArbitrageEngine(self.config, self.streamer)
        self.execution_mgr = ExecutionManager(self.config, mode='dry-run')
        self.risk_sentinel = RiskSentinel(self.config, self.execution_mgr)

    def test_annualized_apr_calculation(self):
        """Verifies 8h funding rate to yearly APR % calculation."""
        raw_8h_rate = 0.0005  # 0.05% per 8h
        # Yearly APR = 0.0005 * 3 * 365 * 100 = 54.75%
        expected_apr = 0.0005 * 3 * 365 * 100
        
        self.streamer.update_rate('BTC', 'hyperliquid', 90000.0, raw_8h_rate)
        rate = self.streamer.get_rate('BTC', 'hyperliquid')
        
        self.assertIsNotNone(rate)
        self.assertAlmostEqual(rate.yearly_apr, expected_apr, places=2)
        self.assertEqual(rate.yearly_apr, 54.75)

    def test_single_exchange_cash_carry_detection(self):
        """Verifies detection of high-yield Cash & Carry opportunities."""
        # Hyperliquid BTC perp rate 0.0003 = 32.85% APR (> 20% threshold)
        self.streamer.update_rate('BTC', 'hyperliquid', 90000.0, 0.0003)
        
        opportunities = self.engine.scan_opportunities()
        self.assertGreaterEqual(len(opportunities), 1)
        
        top_opp = opportunities[0]
        self.assertEqual(top_opp.symbol, 'BTC')
        self.assertEqual(top_opp.strategy, StrategyType.SINGLE_EXCHANGE_CASH_CARRY)
        self.assertAlmostEqual(top_opp.net_spread_apr, 32.85, places=2)

    def test_cross_exchange_spread_detection(self):
        """Verifies detection of cross-exchange funding spreads."""
        # Binance SOL 0.0004 = 43.8% APR
        # Aster SOL 0.00005 = 5.475% APR
        # Spread = 38.325% APR (> 12% threshold)
        self.streamer.update_rate('SOL', 'binance', 200.0, 0.0004)
        self.streamer.update_rate('SOL', 'aster', 200.0, 0.00005)

        opportunities = self.engine.scan_opportunities()
        cross_opps = [o for o in opportunities if o.strategy == StrategyType.CROSS_EXCHANGE_FUNDING_ARB]
        
        self.assertGreaterEqual(len(cross_opps), 1)
        opp = cross_opps[0]
        self.assertEqual(opp.symbol, 'SOL')
        self.assertEqual(opp.short_exchange, 'Binance')
        self.assertEqual(opp.long_exchange, 'Aster')
        self.assertAlmostEqual(opp.net_spread_apr, 38.325, places=2)

    def test_delta_neutral_position_sizing(self):
        """Verifies position quantity calculation & symbol precision."""
        self.streamer.update_rate('BTC', 'binance', 100000.0, 0.0003)
        opportunities = self.engine.scan_opportunities()
        opp = opportunities[0]

        # Available equity = $10,000, 95% = $9,500 margin * 3x leverage = $28,500 notional
        # At $100,000/BTC -> 0.285 BTC
        plan = self.engine.calculate_position_size(opp, available_equity_usd=10000.0, leverage=3)
        
        self.assertEqual(plan.symbol, 'BTC')
        self.assertEqual(plan.unit_quantity, 0.285)
        self.assertEqual(plan.notional_value_usd, 28500.0)
        self.assertEqual(plan.margin_required_usd, 9500.0)

    def test_dry_run_trade_execution(self):
        """Tests dry-run paper trading execution and yield updates."""
        self.streamer.update_rate('ETH', 'hyperliquid', 3000.0, 0.0004)
        opps = self.engine.scan_opportunities()
        plan = self.engine.calculate_position_size(opps[0], available_equity_usd=10000.0)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        pos = loop.run_until_complete(
            self.execution_mgr.execute_arbitrage_play(opps[0], plan)
        )
        
        self.assertIsNotNone(pos)
        self.assertEqual(pos.symbol, 'ETH')
        self.assertEqual(pos.long_leg.status, 'FILLED')
        self.assertEqual(pos.short_leg.status, 'FILLED')
        self.assertIn(pos.position_id, self.execution_mgr.active_positions)

        # Test yield update over simulated time
        pos.entry_time = time.time() - 3600.0  # 1 hour ago
        self.execution_mgr.update_position_yields({'ETH': 3000.0})
        self.assertGreater(pos.accumulated_funding_usd, 0.0)
        
        loop.close()

    def test_risk_sentinel_funding_compression(self):
        """Tests risk sentinel triggering exit on funding compression."""
        self.streamer.update_rate('SOL', 'hyperliquid', 200.0, 0.0004)
        opps = self.engine.scan_opportunities()
        plan = self.engine.calculate_position_size(opps[0], available_equity_usd=10000.0)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pos = loop.run_until_complete(
            self.execution_mgr.execute_arbitrage_play(opps[0], plan)
        )

        # Funding spread drops to 1.0% APR (< 3.0% EXIT threshold)
        should_close, reason = self.risk_sentinel.check_position_risk(pos, current_spread_apr=1.0, current_mark_price=200.0)
        self.assertTrue(should_close)
        self.assertIn("Funding compression", reason)

        loop.close()

if __name__ == '__main__':
    unittest.main()
