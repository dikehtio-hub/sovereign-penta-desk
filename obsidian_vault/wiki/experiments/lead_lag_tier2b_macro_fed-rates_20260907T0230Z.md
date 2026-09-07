---
type: Experiment
title: 'Lead-lag verdict: Tier 2b, macro / fed-rates, 2026-09-07 02:30Z'
description: 'Tier 2b lead-lag verdict for macro / fed-rates: no-lead.'
tags:
- experiment
- desk-3
- item-18
- lead-lag
- verdict
- tier-2b
- no-lead
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T02:30:29Z'
status: draft
sources:
- id: verdict-json
  resource: cross_market/data/lead_lag_tier2b_fed-rates_verdict.json
  title: cross_market.lead_lag --json output
  author: process:cross_market.lead_lag
dev:
  desk: 3
  item: 18
  kind: lead_lag_verdict
  tier: 2b
  family: macro
  subfamily: fed-rates
  membership: tags
  sufficient: true
  best_lag_minutes: 58
  correlation: 0.13506220849793246
  n: 890
  events: 76
  price_points: 5676
  latency_minutes: 0.0
  min_abs_corr: 0.2
  classification: no-lead
  tests_run: 1
---
# Lead-lag verdict: Tier 2b, macro / fed-rates, 2026-09-07 02:30Z

> Class: **no-lead** · no measurable lead-lag (peak |corr| 0.14 < 0.2)

## Verdict

| Field | Value |
|---|---|
| tier | 2b |
| family / subfamily | macro / fed-rates |
| membership | tags |
| sufficient | True |
| probability shifts (events) | 76 |
| price points | 5676 |
| best lag (min, + = Polymarket leads) | 58 |
| correlation at peak | +0.135 |
| n at peak | 890 |
| latency rule (min) | 0.0 |
| bar (min abs corr) | 0.2 |
| classification | **no-lead** |

## Strongest lags

| Lag (min) | Corr | n |
|---|---|---|
| +58 | +0.135 | 890 |
| -58 | +0.082 | 947 |
| +38 | -0.080 | 910 |
| -43 | -0.069 | 947 |
| +11 | -0.054 | 937 |

## Related

- [[btc_macro_regime|BTC macro regime]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
