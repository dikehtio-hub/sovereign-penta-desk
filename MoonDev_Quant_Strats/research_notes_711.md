# 🌙 Strategy #2: 7/11 EMA-SMA Fast Crossover System Pro

## Executive Quantitative Summary
The **7/11 EMA-SMA Fast Crossover System** is an ultra-responsive trend-momentum engine originally designed to capture rapid momentum acceleration on intraday timeframes (1m to 15m). By pairing a fast **7-period Exponential Moving Average (EMA)** with an **11-period Simple Moving Average (SMA)**, the system creates a tight dynamic ribbon with minimal phase lag.

However, historical analysis across Moon Dev Discord archives revealed severe vulnerabilities in sideways, choppy market regimes (raw win rate sitting at **30%–37%**, high churn, and deep drawdowns caused by fixed 1:2 risk-reward stops and single-bar wick stop-outs).

This quantitative overhaul introduces **5 core institutional enhancements** that filter out chop, dynamicize stop placement, scale out profits at high-probability milestones, and trail runners across macro trend expansions.

---

## 1. Base Strategy Mechanics & Historical Bottlenecks

### Base Rules:
- **Fast Moving Average**: 7-period EMA (\(\alpha = \frac{2}{7 + 1} = 0.25\))
- **Slow Moving Average**: 11-period SMA (\(\frac{1}{11} \sum_{i=0}^{10} P_{t-i}\))
- **Bullish Entry**: 7 EMA crosses above 11 SMA + Bullish candle confirmation (\(Close_t > Open_t\)).
- **Bearish Entry**: 7 EMA crosses below 11 SMA + Bearish candle confirmation (\(Close_t < Open_t\)).
- **Legacy Risk Model**: Fixed Stop Loss at \(Low_{t-1}\) (Long) / \(High_{t-1}\) (Short); Take Profit fixed at \(2.0 \times\) initial risk.

### Mathematical & Structural Bottlenecks Identified:
1. **Chop Churn & Moving Average Whipsaws**: In range-bound markets (\(ADX < 20\)), fast moving averages produce continuous false crossings, incurring heavy spread and commission degradation.
2. **Single-Bar Stop Fragility**: Placing stops at \(Low_{t-1}\) or \(High_{t-1}\) without volatility buffering leaves positions exposed to routine market microstructure liquidity sweeps and spread widening.
3. **Fixed 1:2 R:R Profit Truncation**: A rigid 1:2 take-profit closes winning trades prematurely on strong trend days, sacrificing the fat-tailed right skew essential for positive mathematical expectancy.
4. **Counter-Trend Entrapment**: Taking short signals in macro bull trends (or long signals in macro bear trends) results in severe adverse selection.

---

## 2. Quantitative Enhancements Implemented

```
+-------------------------------------------------------------------------------+
|                      7/11 PRO CONFLUENCE DECISION MATRIX                      |
+-------------------------------------------------------------------------------+
| 1. Macro Regime Filter     : Price > HTF 200 EMA (Long) or < HTF 200 EMA (Short)  |
| 2. Trend Expansion Gate   : ADX(14) >= 20.0 (Filters dead range consolidation)   |
| 3. Volume Surge Gate       : Volume >= 1.2x SMA(Volume, 20) (Institutional push)  |
| 4. RSI Momentum Corridor   : RSI(14) ∈ [50, 70] (Longs) / [30, 50] (Shorts)        |
| 5. Time-of-Day Killzone    : Active during high-volume sessions (NY / London)    |
| 6. Entry Trigger           : Fast 7 EMA x 11 SMA Crossover + Candle Confirmation  |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
|                    MULTI-STAGE RISK & EXECUTION ENGINE                        |
+-------------------------------------------------------------------------------+
| • Volatility Stop Loss     : Min(Low[1], Low[2]) - 0.5 * ATR(14) [Capped at Max] |
| • Stage 1 Take Profit (50%): Limit at Entry + 1.5x Initial Risk R (De-risking)|
| • Breakeven Ratchet        : Stop Loss migrated to Entry + Buffer on TP1 Hit   |
| • Stage 2 Runner (50%)     : Trailed via 11-SMA Cross or 1.5x ATR Trailing Band|
+-------------------------------------------------------------------------------+
```

### Enhancement 1: Macro Regime & Trend Bias Filter
- **Mechanism**: Reads the Higher Timeframe (1H / 4H) 200-period EMA.
- **Rule**:
  $$\text{Allow Long} \iff Close_t > EMA_{HTF}(200) \quad \land \quad ADX(14) \ge 20$$
  $$\text{Allow Short} \iff Close_t < EMA_{HTF}(200) \quad \land \quad ADX(14) \ge 20$$
- **Effect**: Eliminates over 50% of counter-trend whipsaws and blocks entries during low-volatility dead zones.

