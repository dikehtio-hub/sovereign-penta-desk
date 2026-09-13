---
type: Event
title: 'Data gap: 2026-09-13_polymarket_drops_sleep'
description: '9.0 h with no recording in Sports_Desk/data/polymarket_drops stamped
  drops: 2026-09-13T07:45:06Z to 2026-09-13T16:45:16Z. Round 128.'
tags:
- event
- data-gap
- desk-3
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
  desk: 3
  window:
    start: '2026-09-13T07:45:06Z'
    end: '2026-09-13T16:45:16Z'
  gap_hours: 9.0
  tables:
  - Sports_Desk/data/polymarket_drops stamped drops (last stamps polymarket_macro_20260913T074506Z
    / polymarket_sports_20260913T074506Z, first new 20260913T164516Z; 9.00 h with
    no stamp)
  cause: 'Same sleep as 2026-09-13_hl_sleep: the watcher (pid 62448 since 09-12) died
    with the sleep and was relaunched by resume_all.bat at 12:45 EDT as pid 95876
    (16:45:12Z).'
  affected_evaluations:
  - 'none registered: the tagged-stamp series restarts a new continuous segment from
    16:45:16Z, which the two-stream gate will report on any future unbounded check'
  round: 128
  detected_utc: '2026-09-13T16:50:00Z'
  resolved_utc: '2026-09-13T16:45:16Z'
---
# Data gap: 2026-09-13_polymarket_drops_sleep

> **9.0 h with no recording** - 2026-09-13T07:45:06Z to 2026-09-13T16:45:16Z (desk 3). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Same sleep as 2026-09-13_hl_sleep: the watcher (pid 62448 since 09-12) died with the sleep and was relaunched by resume_all.bat at 12:45 EDT as pid 95876 (16:45:12Z).

## Streams affected

- Sports_Desk/data/polymarket_drops stamped drops (last stamps polymarket_macro_20260913T074506Z / polymarket_sports_20260913T074506Z, first new 20260913T164516Z; 9.00 h with no stamp)

## Evaluations that touch this interval

- none registered: the tagged-stamp series restarts a new continuous segment from 16:45:16Z, which the two-stream gate will report on any future unbounded check

## Detection and resolution

- detected 2026-09-13T16:50:00Z; resolved 2026-09-13T16:45:16Z
- resume_all.bat; watcher RUNNING pid 95876; stamps resumed at the 5-minute cadence (macro and sports stamps 3.4 min old at 16:49Z).

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
