---
type: Item
title: 'Item 1: Sports Odds Ingestion & Fair-Value (No-Vig) Engine'
description: Pulls multi-bookmaker odds (Pinnacle, Circa, retail books).
tags:
- item
- desk-2
- tier-1
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T20:05:15Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 2
  item: 1
  tier: 1
  registry_checked: true
  asserts:
  - file: Sports_Desk/engine/fair_value.py
    pattern: .
    claim: primary code present at the registered path
  - file: Sports_Desk/ingestors/odds_fetcher.py
    pattern: .
    claim: primary code present at the registered path
  - file: Sports_Desk/ingestors/odds_watcher.py
    pattern: .
    claim: primary code present at the registered path
---
# Item 1: Sports Odds Ingestion & Fair-Value (No-Vig) Engine

> Tier 1: Core Foundation & Risk Defense · deployed · [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]

## What it does

Pulls multi-bookmaker odds (Pinnacle, Circa, retail books). Strips
the bookmaker overround/vig using Shin's method, Power oracle, or closed-form
exact deduction to compute the true mathematical fair-value probability.

## Where it lives

- `Sports_Desk/engine/fair_value.py`
- `Sports_Desk/ingestors/odds_fetcher.py`
- `Sports_Desk/ingestors/odds_watcher.py`
- database: `Sports_Desk/data/sports_market.db`

## How to activate

```
# Ingest sample multi-bookmaker odds and compute no-vig fair value:
python -m Sports_Desk.ingestors.odds_fetcher --sample --run-watcher --hurdle-from-ledger
# Continuous polling with live feed (only drops/recalculates on price change):
python -m Sports_Desk.ingestors.odds_fetcher --watch --interval 300 --url <FEED_URL> --run-watcher --hurdle-from-ledger
```

## Test

```
python -m unittest Sports_Desk.tests.test_fair_value Sports_Desk.tests.test_odds_watcher
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline)

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
