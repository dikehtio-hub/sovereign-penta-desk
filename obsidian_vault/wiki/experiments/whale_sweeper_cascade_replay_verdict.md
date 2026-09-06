---
type: Experiment
title: Whale sweeper cascade replay - verdict
description: 'Item 14 retrospective replay graded against its pre-registered bar:
  **INSUFFICIENT** (ratio 0.6169, P 0.0000, 14,467 events on 58 coins). Retrospective
  replay, not a forward test.'
tags:
- experiment
- desk-1
- item-14
- cascade
- verdict
- insufficient
- retrospective-replay
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T05:21:48Z'
status: draft
sources:
- id: replay-json
  resource: cross_market/data/whale_sweeper_cascade_replay_verdict.json
  title: cascade_replay --json artifact
  author: process:HyperLiquid.HL_Monarch.analytics.cascade_replay
- id: registration
  resource: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
  title: whale_sweeper_cascade_replay pre-registration (B15)
  author: claude-code/fable-5.1
dev:
  desk: 1
  item: 14
  kind: cascade_replay_verdict
  grade: INSUFFICIENT
  engine_verdict: INSUFFICIENT
  grades_agree: true
  band_if_sample_qualified: FAIL
  gate_failures:
  - top_coin_share=0.2249 > 0.2
  measurement:
    fade_ratio_30m: 0.6169470524643818
    cluster_p_ge_1_25: 0.0
    rows_at_run: 29612
    raw_loaded: 14806
    qualifying: 14467
    truncated: 226
    seed: 7
    resamples: 10000
  sample_metrics:
    events: 14467
    coins: 58
    top_coin: PONS
    top_coin_share: 0.22492569295638348
    hhi: 0.14195683758655983
  grade_vocabulary:
  - PASS
  - RETUNE
  - FAIL
  - INSUFFICIENT
  registration: whale_sweeper_cascade_replay_meta
  observed_at: '2026-09-06T04:54:00.462755Z'
  observed_from: the artifact's own `_artifact.written_at`
  parameters:
  - name: cascade_replay_min_events
    value: 500
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.min_events
  - name: cascade_replay_min_coins
    value: 20
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.min_coins
  - name: cascade_replay_max_single_coin_share
    value: 0.2
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.max_single_coin_share
  - name: cascade_replay_max_hhi
    value: 0.15
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.max_hhi
  requires_files:
  - HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
  history:
  - at: '2026-09-06T03:36:01Z'
    observed_at: '2026-09-06T03:18:04Z'
    rows_at_run: 29350
    events: 14336
    top_coin_share: 0.22481863839285715
    ratio_30m: 0.6123737957384416
    cluster_p: 0.0
    grade: INSUFFICIENT
  - at: '2026-09-06T04:54:23Z'
    observed_at: '2026-09-06T04:54:00.462755Z'
    rows_at_run: 29612
    events: 14467
    top_coin_share: 0.22492569295638348
    ratio_30m: 0.6169470524643818
    cluster_p: 0.0
    grade: INSUFFICIENT
---
# Whale sweeper cascade replay - verdict

> **INSUFFICIENT**. Graded here against the pre-registration (backlog B15, registered 2026-09-06T02:06:00+00:00), not copied from the engine's output.

## Grade of evidence

**RETROSPECTIVE REPLAY, NOT A FORWARD TEST.** A PASS is grounds to propose un-gating and to design a forward test. A PASS IS NOT AN UN-GATING. Item 14 stays gated off until a separate ruling, on separate evidence, says otherwise.

## Verdict

- **This page grades: INSUFFICIENT**
- The engine reported: `INSUFFICIENT` -> the two agree.

The sample requirements are NOT met, so **no verdict is issued** (registration: "a run failing any gate produces NO verdict, not a weak one"). Unmet:

- top_coin_share=0.2249 > 0.2

Had the sample qualified, P = 0.0000 would have fallen in the **FAIL** band. That is stated for completeness and **is not a verdict**; it is exactly the reading the gates exist to prevent.

## Sample gates, re-checked here

| Requirement | Registered | Measured | |
|---|---|---|---|
| events | >= 500 | 14,467 | ok |
| coins | >= 20 | 58 | ok |
| top coin share | <= 0.2 | 0.2249 | **FAIL** |
| HHI | <= 0.15 | 0.142 | ok |

The failing concentration is `PONS`. Note the HHI passes with very little room (0.14196 against a 0.15 ceiling), so this sample is narrow on two axes, not one.

## Primary metric

`fade_ratio_30m` = median(mfe_30m) / median(mae_30m) = **0.6169**. A ratio below 1 means the average cascade kept going rather than reverting: the adverse excursion was larger than the favourable one.

