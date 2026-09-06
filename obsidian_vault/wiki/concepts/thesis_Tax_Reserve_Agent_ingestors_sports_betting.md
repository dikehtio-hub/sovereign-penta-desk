---
type: Concept
title: 'Thesis: Tax_Reserve_Agent/ingestors/sports_betting.py'
description: 'This is the single most important decision in the file. A wager is not
  fungible with another wager on the same selection: two $20 and $500 tickets on CHIEFS
  -3.5 are two distinct lots with two distinct stakes, and if they share a `symbol`
  the lot matcher will settle one against t…'
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
  resource: Tax_Reserve_Agent/ingestors/sports_betting.py
  title: Tax_Reserve_Agent/ingestors/sports_betting.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Tax_Reserve_Agent/ingestors/sports_betting.py
  headings:
  - THE TICKET IS THE LOT
  - FRACTIONAL SETTLEMENT
  - WHAT A SETTLEMENT ROW MEANS
  asserts:
  - file: Tax_Reserve_Agent/ingestors/sports_betting.py
    pattern: THE\ TICKET\ IS\ THE\ LOT
    claim: the docstring still carries the section 'THE TICKET IS THE LOT'
  - file: Tax_Reserve_Agent/ingestors/sports_betting.py
    pattern: FRACTIONAL\ SETTLEMENT
    claim: the docstring still carries the section 'FRACTIONAL SETTLEMENT'
  - file: Tax_Reserve_Agent/ingestors/sports_betting.py
    pattern: WHAT\ A\ SETTLEMENT\ ROW\ MEANS
    claim: the docstring still carries the section 'WHAT A SETTLEMENT ROW MEANS'
  requires_files:
  - Tax_Reserve_Agent/ingestors/sports_betting.py
  desk: 5
---
# Thesis: Tax_Reserve_Agent/ingestors/sports_betting.py

> 3 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Ticket Is The Lot

This is the single most important decision in the file. A wager is not fungible with another wager on the same selection: two $20 and $500 tickets on CHIEFS -3.5 are two distinct lots with two distinct stakes, and if they share a `symbol` the lot matcher will settle one against the other's basis. Keying the symbol on the ticket id makes each ticket its own lot family and makes cross-matching structurally impossible rather than merely unlikely.

 DK:NFL:CHIEFS_-3.5#T1

## Fractional Settlement

The opening lot carries `quantity = 1.0` - one ticket - so a settlement of `quantity = f` closes the fraction `f` of it and leaves the rest open. That is what makes dead heats, partial voids and partial cashouts representable without a second lot model: settle `f` at `payout / f` and the engine books `payout` of proceeds against `f x wager` of basis, which is exactly the arithmetic a book prints on the ticket.

## What A Settlement Row Means

BET_WIN ticket won; `price` is the total returned, stake included BET_LOSS ticket lost; proceeds are zero BY DEFINITION, not by price BET_PUSH stake refunded (push, void, postponed, cancelled) - nets to zero BET_CASHOUT settled early for `price`, which may be above OR below the stake. A cashout below the stake is a real loss of (stake - price), NOT a loss of the stake, which is why it cannot be a BET_LOSS.

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
- [[theses_register|Theses register]]
