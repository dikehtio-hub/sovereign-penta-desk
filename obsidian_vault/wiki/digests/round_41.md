---
type: Digest
title: Round 41 digest
description: 'Round 41: SYNTHETIC EQUITY QUARANTINE, DYNAMIC SPOT FLOOR, ILLIQUID-LEG
  REPORTING & UNMAPPED-SPOT TELEMETRY'
tags:
- digest
- work-chain
- round-41
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-41-complete
  title: AGENTS.md - Round 41 complete
  author: claude-code/fable-5.1
dev:
  round: 41
  date: null
  kind: round_digest
---
# Round 41 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

SYNTHETIC EQUITY QUARANTINE, DYNAMIC SPOT FLOOR, ILLIQUID-LEG

REPORTING & UNMAPPED-SPOT TELEMETRY. Tokenised equities (NVDAX, TSLAX, EQ*)
live in `SYNTHETIC_EQUITY_ALIASES` and are ignored while
`ALLOW_SYNTHETIC_EQUITY_BASIS = False`; the spot floor is
`effective_spot_min_volume() = max($50k, 5 x basis_notional_usd)`; the "U"
wrapper now outranks the bare name on ties and in no-volume calls; the paper
book tags positions whose spot leg is under the floor `[ILLIQUID SPOT]` (three
of five live); `python main.py basis --unmapped-spot` lists liquid spot tokens
no perp resolves to (13 live). 4 new tests.

## Related

- [[digests_register|Digests register]]
