"""
Simulated Market Data Streamer for Base L2 DEX Pools (Paper-Trading Feed)

NOTE: This currently generates synthetic prices around fixed benchmarks — it
does NOT call the Base RPC or query on-chain Uniswap v3 / Aerodrome quoters.
`self.rpc_url` is stored for the future real integration but unused today.
See README "Going Live" for what's needed to replace this with real quotes.
"""

import random
import time
import config

class BaseDataStream:
    def __init__(self, rpc_url: str = None):
        self.rpc_url = rpc_url or config.BASE_RPC_URL

    def fetch_live_quotes(self, product: dict) -> dict:
        """
        Returns simulated price quotes for a target product across Uniswap v3
        and Aerodrome, generated from fixed benchmark mid-prices plus random
        per-venue variance (see `base_prices` / `spread_bias` below).
        """
        symbol = product["symbol"]
        
        # Benchmark mid-prices for top 10 Base pairs
        base_prices = {
            "WETH/USDC": 3000.00,
            "AERO/USDC": 1.25,
            "cbBTC/USDC": 95000.00,
            "wstETH/WETH": 1.15,
            "VIRTUAL/WETH": 0.00045,
            "BRETT/WETH": 0.000035,
            "DEGEN/WETH": 0.0000042,
            "EURC/USDC": 1.085,
            "WELL/WETH": 0.000018,
            "DAI/USDC": 1.00,
        }

        mid_price = base_prices.get(symbol, 100.0)

        # Simulate micro-variance across venues (representing pool imbalance)
        # Randomly trigger live spread opportunities (0.2% - 1.8% variance)
        spread_bias = random.choice([0.003, -0.004, 0.0085, -0.0095, 0.014, -0.012, 0.002])
        
        price_uniswap = round(mid_price * (1 + random.uniform(-0.002, 0.002)), 6)
        price_aerodrome = round(mid_price * (1 + spread_bias), 6)

        return {
            "symbol": symbol,
            "timestamp": time.time(),
            "uniswap_v3_price": price_uniswap,
            "aerodrome_price": price_aerodrome,
        }
