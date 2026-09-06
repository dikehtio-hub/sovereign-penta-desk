---
type: Concept
title: 'Thesis: Polymarket/Polymarket_Monarch/dutched_arb.py'
description: "Both were found by running it.\n\n 1. EMPTY BOOKS INFLATE THE SUM INTO\
  \ NONSENSE. Illiquid long-tail outcomes quote bestAsk at or near 1.00 with no real\
  \ offer behind it. Summing those gives totals like 77.0 and 88.0 on real 128-outcome\
  \ election events. Worse, the failure is not symm…"
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
  resource: Polymarket/Polymarket_Monarch/dutched_arb.py
  title: Polymarket/Polymarket_Monarch/dutched_arb.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Polymarket/Polymarket_Monarch/dutched_arb.py
  headings:
  - TWO THINGS THAT MAKE THE NAIVE VERSION WRONG
  - EXPECT ZERO HITS
  asserts:
  - file: Polymarket/Polymarket_Monarch/dutched_arb.py
    pattern: TWO\ THINGS\ THAT\ MAKE\ THE\ NAIVE\ VERSION\ WRONG
    claim: the docstring still carries the section 'TWO THINGS THAT MAKE THE NAIVE
      VERSION WRONG'
  - file: Polymarket/Polymarket_Monarch/dutched_arb.py
    pattern: EXPECT\ ZERO\ HITS
    claim: the docstring still carries the section 'EXPECT ZERO HITS'
  requires_files:
  - Polymarket/Polymarket_Monarch/dutched_arb.py
  desk: 3
---
# Thesis: Polymarket/Polymarket_Monarch/dutched_arb.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Two Things That Make The Naive Version Wrong

Both were found by running it.

 1. EMPTY BOOKS INFLATE THE SUM INTO NONSENSE. Illiquid long-tail outcomes quote bestAsk at or near 1.00 with no real offer behind it. Summing those gives totals like 77.0 and 88.0 on real 128-outcome election events. Worse, the failure is not symmetric: a leg you cannot actually buy makes an event look un-arbable, while a leg with a stale thin ask can make one look arbable when the size is $3. Every leg is therefore required to have a genuine two-sided book before the event's sum is treated as meaningful at all.

 2. TOP-OF-BOOK IS NOT A TRADE. bestAsk is one price level. The real position is capped by the SMALLEST leg's depth - buy 500 of a 32-outcome event and you need 500 available on all 32 legs. A flagged event is therefore re-priced against the full CLOB book, walking each leg's asks to find the size actually executable and the true average cost. `--no-depth` skips this, and is only for eyeballing the distribution.

## Expect Zero Hits

A 4%+ risk-free return on fully collateralised, instantly settling inventory is the most competitive trade on the venue; it is arbitraged in seconds by bots co-located far closer than this script. This tool is built to report the DISTRIBUTION - how close the tightest books actually get to 1.00 - so an empty result is an informative measurement rather than a blank screen. If it ever does fire, treat it as a data error until proven otherwise.

 NOT PRICED HERE: gas/approval costs, the risk that a leg fills partially and leaves you directionally exposed, and the possibility that the event's outcome set is not truly exhaustive (a "none of the above" resolution breaks the whole premise - check the resolution criteria before believing any edge). ================================================================================

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
