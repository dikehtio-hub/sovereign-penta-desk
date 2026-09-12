---
type: Event
title: 'Data gap: 2026-09-12_polymarket_drops_shutdown'
description: '9.44 h with no recording in Sports_Desk/data/polymarket_drops stamped
  drops: 2026-09-12T05:54:25Z to 2026-09-12T15:21:01Z. Round 127.'
tags:
- event
- data-gap
- desk-3
- incident
generated:
  by: claude-code/fable-5.1
  at: '2026-09-12T15:59:45Z'
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
    start: '2026-09-12T05:54:25Z'
    end: '2026-09-12T15:21:01Z'
  gap_hours: 9.44
  tables:
  - Sports_Desk/data/polymarket_drops stamped drops (last stamp 20260912T055425Z,
    first new 20260912T152101Z; 9.44 h with no stamp)
  cause: Same planned shutdown as 2026-09-12_hl_shutdown. The watcher died with the
    machine and was relaunched by resume_all.bat as pid 62448.
  affected_evaluations:
  - 'none registered: the tagged-stamp series restarts a new continuous segment from
    15:21:01Z, which the two-stream gate will report on any future unbounded check'
  round: 127
  detected_utc: '2026-09-12T15:22:00Z'
  resolved_utc: '2026-09-12T15:21:01Z'
---
# Data gap: 2026-09-12_polymarket_drops_shutdown

> **9.44 h with no recording** - 2026-09-12T05:54:25Z to 2026-09-12T15:21:01Z (desk 3). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Same planned shutdown as 2026-09-12_hl_shutdown. The watcher died with the machine and was relaunched by resume_all.bat as pid 62448.

## Streams affected

- Sports_Desk/data/polymarket_drops stamped drops (last stamp 20260912T055425Z, first new 20260912T152101Z; 9.44 h with no stamp)

## Evaluations that touch this interval

- none registered: the tagged-stamp series restarts a new continuous segment from 15:21:01Z, which the two-stream gate will report on any future unbounded check

## Detection and resolution

- detected 2026-09-12T15:22:00Z; resolved 2026-09-12T15:21:01Z
- resume_all.bat; watcher RUNNING pid 62448; stamps resumed at the 5-minute cadence.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
