---
type: Digest
title: Round 109 digest
description: 'Round 109 (2026-09-06): THE WORK CHAIN IS ADDRESSABLE, AND THE PRE-REGISTERED
  RULES NOW HAVE A GUARD ON BOTH COPIES'
tags:
- digest
- work-chain
- round-109
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-109-complete
  title: AGENTS.md - Round 109 complete
  author: claude-code/fable-5.1
dev:
  round: 109
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 109 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 109 digest

> 2026-09-06 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE WORK CHAIN IS ADDRESSABLE, AND THE PRE-REGISTERED RULES

NOW HAVE A GUARD ON BOTH COPIES. B5: knowledge/ingest/digests.py compiles one Digest page per
round from this log - 63 of them - so answering "what happened in Round 97?" is a lookup
rather than a scan of 210 KB. THE LOG REMAINS THE RECORD; the digests cite it and lose to it.
R108-1.E: lint C1 now compares `dev.rules` against the raw registration JSON field by field, so
the second copy Round 108 created cannot drift - a token id that slips there is the card
telling an operator to trade a different market than the one registered before the data was
seen. The compiler and the checker SHARE one transform, because two transcriptions would drift
exactly the way the check exists to catch. R108-1.D: Event pages declare `dev.books_dir` and
the card reads it instead of constructing a path. Tests: knowledge 202 (+26), all green
offline. Vault 487 pages (+64), lint CLEAN. NO DAEMON RESTARTED.

## Related

- [[digests_register|Digests register]]
