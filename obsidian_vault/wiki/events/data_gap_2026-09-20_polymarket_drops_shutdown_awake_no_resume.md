---
type: Event
title: 'Data gap: 2026-09-20_polymarket_drops_shutdown_awake_no_resume'
description: '19.75 h with no recording in Sports_Desk/data/polymarket_drops stamped
  drops: 2026-09-20T06:19:45Z to 2026-09-21T02:04:39Z. Round 128.'
tags:
- event
- data-gap
- desk-3
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
  desk: 3
  window:
    start: '2026-09-20T06:19:45Z'
    end: '2026-09-21T02:04:39Z'
  gap_hours: 19.75
  tables:
  - Sports_Desk/data/polymarket_drops stamped drops (last stamp polymarket_sports_20260920T061945Z,
    first new polymarket_macro_20260921T020439Z; 19.75 h with no stamp)
  cause: Same shutdown as 2026-09-20_hl_shutdown_awake_no_resume. The watcher was
    stopped cleanly at 06:21Z through its own `polymarket_fetcher --stop` CLI (pid
    24528 terminated, lock swept) rather than by the window-title filter, which cannot
    match a detached pythonw - the first live use of the ratified shutdown fix (a).
    It was then simply never restarted for 19.7 h while the machine stayed awake.
    Relaunched by resume_all.bat at 02:04Z after its stale lock was swept; --status
    at resume confirmed the newest stamp was 1,184.8 min old and that the Round 76
    tags code is still live.
  affected_evaluations:
  - the tagged-stamp series restarts a new continuous segment from 02:04:39Z; the
    two-stream gate reports it on any unbounded check
  round: 128
  detected_utc: '2026-09-21T01:47:32Z'
  resolved_utc: '2026-09-21T02:04:39Z'
---
# Data gap: 2026-09-20_polymarket_drops_shutdown_awake_no_resume

> **19.75 h with no recording** - 2026-09-20T06:19:45Z to 2026-09-21T02:04:39Z (desk 3). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Same shutdown as 2026-09-20_hl_shutdown_awake_no_resume. The watcher was stopped cleanly at 06:21Z through its own `polymarket_fetcher --stop` CLI (pid 24528 terminated, lock swept) rather than by the window-title filter, which cannot match a detached pythonw - the first live use of the ratified shutdown fix (a). It was then simply never restarted for 19.7 h while the machine stayed awake. Relaunched by resume_all.bat at 02:04Z after its stale lock was swept; --status at resume confirmed the newest stamp was 1,184.8 min old and that the Round 76 tags code is still live.

## Streams affected

- Sports_Desk/data/polymarket_drops stamped drops (last stamp polymarket_sports_20260920T061945Z, first new polymarket_macro_20260921T020439Z; 19.75 h with no stamp)

## Evaluations that touch this interval

- the tagged-stamp series restarts a new continuous segment from 02:04:39Z; the two-stream gate reports it on any unbounded check

## Detection and resolution

- detected 2026-09-21T01:47:32Z; resolved 2026-09-21T02:04:39Z
- resume_all.bat 09-20 22:04 EDT; first new stamps polymarket_macro_20260921T020439Z and polymarket_sports_20260921T020439Z, both written within 9 s of the watcher launching.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
