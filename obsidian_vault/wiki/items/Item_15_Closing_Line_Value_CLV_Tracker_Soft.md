---
type: Item
title: 'Item 15: Closing Line Value (Clv) Tracker & Soft-Book Health Monitor'
description: 'Measures achieved execution odds against Pinnacle closing lines

  to verify true mathematical edge.'
tags:
- item
- desk-2
- tier-3
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
  item: 15
  tier: 3
  registry_checked: true
  asserts:
  - file: Sports_Desk/interfaces/monarch_shark.py
    pattern: .
    claim: primary code present at the registered path
---
# Item 15: Closing Line Value (Clv) Tracker & Soft-Book Health Monitor

> Tier 3: Edge Refinement & Trading Lab Scaling · deployed · [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]

## What it does

Measures achieved execution odds against Pinnacle closing lines
to verify true mathematical edge. Drops odds snapshots into sports_market.db
with staleness filters and displays CLV distribution in terminal HUD.

## Where it lives

- `Sports_Desk/engine/clv_tracker.py`
- `Sports_Desk/interfaces/monarch_shark.py`

## How to activate

```
# Display CLV metrics and performance against the closing line:
python -m Sports_Desk.interfaces.monarch_shark --clv
```

## Test

```
python -m unittest Sports_Desk.tests.test_results_watcher
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline)

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
