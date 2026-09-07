---
type: Digest
title: Round 118 digest
description: 'Round 118 (2026-09-06): A BAD TOKEN IS NOW AN ERROR ON THE PAGE, NOT
  A MISSING PAGE; SCRATCH KEEPS THREE RUNS; THE SCHEDULER PROBE IS WRITTEN FOR THE
  OPERATOR'
tags:
- digest
- work-chain
- round-118
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T00:20:00Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-118-complete
  title: AGENTS.md - Round 118 complete
  author: claude-code/fable-5.1
dev:
  round: 118
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 118 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 118 digest

> 2026-09-06 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

A BAD TOKEN IS NOW AN ERROR ON THE PAGE, NOT A MISSING PAGE; SCRATCH

KEEPS THREE RUNS; THE SCHEDULER PROBE IS WRITTEN FOR THE OPERATOR. D1 (R116-1.D, DEVIATION): the directive
said reject a rules registration whose market ids are not all digits. A refused registration is an absent
page - the silence pattern of Rounds 108-116 - so the adapter compiles the page anyway, records the
offenders under dev.invalid_tokens, and new lint C6 makes it an ERROR naming the token. The live rehearsal
already refuses to record on the same condition. The fixture's four TOK_* tokens (27 uses) became 76-digit
numerics, which is what let this be tested at all. D2 (R116-1.E): fomc_live_rehearsal prunes default
run dirs under cross_market/data/rehearsals/ to the newest 3; probe_* and any --scratch are never touched;
reported as a check. D3 (R116-1.F): cross_market/scripts/probe_scheduled_task.ps1 registers a one-off
Monarch_Rehearsal_Probe with the drill task's shape (current user, interactive, default battery flags),
fires in 2 min running the TRACKED batch with 20 s and a probe_<stamp> scratch books dir, waits, reports
LastTaskResult and stamp count (~60), unregisters itself; -WhatIf registers nothing. Parsed clean and
-WhatIf-run; the REAL run is the operator's (checklist). Tests: knowledge 342. Lint CLEAN. NO DAEMON
RESTARTED.

## Related

- [[digests_register|Digests register]]
