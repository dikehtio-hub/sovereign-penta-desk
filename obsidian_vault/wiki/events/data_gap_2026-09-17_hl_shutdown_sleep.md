---
type: Event
title: 'Data gap: 2026-09-17_hl_shutdown_sleep'
description: '14.96 h with no recording in asset_snapshots, liquidation_clusters:
  2026-09-17T04:27:31Z to 2026-09-17T19:25:19Z. Round 128.'
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
    start: '2026-09-17T04:27:31Z'
    end: '2026-09-17T19:25:19Z'
  gap_hours: 14.96
  tables:
  - asset_snapshots (no rows 04:27:27.270Z -> 19:25:19.410Z, 14.97 h; point-in-time
    polls, unrecoverable)
  - liquidation_clusters (no rows 04:27:27.726Z -> 19:25:19.653Z, 14.97 h; unrecoverable)
  - orderbook_snapshots (no rows 04:26:42.534Z -> 19:27:28.175Z, 15.01 h; unrecoverable)
  - 'trades (EFFECTIVELY EMPTY: 1,373 subscribe-time backfill rows spread 15:42:23Z
    -> 19:25:24Z against a live rate of ~160,000 an hour (159,771 rows in 03:00-04:00Z
    on 09-18), so the interval holds under 0.1 % of what was traded; unrecoverable)'
  - liquidation_events (0 rows 04:27:06.724Z -> 19:25:47.039Z; unrecoverable)
  - latest_snapshots (stale for the whole interval)
  cause: 'Operator night shutdown followed by sleep, found and registered a day late.
    shutdown_all.bat ran at 00:27 EDT Wed 09-17: stop_file_observed 04:27:31.862Z,
    collector_stopped_by_operator after 293,899 s (3.4 days) of runtime. The laptop
    then slept at 04:53:53Z (Kernel-Power 42, RuntimeBroker-initiated power transition
    at 04:53:40Z), returned from low power at 16:32:33Z (12:32 EDT), slept again 16:39:08Z
    and returned 18:51:23Z (14:51 EDT). resume_all.bat at 15:25 EDT: service_start
    19:25:15.708Z pid 10968; the first child (53556) was restarted 6 s later by the
    silent-failure watchdog, which saw the 897.9-minute-old newest snapshot before
    the first new one was counted (same shape as 2026-09-13_hl_sleep), and the second
    child (89344) ran from 19:25:24.5Z until the 01:30Z reboot (2026-09-18_hl_reboot).
    First new snapshot 19:25:19.410Z. Not registered on the day: no AGENTS.md or HOMEWORK.md
    line mentions the 09-17 stop or resume; discovered on 09-18 from collector_service.jsonl
    while registering that night''s gap. Section 94 era (rounds frozen at 128 since
    the section-numbered exchange took over).'
  affected_evaluations:
  - 'none registered: the FOMC drill window [2026-09-16T17:00Z, 18:05Z] was complete
    and ingested before the stop; Phase 2 event 2 is the CPI print of 2026-10-14'
  - the Item 18 lead-lag price series restarts a new continuous segment from 19:25:19Z;
    it was cut again by 2026-09-18_hl_reboot and 2026-09-18_hl_shutdown_sleep before
    reaching 24 h
  - 'OPEN NOTE for the auditor: the cross-market exporter''s lead-lag gate reported
    ''price stream has 1 hole(s) > 60 min ... largest 61 min: 2026-09-17T18:24:25Z
    -> 2026-09-17T19:25:19Z'', but asset_snapshots holds no row between 04:27:27Z
    and 19:25:19Z, so the 18:24:25Z point is not a database row; where the exporter''s
    series got it is unexplained'
  round: 128
  detected_utc: '2026-09-18T20:15:00Z'
  resolved_utc: '2026-09-17T19:25:19Z'
---
# Data gap: 2026-09-17_hl_shutdown_sleep

> **14.96 h with no recording** - 2026-09-17T04:27:31Z to 2026-09-17T19:25:19Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Operator night shutdown followed by sleep, found and registered a day late. shutdown_all.bat ran at 00:27 EDT Wed 09-17: stop_file_observed 04:27:31.862Z, collector_stopped_by_operator after 293,899 s (3.4 days) of runtime. The laptop then slept at 04:53:53Z (Kernel-Power 42, RuntimeBroker-initiated power transition at 04:53:40Z), returned from low power at 16:32:33Z (12:32 EDT), slept again 16:39:08Z and returned 18:51:23Z (14:51 EDT). resume_all.bat at 15:25 EDT: service_start 19:25:15.708Z pid 10968; the first child (53556) was restarted 6 s later by the silent-failure watchdog, which saw the 897.9-minute-old newest snapshot before the first new one was counted (same shape as 2026-09-13_hl_sleep), and the second child (89344) ran from 19:25:24.5Z until the 01:30Z reboot (2026-09-18_hl_reboot). First new snapshot 19:25:19.410Z. Not registered on the day: no AGENTS.md or HOMEWORK.md line mentions the 09-17 stop or resume; discovered on 09-18 from collector_service.jsonl while registering that night's gap. Section 94 era (rounds frozen at 128 since the section-numbered exchange took over).

## Streams affected

- asset_snapshots (no rows 04:27:27.270Z -> 19:25:19.410Z, 14.97 h; point-in-time polls, unrecoverable)
- liquidation_clusters (no rows 04:27:27.726Z -> 19:25:19.653Z, 14.97 h; unrecoverable)
- orderbook_snapshots (no rows 04:26:42.534Z -> 19:27:28.175Z, 15.01 h; unrecoverable)
- trades (EFFECTIVELY EMPTY: 1,373 subscribe-time backfill rows spread 15:42:23Z -> 19:25:24Z against a live rate of ~160,000 an hour (159,771 rows in 03:00-04:00Z on 09-18), so the interval holds under 0.1 % of what was traded; unrecoverable)
- liquidation_events (0 rows 04:27:06.724Z -> 19:25:47.039Z; unrecoverable)
- latest_snapshots (stale for the whole interval)

## Evaluations that touch this interval

- none registered: the FOMC drill window [2026-09-16T17:00Z, 18:05Z] was complete and ingested before the stop; Phase 2 event 2 is the CPI print of 2026-10-14
- the Item 18 lead-lag price series restarts a new continuous segment from 19:25:19Z; it was cut again by 2026-09-18_hl_reboot and 2026-09-18_hl_shutdown_sleep before reaching 24 h
- OPEN NOTE for the auditor: the cross-market exporter's lead-lag gate reported 'price stream has 1 hole(s) > 60 min ... largest 61 min: 2026-09-17T18:24:25Z -> 2026-09-17T19:25:19Z', but asset_snapshots holds no row between 04:27:27Z and 19:25:19Z, so the 18:24:25Z point is not a database row; where the exporter's series got it is unexplained

## Detection and resolution

- detected 2026-09-18T20:15:00Z; resolved 2026-09-17T19:25:19Z
- resume_all.bat 09-17 15:25 EDT (operator). Registered retroactively 09-18 16:20 EDT by Claude Code from collector_service.jsonl, the Windows System log and hyperliquid_data.db bounds.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
