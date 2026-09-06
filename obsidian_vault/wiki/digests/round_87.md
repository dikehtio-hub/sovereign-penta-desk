---
type: Digest
title: Round 87 digest
description: 'Round 87 (2026-09-05): ITEM 12 PHASE 1 - OFFLINE ENGINE + MEASUREMENT
  INSTRUMENT (registry line 273, not 181 as the prompt said)'
tags:
- digest
- work-chain
- round-87
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-87-complete
  title: AGENTS.md - Round 87 complete
  author: claude-code/fable-5.1
dev:
  round: 87
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 87 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 87 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

ITEM 12 PHASE 1 - OFFLINE ENGINE + MEASUREMENT

INSTRUMENT (registry line 273, not 181 as the prompt said). NEW
cross_market/latency_sniper.py: pre-registered RULES map an event payload to
one market's YES/NO (kind + field + op + value; a numeric rule needs a
numeric payload, anything else says nothing); a CLOB BOOK snapshot is walked
best-first taking each level only while the event's confidence clears the
Tax Reserve Agent's after-tax BREAKEVEN at that level's fee-adjusted odds
(hook.after_tax_edge_hurdle), capped by quarter-Kelly of the safe bankroll
and hook.max_position_size; a NO outcome hits YES bids at (1 - bid).
Fail-closed: HALT.flag refuses everything (exit 3), confidence < 0.99
refuses everything, a book older than 10 s or from the future is skipped,
a market without a rule is never touched. The ONLY execution is PAPER
receipts (strategy latency_sniper, paper:1) under
cross_market/data/paper_receipts; there is no live path in the module.
`--record --tokens` stamps CLOB depth (the one read-only GET) into
cross_market/data/clob_books/ (ignored) so the roadmap's "10-50% per event"
can be MEASURED by replaying rules against stamps (`--now`) before anything
else is built. Sample rules with placeholder tokens:
cross_market/experiments/sniper_rules.sample.json. Tests: master MODULE 21
(9 tests, no network). Daemons and tonight's tasks untouched.

## Related

- [[digests_register|Digests register]]
