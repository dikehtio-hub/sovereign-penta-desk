---
type: Event
title: 'Data gap: 2026-09-19_polymarket_drops_shutdown_update_sleep'
description: '15.06 h with no recording in Sports_Desk/data/polymarket_drops stamped
  drops: 2026-09-19T02:26:05Z to 2026-09-19T17:29:34Z. Round 128.'
tags:
- event
- data-gap
- desk-3
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
  desk: 3
  window:
    start: '2026-09-19T02:26:05Z'
    end: '2026-09-19T17:29:34Z'
  gap_hours: 15.06
  tables:
  - Sports_Desk/data/polymarket_drops stamped drops (last stamp polymarket_sports_20260919T022605Z,
    first new polymarket_macro_20260919T172934Z; 15.06 h with no stamp)
  cause: 'Same night as 2026-09-19_hl_shutdown_update_sleep. The watcher''s last stamp
    is 02:26:05Z, 2.8 minutes before the collector''s clean stop at 02:28:52Z: shutdown_all.bat''s
    layer-2 stop is a taskkill /FI WINDOWTITLE filter that cannot match a detached
    pythonw process, so the watcher was stopped by PID (or died with the 02:29:54Z
    reboot) rather than by its own --stop CLI. Relaunched by resume_all.bat at 17:29Z
    after its stale lock was swept. NOT REGISTERED AT THE TIME - appended 2026-09-20
    from the stamps on disk.'
  affected_evaluations:
  - the tagged-stamp series restarts a new continuous segment from 17:29:34Z, which
    the two-stream gate reports on any unbounded check
  round: 128
  detected_utc: '2026-09-20T06:18:14Z'
  resolved_utc: '2026-09-19T17:29:34Z'
---
# Data gap: 2026-09-19_polymarket_drops_shutdown_update_sleep

> **15.06 h with no recording** - 2026-09-19T02:26:05Z to 2026-09-19T17:29:34Z (desk 3). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Same night as 2026-09-19_hl_shutdown_update_sleep. The watcher's last stamp is 02:26:05Z, 2.8 minutes before the collector's clean stop at 02:28:52Z: shutdown_all.bat's layer-2 stop is a taskkill /FI WINDOWTITLE filter that cannot match a detached pythonw process, so the watcher was stopped by PID (or died with the 02:29:54Z reboot) rather than by its own --stop CLI. Relaunched by resume_all.bat at 17:29Z after its stale lock was swept. NOT REGISTERED AT THE TIME - appended 2026-09-20 from the stamps on disk.

## Streams affected

- Sports_Desk/data/polymarket_drops stamped drops (last stamp polymarket_sports_20260919T022605Z, first new polymarket_macro_20260919T172934Z; 15.06 h with no stamp)

## Evaluations that touch this interval

- the tagged-stamp series restarts a new continuous segment from 17:29:34Z, which the two-stream gate reports on any unbounded check

## Detection and resolution

- detected 2026-09-20T06:18:14Z; resolved 2026-09-19T17:29:34Z
- resume_all.bat 09-19 13:29 EDT; first new stamp polymarket_macro_20260919T172934Z. 3,019 stamped drops on disk at the time of writing, spanning 2026-09-12T15:21:01Z to 2026-09-20T06:19:45Z under the 192 h retention.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
