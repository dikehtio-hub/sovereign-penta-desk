---
type: Concept
title: 'Thesis: Tax_Reserve_Agent/engine/gambling_tax.py'
description: "-------------------------------------------\n\n 1. GROSS WINNINGS ARE\
  \ NOT NET WINNINGS. IRC 61 taxes every winning wager. IRC 165(d) makes losses a\
  \ DEDUCTION, and a deduction is only worth something to someone who itemises. A\
  \ bettor who wins $80,000 and loses $79,000 over a year an…"
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
  resource: Tax_Reserve_Agent/engine/gambling_tax.py
  title: Tax_Reserve_Agent/engine/gambling_tax.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Tax_Reserve_Agent/engine/gambling_tax.py
  headings:
  - FOUR THINGS THIS MODULE EXISTS TO GET RIGHT
  - WHAT THIS MODULE DELIBERATELY DOES NOT DO
  asserts:
  - file: Tax_Reserve_Agent/engine/gambling_tax.py
    pattern: FOUR\ THINGS\ THIS\ MODULE\ EXISTS\ TO\ GET\ RIGHT
    claim: the docstring still carries the section 'FOUR THINGS THIS MODULE EXISTS
      TO GET RIGHT'
  - file: Tax_Reserve_Agent/engine/gambling_tax.py
    pattern: WHAT\ THIS\ MODULE\ DELIBERATELY\ DOES\ NOT\ DO
    claim: the docstring still carries the section 'WHAT THIS MODULE DELIBERATELY
      DOES NOT DO'
  requires_files:
  - Tax_Reserve_Agent/engine/gambling_tax.py
  desk: 5
---
# Thesis: Tax_Reserve_Agent/engine/gambling_tax.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Four Things This Module Exists To Get Right

-------------------------------------------

 1. GROSS WINNINGS ARE NOT NET WINNINGS. IRC 61 taxes every winning wager. IRC 165(d) makes losses a DEDUCTION, and a deduction is only worth something to someone who itemises. A bettor who wins $80,000 and loses $79,000 over a year and takes the standard deduction owes tax on $80,000. That is the single most expensive fact in this file and the default mode enforces it.

 "Winnings" here means proceeds from a wager NET OF THAT WAGER's own stake - the Reg. 1.6041-10 measure a W-2G reports, not the gross amount handed back. A $100 bet returning $250 is $150 of winnings, not $250.

 2. THE 2026 90% HAIRCUT. OBBBA 70114 amended 165(d) for tax years beginning after 2025: the deduction is limited to 90% of losses, still capped at winnings. Break even at $100k in and $100k out and you now have $10,000 of phantom taxable income. This is CONFIGURABLE (`loss_deduction_pct`) and dated (`loss_haircut_effective_year`) precisely because it has been the subject of repeal attempts - set it to 1.0 for one line and pre-2026 behaviour returns.

 3. A W-2G CREDIT IS FEDERAL AND ONLY FEDERAL. The 24% a sportsbook withholds is federal income tax. It does not pay state tax, and it certainly does not pay this agent's safety buffer. Netting it against a composite rate credits the bettor with money nobody sent to their state, and it moves the reserve DOWN - the one direction this ledger must never move on an assumption. Credit is therefore capped at the federal leg, and any excess is reported as a refund receivable rather than silently absorbed.

 4. LOSSES CANNOT CREATE A REFUND. Under every mode the taxable base floors at zero and the escrow floors at zero. A losing year releases no escrow that another bucket is responsible for.

## What This Module Deliberately Does Not Do

----------------------------------------- It does not compute a return. It sizes an ESCROW - money to keep in cash so April is funded - using flat marginal rates from config. It has no brackets, no AGI phase-outs, no standard-deduction amount, and no state apportionment. Those turn a reserve estimator into a tax preparer, and getting them half-right is worse than not having them.

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
- [[theses_register|Theses register]]
