---
type: Concept
title: 'Thesis: Sports_Desk/engine/arbitrage.py'
description: A cross-book arb wins one leg and loses the other, every single time.
  The winning leg is ordinary income; the losing leg is a wagering loss, and under
  IRC 165(d) a casual bettor on the standard deduction may not deduct it at all. So
  a 2% arbitrage - which is a good one, in practi…
tags:
- concept
- thesis
- desk-2
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: Sports_Desk/engine/arbitrage.py
  title: Sports_Desk/engine/arbitrage.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Sports_Desk/engine/arbitrage.py
  headings:
  - THE PART EVERYONE GETS WRONG IS THE TAX
  - WHAT THIS MODULE DOES NOT DO
  - STALENESS IS THE DOMINANT FALSE POSITIVE
  asserts:
  - file: Sports_Desk/engine/arbitrage.py
    pattern: THE\ PART\ EVERYONE\ GETS\ WRONG\ IS\ THE\ TAX
    claim: the docstring still carries the section 'THE PART EVERYONE GETS WRONG IS
      THE TAX'
  - file: Sports_Desk/engine/arbitrage.py
    pattern: WHAT\ THIS\ MODULE\ DOES\ NOT\ DO
    claim: the docstring still carries the section 'WHAT THIS MODULE DOES NOT DO'
  - file: Sports_Desk/engine/arbitrage.py
    pattern: STALENESS\ IS\ THE\ DOMINANT\ FALSE\ POSITIVE
    claim: the docstring still carries the section 'STALENESS IS THE DOMINANT FALSE
      POSITIVE'
  requires_files:
  - Sports_Desk/engine/arbitrage.py
  desk: 2
---
# Thesis: Sports_Desk/engine/arbitrage.py

> 3 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Part Everyone Gets Wrong Is The Tax

A cross-book arb wins one leg and loses the other, every single time. The winning leg is ordinary income; the losing leg is a wagering loss, and under IRC 165(d) a casual bettor on the standard deduction may not deduct it at all. So a 2% arbitrage - which is a good one, in practice - carries roughly a 14% after-tax LOSS. It is not a thin edge, it is a reliable one, in the wrong direction, and it looks like free money right up to the moment the return is filed.

 Worse, AN ARBITRAGE IS NOT EVEN RISKLESS AFTER TAX. The legs are taxed asymmetrically, so a position that is riskless in dollars has a different after-tax outcome depending on which side wins - unless the stakes happen to be equal or losses are fully deductible. The binding case is always the longest-odds leg, because that is the smallest stake and therefore the largest non-deductible loss. `monarch_hook.after_tax_arbitrage_hurdle` prices exactly that branch, and nothing here reports an opportunity that does not clear it.

## What This Module Does Not Do

It does not devig. An arbitrage is a statement about PRICES, not about probabilities: you are not claiming to know the true chance of anything, only that two books disagree by more than their combined margin. Fair value belongs to `fair_value.py` and has no role here.

## Staleness Is The Dominant False Positive

Most apparent cross-book arbs are two quotes captured minutes apart, and the "edge" is the market having moved in between. Quotes are filtered through the same per-sport staleness rule the odds watcher uses before any of them are compared.

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[theses_register|Theses register]]
