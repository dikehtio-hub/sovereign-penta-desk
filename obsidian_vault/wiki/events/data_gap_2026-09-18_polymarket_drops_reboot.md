---
type: Event
title: 'Data gap: 2026-09-18_polymarket_drops_reboot'
description: '0.68 h with no recording in Sports_Desk/data/polymarket_drops stamped
  drops: 2026-09-18T01:24:44Z to 2026-09-18T02:05:34Z. Round 128.'
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
    start: '2026-09-18T01:24:44Z'
    end: '2026-09-18T02:05:34Z'
  gap_hours: 0.68
  tables:
  - Sports_Desk/data/polymarket_drops stamped drops (last stamp polymarket_macro_20260918T012444Z,
    first new polymarket_macro_20260918T020534Z; 0.68 h with no stamp)
  cause: 'Same reboot as 2026-09-18_hl_reboot: the watcher died at 01:30Z and was
    relaunched by resume_all.bat at 02:05Z (22:05 EDT 09-17).'
  affected_evaluations:
  - 'none registered: the tagged-stamp series restarts a new continuous segment from
    02:05:34Z'
  round: 128
  detected_utc: '2026-09-18T20:15:00Z'
  resolved_utc: '2026-09-18T02:05:34Z'
---
# Data gap: 2026-09-18_polymarket_drops_reboot

> **0.68 h with no recording** - 2026-09-18T01:24:44Z to 2026-09-18T02:05:34Z (desk 3). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

Same reboot as 2026-09-18_hl_reboot: the watcher died at 01:30Z and was relaunched by resume_all.bat at 02:05Z (22:05 EDT 09-17).

## Streams affected

- Sports_Desk/data/polymarket_drops stamped drops (last stamp polymarket_macro_20260918T012444Z, first new polymarket_macro_20260918T020534Z; 0.68 h with no stamp)

## Evaluations that touch this interval

- none registered: the tagged-stamp series restarts a new continuous segment from 02:05:34Z

## Detection and resolution

- detected 2026-09-18T20:15:00Z; resolved 2026-09-18T02:05:34Z
- resume_all.bat; stamps resumed at the 5-minute cadence. Registered retroactively 09-18.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
