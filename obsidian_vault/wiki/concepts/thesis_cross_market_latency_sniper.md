---
type: Concept
title: 'Thesis: cross_market/latency_sniper.py'
description: No orders, no sockets except one read-only GET when the operator asks
  it to record order books.
tags:
- concept
- thesis
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: cross_market/latency_sniper.py
  title: cross_market/latency_sniper.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: cross_market/latency_sniper.py
  headings:
  - OFFLINE ENGINE AND MEASUREMENT INSTRUMENT
  - THE THESIS
  - WHAT THIS PHASE DOES
  - WHAT IT DOES NOT CLAIM
  asserts:
  - file: cross_market/latency_sniper.py
    pattern: OFFLINE\ ENGINE\ AND\ MEASUREMENT\ INSTRUMENT
    claim: the docstring still carries the section 'OFFLINE ENGINE AND MEASUREMENT
      INSTRUMENT'
  - file: cross_market/latency_sniper.py
    pattern: THE\ THESIS
    claim: the docstring still carries the section 'THE THESIS'
  - file: cross_market/latency_sniper.py
    pattern: WHAT\ THIS\ PHASE\ DOES
    claim: the docstring still carries the section 'WHAT THIS PHASE DOES'
  - file: cross_market/latency_sniper.py
    pattern: WHAT\ IT\ DOES\ NOT\ CLAIM
    claim: the docstring still carries the section 'WHAT IT DOES NOT CLAIM'
  requires_files:
  - cross_market/latency_sniper.py
  desk: 3
---
# Thesis: cross_market/latency_sniper.py

> 4 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Offline Engine And Measurement Instrument

No orders, no sockets except one read-only GET when the operator asks it to record order books.

## The Thesis

When a scheduled number prints (a Fed decision, a CPI release) or a race is called, some limit orders on the matching Polymarket markets rest at pre-news prices for a few seconds. Whoever resolves the market from the number first can take those orders at a near-certain edge.

## What This Phase Does

1. A pre-registered RULE maps an event payload to ONE market's outcome (YES/NO) with no interpretation at run time. A market without a rule is never touched; an event kind a rule does not know is ignored. 2. A BOOK (a CLOB depth snapshot) is walked from the best price outward. Each level is taken only while the outcome's confidence clears the Tax Reserve Agent's after-tax BREAKEVEN win probability at that level's fee-adjusted odds. 3. Size is capped by quarter-Kelly of the safe deployable bankroll and by the hook's per-order ceiling; the smaller wins. 4. HALT.flag refuses everything; confidence under 0.99 refuses everything; a book older than `max_book_age_s` is skipped (the orders are probably gone). 5. Fills are PAPER receipts under cross_market/data/paper_receipts tagged strategy `latency_sniper`. There is no live path in this module at all.

## What It Does Not Claim

The roadmap's "10-50% per event" is unmeasured. The first job of this engine is to measure it: `--record` stamps CLOB depth for the watched tokens around a scheduled release, and a replay of the rules against those stamps says what was actually there to take, and for how long. Round 94: `--survival-curve` replays the rules against every stamp of a `--record-loop` drill and reports that "for how long" second by second - the pre-print baseline, the first change, the seconds to half, a tenth and nothing, and the dollar-seconds of fillable notional after the print.

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
