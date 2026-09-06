---
title: Risk Sentinel - Multi-Desk Monte Carlo
tags:
  - risk
  - monte-carlo
  - risk-of-ruin
  - cross-market
  - dashboard
last_synced: "2026-09-06 00:42:57 UTC"
---

# 🛡 Risk Sentinel - Multi-Desk Monte Carlo (Item 19)

> [!SUCCESS] **Practical ruin (-50%) over 365d: `0.00%`** · hard ruin `0.000%`
> - **Last Synchronized**: `2026-09-06 00:42:57 UTC`
> - **Paths**: `20,000` × `365` days, seed `7`, start equity `$100,397.29`
> - **Buffer**: keep `$3,426` unallocated (VaR99 365d drawdown `3.4%`); size every desk at `x2.00`
> - Shell twin: `python -m cross_market.risk_simulator --iterations 20000 --json`

> **Cockpit Navigation**: [[Monarch_Hub|👑 Master Hub]] • [[HyperLiquid_Monarch|🏛 HyperLiquid]] • [[Sports_Desk|🏈 Sports Desk]] • [[Cross_Market_Arb|⚖️ Cross-Market Arb]] • [[Cross_Market_Titans|🌐 Titans]] • [[Bot_Config|⚙️ Bot Config]]

---

## 📉 Ruin & Drawdown

| Metric | 30d | 365d |
| :--- | :---: | :---: |
| Hard ruin P(equity ≤ 0) | `0.000%` | `0.000%` |
| Practical ruin P(drawdown ≥ 50%) | `0.00%` | `0.00%` |
| Max drawdown VaR 95 | `0.71%` | `2.82%` |
| Max drawdown VaR 99 | `1.13%` | `3.41%` |
| Median max drawdown | — | `1.95%` |

**Terminal equity** (365d): p05 `$105,896` · p50 `$109,090` · p95 `$112,307` · median log growth `+0.0830` · escrow median `$4,151`

**Desk mean P&L** (365d): basis `$6,087` · sports `$2,303` · arb `$4,461` · tax `-$4,161` · liquidations per path `0.154`

---

## 🎯 Cross-Desk Kelly Shrinkage

Multiplier on every desk's sizing (basis capital per position, sports Kelly fraction, arb capital); the recommendation maximises median log growth with practical ruin ≤ `5%` and the desks' capital fitting inside the equity (allocation ≤ 100%). Tax escrow leaves the trading bankroll and therefore counts as drawdown here.

| Multiplier | Median log growth | Practical ruin | Hard ruin | VaR95 365d | Allocation | |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `x0.25` | `+0.0212` | `0.00%` | `0.00%` | `0.7%` | `20%` |  |
| `x0.50` | `+0.0420` | `0.00%` | `0.00%` | `1.4%` | `30%` |  |
| `x0.75` | `+0.0624` | `0.00%` | `0.00%` | `2.1%` | `41%` |  |
| `x1.00` | `+0.0825` | `0.00%` | `0.00%` | `2.8%` | `51%` |  |
| `x1.25` | `+0.1023` | `0.00%` | `0.00%` | `3.5%` | `61%` |  |
| `x1.50` | `+0.1217` | `0.00%` | `0.00%` | `4.2%` | `71%` |  |
| `x2.00` | `+0.1596` | `0.00%` | `0.00%` | `5.5%` | `92%` | **recommended** |

**Binding constraint**: capital allocation - ruin never bound at any size that fits the equity, so the pick means 'risk is not the limit', not 'add leverage'.

---

## ⚡ Systemic Stress

Correlation `0.50`, shock-day probability `0.020` (`7.3` days per path), perp vol `x3.0` on shock days; sports wagers are unaffected (nothing links them to a crypto squeeze).

