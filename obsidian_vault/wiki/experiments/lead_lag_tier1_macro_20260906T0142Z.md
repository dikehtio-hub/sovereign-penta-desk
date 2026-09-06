---
type: Experiment
title: 'Lead-lag verdict: Tier 1, macro, 2026-09-06 01:42Z'
description: 'Tier 1 lead-lag verdict for macro: no-lead.'
tags:
- experiment
- desk-3
- item-18
- lead-lag
- verdict
- tier-1
- no-lead
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T01:42:14Z'
status: draft
sources:
- id: verdict-json
  resource: cross_market/data/lead_lag_tier1_verdict.json
  title: cross_market.lead_lag --json output
  author: process:cross_market.lead_lag
dev:
  desk: 3
  item: 18
  kind: lead_lag_verdict
  tier: '1'
  family: macro
  subfamily: null
  membership: label
  sufficient: true
  best_lag_minutes: -45
  correlation: 0.0696256609657804
  n: 1497
  events: 1465
  price_points: 8927
  latency_minutes: 0.0
  min_abs_corr: 0.2
  classification: no-lead
  tests_run: 1
---
# Lead-lag verdict: Tier 1, macro, 2026-09-06 01:42Z

> Class: **no-lead** · no measurable lead-lag (peak |corr| 0.07 < 0.2)

## Verdict

| Field | Value |
|---|---|
| tier | 1 |
| family / subfamily | macro / - |
| membership | label |
| sufficient | True |
| probability shifts (events) | 1465 |
| price points | 8927 |
| best lag (min, + = Polymarket leads) | -45 |
| correlation at peak | +0.070 |
| n at peak | 1497 |
| latency rule (min) | 0.0 |
| bar (min abs corr) | 0.2 |
| classification | **no-lead** |

## Strongest lags

| Lag (min) | Corr | n |
|---|---|---|
| -45 | +0.070 | 1497 |
| -46 | -0.069 | 1497 |
| -31 | +0.061 | 1497 |
| -7 | +0.060 | 1497 |
| -33 | -0.060 | 1497 |

## Related

- [[btc_macro_regime|BTC macro regime]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
