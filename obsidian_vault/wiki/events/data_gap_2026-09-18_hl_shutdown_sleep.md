---
type: Event
title: 'Data gap: 2026-09-18_hl_shutdown_sleep'
description: '15.88 h with no recording in asset_snapshots, liquidation_clusters:
  2026-09-18T04:13:04Z to 2026-09-18T20:05:57Z. Round 128.'
tags:
- event
- data-gap
- desk-1
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-18T20:20:00Z'
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
    start: '2026-09-18T04:13:04Z'
    end: '2026-09-18T20:05:57Z'
  gap_hours: 15.88
  tables:
  - asset_snapshots (no rows after the final poll at 04:13:04.254Z until 20:05:57.270Z,
    15.88 h; point-in-time polls, unrecoverable)
  - liquidation_clusters (no rows 04:13:04.777Z -> 20:05:57.877Z, 15.88 h; unrecoverable)
  - orderbook_snapshots (no rows 04:11:26.454Z -> 20:07:58.407Z, 15.94 h; unrecoverable)
  - 'trades (EFFECTIVELY EMPTY: 1,111 subscribe-time backfill rows strictly inside
    the interval against ~160,000 an hour live; unrecoverable)'
  - liquidation_events (0 rows 04:12:53.612Z -> 20:06:41.988Z; unrecoverable)
  - latest_snapshots (stale for the whole interval)
  cause: 'Planned operator night shutdown, run by Claude Code at the operator''s request.
    shutdown_all.bat at 00:13 EDT Thu 09-18: stop_file_observed 04:13:08.103Z, collector_stopped_by_operator
    (runtime 7,652.9 s since the 02:05Z restart), keep_awake_released, service_stop
    04:13:10.402Z, graceful=true forced=false, WAL checkpointed (0 bytes before and
    after). The script''s layer-2 and layer-3 stops (taskkill /FI WINDOWTITLE) matched
    nothing because every daemon runs as detached pythonw; the 8 survivors were stopped
    by PID at about 04:14Z (defect and fix ruling in AGENTS.md 09-18). The laptop
    slept at 04:52:21Z (Kernel-Power 42, 00:52 EDT), woke at 16:42:32Z (Kernel-General
    time sync and Kernel-Power 566 session transition, 12:42 EDT) and then sat awake
    with the pipeline down for 3.4 h until resume_all.bat at 16:05 EDT: service_start
    20:05:45.451Z pid 39344; first child 52288 restarted by the watchdog at 20:05:50.996Z
    (newest snapshot 952.8 min old, coverage 31.1 %), logged as collector_crashed_early
    exit 1 after 6.5 s; second child 47588 from 20:05:54.003Z. First new snapshot
    20:05:57.270Z; 448 assets in the last 30 s and 2,240 snapshot rows a minute at
    20:10Z.'
  affected_evaluations:
  - 'none registered: Phase 2 event 2 is the CPI print of 2026-10-14; the lead-lag
    price series restarts a new continuous segment from 20:05:57Z (exporter gate at
    20:06Z: NOT READY, span 0.0 h < 24 h, points 1 < 200; earliest READY 2026-09-19T20:06Z
    if nothing cuts it)'
  - 'passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions
    measured inside; their gates clear later by the gap length'
  - 'basis windows: overlapping windows are marked by their own coverage column'
  round: 128
  detected_utc: '2026-09-18T04:13:03Z'
  resolved_utc: '2026-09-18T20:05:57Z'
---
# Data gap: 2026-09-18_hl_shutdown_sleep

> **15.88 h with no recording** - 2026-09-18T04:13:04Z to 2026-09-18T20:05:57Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Planned operator night shutdown, run by Claude Code at the operator's request. shutdown_all.bat at 00:13 EDT Thu 09-18: stop_file_observed 04:13:08.103Z, collector_stopped_by_operator (runtime 7,652.9 s since the 02:05Z restart), keep_awake_released, service_stop 04:13:10.402Z, graceful=true forced=false, WAL checkpointed (0 bytes before and after). The script's layer-2 and layer-3 stops (taskkill /FI WINDOWTITLE) matched nothing because every daemon runs as detached pythonw; the 8 survivors were stopped by PID at about 04:14Z (defect and fix ruling in AGENTS.md 09-18). The laptop slept at 04:52:21Z (Kernel-Power 42, 00:52 EDT), woke at 16:42:32Z (Kernel-General time sync and Kernel-Power 566 session transition, 12:42 EDT) and then sat awake with the pipeline down for 3.4 h until resume_all.bat at 16:05 EDT: service_start 20:05:45.451Z pid 39344; first child 52288 restarted by the watchdog at 20:05:50.996Z (newest snapshot 952.8 min old, coverage 31.1 %), logged as collector_crashed_early exit 1 after 6.5 s; second child 47588 from 20:05:54.003Z. First new snapshot 20:05:57.270Z; 448 assets in the last 30 s and 2,240 snapshot rows a minute at 20:10Z.

## Streams affected

- asset_snapshots (no rows after the final poll at 04:13:04.254Z until 20:05:57.270Z, 15.88 h; point-in-time polls, unrecoverable)
- liquidation_clusters (no rows 04:13:04.777Z -> 20:05:57.877Z, 15.88 h; unrecoverable)
- orderbook_snapshots (no rows 04:11:26.454Z -> 20:07:58.407Z, 15.94 h; unrecoverable)
- trades (EFFECTIVELY EMPTY: 1,111 subscribe-time backfill rows strictly inside the interval against ~160,000 an hour live; unrecoverable)
- liquidation_events (0 rows 04:12:53.612Z -> 20:06:41.988Z; unrecoverable)
- latest_snapshots (stale for the whole interval)

## Evaluations that touch this interval

- none registered: Phase 2 event 2 is the CPI print of 2026-10-14; the lead-lag price series restarts a new continuous segment from 20:05:57Z (exporter gate at 20:06Z: NOT READY, span 0.0 h < 24 h, points 1 < 200; earliest READY 2026-09-19T20:06Z if nothing cuts it)
- passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions measured inside; their gates clear later by the gap length
- basis windows: overlapping windows are marked by their own coverage column

## Detection and resolution

- detected 2026-09-18T04:13:03Z; resolved 2026-09-18T20:05:57Z
- resume_all.bat 09-18 16:05 EDT run by Claude Code: collector/supervisor RUNNING pid 39344 (child 47588), Polymarket watcher pid 57524, cross-market exporter pid 54828, telemetry 5/5 (hyperliquid 56652, polymarket 60824, tax 50012, sports 56964, quantlab 49636).

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
