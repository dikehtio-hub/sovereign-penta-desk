---
type: Desk
title: 'Desk 2: Sports Desk'
description: 'Sportsbook desk: multi-book odds ingestion, Shin/Power devigging to
  fair value, after-tax edge hurdle, execution CLV, stale-quote guard and the Polymarket
  drop watcher that feeds Item 18.'
tags:
- desk
- desk-2
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T20:48:24Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
- id: round-95-blueprint
  resource: LLM_WIKI_BLUEPRINT.md
  title: Round 95 five-desk audit
  author: claude-code/fable-5.1
dev:
  desk: 2
  asserts:
  - file: Sports_Desk/engine/fair_value.py
    pattern: 'def '
    claim: the pure devigging engine is at its registered path
  parameters:
  - name: kelly_fraction
    value: 0.25
    file: Sports_Desk/engine/fair_value.py
    pattern: 'def kelly_fraction\(fair_prob: float, offered_odds: float, fraction:
      float = ([0-9.]+)\)'
---
# Desk 2: Sports Desk

Sportsbook desk: multi-book odds ingestion, Shin/Power devigging to fair value, after-tax edge hurdle, execution CLV, stale-quote guard and the Polymarket drop watcher that feeds Item 18.

**Domain**: Sportsbooks and Polymarket sports questions

## Code roots

- `Sports_Desk`

## Raw streams (federated, read-only)

- `Sports_Desk/data/sports_market.db (8 tables)`
- `Sports_Desk/data/polymarket_drops/ (stamped macro + sports JSON)`
- `Sports_Desk/data/odds_drops/, results_drops/`

## Vault surface (exporter-owned, never written by the knowledge layer)

- `Sports_Desk.md`

## Items

- [[Item_01_Sports_Odds_Ingestion_Fair_Value_No|Item 1: Sports Odds Ingestion & Fair-Value (No-Vig) Engine]] · deployed
- [[Item_05_Fractional_Kelly_Staking_Engine|Item 5: Fractional Kelly Staking Engine]] · deployed
- [[Item_07_Automated_Headless_Sports_Execution_Agent|Item 7: Automated Headless Sports Execution Agent]] · roadmap
- [[Item_15_Closing_Line_Value_CLV_Tracker_Soft|Item 15: Closing Line Value (Clv) Tracker & Soft-Book Health Monitor]] · deployed

## Rulings

- [[Ruling_R95|R95 - Ratification of the knowledge layer (R95-A to R95-G)]]

## Other desks

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Desk_04_Quant_Trading_Lab|Desk 4: Quant Trading Lab]]
- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]

## Related

- [[Monarch_Hub|Monarch Hub]] (exporter-owned dashboard index)
