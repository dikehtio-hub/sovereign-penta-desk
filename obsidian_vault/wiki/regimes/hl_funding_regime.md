---
type: Regime
title: HyperLiquid funding regime
description: 'Realised basis funding across 10,635 windows: all-window median 6.4%,
  gross-bar-only median 28.05% (an upper bound) with 53.5% clearing the 25.0% bar;
  the net bar is unmeasurable.'
tags:
- regime
- desk-1
- item-8
- funding
- basis
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T03:47:00Z'
status: draft
sources:
- id: basis-windows
  resource: HyperLiquid/HL_Monarch/data/hyperliquid_data.db
  title: hyperliquid_data.db basis_realised_windows (mode=ro)
  author: process:HL_Monarch.storage.incremental_persistence
- id: bars
  resource: HyperLiquid/HL_Monarch/config/settings.py
  title: the harvester's entry bars
  author: human:operator
dev:
  desk: 1
  item: 8
  kind: funding_regime
  measurement:
    rows: 10635
    assets: 441
    realised_present: 6796
    all_windows:
      n: 6796
      median: 6.4
      mean: 2.65
      p10: -1.36
      p25: 0.0
      p75: 10.95
      p90: 18.58
      negative_pct: 10.9
      at_or_above_bar: 520
      at_or_above_bar_pct: 7.7
    gross_bar_only:
      n: 473
      median: 28.05
      mean: 46.65
      p10: -3.52
      p25: 10.68
      p75: 61.49
      p90: 96.65
      negative_pct: 12.3
      at_or_above_bar: 253
      at_or_above_bar_pct: 53.5
    gross_bar_only_n: 473
    net:
      measured_rows: 197
      measured_pct: 1.9
      distribution:
        n: 197
        median: -0.16
        mean: -8.88
        p10: -33.56
        p25: -6.49
        p75: 6.98
        p90: 21.79
        negative_pct: 50.3
        at_or_above_bar: 20
        at_or_above_bar_pct: 10.2
      verdict: UNMEASURABLE - the net bar cannot be judged on this data
    median_coverage: 0.808
    regimes:
      UNKNOWN: 2632
      VOL_HIGH|FUND_FLAT: 880
      VOL_LOW|FUND_FLAT: 1406
      VOL_MID|FUND_FLAT: 5717
  parameters:
  - name: basis_min_funding_apr
    value: 25.0
    file: HyperLiquid/HL_Monarch/config/settings.py
    pattern: ^BASIS_MIN_FUNDING_APR\s*=\s*([0-9.]+)
  - name: basis_min_net_apr
    value: 20.0
    file: HyperLiquid/HL_Monarch/config/settings.py
    pattern: ^BASIS_MIN_NET_APR\s*=\s*([0-9.]+)
  requires_files:
  - HyperLiquid/HL_Monarch/config/settings.py
  history:
  - at: '2026-09-06T03:25:51Z'
    rows: 10635
    assets: 441
    all_median: 6.4
    qual_n: 473
    qual_median: 28.05
    qual_at_bar_pct: 53.5
    net_measured_pct: 1.9
  - at: '2026-09-06T03:28:03Z'
    rows: 10635
    assets: 441
    all_median: 6.4
    qual_n: 473
    qual_median: 28.05
    qual_at_bar_pct: 53.5
    net_measured_pct: 1.9
  - at: '2026-09-06T03:35:59Z'
    rows: 10635
    assets: 441
    all_median: 6.4
    qual_n: 473
    qual_median: 28.05
    qual_at_bar_pct: 53.5
    net_measured_pct: 1.9
  - at: '2026-09-06T03:47:00Z'
    rows: 10635
    assets: 441
    all_median: 6.4
    gross_n: 473
    gross_median: 28.05
    gross_at_bar_pct: 53.5
    net_measured_pct: 1.9
---
# HyperLiquid funding regime (Desk 1, Item 8)

> What the delta-neutral basis book ACTUALLY realised across 10,635 recorded windows on 441 assets, against the harvester's own entry bars.

## The two populations

The table holds every candidate window the measurement grid opened on a stride, most of which the
harvester would never have entered. Judging the strategy on all of them understates it. The second
row below is NOT a backtest of the strategy - see the caveat under it - but an upper bound.

Of the 10,635 windows, **6,796 carry a `realised_apr`**; the rest are NULL because coverage fell below `MEASUREMENT_MIN_COVERAGE` (0.60) - an observability exclusion, not an outcome one. `realised_apr` is annualised, so it compares directly against the bars. Percentages below are shares of each population, not of the table.

| Population | n | median APR | mean | p10 | p90 | >= 25.0 bar | negative |
|---|---|---|---|---|---|---|---|
| All recorded windows | 6,796 | 6.4 | 2.65 | -1.36 | 18.58 | 7.7% | 10.9% |
| Clears the GROSS bar only (quote_apr_entry >= 25.0) | 473 | 28.05 | 46.65 | -3.52 | 96.65 | 53.5% | 12.3% |

## Reading

- Selecting on the quoted rate is doing real work: those windows realise a median **28.05%** against **6.4%** across all windows.
- But only **53.5%** of the windows that cleared the quoted bar actually realised at or above 25.0%, and **12.3%** went negative. Entering on a quoted rate is not the same as earning it.
- p10 to p90 on those windows: -3.52% to 96.65%. Wide and fat-tailed, not an annuity.

> **This is an upper bound, not a backtest.** The live entry rule (`scan_basis_opportunities` in `execution/strategies/basis_strategy.py`) requires the gross bar **and** the net bar **and** a spread ceiling, and it refuses any trade whose spread it could not measure - "a basis trade whose cost has not been measured has not been evaluated". The measurement grid has no such scruple: it opens a window on a stride regardless. So these windows have neither paid a spread nor been filtered by the spread ceiling, and the real strategy would have taken a SUBSET of them at a LOWER realised rate.

## The net bar

`BASIS_MIN_NET_APR = 20.0` is the bar that matters after paying spread on both legs. It IS enforced on every live entry; what cannot be done is judging it retrospectively here. It is **UNMEASURABLE - the net bar cannot be judged on this data**: only 197 of 10,635 rows (1.9%) carry a measured `net_apr_after_fees`; the rest have `fee_basis = 'unmeasured'` because spreads were not recorded when the window closed. No net verdict is issued over a 2% sample, and the gross figure is NOT substituted for it.

## Coverage and regimes

- median window coverage: 0.808
- windows by regime tag: `UNKNOWN` 2,632, `VOL_HIGH|FUND_FLAT` 880, `VOL_LOW|FUND_FLAT` 1,406, `VOL_MID|FUND_FLAT` 5,717

## History

| At | rows | assets | all median | gross-bar n | gross-bar median | >= bar | net measured |
|---|---|---|---|---|---|---|---|
| 2026-09-06T03:25:51Z | 10,635 | 441 | 6.4 | 473 | 28.05 | 53.5% | 1.9% |
| 2026-09-06T03:28:03Z | 10,635 | 441 | 6.4 | 473 | 28.05 | 53.5% | 1.9% |
| 2026-09-06T03:35:59Z | 10,635 | 441 | 6.4 | 473 | 28.05 | 53.5% | 1.9% |
| 2026-09-06T03:47:00Z | 10,635 | 441 | 6.4 | 473 | 28.05 | 53.5% | 1.9% |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester|Item 8: Delta-Neutral Funding Rate Harvester]]
