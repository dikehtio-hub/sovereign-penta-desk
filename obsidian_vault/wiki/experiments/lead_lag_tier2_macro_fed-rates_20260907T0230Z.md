---
type: Experiment
title: 'Lead-lag verdict: Tier 2, macro / fed-rates, 2026-09-07 02:30Z'
description: 'Tier 2 lead-lag verdict for macro / fed-rates: no-lead.'
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
  at: '2026-09-07T02:30:18Z'
status: draft
sources:
- id: verdict-json
  resource: cross_market/experiments/lead_lag_tier2_fed-rates_verdict.json
  title: cross_market.lead_lag --json output
  author: process:cross_market.lead_lag
dev:
  desk: 3
  item: 18
  kind: lead_lag_verdict
  tier: '2'
  family: macro
  subfamily: fed-rates
  membership: label
  sufficient: true
  best_lag_minutes: -10
  correlation: 0.05248156354629275
  n: 2416
  events: 234
  price_points: 14442
  latency_minutes: 0.0
  min_abs_corr: 0.2
  classification: no-lead
  tests_run: 1
---
# Lead-lag verdict: Tier 2, macro / fed-rates, 2026-09-07 02:30Z

> Class: **no-lead** · no measurable lead-lag (peak |corr| 0.05 < 0.2)

## Verdict

| Field | Value |
|---|---|
| tier | 2 |
| family / subfamily | macro / fed-rates |
| membership | label |
| sufficient | True |
| probability shifts (events) | 234 |
| price points | 14442 |
| best lag (min, + = Polymarket leads) | -10 |
| correlation at peak | +0.052 |
| n at peak | 2416 |
| latency rule (min) | 0.0 |
| bar (min abs corr) | 0.2 |
| classification | **no-lead** |

## Strongest lags

| Lag (min) | Corr | n |
|---|---|---|
| -10 | +0.052 | 2416 |
| -24 | -0.043 | 2416 |
| +18 | +0.041 | 2399 |
| +58 | +0.039 | 2359 |
| -42 | +0.039 | 2416 |

## Related

- [[btc_macro_regime|BTC macro regime]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
