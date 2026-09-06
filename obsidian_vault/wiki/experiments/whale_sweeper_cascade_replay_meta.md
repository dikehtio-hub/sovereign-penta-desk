---
type: Experiment
title: 'Experiment: whale_sweeper_cascade_replay'
description: PRE-REGISTERED (Round 103, backlog B15).
tags:
- experiment
- desk-1
- registration
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T18:33:57Z'
status: stable
sources:
- id: registration
  resource: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
  title: whale_sweeper_cascade_replay.meta.json
  author: human:operator
dev:
  desk: 1
  registration: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
  kind: registration
  item: 14
  related_items:
  - 8
  registered_utc: '2026-09-06T02:06:00+00:00'
  progress:
    accumulated: 19008
    target: 500
    unit: events
    status: evaluated
    measured_at: '2026-09-06T17:32:28Z'
    gates:
      min_events:
        value: 19008
        bar: 500
        pass: true
      min_coins:
        value: 62
        bar: 20
        pass: true
      max_single_coin_share:
        value: 0.1984
        bar: 0.2
        pass: true
  parameters:
  - name: whale_sweeper_cascade_replay_sample_requirements_min_events
    value: 500
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.min_events
  - name: whale_sweeper_cascade_replay_sample_requirements_min_coins
    value: 20
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.min_coins
  - name: whale_sweeper_cascade_replay_sample_requirements_max_single_coin_share
    value: 0.2
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.max_single_coin_share
  - name: whale_sweeper_cascade_replay_sample_requirements_max_hhi
    value: 0.15
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.max_hhi
  - name: whale_sweeper_cascade_replay_sample_requirements_min_samples_60m_per_event
    value: 1
    file: HyperLiquid/HL_Monarch/data/experiments/whale_sweeper_cascade_replay.meta.json
    json_path: sample_requirements.min_samples_60m_per_event
  tests_run: 0
  ratified_by: 103-B15
verified:
- by: antigravity/architect
  at: '2026-09-06T02:31:00Z'
---
# Experiment: whale_sweeper_cascade_replay

> Pre-registration: bars fixed before the data. Amendments are listed, never applied silently.

## Registered utc

2026-09-06T02:06:00+00:00

## Status

PRE-REGISTERED (Round 103, backlog B15). The acceptance bar below is fixed BEFORE any replay is run. Item 14 (Hyperliquid Whale Cascade Sweeper) has been built and gated OFF since Round 31 for want of evidence; 28,544 cascade excursions have accumulated in the meantime. This registration says what would count as evidence, so the replay cannot be graded after the fact.

## Authored by

claude-code/fable-5.1 - NOT YET RATIFIED. Antigravity must verify this page before the replay runs (WIKI_SCHEMA.md s.2: an agent never verifies its own page).

## Item

14

## Desk

1

## Question

After a large liquidation cascade on HyperLiquid, does price mean-revert enough that fading the cascade would have paid, on a sample wide enough to rule out one or two microcaps carrying the result?

## Grade of evidence

| Key | Value |
|---|---|
| `kind` | RETROSPECTIVE REPLAY, NOT A FORWARD TEST |
| `why_it_matters` | cascade_excursions was collected before this bar was written, and the sweeper's own thresholds were chosen by people who had already seen some of this regime. Pre-registration here binds the ANALYSIS, not the data collection, so a PASS is w |
| `consequence` | A PASS is grounds to propose un-gating and to design a forward test. A PASS IS NOT AN UN-GATING. Item 14 stays gated off until a separate ruling, on separate evidence, says otherwise. |

## Data