- P(ratio >= 1.25) = **0.0000** under a cluster bootstrap resampling coins (10,000 draws, seed 7).
- Registered bands: PASS `P(fade_ratio_30m >= 1.25) > 0.90 under a CLUSTER bootstrap resampling COINS` · RETUNE `0.50 <= P(fade_ratio_30m >= 1.25) <= 0.90` · FAIL `P(fade_ratio_30m >= 1.25) < 0.50` · INSUFFICIENT `any sample requirement unmet - no verdict is issued`.

## Horizons (reported, not deciding)

The registration pre-committed to 30m and says the others are reported only.

| Horizon | n | median MFE | median MAE | ratio | win share | $ expectancy |
|---|---|---|---|---|---|---|
| 5m | 13,550 | 0.1402 | 0.2486 | 0.5638 | 42.27% | -0.0348 |
| 15m | 13,805 | 0.2627 | 0.4276 | 0.6145 | 45.14% | -0.0364 |
| 30m **(pre-committed)** | 14,467 | 0.3710 | 0.6014 | 0.6169 | 43.91% | -0.0422 |
| 60m | 14,467 | 0.5722 | 0.7415 | 0.7717 | 46.50% | -0.0092 |

Every horizon is below 1.0 and every dollar expectancy is negative. The result does not depend on the horizon choice.

## Both cascade sides (registration commitment 5)

| Side | n | median ratio 30m | $ expectancy | P(>= 1.25) |
|---|---|---|---|---|
| A - sell cascade, fade by buying | 6,905 | 0.2787 | -0.0590 | 0.0137 |
| B - buy cascade, fade by selling | 7,562 | 1.7135 | -0.0250 | 0.4823 |

Side B's median ratio above 1.25 is the one eye-catching number in this artifact, and it does not survive clustering: its own P is below the PASS bar, and the registration's bands apply to the POOLED primary metric, not to a side split. **Reading a side split against the pooled bands is not something this registration authorises**, and Round 103's handoff note did exactly that from a transcribed 0.5020 that the artifact now puts at 0.4823 - across the 0.50 boundary. Both reasons independently invalidate that reading.

## Data audit

- rows in `cascade_excursions` at run: **29,612** (the registration counted 28,544 at registration; the table is written by a live collector and grows continuously)
- loaded after excluding matched controls (`event_id > 0 AND source NOT LIKE 'control:%'`): **14,806**. Roughly half the table is synthetic control rows by design; this is not data loss.
- qualifying after the truncation and null filters: **14,467** (226 excluded for an incomplete forward series, per the registration's `known_defect_not_fixed`)

- artifact written at **2026-09-06T04:54:00.462755Z** by `HyperLiquid.HL_Monarch.analytics.cascade_replay`, from 29,612 rows, seed 7 (source: the artifact's own `_artifact.written_at`). Ruling R104-2 put this envelope on the engine in Round 105, so two runs over a continuously growing table can finally be ordered from their own contents.

## Regime breakdown (reported)

| Regime | n | median ratio 30m | $ expectancy |
|---|---|---|---|
| `UNKNOWN` | 4,476 | 1.0925 | -0.0064 |
| `VOL_HIGH\|FUND_FLAT` | 1,351 | 0.7296 | -0.0471 |
| `VOL_LOW\|FUND_FLAT` | 3,852 | 0.5934 | -0.0653 |
| `VOL_MID\|FUND_FLAT` | 4,788 | 0.4291 | -0.0468 |

## What follows from this

- Item 14 stays gated off. It was already gated, and an INSUFFICIENT sample is not grounds to change anything in either direction.
- The registration's remedy for a narrow sample is to wait for a wider one, not to relax the gate. `PONS` supplies 22.5% of events against a 20% ceiling; that share falls as other coins accumulate.
- Nothing here licenses a forward test either. A forward test follows a PASS.

## History

| At | rows at run | events | top coin share | ratio 30m | P | grade |
|---|---|---|---|---|---|---|
| 2026-09-06T03:36:01Z | 29,350 | 14,336 | 0.2248 | 0.6124 | 0.0000 | INSUFFICIENT |
| 2026-09-06T04:54:23Z | 29,612 | 14,467 | 0.2249 | 0.6169 | 0.0000 | INSUFFICIENT |

## Related

- [[whale_sweeper_cascade_replay_meta|The pre-registration (B15)]]
- [[Item_14_Hyperliquid_Whale_Cascade_Sweeper|Item 14: Whale Cascade Sweeper]]
- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
