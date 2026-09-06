---
type: Item
title: 'Item 20: Sovereign Master Cockpit Ui (War Room Dashboard & Canvas)'
description: 'Real-time visual interface rendering the entire penta-desk

  ecosystem.'
tags:
- item
- desk-1
- tier-4
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
  desk: 1
  item: 20
  tier: 4
  registry_checked: true
  requires_files:
  - HyperLiquid/HL_Monarch/ui/terminal_dashboard.py
---
# Item 20: Sovereign Master Cockpit Ui (War Room Dashboard & Canvas)

> Tier 4: Analytics, Optimization & Master Cockpit · deployed · [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]

## What it does

Real-time visual interface rendering the entire penta-desk
ecosystem. Provided across two synchronized channels:
1. Rich Read-Only Terminal Dashboard: Displays collector PID, service mode,
novel-dex badges, L2 candidate rotation, and real-time funding yield.
2. Obsidian Penta-Desk Canvas: Visual multi-card cockpit displaying all 5
desk markdown summaries around the central Tax Reserve escrow node.

## Where it lives

- `HyperLiquid/HL_Monarch/ui/terminal_dashboard.py`
- `HyperLiquid/HL_Monarch/exporters/obsidian_exporter.py`

## How to activate

```
# Launch terminal dashboard:
python HyperLiquid/HL_Monarch/main.py dashboard
# Refresh all Obsidian cockpit cards on demand:
python HyperLiquid/HL_Monarch/main.py obsidian --once
```

## Test

```
python -m pytest HyperLiquid/HL_Monarch/tests/test_dashboard_service_mode.py -q
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline; Canvas Round 34: 2026-09-04 11:20 EDT, Read-only Round 36: 2026-09-04 12:23 EDT)

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
