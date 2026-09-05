---
title: Risk Sentinel - Multi-Desk Monte Carlo
tags:
  - risk
  - monte-carlo
  - risk-of-ruin
  - cross-market
  - dashboard
last_synced: "2026-09-05 03:58:37 UTC"
---

# 🛡 Risk Sentinel - Multi-Desk Monte Carlo (Item 19)

> [!SUCCESS] **Practical ruin (-50%) over 365d: `0.00%`** · hard ruin `0.000%`
> - **Last Synchronized**: `2026-09-05 03:58:37 UTC`
> - **Paths**: `100,000` × `365` days, seed `7`, start equity `$100,320.45`
> - **Buffer**: keep `$3,519` unallocated (VaR99 365d drawdown `3.5%`); size every desk at `x2.00`
> - Shell twin: `python -m cross_market.risk_simulator --iterations 100000 --json`

> **Cockpit Navigation**: [[Monarch_Hub|👑 Master Hub]] • [[HyperLiquid_Monarch|🏛 HyperLiquid]] • [[Sports_Desk|🏈 Sports Desk]] • [[Cross_Market_Arb|⚖️ Cross-Market Arb]] • [[Cross_Market_Titans|🌐 Titans]] • [[Bot_Config|⚙️ Bot Config]]

---

## 📉 Ruin & Drawdown

| Metric | 30d | 365d |
| :--- | :---: | :---: |
| Hard ruin P(equity ≤ 0) | `0.000%` | `0.000%` |
| Practical ruin P(drawdown ≥ 50%) | `0.00%` | `0.00%` |
| Max drawdown VaR 95 | `0.72%` | `2.94%` |
| Max drawdown VaR 99 | `1.17%` | `3.51%` |
| Median max drawdown | — | `2.03%` |

**Terminal equity** (365d): p05 `$105,828` · p50 `$109,131` · p95 `$112,458` · median log growth `+0.0842` · escrow median `$4,213`

**Desk mean P&L** (365d): basis `$6,289` · sports `$2,292` · arb `$4,460` · tax `-$4,225` · liquidations per path `0.172`

---

## 🎯 Cross-Desk Kelly Shrinkage

Multiplier on every desk's sizing (basis capital per position, sports Kelly fraction, arb capital); the recommendation maximises median log growth with practical ruin ≤ `5%` and the desks' capital fitting inside the equity (allocation ≤ 100%). Tax escrow leaves the trading bankroll and therefore counts as drawdown here.

| Multiplier | Median log growth | Practical ruin | Hard ruin | VaR95 365d | Allocation | |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `x0.25` | `+0.0216` | `0.00%` | `0.00%` | `0.8%` | `20%` |  |
| `x0.50` | `+0.0429` | `0.00%` | `0.00%` | `1.5%` | `30%` |  |
| `x0.75` | `+0.0638` | `0.00%` | `0.00%` | `2.2%` | `41%` |  |
| `x1.00` | `+0.0844` | `0.00%` | `0.00%` | `3.0%` | `51%` |  |
| `x1.25` | `+0.1046` | `0.00%` | `0.00%` | `3.7%` | `61%` |  |
| `x1.50` | `+0.1245` | `0.00%` | `0.00%` | `4.4%` | `71%` |  |
| `x2.00` | `+0.1633` | `0.00%` | `0.00%` | `5.7%` | `92%` | **recommended** |

**Binding constraint**: capital allocation - ruin never bound at any size that fits the equity, so the pick means 'risk is not the limit', not 'add leverage'.

---

## ⚡ Systemic Stress

Correlation `0.50`, shock-day probability `0.020` (`7.3` days per path), perp vol `x3.0` on shock days; sports wagers are unaffected (nothing links them to a crypto squeeze).

