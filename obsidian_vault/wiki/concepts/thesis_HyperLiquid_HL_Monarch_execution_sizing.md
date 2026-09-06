---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/execution/sizing.py'
description: 'Hyperliquid quotes `szDecimals` per instrument, and the spot token and
  the perp contract for the SAME asset frequently disagree. MON is live proof: the
  PERP is szDecimals=0 (whole units only) while SPOT is szDecimals=2. Send a fractional
  size to the perp and that leg is rejected …'
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
  resource: HyperLiquid/HL_Monarch/execution/sizing.py
  title: HyperLiquid/HL_Monarch/execution/sizing.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/execution/sizing.py
  headings:
  - THE HAZARD
  - WHY INDEPENDENT ROUNDING IS THE WRONG FIX
  - WHAT THIS DOES INSTEAD
  asserts:
  - file: HyperLiquid/HL_Monarch/execution/sizing.py
    pattern: THE\ HAZARD
    claim: the docstring still carries the section 'THE HAZARD'
  - file: HyperLiquid/HL_Monarch/execution/sizing.py
    pattern: WHY\ INDEPENDENT\ ROUNDING\ IS\ THE\ WRONG\ FIX
    claim: the docstring still carries the section 'WHY INDEPENDENT ROUNDING IS THE
      WRONG FIX'
  - file: HyperLiquid/HL_Monarch/execution/sizing.py
    pattern: WHAT\ THIS\ DOES\ INSTEAD
    claim: the docstring still carries the section 'WHAT THIS DOES INSTEAD'
  requires_files:
  - HyperLiquid/HL_Monarch/execution/sizing.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/execution/sizing.py

> 3 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Hazard

Hyperliquid quotes `szDecimals` per instrument, and the spot token and the perp contract for the SAME asset frequently disagree. MON is live proof: the PERP is szDecimals=0 (whole units only) while SPOT is szDecimals=2. Send a fractional size to the perp and that leg is rejected while the spot leg fills - leaving unhedged inventory in a position whose entire premise is that it has no directional exposure.

## Why Independent Rounding Is The Wrong Fix

The obvious response is to floor each leg to its own precision. That prevents the REJECTION but reintroduces the exposure it was meant to remove: flooring 1000.567 gives a 1000-unit perp against a 1000.56 spot, and the 0.56 difference is naked. Independent rounding converts a loud failure into a quiet one.

## What This Does Instead

Both legs are floored to the COARSER of the two precisions, so they are equal by construction and the residual is exactly zero. The cost is a slightly smaller position than requested - always smaller, never larger, because rounding up could exceed available capital or margin.

 `min_size` guards the degenerate case: when the coarser precision is 0 and the target size is under one whole unit, there is no tradeable 1:1 position at all and the caller must be told, not handed a zero-size fill.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
