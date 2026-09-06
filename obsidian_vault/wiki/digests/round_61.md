---
type: Digest
title: Round 61 digest
description: 'Round 61: PER-COIN SHOCK MEDIANS, CALENDAR-DAY CADENCE, ARB RECEIPT
  HISTORY, --calibration-report'
tags:
- digest
- work-chain
- round-61
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-61-complete
  title: AGENTS.md - Round 61 complete
  author: claude-code/fable-5.1
dev:
  round: 61
  date: null
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 61 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 61 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

PER-COIN SHOCK MEDIANS, CALENDAR-DAY CADENCE, ARB RECEIPT

HISTORY, --calibration-report. stress_calibration() judges each held perp
against its OWN median daily vol (shock = > 3x it), qualifies a coin at >= 14
distinct days, and averages shock probability / multiplier over qualifying
coins (Ruling 61-1). Sports cadence = settled / calendar days spanned
(Ruling 61-3). _measure_arb_history reads fills_polymarket_dutched_arb*.csv
receipts in Tax_Reserve_Agent/data/imports (+ processed/): fills sharing a
timestamp are one execution, >= 2 BUY legs price a dutch (1/sum - 1), >= 10
fills replace arb_per_day / gross return / std / capital, else "assumed (< 10
arb fills)". `python -m cross_market.risk_simulator --calibration-report
[--json]` prints the per-coin daily vol table with shock days, the sports
settlement line and the arb receipt line for auditing before the 14-day mark.
3 new tests. Live: no coin qualifies yet (4 days), no settled wagers, no arb
receipts - every calibration says so.

## Related

- [[digests_register|Digests register]]
