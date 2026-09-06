---
type: Concept
title: 'Thesis: cross_market/matcher.py'
description: A pricing error in a hedge costs a few basis points. A MATCHING error
  costs the whole position, because the two legs stop being a hedge and become the
  same bet placed twice. If "Kansas City Chiefs" is matched to a Kansas City ROYALS
  market, or a YES on "Chiefs win" is paired with…
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
  resource: cross_market/matcher.py
  title: cross_market/matcher.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: cross_market/matcher.py
  headings:
  - THE FAILURE MODE THIS MODULE EXISTS TO PREVENT
  asserts:
  - file: cross_market/matcher.py
    pattern: THE\ FAILURE\ MODE\ THIS\ MODULE\ EXISTS\ TO\ PREVENT
    claim: the docstring still carries the section 'THE FAILURE MODE THIS MODULE EXISTS
      TO PREVENT'
  requires_files:
  - cross_market/matcher.py
  desk: 3
---
# Thesis: cross_market/matcher.py

> 1 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Failure Mode This Module Exists To Prevent

A pricing error in a hedge costs a few basis points. A MATCHING error costs the whole position, because the two legs stop being a hedge and become the same bet placed twice. If "Kansas City Chiefs" is matched to a Kansas City ROYALS market, or a YES on "Chiefs win" is paired with a sportsbook bet ON the Chiefs rather than against them, the desk ends up with double exposure to one outcome while the ledger records a riskless arbitrage. Nothing downstream can detect that: the tax engine, the sizer and the HUD will all faithfully price a position that does not exist.

 So this module refuses far more than it guesses. Three rules follow from that:

 1. NICKNAME IS THE KEY, CITY IS ONLY A DISAMBIGUATOR. Kansas City fields the Chiefs and the Royals; New York fields the Giants and the Jets; Los Angeles fields the Kings, the Lakers, the Clippers, the Rams, the Chargers and the Dodgers. Matching on city is not matching.

 2. AMBIGUITY IS AN ERROR, NOT A TIE-BREAK. "Cardinals" is Arizona in the NFL and St. Louis in MLB; "Panthers" is Carolina in the NFL and Florida in the NHL; "Kings" is Los Angeles in the NHL and Sacramento in the NBA. Within one sport these are unique, so a resolution without a sport that hits more than one canonical team returns no match rather than the first one.

 3. THE HEDGE MUST BE PROVED OPPOSITE, NOT ASSUMED. `hedge_leg_for` derives the complementary selection from the market type, and returns None when it cannot. A moneyline YES on one team hedges the other team; an Over hedges the Under AT THE SAME TOTAL; a spread hedges the mirrored handicap AND ONLY at the same number. Pairing -3.5 against +7.5 is not a hedge, it is two bets with a four-point hole in the middle, and a half-point difference is the difference between a hedge and a middle.

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
