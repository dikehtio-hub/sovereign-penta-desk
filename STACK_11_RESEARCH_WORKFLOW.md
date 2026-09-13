# STACK 11 — Volatility Squeeze Expansion: Research & Backtest Protocol

**Protocol Status**: COMPLETE (Empirical real-data backtest across 17 datasets, 1,003 trades, two-way slippage and exchange friction verified).  
**Harness Target**: `quant_trading_lab/strategies/stack11_volatility_squeeze.py` & `backtesters/test_stack11_squeeze.py`.  
**Execution Context**: Pre-Drill Sandbox (in-memory execution over historical CSVs; zero production daemon interaction; September 16 FOMC freeze upheld).  

---

## 1. Executive Summary & Core Findings

1. **Intraday Squeeze Expansion on Index Futures (ES 5m)**:
   - Squeeze expansion on 5m ES shows positive in-sample edge on the available 10-week sample (`data/ES_5m.csv`).
   - At baseline ($1.5 \times ATR$ stop, $2.0R$ target), ES 5m nets **+$28,551.09** ($PF = 1.26, 62 \text{ trades}, t = 0.81, P(net \le 0) = 0.208$).
   - Under calibrated tuning ($sq=4$ compression bars, $2.0 \times ATR$ stop, $2.5R$ target), ES 5m reaches **$PF = 1.59$** ($53 \text{ trades}, \text{Win Rate } 47.2\%, t = 1.45, P(net \le 0) = 0.071$, best trade 21% of net).
   - **Data Caveat**: The dataset spans only 10 weeks (53-62 trades); statistical significance is not established ($t = 1.45 < 1.96$), and out-of-sample multi-year validation is blocked by the Milestone 10 CME 5m history gap. Anatomical analysis shows 100% of profit was generated on the short side ($PF = 3.28$ short vs $0.62$ long).
2. **Commodity Intraday Squeeze (CL 5m Intraday) — FAILED Cross-Check**:
   - Post-fix cross-check shows CL 5m baseline nets **-$2,987.41** ($PF = 0.95, 58 \text{ trades}$).
   - Parameter sweep across grid shows $PF = 0.80 \text{ to } 1.10$, with 5 of 8 cells $\le 1.01$. Apparent edge deltas against random entries swing wildly due to high random baseline variance on short files. CL 5m edge does not survive rigorous auditing.
3. **Crypto Perpetual 1-Hour Squeeze (BTC 1h) — FORMALLY RETRACTED**:
   - The initial $PF = 1.44$ on 90-day `BTC_PERP_1h.csv` was an artifact of stale momentum calculation on a short window.
   - Post-fix on the 90-day file yields **43 trades, $PF = 0.96$, -$1,161.96** ($t = -0.10$).
   - On the 6.67-year continuous history (`continuous/BTCUSDT_1h_binance.csv`, 2020-01 to 2026-08), Stack 11 on BTC 1h is **statistically significantly negative**: **1,330 trades, $PF = 0.82$, -$192,702.20, t = -2.83, P(net \le 0) = 0.997**, below random baseline ($PF = 0.94$) and losing in 6 of 7 years.
   - The claim of "1h BTC alpha isolated" is formally retracted.
4. **The 5-Minute Crypto Friction Rule Confirmed at Scale**:
   - Evaluated on 3.67 years of Binance data (`continuous/BTCUSDT_5m_binance.csv`, 2023-01 to 2026-08): **6,909 trades, $PF = 0.57$, -$913,243.29, -9.9 \text{ bps/trade}, t = -18.84, P(net \le 0) = 1.000**.
   - Net loss per trade precisely tracks the round-trip taker friction ($\sim 10 \text{ bps}$). Independently confirms at massive scale that 5m crypto market-order breakout strategies cannot overcome exchange friction.
5. **Gold Futures Multi-Year Positive Cell (GC 1h)**:
   - On the 2.4-year history (`continuous/MGC_1h_continuous.csv` / `GC_1h.csv`), GC 1h is the only surviving multi-year positive cell: **51 trades, $PF = 1.30$, +$11,368.10, \text{Max DD } \$9,113.14$, vs random $0.60$**. Optional candidate for future pre-registration.

---

