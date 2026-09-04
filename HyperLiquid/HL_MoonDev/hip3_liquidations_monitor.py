"""
MoonDev HIP3 TradFi Liquidation Monitor (Reference Benchmark).
Uses MoonDev API key to query https://api.moondev.com/api/hip3/liquidations.
"""
import time
import os
from moondev_client import MoonDevClient

def run_moondev_hip3_monitor():
    api_key = os.getenv("MOONDEV_API_KEY", "YOUR_API_KEY")
    client = MoonDevClient(api_key=api_key)
    
    print("=" * 70)
    print("  MOONDEV REFERENCE BENCHMARK: HIP3 TRADFI LIQUIDATION MONITOR")
    print("=" * 70)

    try:
        prices = client.get_hip3_prices()
        print(f"Loaded {len(prices.get('prices', {}))} TradFi prices from MoonDev API.")
        
        liqs = client.get_hip3_liquidations()
        print(f"Recent TradFi Liquidations ({len(liqs)} events):")
        for liq in liqs[:10]:
            print(f"  {liq.get('coin')} | {liq.get('side')} | ${liq.get('px')} | sz: {liq.get('sz')} | ${liq.get('notional'):,.2f}")

    except Exception as e:
        print(f"MoonDev API error (API Key may be missing/invalid): {e}")

if __name__ == "__main__":
    run_moondev_hip3_monitor()
