---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/execution/basis_harvester.py'
description: 'Positive funding means longs pay shorts. The harvester shorts the perp
  to collect that and buys the same notional of spot so the price exposure cancels.
  Net delta zero, 1:1 by construction: the funding IS the return.'
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
  resource: HyperLiquid/HL_Monarch/execution/basis_harvester.py
  title: HyperLiquid/HL_Monarch/execution/basis_harvester.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/execution/basis_harvester.py
  headings:
  - WHAT IT TRADES
  - WHY THIS IS STRUCTURALLY DIFFERENT FROM WHAT IT REPLACED
  - HOW FUNDING ACCRUES
  - WHAT IS STILL NOT MODELLED
  asserts:
  - file: HyperLiquid/HL_Monarch/execution/basis_harvester.py
    pattern: WHAT\ IT\ TRADES
    claim: the docstring still carries the section 'WHAT IT TRADES'
  - file: HyperLiquid/HL_Monarch/execution/basis_harvester.py
    pattern: WHY\ THIS\ IS\ STRUCTURALLY\ DIFFERENT\ FROM\ WHAT\ IT\ REPLACED
    claim: the docstring still carries the section 'WHY THIS IS STRUCTURALLY DIFFERENT
      FROM WHAT IT REPLACED'
  - file: HyperLiquid/HL_Monarch/execution/basis_harvester.py
    pattern: HOW\ FUNDING\ ACCRUES
    claim: the docstring still carries the section 'HOW FUNDING ACCRUES'
  - file: HyperLiquid/HL_Monarch/execution/basis_harvester.py
    pattern: WHAT\ IS\ STILL\ NOT\ MODELLED
    claim: the docstring still carries the section 'WHAT IS STILL NOT MODELLED'
  requires_files:
  - HyperLiquid/HL_Monarch/execution/basis_harvester.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/execution/basis_harvester.py

> 4 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## What It Trades

Positive funding means longs pay shorts. The harvester shorts the perp to collect that and buys the same notional of spot so the price exposure cancels. Net delta zero, 1:1 by construction: the funding IS the return.

## Why This Is Structurally Different From What It Replaced

The liquidation fade was retired because its entry signal was measured wrong-sided (MFE/MAE 0.513 against a 1.092 control). That was a DIRECTIONAL bet dressed up as a mean-reversion edge. This is not a directional bet at all - the two legs cancel, and the return does not depend on predicting anything. The risk moves from "was the forecast right" to "does the rate persist and do both legs stay hedged".

## How Funding Accrues

Funding is paid hourly on the PERP notional. The spot leg is unlevered inventory and pays nothing. So:

 hourly_pnl = perp_notional x funding_rate_1h

 `accrue()` takes the CURRENT rate each hour rather than extrapolating the entry rate. That distinction is the entire risk of the strategy: an entry APR is an instantaneous quote, and a position opened at 56% APR earns whatever the rate actually turns out to be - which may be zero, or negative, within hours. A harvester that projected its entry rate forward would report a fantasy.

## What Is Still Not Modelled

Spot/perp basis drift between the legs (the hedge is exact in notional at entry, not thereafter), liquidation of the perp leg if margin is not shared with the spot leg, transfer frictions between spot and perp wallets, and the borrow that would be needed to run this in reverse (which is why only positive-funding markets are ever opened - see basis_strategy.build_position).

 WHAT THE RETURNS LOOK LIKE (Round 43, Ruling 43-5). Funding income is heavy in the right tail. Measured on the paper book on 2026-09-04: five positions, one of them (para:ANSEM, quoted 2,925% APR at entry) realised 554% over 51 hours and paid $322 of the book's $350; the other four realised 9% to 50%. That is the shape of this strategy, not an anomaly: most entries pay a little, a few pay for the book. Two consequences. A mean realised APR is a poor summary - report the median and the top position's share. And the entry bar stays at 25% gross / 20% net: at the ~11% baseline funding of the liquid large caps, fee-plus-spread drag over a 7-day hold is roughly 15%, so the expectancy is negative and idle cash at 0% outranks churning it.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
