---
type: Entity/Sportsbook
title: Sportsbook betmgm
description: 'betmgm: soft book in the Sports Desk fair-value engine; 32 edges recorded
  across 3 sport/market-type cell(s).'
tags:
- crm
- sportsbook
- desk-2
- soft
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:50Z'
status: draft
sources:
- id: sports_market
  resource: Sports_Desk/data/sports_market.db
  title: sports_market.db edge_opportunities (mode=ro)
  author: process:Sports_Desk.odds_watcher
dev:
  desk: 2
  book: betmgm
  role: soft
  measurements: 0
  evidence:
  - sport: NFL
    market_type: moneyline
    edges: 12
    cleared: 0
    mean_gross_edge: -0.0399
    max_gross_edge: -0.0179
    first: '2026-09-04T04:01:42.621908+00:00'
    last: '2026-09-04T15:52:34.710038+00:00'
    at: '2026-09-04T15:52:34.710038+00:00'
---
# Sportsbook betmgm

## Identity

- book: **betmgm**
- role in the fair-value engine: **soft** (a retail book whose stale lines are the edge)
- fair-odds measurements as reference: 0

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

| at | sport | market_type | edges | cleared | mean_gross_edge | max_gross_edge | first |
|---|---|---|---|---|---|---|---|
| 2026-09-04T15:52:34.710038+00:00 | NFL | moneyline | 12 | 0 | -0.0399 | -0.0179 | 2026-09-04T04:01:42.621908+00:00 |

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[Item_15_Closing_Line_Value_CLV_Tracker_Soft|Item 15: CLV tracker & soft-book health]]
- [[crm_register|CRM register]]
