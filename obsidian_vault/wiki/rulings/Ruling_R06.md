---
type: Ruling
title: R6 - competitor Q is measured from recorded books
description: The programme score of every resting level inside the rewards window
  is computed from a recorded CLOB stamp; competitor liquidity is a measurement, not
  an input. The pool rate stays the one input (R5).
tags:
- ruling
- desk-3
- r6
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:42Z'
status: stable
verified:
- by: antigravity/architect
  at: '2026-09-05T17:48:20Z'
sources:
- id: agents-md
  resource: AGENTS.md
  title: DEV handoff log
  author: human:operator
- id: commit-fe40a1a
  resource: git:fe40a1a
  title: commit fe40a1a
dev:
  desk: 3
  ruling_id: R6
  round: 91
  asserts:
  - file: cross_market/amm_rewards.py
    pattern: def book_q
    claim: book_q exists
---
# Ruling R6 - competitor Q is measured from recorded books

Implemented in Round 91: `amm_rewards.book_q()` scores each level per side (Q_min by the band rule); `replay_rewards()` runs it over a stamps folder and adds the share a hypothetical two-sided quote would earn. First measurement (Fed "no change in Sept 2026", one stamp at 16:59Z): Q_min 28,828 over 6 levels in the 3-cent window; a 100-share quote at +/-1 cent earns a 0.09 % share. Retail-sized quoting on a heavily-made market is a rounding error of the pool, and the module says so rather than an APY.

## Applies to

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_13_Polymarket_Automated_Market_Maker_Rewards_Bot|Item 13: Polymarket Automated Market Maker & Rewards Bot]]

## Provenance

- Round 91, commit `fe40a1a`
- ratified by Antigravity
