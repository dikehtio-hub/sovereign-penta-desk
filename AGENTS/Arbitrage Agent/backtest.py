"""
Backtesting & Compounding Yield Simulator for Base L2 Arbitrage
Simulates strategy performance across 7-day, 35-day, and 70-day horizons.
"""

from termcolor import cprint
import config

def run_simulation(
    starting_capital: float = None,
    daily_avg_return_pct: float = 3.0,
    days: int = 70,
    offramp_trigger_pct: float = None,
):
    # Defaults are pulled from config.py so the simulator always matches the
    # live agent's current capital/milestone settings instead of drifting.
    cap = config.CAPITAL_CONFIG
    starting_capital = starting_capital if starting_capital is not None else cap["TOTAL_BANKROLL_USD"]
    gas_reserve_usd = cap["TOTAL_BANKROLL_USD"] - cap["WORKING_USDC"]
    if offramp_trigger_pct is None:
        offramp_trigger_pct = (cap["OFFRAMP_TRIGGER_USDC"] / cap["WORKING_USDC"] - 1) * 100.0

    cprint("=" * 80, "cyan")
    cprint(f"   BASE L2 DEX ARBITRAGE COMPOUNDING SIMULATOR (${starting_capital:,.2f} PRINCIPAL)", "white", "on_blue", attrs=["bold"])
    cprint("=" * 80, "cyan")

    working_usdc = starting_capital - gas_reserve_usd
    offramp_target = working_usdc * (1 + offramp_trigger_pct / 100.0)
    
    current_usdc = working_usdc
    total_harvested_fiat = 0.0
    
    milestone_days = [7, 35, 70]
    
    cprint(f"Initial Allocation: ${working_usdc:,.2f} USDC Working Capital | ${gas_reserve_usd:,.2f} ETH Gas Reserve", "yellow")
    cprint(f"Off-Ramp Target Trigger: ${offramp_target:,.2f} USDC (+${working_usdc * (offramp_trigger_pct/100):,.2f} Profit Harvest)\n", "yellow")
    
    for day in range(1, days + 1):
        # Apply daily return
        daily_profit = current_usdc * (daily_avg_return_pct / 100.0)
        current_usdc += daily_profit
        
        # Check off-ramp trigger
        if current_usdc >= offramp_target:
            harvest = current_usdc - working_usdc
            total_harvested_fiat += harvest
            current_usdc = working_usdc  # Reset to working capital
            
        if day in milestone_days:
            net_gain = (current_usdc - working_usdc) + total_harvested_fiat
            cprint(
                f"DAY {day:2d} | Current Hot Wallet: ${current_usdc:,.2f} USDC | Total Off-Ramped Profit: ${total_harvested_fiat:,.2f} USD | Net Gain: +${net_gain:,.2f}",
                "green" if net_gain > 0 else "white",
            )
            
    cprint("-" * 80, "cyan")
    cprint(f"SUMMARY AFTER {days} DAYS (@ {daily_avg_return_pct}% Avg Daily Return):", "white", "on_green", attrs=["bold"])
    cprint(f"Total Realized Profit Off-Ramped to Coinbase: ${total_harvested_fiat:,.2f} USD", "white", attrs=["bold"])
    cprint(f"Current Working Capital On Base: ${current_usdc:,.2f} USDC", "white", attrs=["bold"])
    cprint("=" * 80, "cyan")

if __name__ == "__main__":
    run_simulation(daily_avg_return_pct=3.0, days=70)
