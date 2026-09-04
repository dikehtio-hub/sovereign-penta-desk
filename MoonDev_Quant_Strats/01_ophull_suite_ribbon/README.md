# Strategy #1: OP Hull Suite Ribbon Pro (`ophullrib`)

**Category**: Trend Momentum & Hull Strain Reversal System  
**Author / Lab Reference**: Moon Dev Quant Elite Lab (Discord Strategy #474 & #480)  
**Primary Target Assets**: Solana (`SOL-USD`), E-mini Nasdaq Futures (`/NQ`), Bitcoin (`BTC-USD`), Ethereum (`ETH-USD`)  
**Recommended Timeframes**: `1H`, `4H` (Swing Horizon) | `15m` (Scalp with MTF filter)

---

## 🌟 Strategy Overview & Quantitative Edge

The **OP Hull Suite Ribbon Pro** is a high-conviction trend capture engine that replaces standard moving averages with an ultra-responsive, phase-corrected **Triple Hull Moving Average (THMA)** coupled with a **Normalized Distance Weight Oscillator**.

### Quantitative Architecture & Core Components:
1. **Triple Hull Moving Average (THMA)**:
   $$\text{THMA}(src, n) = \text{WMA}(3 \cdot \text{WMA}(src, n/3) - \text{WMA}(src, n/2) - \text{WMA}(src, n), n)$$
   Eliminates the lag inherent in standard exponential and simple moving averages while eliminating whipsaws.
2. **Normalized Distance Epoch Weight Strain**:
   $$\text{Dist}_t = \frac{\text{SHULL}_t - \text{MHULL}_t}{\max(\text{MHULL}_t, \text{SHULL}_t)} \times 1000$$
   Accumulates epoch strain across market waves. Only allows trades when previous cycle momentum $|W| > \text{Threshold}$, preventing entries in weak micro-chop.
3. **200 EMA Macro Regime Filter**:
   Restricts long entries to macro bull regimes ($Price > EMA_{200}$) and shorts to macro bear regimes ($Price < EMA_{200}$).
4. **ADX Trend Expansion Filter**:
   Requires $ADX \ge 18–20$ to ensure the market is expanding directionally.
5. **Multi-Stage Exit Engine**:
   - **Stage 1**: Take 50% profit at $+2.0\times$ ATR.
   - **Stage 2**: Ratchet Stop Loss to Entry Price (Breakeven).
   - **Stage 3**: Let the remaining 50% macro runner ride until the Ribbon Flips.
6. **Multi-Timeframe (MTF) Ribbon Confluence**:
   Aligns local 15m/1H entries with the 4H/Daily macro trend.
7. **Session / Time-of-Day Filter**:
   Restricts index futures entries (/NQ) to the high-liquidity New York trading session ($09:30 - 16:00$ EST).

---

## 📊 3-Year Quantitative Benchmark ($10,000 Starting Cash)

| Asset / Product | Timeframe | 3-Year Window | Ending Equity | Net Return | Buy & Hold | Win Rate | Profit Factor | Sortino | Max Drawdown | Total Trades |
|---|---|---|---|---|---|---|---|---|---|---|
| **SOL-USD** | **4H** | 2023/11 – 2024/04 | **$21,685.84** | **+116.86%** | +146.30% | **58.3%** | **4.08** | **14.16** | -30.55% | 12 |
| **/NQ Futures** | **1H** | 2026/05 – 2026/08 | **$22,864.75** | **+128.65%** | +202.06% | **75.0%** | **3.43** | **20.29** | -64.14% | 8 |
| **SOL-USD** | **1H** | 2023/11 – 2024/04 | **$16,427.37** | **+64.27%** | +148.72% | **45.7%** | **1.87** | **8.06** | **-17.18%** | 46 |
| **SOL-USD** | **15m** | 2023/11 – 2024/04 | **$11,397.99** | **+13.98%** | +145.62% | 37.9% | 1.17 | 1.53 | -21.29% | 132 |
| **ETH-USD** | **1H** | 2022/01 – 2023/11 | **$10,743.60** | **+7.44%** | -46.57% | 36.7% | 1.13 | 0.29 | **-20.36%** | 90 |

---

## 📁 Repository Deliverables

- 📄 [`OP_Hull_Suite_Ribbon_Strategy.pine`](file:///C:/Users/ixis1/Desktop/DEV/MoonDev_Quant_Strats/01_ophull_suite_ribbon/OP_Hull_Suite_Ribbon_Strategy.pine): Pine Script v5 Strategy with HUD, multi-stage exits & webhooks.
- 📄 [`OP_Hull_Suite_Ribbon_Indicator.pine`](file:///C:/Users/ixis1/Desktop/DEV/MoonDev_Quant_Strats/01_ophull_suite_ribbon/OP_Hull_Suite_Ribbon_Indicator.pine): Pine Script v5 Indicator with visual signals & `alertcondition()`.
- 🐍 [`backtest_ophullrib.py`](file:///C:/Users/ixis1/Desktop/DEV/MoonDev_Quant_Strats/01_ophull_suite_ribbon/backtest_ophullrib.py): Modular Python backtester with resampling, date slicing, optimization, and chart plotting.
- 📊 [`run_multi_asset_backtest.py`](file:///C:/Users/ixis1/Desktop/DEV/MoonDev_Quant_Strats/01_ophull_suite_ribbon/run_multi_asset_backtest.py): Multi-product benchmark harness comparing SOL, BTC, ETH, and /NQ.

---

## 🤖 Webhook Automation Integration

To connect TradingView to an automated bot:
1. In TradingView, create an alert on `OP_Hull_Suite_Ribbon_Strategy`.
2. In the **Message** field, enter:
   ```json
   {{strategy.order.alert_message}}
   ```
3. Set the Webhook URL to your bot endpoint (e.g. `http://your-server-ip:8000/webhook/order`).
