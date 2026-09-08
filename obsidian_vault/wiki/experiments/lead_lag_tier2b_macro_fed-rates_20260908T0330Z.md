---
type: Experiment
title: 'Lead-lag verdict: Tier 2b, macro / fed-rates, 2026-09-08 03:30Z'
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
  at: '2026-09-08T03:30:01Z'
status: draft
sources:
- id: verdict-json
  resource: cross_market/experiments/lead_lag_tier2b_fed-rates_verdict_run2.json
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
  best_lag_minutes: 10
  correlation: -0.07129424788934347
  n: 1553
  events: 82
  price_points: 9275
  latency_minutes: 0.0
  min_abs_corr: 0.2
  classification: no-lead
  tests_run: 2
  measurement:
    first_event_utc: '2026-09-07T01:21:37Z'
    last_event_utc: '2026-09-08T04:28:28Z'
    price_first_utc: '2026-09-07T01:21:39Z'
    price_last_utc: '2026-09-08T03:29:12Z'
    shift_first_utc: '2026-09-07T02:22:37Z'
    shift_last_utc: '2026-09-08T03:27:28Z'
  data_gaps: []
---
# Lead-lag verdict: Tier 2b, macro / fed-rates, 2026-09-08 03:30Z

> Class: **no-lead** · no measurable lead-lag (peak |corr| 0.07 < 0.2)

## Verdict

| Field | Value |
|---|---|
| tier | 2b |
| family / subfamily | macro / fed-rates |
| membership | tags |
| sufficient | True |
| probability shifts (events) | 82 |
| price points | 9275 |
| best lag (min, + = Polymarket leads) | 10 |
| correlation at peak | -0.071 |
| n at peak | 1553 |
| latency rule (min) | 0.0 |
| bar (min abs corr) | 0.2 |
| classification | **no-lead** |

## Measured span

| Bound | UTC |
|---|---|
| window first (prices sought from) | 2026-09-07T01:21:37Z |
| window last (prices sought to) | 2026-09-08T04:28:28Z |
| price coverage | 2026-09-07T01:21:39Z .. 2026-09-08T03:29:12Z |
| probability shifts | 2026-09-07T02:22:37Z .. 2026-09-08T03:27:28Z |

**data gaps inside this span**: none recorded

## Strongest lags

| Lag (min) | Corr | n |
|---|---|---|
| +10 | -0.071 | 1553 |
| -4 | -0.065 | 1563 |
| -16 | +0.060 | 1563 |
| -33 | +0.059 | 1563 |
| +4 | +0.059 | 1559 |

## Related

- [[btc_macro_regime|BTC macro regime]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
