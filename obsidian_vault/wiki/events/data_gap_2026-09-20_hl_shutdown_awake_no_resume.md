---
type: Event
title: 'Data gap: 2026-09-20_hl_shutdown_awake_no_resume'
description: '19.73 h with no recording in asset_snapshots, trades: 2026-09-20T06:20:54Z
  to 2026-09-21T02:04:43Z. Round 128.'
tags:
- event
- data-gap
- desk-1
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-21T02:07:25Z'
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
    start: '2026-09-20T06:20:54Z'
    end: '2026-09-21T02:04:43Z'
  gap_hours: 19.73
  tables:
  - asset_snapshots (last row 06:20:54.663Z, first new row 2026-09-21T02:04:43.373Z,
    19.73 h, 0 rows strictly inside; point-in-time polls, unrecoverable)
  - 'trades (EFFECTIVELY EMPTY: 1,066 subscribe-time backfill rows strictly inside
    06:20:54.354Z -> 02:04:43.375Z against a live baseline of 70,665/h in the hour
    before the stop; unrecoverable)'
  - 'liquidation_clusters (last row 06:20:55.424Z, first new 02:04:43.612Z. 212 rows
    carry in-gap timestamps but ALL fall in the single second 06:20:54-06:20:55Z:
    that is the collector''s final flush at shutdown, not in-gap data - 11/h against
    a live rate of 87,476/h, 0.01 %. The gap itself is clean.)'
  - orderbook_snapshots (last row 06:20:11.866Z; no new row yet at the time of registration
    - the L2 sampler runs on a ~2 min cadence and had not completed a pass; unrecoverable)
  - liquidation_events (1 row strictly inside 06:19:45.273Z -> 02:04:43.577Z, 19.75
    h; unrecoverable)
  - latest_snapshots (stale for the whole interval)
  cause: 'Planned operator night shutdown - but THE MACHINE NEVER SLEPT AND WAS NEVER
    POWERED OFF, and nobody resumed for 19.7 h. This is the longest of the four recent
    outages and the only one with no power event behind it. shutdown_all.bat was run
    by Claude Code at the operator''s request at 02:20 EDT Sun 09-20: stop_file_observed
    06:20:58.850Z, collector_stopped_by_operator runtime 46,285.4 s, keep_awake_released,
    service_stop 06:21:00.648Z, graceful=true forced=false waited 2.5 s, WAL checkpointed
    (0 bytes before and after), restarts 1, coverage 53.56 %. Layers 2 and 3 again
    survived the WINDOWTITLE stops and were taken down by their own --stop CLIs and
    a command-line PID sweep; 0 Monarch processes remained, verified. The Windows
    System log then records ZERO Kernel-Power 42/107, zero 109/13/12 and zero User32
    1074 between 06:21Z on 09-20 and 02:04Z on 09-21: uptime ran continuously from
    the 09-19T03:04Z boot to 46.7 h at the point of detection, on mains at 98 %. So
    the host sat awake and idle with the pipeline down for the whole interval. Two
    other Claude Code sessions did work in DEV inside the window without restarting
    it - commits 4efdfff and ccdfa5c at 07:23Z (the digest/ruling adapters taught
    to read AGENTS_ARCHIVE.md, clearing the 109 C1 errors) and an uncommitted TradingView
    MCP vendoring at 23:48Z - which is the operational lesson here: a session that
    edits the repo does not imply a session that watches the pipeline. Detected at
    01:47Z on 09-21 only because the operator asked what was running. resume_all.bat
    at 02:04:30Z: service_start pid 48420, keep_awake re-held 02:04:34Z, first child
    16544 restarted by the watchdog 4 s later (snapshot_age 71,023.5 s, coverage 17.79
    %) and logged as collector_crashed_early exit 1 after 5.0 s, second child 17852
    from 02:04:41Z. That resume-time false restart is the same unfixed first-tick
    watchdog defect seen on 09-13, 09-17, 09-18 and 09-19 (HOMEWORK go/no-go item
    (b)); it is now 5 for 5 and is the single most reliably reproducible defect in
    the system.'
  affected_evaluations:
  - 'lead-lag: the continuous segment that began 2026-09-19T17:29:36Z was cut at 06:20:54Z
    after 12.86 h, short of the 24 h bar; a new segment starts 2026-09-21T02:04:43Z.
    The exporter''s own gate at resume reported NOT READY (span 12.8 h < 24 h, points
    147 < 200) and also flagged a 61-min hole 2026-09-19T16:28:34Z -> 17:29:36Z, which
    is the synthetic max_lag+1 lookback edge meeting the previous resume, not a data
    defect (ruled 09-18, AGENTS.md).'
  - 'passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions
    measured inside; their window gates clear later by the gap length'
  - 'basis windows: overlapping windows carry their own coverage column - the supervisor
    reported coverage 17.79 % at resume, the lowest of any recent restart'
  round: 128
  detected_utc: '2026-09-21T01:47:32Z'
  resolved_utc: '2026-09-21T02:04:43Z'
