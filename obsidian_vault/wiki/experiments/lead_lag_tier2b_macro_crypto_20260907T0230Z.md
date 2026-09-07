---
type: Experiment
title: 'Lead-lag verdict: Tier 2b, macro / crypto, 2026-09-07 02:30Z'
description: 'Tier 2b lead-lag verdict for macro / crypto: polymarket-leads.'
tags:
- experiment
- desk-3
- item-18
- lead-lag
- verdict
- tier-2b
- polymarket-leads
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T02:30:34Z'
status: draft
sources:
- id: verdict-json
  resource: cross_market/data/lead_lag_tier2b_crypto_verdict.json
  title: cross_market.lead_lag --json output
  author: process:cross_market.lead_lag
dev:
  desk: 3
  item: 18
  kind: lead_lag_verdict
  tier: 2b
  family: macro
  subfamily: crypto
  membership: tags
  sufficient: true
  best_lag_minutes: 38
  correlation: -0.32504762712388213
  n: 910
  events: 1751
  price_points: 5677
  latency_minutes: 5.0
  min_abs_corr: 0.2
  classification: polymarket-leads
  tests_run: 1
---
# Lead-lag verdict: Tier 2b, macro / crypto, 2026-09-07 02:30Z

> Class: **polymarket-leads** · Polymarket leads HyperLiquid by 38 min (corr -0.33, n=910)

## Verdict

| Field | Value |
|---|---|
| tier | 2b |
| family / subfamily | macro / crypto |
| membership | tags |
| sufficient | True |
| probability shifts (events) | 1751 |
| price points | 5677 |
| best lag (min, + = Polymarket leads) | 38 |
| correlation at peak | -0.325 |
| n at peak | 910 |
| latency rule (min) | 5.0 |
| bar (min abs corr) | 0.2 |
| classification | **polymarket-leads** |

## Strongest lags

| Lag (min) | Corr | n |
|---|---|---|
| +38 | -0.325 | 910 |
| +53 | +0.269 | 895 |
| +43 | -0.234 | 905 |
| -48 | +0.192 | 947 |
| -28 | -0.176 | 947 |

## Related

- [[btc_macro_regime|BTC macro regime]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
