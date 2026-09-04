"""
===============================================================================
STRATEGY TEMPLATE: Quantitative Signal Generator
===============================================================================
Location: DEV/strategies/strategy_template.py

DESCRIPTION OF THIS MODULE:
---------------------------
A Strategy module is the "brain" of a trading system. Its sole responsibility is 
to evaluate market data and return a decision on whether to trade.

Key Design Principles:
1. PURE LOGIC: It contains no network API code, exchange connections, or wallet keys.
2. DETERMINISTIC: Given the exact same price inputs, it always yields the exact same outputs.
3. STANDARDIZED OUTPUT: Returns a dictionary with an explicit "action" ("BUY", "SELL", or "HOLD")
   so any Agent can easily consume the signal.

WORKFLOW OVERVIEW:
------------------
  [ Market Data / Prices ] 
           │
           ▼
  [ generate_signal() ]
           │
           ├── Step 1: Input Validation (Guard Clauses)
           ├── Step 2: Mathematical Spread & PnL Calculations
           ├── Step 3: Rule Evaluation & Hurdle Check
           └── Step 4: Decision Output Formulation
           │
           ▼
  { "action": "BUY", "net_profit_usd": 17.70, "is_viable": True }
===============================================================================
"""

from typing import Dict, Optional


class BaseStrategyTemplate:
    """
    Base Strategy Class Template for Quantitative Signal Generation.

    This class encapsulates trading rules, thresholds, and financial formulas.
    You can customize this class for different strategies (e.g. RSI, Moving Averages, Arbitrage).

    CLASS ATTRIBUTES & PARAMETERS:
    ------------------------------
    min_spread_pct (float): 
        The minimum percentage gap between sell and buy prices required to consider a trade.
        Default is 0.80% (which comfortably exceeds the 0.60% protocol fee hurdle).

    min_profit_usd (float): 
        The minimum net profit requirement in USD after deducting exchange/protocol fees.
        Default is $6.00 USD to prevent taking micro-trades with negligible yield.

    fee_pct (float): 
        The combined percentage fee incurred across transaction legs (e.g. 0.30% * 2 legs = 0.60%).
    """

    def __init__(
        self,
        min_spread_pct: float = 0.80,
        min_profit_usd: float = 6.00,
        fee_pct: float = 0.60,
    ):
        """
        Initializes the strategy with custom or default risk/profit thresholds.
        """
        self.min_spread_pct = min_spread_pct
        self.min_profit_usd = min_profit_usd
        self.fee_pct = fee_pct

    def generate_signal(
        self,
        symbol: str,
        buy_price: float,
        sell_price: float,
        capital_usd: float = 2950.0,
    ) -> Dict:
        """
        Evaluates input price quotes and computes net profitability metrics.

        METHOD PARAMETERS:
        ------------------
        symbol (str): 
            The ticker identifier for the asset pair (e.g., "WETH/USDC").

        buy_price (float): 
            The entry or buy price quoted on the cheaper venue/exchange.

        sell_price (float): 
            The exit or sell price quoted on the more expensive venue/exchange.

        capital_usd (float): 
            The amount of working capital deployed into the trade (default: $2,950 USDC).

        RETURNS:
        --------
        Dict: A comprehensive dictionary detailing the trade decision, including:
            - "action": "BUY" if profitable & above hurdles; "HOLD" otherwise.
            - "gross_spread_pct": Percentage difference between sell and buy price.
            - "net_spread_pct": Spread remaining after deducting protocol fees.
            - "gross_profit_usd": Total dollar gain before fees.
            - "fee_cost_usd": Total dollar cost of exchange/protocol fees.
            - "net_profit_usd": Final net profit in USD.
            - "is_viable": Boolean flag indicating if trade satisfies all hurdles.
        """

        # =========================================================================
        # STEP 1: INPUT VALIDATION (Guard Clause)
        # -------------------------------------------------------------------------
        # Protects against invalid, missing, or non-positive price feeds.
        # If market data is corrupted, immediately return a safe "HOLD" decision.
        # =========================================================================
        if buy_price <= 0 or sell_price <= 0:
            return {
                "symbol": symbol,
                "action": "HOLD",
                "reason": "Invalid or missing price data (price <= 0)",
                "is_viable": False,
            }

        # =========================================================================
        # STEP 2: MATHEMATICAL CALCULATIONS
        # -------------------------------------------------------------------------
        # Formula 1: Gross Spread % = ((Sell Price - Buy Price) / Buy Price) * 100
        # Formula 2: Net Spread %   = Gross Spread % - Protocol Fee %
        # Formula 3: Net Profit USD = Capital * (Net Spread % / 100)
        # =========================================================================
        gross_spread_pct = ((sell_price - buy_price) / buy_price) * 100.0
        net_spread_pct = gross_spread_pct - self.fee_pct

        gross_profit_usd = capital_usd * (gross_spread_pct / 100.0)
        fee_cost_usd = capital_usd * (self.fee_pct / 100.0)
        net_profit_usd = gross_profit_usd - fee_cost_usd

        # =========================================================================
        # STEP 3: STRATEGY RULE EVALUATION (Hurdle Check)
        # -------------------------------------------------------------------------
        # A trade is considered "viable" ONLY IF BOTH criteria are met:
        # 1. Gross Spread % is greater than or equal to minimum required spread threshold.
        # 2. Net Profit in USD is greater than or equal to minimum required profit floor.
        # =========================================================================
        is_viable = (gross_spread_pct >= self.min_spread_pct) and (
            net_profit_usd >= self.min_profit_usd
        )

        # =========================================================================
        # STEP 4: DECISION OUTPUT FORMULATION
        # -------------------------------------------------------------------------
        # If viable -> Signal = "BUY"
        # If not viable -> Signal = "HOLD"
        # =========================================================================
        action = "BUY" if is_viable else "HOLD"

        return {
            "symbol": symbol,
            "action": action,                  # Signal: "BUY", "SELL", or "HOLD"
            "buy_price": round(buy_price, 6),   # Entry price
            "sell_price": round(sell_price, 6), # Exit price
            "gross_spread_pct": round(gross_spread_pct, 4),
            "net_spread_pct": round(net_spread_pct, 4),
            "gross_profit_usd": round(gross_profit_usd, 2),
            "fee_cost_usd": round(fee_cost_usd, 2),
            "net_profit_usd": round(net_profit_usd, 2),
            "capital_usd": capital_usd,
            "is_viable": is_viable,
        }


