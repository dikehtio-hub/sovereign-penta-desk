---
type: Digest
title: Round 115 digest
description: 'Round 115 (2026-09-06): THE WHALE-SWEEPER REPLAY WAS RE-RUN AND IS STILL
  INSUFFICIENT - BY 0.20 POINTS, ON THE ROWS THE ENGINE ACTUALLY COUNTS; THE ENGINE
  GATE NOW CHECKS THE COVERED SPAN; DESK 4 CONSTRUCTS FROM ANY DIRECTORY'
tags:
- digest
- work-chain
- round-115
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T22:51:24Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-115-complete
  title: AGENTS.md - Round 115 complete
  author: claude-code/fable-5.1
dev:
  round: 115
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 115 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 115 digest

> 2026-09-06 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE WHALE-SWEEPER REPLAY WAS RE-RUN AND IS STILL INSUFFICIENT - BY

0.20 POINTS, ON THE ROWS THE ENGINE ACTUALLY COUNTS; THE ENGINE GATE NOW CHECKS THE COVERED SPAN;
DESK 4 CONSTRUCTS FROM ANY DIRECTORY. D1 (R114-1.B/D): analytics/cascade_replay.py re-run over
38,016 rows into data/experiments/whale_sweeper_cascade_replay.verdict.json (tracked, beside the
registration; the knowledge adapter's default and its test fixture moved with it). Qualifying rows
(complete 60-minute forward series) 18,669 on 62 coins, top coin ZEC 20.20% against a 20%
ceiling, HHI 0.1334 - SAMPLE_TOO_NARROW; ratio_30m 0.9029, P(>= 1.25) = 0.1167 had it qualified
(RETUNE band, stated, not a verdict). Page and engine agree: INSUFFICIENT. THE LESSON: Round 114's
mirror counted every treatment row (ZEC 19.84%, `ready`); the registration requires
min_samples_60m_per_event >= 1 and its engine filters on it; over those rows ZEC is over the line.
The mirror now applies that requirement, so the whale page reads ACCUMULATING (share 20.08%)
and names the blocker instead of promising a re-run L11 would have demanded. The whale registration
also carries a dated `population: pooled` block (R114-1.A brainstorm item 8) and the mirror treats
`pooled`/`all` as pooled. D2 (R114-1.F): wick_benchmark.benchmark() reports `span_days` and
_reopening_sample_gate fails closed without it and fails on a span under the window; the fade
runner passes its span in and no longer duplicates the check; cascade_replay.py was NOT changed -
its registration binds no window, so a span gate there would be unregistered. D3: RiskSentinel's
two constructor defaults anchored to the desk root; committed in the nested repo from a blob built
from HEAD plus those lines only (the other agent's three uncommitted hunks in the same file stay
theirs). From the workspace root Desk 4 goes 73 failed -> 2 failed, both in the other agent's
UNTRACKED tests/test_tax_bankroll_integration.py, which hard-codes a relative config path itself.
Tests: knowledge 303, HL 1110, Desk 4 151 from its directory. Lint CLEAN, idempotent.
NO DAEMON RESTARTED.

## Related

- [[digests_register|Digests register]]
