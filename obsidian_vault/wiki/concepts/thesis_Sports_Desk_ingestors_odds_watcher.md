---
type: Concept
title: 'Thesis: Sports_Desk/ingestors/odds_watcher.py'
description: 'This is the question the plan left open and this module answers it in
  code: the SHARP book is devigged to produce fair probabilities, and every retail
  quote is scored against those. Retail books are never devigged - you bet the price
  a book offers, not a fair one, so the retail s…'
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
  resource: Sports_Desk/ingestors/odds_watcher.py
  title: Sports_Desk/ingestors/odds_watcher.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Sports_Desk/ingestors/odds_watcher.py
  headings:
  - WHICH BOOK IS THE TRUTH-TELLER
  asserts:
  - file: Sports_Desk/ingestors/odds_watcher.py
    pattern: WHICH\ BOOK\ IS\ THE\ TRUTH\-TELLER
    claim: the docstring still carries the section 'WHICH BOOK IS THE TRUTH-TELLER'
  requires_files:
  - Sports_Desk/ingestors/odds_watcher.py
  desk: 2
---
# Thesis: Sports_Desk/ingestors/odds_watcher.py

> 1 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Which Book Is The Truth-Teller

This is the question the plan left open and this module answers it in code: the SHARP book is devigged to produce fair probabilities, and every retail quote is scored against those. Retail books are never devigged - you bet the price a book offers, not a fair one, so the retail side is stored raw. `SHARP_BOOKS` names the references; a row may also carry an `is_sharp` column to override per market.

 EXPECTED CSV SHAPE (column order irrelevant, names flexible):

 event_id,sport,market_type,line,selection,book,odds,is_sharp,timestamp,is_closing NFL_KC_BAL,NFL,moneyline,,Chiefs,Pinnacle,-140,1,2026-09-03T18:00:00Z,0 NFL_KC_BAL,NFL,moneyline,,Ravens,Pinnacle,+120,1,2026-09-03T18:00:00Z,0 NFL_KC_BAL,NFL,moneyline,,Chiefs,DraftKings,-130,0,2026-09-03T18:00:00Z,0 NFL_KC_BAL,NFL,spread,-3.5,Chiefs,Pinnacle,-110,1,2026-09-03T18:00:00Z,0

 Rows group by (event_id, sport, market_type, LINE). The line is part of the market identity, not an attribute of it: Chiefs -3.5 and Chiefs -2.5 are different bets with different fair prices, and grouping them devigs one book against another quoting a different number - the "edge" that falls out is just the half-point. `line` is blank for a moneyline.

 `timestamp` and `is_closing` are optional. Without timestamps the staleness guard cannot run and says so; without `is_closing` nothing marks a closing line and CLV has nothing to compare against.

 Odds accept anything `parse_odds` reads.

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[theses_register|Theses register]]
