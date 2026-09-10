---
type: Experiment
title: 'Experiment: passive_fade_rebenchmark'
description: PASSIVE - the fade does not trade; sweeps accumulate with execution disabled
tags:
- experiment
- desk-1
- registration
generated:
  by: claude-code/fable-5.1
  at: '2026-09-10T21:28:10Z'
status: draft
sources:
- id: registration
  resource: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
  title: passive_fade_rebenchmark.meta.json
  author: human:operator
dev:
  desk: 1
  registration: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
  kind: registration
  item: 14
  related_items:
  - 8
  registered_utc: '2026-09-01T05:42:16.383702+00:00'
  progress:
    accumulated: 21383
    target: 500
    unit: events
    status: accumulating
    measured_at: '2026-09-10T21:28:10Z'
    gates:
      min_events:
        value: 21383
        bar: 500
        pass: true
      min_coins:
        value: 76
        bar: 20
        pass: true
      max_single_coin_share:
        value: 0.2457
        bar: 0.2
        pass: false
      window_days:
        value: 9.68
        bar: 7.0
        pass: true
    population: trade_sweep
    last_verdict:
      grade: INSUFFICIENT
      page: passive_fade_rebenchmark_verdict
      at: '2026-09-06T19:44:26.500127Z'
  parameters:
  - name: passive_fade_rebenchmark_sample_requirements_window_days
    value: 7
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: sample_requirements.window_days
  - name: passive_fade_rebenchmark_sample_requirements_min_events
    value: 500
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: sample_requirements.min_events
  - name: passive_fade_rebenchmark_sample_requirements_min_coins
    value: 20
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: sample_requirements.min_coins
  - name: passive_fade_rebenchmark_sample_requirements_max_single_coin_share
    value: 0.2
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: sample_requirements.max_single_coin_share
  - name: passive_fade_rebenchmark_state_at_registration_events
    value: 492
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.events
  - name: passive_fade_rebenchmark_state_at_registration_coins
    value: 15
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.coins
  - name: passive_fade_rebenchmark_state_at_registration_hhi
    value: 0.36
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.hhi
  - name: passive_fade_rebenchmark_state_at_registration_top_coin_share
    value: 0.43
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.top_coin_share
  - name: passive_fade_rebenchmark_state_at_registration_ratio_30m
    value: 0.518
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.ratio_30m
  - name: passive_fade_rebenchmark_state_at_registration_control_30m
    value: 0.862
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.control_30m
  - name: passive_fade_rebenchmark_state_at_registration_cluster_p_ge_1_by_horizon_5m
    value: 0.0827
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.cluster_p_ge_1_by_horizon.5m
  - name: passive_fade_rebenchmark_state_at_registration_cluster_p_ge_1_by_horizon_15m
    value: 0.0772
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.cluster_p_ge_1_by_horizon.15m
  - name: passive_fade_rebenchmark_state_at_registration_cluster_p_ge_1_by_horizon_30m
    value: 0.0259
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: state_at_registration.cluster_p_ge_1_by_horizon.30m
  tests_run: 0
---
# Experiment: passive_fade_rebenchmark

> Pre-registration: bars fixed before the data. Amendments are listed, never applied silently.
> [!NOTE]
> **ACCUMULATING** - 3/4 sample gates pass over population `trade_sweep`. Failing: max_single_coin_share 0.2457 vs 0.2. Last evaluation 2026-09-06: **INSUFFICIENT** ([[passive_fade_rebenchmark_verdict]]) - an insufficient sample is never a verdict, so the question stays open.


## Registered utc

2026-09-01T05:42:16.383702+00:00

## Status

PASSIVE - the fade does not trade; sweeps accumulate with execution disabled

## Why

The retirement verdict came from 15.2 hours in which CASHCAT and PONS supplied 83% of all events (HHI 0.360). The direction was consistent across 10 of 12 coins, but the headline 0.513 is substantially a two-microcap artifact - the broad-market effect was 0.849.

## Sample requirements

| Key | Value |
|---|---|
| `window_days` | 7 |
| `min_events` | 500 |
| `min_coins` | 20 |
| `max_single_coin_share` | 0.2 |
| `note` | Enforced in code by wick_benchmark.reopening_gate(). |

## Population

| Key | Value |
|---|---|
| `recorded_utc` | 2026-09-06T19:10:12.329926Z |
| `source` | trade_sweep |
| `basis` | wick_benchmark.benchmark() and the `excursion` command default to trade_sweep ('the strategy's'); this registration's status line says sweeps accumulate; measurement_schema.sql keeps the source column because the two event sources answer di |
| `finding` | Round 113 mirrored the sample gates over BOTH treatment sources pooled (19,008 events, 62 coins, top coin ZEC 19.84%) and marked this registration ready. Over trade_sweep alone at the same instant: 13,645 events, 46 coins, top coin ZEC 26.6 |
| `bars_unchanged` | true |

## Reopening bar

| Key | Value |
|---|---|
| `rule` | P(ratio >= 1.25) > 0.90 under a CLUSTER bootstrap resampling coins |
| `rationale` | Deliberately asymmetric. Retiring took p=0.024 on a narrow sample; coming back should cost more than leaving did. |

## State at registration

| Key | Value |
|---|---|
| `events` | 492 |
| `coins` | 15 |
| `hhi` | 0.36 |
| `top_coin_share` | 0.43 |
| `ratio_30m` | 0.518 |
| `control_30m` | 0.862 |
| `cluster_p_ge_1_by_horizon` | {"5m": 0.0827, "15m": 0.0772, "30m": 0.0259} |
| `caveat` | Only the 30m horizon clears p<0.05 under clustering. At 5m and 15m the result is NOT significant. The retirement rests on one horizon of a concentrated sample. |

## Auditing standard

Every excursion run now reports asset-concentration HHI, coins measured, top-coin share, and a cluster-bootstrapped p-value. Event-level bootstraps are invalid here because forward windows on the same coin overlap.

## Data retention

| Key | Value |
|---|---|
| `recorded_utc` | 2026-09-04T00:00:00+00:00 |
| `finding` | Round 32: SNAPSHOT_RETENTION_HOURS was 72 while this registration requires a 7-day window. Excursions are measured against asset_snapshots, so events older than 3 days had no price series and the reopening gate was unreachable by constructi |
| `fix` | Round 33: SNAPSHOT_RETENTION_HOURS = 192 and TRADE_RETENTION_HOURS = 192. |
| `required_snapshot_hours` | 168.5 |
| `note` | Raising retention does not recreate pruned history. Snapshots spanned 69.1h at the fix; a full 7-day window first exists ~4.1 days later. The reopening bar above is unchanged. |
| `enforced_in_code` | wick_benchmark.retention_covers_window(), checked first by reopening_gate() |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Item_14_Hyperliquid_Whale_Cascade_Sweeper|Item 14: Hyperliquid Whale Cascade Sweeper]] (primary)
- [[Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester|Item 8: Hyperliquid Delta-Neutral Funding Rate Harvester]] (cross-reference)
- [[experiments_register|Experiments register]]
