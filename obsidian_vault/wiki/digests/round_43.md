---
type: Digest
title: Round 43 digest
description: 'Round 43: DEX-LEVEL TRADFI QUARANTINE, CANONICAL DUPLICATE GUARD, ONE
  VOLUME MAP PER CYCLE, VAULT FIX & HOT-RELOADED THRESHOLDS'
tags:
- digest
- work-chain
- round-43
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-43-complete
  title: AGENTS.md - Round 43 complete
  author: claude-code/fable-5.1
dev:
  round: 43
  date: null
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 43 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 43 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

DEX-LEVEL TRADFI QUARANTINE, CANONICAL DUPLICATE GUARD, ONE

VOLUME MAP PER CYCLE, VAULT FIX & HOT-RELOADED THRESHOLDS. `TRADFI_DEXES`
(xyz, km, cash, flx) quarantines whatever lists there; the symbol set covers
para: and main. `canonical_spot_base` makes ANSEM/UANSEM and FARTCOIN/UFART one
underlying for the duplicate guard, and the guard compares perp bases too. The
hourly cycle builds ONE engine whose volume map feeds the sweep, the scan and
the sampler cache. The Trading Terminal's closed-trades table read keys the
harvester never writes (every swept trade showed $0.00 / 0.0h) - fixed and the
vault refreshed. `allow_synthetic_tradfi_basis`, `spot_min_volume_notional_
multiple` and `spot_min_day_volume` are Bot_Config fields now. 6 new tests.

## Related

- [[digests_register|Digests register]]
