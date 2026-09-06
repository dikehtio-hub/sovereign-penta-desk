---
type: Concept
title: 'Thesis: Sports_Desk/interfaces/monarch_shark.py'
description: It does not place bets with a sportsbook - there is no API to place them
  through, and building one would be the least interesting and most dangerous part
  of this system. It shows the hotlist, takes a decision, and records what was staked
  at what price. The human does the clicking…
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
  resource: Sports_Desk/interfaces/monarch_shark.py
  title: Sports_Desk/interfaces/monarch_shark.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Sports_Desk/interfaces/monarch_shark.py
  headings:
  - WHAT IT IS NOT
  - WHY RECORDING MATTERS MORE THAN IT LOOKS
  - TWO THINGS THIS DELIBERATELY REFUSES TO DO
  asserts:
  - file: Sports_Desk/interfaces/monarch_shark.py
    pattern: WHAT\ IT\ IS\ NOT
    claim: the docstring still carries the section 'WHAT IT IS NOT'
  - file: Sports_Desk/interfaces/monarch_shark.py
    pattern: WHY\ RECORDING\ MATTERS\ MORE\ THAN\ IT\ LOOKS
    claim: the docstring still carries the section 'WHY RECORDING MATTERS MORE THAN
      IT LOOKS'
  - file: Sports_Desk/interfaces/monarch_shark.py
    pattern: TWO\ THINGS\ THIS\ DELIBERATELY\ REFUSES\ TO\ DO
    claim: the docstring still carries the section 'TWO THINGS THIS DELIBERATELY REFUSES
      TO DO'
  requires_files:
  - Sports_Desk/interfaces/monarch_shark.py
  desk: 2
---
# Thesis: Sports_Desk/interfaces/monarch_shark.py

> 3 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## What It Is Not

It does not place bets with a sportsbook - there is no API to place them through, and building one would be the least interesting and most dangerous part of this system. It shows the hotlist, takes a decision, and records what was staked at what price. The human does the clicking.

## Why Recording Matters More Than It Looks

`edge_opportunities` holds what was OFFERED; `placed_bets` holds what was TAKEN. The gap between them is execution slippage, and it is completely invisible unless both are kept. A desk that logs only its ideas will conclude it has an edge long after the prices it can actually get have stopped supporting one.

## Two Things This Deliberately Refuses To Do

* It will not stake a bet the bankroll gate rejected. The gate already knows about the after-tax hurdle, the strategy bucket and the escrow; overriding it from a betslip would make all three advisory. * It will not stake the same capital twice. THE GATE IS PER-ORDER, and it measures existing exposure from the TAX LEDGER - which does not learn about a wager until the book's export is imported, possibly days later. Left alone, every bet in a session is approved against a bucket that looks empty: measured on a $750 bucket, forty $31 bets went through for $1,249, or 1.7x. So the betslip reports its own open exposure to the gate on every order. * It does not write to the tax ledger. `Tax_Reserve_Agent` is fed by the book's own export, because the escrow must reserve against what the BOOK says happened, not what this desk believes it did. The confirmation says so every time, because forgetting it is how the escrow silently goes stale.

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[theses_register|Theses register]]
