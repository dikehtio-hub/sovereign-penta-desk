---
type: Digest
title: Round 44 digest
description: 'Round 44: TRADFI_DEXES GAINS mkts AND io; CONFIG CLAMP FLOOR $10k; MALFORMED
  FIELDS FALL BACK WITH A WARNING'
tags:
- digest
- work-chain
- round-44
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-44-complete
  title: AGENTS.md - Round 44 complete
  author: claude-code/fable-5.1
dev:
  round: 44
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 44 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 44 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

TRADFI_DEXES GAINS mkts AND io; CONFIG CLAMP FLOOR $10k;

MALFORMED FIELDS FALL BACK WITH A WARNING. `TRADFI_DEXES` now covers xyz, km,
cash, flx, mkts (Markets By Kinetiq) and io (EntropyIO pre-IPO equities), all
verified against the live perpDexs payload. `spot_min_day_volume` clamps to
$10k minimum; a Bot_Config field that will not parse falls back to its settings
default with a logged warning instead of failing the whole reload. The
Penta-Desk header was already in place from Round 43. 1 new test, 1 extended.

## Related

- [[digests_register|Digests register]]
