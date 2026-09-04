"""
Main CLI Dashboard & Orchestrator for Autonomous Funding Arbitrage Trading Agent.
Executes live real-time terminal display, opportunity scanning, paper trading, and automated risk protection.
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from termcolor import colored, cprint

from config import Config
from market_data import MarketDataStreamer
from arbitrage_engine import ArbitrageEngine
from execution_manager import ExecutionManager
from risk_sentinel import RiskSentinel

class ArbitrageAgent:
    """
    Main Autonomous Agent orchestrating market data streams, arbitrage strategy calculations,
    trade execution, and live terminal dashboard updates.
    """
    def __init__(self, mode: str = 'dry-run', auto_trade: bool = False, leverage: int = 3, strategy: str = 'all'):
        self.config = Config(
            DEFAULT_LEVERAGE=leverage,
            ENABLED_STRATEGIES=['all'] if strategy == 'all' else [strategy]
        )
        self.mode = mode.lower()
        self.auto_trade = auto_trade
        
        self.streamer = MarketDataStreamer(self.config.SYMBOLS, self.config.EXCHANGES)
        self.engine = ArbitrageEngine(self.config, self.streamer)
        self.execution_mgr = ExecutionManager(self.config, mode=self.mode)
        self.risk_sentinel = RiskSentinel(self.config, self.execution_mgr)
        self._running = False

    def clear_terminal(self):
        """Clears terminal screen cleanly across OS platforms."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def render_dashboard(self, opportunities, active_positions):
        """Renders rich terminal UI dashboard with color-coded rate matrix & position logs."""
        self.clear_terminal()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        mode_str = colored(" [ DRY-RUN PAPER TRADING MODE ] ", "white", "on_blue", attrs=["bold"]) if self.mode == 'dry-run' \
            else colored(" 🚨 [ LIVE TRADING MODE ] 🚨 ", "white", "on_red", attrs=["bold"])

        print("=================================================================================")
        print(f" [ARB] AUTONOMOUS FUNDING ARBITRAGE AGENT | {now_str} | {mode_str}")
        print("=================================================================================")
        
        balance = self.execution_mgr.get_account_balance()
        print(f" [$] Account Equity: ${balance:,.2f} USD | Target Leverage: {self.config.DEFAULT_LEVERAGE}x | Max Margin: {self.config.MAX_EQUITY_PERCENT}%")
        print("---------------------------------------------------------------------------------")
        
        # 1. Real-Time Funding Rate Matrix
        print(colored("\n [*] LIVE FUNDING RATES & MARK PRICES (ANNUALIZED APR)", "cyan", attrs=["bold"]))
        rates = self.streamer.get_all_rates()
        
        print(f" {'SYMBOL':<8} | {'EXCHANGE':<12} | {'MARK PRICE':<12} | {'8H RATE':<10} | {'ANNUAL APR':<12}")
        print(" " + "-"*65)
        
        for symbol in self.config.SYMBOLS:
            ex_data = rates.get(symbol, {})
            if not ex_data:
                print(f" {symbol:<8} | waiting for data streams...")
                continue
                
            for ex_name, rate in ex_data.items():
                apr = rate.yearly_apr
                # Color coding based on yield rate
                if apr > 40.0:
                    apr_str = colored(f"{apr:>10.2f}%", "white", "on_red")
                elif apr > 20.0:
                    apr_str = colored(f"{apr:>10.2f}%", "black", "on_yellow")
                elif apr > 10.0:
                    apr_str = colored(f"{apr:>10.2f}%", "black", "on_cyan")
                elif apr < -5.0:
                    apr_str = colored(f"{apr:>10.2f}%", "white", "on_green")
                else:
                    apr_str = colored(f"{apr:>10.2f}%", "white")
                    
                sim_tag = " (sim)" if rate.is_simulated else ""
                print(f" {symbol:<8} | {ex_name.title() + sim_tag:<12} | ${rate.mark_price:<11,.2f} | {rate.funding_rate_8h*100:>8.4f}% | {apr_str}")

        # 2. Detected Arbitrage Opportunities
        print(colored("\n [+] DETECTED HIGH-YIELD ARBITRAGE OPPORTUNITIES", "yellow", attrs=["bold"]))
        if not opportunities:
            print("  No active arbitrage opportunities matching threshold criteria right now.")
        else:
            print(f" {'SYMBOL':<8} | {'LONG SIDE':<18} | {'SHORT SIDE':<18} | {'SPREAD APR':<12} | {'EST. DAILY %'}")
            print(" " + "-"*75)
            for opp in opportunities[:4]:  # Top 4 plays
                print(f" {opp.symbol:<8} | {opp.long_exchange:<18} | {opp.short_exchange:<18} | "
                      f"{colored(f'+{opp.net_spread_apr:.2f}%', 'green', attrs=['bold']):<12} | +{opp.estimated_daily_yield_pct:.3f}%/day")

        # 3. Active Arbitrage Positions
        print(colored("\n [POS] ACTIVE DELTA-NEUTRAL ARBITRAGE POSITIONS", "green", attrs=["bold"]))
        open_positions = [p for p in active_positions.values() if not p.is_closed]
        if not open_positions:
            print("  No active open positions.")
        else:
            print(f" {'POS ID':<20} | {'SYMBOL':<8} | {'QTY':<8} | {'ENTRY PX':<10} | {'SPREAD APR':<11} | {'YIELD ACCRUED'}")
            print(" " + "-"*75)
            for pos in open_positions:
                yield_str = colored(f"+${pos.accumulated_funding_usd:.4f}", "green", attrs=["bold"])
                print(f" {pos.position_id:<20} | {pos.symbol:<8} | {pos.quantity:<8} | ${pos.entry_price:<9.2f} | "
                      f"+{pos.net_spread_apr:.2f}%     | {yield_str}")

        print("\n=================================================================================")
        print(" Press Ctrl+C to safely exit agent.")

    async def run(self):
        """Main asynchronous agent loop."""
        self._running = True
        cprint("[+] Starting Autonomous Funding Arbitrage Agent Data Streams...", "cyan")
        await self.streamer.start()
        await asyncio.sleep(2)  # Allow streams to warm up

        try:
            while self._running:
                # 1. Scan for opportunities
                opportunities = self.engine.scan_opportunities()

                # 2. Update position yields & mark prices
                current_rates = self.streamer.get_all_rates()
                mark_prices = {}
                for sym, ex_map in current_rates.items():
                    if ex_map:
                        mark_prices[sym] = list(ex_map.values())[0].mark_price

                self.execution_mgr.update_position_yields(mark_prices)

                # 3. Audit active position risks
                await self.risk_sentinel.audit_all_positions(current_rates)

                # 4. Auto-trade if enabled and valid opportunity exists
                if self.auto_trade and opportunities:
                    top_opp = opportunities[0]
                    # Check if we already have a position in this symbol
                    has_pos = any(p.symbol == top_opp.symbol and not p.is_closed for p in self.execution_mgr.active_positions.values())
                    if not has_pos:
                        plan = self.engine.calculate_position_size(top_opp, self.execution_mgr.get_account_balance())
                        if plan.unit_quantity > 0:
                            await self.execution_mgr.execute_arbitrage_play(top_opp, plan)

                # 5. Render live display
                self.render_dashboard(opportunities, self.execution_mgr.active_positions)
                await asyncio.sleep(self.config.MONITORING_INTERVAL_SEC)

        except asyncio.CancelledError:
            pass
        finally:
            cprint("\n[*] Shutting down Agent streams safely...", "yellow")
            await self.streamer.stop()

def main():
    parser = argparse.ArgumentParser(description="Autonomous Funding Arbitrage Trading Agent")
    parser.add_argument('--mode', type=str, default='dry-run', choices=['dry-run', 'live'], help='Trading mode: dry-run (paper) or live')
    parser.add_argument('--auto-trade', action='store_true', help='Automatically execute top detected arbitrage opportunities')
    parser.add_argument('--leverage', type=int, default=3, help='Default leverage cap')
    parser.add_argument('--strategy', type=str, default='all', choices=['all', 'cash-carry', 'cross-funding'], 
                        help='Strategy to run: cash-carry (Spot Long / Perp Short), cross-funding (Perp-Perp Arb), or all')
    
    args = parser.parse_args()
    
    agent = ArbitrageAgent(mode=args.mode, auto_trade=args.auto_trade, leverage=args.leverage, strategy=args.strategy)
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\nAgent stopped by user.")
        sys.exit(0)

if __name__ == '__main__':
    main()
