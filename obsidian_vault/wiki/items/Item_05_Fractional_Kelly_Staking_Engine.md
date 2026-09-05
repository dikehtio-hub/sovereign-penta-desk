---
type: Item
title: 'Item 5: Fractional Kelly Staking Engine'
description: 'Dynamic bet sizing engine implementing Quarter-Kelly staking

  scaled against the net after-tax hurdle rate.'
tags:
- item
- desk-2
- tier-1
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:52:42Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 2
  item: 5
  tier: 1
  registry_checked: true
  requires_files:
  - Sports_Desk/engine/fair_value.py
  - Tax_Reserve_Agent/interfaces/monarch_hook.py
---
# Item 5: Fractional Kelly Staking Engine

> Tier 1: Core Foundation & Risk Defense · deployed · [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]

## What it does

Dynamic bet sizing engine implementing Quarter-Kelly staking
scaled against the net after-tax hurdle rate. Enforces strict 1-game 1-position
risk limits (e.g. Chiefs ML and Chiefs -3.5 share one aggregate exposure cap).

## Where it lives

- `Sports_Desk/engine/fair_value.py`
- `Tax_Reserve_Agent/interfaces/monarch_hook.py`

## How to activate

```
# Integrated inside the Sports CLI and odds watcher:
python -m Sports_Desk.interfaces.monarch_shark --performance
```

## Test

```
python -m unittest Sports_Desk.tests.test_fair_value
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline)

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
