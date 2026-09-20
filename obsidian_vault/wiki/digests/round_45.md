---
type: Digest
title: Round 45 digest
description: 'Round 45: PER-FIELD CONFIG FALLBACK FOR EVERY FIELD & UNCLASSIFIED-DEX
  FAIL-CLOSED'
tags:
- digest
- work-chain
- round-45
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-45-complete
  title: AGENTS_ARCHIVE.md - Round 45 complete
  author: claude-code/fable-5.1
dev:
  round: 45
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 45 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 45 digest

> date not recorded in the log · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

PER-FIELD CONFIG FALLBACK FOR EVERY FIELD & UNCLASSIFIED-DEX

FAIL-CLOSED. Every Bot_Config field now parses on its own through
`_config_number` / `_config_int` / `_config_flag`: a corrupt value warns and
takes that field's default while its neighbours load; the whole-file kill-switch
path fires only when the note cannot be read or yields no fields. The two safety
flags fail ARMED on a malformed value (deviation, see findings).
`UNCLASSIFIED_DEXES` (vntl, hyna, abcd) is documented as excluded from
ACTIVE_DEXES and `spot_symbol_candidates` returns [] for a perp on one, with no
runtime switch. 3 new tests.

## Related

- [[digests_register|Digests register]]
