---
type: Experiment
title: 'Experiment: regime_filtered_v1'
description: regime_filtered_v1
tags:
- experiment
- desk-1
- registration
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T17:32:28Z'
status: draft
sources:
- id: registration
  resource: HyperLiquid/HL_Monarch/data/experiments/regime_filtered_v1.meta.json
  title: regime_filtered_v1.meta.json
  author: human:operator
dev:
  desk: 1
  registration: HyperLiquid/HL_Monarch/data/experiments/regime_filtered_v1.meta.json
  kind: registration
  item: 14
  related_items:
  - 8
  registered_utc: '2026-09-01T04:40:14.107981+00:00'
  progress:
    accumulated: 0
    target: 50
    unit: closed_trades
    status: parked
    measured_at: '2026-09-06T17:32:28Z'
  parameters:
  - name: regime_filtered_v1_acceptance_bar_min_closed_trades
    value: 50
    file: HyperLiquid/HL_Monarch/data/experiments/regime_filtered_v1.meta.json
    json_path: acceptance_bar.min_closed_trades
  requires_files:
  - HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.json
  tests_run: 0
---
# Experiment: regime_filtered_v1

> Pre-registration: bars fixed before the data. Amendments are listed, never applied silently.
> [!NOTE]
> **PARKED (2026-09-06)**: Measured 2026-09-06: paper_trading_state.json holds closed_trades=0 and was last written 2026-09-01T05:59:39Z, 80 minutes after registration; no paper-trading process has run since. The registration's own known_defect_not_fixed stands (targets sized off a 15-minute ATR while positions force-close at 600 s; median time to a 1.0xATR target measured at 1,224 s), and with the FOMC drill occupying the calendar to 2026-09-16 there is no window to accumulate 50 closed trades on a configuration carrying that defect.


## Registered utc

2026-09-01T04:40:14.107981+00:00

## Control

data/experiments/baseline_unfiltered_N12_2026-09-01.json

## Changes vs control

- EMA-50/RSI-14 trend gate on 15m buckets; blocks fades leaning into a strong trend unless RSI is stretched past 32/68
- ATR-scaled geometry: offset max(0.40%, 0.50xATR), TP/SL max(0.30%, 1.0xATR), still 1:1
- Dual rotation pool: 20 volume-ranked majors + 15 exotics (<$5M OI, >$100k vol)
- Unknown regime BLOCKS rather than permits

## Acceptance bar

| Key | Value |
|---|---|
| `min_closed_trades` | 50 |
| `PASS` | win rate >= 54.0% AND profit factor >= 1.25 |
| `RETUNE` | win rate 48.0-54.0% |
| `FAIL` | win rate < 48.0% |
| `note` | Unchanged from the standing hurdle. Fixed before any data is collected. |

## Commitments

- No mid-flight parameter changes before N=50.
- The control is archived, not overwritten - the two runs are comparable.
- Four variables changed at once, so a PASS identifies the BUNDLE, not which component earned it. Attribution needs a follow-up ablation.

## Amendments

- **utc**: 2026-09-01T05:00:10.535537+00:00; **closed_trades_at_amendment**: 0; **change**: ATR switched from close-to-close proxy to sampled true range (intra-bucket high/low from ~67 samples per 15m bucket).; **why**: Measurement correction, not a tuning change. The close-to-close proxy understated measured true range by a median 1.59x across the watchlist. Antigravity proposed a flat 1.25x multiplier; that was rej; **legitimacy**: Made at N=0 closed trades, so no result could have influenced it. A change after data existed would have required a fresh registration.; **effect**: Targets widen; fee burden falls from ~15% of gross to ~8-11% on volatile markets. Offset floor still binds on 27/35 markets, target floor on 15/35.
- **utc**: 2026-09-06T17:27:22.768909+00:00; **closed_trades_at_amendment**: 0; **action**: parked; **change**: Formally parked, unflown. The registration, its acceptance bar and the archived N=12 control are unchanged; this amendment records that no trial was ever run against them.; **why**: Measured 2026-09-06: paper_trading_state.json holds closed_trades=0 and was last written 2026-09-01T05:59:39Z, 80 minutes after registration; no paper-trading process has run since. The registration's; **not_cited_as_evidence**: The Round 104 whale-sweeper cascade replay is ADJACENT, not a verdict on this strategy: it tested Item 14's liquidation-cascade fade, this registration is a passive fade with an EMA/RSI trend gate, an; **legitimacy**: Made at N=0 closed trades. Parking changes no bar and reads no result; any retuned trial requires a fresh pre-registration.

## Known defect not fixed

| Key | Value |
|---|---|
| `issue` | Targets are sized off a 15-minute ATR bar but positions are force-closed after FADE_POSITION_MAX_HOLD_SECONDS=600s. |
| `measured` | Median time to reach a 1.0xATR target is 1,224s. The target is reached inside the 600s window in <50% of cases in 35/35 markets (median 16.5%; BTC 3.4%; xyz:SP500 ~0%). |
| `consequence` | Most positions will exit TIME_STOP at the mid, not at TP or SL. The 1:1 geometry is largely decorative, and the run measures a near coin-flip minus fees rather than whether the trend filter works. |
| `retrodiction` | This also explains the archived control: 25% win rate and PF 0.123 is what a fee-laden time-stop coin flip looks like. |
| `status` | NOT changed unilaterally - max hold is a frozen strategy parameter. Needs an explicit decision before this run can answer its own question. |
| `suggested_fix` | FADE_POSITION_MAX_HOLD_SECONDS 600 -> ~1800, or halve the ATR target multiplier. Either requires a fresh registration. |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Item_14_Hyperliquid_Whale_Cascade_Sweeper|Item 14: Hyperliquid Whale Cascade Sweeper]] (primary)
- [[Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester|Item 8: Hyperliquid Delta-Neutral Funding Rate Harvester]] (cross-reference)
- [[experiments_register|Experiments register]]