| Metric | Baseline | Stressed | Δ |
| :--- | :---: | :---: | :---: |
| VaR99 max drawdown 365d | `3.40%` | `3.41%` | `+0.01 pp` |
| VaR95 max drawdown 365d | `2.82%` | `2.82%` | `+0.00 pp` |
| Practical ruin 365d | `0.00%` | `0.00%` | `+0.00 pp` |
| Recommended cash buffer | `$3,413` | `$3,426` | `+13` |
| Basis desk P&L | `$6,237` | `$6,087` | `-150` |
| Arb desk P&L | `$4,471` | `$4,461` | `-10` |
| Liquidations per path | `0.136` | `0.154` | `+0.018` |

---

## 🧾 Inputs & Provenance

Desk 4 (Quant Trading Lab) is outside this simulation. `assumed` inputs have no live history yet.

| Input | Value | Provenance |
| :--- | :---: | :--- |
| `arb_capital` | `1000` | assumed (< 10 arb fills) |
| `arb_desync_loss_max` | `0.08` | assumed |
| `arb_gross_return` | `0.015` | assumed (< 10 arb fills) |
| `arb_leg_fail_prob` | `0.05` | assumed |
| `arb_per_day` | `1` | assumed (< 10 arb fills) |
| `arb_return_std` | `0.005` | assumed (< 10 arb fills) |
| `basis_capital_per_position` | `20000` | measured (basis_paper_state.json) |
| `basis_daily_vol` | `0.114344` | measured (hyperliquid_data.db, para:ANSEM, XPL, 90h) |
| `basis_funding_apr` | `264.438` | measured (hyperliquid_data.db, para:ANSEM, XPL, 90h) - book entry APR 1478.2% |
| `basis_funding_autocorr` | `0.206074` | measured (hyperliquid_data.db, para:ANSEM, XPL, 90h) |
| `basis_funding_half_life_days` | `7` | assumed |
| `basis_funding_hourly_std` | `0.000560597` | measured (hyperliquid_data.db, para:ANSEM, XPL, 90h) |
| `basis_funding_long_run_apr` | `25` | assumed |
| `basis_leverage` | `1` | assumed |
| `basis_liquidation_cost` | `0.03` | assumed |
| `basis_positions` | `2` | measured (basis_paper_state.json) |
| `basis_rebalance_days` | `1` | assumed |
| `basis_tail_df` | `3` | assumed |
| `equity` | `100397` | measured (basis_paper_state.json) |
| `sports_bankroll_fraction` | `0.1` | assumed |
| `sports_bets_per_day` | `3` | assumed (< 20 settled wagers) |
| `sports_decimal_odds` | `2.4` | measured (sports_market.db edge_opportunities, 3 positive-Kelly rows) |
| `sports_kelly_fraction` | `0.25` | assumed |
| `sports_max_stake_fraction` | `0.02` | assumed |
| `sports_win_prob_mean` | `0.430556` | measured (sports_market.db edge_opportunities, 3 positive-Kelly rows) |
| `sports_win_prob_std` | `0` | measured (sports_market.db edge_opportunities, 3 positive-Kelly rows) |
| `stress_correlation` | `0.5` | override (exporter) |
| `stress_day_prob` | `0.02` | assumed (< 14 days of marks) |
| `stress_vol_multiplier` | `3` | assumed (< 14 days of marks) |
| `tax_rate` | `0.3237` | measured (Tax_Reserve_Agent.config) |

---

## 🧭 Model Notes

1. **Basis**: the funding level starts at the book's measured mean and decays toward `basis_funding_long_run_apr` with half-life `basis_funding_half_life_days` (a para coin can print a four-digit APR for a day, not a year); hourly AR(1) noise (std and persistence from the snapshot DB) rides on top, so negative streaks occur. The short perp leg takes Student-t daily moves and is liquidated past `1/leverage - maintenance` before the next rebalance, costing a slice of the position's capital.
2. **Sports**: each wager draws a win probability, stakes the fractional Kelly of that edge at the offered odds (capped per wager), settles as a Bernoulli against a bankroll that is a fraction of equity.
3. **Arb**: Poisson arrivals; a leg failure leaves a naked leg losing a uniform slice, else the gross return is banked.
4. **Tax**: the composite rate of each quarter's positive net gain leaves the trading bankroll as escrow.
