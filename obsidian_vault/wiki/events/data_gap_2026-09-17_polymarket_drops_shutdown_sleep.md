---
type: Event
title: 'Data gap: 2026-09-17_polymarket_drops_shutdown_sleep'
description: '14.56 h with no recording in Sports_Desk/data/polymarket_drops stamped
  drops: 2026-09-17T04:51:38Z to 2026-09-17T19:25:25Z. Round 128.'
tags:
- event
- data-gap
- desk-3
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
  desk: 3
  window:
    start: '2026-09-17T04:51:38Z'
    end: '2026-09-17T19:25:25Z'
  gap_hours: 14.56
  tables:
  - Sports_Desk/data/polymarket_drops stamped drops (last stamps polymarket_macro_20260917T045138Z
    / polymarket_sports at the same poll, first new polymarket_sports_20260917T192524Z
    and polymarket_macro_20260917T192525Z; 14.56 h with no stamp)
  cause: 'Same night as 2026-09-17_hl_shutdown_sleep, with a twist that exposed a
    script defect: shutdown_all.bat''s layer-2 stop (taskkill /FI WINDOWTITLE) cannot
    match the detached pythonw watcher, so the watcher kept stamping at the 5-minute
    cadence for 24 minutes after the collector stop (stamps 04:31, 04:36, 04:41, 04:46,
    04:51:38Z) and only died with the 04:53:53Z sleep. Defect and fix ruling logged
    in AGENTS.md on 09-18 (layer 2 must call polymarket_fetcher --stop). Relaunched
    by resume_all.bat at 19:25Z on 09-17.'
  affected_evaluations:
  - 'none registered: the tagged-stamp series restarts a new continuous segment from
    19:25:25Z, which the two-stream gate will report on any future unbounded check'
  round: 128
  detected_utc: '2026-09-18T20:15:00Z'
  resolved_utc: '2026-09-17T19:25:25Z'
---
# Data gap: 2026-09-17_polymarket_drops_shutdown_sleep

> **14.56 h with no recording** - 2026-09-17T04:51:38Z to 2026-09-17T19:25:25Z (desk 3). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Same night as 2026-09-17_hl_shutdown_sleep, with a twist that exposed a script defect: shutdown_all.bat's layer-2 stop (taskkill /FI WINDOWTITLE) cannot match the detached pythonw watcher, so the watcher kept stamping at the 5-minute cadence for 24 minutes after the collector stop (stamps 04:31, 04:36, 04:41, 04:46, 04:51:38Z) and only died with the 04:53:53Z sleep. Defect and fix ruling logged in AGENTS.md on 09-18 (layer 2 must call polymarket_fetcher --stop). Relaunched by resume_all.bat at 19:25Z on 09-17.

## Streams affected

- Sports_Desk/data/polymarket_drops stamped drops (last stamps polymarket_macro_20260917T045138Z / polymarket_sports at the same poll, first new polymarket_sports_20260917T192524Z and polymarket_macro_20260917T192525Z; 14.56 h with no stamp)

## Evaluations that touch this interval

- none registered: the tagged-stamp series restarts a new continuous segment from 19:25:25Z, which the two-stream gate will report on any future unbounded check

## Detection and resolution

- detected 2026-09-18T20:15:00Z; resolved 2026-09-17T19:25:25Z
- resume_all.bat 09-17 15:25 EDT; stamps resumed at the 5-minute cadence (19:25, 19:30, 19:35 ... on 09-17). Registered retroactively 09-18.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
