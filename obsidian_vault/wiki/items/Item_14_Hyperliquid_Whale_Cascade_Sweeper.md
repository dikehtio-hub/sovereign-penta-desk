---
type: Item
title: 'Item 14: Hyperliquid Whale Cascade Sweeper'
description: Gated, non-trading passive accumulation module.
tags:
- item
- desk-1
- tier-3
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:19Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 1
  item: 14
  tier: 3
  registry_checked: true
  requires_files:
  - HyperLiquid/HL_Monarch/strategies/whale_sweeper.py
---
# Item 14: Hyperliquid Whale Cascade Sweeper

> Tier 3: Edge Refinement & Trading Lab Scaling · deployed · [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]

## What it does

Gated, non-trading passive accumulation module. Identifies large
whale liquidation clusters on HyperLiquid, measures adverse momentum excursions,
and logs cascade profiles to validate mean-reversion theses without risking capital.

## Where it lives

- `HyperLiquid/HL_Monarch/strategies/whale_sweeper.py`
- `HyperLiquid/HL_Monarch/analytics/excursions.py`

## Test

```
python -m pytest HyperLiquid/HL_Monarch/tests/test_whale_sweeper.py -q
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 23:03 EDT (Round 31 — built gated off)

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
