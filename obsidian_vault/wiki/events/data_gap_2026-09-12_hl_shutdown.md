---
type: Event
title: 'Data gap: 2026-09-12_hl_shutdown'
description: '9.57 h with no recording in asset_snapshots, liquidation_events: 2026-09-12T05:46:48Z
  to 2026-09-12T15:21:06Z. Round 127.'
tags:
- event
- data-gap
- desk-1
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-12T15:59:45Z'
status: draft
sources:
- id: gaps
  resource: knowledge/data_gaps.json
  title: data_gaps.json
  author: human:operator
dev:
  kind: data_gap
  desk: 1
  window:
    start: '2026-09-12T05:46:48Z'
    end: '2026-09-12T15:21:06Z'
  gap_hours: 9.57
  tables:
  - asset_snapshots (no rows 05:49:29Z -> 15:21:06Z, 9.53 h; point-in-time polls,
    unrecoverable)
  - liquidation_events (no rows 05:46:48Z -> 15:20:53Z, 9.57 h; unrecoverable)
  - 'trades (LARGELY RECOVERED: exchange-side timestamps let the collector backfill
    on resume, so the residual gap is only 05:49:36Z -> 06:58:22Z, 1.15 h. The backfill
    reached back to ~06:58 and no further, consistent with an API lookback limit)'
  - latest_snapshots (stale for the whole interval)
  - 'cascade_excursions (NOT part of this event: its largest nearby gap is 04:08:21Z
    -> 04:57:13Z, 0.81 h, which predates the shutdown)'
  cause: 'Planned overnight shutdown, taken deliberately after confirming the autoresearch
    campaign reads only historical archive data and so was unaffected. The collector
    supervisor and its child were stopped and the machine powered off; resume_all.bat
    brought the pipeline back at 11:21 EDT (supervisor pid 54884, collector 88176).
    This was the first shutdown after run_collector_service.py gained a --stop flag
    (commit ca02ca7): the WAL was checkpointed and the sentinel cleaned up, though
    the then-running supervisor predated the sentinel and so took the forced path,
    exactly as that commit predicted.'
  affected_evaluations:
  - 'none registered: Campaign 4 autoresearch reads data/continuous (historical Binance
    archive, research span ends 2026-09-01) and is not fed by this collector'
  - Item 18 Phase 2 needs the 09-16 window, which is unaffected
  round: 127
  detected_utc: '2026-09-12T15:22:00Z'
  resolved_utc: '2026-09-12T15:21:06Z'
---
# Data gap: 2026-09-12_hl_shutdown

> **9.57 h with no recording** - 2026-09-12T05:46:48Z to 2026-09-12T15:21:06Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Planned overnight shutdown, taken deliberately after confirming the autoresearch campaign reads only historical archive data and so was unaffected. The collector supervisor and its child were stopped and the machine powered off; resume_all.bat brought the pipeline back at 11:21 EDT (supervisor pid 54884, collector 88176). This was the first shutdown after run_collector_service.py gained a --stop flag (commit ca02ca7): the WAL was checkpointed and the sentinel cleaned up, though the then-running supervisor predated the sentinel and so took the forced path, exactly as that commit predicted.

## Streams affected

- asset_snapshots (no rows 05:49:29Z -> 15:21:06Z, 9.53 h; point-in-time polls, unrecoverable)
- liquidation_events (no rows 05:46:48Z -> 15:20:53Z, 9.57 h; unrecoverable)
- trades (LARGELY RECOVERED: exchange-side timestamps let the collector backfill on resume, so the residual gap is only 05:49:36Z -> 06:58:22Z, 1.15 h. The backfill reached back to ~06:58 and no further, consistent with an API lookback limit)
- latest_snapshots (stale for the whole interval)
- cascade_excursions (NOT part of this event: its largest nearby gap is 04:08:21Z -> 04:57:13Z, 0.81 h, which predates the shutdown)

## Evaluations that touch this interval

- none registered: Campaign 4 autoresearch reads data/continuous (historical Binance archive, research span ends 2026-09-01) and is not fed by this collector
- Item 18 Phase 2 needs the 09-16 window, which is unaffected

## Detection and resolution

- detected 2026-09-12T15:22:00Z; resolved 2026-09-12T15:21:06Z
- resume_all.bat; supervisor RUNNING pid 54884 with child 88176; --status confirmed running:true after a brief startup race in which the pid lock was not yet held. Trades partially self-healed by backfill; snapshots and liquidations did not and cannot.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
