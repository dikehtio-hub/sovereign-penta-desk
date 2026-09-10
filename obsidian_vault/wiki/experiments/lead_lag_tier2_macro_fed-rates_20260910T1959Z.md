---
type: Experiment
title: 'Lead-lag verdict: Tier 2, macro / fed-rates, 2026-09-10 19:59Z'
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
  at: '2026-09-10T19:59:30Z'
status: draft
sources:
- id: verdict-json
  resource: cross_market/experiments/lead_lag_tier2_fed-rates_verdict_run3.json
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
  best_lag_minutes: 13
  correlation: 0.07869253487776973
  n: 1503
  events: 229
  price_points: 8370
  latency_minutes: 0.0
  min_abs_corr: 0.2
  classification: no-lead
  tests_run: 3
  measurement:
    first_event_utc: '2026-09-09T18:30:09Z'
    last_event_utc: '2026-09-10T20:57:49Z'
    price_first_utc: '2026-09-09T18:30:15Z'
    price_last_utc: '2026-09-10T19:58:54Z'
    shift_first_utc: '2026-09-09T19:31:09Z'
    shift_last_utc: '2026-09-10T19:56:49Z'
  data_gaps: []
---
# Lead-lag verdict: Tier 2, macro / fed-rates, 2026-09-10 19:59Z

> Class: **no-lead** · no measurable lead-lag (peak |corr| 0.08 < 0.2)

## Verdict

| Field | Value |
|---|---|
| tier | 2 |
| family / subfamily | macro / fed-rates |
| membership | label |
| sufficient | True |
| probability shifts (events) | 229 |
| price points | 8370 |
| best lag (min, + = Polymarket leads) | 13 |
| correlation at peak | +0.079 |
| n at peak | 1503 |
| latency rule (min) | 0.0 |
| bar (min abs corr) | 0.2 |
| classification | **no-lead** |

## Measured span

| Bound | UTC |
|---|---|
| window first (prices sought from) | 2026-09-09T18:30:09Z |
| window last (prices sought to) | 2026-09-10T20:57:49Z |
| price coverage | 2026-09-09T18:30:15Z .. 2026-09-10T19:58:54Z |
| probability shifts | 2026-09-09T19:31:09Z .. 2026-09-10T19:56:49Z |

**data gaps inside this span**: none recorded

## Strongest lags

| Lag (min) | Corr | n |
|---|---|---|
| +13 | +0.079 | 1503 |
| +3 | +0.078 | 1512 |
| -47 | -0.071 | 1514 |
| +9 | -0.067 | 1507 |
| -10 | -0.063 | 1514 |

## Related

- [[btc_macro_regime|BTC macro regime]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
