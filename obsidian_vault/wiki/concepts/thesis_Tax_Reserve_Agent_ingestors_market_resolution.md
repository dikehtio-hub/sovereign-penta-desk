---
type: Concept
title: 'Thesis: Tax_Reserve_Agent/ingestors/market_resolution.py'
description: Every other ingestor reports something that happened; this one INFERS
  that something happened and then writes a realised loss off the back of that inference.
  A false write-off invents a capital loss, which lowers net gains, which lowers the
  tax escrow - so the failure mode points…
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
  resource: Tax_Reserve_Agent/ingestors/market_resolution.py
  title: Tax_Reserve_Agent/ingestors/market_resolution.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Tax_Reserve_Agent/ingestors/market_resolution.py
  headings:
  - WHY THIS IS WRITTEN SO DEFENSIVELY
  asserts:
  - file: Tax_Reserve_Agent/ingestors/market_resolution.py
    pattern: WHY\ THIS\ IS\ WRITTEN\ SO\ DEFENSIVELY
    claim: the docstring still carries the section 'WHY THIS IS WRITTEN SO DEFENSIVELY'
  requires_files:
  - Tax_Reserve_Agent/ingestors/market_resolution.py
  desk: 5
---
# Thesis: Tax_Reserve_Agent/ingestors/market_resolution.py

> 1 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Why This Is Written So Defensively

Every other ingestor reports something that happened; this one INFERS that something happened and then writes a realised loss off the back of that inference. A false write-off invents a capital loss, which lowers net gains, which lowers the tax escrow - so the failure mode points directly at under-reserving for a real tax bill. Three rules follow from that:

 1. RESOLUTION IS VERIFIED ON CHAIN, NOT ASSUMED FROM GAMMA. Gamma's `closed` flag means the market stopped trading, which is not the same as payouts having been reported - a market can close days before UMA resolves it, and can close disputed. `payoutDenominator > 0` on the ConditionalTokens contract is the authoritative statement that payouts exist. Gamma is used to find CANDIDATES cheaply; the chain decides. `--trust-gamma` relaxes this and says so loudly. 2. A CONDITION'S LEGS SETTLE TOGETHER. Splitting $100 and holding both legs to resolution is a wash: +$50 winner, -$50 loser. Writing off only the loser invents a $50 loss. Every open leg of a resolved condition is booked in the same batch. 3. NOTHING IS WRITTEN WITHOUT `--apply`. The default is a plan you can read.

 The settlement is dated to the market's resolution, never to today, because the date picks the tax year. A condition whose resolution date cannot be established is skipped rather than dated to now.

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
- [[theses_register|Theses register]]
