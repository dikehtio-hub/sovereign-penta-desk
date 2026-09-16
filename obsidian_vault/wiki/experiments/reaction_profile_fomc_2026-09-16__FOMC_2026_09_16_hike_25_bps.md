---
type: Experiment
title: 'Reaction profile: fomc_2026-09-16 / FOMC 2026-09-16: hike 25 bps'
description: 'fomc_2026-09-16: FOMC 2026-09-16: hike 25 bps - uninformative-shock.'
tags:
- experiment
- desk-3
- item-18
- lead-lag
- event-study
- reaction-profile
- uninformative-shock
- fomc_2026-09-16
generated:
  by: claude-code/fable-5.1
  at: '2026-09-16T21:13:59Z'
status: draft
sources:
- id: event-study-json
  resource: cross_market/experiments/event_study_fomc_2026-09-16.json
  title: cross_market.event_study --json
  author: process:cross_market.event_study
dev:
  desk: 3
  item: 18
  kind: event_study_profile
  event: fomc_2026-09-16
  event_kind: fed_rate
  token_id: '63842529068710005716169325380315470359047749786610778647370693404952498013178'
  label: 'FOMC 2026-09-16: hike 25 bps'
  registration: cross_market/experiments/lead_lag_phase2_fomc.meta.json
  release_utc: '2026-09-16T18:00:00Z'
  classification: uninformative-shock
  lead_s: null
  informative: false
  sufficient: true
  primary: true
  pm:
    baseline: 0.875
    final: 0.975
    dp: 0.1
    displaced: true
    t_star_rel_s: 1
    stamps: 418
  hl:
    coin: BTC
    baseline_px: 75783.0
    baseline_age_s: 0.319
    final_px: 75832.0
    dp_rel_bps: 6.4658
    displaced: false
    t_star_rel_s: null
    prints: 10274
  bars:
    pm_min_displacement: 0.02
    hl_bar_bps: 17.4292
    hl_bar_source: trailing_60m_relative
    hl_median_5m_bps: 5.8097
    hl_marks: 244
    lead_tolerance_s: 1.0
    half_life_fraction: 0.5
  measurement:
    first_event_utc: '2026-09-16T17:58:01Z'
    last_event_utc: '2026-09-16T18:05:00Z'
    baseline_utc: '2026-09-16T17:59:55Z'
  data_gaps: []
---
# Reaction profile: fomc_2026-09-16 / FOMC 2026-09-16: hike 25 bps

> Event `fomc_2026-09-16` (FOMC rate decision, 2026-09-16 14:00 EDT) · T `2026-09-16T18:00:00Z` · class **uninformative-shock** · lead n/a s · NOT counted toward the panel

## Measurement

| Field | Polymarket (this market) | HyperLiquid (BTC) |
|---|---|---|
| baseline P(T-5 s) | 0.875 | 75783 (print age 0.319 s) |
| final P(T+300 s) | 0.975 | 75832 |
| displacement | 0.1 | 6.4658 bps |
| bar | 0.02 | 17.4292 bps (trailing_60m_relative) |
| displaced | True | False |
| t*50% (s from T) | 1 | n/a |
| stamps / prints in window | 418 | 10274 |

## Grid

- T0 (first stamp): `2026-09-16T17:58:01Z`; baseline `2026-09-16T17:59:55Z`; window end `2026-09-16T18:05:00Z`; grid 1 s
- lead_s = t*HL - t*PM = n/a; tolerance ±1 s; half-life fraction 0.5

## Reasons

- uninformative: hyperliquid |dP| 6.47 bps < bar 17.43 bps

## Related

- [[lead_lag_phase2_fomc_meta|Phase 2 registration]]
- [[lead_lag_phase2_panel|Phase 2 panel]]
- [[btc_macro_regime|BTC macro regime (Phase 1 consensus)]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
