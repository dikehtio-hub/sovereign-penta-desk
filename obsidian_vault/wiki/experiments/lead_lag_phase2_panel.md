---
type: Experiment
title: Item 18 Phase 2 panel
description: 'Event-driven lead-lag panel: insufficient (0 of 3 informative events).'
tags:
- experiment
- desk-3
- item-18
- lead-lag
- event-study
- panel
generated:
  by: claude-code/fable-5.1
  at: '2026-09-16T21:13:59Z'
status: draft
sources:
- id: profiles
  resource: obsidian_vault/wiki/experiments
  title: reaction_profile_* pages
  author: claude-code/fable-5.1
dev:
  desk: 3
  item: 18
  kind: event_study_panel
  registration: cross_market/experiments/lead_lag_phase2_fomc.meta.json
  profiles:
  - reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_hike_25_bps
  - reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_hike_50_bps
  - reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_no_change
  events:
  - event: fomc_2026-09-16
    classification: uninformative-shock
    informative: false
    release_utc: '2026-09-16T18:00:00Z'
    lead_s: null
  status:
    events: 1
    informative_events: 0
    min_informative_events: 3
    verdict: insufficient (0 of 3 informative events)
    stopping: null
---
# Item 18 Phase 2 panel: event-driven lead-lag

> 0 informative event(s) of 3 required · verdict: **insufficient (0 of 3 informative events)**

## Profiles

| Event | Market | Class | Lead (s) | Counted | Primary | Print |
|---|---|---|---|---|---|---|
| [[reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_hike_25_bps\|fomc_2026-09-16]] | FOMC 2026-09-16: hike 25 bps | uninformative-shock | n/a | no | primary | 2026-09-16 |
| [[reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_hike_50_bps\|fomc_2026-09-16]] | FOMC 2026-09-16: hike 50+ bps | uninformative-shock | n/a | no |  | 2026-09-16 |
| [[reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_no_change\|fomc_2026-09-16]] | FOMC 2026-09-16: no change | uninformative-shock | n/a | no |  | 2026-09-16 |

## Sequence of primary markets

| Print | Event | Class | Lead (s) | Counted |
|---|---|---|---|---|
| 2026-09-16 | fomc_2026-09-16 | uninformative-shock | n/a | no |

## Stopping rules (pre-registered, R125-2 s.8.4)

- non-displacing print: uninformative-shock, logged, not counted
- rule 1: two consecutive informative events contemporaneous or hyperliquid-leads -> the line is terminated
- rule 2: the three registered prints all uninformative -> retired 2026-11-01
- capital bar: polymarket-leads-event on at least 2 of 3 informative events

## Related

- [[lead_lag_phase2_fomc_meta|Phase 2 registration]]
- [[btc_macro_regime|BTC macro regime (Phase 1 consensus)]]
- [[experiments_register|Experiments register]]
