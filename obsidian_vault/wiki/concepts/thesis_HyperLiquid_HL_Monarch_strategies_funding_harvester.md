---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/strategies/funding_harvester.py'
description: The delta-neutral engine already exists and works. `execution/basis_harvester.py`
  shorts the perp, buys matching spot, accrues at the CURRENT hourly rate rather than
  extrapolating the entry quote, and refuses uncosted rows; `analytics/funding_arbitrage.py`
  scans the universe and …
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
  resource: HyperLiquid/HL_Monarch/strategies/funding_harvester.py
  title: HyperLiquid/HL_Monarch/strategies/funding_harvester.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/strategies/funding_harvester.py
  headings:
  - WHAT THIS IS, AND WHAT IT IS NOT
  - 'SECOND: THE HEADLINE APR IS QUOTED AGAINST ONE LEG AND THE CAPITAL IS TWO'
  asserts:
  - file: HyperLiquid/HL_Monarch/strategies/funding_harvester.py
    pattern: WHAT\ THIS\ IS,\ AND\ WHAT\ IT\ IS\ NOT
    claim: the docstring still carries the section 'WHAT THIS IS, AND WHAT IT IS NOT'
  - file: HyperLiquid/HL_Monarch/strategies/funding_harvester.py
    pattern: SECOND:\ THE\ HEADLINE\ APR\ IS\ QUOTED\ AGAINST\ ONE\ LEG\ AND\ THE\
      CAPITAL\ IS\ TWO
    claim: 'the docstring still carries the section ''SECOND: THE HEADLINE APR IS
      QUOTED AGAINST ONE LEG AND THE CAPITAL IS TWO'''
  requires_files:
  - HyperLiquid/HL_Monarch/strategies/funding_harvester.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/strategies/funding_harvester.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## What This Is, And What It Is Not

The delta-neutral engine already exists and works. `execution/basis_harvester.py` shorts the perp, buys matching spot, accrues at the CURRENT hourly rate rather than extrapolating the entry quote, and refuses uncosted rows; `analytics/funding_arbitrage.py` scans the universe and amortises the spread over a realistic hold. None of that is rebuilt here, and duplicating it would be worse than useless - a second engine with its own copy of the fee model is a second thing to keep correct.

 What was missing is the layer between that engine and the rest of the desk, and it was missing in two specific ways.

 FIRST: THE HARVESTER NEVER ASKED THE BANKROLL. `BasisHarvester.can_open` gates on `self.cash` - the paper engine's own float - and imports STRATEGY_BASIS_HARVEST only to TAG RECEIPTS. `RiskManager` holds a real `MonarchBankrollHook` gate at `check_order(..., strategy=...)`, but nothing routed the harvester through it, and `market_collector.py` opens positions with no bucket check at all. Two positions at the configured $10,000 per leg is $40,000 of capital committed without one reference to whether the `hl_basis_harvest` bucket allows it. This is the same defect that let Monarch_Shark run 1.7x over its sports bucket: an engine sizing against local state instead of the shared one.

## Second: The Headline Apr Is Quoted Against One Leg And The Capital Is Two

`capital_required()` returns `notional_per_leg * 2`, correctly, because both legs tie up money. But every APR in the system - the scanner's `funding_apr`, the entry quote, `format_report`'s realised APR, which divides accrued funding by `notional_per_leg` - is a return on ONE leg. So a position reporting 56% realised is earning 28% on the capital it actually consumes. That is not a rounding difference; it is a factor of two on the only number that decides whether the strategy is worth running.

 Put the two corrections together with tax and the decision changes shape:

 quoted net APR 20.0% on capital actually employed (2 legs) 10.0% after tax at the NJ composite 32.37% 6.8% Treasury bills at 5%, after tax on THEIR terms 3.7%

 The strategy still wins, but by three points rather than fifteen, and that margin is what has to cover basis drift, liquidation risk on the perp leg, and the rate evaporating mid-hold. Quoting 20% against a 5% Treasury makes it look like a different trade than it is.

 THE TREASURY COMPARISON IS DONE ON EACH INSTRUMENT'S OWN TAX TERMS, which is why it is not simply `hurdle * (1 - t)`. Treasury interest is exempt from state income tax under 31 USC 3124(a); funding income is not. For a New Jersey resident that hands T-bills a 6.37-point advantage in tax rate that a gross-to-gross comparison never shows.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
