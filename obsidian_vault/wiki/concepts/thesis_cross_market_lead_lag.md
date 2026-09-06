---
type: Concept
title: 'Thesis: cross_market/lead_lag.py'
description: 'When a Polymarket market''s implied probability moves, does the HyperLiquid
  perp for the related asset move before it, with it, or after it - and by how many
  minutes? The answer is a lag: the offset tau at which the cross-correlation between
  the minute series of probability change…'
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
  resource: cross_market/lead_lag.py
  title: cross_market/lead_lag.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: cross_market/lead_lag.py
  headings:
  - THE QUESTION
  - WHAT THE INPUTS ARE
  - WHAT IT REFUSES TO SAY
  - KNOWN LIMIT TODAY
  asserts:
  - file: cross_market/lead_lag.py
    pattern: THE\ QUESTION
    claim: the docstring still carries the section 'THE QUESTION'
  - file: cross_market/lead_lag.py
    pattern: WHAT\ THE\ INPUTS\ ARE
    claim: the docstring still carries the section 'WHAT THE INPUTS ARE'
  - file: cross_market/lead_lag.py
    pattern: WHAT\ IT\ REFUSES\ TO\ SAY
    claim: the docstring still carries the section 'WHAT IT REFUSES TO SAY'
  - file: cross_market/lead_lag.py
    pattern: KNOWN\ LIMIT\ TODAY
    claim: the docstring still carries the section 'KNOWN LIMIT TODAY'
  requires_files:
  - cross_market/lead_lag.py
  desk: 3
---
# Thesis: cross_market/lead_lag.py

> 4 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## The Question

When a Polymarket market's implied probability moves, does the HyperLiquid perp for the related asset move before it, with it, or after it - and by how many minutes? The answer is a lag: the offset tau at which the cross-correlation between the minute series of probability changes and the minute series of log returns peaks. tau > 0 means the perp moved AFTER the probability (Polymarket leads); tau < 0 means the perp moved first.

## What The Inputs Are

Probability series come from timestamped Polymarket drop files (a list of questions with `question`, `token_id`, `yes_price`, `fetched_at`) or a flat CSV of (ts, key, probability). Prices come from asset_snapshots in hyperliquid_data.db, ~10s cadence, binned to minutes (last mark in the minute).

## What It Refuses To Say

Fewer than `min_events` shifts, or fewer than `min_points` overlapping minutes, and the result is `sufficient: False` with the reason; a peak correlation under `min_abs_corr` is reported as "no measurable lead-lag", not as a lag. A single coincidence is not a lead.

## Known Limit Today

The Polymarket fetcher overwrites one drop file in place, so there is no probability time series on disk yet; this module runs on synthetic data in its tests and on real data once the fetcher keeps timestamped drops.

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
