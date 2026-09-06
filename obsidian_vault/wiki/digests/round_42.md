---
type: Digest
title: Round 42 digest
description: 'Round 42: PERP-LEVEL TRADFI QUARANTINE, ILLIQUID-LEG SWEEP & 10x ADV
  FLOOR'
tags:
- digest
- work-chain
- round-42
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-42-complete
  title: AGENTS.md - Round 42 complete
  author: claude-code/fable-5.1
dev:
  round: 42
  date: null
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 42 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 42 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

PERP-LEVEL TRADFI QUARANTINE, ILLIQUID-LEG SWEEP & 10x ADV

FLOOR. `ALLOW_SYNTHETIC_TRADFI_BASIS = False` with `SYNTHETIC_TRADFI_SYMBOLS`
(the ruled set plus every TradFi base observed live across the cash/flx/km/xyz/
para dexes): a quarantined perp has NO spot candidates - bare, wrapper or alias.
SPX -> UUUSPX ("Unit SPX6900", the memecoin). `BasisHarvester.sweep_illiquid_
exits` closes positions whose spot leg is under the floor or whose perp is
quarantined; hooked into the hourly accrual cycle and `basis --sweep-illiquid`
(refuses while a service collector is alive). The three dead-leg paper positions
were swept with the service stopped. Floor multiple 5x -> 10x ($100k at $10k).
3 new tests.

## Related

- [[digests_register|Digests register]]
