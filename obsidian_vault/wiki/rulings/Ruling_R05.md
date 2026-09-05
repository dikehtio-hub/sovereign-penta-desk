---
type: Ruling
title: R5 - record the rewards pool rate (pending)
description: The AMM rewards estimator treats the daily pool rate as an ASSUMED input
  until a ruling records it from live markets. That ruling has not been issued; the
  module names it as the one input left.
tags:
- ruling
- desk-3
- r5
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:42Z'
status: draft
sources:
- id: agents-md
  resource: AGENTS.md
  title: DEV handoff log
  author: human:operator
dev:
  desk: 3
  ruling_id: R5
  asserts:
  - file: cross_market/amm_rewards.py
    pattern: Ruling R5
    claim: the module still names R5 as the pending ruling
---
# Ruling R5 - record the rewards pool rate (pending)

`cross_market/amm_rewards.py` prints "the pool rate is the only input left (Ruling R5)" and refuses `--replay-books` without `--pool`. Item 13 Phase 2 (record rewards fields additively in the fetcher, post-maiden) is the prerequisite. This page turns `stable` when the ruling is issued and the recording exists.

## Applies to

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_13_Polymarket_Automated_Market_Maker_Rewards_Bot|Item 13: Polymarket Automated Market Maker & Rewards Bot]]

## Provenance

- NOT ratified: no recorded text
