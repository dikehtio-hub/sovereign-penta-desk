# HL_Monarch Execution & Trading Bot Engine (Reserved)

This directory is reserved for **automated trading bots, order execution engines, and risk management systems** on Hyperliquid.

---

## 🔒 Architecture Blueprint (When Ready to Enable)

### Planned Modules:
1. **`wallet_manager.py`**:
   - Manages secure connection to Hyperliquid via EIP-712 transaction signing.
   - Recommended: Use a dedicated **Hyperliquid API Agent Wallet** (delegated key with trading-only permissions, zero withdrawal risk).
2. **`order_executor.py`**:
   - Native order placement: Limit Orders, Market (IOC) Fills, Stop-Loss / Take-Profit brackets, Trailing Stops, Order Cancels.
3. **`risk_manager.py`**:
   - Max drawdown guard, position sizing limits, margin utilization caps, and automated circuit breakers.
4. **`strategies/`**:
   - `liquidation_fade_bot.py`: Fades extreme liquidation cascade exhaustion points.
   - `funding_arbitrage_bot.py`: Captures funding rate spreads between TradFi and Crypto perps.
   - `orderbook_scalper.py`: High-frequency spread quoting based on order book depth imbalance.

---

*Note: No live trading logic is active until you explicitly configure your strategy parameters and agent credentials.*
