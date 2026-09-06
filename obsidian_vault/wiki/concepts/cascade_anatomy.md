---
type: Concept
title: Cascade anatomy
description: 'Microstructure of the cascade excursion table: side A median 0.2787
  (momentum persists) against side B 1.7135 (which does not survive clustering, P
  0.4823), and the 1-to-1 synthetic control matching that makes the table exactly
  half controls.'
tags:
- concept
- desk-1
- item-14
- cascade
- microstructure
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T05:21:50Z'
status: draft
sources:
- id: replay-json
  resource: cross_market/data/whale_sweeper_cascade_replay_verdict.json
  title: cascade_replay --json artifact
  author: process:HyperLiquid.HL_Monarch.analytics.cascade_replay
- id: control-constant
  resource: HyperLiquid/HL_Monarch/config/settings.py
  title: EXCURSION_CONTROL_MULTIPLE
  author: human:operator
dev:
  desk: 1
  item: 14
  kind: cascade_anatomy
  control_audit:
    total_in_table: 29612
    raw_loaded: 14806
    treatment_share: 0.5
    control_multiple: 1
    expected_share: 0.5
    holds: true
    qualifying: 14467
    truncated: 226
    null_30m: 339
    excluded: 339
    truncation_within_null: true
  asymmetry:
    A:
      n: 6905
      median_fade_ratio_30m: 0.27867336805976284
      mean_fade_ratio_30m: 0.6560683339708684
      dollar_expectancy: -0.0589508008112872
      cluster_p_ge_1_25: 0.0137
    B:
      n: 7562
      median_fade_ratio_30m: 1.7135043638214194
      mean_fade_ratio_30m: 0.7194416787493264
      dollar_expectancy: -0.025021334830985443
      cluster_p_ge_1_25: 0.4823
  artifact_written_at: '2026-09-06T04:54:00.462755Z'
  artifact_written_at_from: the artifact's own `_artifact.written_at`
  requires_files:
  - HyperLiquid/HL_Monarch/config/settings.py
  history:
  - at: '2026-09-06T04:59:43Z'
    artifact_written_at: '2026-09-06T04:54:00.462755Z'
    rows_in_table: 29612
    side_a_median: 0.27867336805976284
    side_b_median: 1.7135043638214194
    side_b_cluster_p: 0.4823
  parameters:
  - name: excursion_control_multiple
    value: 1
    file: HyperLiquid/HL_Monarch/config/settings.py
    pattern: ^EXCURSION_CONTROL_MULTIPLE\s*=\s*(\d+)
---
# Cascade anatomy

> What the cascade excursion data looks like structurally. The verdict is on the replay verdict page; this page is the shape of the data underneath it.

## 1. The two sides are not symmetric

| Side | direction | n | median ratio 30m | mean ratio 30m | $ expectancy | P(>= 1.25) |
|---|---|---|---|---|---|---|
| **A** | sell cascade, faded by buying | 6,905 | 0.2787 | 0.6561 | -0.0590 | 0.0137 |
| **B** | buy cascade, faded by selling | 7,562 | 1.7135 | 0.7194 | -0.0250 | 0.4823 |

### Side A: momentum persists

A median ratio of **0.2787** means the adverse excursion was roughly 3.6x the favourable one. Buying into a sell cascade did not catch a reversal; it caught more selling. With a cluster P of **0.0137** this is the clearest single result in the experiment, and it is a negative one.

### Side B: the number that looks like alpha and is not

A median ratio of **1.7135** sits above the 1.25 acceptance threshold, and it is the only figure anywhere in this experiment that does. Three things stop it from being a finding:

1. **Its own cluster P is 0.4823**, nowhere near the 0.90 a PASS needs. Resampling coins - not events, because forward windows on one coin overlap - dissolves it.
2. **Its dollar expectancy is -0.0250**, i.e. negative. A ratio above 1 that loses money is telling you the ratio is not measuring what pays.
3. **The registration does not grade sides.** The acceptance bar governs the pooled `fade_ratio_30m`; both sides are a required separate report (commitment 5). Grading a side split against the pooled bands is a post-hoc test the pre-registration exists to forbid.

### The median/mean divergence is the real signal

Side B's median ratio is **1.7135** while its mean ratio is **0.7194**. The typical buy cascade reverts modestly; the average one does not, because a minority run violently against the fade and dominate the mean. That single fact reconciles a median above the threshold with a negative expectancy, and it is the exact risk shape a median-only reading conceals: many small wins, occasional large losses. It is also the strongest argument for the pre-registration's insistence on a clustered, pooled metric rather than a headline median.

## 2. Half the table is synthetic, by construction

`EXCURSION_CONTROL_MULTIPLE = 1` in `HyperLiquid/HL_Monarch/config/settings.py`: every persisted event gets exactly 1 matched random-entry control row. So of **29,612** rows in `cascade_excursions`, the replay loads **14,806** treatment rows - a share of **0.5** against an expected **0.5**: **the identity holds**.

An exact 50/50 split reads like a truncation bug to anyone who has not seen the constant, which is why it is pinned here rather than described. Controls are excluded by `event_id > 0 AND source NOT LIKE 'control:%'`; they exist so a future run can ask whether cascade entries beat random ones, a question this replay does not attempt.

### The two exclusion filters overlap

Of 14,806 loaded rows, **14,467** qualify: 339 are excluded. But the two reported filters are 226 truncated (incomplete forward series) and 339 null at 30 minutes, which sum to 565 - more than the exclusions, because a row can fail both. In this artifact the excluded count equals the null count exactly, so **every truncated row is also a null-30m row**: truncation is a subset of nullity here, not an independent filter. Stated because adding the two filters will not reproduce the qualifying count.

## Provenance

- artifact written **2026-09-06T04:54:00.462755Z** (source: the artifact's own `_artifact.written_at`)
- These figures move between runs because the collector is live. Round 104 measured side B at 1.7378 with P 0.4808 over 29,350 rows; this page recompiles from whatever the artifact currently says, which is the only reason the two can be compared at all.

## History

| At | artifact written | rows | side A median | side B median | side B P |
|---|---|---|---|---|---|
| 2026-09-06T04:59:43Z | 2026-09-06T04:54:00.462755Z | 29,612 | 0.2787 | 1.7135 | 0.4823 |

## Related

- [[whale_sweeper_cascade_replay_verdict|The replay verdict]]
- [[whale_sweeper_cascade_replay_meta|The pre-registration (B15)]]
- [[Item_14_Hyperliquid_Whale_Cascade_Sweeper|Item 14: Whale Cascade Sweeper]]
- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
