---
type: Digest
title: Round 58 digest
description: 'Round 58: ITEM 19 MULTI-DESK MONTE CARLO RISK-OF-RUIN SIMULATOR'
tags:
- digest
- work-chain
- round-58
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-58-complete
  title: AGENTS.md - Round 58 complete
  author: claude-code/fable-5.1
dev:
  round: 58
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 58 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 58 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

ITEM 19 MULTI-DESK MONTE CARLO RISK-OF-RUIN SIMULATOR.

cross_market/risk_simulator.py runs one joint numpy simulation of the trading
bankroll across the basis book (funding level decaying from the measured mean
toward a long-run APR, hourly AR(1) noise, Student-t perp moves, liquidation
past 1/leverage - maintenance), quarter-Kelly sports wagers, Poisson arb
arrivals with leg failures, and quarterly tax escrow (NJ 32.37%). 100,000
paths x 365 d in ~10 s (only running equity / peak / drawdown are kept).
Reports hard ruin (equity <= 0) AND practical ruin (-50% drawdown), max-
drawdown VaR 95/99 at 30 d and the horizon, terminal equity, escrow, per-desk
P&L, and a Kelly shrinkage grid (max median log growth s.t. practical ruin
<= 5% and allocation <= 100%) with the binding constraint named. Inputs are
measured from basis_paper_state.json, hyperliquid_data.db (funding mean/std/
persistence, realized vol of the held coins), sports_market.db edge rows and
Tax_Reserve_Agent.config, else labelled assumed. CLI --iterations/--json/
--inputs/--assume-defaults/--no-grid/--no-vault; writes
obsidian_vault/Risk_Sentinel.md. 12 tests; master suite is 17 modules now.

## Related

- [[digests_register|Digests register]]
