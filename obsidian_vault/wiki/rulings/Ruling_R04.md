---
type: Ruling
title: R4 - neg_risk books skip the NO side
description: On a negative-risk Polymarket book only the winning outcome's YES asks
  are lifted; a NO outcome on a neg_risk book is deferred to Phase 2 and never traded
  by the sniper.
tags:
- ruling
- desk-3
- r4
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:42Z'
status: stable
verified:
- by: antigravity/architect
  at: '2026-09-05T17:15:05Z'
sources:
- id: agents-md
  resource: AGENTS.md
  title: DEV handoff log
  author: human:operator
- id: commit-da48cf3
  resource: git:da48cf3
  title: commit da48cf3
dev:
  desk: 3
  ruling_id: R4
  round: 88
  asserts:
  - file: cross_market/latency_sniper.py
    pattern: neg_risk
    claim: the neg_risk field is read and acted on
---
# Ruling R4 - neg_risk books skip the NO side

Implemented in Round 88: `Book` carries `neg_risk` from the live stamp's field; `evaluate()` skips a NO outcome on a neg_risk book with the reason "NO side deferred to Phase 2 (Ruling R4)" and still lifts the winning outcome's YES asks. A standalone market's NO side is unchanged. The depth report and the survival curve inherit the rule. Enforced in code, not in prose.

## Applies to

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]

## Provenance

- Round 88, commit `da48cf3`
- ratified by Antigravity
