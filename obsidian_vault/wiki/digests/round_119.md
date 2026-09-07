---
type: Digest
title: Round 119 digest
description: 'Round 119 (2026-09-06, INCIDENT, operator-authorised restart): THE HL
  COLLECTOR WROTE NO PRICE SNAPSHOT FOR 9 H 18 MIN AND NOTHING NOTICED'
tags:
- digest
- work-chain
- round-119
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T01:10:51Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-119-complete
  title: AGENTS.md - Round 119 complete
  author: claude-code/fable-5.1
dev:
  round: 119
  date: 2026-09-06, INCIDENT, operator-authorised restart
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 119 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 119 digest

> 2026-09-06, INCIDENT, operator-authorised restart · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE HL COLLECTOR WROTE NO PRICE

SNAPSHOT FOR 9 H 18 MIN AND NOTHING NOTICED. The operator asked for a check after their VPN flapped; the
VPN was innocent (one network event at 16:12 EDT; every daemon alive with its original start; Tier 2b
series unbroken, largest gap 5.1 min). The collector's market-context loop had logged `FOREIGN KEY
constraint failed` every 10 s since 11:46:21 EDT (3,300+ lines), and asset_snapshots' newest row was
11:46:10 EDT. Root cause: a coin newly listed on the exchange (`para:CIFR`, first snapshot 2026-09-07T01:04:32Z) had
no row in `assets`; the collector upserts assets ONCE at startup (`_sync_universe_metadata`, awaited
only from `run()`), snapshots are one batch per transaction, and `PRAGMA foreign_keys = ON` - so one
unknown coin failed every batch. The process never crashed, so the supervisor never restarted it;
coverage fell 66% -> 62% over the last hour as the only visible signal. The operator authorised the
restart: stop_collector.bat printed 'Terminating PID ...' and reported success WITHOUT KILLING ANYTHING
(cmd expands %VAR% at block-parse time, before `set /p` runs - an empty pid), deleted the pid files, and
start_collector.bat then launched a SECOND supervisor+collector pair against the same database; the old
pair was killed by PID (supervisor first). Result: supervisor 24504, collector 60756, 442 assets, 442
snapshots per pass, 0 FK errors, newest snapshot seconds old. stop_collector.bat fixed (delayed
expansion, supervisor first, reports 'no such process' instead of success) and tested offline against
bogus pids. NO OTHER DAEMON TOUCHED.

## Related

- [[digests_register|Digests register]]
