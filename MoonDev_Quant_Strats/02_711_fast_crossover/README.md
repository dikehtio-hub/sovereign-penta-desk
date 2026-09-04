# 🌙 Strategy #02: 7/11 EMA-SMA Fast Crossover System Pro (`711_crossover`)

## 📌 Overview
An ultra-responsive fast moving average crossover system combining a 7-period Exponential Moving Average (EMA) and an 11-period Simple Moving Average (SMA) with 5 quantitative institutional confirmation filters.

---

## 🛠️ Enhancements & Architecture
1. **Macro Trend Filter**: HTF 200 EMA + ADX(14) > 20 strength threshold.
2. **Dynamic Volatility Stops**: 2-bar swing extremity buffered by 0.5x ATR with hard tick/point risk caps (e.g. 35 ticks on /NQ).
3. **Multi-Stage Exits**: Scale out 50% at 1.5R initial risk, migrate stop to Breakeven + buffer, and trail runner on 11-SMA or 1.5x ATR trailing band.
4. **Volume & Momentum Gates**: Volume > 1.2x SMA20 and RSI within the active momentum corridor (50–70 for Longs, 30–50 for Shorts).
5. **Time-of-Day Killzones**: US Equities (09:30–11:30 & 13:30–15:30 EST) and Crypto London/NY active sessions.
6. **Automation**: Standardized JSON webhook payloads for automated bot execution (`{{strategy.order.alert_message}}`).

---

## 🚀 Files
- `strategy_02_711_crossover_pro.pine`: Production TradingView Pine Script v5 Strategy with HUD dashboard.
- `backtest_711_crossover.py`: Vectorized backtest & parameter grid optimizer engine.
- `research_notes_711.md`: Quantitative breakdown and asset specifications.
