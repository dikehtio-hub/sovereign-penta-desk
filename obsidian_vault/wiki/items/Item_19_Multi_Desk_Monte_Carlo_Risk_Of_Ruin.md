---
type: Item
title: 'Item 19: Multi-Desk Monte Carlo Risk-Of-Ruin Simulator'
description: '100,000-path joint simulation of the trading bankroll across the basis
  book

  (funding level decaying from the measured mean toward a long-run APR, hourly AR(1)
  noise,

  Student-t perp moves, liquidation past 1/leverage - maintenance), quarter-Kelly
  sports

  wagers on the desk''s edge distribution, Poisson'
tags:
- item
- desk-3
- tier-4
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:42Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 3
  item: 19
  tier: 4
  registry_checked: true
---
# Item 19: Multi-Desk Monte Carlo Risk-Of-Ruin Simulator

> Tier 4: Analytics, Optimization & Master Cockpit · deployed · [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]

## What it does

100,000-path joint simulation of the trading bankroll across the basis book
(funding level decaying from the measured mean toward a long-run APR, hourly AR(1) noise,
Student-t perp moves, liquidation past 1/leverage - maintenance), quarter-Kelly sports
wagers on the desk's edge distribution, Poisson cross-market arbs with leg failures, and
quarterly tax escrow (NJ 32.37% composite). Reports hard ruin (equity <= 0) and practical
ruin (-50% drawdown), max-drawdown VaR 95/99 at 30 d and 365 d, terminal equity, per-desk
P&L, a cross-desk Kelly shrinkage grid (max median log growth s.t. practical ruin <= 5% and
allocation <= 100%) with its binding constraint, and a cash buffer (VaR99 drawdown).

## Status

[DEPLOYED Round 58 — 2026-09-04 23:21 EDT] cross_market/risk_simulator.py; card obsidian_vault/Risk_Sentinel.md

Added: 2026-09-04 23:21 EDT (Round 58 Deployed)

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
