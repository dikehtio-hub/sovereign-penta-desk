"""
DEX-to-DEX Quantitative Arbitrage Strategy Module for Base L2
"""

from typing import Dict, Optional
import config

class DEXArbitrageStrategy:
    def __init__(self, working_capital: float = None, min_profit_usd: float = None):
        self.working_capital = working_capital or config.CAPITAL_CONFIG["WORKING_USDC"]
        self.min_profit_usd = min_profit_usd or config.CAPITAL_CONFIG["MIN_PROFIT_USD"]
        self.cumulative_fee_pct = config.CAPITAL_CONFIG["CUMULATIVE_FEE_PCT"]

    def evaluate_spread(
        self,
        product: Dict,
        price_uniswap: float,
        price_aerodrome: float
    ) -> Optional[Dict]:
        """
        Evaluates a price spread between Uniswap v3 and Aerodrome.
        Determines the optimal swap direction (Leg 1 Buy -> Leg 2 Sell) and calculates net profitability.
        """
        if not price_uniswap or not price_aerodrome or price_uniswap <= 0 or price_aerodrome <= 0:
            return None

        # Determine buy and sell venues
        if price_aerodrome > price_uniswap:
            # Buy on Uniswap v3 (lower price), Sell on Aerodrome (higher price)
            buy_venue = "Uniswap v3"
            sell_venue = "Aerodrome"
            buy_price = price_uniswap
            sell_price = price_aerodrome
        elif price_uniswap > price_aerodrome:
            # Buy on Aerodrome (lower price), Sell on Uniswap v3 (higher price)
            buy_venue = "Aerodrome"
            sell_venue = "Uniswap v3"
            buy_price = price_aerodrome
            sell_price = price_uniswap
        else:
            return None

        # 1. Calculate Gross Spread
        gross_spread_pct = ((sell_price - buy_price) / buy_price) * 100.0

        # 2. Calculate Net Spread after 0.60% cumulative DEX swap fees
        net_spread_pct = gross_spread_pct - self.cumulative_fee_pct

        # 3. Calculate Nominal USD Returns
        gross_profit_usd = self.working_capital * (gross_spread_pct / 100.0)
        fee_cost_usd = self.working_capital * (self.cumulative_fee_pct / 100.0)
        net_profit_usd = gross_profit_usd - fee_cost_usd

        # 4. Hurdle Check
        required_min_spread = product.get("min_spread", config.CAPITAL_CONFIG["MIN_SPREAD_PCT"])
        is_viable = (gross_spread_pct >= required_min_spread) and (net_profit_usd >= self.min_profit_usd)

        return {
            "symbol": product["symbol"],
            "base_token": product["base"],
            "quote_token": product["quote"],
            "buy_venue": buy_venue,
            "sell_venue": sell_venue,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "gross_spread_pct": round(gross_spread_pct, 4),
            "net_spread_pct": round(net_spread_pct, 4),
            "gross_profit_usd": round(gross_profit_usd, 2),
            "fee_cost_usd": round(fee_cost_usd, 2),
            "net_profit_usd": round(net_profit_usd, 2),
            "working_capital_usd": self.working_capital,
            "is_viable": is_viable,
        }
