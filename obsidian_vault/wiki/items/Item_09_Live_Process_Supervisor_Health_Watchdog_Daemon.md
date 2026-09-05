---
type: Item
title: 'Item 9: Live Process Supervisor & Health Watchdog Daemon'
description: 'Robust process daemon managing the 24/7 background collector.

  Holds Windows OS keep-awake flags (ES_CONTINUOUS | ES_SYSTEM_REQUIRED), tracks

  coverage every 15 minutes, auto-restarts failed children with backoff, and

  isolates crashes.'
tags:
- item
- desk-1
- tier-2
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
  item: 9
  tier: 2
  registry_checked: true
  requires_files:
  - HyperLiquid/HL_Monarch/run_collector_service.py
---
# Item 9: Live Process Supervisor & Health Watchdog Daemon

> Tier 2: Core Execution & Cross-Market Alpha · deployed · [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]

## What it does

Robust process daemon managing the 24/7 background collector.
Holds Windows OS keep-awake flags (ES_CONTINUOUS | ES_SYSTEM_REQUIRED), tracks
coverage every 15 minutes, auto-restarts failed children with backoff, and
isolates crashes.

## Where it lives

- `HyperLiquid/HL_Monarch/run_collector_service.py`

## How to activate

```
# Launch 24/7 supervisor and collector service:
cmd /c "C:\Users\ixis1\Desktop\DEV\HyperLiquid\HL_Monarch\scripts\launchers\start_collector.bat"
# Gracefully terminate service and collector:
cmd /c "C:\Users\ixis1\Desktop\DEV\HyperLiquid\HL_Monarch\scripts\launchers\stop_collector.bat"
```

## Test

```
python -m pytest HyperLiquid/HL_Monarch/tests/test_dashboard_service_mode.py -q
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L; detached supervisor Round 53: 2026-09-04 21:09 EDT, watchdog Round 54: 2026-09-04 21:41 EDT)

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
