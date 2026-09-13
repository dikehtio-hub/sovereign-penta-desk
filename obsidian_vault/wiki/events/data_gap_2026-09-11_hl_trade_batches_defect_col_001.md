---
type: Event
title: 'Data gap: 2026-09-11_hl_trade_batches_defect_col_001'
description: '48.33 h with no recording in trades, liquidation_events: 2026-09-11T16:37:01Z
  to 2026-09-13T16:56:47Z. Round 128.'
tags:
- event
- data-gap
- desk-1
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
  desk: 1
  window:
    start: '2026-09-11T16:37:01Z'
    end: '2026-09-13T16:56:47Z'
  gap_hours: 48.33
  tables:
  - 'trades (OPEN, PARTIAL: 181 flush batches discarded to date - 4,963 rows on 09-11,
    5,460 on 09-12, 14,943 on 09-13 (14,226 before the sleep, 717 after the 16:45Z
    restart) - about 1 % of the ~60,000 trades an hour the feed records; each loss
    is a 10-second batch, unrecoverable)'
  - 'liquidation_events (OPEN, PARTIAL: 99 events discarded in the same batches -
    46 / 11 / 42 by day; unrecoverable)'
  - orderbook_snapshots (45 sampling passes failed on the same lock; the 30-second
    cadence resumes on the next pass)
  - whale_wallets (37 persist failures on the same lock)
  - 'asset_snapshots (NOT affected: the 1 s price stream writes on a separate path
    and shows no hole in this interval outside the registered sleep gaps)'
  cause: DEFECT-COL-001 (Antigravity Section 57). Every ~7 minutes storage/repository.py
    prune_old_data runs five DELETEs in one transaction on the 8.1 GB database and
    run_maintenance follows with checkpoint(TRUNCATE); the exclusive lock outlasts
    the 30-second busy_timeout every connection already sets, so the flush thread's
    write fails with 'database is locked'. collectors/market_collector.py _flush_loop
    swaps the trade and liquidation buffers out BEFORE writing and only logs on failure
    (~line 351), so the swapped batch is dropped. First failed flush 2026-09-11 12:37:01
    EDT, 86 seconds before the first logged maintenance pass; clusters of lock errors
    precede each pass since. Errors continue after the 09-13 restart (2 batches, 717
    trades, at 16:55-16:56Z). Found in the 2026-09-13 morning start check; recorded
    nowhere before.
  affected_evaluations:
  - any evaluation over this interval that reads trades or liquidation_events - cascade_excursions
    and basis_realised_windows are persisted from those tables by storage/incremental_persistence
    - runs on streams missing ~1 % of trades and 99 liquidation events; asset_snapshots-based
    evaluations (Item 18 lead-lag, the FOMC drill) are unaffected
  round: 128
  detected_utc: '2026-09-13T16:55:00Z'
  resolved_utc: null
---
# Data gap: 2026-09-11_hl_trade_batches_defect_col_001

> **48.33 h with no recording** - 2026-09-11T16:37:01Z to 2026-09-13T16:56:47Z (desk 1). Any evaluation whose window overlaps this interval must say so; lint L12 checks.

## Cause

DEFECT-COL-001 (Antigravity Section 57). Every ~7 minutes storage/repository.py prune_old_data runs five DELETEs in one transaction on the 8.1 GB database and run_maintenance follows with checkpoint(TRUNCATE); the exclusive lock outlasts the 30-second busy_timeout every connection already sets, so the flush thread's write fails with 'database is locked'. collectors/market_collector.py _flush_loop swaps the trade and liquidation buffers out BEFORE writing and only logs on failure (~line 351), so the swapped batch is dropped. First failed flush 2026-09-11 12:37:01 EDT, 86 seconds before the first logged maintenance pass; clusters of lock errors precede each pass since. Errors continue after the 09-13 restart (2 batches, 717 trades, at 16:55-16:56Z). Found in the 2026-09-13 morning start check; recorded nowhere before.

## Streams affected

- trades (OPEN, PARTIAL: 181 flush batches discarded to date - 4,963 rows on 09-11, 5,460 on 09-12, 14,943 on 09-13 (14,226 before the sleep, 717 after the 16:45Z restart) - about 1 % of the ~60,000 trades an hour the feed records; each loss is a 10-second batch, unrecoverable)
- liquidation_events (OPEN, PARTIAL: 99 events discarded in the same batches - 46 / 11 / 42 by day; unrecoverable)
- orderbook_snapshots (45 sampling passes failed on the same lock; the 30-second cadence resumes on the next pass)
- whale_wallets (37 persist failures on the same lock)
- asset_snapshots (NOT affected: the 1 s price stream writes on a separate path and shows no hole in this interval outside the registered sleep gaps)

## Evaluations that touch this interval

- any evaluation over this interval that reads trades or liquidation_events - cascade_excursions and basis_realised_windows are persisted from those tables by storage/incremental_persistence - runs on streams missing ~1 % of trades and 99 liquidation events; asset_snapshots-based evaluations (Item 18 lead-lag, the FOMC drill) are unaffected

## Detection and resolution

- detected 2026-09-13T16:55:00Z; resolved None
- OPEN. Section 57 rules the fix for after the 2026-09-16 FOMC drill (daemon freeze): restore an unwritten batch to the head of its buffer on a transient write error, bounded by MAX_BUFFERED_TRADES / MAX_BUFFERED_LIQ_EVENTS; chunk the prunes into small transactions (Python's SQLite 3.45.3 is built without DELETE ... LIMIT, so chunk by rowid IN (SELECT rowid ... LIMIT n)); checkpoint PASSIVE or RESTART during collection. end_utc is the last measured failed flush and is extended when the fix deploys - this is an open gap, not a closed one.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[events_register|Events register]]
