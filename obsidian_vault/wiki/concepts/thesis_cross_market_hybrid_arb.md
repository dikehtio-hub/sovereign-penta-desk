---
type: Concept
title: 'Thesis: cross_market/hybrid_arb.py'
description: A Polymarket position and a sportsbook position on opposite sides of
  the same event look like the cleanest arbitrage available, because the two venues
  price independently and their errors are uncorrelated. In dollars that is true.
  After tax it is usually false, and the gap is not…
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
  resource: cross_market/hybrid_arb.py
  title: cross_market/hybrid_arb.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: cross_market/hybrid_arb.py
  headings:
  - WHY THIS MODULE EXISTS, AND WHAT IT MOSTLY SAYS
  - DOES NOT PRODUCE
  asserts:
  - file: cross_market/hybrid_arb.py
    pattern: WHY\ THIS\ MODULE\ EXISTS,\ AND\ WHAT\ IT\ MOSTLY\ SAYS
    claim: the docstring still carries the section 'WHY THIS MODULE EXISTS, AND WHAT
      IT MOSTLY SAYS'
  - file: cross_market/hybrid_arb.py
    pattern: DOES\ NOT\ PRODUCE
    claim: the docstring still carries the section 'DOES NOT PRODUCE'
  requires_files:
  - cross_market/hybrid_arb.py
  desk: 3
---
# Thesis: cross_market/hybrid_arb.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Why This Module Exists, And What It Mostly Says

A Polymarket position and a sportsbook position on opposite sides of the same event look like the cleanest arbitrage available, because the two venues price independently and their errors are uncorrelated. In dollars that is true. After tax it is usually false, and the gap is not small.

 The reason is an asymmetry with no analogue in single-venue arbitrage:

## Does Not Produce

* When the sportsbook leg loses, the winner is Polymarket. Under the capital reading that is a CAPITAL GAIN, not a gambling winning. NJ GITA 54A:5-1(g) nets gambling losses against gambling WINNINGS - same category, same year, capped at winnings. There are none here. The state relief that makes a sportsbook loss bearable is not available in the branch that needs it.

 * When the Polymarket leg loses, the winner is the sportsbook. That is ORDINARY income. IRC 1211(b) lets a capital loss offset capital gains without limit but ordinary income by only $3,000 a year; the rest carries forward and is worth nothing this year. The capital relief that makes a Polymarket loss bearable is likewise unavailable in the branch that needs it.

 Both reliefs therefore depend on income the position does not generate - on CAPACITY the taxpayer either has from elsewhere or does not have at all. That is why this module takes `gambling_win_capacity` and `capital_gain_capacity` as inputs and defaults both to ZERO. A delta is not a property of a leg; it is a property of the leg and the rest of the return together.

 WHAT THE NUMBERS COME OUT AT (NJ resident, composite 32.37%, state 6.37%):

 required gross arbitrage, both capacities ample 8.83% required gross arbitrage, no capacity at all 16.75% for reference, single-venue sportsbook arb 23.93% what cross-book arbitrage actually pays 1-3%

 So cross-market genuinely beats staying inside the sportsbook - the capital leg is worth roughly seven points of hurdle - and it is still nowhere near riskless. At 1-3% gross, every opportunity this module finds is an after-tax loss, and its main job is to say so before the capital is committed.

 ONE ASSUMPTION IS LOAD-BEARING AND UNSETTLED: that a Polymarket event contract is CAPITAL rather than wagering. The IRS has not ruled on retail-held CFTC-regulated binary event contracts. IRC 1234A supports capital treatment for gain or loss on the termination of a right with respect to property; a characterisation as wagering would put the leg under IRC 165(d) and collapse it to the same trap as the sportsbook. `prediction_as_wagering_tax` prices that reading, and it is materially worse. Do not present the capital number as settled.

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
