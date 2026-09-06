---
type: Digest
title: Round 117 digest
description: 'Round 117 (2026-09-06, SELF-DIRECTED addendum, stopped at the authorisation
  boundary): the pre-flight gained `--online` - one read-only fetch of each registered
  token''s live book through latency_sniper.default_fetch (the browser User-Agent
  the CLOB requires), PASS only when the book echoes the same asset_id and has depth;
  a…'
tags:
- digest
- work-chain
- round-117
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T23:32:03Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-117-complete
  title: AGENTS.md - Round 117 complete
  author: claude-code/fable-5.1
dev:
  round: 117
  date: 2026-09-06, SELF-DIRECTED addendum, stopped at the authorisation boundary
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 117 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 117 digest

> 2026-09-06, SELF-DIRECTED addendum, stopped at the authorisation boundary · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

the

pre-flight gained `--online` - one read-only fetch of each registered token's live book through
latency_sniper.default_fetch (the browser User-Agent the CLOB requires), PASS only when the book echoes
the same asset_id and has depth; a 403, a timeout or a mismatched asset_id is a FAIL naming the token.
Offline by default, so nothing else changed. Real run: 30 checks, 0 FAIL, 3 WARN. This is the morning-of
command for the 16th: `python -m knowledge.drills.fomc_rehearsal --online`. EVERYTHING ELSE ON THE BOARD
NEEDS SOMEONE ELSE: the operator (W32Time, battery flags, collector restart window, Desk 4 packages, a
one-off scheduled task to prove the scheduler->batch chain) or Antigravity (rulings R115-1.A-E and
R116-1.A-E, including whether the token-shape check belongs at registration time and whether rehearsal
scratch dirs are pruned). Tests: knowledge 319 (+1). NO DAEMON RESTARTED.

## Related

- [[digests_register|Digests register]]
