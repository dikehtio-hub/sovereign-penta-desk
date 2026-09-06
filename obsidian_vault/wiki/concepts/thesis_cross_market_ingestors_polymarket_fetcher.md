---
type: Concept
title: 'Thesis: cross_market/ingestors/polymarket_fetcher.py'
description: '`Cross_Market_Arb.md` reported "0 questions loaded" because nothing
  had ever written a JSON file into the drop folder the exporter reads. The matcher,
  the asymmetric-tax engine and the two hurdles were all built and had never seen
  a Polymarket question. This module is the collect…'
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
  resource: cross_market/ingestors/polymarket_fetcher.py
  title: cross_market/ingestors/polymarket_fetcher.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: cross_market/ingestors/polymarket_fetcher.py
  headings:
  - WHAT THIS CLOSES
  - OFFLINE BY DEFAULT
  - THE LIVE PATH, VERIFIED 2026-09-04 AGAINST GAMMA
  asserts:
  - file: cross_market/ingestors/polymarket_fetcher.py
    pattern: WHAT\ THIS\ CLOSES
    claim: the docstring still carries the section 'WHAT THIS CLOSES'
  - file: cross_market/ingestors/polymarket_fetcher.py
    pattern: OFFLINE\ BY\ DEFAULT
    claim: the docstring still carries the section 'OFFLINE BY DEFAULT'
  - file: cross_market/ingestors/polymarket_fetcher.py
    pattern: THE\ LIVE\ PATH,\ VERIFIED\ 2026\-09\-04\ AGAINST\ GAMMA
    claim: the docstring still carries the section 'THE LIVE PATH, VERIFIED 2026-09-04
      AGAINST GAMMA'
  requires_files:
  - cross_market/ingestors/polymarket_fetcher.py
  desk: 3
---
# Thesis: cross_market/ingestors/polymarket_fetcher.py

> 3 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## What This Closes

`Cross_Market_Arb.md` reported "0 questions loaded" because nothing had ever written a JSON file into the drop folder the exporter reads. The matcher, the asymmetric-tax engine and the two hurdles were all built and had never seen a Polymarket question. This module is the collector that makes the first one exist.

## Offline By Default

The bundled sample carries questions on the SAME fixtures `odds_fetcher.py` prices into `sports_market.db` (Chiefs/Ravens, Eagles/Cowboys), phrased in the shapes `matcher.parse_polymarket_question` actually parses, so the pipeline produces matched pairs rather than an empty table. Prices are plausible, not live; every pair is expected to REJECT against the 16.75% hurdle, because real cross-market arbs pay 1-3% and the sample does not pretend otherwise.

## The Live Path, Verified 2026-09-04 Against Gamma

* `?tag=sports` is IGNORED. Antigravity's handoff named it; a live call returned a crypto IPO event and a French-politics event. The filter Gamma honours is `tag_id=1`, and `/tags/slug/sports` confirms id 1 is the "Sports" tag. * `outcomes`, `outcomePrices` and `clobTokenIds` arrive as JSON-encoded STRINGS, not arrays (the tax ingestor learned this in Round 26). * Two market shapes exist. A binary ("Will Jannik Sinner win ...?") has outcomes ["Yes","No"] and the YES price is outcomePrices[0]. A FIXTURE market ("St. Louis Cardinals vs. Los Angeles Dodgers") has the two TEAMS as outcomes; it is not yes/no, and the matcher cannot read a bare "A vs B" because it does not say which side the share is long. So a fixture market is rewritten into two derived questions - "Will the A beat the B?" priced at outcome 0, "Will the B beat the A?" at outcome 1 - each carrying `derived_from` so nobody mistakes the wording for Polymarket's. * `bestAsk` is what a YES share costs to BUY, so it is the price used for the first outcome when present; otherwise `outcomePrices`. The basis is recorded. * Fees are NOT inferred. `takerBaseFee` appears on markets and its unit is not documented; guessing a fee into the hurdle would be a fabricated number. The raw value is carried for the record and `fee_rate` comes only from `--fee-rate`, which defaults to 0.0.

 Questions are written in exactly the dict shape `hud.scan_cross_market` consumes: `question`, `yes_price`, `token_id`, and optionally `sport` and `fee_rate`.

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
