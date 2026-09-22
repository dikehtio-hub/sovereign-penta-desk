---
type: Event
title: 'Data gap: 2026-09-19_hl_shutdown_update_sleep'
description: '15.01 h with no recording in asset_snapshots, trades: 2026-09-19T02:28:44Z
  to 2026-09-19T17:29:36Z. Round 128.'
tags:
- event
- data-gap
- desk-1
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T06:34:16Z'
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
    start: '2026-09-19T02:28:44Z'
    end: '2026-09-19T17:29:36Z'
  gap_hours: 15.01
  tables:
  - asset_snapshots (last row 02:28:44.191Z, first new row 17:29:36.327Z, 15.01 h,
    0 rows strictly inside; point-in-time polls, unrecoverable)
  - 'trades (EFFECTIVELY EMPTY: 1,485 subscribe-time backfill rows strictly inside
    02:28:44.085Z -> 17:29:36.392Z against a live baseline of 93,409/h in the hour
    before the stop and 100,862/h in the hour after the resume; unrecoverable)'
  - orderbook_snapshots (no rows 02:28:29.165Z -> 17:31:37.293Z, 15.05 h; unrecoverable)
  - liquidation_events (3 rows strictly inside 02:28:43.263Z -> 17:29:41.705Z, 15.02
    h; unrecoverable)
  - 'liquidation_clusters (cannot be bounded from below: the earliest row in the table
    overall is 17:29:36.590Z, i.e. the resume instant, so retention has already consumed
    everything before the gap)'
  - latest_snapshots (stale for the whole interval)
  cause: 'Operator night shutdown on Friday 09-18 22:28 EDT followed by an Intel driver
    restart storm, a second failed Windows 11 25H2 upgrade, and a 10.4 h sleep. NOT
    REGISTERED AT THE TIME - reconstructed and appended 2026-09-20 by Claude Code
    while running the shutdown routine, which is why the round field is unchanged.
    Sequence, all UTC: collector stopped cleanly at 02:28:52.650Z (stop_file_observed,
    collector_stopped_by_operator runtime 22,978.7 s, keep_awake_released, service_stop
    02:28:54.725Z, restarts 1, coverage 33.81 %); five full shutdown/boot cycles between
    02:29:54Z and 03:04:51Z (EventLog 6006/6005 + Kernel-Power 109 + Kernel-General
    13/12, boot type 0x0 every time), initiated by User32 1074 as RuntimeBroker.exe
    on behalf of ixis1 at 02:31:32Z, 02:50:41Z and 03:03:40Z and by msiexec.exe on
    behalf of SYSTEM at 02:34:08Z; the driver payload behind them was Intel Display
    31.0.101.5187 and Intel Extension 32.0.101.6733, installed at 02:42:39-02:44:37Z
    and installed a SECOND time at 02:57:44-03:00:02Z, plus Defender KB2267602 1.459.280.0
    and a Store app. Windows 11 version 25H2 then started installing at 05:09:07Z
    and FAILED at 05:15:01Z with 0xC1900208, the same compatibility hold that failed
    it on 09-17. RuntimeBroker initiated a power off on behalf of ixis1 at 05:38:49Z,
    which the kernel recorded as sleep (Kernel-Power 566 then 42 at 05:39:00-05:39:02Z);
    the machine stayed asleep until 16:03:23Z, proved by the Kernel-General 1 clock
    restore reading ''changed to 2026-09-19T16:03:23Z from 2026-09-19T05:39:0x''.
    Session transitions 16:03:26-16:08:57Z, .NET KB5126106 and KB5126104 installed
    16:04-16:56Z, and the machine then sat AWAKE with the pipeline down for 1.43 h
    until resume_all.bat at 17:29:25.810Z (service_start pid 57784; first child 22476
    restarted by the watchdog 4.7 s later - snapshot_age 54,046.3 s, coverage 26.6
    % - logged as collector_crashed_early exit 1 after 5.7 s; second child 55588 from
    17:29:33.497Z). That resume-time false restart is the same first-tick watchdog
    defect ruled on 09-18 and still unfixed (HOMEWORK go/no-go item (b)).'
  affected_evaluations:
  - 'lead-lag: the continuous price/stamp segment that began 2026-09-18T20:05:57Z
    was cut at 02:28:44Z after 6.4 h, well short of the 24 h bar; a new segment ran
    17:29:36Z -> 2026-09-20T06:20:54Z (12.86 h) and was cut again by tonight''s shutdown.
    No Item 18 run was executed against either segment.'
  - 'passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions
    measured inside; their window gates clear later by the gap length'
  - 'basis windows: overlapping windows carry their own coverage column - the supervisor
    reported coverage 26.6 % at resume, recovering to 53.56 % by tonight''s stop'
  round: 128
  detected_utc: '2026-09-20T06:18:14Z'
  resolved_utc: '2026-09-19T17:29:36Z'