| Metric | Baseline | Stressed | Δ |
| :--- | :---: | :---: | :---: |
| VaR99 max drawdown 365d | `3.49%` | `3.51%` | `+0.01 pp` |
| VaR95 max drawdown 365d | `2.94%` | `2.94%` | `+0.01 pp` |
| Practical ruin 365d | `0.00%` | `0.00%` | `+0.00 pp` |
| Recommended cash buffer | `$3,505` | `$3,519` | `+15` |
| Basis desk P&L | `$6,445` | `$6,289` | `-156` |
| Arb desk P&L | `$4,470` | `$4,460` | `-10` |
| Liquidations per path | `0.153` | `0.172` | `+0.019` |

---

## 🧾 Inputs & Provenance

Desk 4 (Quant Trading Lab) is outside this simulation. `assumed` inputs have no live history yet.

| Input | Value | Provenance |
| :--- | :---: | :--- |
| `arb_capital` | `1000` | assumed |
| `arb_desync_loss_max` | `0.08` | assumed |
| `arb_gross_return` | `0.015` | assumed |
| `arb_leg_fail_prob` | `0.05` | assumed |
| `arb_per_day` | `1` | assumed |
| `basis_capital_per_position` | `20000` | measured (basis_paper_state.json) |
| `basis_daily_vol` | `0.120395` | measured (hyperliquid_data.db, para:ANSEM, XPL, 69h) |
| `basis_funding_apr` | `304.998` | measured (hyperliquid_data.db, para:ANSEM, XPL, 69h) - book entry APR 1478.2% |
| `basis_funding_autocorr` | `0.207365` | measured (hyperliquid_data.db, para:ANSEM, XPL, 69h) |
| `basis_funding_half_life_days` | `7` | assumed |
| `basis_funding_hourly_std` | `0.00062616` | measured (hyperliquid_data.db, para:ANSEM, XPL, 69h) |
| `basis_funding_long_run_apr` | `25` | assumed |
| `basis_leverage` | `1` | assumed |
| `basis_liquidation_cost` | `0.03` | assumed |
| `basis_positions` | `2` | measured (basis_paper_state.json) |
| `basis_rebalance_days` | `1` | assumed |
| `basis_tail_df` | `3` | assumed |
| `equity` | `100320` | measured (basis_paper_state.json) |
| `sports_bankroll_fraction` | `0.1` | assumed |
| `sports_bets_per_day` | `3` | assumed (< 20 settled wagers) |
| `sports_decimal_odds` | `2.4` | measured (sports_market.db edge_opportunities, 3 positive-Kelly rows) |
| `sports_kelly_fraction` | `0.25` | assumed |
| `sports_max_stake_fraction` | `0.02` | assumed |
| `sports_win_prob_mean` | `0.430556` | measured (sports_market.db edge_opportunities, 3 positive-Kelly rows) |
| `sports_win_prob_std` | `0` | measured (sports_market.db edge_opportunities, 3 positive-Kelly rows) |
| `stress_correlation` | `0.5` | override (cli) |
| `stress_day_prob` | `0.02` | assumed (< 14 days of marks) |
| `stress_vol_multiplier` | `3` | assumed (< 14 days of marks) |
| `tax_rate` | `0.3237` | measured (Tax_Reserve_Agent.config) |

---

## 🧭 Model Notes

1. **Basis**: the funding level starts at the book's measured mean and decays toward `basis_funding_long_run_apr` with half-life `basis_funding_half_life_days` (a para coin can print a four-digit APR for a day, not a year); hourly AR(1) noise (std and persistence from the snapshot DB) rides on top, so negative streaks occur. The short perp leg takes Student-t daily moves and is liquidated past `1/leverage - maintenance` before the next rebalance, costing a slice of the position's capital.
2. **Sports**: each wager draws a win probability, stakes the fractional Kelly of that edge at the offered odds (capped per wager), settles as a Bernoulli against a bankroll that is a fraction of equity.
3. **Arb**: Poisson arrivals; a leg failure leaves a naked leg losing a uniform slice, else the gross return is banked.
4. **Tax**: the composite rate of each quarter's positive net gain leaves the trading bankroll as escrow.
