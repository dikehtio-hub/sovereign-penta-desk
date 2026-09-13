---
type: Event
title: 'Data gap: 2026-09-13_hl_sleep'
description: '9.0 h with no recording in asset_snapshots, liquidation_clusters: 2026-09-13T07:45:38Z
  to 2026-09-13T16:45:46Z. Round 128.'
tags:
- event
- data-gap
- desk-1
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-13T18:19:00Z'
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
    start: '2026-09-13T07:45:38Z'
    end: '2026-09-13T16:45:46Z'
  gap_hours: 9.0
  tables:
  - asset_snapshots (no rows 07:45:38Z -> 16:45:46Z, 9.00 h; point-in-time polls,
    unrecoverable)
  - liquidation_clusters (no rows 07:45:38Z -> 16:45:46Z, 9.00 h; unrecoverable)
  - orderbook_snapshots (no rows 07:45:29Z -> 16:47:58Z, 9.04 h; unrecoverable)
  - 'trades (EFFECTIVELY EMPTY: the subscribe-time backfill on resume delivered 998
    rows spread 09:04Z -> 16:44Z against a live rate of ~60,000 an hour, so the interval
    holds well under 1 % of what was traded; unrecoverable)'
  - liquidation_events (4 rows in the interval, 10:03Z and 14:27Z; effectively empty,
    unrecoverable)
  - latest_snapshots (stale for the whole interval)
  cause: Overnight sleep, not a shutdown. The operator ran shutdown_all.bat and then
    the machine entered sleep at 03:45:55 EDT (Kernel-Power 42; a lid close or power-menu
    sleep) - the same shape as 2026-09-11 - and resumed at 12:41 EDT. The collector's
    last persisted snapshot was 03:45:40 EDT (07:45:38Z). resume_all.bat at 12:45
    EDT relaunched the supervisor (pid 83292, service_start 16:45:43Z); its first
    child (42868) was restarted 8 s later by the silent-failure watchdog, which saw
    the 9-hour-old newest snapshot before the first new one landed, and the second
    child (64720) has run since. First new snapshot 16:45:46Z.
  affected_evaluations:
  - 'none registered: the FOMC drill of 2026-09-16 has not run; the Item 18 lead-lag
    price series restarts a new continuous segment from 16:45:46Z (exporter ETA 2026-09-14T16:45Z),
    which the two-stream gate will report on any future unbounded check'
  round: 128
  detected_utc: '2026-09-13T16:50:00Z'
  resolved_utc: '2026-09-13T16:45:46Z'
---
# Data gap: 2026-09-13_hl_sleep

> **9.0 h with no recording** - 2026-09-13T07:45:38Z to 2026-09-13T16:45:46Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Overnight sleep, not a shutdown. The operator ran shutdown_all.bat and then the machine entered sleep at 03:45:55 EDT (Kernel-Power 42; a lid close or power-menu sleep) - the same shape as 2026-09-11 - and resumed at 12:41 EDT. The collector's last persisted snapshot was 03:45:40 EDT (07:45:38Z). resume_all.bat at 12:45 EDT relaunched the supervisor (pid 83292, service_start 16:45:43Z); its first child (42868) was restarted 8 s later by the silent-failure watchdog, which saw the 9-hour-old newest snapshot before the first new one landed, and the second child (64720) has run since. First new snapshot 16:45:46Z.

## Streams affected

- asset_snapshots (no rows 07:45:38Z -> 16:45:46Z, 9.00 h; point-in-time polls, unrecoverable)
- liquidation_clusters (no rows 07:45:38Z -> 16:45:46Z, 9.00 h; unrecoverable)
- orderbook_snapshots (no rows 07:45:29Z -> 16:47:58Z, 9.04 h; unrecoverable)
- trades (EFFECTIVELY EMPTY: the subscribe-time backfill on resume delivered 998 rows spread 09:04Z -> 16:44Z against a live rate of ~60,000 an hour, so the interval holds well under 1 % of what was traded; unrecoverable)
- liquidation_events (4 rows in the interval, 10:03Z and 14:27Z; effectively empty, unrecoverable)
- latest_snapshots (stale for the whole interval)

## Evaluations that touch this interval

- none registered: the FOMC drill of 2026-09-16 has not run; the Item 18 lead-lag price series restarts a new continuous segment from 16:45:46Z (exporter ETA 2026-09-14T16:45Z), which the two-stream gate will report on any future unbounded check

## Detection and resolution

- detected 2026-09-13T16:50:00Z; resolved 2026-09-13T16:45:46Z
- resume_all.bat; supervisor RUNNING pid 83292 with child 64720; snapshots every ~9 s across 445 assets confirmed at 16:48Z; fomc_rehearsal --online 33 checks 0 FAIL at 16:51Z.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
