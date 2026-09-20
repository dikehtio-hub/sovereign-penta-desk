---
type: Digest
title: Round 38 digest
description: 'Round 38: SPOT-GROUNDED CANDIDATES, SPREAD CEILING & CONCENTRATION GUARD'
tags:
- digest
- work-chain
- round-38
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-38-complete
  title: AGENTS_ARCHIVE.md - Round 38 complete
  author: claude-code/fable-5.1
dev:
  round: 38
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 38 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 38 digest

> date not recorded in the log · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

SPOT-GROUNDED CANDIDATES, SPREAD CEILING & CONCENTRATION

GUARD. Funding candidates for the spread sampler are now decided by
`spot_symbol_for` against the live spot universe (the ':' prefix rule was wrong
both ways) and pre-filtered by the OI/volume floors; the basis spread ceiling
now reaches every costed row in the scan AND the harvester's own gate (para:AVGO
had entered at 35 bps against 25); one paper position per spot symbol
(para:AVGO + xyz:AVGO were both hedged with AVGO); the stalled-service threshold
is derived from REST_POLL_INTERVAL with a 45s floor; Bot_Config.md's preset label
is "custom" to match its 5 slots. 12 new tests.

## Related

- [[digests_register|Digests register]]
