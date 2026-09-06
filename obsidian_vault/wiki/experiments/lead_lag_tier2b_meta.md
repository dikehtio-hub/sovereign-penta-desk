---
type: Experiment
title: 'Experiment: lead_lag_tier2b_dual_tag_membership'
description: PRE-REGISTERED - runs only after (1) the Tier 1 maiden verdict is in
  Cross_Market_Titans.md, (2) the watcher has been restarted with the Round 76 code,
  and (3) the TAGGED macro series clears the readiness bar on its own
tags:
- experiment
- desk-3
- item-18
- lead-lag
- pre-registered
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:49Z'
status: draft
sources:
- id: registration
  resource: cross_market/experiments/lead_lag_tier2b.meta.json
  title: lead_lag_tier2b.meta.json
  author: human:operator
dev:
  desk: 3
  item: 18
  registration: cross_market/experiments/lead_lag_tier2b.meta.json
  kind: lead_lag
  registered_utc: '2026-09-05T14:27:34.659416+00:00'
  parameters:
  - name: lead_lag_min_abs_corr
    value: 0.2
    file: cross_market/experiments/lead_lag_tier2b.meta.json
    json_path: bars.min_abs_corr
  - name: lead_lag_min_events
    value: 5
    file: cross_market/experiments/lead_lag_tier2b.meta.json
    json_path: bars.min_events
  - name: lead_lag_min_points
    value: 60
    file: cross_market/experiments/lead_lag_tier2b.meta.json
    json_path: bars.min_points
  - name: lead_lag_latency_minutes_crypto
    value: 5.0
    file: cross_market/experiments/lead_lag_tier2b.meta.json
    json_path: bars.latency_minutes_crypto
  - name: lead_lag_latency_minutes_fed_rates
    value: 0.0
    file: cross_market/experiments/lead_lag_tier2b.meta.json
    json_path: bars.latency_minutes_fed_rates
  tests_run: 0
---
# Experiment: lead_lag_tier2b_dual_tag_membership

> Pre-registration, Item 18 (lead-lag). Verdict pages link back here when they land.

## Status at registration

PRE-REGISTERED - runs only after (1) the Tier 1 maiden verdict is in Cross_Market_Titans.md, (2) the watcher has been restarted with the Round 76 code, and (3) the TAGGED macro series clears the readiness bar on its own

## Decision

Ratification 76-3 (Round 77 prompt): Tier 2 stays an exclusive partition by `sport`; membership analysis is registered here as Tier 2b in a NEW file, never by amending lead_lag_tier2.meta.json.

## Differs from tier2 only in

MEMBERSHIP: a question belongs to every subfamily named in its Round 76 `tags` list, so a market fetched under both crypto and fed-rates counts in BOTH. Under Tier 2 (first tag wins) it counts once, as crypto.

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

## Reading rule

Report Tier 2 and Tier 2b side by side per subfamily. Where they agree, the dual-tagged markets do not drive the result. Where they disagree, that disagreement IS the finding: the dual-tagged markets carry it, and neither tier is 'the' answer. Tier 2b never overrides Tier 2; the Tier 1 bar and verdict are untouched.

## Commands

```
python -m cross_market.lead_lag --coin BTC --family macro --subfamily fed-rates --subfamily-from tags
python -m cross_market.lead_lag --coin BTC --family macro --subfamily crypto --subfamily-from tags --latency-minutes 5
```

## Caveats

- Not independent of Tier 2: the same markets and the same BTC return series.
- A Tier 2b subfamily can be READY only ~24 h after the post-maiden watcher restart.
- The `tags` list holds the slugs the market was fetched under (--tags), not every Gamma tag on the event.

## Enforced in code

lead_lag.load_drop_records(subfamily_from='tags'), lead_lag.tagged_stamped_moments(), CLI --subfamily-from tags (gate and --check-data count tagged stamps only)

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
- [[experiments_register|Experiments register]]
