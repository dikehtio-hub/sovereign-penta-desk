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
  at: '2026-09-07T02:30:34Z'
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
      regime_consensus_3: insufficient-history
      runs: 1
    tier 2 macro_crypto:
      latest_verdict: no-lead
      regime_consensus_3: insufficient-history
      runs: 1
    tier 2b macro_fed-rates:
      latest_verdict: no-lead
      regime_consensus_3: insufficient-history
      runs: 1
    tier 2b macro_crypto:
      latest_verdict: polymarket-leads
      regime_consensus_3: insufficient-history
      runs: 1
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
---
# BTC macro regime

> One row per lead-lag verdict. The class vocabulary is fixed in WIKI_SCHEMA.md s.7; where Tier 2 and
> Tier 2b disagree for the same scope, that disagreement is the finding (the dual-tagged markets carry it).
> `Consensus (3)` is the class only when the last three runs of that tier and scope agree.

## Current, per tier and scope

| Tier | Scope | Membership | Latest | Consensus (3) | Lag (min) | Corr | n | As of |
|---|---|---|---|---|---|---|---|---|
| 1 | macro | label | **no-lead** | insufficient-history | -45 | +0.070 | 1497 | 2026-09-06T01:42:14Z |
| 2b | macro_crypto | tags | **polymarket-leads** | insufficient-history | 38 | -0.325 | 910 | 2026-09-07T02:30:34Z |
| 2b | macro_fed-rates | tags | **no-lead** | insufficient-history | 58 | +0.135 | 890 | 2026-09-07T02:30:29Z |
| 2 | macro_crypto | label | **no-lead** | insufficient-history | 38 | -0.138 | 2389 | 2026-09-07T02:30:23Z |
| 2 | macro_fed-rates | label | **no-lead** | insufficient-history | -10 | +0.052 | 2416 | 2026-09-07T02:30:18Z |

## Disagreements

- **macro_crypto**: Tier 2 says no-lead, Tier 2b says polymarket-leads

## History

| At | Tier | Scope | Membership | Class | Lag | Corr | n | Verdict page |
|---|---|---|---|---|---|---|---|---|
| 2026-09-06T01:42:14Z | 1 | macro | label | no-lead | -45 | +0.070 | 1497 | [[lead_lag_tier1_macro_20260906T0142Z]] |
| 2026-09-07T02:30:18Z | 2 | macro_fed-rates | label | no-lead | -10 | +0.052 | 2416 | [[lead_lag_tier2_macro_fed-rates_20260907T0230Z]] |
| 2026-09-07T02:30:23Z | 2 | macro_crypto | label | no-lead | 38 | -0.138 | 2389 | [[lead_lag_tier2_macro_crypto_20260907T0230Z]] |
| 2026-09-07T02:30:29Z | 2b | macro_fed-rates | tags | no-lead | 58 | +0.135 | 890 | [[lead_lag_tier2b_macro_fed-rates_20260907T0230Z]] |
| 2026-09-07T02:30:34Z | 2b | macro_crypto | tags | polymarket-leads | 38 | -0.325 | 910 | [[lead_lag_tier2b_macro_crypto_20260907T0230Z]] |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
