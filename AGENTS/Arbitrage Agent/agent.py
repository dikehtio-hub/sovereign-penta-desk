"""
Autonomous Quantitative Arbitrage Trading Agent for Base L2
Executes the RBI Workflow (Research, Backtest/Pre-Flight, Implement/Execute)
"""

import argparse
import os
import sys
import time
from datetime import datetime
from termcolor import cprint

import config
from data_stream import BaseDataStream
from execution import ExecutionEngine
from risk_manager import RiskManager
from strategies.dex_arb import DEXArbitrageStrategy


class ArbitrageAgent:
    def __init__(self, mode: str = "paper", scan_interval: float = 2.0):
        self.mode = mode.lower()
        self.scan_interval = scan_interval
        
        cprint("=" * 80, "cyan")
        cprint(
            f"   AUTONOMOUS BASE L2 DEX ARBITRAGE AGENT (MODE: {self.mode.upper()})",
            "white",
            "on_blue",
            attrs=["bold"],
        )
        cprint("=" * 80, "cyan")

        self.strategy = DEXArbitrageStrategy()
        self.data_stream = BaseDataStream()
        self.execution_engine = ExecutionEngine(mode=self.mode)
        self.risk_manager = RiskManager()

        cprint(f"[CONFIG] Base RPC: {config.BASE_RPC_URL}", "yellow")
        cprint(f"[CONFIG] Working Capital: ${config.CAPITAL_CONFIG['WORKING_USDC']:,.2f} USDC", "yellow")
        gas_reserve_usd = config.CAPITAL_CONFIG["TOTAL_BANKROLL_USD"] - config.CAPITAL_CONFIG["WORKING_USDC"]
        cprint(f"[CONFIG] Gas Reserve: {config.CAPITAL_CONFIG['GAS_RESERVE_ETH']} ETH (~${gas_reserve_usd:,.2f} USD)", "yellow")
        cprint(f"[CONFIG] Min Spread Hurdle: {config.CAPITAL_CONFIG['MIN_SPREAD_PCT']}% | Min Net Profit: ${config.CAPITAL_CONFIG['MIN_PROFIT_USD']:.2f}", "yellow")
        cprint(f"[CONFIG] Off-Ramp Trigger: ${config.CAPITAL_CONFIG['OFFRAMP_TRIGGER_USDC']:,.2f} USDC\n", "yellow")

    def run(self):
        """
        Main Autonomous Trading Loop executing the RBI Cycle.
        """
        cprint("Starting real-time multi-pair DEX quote scanner across Base L2...", "green")
        scan_cycle = 0

        try:
            while True:
                scan_cycle += 1
                now_str = datetime.now().strftime("%H:%M:%S")
                
                # Check Risk Manager Gas & Circuit Breaker State
                if not self.risk_manager.check_gas_reserve():
                    cprint(f"[{now_str}] CRITICAL: Gas reserve critically low (<{self.risk_manager.min_gas_reserve_eth} ETH). Agent Paused.", "white", "on_red")
                    time.sleep(10)
                    continue

                # --- STEP 1: RESEARCH & SCAN (Multi-Pair Scanner) ---
                viable_opportunities = []

                for product in config.TARGET_PRODUCTS:
                    quote = self.data_stream.fetch_live_quotes(product)
                    
                    # --- STEP 2: BACKTEST & PRE-FLIGHT (Evaluate Spread vs Fee Hurdle) ---
                    evaluation = self.strategy.evaluate_spread(
                        product=product,
                        price_uniswap=quote["uniswap_v3_price"],
                        price_aerodrome=quote["aerodrome_price"],
                    )

                    if evaluation and evaluation["is_viable"]:
                        viable_opportunities.append(evaluation)

                # --- STEP 3: IMPLEMENT & EXECUTE (Dispatch Best Trade Signal) ---
                if viable_opportunities:
                    # Sort by highest net profit
                    viable_opportunities.sort(key=lambda x: x["net_profit_usd"], reverse=True)
                    best_op = viable_opportunities[0]

                    cprint(
                        f"\n[{now_str}] [SIGNAL DETECTED] {best_op['symbol']} | Gross Spread: {best_op['gross_spread_pct']}% | Net Profit: +${best_op['net_profit_usd']:.2f} USDC",
                        "black",
                        "on_green",
                        attrs=["bold"],
                    )
                    cprint(
                        f"  -> Action: Buy on {best_op['buy_venue']} (${best_op['buy_price']:.6f}) --> Sell on {best_op['sell_venue']} (${best_op['sell_price']:.6f})",
                        "green",
                    )

                    # Execute Trade (Paper or Live)
                    result = self.execution_engine.execute_arbitrage(best_op)

                    # --- STEP 4: RISK & MILESTONE GUARD ---
                    risk_status = self.risk_manager.record_trade_result(result)

                    if result["status"] == "SUCCESS":
                        cprint(
                            f"  -> Execution {result['status']}: Tx {result['tx_hash'][:14]}... | Total PnL: +${self.risk_manager.total_net_pnl:.2f} USDC | Hot Wallet Balance: ${self.risk_manager.current_usdc:.2f} USDC",
                            "cyan",
                        )
                    elif result["status"] == "REVERTED":
                        cprint(f"  -> Execution REVERTED: {result.get('error')}", "yellow")

                    if risk_status["circuit_breaker"]:
                        cprint("Circuit breaker triggered. Sleeping 30 seconds to allow market stability...", "red")
                        time.sleep(30)

                else:
                    # Print pulse status every 5 cycles
                    if scan_cycle % 5 == 0:
                        cprint(
                            f"[{now_str}] Scanning {len(config.TARGET_PRODUCTS)} Base L2 products... (Spreads within normal 0.1%-0.5% fee threshold)",
                            "white",
                        )

                time.sleep(self.scan_interval)

        except KeyboardInterrupt:
            cprint("\n[STOP] Agent safely stopped by user.", "white", "on_red")
            self.print_summary()

    def print_summary(self):
        cprint("\n" + "=" * 80, "cyan")
        cprint("   FINAL SESSION PERFORMANCE SUMMARY", "white", "on_blue", attrs=["bold"])
        cprint("=" * 80, "cyan")
        cprint(f"Total Trades Executed: {self.risk_manager.total_trades_executed}", "yellow")
        cprint(f"Total Net PnL Realized: +${self.risk_manager.total_net_pnl:.2f} USDC", "green", attrs=["bold"])
        cprint(f"Ending Hot Wallet Balance: ${self.risk_manager.current_usdc:.2f} USDC", "green", attrs=["bold"])
        cprint(f"Ending Gas Reserve: {self.risk_manager.gas_reserve_eth:.5f} ETH", "yellow")
        cprint("=" * 80, "cyan")


def main():
    parser = argparse.ArgumentParser(description="Autonomous Base L2 DEX Arbitrage Agent")
    parser.add_argument("--mode", type=str, default="paper", choices=["paper", "live"], help="Execution mode (paper or live)")
    parser.add_argument("--interval", type=float, default=2.0, help="Scan interval in seconds")
    args = parser.parse_args()

    try:
        agent = ArbitrageAgent(mode=args.mode, scan_interval=args.interval)
    except RuntimeError as e:
        cprint(f"\n[STARTUP ERROR] {e}", "white", "on_red")
        sys.exit(1)

    agent.run()


if __name__ == "__main__":
    main()
