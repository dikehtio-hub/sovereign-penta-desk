---
type: Event
title: 'Data gap: 2026-09-18_polymarket_drops_shutdown_sleep'
description: '15.9 h with no recording in Sports_Desk/data/polymarket_drops stamped
  drops: 2026-09-18T04:12:03Z to 2026-09-18T20:05:55Z. Round 128.'
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
    start: '2026-09-18T04:12:03Z'
    end: '2026-09-18T20:05:55Z'
  gap_hours: 15.9
  tables:
  - Sports_Desk/data/polymarket_drops stamped drops (last stamps polymarket_macro_20260918T041203Z
    / polymarket_sports_20260918T041203Z, first new polymarket_sports_20260918T200555Z
    / polymarket_macro_20260918T200555Z; 15.90 h with no stamp)
  cause: 'Same night as 2026-09-18_hl_shutdown_sleep: the watcher (pid 6300) survived
    shutdown_all.bat''s window-title stop and was stopped by PID at about 04:14Z,
    2 minutes after its 04:12:03Z stamp; relaunched by resume_all.bat at 20:05Z as
    pid 57524 after sweeping its stale lock.'
  affected_evaluations:
  - 'none registered: the tagged-stamp series restarts a new continuous segment from
    20:05:55Z, which the two-stream gate will report on any future unbounded check'
  round: 128
  detected_utc: '2026-09-18T04:13:03Z'
  resolved_utc: '2026-09-18T20:05:55Z'
---
# Data gap: 2026-09-18_polymarket_drops_shutdown_sleep

> **15.9 h with no recording** - 2026-09-18T04:12:03Z to 2026-09-18T20:05:55Z (desk 3). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Same night as 2026-09-18_hl_shutdown_sleep: the watcher (pid 6300) survived shutdown_all.bat's window-title stop and was stopped by PID at about 04:14Z, 2 minutes after its 04:12:03Z stamp; relaunched by resume_all.bat at 20:05Z as pid 57524 after sweeping its stale lock.

## Streams affected

- Sports_Desk/data/polymarket_drops stamped drops (last stamps polymarket_macro_20260918T041203Z / polymarket_sports_20260918T041203Z, first new polymarket_sports_20260918T200555Z / polymarket_macro_20260918T200555Z; 15.90 h with no stamp)

## Evaluations that touch this interval

- none registered: the tagged-stamp series restarts a new continuous segment from 20:05:55Z, which the two-stream gate will report on any future unbounded check

## Detection and resolution

- detected 2026-09-18T04:13:03Z; resolved 2026-09-18T20:05:55Z
- resume_all.bat 09-18 16:05 EDT; watcher RUNNING pid 57524; first poll stamped macro (286 questions) and sports at 20:05:55Z and pruned 376 stamps older than 192 h.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
