---
type: Event
title: 'Data gap: 2026-09-08_hl_asset_snapshots_2'
description: '26.42 h with no recording in asset_snapshots, latest_snapshots: 2026-09-08T16:01:22Z
  to 2026-09-09T18:26:39Z. Round 125.'
tags:
- event
- data-gap
- desk-1
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-09T18:32:02Z'
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
    start: '2026-09-08T16:01:22Z'
    end: '2026-09-09T18:26:39Z'
  gap_hours: 26.42
  tables:
  - asset_snapshots (no rows written; last old row 16:01:22.392Z, first new row 18:26:39.445Z)
  - latest_snapshots (stale for the whole interval)
  - cascade_excursions (no forward excursions measured inside the interval)
  - basis_realised_windows (no windows opened inside; overlapping windows carry their
    own coverage column)
  cause: 'Every 10-second snapshot batch failed with FOREIGN KEY constraint failed:
    USELESS (main DEX) and para:TREAD (para DEX) were listed after the 2026-09-07
    01:05Z restart with no row in assets (442 rows), and the pre-hardening collector
    synced assets only at startup and wrote each batch as one transaction, so two
    unknown coins rejected every row of every pass (8,206 errors in collector.log
    from 2026-09-08 12:01:37 EDT). The process never crashed (supervisor 24504 / collector
    60756 stayed alive), so the crash-only policy never fired; collector_service.jsonl
    logged coverage_pct 0.0, samples 0, restarts 0 every 15 min. Second occurrence
    of the Round 119 failure; the fix had been staged on feat/collector-hardening
    since Round 121. Round 125.'
  affected_evaluations:
  - 'lead_lag Tier 2 and Tier 2b run 3 (executed 2026-09-09T18:02Z over --since 2026-09-08T03:27:29Z,
    all four no-lead): 26.0 h of the 38.5 h window had no price series; declared VOID
    by Ruling R125-1.A, never ingested, the four _run3.json artifacts discarded; run
    3 re-bound to a fresh disjoint window from 2026-09-09T18:26:39Z.'
  - 'passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions
    were measured inside the gap; their window gates clear later by its length.'
  - 'basis windows: none opened inside the gap; overlapping windows are marked by
    their own coverage column.'
  round: 125
  detected_utc: '2026-09-09T18:03:00Z'
  resolved_utc: '2026-09-09T18:26:39Z'
---
# Data gap: 2026-09-08_hl_asset_snapshots_2

> **26.42 h with no recording** - 2026-09-08T16:01:22Z to 2026-09-09T18:26:39Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Every 10-second snapshot batch failed with FOREIGN KEY constraint failed: USELESS (main DEX) and para:TREAD (para DEX) were listed after the 2026-09-07 01:05Z restart with no row in assets (442 rows), and the pre-hardening collector synced assets only at startup and wrote each batch as one transaction, so two unknown coins rejected every row of every pass (8,206 errors in collector.log from 2026-09-08 12:01:37 EDT). The process never crashed (supervisor 24504 / collector 60756 stayed alive), so the crash-only policy never fired; collector_service.jsonl logged coverage_pct 0.0, samples 0, restarts 0 every 15 min. Second occurrence of the Round 119 failure; the fix had been staged on feat/collector-hardening since Round 121. Round 125.

## Streams affected

- asset_snapshots (no rows written; last old row 16:01:22.392Z, first new row 18:26:39.445Z)
- latest_snapshots (stale for the whole interval)
- cascade_excursions (no forward excursions measured inside the interval)
- basis_realised_windows (no windows opened inside; overlapping windows carry their own coverage column)

## Evaluations that touch this interval

- lead_lag Tier 2 and Tier 2b run 3 (executed 2026-09-09T18:02Z over --since 2026-09-08T03:27:29Z, all four no-lead): 26.0 h of the 38.5 h window had no price series; declared VOID by Ruling R125-1.A, never ingested, the four _run3.json artifacts discarded; run 3 re-bound to a fresh disjoint window from 2026-09-09T18:26:39Z.
- passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions were measured inside the gap; their window gates clear later by its length.
- basis windows: none opened inside the gap; overlapping windows are marked by their own coverage column.

## Detection and resolution

- detected 2026-09-09T18:03:00Z; resolved 2026-09-09T18:26:39Z
- Hardening 70bd232 merged to master as d3df1cb (8/8 tests) and deployed on the operator's authorisation (Ruling R125-1.B): stop_collector.bat at 18:26:30Z (pids 24504/60756 gone), start_collector.bat at 18:26:34Z (supervisor 16844, collector 74972); universe re-synced 442 -> 444; first new snapshot 18:26:39.445Z. The hardened collector re-syncs the universe every 60 polls and at once after a batch skips an unknown coin, inserts row-by-row, and the supervisor carries a silent-failure watchdog. Readiness gate hardened the same round (R125-1.C): cross_market.lead_lag --check-data now judges the price stream too.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
