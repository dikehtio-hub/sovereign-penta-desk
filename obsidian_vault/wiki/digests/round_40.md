---
type: Digest
title: Round 40 digest
description: 'Round 40: SPOT ALIASES, LIQUIDITY-MAXIMISING HEDGE SELECTION & SPOT
  DECIMALS FIX'
tags:
- digest
- work-chain
- round-40
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-40-complete
  title: AGENTS.md - Round 40 complete
  author: claude-code/fable-5.1
dev:
  round: 40
  date: null
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 40 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 40 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

SPOT ALIASES, LIQUIDITY-MAXIMISING HEDGE SELECTION & SPOT

DECIMALS FIX. `SPOT_SYMBOL_ALIASES` (hand-kept, verified against live
fullNames) lets `spot_symbol_for` see wrappers that are not "U" + name (UFART,
XMR1, NVDAX...); with `spot_volumes` it picks the MOST LIQUID of several hedges
(para:ANSEM -> UANSEM $928k/day, not ANSEM $1.5k); the spot leg's szDecimals
is now read for the spot symbol itself (every wrapped hedge came back None
before); SPOT_MIN_DAY_VOLUME raised to $50k (32 of 499 tokens). The paper
state's para:ANSEM spot leg was rewritten to UANSEM while the service was
stopped. 3 new tests.

## Related

- [[digests_register|Digests register]]
