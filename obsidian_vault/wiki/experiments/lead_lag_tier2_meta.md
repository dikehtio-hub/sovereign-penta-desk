---
type: Experiment
title: 'Experiment: lead_lag_tier2_subfamilies'
description: PRE-REGISTERED - runs only AFTER the Tier 1 maiden run has written its
  verdict to Cross_Market_Titans.md
tags:
- experiment
- desk-3
- item-18
- lead-lag
- pre-registered
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T03:28:56Z'
status: draft
sources:
- id: registration
  resource: cross_market/experiments/lead_lag_tier2.meta.json
  title: lead_lag_tier2.meta.json
  author: human:operator
dev:
  desk: 3
  item: 18
  registration: cross_market/experiments/lead_lag_tier2.meta.json
  kind: lead_lag
  registered_utc: '2026-09-05T10:00:03.614113+00:00'
  parameters:
  - name: lead_lag_min_abs_corr
    value: 0.2
    file: cross_market/experiments/lead_lag_tier2.meta.json
    json_path: bars.min_abs_corr
  - name: lead_lag_min_events
    value: 5
    file: cross_market/experiments/lead_lag_tier2.meta.json
    json_path: bars.min_events
  - name: lead_lag_min_points
    value: 60
    file: cross_market/experiments/lead_lag_tier2.meta.json
    json_path: bars.min_points
  - name: lead_lag_latency_minutes_crypto
    value: 5.0
    file: cross_market/experiments/lead_lag_tier2.meta.json
    json_path: bars.latency_minutes_crypto
  - name: lead_lag_latency_minutes_fed_rates
    value: 0.0
    file: cross_market/experiments/lead_lag_tier2.meta.json
    json_path: bars.latency_minutes_fed_rates
  tests_run: 6
---
# Experiment: lead_lag_tier2_subfamilies

> Pre-registration, Item 18 (lead-lag). Verdict pages link back here when they land.

## Status at registration

PRE-REGISTERED - runs only AFTER the Tier 1 maiden run has written its verdict to Cross_Market_Titans.md

## Why

The macro family mixes exogenous policy questions (Fed decisions) with crypto milestone questions ('Will the price of Bitcoin be above $80,000 on September 5?') whose probability moves BECAUSE BTC moved. Pooled, the mechanical group dominates the correlation, and any lead it shows can be the watcher's 5-minute poll latency rather than prediction.

## Tier1 unchanged

{'family': 'macro', 'min_abs_corr': 0.2, 'min_events': 5, 'min_points': 60, 'readiness': {'min_span_hours': 24, 'min_points': 200, 'max_gap_minutes': 60}, 'due_utc': '2026-09-06T01:39:49Z', 'rule': 'Ruling 74-2: the Tier 1 bar and gate are not moved, relaxed or amended by anything below.'}

## Bars

| Bar | Value |
|---|---|
| `min_abs_corr` | 0.2 |
| `min_events` | 5 |
| `min_points` | 60 |
| `insufficient_rule` | a subfamily under min_events or min_points is 'insufficient', not a verdict |
| `latency_minutes_crypto` | 5.0 |
| `latency_minutes_fed_rates` | 0.0 |

## Subfamilies

- **fed-rates**: exogenous: a policy repricing that BTC may or may not follow · the Tier 1 interpretation, unchanged
- **crypto**: endogenous: the question is a function of the BTC price · a peak with |lag| <= 5 min (POLL_INTERVAL_MINUTES) is 'contemporaneous repricing within the poll interval: latency, not a lead'; only a peak OUTSIDE the poll interval that clears the bar may be called a lead

## Commands

```
python -m cross_market.lead_lag --coin BTC --family macro --subfamily fed-rates
python -m cross_market.lead_lag --coin BTC --family macro --subfamily crypto --latency-minutes 5
```

## Caveats

- collect_live_questions dedupes by token with FIRST TAG WINS; the launcher fetches crypto before fed-rates, so a market carrying both tags is labelled CRYPTO.
- Drop records carry no tag_slug field; the label lives in `sport` (Round 52 category labelling).
- The two subfamilies share the BTC return series, so their results are not independent tests.

## Enforced in code

lead_lag.load_drop_records(subfamily=...), lead_lag_report(latency_minutes=...)

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
- [[experiments_register|Experiments register]]