## 2. Mathematical Specification: Stack 11 Volatility Squeeze

### 2.1 Compression Phase (The Squeeze)
For bar $t$, calculate Bollinger Bands ($SMA_{20}, 2.0\sigma$) and Keltner Channels ($SMA_{20}, 1.5 \times ATR_{20}$):
$$\text{Upper}_{BB} = \mu_{20} + 2.0 \cdot \sigma_{20}, \quad \text{Lower}_{BB} = \mu_{20} - 2.0 \cdot \sigma_{20}$$
$$\text{Upper}_{KC} = \mu_{20} + 1.5 \cdot ATR_{20}, \quad \text{Lower}_{KC} = \mu_{20} - 1.5 \cdot ATR_{20}$$
$$\text{Squeeze}(t) \iff \text{Upper}_{BB} < \text{Upper}_{KC} \land \text{Lower}_{BB} > \text{Lower}_{KC} \iff 2.0 \cdot \sigma_{20} < 1.5 \cdot ATR_{20}$$
The squeeze must hold for at least $\text{min\_squeeze\_bars}$ (default: 3 bars) prior to release.

### 2.2 Expansion Phase (The Firing Trigger)
The squeeze **fires** on bar $t$ when volatility expands out of compression:
$$\text{Fire}(t) \iff \neg\text{Squeeze}(t) \land \left(\bigwedge_{i=1}^{k} \text{Squeeze}(t-i)\right), \quad k \ge \text{min\_squeeze\_bars}$$

### 2.3 Directional Momentum Filter
Direction is determined by linear regression slope of price displacement from the composite midline:
$$\Delta_i = Close_i - \frac{1}{2}\left(\frac{\max(H_{20}) + \min(L_{20})}{2} + SMA_{20}(Close)\right)$$
$$\text{Momentum}(t) = \text{LinRegEndpoint}(\Delta, 20)$$
- **Long Signal**: $\text{Fire}(t) \land \text{Momentum}(t) > 0 \land Close_t > SMA_{20}$
- **Short Signal**: $\text{Fire}(t) \land \text{Momentum}(t) < 0 \land Close_t < SMA_{20}$

### 2.4 Risk & Position Mechanics
- **Stop Loss**: $ATR_{14} \times \text{atr\_stop\_multiple}$ (default: $1.5$ to $2.0$).
- **Take Profit**: $\text{stop\_distance} \times \text{reward\_multiple}$ (default: $2.0$ to $2.5R$).
- **Session Auto-Flatten**: For CME Futures (`NQ`, `ES`, `GC`, `CL`), trades enter only during RTH ($09:30 - 15:30 \text{ EST}$) and auto-flatten before exchange close ($16:00 \text{ EST}$ for indices, $14:30$ for oil, $13:30$ for gold) via `engine/session_clock.py`. Crypto perps run 24/7 without session cutoffs.
- **Two-Way Slippage**: Fills are strictly charged two-way slippage:
  $$\text{Fill}_{\text{entry}} = \text{entry} + \text{direction} \cdot \text{slip}, \quad \text{Fill}_{\text{exit}} = \text{exit} - \text{direction} \cdot \text{slip}$$

---

## 3. Empirical Results: Universal Baseline Matrix (Post-Fix Re-Scored)

Parameters: $BB(20, 2.0)$, $KC(20, 1.5)$, $\text{min\_sq} = 3$, $\text{Stop} = 1.5 \times ATR$, $\text{Target} = 2.0R$.  
Evaluated over 17 historical datasets in `quant_trading_lab/data/` (scaled_500k sizing tier, true two-way slippage, full exchange friction):

