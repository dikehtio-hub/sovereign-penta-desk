---
type: Item
title: 'Item 6: Cross-Market Arbitrage Engine (Polymarket Vs Sportsbooks)'
description: 'Matches sports event outcomes on Polymarket''s CLOB against sharp

  and retail sportsbook odds.'
tags:
- item
- desk-3
- tier-2
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:06Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 3
  item: 6
  tier: 2
  registry_checked: true
  requires_files:
  - cross_market/hybrid_arb.py
  - cross_market/matcher.py
  - cross_market/hud.py
  - Sports_Desk/interfaces/monarch_shark.py
---
# Item 6: Cross-Market Arbitrage Engine (Polymarket Vs Sportsbooks)

> Tier 2: Core Execution & Cross-Market Alpha · deployed · [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]

## What it does

Matches sports event outcomes on Polymarket's CLOB against sharp
and retail sportsbook odds. Evaluates dutched arbitrage under asymmetric tax
treatment (gambling loss relief vs capital gain offsets) with signed spread lines.

## Where it lives

- `cross_market/hybrid_arb.py`
- `cross_market/matcher.py`
- `cross_market/hud.py`
- `Sports_Desk/interfaces/monarch_shark.py`

## How to activate

```
# Run cross-market arbitrage scan between Polymarket and Sportsbooks:
python -m Sports_Desk.interfaces.monarch_shark --cross-market
# Check for desynchronized bets placed >3 days ago:
python -m Sports_Desk.interfaces.monarch_shark --check-sync
python -m Sports_Desk.interfaces.monarch_shark --reconcile   (alias)
# Export cleared cross-market fills to Tax Reserve Agent:
python -m Sports_Desk.interfaces.monarch_shark --export-to-tax-agent
```

## Test

```
python -m unittest cross_market.tests.test_hybrid_arb Sports_Desk.tests.test_arbitrage
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 22:29 EDT (Round 28)

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