# =============================================================================
# EXECUTABLE SELF-TEST / DEMONSTRATION
# =============================================================================
# When this file is run directly (python strategy_template.py), this block runs
# a quick sanity check to demonstrate both profitable and unprofitable scenarios.
# =============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("   RUNNING STRATEGY TEMPLATE SELF-TEST DEMONSTRATION")
    print("=" * 80)

    # Initialize strategy with default risk settings
    strategy = BaseStrategyTemplate(min_spread_pct=0.80, min_profit_usd=6.00)

    # --- Scenario A: High Spread (Profitable Trade) ---
    # Buy @ $3,000.00, Sell @ $3,036.00 -> 1.20% Gross Spread
    result_a = strategy.generate_signal(
        symbol="WETH/USDC",
        buy_price=3000.00,
        sell_price=3036.00,
        capital_usd=2950.00,
    )
    print("\n[SCENARIO A: High Spread (1.20% Gross)]")
    print(f"  -> Signal Action: {result_a['action']}")
    print(f"  -> Trade Viable:  {result_a['is_viable']}")
    print(f"  -> Gross Spread:  {result_a['gross_spread_pct']}%")
    print(f"  -> Fee Deduction: ${result_a['fee_cost_usd']}")
    print(f"  -> Net Profit:    +${result_a['net_profit_usd']} USDC")

    # --- Scenario B: Low Spread (Unprofitable / Below Hurdle) ---
    # Buy @ $3,000.00, Sell @ $3,009.00 -> 0.30% Gross Spread
    result_b = strategy.generate_signal(
        symbol="WETH/USDC",
        buy_price=3000.00,
        sell_price=3009.00,
        capital_usd=2950.00,
    )
    print("\n[SCENARIO B: Low Spread (0.30% Gross)]")
    print(f"  -> Signal Action: {result_b['action']}")
    print(f"  -> Trade Viable:  {result_b['is_viable']}")
    print(f"  -> Gross Spread:  {result_b['gross_spread_pct']}%")
    print(f"  -> Net Profit:    ${result_b['net_profit_usd']} USDC (Below $6.00 hurdle)")
    print("=" * 80)
