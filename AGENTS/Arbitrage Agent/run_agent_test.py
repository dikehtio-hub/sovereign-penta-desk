"""
Runner Script to Test 5 Cycles of ArbitrageAgent
"""

import time
import config
from data_stream import BaseDataStream
from execution import ExecutionEngine
from risk_manager import RiskManager
from strategies.dex_arb import DEXArbitrageStrategy
from agent import ArbitrageAgent

if __name__ == "__main__":
    agent = ArbitrageAgent(mode="paper", scan_interval=0.5)
    print("Running 5 test iterations of ArbitrageAgent...")
    
    for i in range(5):
        print(f"\n--- SCAN ITERATION {i+1} ---")
        viable = []
        for product in config.TARGET_PRODUCTS:
            quote = agent.data_stream.fetch_live_quotes(product)
            evaluation = agent.strategy.evaluate_spread(
                product=product,
                price_uniswap=quote["uniswap_v3_price"],
                price_aerodrome=quote["aerodrome_price"]
            )
            if evaluation and evaluation["is_viable"]:
                viable.append(evaluation)
                
        if viable:
            viable.sort(key=lambda x: x["net_profit_usd"], reverse=True)
            best = viable[0]
            print(f"[SIGNAL DETECTED] {best['symbol']} | Gross: {best['gross_spread_pct']}% | Net: +${best['net_profit_usd']:.2f} USDC")
            res = agent.execution_engine.execute_arbitrage(best)
            agent.risk_manager.record_trade_result(res)
            print(f"  -> Execution: {res['status']} | Hot Wallet: ${agent.risk_manager.current_usdc:.2f} USDC")
        else:
            print("No viable spreads above 0.80% hurdle in this cycle.")
            
    print("\n" + "="*60)
    agent.print_summary()
