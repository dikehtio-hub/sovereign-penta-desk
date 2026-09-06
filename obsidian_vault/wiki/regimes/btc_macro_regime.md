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
  at: '2026-09-06T01:42:14Z'
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
---
# BTC macro regime

> One row per lead-lag verdict. The class vocabulary is fixed in WIKI_SCHEMA.md s.7; where Tier 2 and
> Tier 2b disagree for the same scope, that disagreement is the finding (the dual-tagged markets carry it).
> `Consensus (3)` is the class only when the last three runs of that tier and scope agree.

## Current, per tier and scope

| Tier | Scope | Membership | Latest | Consensus (3) | Lag (min) | Corr | n | As of |
|---|---|---|---|---|---|---|---|---|
| 1 | macro | label | **no-lead** | insufficient-history | -45 | +0.070 | 1497 | 2026-09-06T01:42:14Z |

## Disagreements

- none

## History

| At | Tier | Scope | Membership | Class | Lag | Corr | n | Verdict page |
|---|---|---|---|---|---|---|---|---|
| 2026-09-06T01:42:14Z | 1 | macro | label | no-lead | -45 | +0.070 | 1497 | [[lead_lag_tier1_macro_20260906T0142Z]] |

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]