---
# Data gap: 2026-09-19_hl_shutdown_update_sleep

> **15.01 h with no recording** - 2026-09-19T02:28:44Z to 2026-09-19T17:29:36Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Operator night shutdown on Friday 09-18 22:28 EDT followed by an Intel driver restart storm, a second failed Windows 11 25H2 upgrade, and a 10.4 h sleep. NOT REGISTERED AT THE TIME - reconstructed and appended 2026-09-20 by Claude Code while running the shutdown routine, which is why the round field is unchanged. Sequence, all UTC: collector stopped cleanly at 02:28:52.650Z (stop_file_observed, collector_stopped_by_operator runtime 22,978.7 s, keep_awake_released, service_stop 02:28:54.725Z, restarts 1, coverage 33.81 %); five full shutdown/boot cycles between 02:29:54Z and 03:04:51Z (EventLog 6006/6005 + Kernel-Power 109 + Kernel-General 13/12, boot type 0x0 every time), initiated by User32 1074 as RuntimeBroker.exe on behalf of ixis1 at 02:31:32Z, 02:50:41Z and 03:03:40Z and by msiexec.exe on behalf of SYSTEM at 02:34:08Z; the driver payload behind them was Intel Display 31.0.101.5187 and Intel Extension 32.0.101.6733, installed at 02:42:39-02:44:37Z and installed a SECOND time at 02:57:44-03:00:02Z, plus Defender KB2267602 1.459.280.0 and a Store app. Windows 11 version 25H2 then started installing at 05:09:07Z and FAILED at 05:15:01Z with 0xC1900208, the same compatibility hold that failed it on 09-17. RuntimeBroker initiated a power off on behalf of ixis1 at 05:38:49Z, which the kernel recorded as sleep (Kernel-Power 566 then 42 at 05:39:00-05:39:02Z); the machine stayed asleep until 16:03:23Z, proved by the Kernel-General 1 clock restore reading 'changed to 2026-09-19T16:03:23Z from 2026-09-19T05:39:0x'. Session transitions 16:03:26-16:08:57Z, .NET KB5126106 and KB5126104 installed 16:04-16:56Z, and the machine then sat AWAKE with the pipeline down for 1.43 h until resume_all.bat at 17:29:25.810Z (service_start pid 57784; first child 22476 restarted by the watchdog 4.7 s later - snapshot_age 54,046.3 s, coverage 26.6 % - logged as collector_crashed_early exit 1 after 5.7 s; second child 55588 from 17:29:33.497Z). That resume-time false restart is the same first-tick watchdog defect ruled on 09-18 and still unfixed (HOMEWORK go/no-go item (b)).

## Streams affected

- asset_snapshots (last row 02:28:44.191Z, first new row 17:29:36.327Z, 15.01 h, 0 rows strictly inside; point-in-time polls, unrecoverable)
- trades (EFFECTIVELY EMPTY: 1,485 subscribe-time backfill rows strictly inside 02:28:44.085Z -> 17:29:36.392Z against a live baseline of 93,409/h in the hour before the stop and 100,862/h in the hour after the resume; unrecoverable)
- orderbook_snapshots (no rows 02:28:29.165Z -> 17:31:37.293Z, 15.05 h; unrecoverable)
- liquidation_events (3 rows strictly inside 02:28:43.263Z -> 17:29:41.705Z, 15.02 h; unrecoverable)
- liquidation_clusters (cannot be bounded from below: the earliest row in the table overall is 17:29:36.590Z, i.e. the resume instant, so retention has already consumed everything before the gap)
- latest_snapshots (stale for the whole interval)

## Evaluations that touch this interval

- lead-lag: the continuous price/stamp segment that began 2026-09-18T20:05:57Z was cut at 02:28:44Z after 6.4 h, well short of the 24 h bar; a new segment ran 17:29:36Z -> 2026-09-20T06:20:54Z (12.86 h) and was cut again by tonight's shutdown. No Item 18 run was executed against either segment.
- passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions measured inside; their window gates clear later by the gap length
- basis windows: overlapping windows carry their own coverage column - the supervisor reported coverage 26.6 % at resume, recovering to 53.56 % by tonight's stop

## Detection and resolution

- detected 2026-09-20T06:18:14Z; resolved 2026-09-19T17:29:36Z
- resume_all.bat 09-19 13:29 EDT: collector/supervisor pid 57784 (child 55588), watcher, cross-market exporter and 5/5 telemetry exporters all recovered; first new snapshot 17:29:36.327Z. Verified retrospectively 2026-09-20 from collector_service.jsonl, the Windows System event log and the tables themselves.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
