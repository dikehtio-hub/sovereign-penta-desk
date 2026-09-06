---
type: Concept
title: 'Thesis: Tax_Reserve_Agent/engine/loss_harvester.py'
description: The ledger knows what every lot cost; it has no idea what any of it is
  worth today. Nothing here invents a price. A position with no mark is listed as
  UNMARKED and excluded from every total - because a made-up mark produces a made-up
  loss, which produces a harvestable-saving figu…
tags:
- concept
- thesis
- desk-5
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: Tax_Reserve_Agent/engine/loss_harvester.py
  title: Tax_Reserve_Agent/engine/loss_harvester.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Tax_Reserve_Agent/engine/loss_harvester.py
  headings:
  - THE HARD PART IS NOT THE ARITHMETIC, IT IS THE MARKS
  - WHAT A HARVEST IS ACTUALLY WORTH
  asserts:
  - file: Tax_Reserve_Agent/engine/loss_harvester.py
    pattern: THE\ HARD\ PART\ IS\ NOT\ THE\ ARITHMETIC,\ IT\ IS\ THE\ MARKS
    claim: the docstring still carries the section 'THE HARD PART IS NOT THE ARITHMETIC,
      IT IS THE MARKS'
  - file: Tax_Reserve_Agent/engine/loss_harvester.py
    pattern: WHAT\ A\ HARVEST\ IS\ ACTUALLY\ WORTH
    claim: the docstring still carries the section 'WHAT A HARVEST IS ACTUALLY WORTH'
  requires_files:
  - Tax_Reserve_Agent/engine/loss_harvester.py
  desk: 5
---
# Thesis: Tax_Reserve_Agent/engine/loss_harvester.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Hard Part Is Not The Arithmetic, It Is The Marks

The ledger knows what every lot cost; it has no idea what any of it is worth today. Nothing here invents a price. A position with no mark is listed as UNMARKED and excluded from every total - because a made-up mark produces a made-up loss, which produces a harvestable-saving figure someone might actually trade on. Marks come from:

 * `data/marks.csv` - `symbol,price` written by hand or by a bot. Always available, fully deterministic, works offline. * a live source - `PolymarketMarkSource` prices open prediction-market positions off the CLOB midpoint. Opt-in, and it degrades to UNMARKED rather than guessing.

## What A Harvest Is Actually Worth

Not `loss * tax_rate`. A capital loss is only worth the tax on the gain it can offset, and US netting has a specific order: short-term losses net against short-term gains, long-term against long-term, then whatever is left crosses over, then up to $3,000 of the remainder goes against ordinary income and the rest carries forward at zero present value. Modelling `loss * rate` overstates the benefit of harvesting into a year with no gains by an order of magnitude, which is exactly when someone would be tempted to do it. `estimate_benefit()` implements the real netting order.

 This is an estimate from your own ledger, not tax advice, and it does not model wash sales - see the note on `WASH_SALE_WARNING`.

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
- [[theses_register|Theses register]]
