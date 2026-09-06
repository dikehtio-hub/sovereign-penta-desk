---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py'
description: "After a forced-sell cascade the fade buys, betting on a snapback. For\
  \ every historical event we measure, over a forward window:\n\n MFE = maximum favourable\
  \ excursion (how far it moved our way) MAE = maximum adverse excursion (how far\
  \ it moved against us)\n\n MFE/MAE >= 1.50 means th…"
tags:
- concept
- thesis
- desk-1
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py
  title: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py
  headings:
  - THE QUESTION
  - WHY THERE IS A CONTROL, AND WHY THE NUMBER IS MEANINGLESS WITHOUT ONE
  - TWO EVENT SOURCES, AND ONLY ONE IS THE STRATEGY'S
  - MEASUREMENT NOTES
  asserts:
  - file: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py
    pattern: THE\ QUESTION
    claim: the docstring still carries the section 'THE QUESTION'
  - file: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py
    pattern: WHY\ THERE\ IS\ A\ CONTROL,\ AND\ WHY\ THE\ NUMBER\ IS\ MEANINGLESS\
      WITHOUT\ ONE
    claim: the docstring still carries the section 'WHY THERE IS A CONTROL, AND WHY
      THE NUMBER IS MEANINGLESS WITHOUT ONE'
  - file: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py
    pattern: TWO\ EVENT\ SOURCES,\ AND\ ONLY\ ONE\ IS\ THE\ STRATEGY'S
    claim: the docstring still carries the section 'TWO EVENT SOURCES, AND ONLY ONE
      IS THE STRATEGY'S'
  - file: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py
    pattern: MEASUREMENT\ NOTES
    claim: the docstring still carries the section 'MEASUREMENT NOTES'
  requires_files:
  - HyperLiquid/HL_Monarch/analytics/wick_benchmark.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/analytics/wick_benchmark.py

> 4 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Question

After a forced-sell cascade the fade buys, betting on a snapback. For every historical event we measure, over a forward window:

 MFE = maximum favourable excursion (how far it moved our way) MAE = maximum adverse excursion (how far it moved against us)

 MFE/MAE >= 1.50 means the signal genuinely leads to asymmetric moves. MFE/MAE ~= 1.00 means it does not, and the fade thesis should be retired.

## Why There Is A Control, And Why The Number Is Meaningless Without One

A driftless random walk produces MFE/MAE ~= 1.00 by construction, so 1.00 is the null - but only if nothing else biases the measurement. Sampling gaps, uneven snapshot density around volatile moments, and the trending tape all shift the ratio on their own. So every run also measures RANDOM entries on the same coins over the same window lengths. The signal's edge is the DIFFERENCE between the two, not the raw ratio. A signal scoring 1.20 against a control of 1.20 has no edge whatsoever, and reporting the 1.20 alone would have looked like a partial success.

## Two Event Sources, And Only One Is The Strategy'S

trade_sweep - the cascade detector the fade actually trades. ~476 events. trade_flow - ANY fill >= $50k, liquidation or not. ~9,353 events, and mostly plain whale orders. It is reported separately because averaging the two would let the larger, contaminated set dominate and answer a question nobody asked.

## Measurement Notes

* Excursions are measured from the MARK at event time, not from the fade's limit price. That isolates the SIGNAL from the execution geometry, which is the whole point - the limit may never fill, and a filled entry sits at a better price, which would flatter MFE. * Ratios are aggregated as mean(MFE)/mean(MAE), not mean(MFE/MAE). Per-event ratios explode when MAE is near zero, and averaging them would let a handful of quiet events dominate the result. * Events whose forward window is not covered by snapshots are DROPPED, not zero-filled. Coverage is reported so a thin result cannot masquerade as a clean one.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
