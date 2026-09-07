---
type: Event
title: 'Data gap: 2026-09-06_hl_asset_snapshots'
description: '9.32 h with no recording in asset_snapshots, latest_snapshots: 2026-09-06T15:46:10Z
  to 2026-09-07T01:05:10Z. Round 119.'
tags:
- event
- data-gap
- desk-1
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T03:24:44Z'
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
    start: '2026-09-06T15:46:10Z'
    end: '2026-09-07T01:05:10Z'
  gap_hours: 9.32
  tables:
  - asset_snapshots (no rows written)
  - latest_snapshots (stale for the whole interval)
  - 'cascade_excursions (no forward excursions measured: ''persisted 0 windows / 0
    events'' on every maintenance pass)'
  - basis_realised_windows (0 windows opened inside; 1,764 overlapping windows carry
    coverage 0.61-0.99)
  cause: 'Every 10-second snapshot batch failed with FOREIGN KEY constraint failed:
    para:CIFR was listed on the exchange (para DEX) with no row in assets; the collector
    syncs assets only at startup and writes each batch as one transaction, so one
    unknown coin rejected all 442 rows per pass. The process never crashed, so the
    supervisor''s crash policy never fired. Round 119.'
  affected_evaluations:
  - 'lead_lag Tier 2 and Tier 2b runs ingested 2026-09-07T02:30Z (Round 120): BTC
    prices come from asset_snapshots, so about 9.3 h of the 24 h window had no price
    series. The registration''s readiness bar covers the tagged Polymarket stamps
    only. The readings stand as recorded; this caveat is now attached to them.'
  - 'passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions
    were measured inside the gap; their window gates clear later by its length.'
  - 'basis windows: none opened inside the gap; the 1,764 that span it are marked
    by their own coverage column.'
  round: 119
  detected_utc: '2026-09-07T00:55:00Z'
  resolved_utc: '2026-09-07T01:05:10Z'
---
# Data gap: 2026-09-06_hl_asset_snapshots

> **9.32 h with no recording** - 2026-09-06T15:46:10Z to 2026-09-07T01:05:10Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Every 10-second snapshot batch failed with FOREIGN KEY constraint failed: para:CIFR was listed on the exchange (para DEX) with no row in assets; the collector syncs assets only at startup and writes each batch as one transaction, so one unknown coin rejected all 442 rows per pass. The process never crashed, so the supervisor's crash policy never fired. Round 119.

## Streams affected

- asset_snapshots (no rows written)
- latest_snapshots (stale for the whole interval)
- cascade_excursions (no forward excursions measured: 'persisted 0 windows / 0 events' on every maintenance pass)
- basis_realised_windows (0 windows opened inside; 1,764 overlapping windows carry coverage 0.61-0.99)

## Evaluations that touch this interval

- lead_lag Tier 2 and Tier 2b runs ingested 2026-09-07T02:30Z (Round 120): BTC prices come from asset_snapshots, so about 9.3 h of the 24 h window had no price series. The registration's readiness bar covers the tagged Polymarket stamps only. The readings stand as recorded; this caveat is now attached to them.
- passive_fade_rebenchmark and whale_sweeper_cascade_replay: no forward excursions were measured inside the gap; their window gates clear later by its length.
- basis windows: none opened inside the gap; the 1,764 that span it are marked by their own coverage column.

## Detection and resolution

- detected 2026-09-07T00:55:00Z; resolved 2026-09-07T01:05:10Z
- Collector restarted on the operator's word (supervisor 24504, collector 60756); assets re-synced (441 -> 442); stop_collector.bat fixed (it had never killed anything); hardening staged on branch feat/collector-hardening per Ruling R119-1.B.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
