---
title: Monarch Trading Terminal & 50-Trade Hurdle Tracker
tags:
  - monarch
  - trading-terminal
  - hurdle-tracker
  - execution-telemetry
last_synced: "2026-09-05 07:58:02 UTC"
---

# 📈 Monarch Trading Terminal & 50-Trade Hurdle Tracker

> [!INFO] **Live Delta-Neutral Harvester Telemetry**
> - **Total Account Equity**: **`$100.3K`** (Starting: `$100.0K`)
> - **Available Cash Balance**: **`$60.3K`** • Deployed Collateral: **`$40.0K`**
> - **Net Realized Yield / PnL**: **`+$337.78`**
> - **Accrued Funding Yield**: **`+$378.78`** (59 accrual cycles)
> - **Total Execution Fees Paid**: `$41.00` (Net of maker/taker accounting)
> - **Active Basis Pairs**: `2 pairs deployed`
> - **Last Synchronized**: `2026-09-05 07:58:02 UTC`

---

## 🎯 Pre-Registered 50-Trade Hurdle Validation Deck

> [!WARNING] **Directional Liquidation Fade: Terminated Early at N=12 & Retired**
> The pre-registered 50-trade hurdle on the **Reactive Liquidation Fade Strategy** was committed on 2026-08-31 to evaluate directional edge under strict maker/taker fees (1.0 bps / 3.5 bps):
> - **Pre-Registered Bar**: Win Rate **`>= 54.0%`** (Net of fees) **AND** Profit Factor **`>= 1.25`** over 50 closed trades.
> - **Archived Baseline ($N=12$)**: Win Rate **`25.0%`** (3 Wins / 9 Losses) • Profit Factor **`0.12`** • Net PnL **`-$536.74`** (Gross: `-$482.76`, Fees: `$53.98`).
> - **Excursion Benchmark (`wick_benchmark.py`)**: Empirical MFE/MAE ratio measured at **`0.513`** vs. random control **`1.092`** ($p = 0.0259$ at 30m). Forced liquidations are momentum drivers that continue running against the position, not mean-reverting wicks.
> - **Current Verdict**: 🔴 **FAIL / RETIRED (TERMINATED EARLY AT N=12 / 50)**
> - **Operational State**: Directional trading is halted ([`FADE_STRATEGY_ENABLED = False`](file:///C:/Users/ixis1/Desktop/DEV/HyperLiquid/HL_Monarch/config/settings.py)). Placed in **PASSIVE Re-benchmarking Mode** (telemetry logs sweeps without placing orders; requires 7d window, >=500 events, $P(\text{ratio} \ge 1.25) > 0.90$ under cluster bootstrap to reopen).
> - **Archive Reference**: `HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json`

| Hurdle Metric | Archived Baseline (N=12) | Required PASS Floor | Verdict / Progress |
| :--- | :---: | :---: | :--- |
| **Sample Size** | **`12 trades`** | `50 trades` | `████░░░░░░░░░░░` **24.0%** (12/50) (Archived early at N=12) |
| **Win Rate** | **`25.0%`** | `>= 54.0%` | `██░░░░░░░░` **25.0%** (25/100) 🔴 **FAIL** (3W / 9L) |
| **Profit Factor** | **`0.12`** | `>= 1.25` | `Gross: $75.30 / Loss: $612.04` 🔴 **FAIL** |
| **Signal MFE/MAE** | **`0.513`** | `>= 1.250` | Control: `1.092` 🔴 **ADVERSE MOMENTUM** |

---

## 📊 Active Delta-Neutral Basis Positions
*Capital redeployed to delta-neutral cash-and-carry funding rate harvesting (Long Spot + Short Perp).*

| Asset | Spot Pair | Leg Notional | Spot Entry | Perp Entry | Entry APR | Realised APR | Funding Accrued | Duration |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`para:ANSEM`** | `UANSEM` | $10.0K | `$0.2996` | `$0.2996` | `+2924.75%` | `+519.75%` | **`+$350.06`** | `97.2h` |
| **`XPL`** | `UXPL` | $10.0K | `$0.0843` | `$0.0843` | `+31.58%` | `+17.41%` | **`+$4.77`** | `54.3h` |

---

## ⏳ Resting Limit Order Book (TTL Countdown)

| Asset | Side | Limit Price | Units | Notional | Order Expiration |
| :--- | :---: | :---: | :---: | :---: | :---: |
| — | — | — | — | — | *No resting limit orders active (FADE_STRATEGY_ENABLED = False).* |

---

## 📜 Recent Closed Trades History

| Asset | Net Realized PnL | Holding Period | Exit Classification |
| :--- | :---: | :---: | :--- |
| **`xyz:HOOD`** | 🟢 **$4.09** | `51.0h` | `ILLIQUID_SPOT_LEG: HOOD is synthetic TradFi (quarantined)` |
| **`para:AVGO`** | 🟢 **$0.15** | `16.0h` | `ILLIQUID_SPOT_LEG: AVGO is synthetic TradFi (quarantined)` |
| **`xyz:AVGO`** | 🔴 **-$7.28** | `16.0h` | `ILLIQUID_SPOT_LEG: AVGO is synthetic TradFi (quarantined)` |

---

## 🔗 Cockpit Navigation

- [[Monarch_Hub|👑 Monarch Intelligence Hub]]
- [[Bot_Control|🎮 Bot Control & Activation Deck]]
- [[Bot_Config|⚙️ Bot Configuration & Risk Controller]]
- [[HyperLiquid_Monarch|🏛 HyperLiquid Market Dashboard]]
- [[Polymarket_Monarch|🌐 Polymarket Intelligence]]
- [[Quant_Trading_Lab|⚡ Quant Trading Lab]]
---
*Generated automatically by Monarch Execution Exporter.*
