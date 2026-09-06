---
type: Digest
title: Round 34 digest
description: 'Round 34: INCREMENTAL PERSISTENCE & DATA INGESTION'
tags:
- digest
- work-chain
- round-34
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-34-complete
  title: AGENTS.md - Round 34 complete
  author: claude-code/fable-5.1
dev:
  round: 34
  date: null
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 34 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 34 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

INCREMENTAL PERSISTENCE & DATA INGESTION. The pruner now

reduces raw rows to `basis_realised_windows` and `cascade_excursions` BEFORE
deleting them (never pruned; Ruling D's 720h standard is now reachable);
Polymarket sports questions flow into `Sports_Desk/data/polymarket_drops/`
(`Cross_Market_Arb.md` shows 6 matched pairs, 0 clearing); the odds fetcher
polls and drops only on price change; `Canvases/Sovereign_Penta_Cockpit.canvas`
renders all six notes around the tax reserve. **The collector was restarted** -
it had been pruning at 72h for 15 hours after Round 33 said 192 (see findings).
58 new tests.

## Related

- [[digests_register|Digests register]]
