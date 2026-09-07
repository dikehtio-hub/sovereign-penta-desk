---
type: Experiment
title: 'Lead-lag verdict: Tier 2, macro / crypto, 2026-09-07 02:30Z'
description: 'Tier 2 lead-lag verdict for macro / crypto: no-lead.'
tags:
- experiment
- desk-3
- item-18
- lead-lag
- verdict
- tier-2
- no-lead
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T02:30:23Z'
status: draft
sources:
- id: verdict-json
  resource: cross_market/experiments/lead_lag_tier2_crypto_verdict.json
  title: cross_market.lead_lag --json output
  author: process:cross_market.lead_lag
dev:
  desk: 3
  item: 18
  kind: lead_lag_verdict
  tier: '2'
  family: macro
  subfamily: crypto
  membership: label
  sufficient: true
  best_lag_minutes: 38
  correlation: -0.13802395931258107
  n: 2389
  events: 3081
  price_points: 14505
  latency_minutes: 5.0
  min_abs_corr: 0.2
  classification: no-lead
  tests_run: 1
---
# Lead-lag verdict: Tier 2, macro / crypto, 2026-09-07 02:30Z

> Class: **no-lead** · no measurable lead-lag (peak |corr| 0.14 < 0.2)

## Verdict

| Field | Value |
|---|---|
| tier | 2 |
| family / subfamily | macro / crypto |
| membership | label |
| sufficient | True |
| probability shifts (events) | 3081 |
| price points | 14505 |
| best lag (min, + = Polymarket leads) | 38 |
| correlation at peak | -0.138 |
| n at peak | 2389 |
| latency rule (min) | 5.0 |
| bar (min abs corr) | 0.2 |
| classification | **no-lead** |

## Strongest lags

| Lag (min) | Corr | n |
|---|---|---|
| +38 | -0.138 | 2389 |
| +53 | +0.106 | 2374 |
| +43 | -0.092 | 2384 |
| -48 | +0.088 | 2427 |
| -28 | -0.057 | 2427 |

## Related

- [[btc_macro_regime|BTC macro regime]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
