---
type: Event
title: 'Data gap: 2026-09-18_hl_reboot'
description: '0.66 h with no recording in asset_snapshots, liquidation_clusters: 2026-09-18T01:25:47Z
  to 2026-09-18T02:05:37Z. Round 128.'
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
    start: '2026-09-18T01:25:47Z'
    end: '2026-09-18T02:05:37Z'
  gap_hours: 0.66
  tables:
  - asset_snapshots (no rows 01:25:47.385Z -> 02:05:37.218Z, 0.66 h; unrecoverable)
  - liquidation_clusters (no rows 01:25:48.670Z -> 02:05:37.451Z, 0.66 h; unrecoverable)
  - orderbook_snapshots (no rows 01:24:59.290Z -> 02:07:37.931Z, 0.71 h; unrecoverable)
  - 'trades (PARTIAL: 4,901 rows between the last snapshot and the 02:05:27Z restart
    against ~160,000 an hour live - the ~4 minutes of live feed before the 01:30Z
    reboot plus the subscribe-time backfill; the ~35 minutes in between are effectively
    empty; unrecoverable)'
  - liquidation_events (10 rows 01:27:38.949Z -> 02:05:27.169Z; effectively empty;
    unrecoverable)
  - latest_snapshots (stale for the interval)
  cause: 'Windows REBOOT, not a sleep, at 21:30 EDT Wed 09-17: EventLog 6006 service
    stopped 01:30:07Z, Kernel-Power 109 shutdown transition 01:30:12Z, LastBootUpTime
    01:30:28Z, EventLog 6005 service started 01:30:49Z. No User32 1074 line names
    an initiator, so whether this was a manual restart or Windows Update is not in
    the System log - operator to say. The supervisor (pid 10968, running since 19:25Z)
    died with the reboot with no service_stop line; its last coverage_report was 01:25:30Z.
    resume_all.bat at 22:05 EDT: service_start 02:05:27.826Z pid 20396; first child
    11312 restarted by the watchdog 4 s later (newest snapshot 39.7 min old), second
    child 23252 from 02:05:35Z until the 04:13Z operator stop. First new snapshot
    02:05:37.218Z. Not registered on the day; found 09-18 16:00 EDT.'
  affected_evaluations:
  - 'none registered: the lead-lag segment that began 19:25:19Z was 6.0 h long when
    cut, short of the 24 h the exporter gate needs; a new segment starts 02:05:37Z
    and is itself cut at 04:13:04Z by 2026-09-18_hl_shutdown_sleep'
  round: 128
  detected_utc: '2026-09-18T20:15:00Z'
  resolved_utc: '2026-09-18T02:05:37Z'
---
# Data gap: 2026-09-18_hl_reboot

> **0.66 h with no recording** - 2026-09-18T01:25:47Z to 2026-09-18T02:05:37Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Windows REBOOT, not a sleep, at 21:30 EDT Wed 09-17: EventLog 6006 service stopped 01:30:07Z, Kernel-Power 109 shutdown transition 01:30:12Z, LastBootUpTime 01:30:28Z, EventLog 6005 service started 01:30:49Z. No User32 1074 line names an initiator, so whether this was a manual restart or Windows Update is not in the System log - operator to say. The supervisor (pid 10968, running since 19:25Z) died with the reboot with no service_stop line; its last coverage_report was 01:25:30Z. resume_all.bat at 22:05 EDT: service_start 02:05:27.826Z pid 20396; first child 11312 restarted by the watchdog 4 s later (newest snapshot 39.7 min old), second child 23252 from 02:05:35Z until the 04:13Z operator stop. First new snapshot 02:05:37.218Z. Not registered on the day; found 09-18 16:00 EDT.

## Streams affected

- asset_snapshots (no rows 01:25:47.385Z -> 02:05:37.218Z, 0.66 h; unrecoverable)
- liquidation_clusters (no rows 01:25:48.670Z -> 02:05:37.451Z, 0.66 h; unrecoverable)
- orderbook_snapshots (no rows 01:24:59.290Z -> 02:07:37.931Z, 0.71 h; unrecoverable)
- trades (PARTIAL: 4,901 rows between the last snapshot and the 02:05:27Z restart against ~160,000 an hour live - the ~4 minutes of live feed before the 01:30Z reboot plus the subscribe-time backfill; the ~35 minutes in between are effectively empty; unrecoverable)
- liquidation_events (10 rows 01:27:38.949Z -> 02:05:27.169Z; effectively empty; unrecoverable)
- latest_snapshots (stale for the interval)

## Evaluations that touch this interval

- none registered: the lead-lag segment that began 19:25:19Z was 6.0 h long when cut, short of the 24 h the exporter gate needs; a new segment starts 02:05:37Z and is itself cut at 04:13:04Z by 2026-09-18_hl_shutdown_sleep

## Detection and resolution

- detected 2026-09-18T20:15:00Z; resolved 2026-09-18T02:05:37Z
- resume_all.bat 09-17 22:05 EDT (operator). Registered retroactively 09-18 by Claude Code.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