| Key | Value |
|---|---|
| `source` | HyperLiquid/HL_Monarch/data/hyperliquid_data.db table cascade_excursions, opened file:...?mode=ro |
| `written_by` | HyperLiquid/HL_Monarch/storage/incremental_persistence.py (NOT analytics/excursions.py - the Top 20 registry's Item 14 Primary Code line cites a path that does not exist; see corrections) |
| `columns_used` | ["event_id", "coin", "timestamp_utc", "cascade_side", "fade_is_long", "notional_usd", "event_px", "entry_px", "mfe_30m", "mae_30m", "samples_60m", "regime_tag"] |
| `state_at_registration` | {"rows": 28544, "coins": 58, "cascade_side_A": 14012, "cascade_side_B": 14532, "counted_at_utc": "2026-09-06T02:04:00+00:00", "note": "Counts only. NO ratio, correlation or excursion statistic of any kind was computed for this registration. |

## Primary metric

| Key | Value |
|---|---|
| `name` | fade_ratio_30m |
| `definition` | median(mfe_30m) / median(mae_30m) over qualifying events, computed per the sign convention in fade_is_long, at the 30-minute horizon. |
| `why_30m` | The passive_fade_rebenchmark registration found that of the 5m, 15m and 30m horizons only 30m cleared p < 0.05 under clustering (cluster_p_ge_1_by_horizon: 5m 0.0827, 15m 0.0772, 30m 0.0259). 30m is therefore the pre-committed horizon; 5m,  |
| `definition_conflict_rule` | If wick_benchmark computes a differently-defined ratio, the replay MUST report both under both names. The registration's definition decides; the code is adapted to the registration, never the reverse. |

## Sample requirements

| Key | Value |
|---|---|
| `min_events` | 500 |
| `min_coins` | 20 |
| `max_single_coin_share` | 0.2 |
| `max_hhi` | 0.15 |
| `min_samples_60m_per_event` | 1 |
| `rationale` | Inherited from passive_fade_rebenchmark. The 2026-09-01 retirement verdict came from a window in which two microcaps supplied 83% of all events (HHI 0.360); the sample gates exist so that cannot happen again. A run failing any gate produces |

## Acceptance bar

| Key | Value |
|---|---|
| `PASS` | P(fade_ratio_30m >= 1.25) > 0.90 under a CLUSTER bootstrap resampling COINS |
| `RETUNE` | 0.50 <= P(fade_ratio_30m >= 1.25) <= 0.90 |
| `FAIL` | P(fade_ratio_30m >= 1.25) < 0.50 |
| `INSUFFICIENT` | any sample requirement unmet - no verdict is issued |
| `rationale` | Identical threshold and probability to passive_fade_rebenchmark's reopening bar, deliberately: the two experiments ask the same question of the same phenomenon on the same desk, and a bar that moves between them is a bar that was chosen to  |
| `fixed_before_any_data` | true |

## Statistical method

| Key | Value |
|---|---|
| `bootstrap` | CLUSTER bootstrap resampling coins with replacement, 10,000 draws, seed 7 |
| `why_not_event_level` | Forward windows on the same coin overlap, so events are not independent. An event-level bootstrap would understate the variance and manufacture significance. This is the standing auditing standard from passive_fade_rebenchmark. |
| `must_report` | ["rows_at_run", "events_qualifying", "coins", "top_coin_share", "hhi", "fade_ratio_30m", "fade_ratio_5m", "fade_ratio_15m", "fade_ratio_60m", "cluster_p_ge_1_25", "seed"] |

## Commitments

- The bar above is not changed after any data is seen. A change requires a dated amendment naming what was already known when it was made.
- The replay is read-only: file:...?mode=ro, no writes to hyperliquid_data.db, no change to whale_sweeper.py, no change to any gate.
- A PASS is written to the wiki as a verdict page and nothing else happens automatically.
- If the run is INSUFFICIENT the page says INSUFFICIENT; an insufficient sample is never reported as a weak PASS or a FAIL.
- Both cascade sides (A 14,012 / B 14,532 at registration) are reported separately as well as pooled, because a result carried by one side only is a different finding from a symmetric one.

## Known defect not fixed

| Key | Value |
|---|---|
| `issue` | The excursion windows were measured against asset_snapshots under a retention policy that changed during collection (Round 32 found SNAPSHOT_RETENTION_HOURS was 72 while a 7-day window was required). |
| `consequence` | Events older than the retention window at the time of measurement may have truncated or absent forward series. The replay must report samples_60m per event and exclude events whose forward series is incomplete, rather than treating a short  |
| `not_fixed_because` | It is a historical property of the data; the fix is to exclude, not to reconstruct. |

## Corrections to the registry

- **what**: The Top 20 registry's Item 14 Primary Code cites HyperLiquid/HL_Monarch/analytics/excursions.py, which does not exist. cascade_excursions is written by storage/incremental_persistence.py and defined i; **action**: Reported to Antigravity for a ruling. Registry lines 80-484 were NOT edited (they are held byte-identical by standing constraint).

## Commands

- # NOT RUN in Round 103. The replay is a later round, and only after Antigravity verifies this page.
- python -m knowledge.ingest.experiments   # compiles this registration into a wiki Experiment page

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Item_14_Hyperliquid_Whale_Cascade_Sweeper|Item 14: Hyperliquid Whale Cascade Sweeper]] (primary)
- [[Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester|Item 8: Hyperliquid Delta-Neutral Funding Rate Harvester]] (cross-reference)
- [[experiments_register|Experiments register]]
