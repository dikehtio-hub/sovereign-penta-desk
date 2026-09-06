---
type: Entity/Sportsbook
title: Sportsbook pinnacle
description: 'pinnacle: sharp book in the Sports Desk fair-value engine.'
tags:
- crm
- sportsbook
- desk-2
- sharp
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T04:51:55Z'
status: draft
sources:
- id: sports_market
  resource: Sports_Desk/data/sports_market.db
  title: sports_market.db edge_opportunities (mode=ro)
  author: process:Sports_Desk.odds_watcher
dev:
  desk: 2
  book: pinnacle
  role: sharp
  measurements: 32
  evidence: []
---
# Sportsbook pinnacle

## Identity

- book: **pinnacle**
- role in the fair-value engine: **sharp** (the devigged reference every edge is priced against)
- fair-odds measurements as reference: 32 · edges priced against it: 96

## Judgement

_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_

## Evidence (dated rows the adapter appends; never live state)

_(no evidence rows yet)_

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[Item_15_Closing_Line_Value_CLV_Tracker_Soft|Item 15: CLV tracker & soft-book health]]
- [[crm_register|CRM register]]
