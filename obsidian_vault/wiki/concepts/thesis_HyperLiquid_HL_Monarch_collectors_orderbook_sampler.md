---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/collectors/orderbook_sampler.py'
description: 'The cost model behind the 7-day basis hold amortises a spread that nothing
  in the repository measured: orderbook_snapshots existed, the repository could write
  it, and no caller ever did. Every persisted basis window therefore carried fee_basis=''unmeasured''
  and a NULL net rate. Th…'
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
  resource: HyperLiquid/HL_Monarch/collectors/orderbook_sampler.py
  title: HyperLiquid/HL_Monarch/collectors/orderbook_sampler.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/collectors/orderbook_sampler.py
  headings:
  - WHAT THIS CLOSES
  - BOUNDED BY DESIGN
  asserts:
  - file: HyperLiquid/HL_Monarch/collectors/orderbook_sampler.py
    pattern: WHAT\ THIS\ CLOSES
    claim: the docstring still carries the section 'WHAT THIS CLOSES'
  - file: HyperLiquid/HL_Monarch/collectors/orderbook_sampler.py
    pattern: BOUNDED\ BY\ DESIGN
    claim: the docstring still carries the section 'BOUNDED BY DESIGN'
  requires_files:
  - HyperLiquid/HL_Monarch/collectors/orderbook_sampler.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/collectors/orderbook_sampler.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## What This Closes

The cost model behind the 7-day basis hold amortises a spread that nothing in the repository measured: orderbook_snapshots existed, the repository could write it, and no caller ever did. Every persisted basis window therefore carried fee_basis='unmeasured' and a NULL net rate. This module is the caller.

## Bounded By Design

One l2Book request per coin per pass, for a capped list of coins, on a slow cadence - the REST budget is nearly consumed by context polling (see settings.ORDERBOOK_SAMPLE_INTERVAL). The pass never raises: a coin that fails is recorded by name and the rest are written, because one 429 must not cost the other twenty-three spreads.

 The depth figures come from the same payload at no extra cost; the spread is what the persistence module reads (spread_bps_at), and it is the PERP leg's spread. The spot leg of a spot-backed basis trade is a different book that is not sampled here; the drag formula's two legs use the perp figure for both.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