| Asset | Timeframe | Trades | Win Rate | Real PF | Random PF | Edge $\Delta PF$ | Net PnL ($) | Max DD ($) | Avg $/Trade | Avg bps | Stat Confidence |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **NQ** | **5m** | 73 | 37.0% | 1.07 | 1.09 | -0.02 | +$11,136.07 | $25,143.57 | +$152.55 | +0.2 | **HIGH** ($\ge 50$) |
| **ES** | **5m** | 62 | 40.3% | **1.26** | 0.96 | **+0.30** | **+$28,551.09** | $13,683.54 | +$460.50 | +1.4 | **HIGH** ($\ge 50$) |
| **CL** | **5m** | 58 | 34.5% | 0.95 | 1.02 | -0.06 | -$2,987.06 | $22,278.96 | -$51.50 | -0.7 | **HIGH** ($\ge 50$) |
| **GC** | **5m** | 55 | 40.0% | 0.88 | 0.99 | -0.11 | -$12,653.12 | $40,449.94 | -$230.06 | -0.5 | **HIGH** ($\ge 50$) |
| **BTCUSDT**| **5m** | 55 | 36.4% | 0.52 | 0.47 | +0.05 | -$8,415.27 | $8,937.80 | -$153.00 | -10.1 | **HIGH** ($\ge 50$) |
| **ETHUSDT**| **5m** | 79 | 34.2% | 0.64 | 0.64 | +0.00 | -$3,361.09 | $3,361.09 | -$42.55 | -9.2 | **HIGH** ($\ge 50$) |
| **NQ** | **15m**| 26 | 53.8% | 1.02 | 0.54 | +0.48 | +$626.43 | $23,063.39 | +$24.09 | -0.2 | LOW (<30) |
| **ES** | **15m**| 32 | 43.8% | 0.98 | 1.01 | -0.04 | -$1,657.12 | $17,917.37 | -$51.79 | -1.4 | MEDIUM (30-49) |
| **CL** | **15m**| 19 | 42.1% | 0.86 | 1.39 | -0.53 | -$3,343.87 | $15,644.61 | -$175.99 | -4.5 | LOW (<30) |
| **GC** | **15m**| 14 | 35.7% | 0.51 | 1.18 | -0.68 | -$12,549.26 | $23,630.79 | -$896.38 | -11.2 | LOW (<30) |
| **BTCUSDT**| **15m**| 81 | 29.6% | 0.50 | 0.75 | -0.25 | -$16,963.55 | $19,517.95 | -$209.43 | -15.2 | **HIGH** ($\ge 50$) |
| **ETHUSDT**| **15m**| 91 | 30.8% | 0.66 | 0.80 | -0.14 | -$4,644.51 | $5,265.26 | -$51.04 | -12.7 | **HIGH** ($\ge 50$) |
| **NQ** | **1h** | 80 | 42.5% | 1.09 | 1.36 | -0.28 | +$10,200.89 | $44,730.54 | +$127.51 | -3.0 | **HIGH** ($\ge 50$) |
| **ES** | **1h** | 110| 44.5% | 0.82 | 1.10 | -0.28 | -$27,491.34 | $32,818.52 | -$249.92 | -3.7 | **HIGH** ($\ge 50$) |
| **CL** | **1h** | 74 | 40.5% | 0.61 | 0.97 | -0.36 | -$27,162.25 | $32,182.75 | -$367.06 | -10.3 | **HIGH** ($\ge 50$) |
| **GC** | **1h** | 51 | 47.1% | **1.30** | 0.60 | **+0.71** | **+$11,368.14** | $9,112.61 | +$222.90 | +2.8 | **HIGH** ($\ge 50$) |
| **BTCUSDT**| **1h** | 43 | 37.2% | 0.96 | 0.67 | +0.29 | -$1,161.96 | $9,566.43 | -$27.02 | +0.1 | MEDIUM (30-49) |
| **TOTAL** | — | **1,003**| — | — | — | — | **-$60,507.79**| — | — | — | — |

---

## 4. Sensitivity Sweep & Out-of-Window Cross-Check Findings

### 4.1 S&P 500 E-mini (ES 5m) — Only Surviving Intraday Cell
* On the 10-week file (`data/ES_5m.csv`), tuning improves performance across all $2.0 \times ATR$ stop configurations:
  - `sq=4, stop=2.0, r=2.5`: **53 trades, Win Rate 47.2%, $PF = 1.59$, Net +$53,588.29, \text{Max DD } \$15,026.00, t = 1.45, P(net \le 0) = 0.071$**.
  - Baseline `sq=3, stop=1.5, r=2.0`: **62 trades, Win Rate 40.3%, $PF = 1.26$, Net +$28,551.09, t = 0.81, P(net \le 0) = 0.208$**.
