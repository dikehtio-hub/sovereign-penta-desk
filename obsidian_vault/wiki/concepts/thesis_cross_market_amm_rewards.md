---
type: Concept
title: 'Thesis: cross_market/amm_rewards.py'
description: 'A maker resting a bid and an ask around fair value earns the spread
  on retail fills and, on markets with a rewards programme, a share of a daily USDC
  pool scored by how close and how large its orders rest. The roadmap''s "20-40% APY"
  is unmeasured: it depends on pool sizes and on …'
tags:
- concept
- thesis
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: cross_market/amm_rewards.py
  title: cross_market/amm_rewards.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: cross_market/amm_rewards.py
  headings:
  - THE THESIS
  - WHAT THIS PHASE DOES
  asserts:
  - file: cross_market/amm_rewards.py
    pattern: THE\ THESIS
    claim: the docstring still carries the section 'THE THESIS'
  - file: cross_market/amm_rewards.py
    pattern: WHAT\ THIS\ PHASE\ DOES
    claim: the docstring still carries the section 'WHAT THIS PHASE DOES'
  requires_files:
  - cross_market/amm_rewards.py
  desk: 3
---
# Thesis: cross_market/amm_rewards.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Thesis

A maker resting a bid and an ask around fair value earns the spread on retail fills and, on markets with a rewards programme, a share of a daily USDC pool scored by how close and how large its orders rest. The roadmap's "20-40% APY" is unmeasured: it depends on pool sizes and on how much competing liquidity shares the pool, and this module takes both as INPUTS. It can say "if the pool is X and the competition Y, the reward is Z"; it cannot say what X and Y are.

## What This Phase Does

1. Quotes: Avellaneda-Stoikov shading. Reservation price r = fair - q*gamma*sigma^2*tau (long inventory shades both quotes down), half-spread from the risk term plus the fill-intensity term, clamped to the tick grid inside (0, 1), and optionally pulled inside the rewards window so both orders score. 2. Rewards: the programme's order score ((v - s) / v)^2 * size for an order resting s from the midpoint inside the max spread v with at least the min size; both sides are needed in the 0.10-0.90 band (Q_min), one side suffices outside it; the daily pool is shared by Q share against competitor liquidity. 3. Simulation: per-minute loop over a fair-value path; retail fills arrive Poisson with intensity A*exp(-k*distance); inventory, cash, spread PnL, mark-to-market and rewards accrue; results carry every assumption that produced them. 4. Guardrails, fail-closed: HALT.flag refuses; an inventory limit makes quoting one-sided (only the reducing side); a volatility spike widens, a larger one pulls; an event window pulls; every pulled minute is counted with its reason. 5. Fills are PAPER receipts (strategy polymarket_amm) under cross_market/data/paper_receipts. No live path exists.

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
