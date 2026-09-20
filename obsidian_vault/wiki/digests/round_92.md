---
type: Digest
title: Round 92 digest
description: 'Round 92 (2026-09-05): OPTION 2 - DEPTH REPORT OVER REAL BOOKS'
tags:
- digest
- work-chain
- round-92
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-92-complete
  title: AGENTS_ARCHIVE.md - Round 92 complete
  author: claude-code/fable-5.1
dev:
  round: 92
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 92 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 92 digest

> 2026-09-05 · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

OPTION 2 - DEPTH REPORT OVER REAL BOOKS.

latency_sniper.depth_report(book, outcome, confidence, breakeven) walks a
recorded book best-first and reports, per level, price (NO: 1 - bid),
fee-adjusted odds, the after-tax breakeven, edge/share and cumulative
shares / notional / VWAP - no cap: the upper bound the book offers before
anyone pulls; NO on a neg_risk book is deferred (Ruling R4). CLI:
latency_sniper --depth-report --books DIR [--confidence 0.995]
[--assume-defaults] [--json]; uses the Tax Reserve Agent breakeven when the
hook loads. MEASUREMENT: 8 live stamps recorded (4 thin Fed-governance
markets, 4 thick: two BTC-dip, two FOMC neg_risk) into
cross_market/data/clob_books/ (ignored). With the outcome known at 0.995
EVERY level below ~0.99 clears the after-tax breakeven, so the "fillable"
upper bound is simply the resting depth: thin books offer $400-$3,300 of
YES depth (15-29 levels) and $1.3k-$41k of NO depth; thick books offer
$50k-$3M. The number that matters is therefore not depth at rest but how
many seconds it survives after the print - which only Ruling R2's T-2/T+5
recording at the 2026-09-16 FOMC can measure. Registry extent corrected:
the Top 20 spans lines 80-484 (Items 19 and 20 at ~447 and ~465), not
80-415; the docs scripts' byte-identical check now covers 80-484. Tests:
module 21 now 12. Daemons and tonight's tasks untouched.

## Related

- [[digests_register|Digests register]]
