---
type: Digest
title: Round 94 digest
description: 'Round 94 (2026-09-05): SURVIVAL-CURVE HARNESS + FOMC DRILL SCHEDULED'
tags:
- digest
- work-chain
- round-94
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-94-complete
  title: AGENTS.md - Round 94 complete
  author: claude-code/fable-5.1
dev:
  round: 94
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 94 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 94 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

SURVIVAL-CURVE HARNESS + FOMC DRILL SCHEDULED.

latency_sniper --survival-curve --event event.json --rules
cross_market\experiments\fomc_2026-09-16.rules.json --books DIR [--step-seconds 1]
[--assume-defaults] [--json]: EVERY stamp of a --record-loop drill (not the newest
per token) replayed through the uncapped depth walk for each market the rules
resolve, indexed by seconds from the event's observed_at (the rules file's
release_utc is printed beside it with the lag). Per market a summary: pre-print
baseline notional, the first post-print second the book changed (CLOB hash, else
the levels), seconds to half and to a tenth of baseline, seconds until nothing
clears, and dollar-seconds of fillable notional after the print (size x
survival). Uncapped on purpose - a Kelly-capped figure sits flat at the cap and
hides the decay. Neg_risk NO sides deferred (R4). Exit 1 = no stamps for the
rules' tokens. THE DRILL IS SCHEDULED: Windows task Monarch_FOMC_Drill fires
2026-09-16 13:58 EDT (= 17:58Z, T-2 min) and runs
cross_market\data\fomc_drill_2026-09-16.bat (operator file, untracked, CRLF):
record-loop on the three registered tokens, 1 s x 420 s, into
cross_market\data\clob_books\fomc_2026-09-16\, log
cross_market\data\fomc_drill_2026-09-16.log. Dry run today (3 s) wrote 9
stamps and the curve replayed them end to end with the Tax Reserve Agent
breakeven. LAPTOP ON AND LOGGED IN at 13:58 EDT on the 16th. After the print the
operator writes event.json {kind fed_rate, payload.change_bps <int from the
statement>, source, confidence >= 0.99, observed_at} and runs the curve.
Docs defect fixed: MASTER_COMMAND_LIST.txt's "Last Update" header had said Round
72 since 9fd5ef1 - the docs scripts replaced a string that was not there, and a
silent replace is a no-op; the script now asserts the anchor. Tests: module 21
now 14. Daemons and tonight's tasks untouched.

## Related

- [[digests_register|Digests register]]