---
# Data gap: 2026-09-20_hl_shutdown_awake_no_resume

> **19.73 h with no recording** - 2026-09-20T06:20:54Z to 2026-09-21T02:04:43Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Planned operator night shutdown - but THE MACHINE NEVER SLEPT AND WAS NEVER POWERED OFF, and nobody resumed for 19.7 h. This is the longest of the four recent outages and the only one with no power event behind it. shutdown_all.bat was run by Claude Code at the operator's request at 02:20 EDT Sun 09-20: stop_file_observed 06:20:58.850Z, collector_stopped_by_operator runtime 46,285.4 s, keep_awake_released, service_stop 06:21:00.648Z, graceful=true forced=false waited 2.5 s, WAL checkpointed (0 bytes before and after), restarts 1, coverage 53.56 %. Layers 2 and 3 again survived the WINDOWTITLE stops and were taken down by their own --stop CLIs and a command-line PID sweep; 0 Monarch processes remained, verified. The Windows System log then records ZERO Kernel-Power 42/107, zero 109/13/12 and zero User32 1074 between 06:21Z on 09-20 and 02:04Z on 09-21: uptime ran continuously from the 09-19T03:04Z boot to 46.7 h at the point of detection, on mains at 98 %. So the host sat awake and idle with the pipeline down for the whole interval. Two other Claude Code sessions did work in DEV inside the window without restarting it - commits 4efdfff and ccdfa5c at 07:23Z (the digest/ruling adapters taught to read AGENTS_ARCHIVE.md, clearing the 109 C1 errors) and an uncommitted TradingView MCP vendoring at 23:48Z - which is the operational lesson here: a session that edits the repo does not imply a session that watches the pipeline. Detected at 01:47Z on 09-21 only because the operator asked what was running. resume_all.bat at 02:04:30Z: service_start pid 48420, keep_awake re-held 02:04:34Z, first child 16544 restarted by the watchdog 4 s later (snapshot_age 71,023.5 s, coverage 17.79 %) and logged as collector_crashed_early exit 1 after 5.0 s, second child 17852 from 02:04:41Z. That resume-time false restart is the same unfixed first-tick watchdog defect seen on 09-13, 09-17, 09-18 and 09-19 (HOMEWORK go/no-go item (b)); it is now 5 for 5 and is the single most reliably reproducible defect in the system.

## Streams affected

- asset_snapshots (last row 06:20:54.663Z, first new row 2026-09-21T02:04:43.373Z, 19.73 h, 0 rows strictly inside; point-in-time polls, unrecoverable)
- trades (EFFECTIVELY EMPTY: 1,066 subscribe-time backfill rows strictly inside 06:20:54.354Z -> 02:04:43.375Z against a live baseline of 70,665/h in the hour before the stop; unrecoverable)
- liquidation_clusters (last row 06:20:55.424Z, first new 02:04:43.612Z. 212 rows carry in-gap timestamps but ALL fall in the single second 06:20:54-06:20:55Z: that is the collector's final flush at shutdown, not in-gap data - 11/h against a live rate of 87,476/h, 0.01 %. The gap itself is clean.)
- orderbook_snapshots (last row 06:20:11.866Z; no new row yet at the time of registration - the L2 sampler runs on a ~2 min cadence and had not completed a pass; unrecoverable)
- liquidation_events (1 row strictly inside 06:19:45.273Z -> 02:04:43.577Z, 19.75 h; unrecoverable)
- latest_snapshots (stale for the whole interval)

## Evaluations that touch this interval

- lead-lag: the continuous segment that began 2026-09-19T17:29:36Z was cut at 06:20:54Z after 12.86 h, short of the 24 h bar; a new segment starts 2026-09-21T02:04:43Z. The exporter's own gate at resume reported NOT READY (span 12.8 h < 24 h, points 147 < 200) and also flagged a 61-min hole 2026-09-19T16:28:34Z -> 17:29:36Z, which is the synthetic max_lag+1 lookback edge meeting the previous resume, not a data defect (ruled 09-18, AGENTS.md).
- passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions measured inside; their window gates clear later by the gap length
- basis windows: overlapping windows carry their own coverage column - the supervisor reported coverage 17.79 % at resume, the lowest of any recent restart

## Detection and resolution

- detected 2026-09-21T01:47:32Z; resolved 2026-09-21T02:04:43Z
- resume_all.bat 09-20 22:04 EDT run by Claude Code at the operator's request: collector/supervisor pid 48420 (child 17852), Polymarket watcher and cross-market exporter both relaunched after their stale locks were swept, telemetry 5/5 (hyperliquid 35852, polymarket 66736, tax 63376, sports 52848, quantlab 65176 with its interpreter pair). Verified WRITING, not merely launched: 1,796 asset_snapshot rows in the first 120 s, newest trade 1.0 s old, new Polymarket stamps at 02:04:39Z.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
