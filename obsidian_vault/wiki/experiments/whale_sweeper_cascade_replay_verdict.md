---
type: Experiment
title: Whale sweeper cascade replay - verdict
description: 'Item 14 retrospective replay graded against its pre-registered bar:
  **INSUFFICIENT** (ratio 0.9029, P 0.1167, 18,669 events on 62 coins). Retrospective
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
  at: '2026-09-06T22:41:49Z'
status: draft
sources:
- id: replay-json
  resource: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.verdict.json
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
  - top_coin_share=0.202 > 0.2
  measurement:
    fade_ratio_30m: 0.9028931836592922
    cluster_p_ge_1_25: 0.1167
    rows_at_run: 38016
    raw_loaded: 19008
    qualifying: 18669
    truncated: 226
    seed: 7
    resamples: 10000
  sample_metrics:
    events: 18669
    coins: 62
    top_coin: ZEC
    top_coin_share: 0.2020461727998286
    hhi: 0.13337421399263177
  grade_vocabulary:
  - PASS
  - RETUNE
  - FAIL
  - INSUFFICIENT
  registration: whale_sweeper_cascade_replay_meta
  observed_at: '2026-09-06T22:39:27.484923Z'
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
  - at: '2026-09-06T22:41:49Z'
    observed_at: '2026-09-06T22:39:27.484923Z'
    rows_at_run: 38016
    events: 18669
    top_coin_share: 0.2020461727998286
    ratio_30m: 0.9028931836592922
    cluster_p: 0.1167
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

- top_coin_share=0.202 > 0.2

Had the sample qualified, P = 0.1167 would have fallen in the **FAIL** band. That is stated for completeness and **is not a verdict**; it is exactly the reading the gates exist to prevent.

## Sample gates, re-checked here

| Requirement | Registered | Measured | |
|---|---|---|---|
| events | >= 500 | 18,669 | ok |
| coins | >= 20 | 62 | ok |
| top coin share | <= 0.2 | 0.202 | **FAIL** |
| HHI | <= 0.15 | 0.1334 | ok |

The failing concentration is `ZEC`. Note the HHI passes with very little room (0.13337 against a 0.15 ceiling), so this sample is narrow on two axes, not one.

## Primary metric

`fade_ratio_30m` = median(mfe_30m) / median(mae_30m) = **0.9029**. A ratio below 1 means the average cascade kept going rather than reverting: the adverse excursion was larger than the favourable one.

- P(ratio >= 1.25) = **0.1167** under a cluster bootstrap resampling coins (10,000 draws, seed 7).
- Registered bands: PASS `P(fade_ratio_30m >= 1.25) > 0.90 under a CLUSTER bootstrap resampling COINS` · RETUNE `0.50 <= P(fade_ratio_30m >= 1.25) <= 0.90` · FAIL `P(fade_ratio_30m >= 1.25) < 0.50` · INSUFFICIENT `any sample requirement unmet - no verdict is issued`.

## Horizons (reported, not deciding)

The registration pre-committed to 30m and says the others are reported only.

| Horizon | n | median MFE | median MAE | ratio | win share | $ expectancy |
|---|---|---|---|---|---|---|
| 5m | 17,752 | 0.2260 | 0.2453 | 0.9211 | 45.30% | -0.0290 |
| 15m | 18,007 | 0.3886 | 0.4069 | 0.9548 | 47.58% | -0.0289 |
| 30m **(pre-committed)** | 18,669 | 0.5647 | 0.6255 | 0.9029 | 46.49% | -0.0317 |
| 60m | 18,669 | 0.8298 | 0.8098 | 1.0247 | 48.03% | -0.0083 |

Every horizon is below 1.0 and every dollar expectancy is negative. The result does not depend on the horizon choice.

## Both cascade sides (registration commitment 5)

| Side | n | median ratio 30m | $ expectancy | P(>= 1.25) |
|---|---|---|---|---|
| A - sell cascade, fade by buying | 8,716 | 0.2925 | -0.0533 | 0.0131 |
| B - buy cascade, fade by selling | 9,953 | 2.3670 | -0.0098 | 0.6775 |

Side B's median ratio above 1.25 is the one eye-catching number in this artifact, and it does not survive clustering: its own P is below the PASS bar, and the registration's bands apply to the POOLED primary metric, not to a side split. **Reading a side split against the pooled bands is not something this registration authorises**, and Round 103's handoff note did exactly that from a transcribed 0.5020 that the artifact now puts at 0.6775 - across the 0.50 boundary. Both reasons independently invalidate that reading.

## Data audit

- rows in `cascade_excursions` at run: **38,016** (the registration counted 28,544 at registration; the table is written by a live collector and grows continuously)
- loaded after excluding matched controls (`event_id > 0 AND source NOT LIKE 'control:%'`): **19,008**. Roughly half the table is synthetic control rows by design; this is not data loss.
- qualifying after the truncation and null filters: **18,669** (226 excluded for an incomplete forward series, per the registration's `known_defect_not_fixed`)

- artifact written at **2026-09-06T22:39:27.484923Z** by `HyperLiquid.HL_Monarch.analytics.cascade_replay`, from 38,016 rows, seed 7 (source: the artifact's own `_artifact.written_at`). Ruling R104-2 put this envelope on the engine in Round 105, so two runs over a continuously growing table can finally be ordered from their own contents.

## Regime breakdown (reported)

| Regime | n | median ratio 30m | $ expectancy |
|---|---|---|---|
| `UNKNOWN` | 4,476 | 1.0925 | -0.0064 |
| `VOL_HIGH\|FUND_FLAT` | 1,351 | 0.7296 | -0.0471 |
| `VOL_LOW\|FUND_FLAT` | 8,054 | 1.6121 | -0.0273 |
| `VOL_MID\|FUND_FLAT` | 4,788 | 0.4291 | -0.0468 |

## What follows from this

- Item 14 stays gated off. It was already gated, and an INSUFFICIENT sample is not grounds to change anything in either direction.
- The registration's remedy for a narrow sample is to wait for a wider one, not to relax the gate. `ZEC` supplies 20.2% of events against a 20% ceiling; that share falls as other coins accumulate.
- Nothing here licenses a forward test either. A forward test follows a PASS.

## History

| At | rows at run | events | top coin share | ratio 30m | P | grade |
|---|---|---|---|---|---|---|
| 2026-09-06T03:36:01Z | 29,350 | 14,336 | 0.2248 | 0.6124 | 0.0000 | INSUFFICIENT |
| 2026-09-06T04:54:23Z | 29,612 | 14,467 | 0.2249 | 0.6169 | 0.0000 | INSUFFICIENT |
| 2026-09-06T22:41:49Z | 38,016 | 18,669 | 0.2020 | 0.9029 | 0.1167 | INSUFFICIENT |

## Related

- [[whale_sweeper_cascade_replay_meta|The pre-registration (B15)]]
- [[Item_14_Hyperliquid_Whale_Cascade_Sweeper|Item 14: Whale Cascade Sweeper]]
- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
