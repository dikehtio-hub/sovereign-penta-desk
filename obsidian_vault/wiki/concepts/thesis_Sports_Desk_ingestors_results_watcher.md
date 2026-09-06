---
type: Concept
title: 'Thesis: Sports_Desk/ingestors/results_watcher.py'
description: Until an outcome is recorded, nothing in this desk can tell a good fair
  probability from a bad one. Closing-line value is a proxy and a useful one, but
  it measures agreement with the market rather than agreement with reality, and a
  book that is systematically wrong in the same di…
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
  resource: Sports_Desk/ingestors/results_watcher.py
  title: Sports_Desk/ingestors/results_watcher.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Sports_Desk/ingestors/results_watcher.py
  headings:
  - WHY THIS EXISTS
  - WHAT A RESULT ROW MEANS
  asserts:
  - file: Sports_Desk/ingestors/results_watcher.py
    pattern: WHY\ THIS\ EXISTS
    claim: the docstring still carries the section 'WHY THIS EXISTS'
  - file: Sports_Desk/ingestors/results_watcher.py
    pattern: WHAT\ A\ RESULT\ ROW\ MEANS
    claim: the docstring still carries the section 'WHAT A RESULT ROW MEANS'
  requires_files:
  - Sports_Desk/ingestors/results_watcher.py
  desk: 2
---
# Thesis: Sports_Desk/ingestors/results_watcher.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Why This Exists

Until an outcome is recorded, nothing in this desk can tell a good fair probability from a bad one. Closing-line value is a proxy and a useful one, but it measures agreement with the market rather than agreement with reality, and a book that is systematically wrong in the same direction as the market will look excellent by CLV forever. A Brier score against settled results is the only thing that closes that loop - and it is what should eventually replace the hardcoded `SHARP_BOOKS` list, because sharpness is a property you measure, not a name you recognise.

## What A Result Row Means

win / won / w / 1 this selection came in loss / lost / l / 0 it did not push / void / tie NO OUTCOME TO SCORE. Recorded as voided and excluded from every Brier computation - squaring a forecast against a push is not a small error, it is a category error, and it drags a real score toward the mean.

 EXPECTED CSV SHAPE (column order irrelevant, names flexible):

 event_id,sport,market_type,line,selection,result,settled_at NFL_KC_BAL,NFL,moneyline,,Chiefs,win,2026-09-03T23:15:00Z NFL_KC_BAL,NFL,moneyline,,Ravens,loss,2026-09-03T23:15:00Z NFL_KC_BAL,NFL,spread,-3.5,Chiefs,push,2026-09-03T23:15:00Z

 The key must match the odds side exactly - (event_id, market_type, line, selection) - or the forecast and the outcome never meet and the row scores nothing. Selections are matched on the same normalised key the odds watcher uses, so case and whitespace are forgiven and nothing else is.

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[theses_register|Theses register]]