* **Critical Anatomical Vulnerability**: Trade decomposition reveals **100% of profit came from short trades** (Shorts: 28 trades, $PF = 3.28$, +$75.6\text{k}$; Longs: 25 trades, $PF = 0.62$, -$22.0\text{k}$). Furthermore, 35.8% of trades exited via `time_flatten` at the 16:00 pit close (+$\text{\$61.3k}$, 78.9% win rate).
* **Verdict**: Promising in-sample, but cannot be established as statistically significant ($t = 1.45$) or structurally stable until Milestone 10 multi-year 5m continuous futures data is ingested.

### 4.2 Crude Oil (CL 5m) — Does Not Survive Cross-Check
* Baseline nets -$2,987.06 ($PF = 0.95$). Sensitivity grid yields $PF = 0.80 \text{ to } 1.10$, with 5 of 8 cells $\le 1.01$. Apparent positive deltas against random baseline are artifacts of random baseline sampling variance on short files. CL 5m is not an edge.

### 4.3 Bitcoin Perpetual (BTC 1h) — Formally Retracted
* Evaluated against continuous multi-year data (`continuous/BTCUSDT_1h_binance.csv`, 2020-2026): **1,330 trades, $PF = 0.82$, Net -$192,702.20, t = -2.83, P(net \le 0) = 0.997$**. Negative 6 of 7 years. The 90-day file gain was a transient window artifact.

---

## 5. Architectural & Capitalization Rules Codified

1. **Futures Contract Sizing Rule**:
   - Full-size contracts (`NQ` $20/pt, `GC` $100/pt) floor to 0 contracts on a standard $100k account under 5m ATR stops. Intraday deployment on accounts under $250k must use micro contracts (`MNQ`, `MES`, `MGC`, `MCL`) or the `scaled_500k` tier.
   - Any signal where sizing floors to 0 contracts must immediately invoke `strategy.notify_position_closed()` to avoid permanently muting the strategy.
2. **Timeframe & Asset Class Demarcation**:
   - **5m Crypto Disqualification Confirmed**: 5-minute crypto market orders lose -9.9 to -10.3 bps/trade, exactly matching taker fee drag across 6,909 trades ($PF = 0.57, t = -18.84$). 5m crypto breakouts are permanently disqualified.
   - **1h Crypto Squeeze Disqualified**: Squeeze breakout on 1h BTC fails across 6.67 years ($PF = 0.82, t = -2.83$).
   - **1h Gold Futures (GC 1h)**: The only multi-year survivor (51 trades, $PF = 1.30$, +$11.4\text{k}$ over 2.4 years). Available for post-drill pre-registration.

---

## 6. How to Reproduce

All commands execute cleanly in under 5 seconds using the project venv:

```powershell
# 1. Run unit tests (non-repainting & signal verification)
quant_trading_lab\venv\Scripts\python.exe -m pytest quant_trading_lab\tests\test_stack11_squeeze.py -v

# 2. Run 5-minute intraday focus matrix across all 6 markets
quant_trading_lab\venv\Scripts\python.exe -u -m backtesters.test_stack11_squeeze --5m

# 3. Run full multi-timeframe matrix (5m, 15m, 1h across 17 datasets)
quant_trading_lab\venv\Scripts\python.exe -u -m backtesters.test_stack11_squeeze --all
```

---

## 7. Artifact Registry

- Strategy Implementation: [`quant_trading_lab/strategies/stack11_volatility_squeeze.py`](file:///c:/Users/ixis1/Desktop/DEV/quant_trading_lab/strategies/stack11_volatility_squeeze.py)
- Unit Test Suite: [`quant_trading_lab/tests/test_stack11_squeeze.py`](file:///c:/Users/ixis1/Desktop/DEV/quant_trading_lab/tests/test_stack11_squeeze.py)
- Research & Backtester Engine: [`quant_trading_lab/backtesters/test_stack11_squeeze.py`](file:///c:/Users/ixis1/Desktop/DEV/quant_trading_lab/backtesters/test_stack11_squeeze.py)
- Documentation Protocol: [`STACK_11_RESEARCH_WORKFLOW.md`](file:///c:/Users/ixis1/Desktop/DEV/STACK_11_RESEARCH_WORKFLOW.md)
