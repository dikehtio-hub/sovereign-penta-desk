---
type: Concept
title: 'Thesis: Sports_Desk/ingestors/odds_fetcher.py'
description: Sports_Desk had 680 passing tests and no database. Every test built its
  own SQLite fixture in a temp directory; `data/odds_drops/` held zero files; `sports_market.db`
  did not exist. The Brier and skill-score machinery was built and had never scored
  a single forecast, because ther…
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
  resource: Sports_Desk/ingestors/odds_fetcher.py
  title: Sports_Desk/ingestors/odds_fetcher.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Sports_Desk/ingestors/odds_fetcher.py
  headings:
  - WHAT THIS CLOSES
  - OFFLINE BY DEFAULT, AND THAT IS NOT A SHORTCUT
  - THE LIVE PATH IS A CONTRACT, NOT A SCRAPER
  asserts:
  - file: Sports_Desk/ingestors/odds_fetcher.py
    pattern: WHAT\ THIS\ CLOSES
    claim: the docstring still carries the section 'WHAT THIS CLOSES'
  - file: Sports_Desk/ingestors/odds_fetcher.py
    pattern: OFFLINE\ BY\ DEFAULT,\ AND\ THAT\ IS\ NOT\ A\ SHORTCUT
    claim: the docstring still carries the section 'OFFLINE BY DEFAULT, AND THAT IS
      NOT A SHORTCUT'
  - file: Sports_Desk/ingestors/odds_fetcher.py
    pattern: THE\ LIVE\ PATH\ IS\ A\ CONTRACT,\ NOT\ A\ SCRAPER
    claim: the docstring still carries the section 'THE LIVE PATH IS A CONTRACT, NOT
      A SCRAPER'
  requires_files:
  - Sports_Desk/ingestors/odds_fetcher.py
  desk: 2
---
# Thesis: Sports_Desk/ingestors/odds_fetcher.py

> 3 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## What This Closes

Sports_Desk had 680 passing tests and no database. Every test built its own SQLite fixture in a temp directory; `data/odds_drops/` held zero files; `sports_market.db` did not exist. The Brier and skill-score machinery was built and had never scored a single forecast, because there were no forecasts. This module is the collector that makes the desk's first real row exist.

## Offline By Default, And That Is Not A Shortcut

Every test in this ecosystem runs without a socket, and the odds watcher it feeds refuses to price a market with no sharp reference in it. So the default source is a bundled multi-book sample that exercises exactly the shape `parse_odds_csv` accepts - a sharp book, three retail books, moneyline / spread / totals, one deliberate retail mispricing per fixture so an edge lands - and a `--url` path for a live feed that is never touched unless asked for. A collector that silently fetched would make the desk's output depend on whether the machine happened to have connectivity, which is not something the operator can see from the screen.

## The Live Path Is A Contract, Not A Scraper

`--url` expects a JSON list of rows already in the CSV column shape below. Adapting a specific provider's payload is a one-function shim the operator writes against the provider's terms; this module does not ship one and does not guess at one.

 event_id,sport,market_type,line,selection,book,odds,is_sharp,timestamp,start_time,is_closing

## Related

- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]
- [[theses_register|Theses register]]
