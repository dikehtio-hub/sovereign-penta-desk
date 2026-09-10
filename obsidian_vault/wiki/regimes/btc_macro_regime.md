---
type: Regime
title: BTC macro regime
description: Rolling classification of the Polymarket macro / Hyperliquid BTC lead-lag
  verdicts, per tier and scope, with the full history.
tags:
- regime
- desk-3
- item-18
- lead-lag
generated:
  by: claude-code/fable-5.1
  at: '2026-09-10T19:59:52Z'
status: draft
sources:
- id: verdicts
  resource: obsidian_vault/wiki/experiments
  title: lead-lag verdict pages
  author: claude-code/fable-5.1
dev:
  desk: 3
  item: 18
  current:
    tier 1 macro:
      latest_verdict: no-lead
      regime_consensus_3: insufficient-history
      runs: 1
    tier 2 macro_fed-rates:
      latest_verdict: no-lead
      regime_consensus_3: no-lead
      runs: 3
    tier 2 macro_crypto:
      latest_verdict: no-lead
      regime_consensus_3: no-lead
      runs: 3
    tier 2b macro_fed-rates:
      latest_verdict: no-lead
      regime_consensus_3: no-lead
      runs: 3
    tier 2b macro_crypto:
      latest_verdict: no-lead
      regime_consensus_3: mixed
      runs: 3
  classes:
  - insufficient
  - no-lead
  - contemporaneous
  - polymarket-leads
  - hyperliquid-leads
  - coincident
  history:
  - at: '2026-09-06T01:42:14Z'
    tier: '1'
    scope: macro
    membership: label
    class: no-lead
    lag: -45
    corr: 0.0696256609657804
    n: 1497
    page: lead_lag_tier1_macro_20260906T0142Z
  - at: '2026-09-07T02:30:18Z'
    tier: '2'
    scope: macro_fed-rates
    membership: label
    class: no-lead
    lag: -10
    corr: 0.05248156354629275
    n: 2416
    page: lead_lag_tier2_macro_fed-rates_20260907T0230Z
  - at: '2026-09-07T02:30:23Z'
    tier: '2'
    scope: macro_crypto
    membership: label
    class: no-lead
    lag: 38
    corr: -0.13802395931258107
    n: 2389
    page: lead_lag_tier2_macro_crypto_20260907T0230Z
  - at: '2026-09-07T02:30:29Z'
    tier: 2b
    scope: macro_fed-rates
    membership: tags
    class: no-lead
    lag: 58
    corr: 0.13506220849793246
    n: 890
    page: lead_lag_tier2b_macro_fed-rates_20260907T0230Z
  - at: '2026-09-07T02:30:34Z'
    tier: 2b
    scope: macro_crypto
    membership: tags
    class: polymarket-leads
    lag: 38
    corr: -0.32504762712388213
    n: 910
    page: lead_lag_tier2b_macro_crypto_20260907T0230Z
  - at: '2026-09-08T03:29:45Z'
    tier: '2'
    scope: macro_fed-rates
    membership: label
    class: no-lead
    lag: 10
    corr: -0.07130135410526685
    n: 1553
    page: lead_lag_tier2_macro_fed-rates_20260908T0329Z
  - at: '2026-09-08T03:29:54Z'
    tier: '2'
    scope: macro_crypto
    membership: label
    class: no-lead
    lag: -35
    corr: -0.10133717034557642
    n: 1563
    page: lead_lag_tier2_macro_crypto_20260908T0329Z
  - at: '2026-09-08T03:30:01Z'
    tier: 2b
    scope: macro_fed-rates
    membership: tags
    class: no-lead
    lag: 10
    corr: -0.07129424788934347
    n: 1553
    page: lead_lag_tier2b_macro_fed-rates_20260908T0330Z
  - at: '2026-09-08T03:30:08Z'
    tier: 2b
    scope: macro_crypto
    membership: tags
    class: no-lead
    lag: -35
    corr: -0.1013092656518123
    n: 1563
    page: lead_lag_tier2b_macro_crypto_20260908T0330Z
  - at: '2026-09-10T19:59:30Z'
    tier: '2'
    scope: macro_fed-rates
    membership: label
    class: no-lead
    lag: 13
    corr: 0.07869253487776973
    n: 1503
    page: lead_lag_tier2_macro_fed-rates_20260910T1959Z
  - at: '2026-09-10T19:59:40Z'
    tier: '2'
    scope: macro_crypto
    membership: label
    class: no-lead
    lag: 7
    corr: -0.07454272620989778
    n: 1508
    page: lead_lag_tier2_macro_crypto_20260910T1959Z
  - at: '2026-09-10T19:59:46Z'
    tier: 2b
    scope: macro_fed-rates
    membership: tags
    class: no-lead
    lag: 13
    corr: 0.07778519618353646
    n: 1504
    page: lead_lag_tier2b_macro_fed-rates_20260910T1959Z
  - at: '2026-09-10T19:59:52Z'
    tier: 2b
    scope: macro_crypto
    membership: tags
    class: no-lead
    lag: 7
    corr: -0.07453031793424048
    n: 1509
    page: lead_lag_tier2b_macro_crypto_20260910T1959Z
