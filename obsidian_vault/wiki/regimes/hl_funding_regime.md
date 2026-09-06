---
type: Regime
title: HyperLiquid funding regime
description: 'Realised basis funding across 10,635 windows: all-window median 6.4%,
  entry-qualifying median 28.05% with 53.5% clearing the 25.0% bar; the net bar is
  unmeasurable.'
tags:
- regime
- desk-1
- item-8
- funding
- basis
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T03:35:59Z'
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
    entry_qualifying:
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
    entry_qualifying_n: 473
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
---
# HyperLiquid funding regime (Desk 1, Item 8)

> What the delta-neutral basis book ACTUALLY realised across 10,635 recorded windows on 441 assets, against the harvester's own entry bars.

## The two populations

The table holds every candidate window the measurement grid opened on a stride, most of which the
harvester would never have entered. Judging the strategy on all of them understates it; judging it
only on the ones it would have taken hides how selective it has to be. Both are below.

Of the 10,635 windows, **6,796 carry a `realised_apr`**; the rest closed without one and are counted nowhere below. Percentages are shares of each population, not of the table.

| Population | n | median APR | mean | p10 | p90 | >= 25.0 bar | negative |
|---|---|---|---|---|---|---|---|
| All recorded windows | 6,796 | 6.4 | 2.65 | -1.36 | 18.58 | 7.7% | 10.9% |
| Entry-qualifying (quote_apr_entry >= 25.0) | 473 | 28.05 | 46.65 | -3.52 | 96.65 | 53.5% | 12.3% |

## Reading

- The entry rule is doing work: qualifying windows realise a median **28.05%** against **6.4%** across all windows.
- But only **53.5%** of the windows that qualified on the quoted APR actually realised at or above the 25.0% bar, and **12.3%** went negative. Entering on a quoted rate is not the same as earning it.
- Spread between p10 and p90 on qualifying windows: -3.52% to 96.65%.

## The net bar

`BASIS_MIN_NET_APR = 20.0` is the bar that matters after paying spread on both legs. It is **UNMEASURABLE - the net bar cannot be judged on this data**: only 197 of 10,635 rows (1.9%) carry a measured `net_apr_after_fees`; the rest have `fee_basis = 'unmeasured'` because spreads were not recorded when the window closed. No net verdict is issued over a 2% sample, and the gross figure is NOT substituted for it.

## Coverage and regimes

- median window coverage: 0.808
- windows by regime tag: `UNKNOWN` 2,632, `VOL_HIGH|FUND_FLAT` 880, `VOL_LOW|FUND_FLAT` 1,406, `VOL_MID|FUND_FLAT` 5,717

## History

| At | rows | assets | all median | qualifying n | qualifying median | >= bar | net measured |
|---|---|---|---|---|---|---|---|
| 2026-09-06T03:25:51Z | 10,635 | 441 | 6.4 | 473 | 28.05 | 53.5% | 1.9% |
| 2026-09-06T03:28:03Z | 10,635 | 441 | 6.4 | 473 | 28.05 | 53.5% | 1.9% |
| 2026-09-06T03:35:59Z | 10,635 | 441 | 6.4 | 473 | 28.05 | 53.5% | 1.9% |

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester|Item 8: Delta-Neutral Funding Rate Harvester]]
