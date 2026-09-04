"""
Arbitrage Engine for Autonomous Funding Arbitrage Trading Agent.
Evaluates market streams, identifies high-yield delta-neutral plays, and calculates precise position sizes.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict
from config import Config
from market_data import MarketDataStreamer, MarketRate

class StrategyType(Enum):
    """
    Supported Funding Arbitrage Strategy Types & Execution Specifications:
    
    1. SINGLE_EXCHANGE_CASH_CARRY
       -------------------------------------------------------------------------
       Description: Single-Exchange Spot Long / Perpetual Short Cash & Carry
       How Executed: 
         - Leg 1: Buys 1.0x Spot Asset (e.g. SOL on Binance Spot).
         - Leg 2: Sells 1.0x Perpetual Short (e.g. SOL-PERP on Binance Futures).
       Yield Mechanism:
         - Holds a zero-directional-risk (delta-neutral) hedge.
         - Accrues funding payments every 8 hours paid by perpetual long traders.
       Trigger Condition:
         - Perpetual Funding Rate Yearly APR >= Config.MIN_SINGLE_EXCHANGE_APR (e.g. >20% APR).

    2. CROSS_EXCHANGE_FUNDING_ARB
       -------------------------------------------------------------------------
       Description: Cross-Exchange Perpetual Long / Perpetual Short Spread Arbitrage
       How Executed:
         - Leg 1: Opens 1.0x Perpetual Long on Exchange A (Low or negative funding rate, e.g. Hyperliquid).
         - Leg 2: Opens 1.0x Perpetual Short on Exchange B (High positive funding rate, e.g. Aster/Binance).
       Yield Mechanism:
         - Net yield = (Exchange B Short APR) - (Exchange A Long APR).
         - Captures rate spread differential while price movements on Exchange A and B cancel out.
       Trigger Condition:
         - Spread APR difference (High APR - Low APR) >= Config.MIN_CROSS_EXCHANGE_SPREAD_APR (e.g. >12% APR diff).
    """
    SINGLE_EXCHANGE_CASH_CARRY = "Single-Exchange Cash & Carry (Spot Long / Perp Short)"
    CROSS_EXCHANGE_FUNDING_ARB = "Cross-Exchange Funding Arbitrage (Perp Long / Perp Short)"

@dataclass
class ArbitrageOpportunity:
    symbol: str
    strategy: StrategyType
    long_exchange: str
    short_exchange: str
    long_apr: float
    short_apr: float
    net_spread_apr: float
    mark_price: float
    estimated_daily_yield_pct: float
    is_valid: bool = True
    reason: str = ""

@dataclass
class PositionSizePlan:
    symbol: str
    unit_quantity: float
    notional_value_usd: float
    margin_required_usd: float
    leverage: int
    long_exchange: str
    short_exchange: str

class ArbitrageEngine:
    def __init__(self, config: Config, data_streamer: MarketDataStreamer):
        self.config = config
        self.streamer = data_streamer

    def scan_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Scans all market streams for active funding rate arbitrage opportunities.
        Returns a sorted list of opportunities ordered by highest net APR yield.
        """
        opportunities: List[ArbitrageOpportunity] = []
        rates_by_symbol = self.streamer.get_all_rates()

        enabled_strats = [s.lower() for s in self.config.ENABLED_STRATEGIES]
        allow_all = 'all' in enabled_strats

        run_cash_carry = allow_all or 'cash-carry' in enabled_strats or 'cash_carry' in enabled_strats
        run_cross_funding = allow_all or 'cross-funding' in enabled_strats or 'cross_funding' in enabled_strats

        for symbol, exchange_rates in rates_by_symbol.items():
            if len(exchange_rates) < 1:
                continue

            # 1. Evaluate Single-Exchange Cash & Carry (High Positive Perp Funding)
            if run_cash_carry:
                for ex_name, rate in exchange_rates.items():
                    if rate.yearly_apr >= self.config.MIN_SINGLE_EXCHANGE_APR:
                        daily_yield = (rate.yearly_apr / 365.0)
                        opportunities.append(ArbitrageOpportunity(
                            symbol=symbol,
                            strategy=StrategyType.SINGLE_EXCHANGE_CASH_CARRY,
                            long_exchange=f"{ex_name.title()} (Spot)",
                            short_exchange=f"{ex_name.title()} (Perp)",
                            long_apr=0.0,
                            short_apr=rate.yearly_apr,
                            net_spread_apr=rate.yearly_apr,
                            mark_price=rate.mark_price,
                            estimated_daily_yield_pct=daily_yield,
                            reason=f"High perp funding yield ({rate.yearly_apr:.2f}% APR)"
                        ))

            # 2. Evaluate Cross-Exchange Funding Arbitrage (Rate Spreads)
            if run_cross_funding and len(exchange_rates) >= 2:
                sorted_rates = sorted(exchange_rates.items(), key=lambda x: x[1].yearly_apr, reverse=True)
                high_ex, high_rate = sorted_rates[0]
                low_ex, low_rate = sorted_rates[-1]

                spread_apr = high_rate.yearly_apr - low_rate.yearly_apr
                if spread_apr >= self.config.MIN_CROSS_EXCHANGE_SPREAD_APR:
                    daily_yield = (spread_apr / 365.0)
                    opportunities.append(ArbitrageOpportunity(
                        symbol=symbol,
                        strategy=StrategyType.CROSS_EXCHANGE_FUNDING_ARB,
                        long_exchange=low_ex.title(),
                        short_exchange=high_ex.title(),
                        long_apr=low_rate.yearly_apr,
                        short_apr=high_rate.yearly_apr,
                        net_spread_apr=spread_apr,
                        mark_price=(high_rate.mark_price + low_rate.mark_price) / 2.0,
                        estimated_daily_yield_pct=daily_yield,
                        reason=f"Cross-exchange funding spread ({spread_apr:.2f}% APR diff)"
                    ))

        # Sort opportunities by net APR yield descending
        opportunities.sort(key=lambda opp: opp.net_spread_apr, reverse=True)
        return opportunities

    def calculate_position_size(
        self,
        opp: ArbitrageOpportunity,
        available_equity_usd: float,
        leverage: Optional[int] = None
    ) -> PositionSizePlan:
        """
        Calculates exact delta-neutral position quantity matching precision rules.
        """
        leverage = leverage or self.config.DEFAULT_LEVERAGE
        leverage = min(leverage, self.config.MAX_LEVERAGE)

        # Allocate margin according to config cap
        usable_margin = available_equity_usd * (self.config.MAX_EQUITY_PERCENT / 100.0)
        target_notional = usable_margin * leverage

        if opp.mark_price <= 0:
            raw_quantity = 0.0
        else:
            raw_quantity = target_notional / opp.mark_price

        # Symbol precision formatting rules matching the 10 target products
        symbol_upper = opp.symbol.upper()
        if 'BTC' in symbol_upper:
            quantity = round(raw_quantity, 3)
        elif 'ETH' in symbol_upper or 'WSTETH' in symbol_upper:
            quantity = round(raw_quantity, 2)
        elif 'AERO' in symbol_upper or 'VIRTUAL' in symbol_upper or 'EURC' in symbol_upper or 'WELL' in symbol_upper:
            quantity = round(raw_quantity, 2)
        elif 'BRETT' in symbol_upper or 'DEGEN' in symbol_upper:
            quantity = round(raw_quantity, 0)
        else:
            quantity = round(raw_quantity, 1)

        actual_notional = round(quantity * opp.mark_price, 2)
        actual_margin = round(actual_notional / leverage if leverage > 0 else actual_notional, 2)

        return PositionSizePlan(
            symbol=opp.symbol,
            unit_quantity=quantity,
            notional_value_usd=actual_notional,
            margin_required_usd=actual_margin,
            leverage=leverage,
            long_exchange=opp.long_exchange,
            short_exchange=opp.short_exchange
        )
