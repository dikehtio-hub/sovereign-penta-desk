---
type: Digest
title: Round 62 digest
description: 'Round 62: CROSS-MARKET DUTCH RECORDER, RECEIPT READER TOLERANCE, COMPACT
  CALIBRATION REPORT'
tags:
- digest
- work-chain
- round-62
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-62-complete
  title: AGENTS.md - Round 62 complete
  author: claude-code/fable-5.1
dev:
  round: 62
  date: null
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 62 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 62 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

CROSS-MARKET DUTCH RECORDER, RECEIPT READER TOLERANCE,

COMPACT CALIBRATION REPORT. New cross_market/execution_log.py: record_dutch()
writes the Polymarket leg as an execution receipt (strategy dutched_arb, venue
polymarket, ONE shared timestamp, notes carry arb_group / gross / cost / legs /
book_leg) and the sportsbook leg into Sports_Desk placed_bets (bet_kind
arbitrage, same arb_group); never raises; CLI `python -m
cross_market.execution_log --pm-market ... --book ... --odds ... --stake ...`
for today's manual executions, exit 0 complete / 1 incomplete / 2 refused.
risk_simulator._measure_arb_history reads fills_*_dutched_arb*.csv (any
venue), groups by arb_group note first and a 60 s timestamp window second,
prices from a gross: note (cost: for capital) before falling back to
1/sum(BUY prices) - 1. --calibration-report shows the last 7 daily rows per
coin (--last-days N, --all). 7 new tests; master suite is 18 modules. Live:
still no receipts, no settled wagers, 3 usable days per coin.

## Related

- [[digests_register|Digests register]]
