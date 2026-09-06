---
type: Concept
title: 'Thesis: Tax_Reserve_Agent/engine/odds.py'
description: 'Odds never enter a tax computation - the IRS cares about dollars received
  and dollars wagered, not the price. They earn their place as a CONSISTENCY CHECK:
  `wager x decimal_odds` is what the ticket should have returned, and a settled row
  whose payout disagrees is a corrupt import…'
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
  resource: Tax_Reserve_Agent/engine/odds.py
  title: Tax_Reserve_Agent/engine/odds.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Tax_Reserve_Agent/engine/odds.py
  headings:
  - WHY THIS IS IN THE TAX AGENT AT ALL
  - FORMAT DETECTION IS AMBIGUOUS, AND WHERE IT IS TRULY AMBIGUOUS THIS REFUSES
  asserts:
  - file: Tax_Reserve_Agent/engine/odds.py
    pattern: WHY\ THIS\ IS\ IN\ THE\ TAX\ AGENT\ AT\ ALL
    claim: the docstring still carries the section 'WHY THIS IS IN THE TAX AGENT AT
      ALL'
  - file: Tax_Reserve_Agent/engine/odds.py
    pattern: FORMAT\ DETECTION\ IS\ AMBIGUOUS,\ AND\ WHERE\ IT\ IS\ TRULY\ AMBIGUOUS\
      THIS\ REFUSES
    claim: the docstring still carries the section 'FORMAT DETECTION IS AMBIGUOUS,
      AND WHERE IT IS TRULY AMBIGUOUS THIS REFUSES'
  requires_files:
  - Tax_Reserve_Agent/engine/odds.py
  desk: 5
---
# Thesis: Tax_Reserve_Agent/engine/odds.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Why This Is In The Tax Agent At All

Odds never enter a tax computation - the IRS cares about dollars received and dollars wagered, not the price. They earn their place as a CONSISTENCY CHECK: `wager x decimal_odds` is what the ticket should have returned, and a settled row whose payout disagrees is a corrupt import. A mistyped payout is invisible in every other check this ledger runs and is wrong in the escrow forever after.

## Format Detection Is Ambiguous, And Where It Is Truly Ambiguous This Refuses

signed (`+150`, `-110`, `-110.0`) American. Decimal odds are never signed and never negative, so a sign settles it. bare integer >= 100 (`150`) American, by industry convention. 1 < x < 100 (`1.91`, `26.0`) decimal. Below +9900 nobody quotes decimal that high, and American cannot live here. bare `150.0` REFUSED. It is either American +150 written by a tool that formatted it as a float, or a genuine decimal 150.0 (+14900). Those differ by 60x. Guessing either way is silent, and wrong half the time. (0, 1] REFUSED. Implied probability, or a typo.

 Refusing is cheap here and guessing is not: odds are metadata, so the ingestor catches the refusal, warns, and still records the wager and its dollars. The tax figure is never at risk; only the payout cross-check is lost. Set `fmt=`, the export's own `odds_format` column, or `gambling.default_odds_format` to make the ambiguous zone readable.

 `implied_probability` is deliberately exposed as its own function: it is the seam the no-vig / fair-value engine (Item 2) attaches to, and it belongs with the conversions rather than duplicated there.

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
- [[theses_register|Theses register]]