### Enhancement 2: Volatility-Adaptive Dynamic Stops (ATR-Bounded)
- **Mechanism**: Stops are anchored to a 2-bar swing extremity with an ATR volatility cushion, subject to a hard tick/point ceiling:
  $$\text{SL}_{Long} = Close_t - \min\left( Close_t - (\min(Low_{t-1}, Low_{t-2}) - 0.5 \times ATR_{14}), \; \text{Max SL Points} \right)$$
- **Effect**: Protects trades from liquidity wicks while strictly enforcing portfolio risk constraints (e.g. max 35 ticks on /NQ).

### Enhancement 3: Multi-Stage Profit Taking & Trailing Engine
- **Stage 1 (TP1 @ 1.5R)**: Scale out **50% of position size** at \(1.5 \times\) initial risk distance.
- **Breakeven Migration**: Once TP1 is filled, the Stop Loss is immediately ratcheted to \(Entry + \text{offset}\), securing a zero-risk trade.
- **Stage 2 (Runner)**: The remaining 50% trails the **11-period SMA** or a **1.5x ATR trailing band** until trend exhaustion.

### Enhancement 4: Volume & Momentum Confirmation Gates
- **Volume Surge Gate**: Entry candle volume must satisfy \(Volume_t \ge 1.2 \times SMA_{20}(Volume)\).
- **RSI Momentum Corridor**:
  - Longs: \(50 \le RSI(14) \le 70\) (active upward momentum without being overbought).
  - Shorts: \(30 \le RSI(14) \le 50\) (active downward momentum without being oversold).

### Enhancement 5: Time-of-Day Execution Killzones
- **US Equities & Index Futures (/NQ, /CL)**:
  - Morning Killzone: `09:30 – 11:30 EST` (Opening drive & volatility expansion)
  - Afternoon Killzone: `13:30 – 15:30 EST` (Institutional rebalancing & close drive)
  - Exclude the `11:30 – 13:30 EST` lunch lull.
- **Crypto (SOLUSDT, BTCUSDT)**:
  - `03:00 – 17:00 EST` (London Open through NY Close overlap).

---

## 3. Asset-Specific Tuning & Recommendations

| Asset | Primary Timeframe | Fast/Slow MA | ATR Buffer | Max SL Cap | Session Window | Key Considerations |
|---|---|---|---|---|---|---|
| **/NQ (E-mini Nasdaq)** | 1m / 5m / 15m | 7 EMA / 11 SMA | 0.5x ATR | 35 ticks (8.75 pts) | 09:30-11:30 & 13:30-15:30 EST | Highly sensitive to opening range news; enforce max tick cap. |
| **/CL (Crude Oil)** | 5m / 15m | 7 EMA / 11 SMA | 0.4x ATR | 40 ticks ($0.40/bbl) | 09:00-11:30 & 13:00-14:30 EST | High momentum follow-through; avoid Wednesday 10:30 EST EIA releases. |
| **SOLUSDT** | 15m / 1H | 7 EMA / 11 SMA | 0.6x ATR | 2.50 USDT | 03:00-17:00 EST | High volatility altcoin; trailing runner captures multi-day macro moves. |
| **BTCUSDT** | 15m / 1H / 4H | 7 EMA / 11 SMA | 0.5x ATR | 850.0 USDT | 24/7 or London/NY Active | Strongest win-rate when aligned with HTF 4H 200 EMA trend. |

---

## 4. Automated Bot Execution & Webhook Payloads

The Pine Script strategy generates structured JSON webhook alerts formatted for direct ingestion by the Moon Dev FastAPI execution server:

### Buy Entry Alert Payload:
```json
{
  "token": "MOONDEV_711_SECRET",
  "account": "hyperliquid_algo_01",
  "magic": 71101,
  "action": "BUY",
  "ticker": "SOLUSDT",
  "price": 182.45,
  "sl": 179.80,
  "tp1": 186.42,
  "risk": 2.65,
  "adx": 24.8,
  "rsi": 58.2,
  "time": 1724126400000
}
```

### Partial TP1 Close Alert Payload:
```json
{
  "token": "MOONDEV_711_SECRET",
  "account": "hyperliquid_algo_01",
  "magic": 71101,
  "action": "PARTIAL_TP1",
  "ticker": "SOLUSDT",
  "price": 186.42,
  "qty_pct": 50,
  "time": 1724128200000
}
```

### Breakeven Ratchet Alert Payload:
```json
{
  "token": "MOONDEV_711_SECRET",
  "account": "hyperliquid_algo_01",
  "magic": 71101,
  "action": "MOVE_TO_BREAKEVEN",
  "ticker": "SOLUSDT",
  "new_sl": 182.70,
  "time": 1724128200000
}
```

---

## 5. File Manifest

All assets for Strategy #2 have been compiled in:
- **Pine Script Strategy**: `pine_scripts/strategy_02_711_crossover_pro.pine`
- **Python Backtester & Optimizer**: `backtests/test_711_crossover.py`
- **Research & Engineering Notes**: `research_notes_711.md`
