---
type: Experiment
title: Passive fade rebenchmark - verdict
description: 'Reopening question graded against the pre-registered bar: **INSUFFICIENT**
  over `trade_sweep` (ratio_30m 0.7896, P 0.0000, 13,645 events on 46 coins, top coin
  0.268). The fade stays retired either way.'
tags:
- experiment
- desk-1
- fade
- verdict
- insufficient
- rebenchmark
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T22:15:50Z'
status: draft
sources:
- id: artifact
  resource: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.verdict.json
  title: fade_rebenchmark artifact
  author: process:HyperLiquid.HL_Monarch.analytics.fade_rebenchmark
- id: registration
  resource: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
  title: passive_fade_rebenchmark pre-registration
  author: claude-code/fable-5.1
dev:
  desk: 1
  kind: rebenchmark_verdict
  grade: INSUFFICIENT
  engine_verdict: INSUFFICIENT
  grades_agree: true
  band_if_sample_qualified: FAIL
  gate_failures:
  - top_coin_share=0.2678 > 0.2
  - span_days=5.49 < 7
  bar_drift: []
  bar:
    ratio: 1.25
    confidence: 0.9
  measurement:
    ratio_30m: 0.7895786288225686
    n_30m: 13553
    cluster_p_ge_1_25: 0.0
    cluster_p_ge_1: 0.0677
    control_ratio_30m: 0.9498057481925781
    edge_vs_control: -0.16022711937000955
    source: trade_sweep
    rows_at_run: 38016
    treatment_rows: 13645
    control_rows: 13645
    first_event_utc: '2026-09-01T03:59:03.823000Z'
    last_event_utc: '2026-09-06T15:43:31.895000Z'
    seed: 7
    resamples: 20000
  sample_metrics:
    events: 13645
    coins: 46
    top_coin_share: 0.2677635947760643
    top_coin: ZEC
    hhi: 0.1903602020796509
    span_days: 5.49
    window_days_required: 7.0
    window_covered: false
  grade_vocabulary:
  - PASS
  - FAIL
  - INSUFFICIENT
  registration: passive_fade_rebenchmark_meta
  observed_at: '2026-09-06T19:44:26.500127Z'
  observed_from: the artifact's own `_artifact.written_at`
  parameters:
  - name: fade_rebenchmark_min_events
    value: 500
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: sample_requirements.min_events
  - name: fade_rebenchmark_min_coins
    value: 20
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: sample_requirements.min_coins
  - name: fade_rebenchmark_max_single_coin_share
    value: 0.2
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: sample_requirements.max_single_coin_share
  - name: fade_rebenchmark_window_days
    value: 7
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: sample_requirements.window_days
  - name: fade_rebenchmark_population
    value: trade_sweep
    file: HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
    json_path: population.source
  requires_files:
  - HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json
  - HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.verdict.json
  history:
  - at: '2026-09-06T22:15:50Z'
    observed_at: '2026-09-06T19:44:26.500127Z'
    rows_at_run: 38016
    events: 13645
    top_coin_share: 0.2677635947760643
    span_days: 5.49
    ratio_30m: 0.7895786288225686
    cluster_p: 0.0
    grade: INSUFFICIENT
---
# Passive fade rebenchmark - verdict

> **INSUFFICIENT**. Graded here against the pre-registration (registered 2026-09-01T05:42:16.383702+00:00), not copied from the engine's output.

## The question

May the retired passive fade be reconsidered? The registration's bar: `P(ratio >= 1.25) > 0.90 under a CLUSTER bootstrap resampling coins`. Deliberately asymmetric. Retiring took p=0.024 on a narrow sample; coming back should cost more than leaving did.

## Verdict

- **This page grades: INSUFFICIENT**
- The engine reported: `INSUFFICIENT` -> the two agree.

The sample requirements are NOT met, so **no verdict is issued** - an insufficient sample is never read as a weak PASS or a FAIL. Unmet:

- top_coin_share=0.2678 > 0.2
- span_days=5.49 < 7

Had the sample qualified, P(ratio_30m >= 1.25) = 0.0000 would have fallen in the **FAIL** band. Stated for completeness; **it is not a verdict**, and it is exactly the reading the gates exist to prevent.

## Sample gates, re-checked here

| Requirement | Registered | Measured | |
|---|---|---|---|
| events | >= 500 | 13,645 | ok |
| coins | >= 20 | 46 | ok |
| top_coin_share | <= 0.2 | 0.2678 | **FAIL** |
| span_days | >= 7 | 5.49 | **FAIL** |

Top coin: `ZEC`. HHI 0.1904 (reported).

## Population

Population `trade_sweep` - the registered population (registration names `trade_sweep`, recorded 2026-09-06). `cascade_excursions` also holds `trade_flow` rows; the desk's schema keeps the source column because the two event sources answer different questions and must never be pooled. Round 113's progress mirror pooled them and read this sample as ready; over the registered population it is not.

## Primary metric

`ratio_30m` = mean(MFE) / mean(MAE) over the fade direction at 30 minutes = **0.7896** on n = 13,553 measurable events. Below 1 means the cascade kept going: the adverse excursion outweighed the favourable one.

- P(ratio_30m >= 1.25) = **0.0000** under a cluster bootstrap resampling coins (20,000 draws, seed 7). Bar: > 0.9.
- P(ratio_30m >= 1.0) = 0.0677 (context; the retirement's own statistic).
- Matched random-entry control ratio 0.9498; edge vs control -0.1602.

## Horizons (5m, 15m, 30m registered; 60m reported only)

| Horizon | n | ratio | control | P(>= 1.0) | P(>= bar) | coins | top share |
|---|---|---|---|---|---|---|---|
| 5m | 12,927 | 0.6778 | 0.9953 | 0.0006 | 0.0000 | 46 | 0.2803 |
| 15m | 13,078 | 0.7589 | 0.9673 | 0.0434 | 0.0001 | 46 | 0.2775 |
| 30m **(decision)** | 13,553 | 0.7896 | 0.9498 | 0.0677 | 0.0000 | 46 | 0.2678 |
| 60m (reported) | 13,645 | 0.8664 | 0.9140 | 0.0422 | 0.0000 | 46 | 0.2660 |

## Data audit

- rows in `cascade_excursions` at run: **38,016**; treatment rows for `trade_sweep`: **13,645**; matched control rows: 13,645
- events span 2026-09-01T03:59:03.823000Z .. 2026-09-06T15:43:31.895000Z (5.49 days)
- measurable at the decision horizon: 13,553
- artifact written at **2026-09-06T19:44:26.500127Z** by `HyperLiquid.HL_Monarch.analytics.fade_rebenchmark` (source: the artifact's own `_artifact.written_at`); resamples 20,000, seed 7

## What follows from this

- The fade stays retired and PASSIVE. Nothing on this page enables execution; a PASS would be a decision for the architect and the operator, not an automatic consequence.
- The remedy for a narrow sample is a wider one, not a relaxed gate. top_coin_share=0.2678 > 0.2; span_days=5.49 < 7 - those are what block.
- The registration page keeps reporting progress against these gates until a PASS or FAIL exists; an INSUFFICIENT evaluation does not close the question.

## History

| At | rows at run | events | top coin share | span d | ratio 30m | P(>= bar) | grade |
|---|---|---|---|---|---|---|---|
| 2026-09-06T22:15:50Z | 38,016 | 13,645 | 0.2678 | 5.49 | 0.7896 | 0.0000 | INSUFFICIENT |

## Related

- [[passive_fade_rebenchmark_meta|The pre-registration]]
- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
