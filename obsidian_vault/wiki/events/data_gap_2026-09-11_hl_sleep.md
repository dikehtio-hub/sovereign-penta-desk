---
type: Event
title: 'Data gap: 2026-09-11_hl_sleep'
description: '10.75 h with no recording in asset_snapshots, trades: 2026-09-11T05:43:07Z
  to 2026-09-11T16:27:59Z. Round 127.'
tags:
- event
- data-gap
- desk-1
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-11T16:31:20Z'
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
    start: '2026-09-11T05:43:07Z'
    end: '2026-09-11T16:27:59Z'
  gap_hours: 10.75
  tables:
  - asset_snapshots (no rows 05:43:07.623Z -> 16:27:59.397Z, 10.75 h)
  - trades (WebSocket silent 05:43:14Z -> 12:49Z, 7.1 h; then a modern-standby trickle
    of 5-42 prints/h until 16:20:43Z; largest gaps 25,573 s, 1,680 s, 1,392 s)
  - latest_snapshots (stale for the whole interval)
  - cascade_excursions / basis_realised_windows (no forward measurements inside; overlapping
    basis windows carry their coverage column)
  cause: 'The laptop entered sleep at 2026-09-11 01:43:25 EDT (Kernel-Power 42 after
    a user-mode SetSuspendState call at 01:43:23 - lid or power menu) and returned
    from low power at 12:21:50 EDT (Kernel-Power 1). Every daemon died with it: supervisor,
    collector, watcher, exporter, all five telemetry exporters (telemetry_health 0/5
    at 12:24). The machine was not rebooted (last boot 09-04). resume_all.bat relaunched
    everything at 12:27:53 EDT (watcher 31600, exporter 69348). No 24 h series was
    accumulating (Item 18 Phase 1 closed 09-10; Phase 2 needs only the 09-16 window),
    so no registered evaluation is affected - the first sleep gap since the standing
    keep-awake rule, taken while nothing was owed. Round 127 (pre-round).'
  affected_evaluations:
  - 'none registered: no lead-lag window was open; the Phase 2 event study reads only
    [T-60 min, T+300 s] around 2026-09-16T18:00Z'
  - 'passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions
    measured inside; their gates clear later by the gap length'
  - 'basis windows: overlapping windows are marked by their own coverage column'
  round: 127
  detected_utc: '2026-09-11T16:24:00Z'
  resolved_utc: '2026-09-11T16:27:59Z'
---
# Data gap: 2026-09-11_hl_sleep

> **10.75 h with no recording** - 2026-09-11T05:43:07Z to 2026-09-11T16:27:59Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

The laptop entered sleep at 2026-09-11 01:43:25 EDT (Kernel-Power 42 after a user-mode SetSuspendState call at 01:43:23 - lid or power menu) and returned from low power at 12:21:50 EDT (Kernel-Power 1). Every daemon died with it: supervisor, collector, watcher, exporter, all five telemetry exporters (telemetry_health 0/5 at 12:24). The machine was not rebooted (last boot 09-04). resume_all.bat relaunched everything at 12:27:53 EDT (watcher 31600, exporter 69348). No 24 h series was accumulating (Item 18 Phase 1 closed 09-10; Phase 2 needs only the 09-16 window), so no registered evaluation is affected - the first sleep gap since the standing keep-awake rule, taken while nothing was owed. Round 127 (pre-round).

## Streams affected

- asset_snapshots (no rows 05:43:07.623Z -> 16:27:59.397Z, 10.75 h)
- trades (WebSocket silent 05:43:14Z -> 12:49Z, 7.1 h; then a modern-standby trickle of 5-42 prints/h until 16:20:43Z; largest gaps 25,573 s, 1,680 s, 1,392 s)
- latest_snapshots (stale for the whole interval)
- cascade_excursions / basis_realised_windows (no forward measurements inside; overlapping basis windows carry their coverage column)

## Evaluations that touch this interval

- none registered: no lead-lag window was open; the Phase 2 event study reads only [T-60 min, T+300 s] around 2026-09-16T18:00Z
- passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions measured inside; their gates clear later by the gap length
- basis windows: overlapping windows are marked by their own coverage column

## Detection and resolution

- detected 2026-09-11T16:24:00Z; resolved 2026-09-11T16:27:59Z
- resume_all.bat at 12:27:53 EDT; collector newest snapshot 0.0 min at 12:28; exporter and watcher RUNNING on fresh pids; telemetry 5/5. Nothing else touched (freeze approaching 09-15).

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