---
# BTC macro regime

> One row per lead-lag verdict. The class vocabulary is fixed in WIKI_SCHEMA.md s.7; where Tier 2 and
> Tier 2b disagree for the same scope, that disagreement is the finding (the dual-tagged markets carry it).
> `Consensus (3)` is the class only when the last three runs of that tier and scope agree.

## Current, per tier and scope

| Tier | Scope | Membership | Latest | Consensus (3) | Lag (min) | Corr | n | As of |
|---|---|---|---|---|---|---|---|---|
| 1 | macro | label | **no-lead** | insufficient-history | -45 | +0.070 | 1497 | 2026-09-06T01:42:14Z |
| 2b | macro_crypto | tags | **no-lead** | mixed | 7 | -0.075 | 1509 | 2026-09-10T19:59:52Z |
| 2b | macro_fed-rates | tags | **no-lead** | no-lead | 13 | +0.078 | 1504 | 2026-09-10T19:59:46Z |
| 2 | macro_crypto | label | **no-lead** | no-lead | 7 | -0.075 | 1508 | 2026-09-10T19:59:40Z |
| 2 | macro_fed-rates | label | **no-lead** | no-lead | 13 | +0.079 | 1503 | 2026-09-10T19:59:30Z |

## Disagreements

- none

## History

| At | Tier | Scope | Membership | Class | Lag | Corr | n | Verdict page |
|---|---|---|---|---|---|---|---|---|
| 2026-09-06T01:42:14Z | 1 | macro | label | no-lead | -45 | +0.070 | 1497 | [[lead_lag_tier1_macro_20260906T0142Z]] |
| 2026-09-07T02:30:18Z | 2 | macro_fed-rates | label | no-lead | -10 | +0.052 | 2416 | [[lead_lag_tier2_macro_fed-rates_20260907T0230Z]] |
| 2026-09-07T02:30:23Z | 2 | macro_crypto | label | no-lead | 38 | -0.138 | 2389 | [[lead_lag_tier2_macro_crypto_20260907T0230Z]] |
| 2026-09-07T02:30:29Z | 2b | macro_fed-rates | tags | no-lead | 58 | +0.135 | 890 | [[lead_lag_tier2b_macro_fed-rates_20260907T0230Z]] |
| 2026-09-07T02:30:34Z | 2b | macro_crypto | tags | polymarket-leads | 38 | -0.325 | 910 | [[lead_lag_tier2b_macro_crypto_20260907T0230Z]] |
| 2026-09-08T03:29:45Z | 2 | macro_fed-rates | label | no-lead | 10 | -0.071 | 1553 | [[lead_lag_tier2_macro_fed-rates_20260908T0329Z]] |
| 2026-09-08T03:29:54Z | 2 | macro_crypto | label | no-lead | -35 | -0.101 | 1563 | [[lead_lag_tier2_macro_crypto_20260908T0329Z]] |
| 2026-09-08T03:30:01Z | 2b | macro_fed-rates | tags | no-lead | 10 | -0.071 | 1553 | [[lead_lag_tier2b_macro_fed-rates_20260908T0330Z]] |
| 2026-09-08T03:30:08Z | 2b | macro_crypto | tags | no-lead | -35 | -0.101 | 1563 | [[lead_lag_tier2b_macro_crypto_20260908T0330Z]] |
| 2026-09-10T19:59:30Z | 2 | macro_fed-rates | label | no-lead | 13 | +0.079 | 1503 | [[lead_lag_tier2_macro_fed-rates_20260910T1959Z]] |
| 2026-09-10T19:59:40Z | 2 | macro_crypto | label | no-lead | 7 | -0.075 | 1508 | [[lead_lag_tier2_macro_crypto_20260910T1959Z]] |
| 2026-09-10T19:59:46Z | 2b | macro_fed-rates | tags | no-lead | 13 | +0.078 | 1504 | [[lead_lag_tier2b_macro_fed-rates_20260910T1959Z]] |
| 2026-09-10T19:59:52Z | 2b | macro_crypto | tags | no-lead | 7 | -0.075 | 1509 | [[lead_lag_tier2b_macro_crypto_20260910T1959Z]] |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
