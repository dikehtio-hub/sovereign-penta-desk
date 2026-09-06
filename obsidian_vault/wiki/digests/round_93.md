---
type: Digest
title: Round 93 digest
description: 'Round 93 (2026-09-05): RULING R2 INSTRUMENT + FOMC RULES REGISTERED'
tags:
- digest
- work-chain
- round-93
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:14:48Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-93-complete
  title: AGENTS.md - Round 93 complete
  author: claude-code/fable-5.1
dev:
  round: 93
  date: '2026-09-05'
  kind: round_digest
---
# Round 93 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

RULING R2 INSTRUMENT + FOMC RULES REGISTERED.

latency_sniper.record_loop() / CLI --record-loop --tokens T[,..] --interval 1
--duration 420 [--books DIR]: one read-only GET per token per interval,
sleeping interval minus fetch time; stops at the duration, on HALT.flag
(exit 3) or Ctrl-C; an HTTP 429 is counted and answered with a growing
pause (5 s x n, max 30 s). cross_market/experiments/fomc_2026-09-16.rules.json
PRE-REGISTERED with the REAL YES token ids from the 2026-09-05 macro drop:
no change (== 0), hike 25 (== 25), hike 50+ (>= 50); the two cut markets do
not exist in the drop today and are listed under not_found_in_drop (may be
APPENDED before the window in a dated re-registration, never edited inside
T-2..T+5). Event schema: kind fed_rate, payload.change_bps int, confidence
>= 0.99 only from the statement itself. All three markets are neg_risk:
YES side only (R4). Tests: module 21 now 13. Daemons and tonight's tasks
untouched. THE DRILL COMMAND for 2026-09-16 17:58Z:
  python -m cross_market.latency_sniper --record-loop --tokens <the three token ids from the rules file> --interval 1 --duration 420

## Related

- [[digests_register|Digests register]]
