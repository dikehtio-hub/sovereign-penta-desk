---
type: Experiment
title: 'Lead-lag verdict: Tier 2b, macro / crypto, 2026-09-08 03:30Z'
description: 'Tier 2b lead-lag verdict for macro / crypto: no-lead.'
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
  at: '2026-09-08T03:30:08Z'
status: draft
sources:
- id: verdict-json
  resource: cross_market/experiments/lead_lag_tier2b_crypto_verdict_run2.json
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
  best_lag_minutes: -35
  correlation: -0.1013092656518123
  n: 1563
  events: 1830
  price_points: 9275
  latency_minutes: 5.0
  min_abs_corr: 0.2
  classification: no-lead
  tests_run: 2
  measurement:
    first_event_utc: '2026-09-07T01:21:37Z'
    last_event_utc: '2026-09-08T04:28:27Z'
    price_first_utc: '2026-09-07T01:21:39Z'
    price_last_utc: '2026-09-08T03:29:12Z'
    shift_first_utc: '2026-09-07T02:22:37Z'
    shift_last_utc: '2026-09-08T03:27:27Z'
  data_gaps: []
---
# Lead-lag verdict: Tier 2b, macro / crypto, 2026-09-08 03:30Z

> Class: **no-lead** · no measurable lead-lag (peak |corr| 0.10 < 0.2)

## Verdict

| Field | Value |
|---|---|
| tier | 2b |
| family / subfamily | macro / crypto |
| membership | tags |
| sufficient | True |
| probability shifts (events) | 1830 |
| price points | 9275 |
| best lag (min, + = Polymarket leads) | -35 |
| correlation at peak | -0.101 |
| n at peak | 1563 |
| latency rule (min) | 5.0 |
| bar (min abs corr) | 0.2 |
| classification | **no-lead** |

## Measured span

| Bound | UTC |
|---|---|
| window first (prices sought from) | 2026-09-07T01:21:37Z |
| window last (prices sought to) | 2026-09-08T04:28:27Z |
| price coverage | 2026-09-07T01:21:39Z .. 2026-09-08T03:29:12Z |
| probability shifts | 2026-09-07T02:22:37Z .. 2026-09-08T03:27:27Z |

**data gaps inside this span**: none recorded

## Strongest lags

| Lag (min) | Corr | n |
|---|---|---|
| -35 | -0.101 | 1563 |
| -59 | -0.096 | 1562 |
| +60 | -0.075 | 1503 |
| -34 | -0.075 | 1563 |
| +45 | +0.073 | 1518 |

## Related

- [[btc_macro_regime|BTC macro regime]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
