---
type: Experiment
title: 'Experiment: baseline_unfiltered'
description: TERMINATED EARLY at N=12 of a pre-registered N=50
tags:
- experiment
- desk-1
- archived-control
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:20Z'
status: draft
sources:
- id: registration
  resource: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
  title: baseline_unfiltered_N12_2026-09-01.meta.json
  author: human:operator
dev:
  desk: 1
  registration: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
  kind: archived_control
  registered_utc: '2026-09-01T04:39:40.619907+00:00'
  parameters:
  - name: baseline_unfiltered_closed_trades
    value: 12
    file: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
    json_path: closed_trades
  - name: baseline_unfiltered_wins
    value: 3
    file: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
    json_path: wins
  - name: baseline_unfiltered_losses
    value: 9
    file: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
    json_path: losses
  - name: baseline_unfiltered_win_rate_pct
    value: 25.0
    file: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
    json_path: win_rate_pct
  - name: baseline_unfiltered_profit_factor
    value: 0.123
    file: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
    json_path: profit_factor
  - name: baseline_unfiltered_net_pnl
    value: -536.74
    file: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
    json_path: net_pnl
  - name: baseline_unfiltered_gross_pnl
    value: -482.76
    file: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
    json_path: gross_pnl
  - name: baseline_unfiltered_fees_paid
    value: 53.98
    file: HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.meta.json
    json_path: fees_paid
  requires_files:
  - HyperLiquid/HL_Monarch/data/experiments/baseline_unfiltered_N12_2026-09-01.json
---
# Experiment: baseline_unfiltered

> Archived control: the result is frozen; its numbers below are guarded by lint C1, so overwriting the file is a finding.

## Archived utc

2026-09-01T04:39:40.619907+00:00

## Status

TERMINATED EARLY at N=12 of a pre-registered N=50

## Why archived

Round 15 resets the paper account to test a trend/ATR filter. The pre-registration fixed on 2026-08-31 committed to running to N=50 closed trades with no mid-flight parameter changes. Stopping at N=12 and overwriting would destroy the only unfiltered control we have, and leave the new configuration with nothing to be measured against.

## Closed trades

12

## Wins

3

## Losses

9

## Win rate pct

25.0

## Profit factor

0.123

## Net pnl

-536.74

## Gross pnl

-482.76

## Fees paid

53.98

## Geometry

static 0.50% offset / 0.65% TP / 0.65% SL, no regime filter

## Rotation

volume-only, 35 slots (selected >$5M OI exclusively -> exotic tier never fired)

## Key finding

Loss was GROSS (-$536.74 net of which only $53.98 was fees). The entries were wrong, not the cost model. Every fill was the $10k major tier.

## Caveat

N=12 is far below the N>=30 the acceptance bar requires. This is a directional signal, NOT a verdict. It cannot reject the strategy at any conventional confidence level.

## Note on fields

gross_profit/gross_loss in the state file are net-of-fee per-trade buckets; profit_factor is therefore a net ratio.

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- paper fade / wick-benchmark family (Items 8 and 14; attribution to be ratified)
- [[experiments_register|Experiments register]]
