---
type: Concept
title: Latency decay across events
description: Seconds of resting depth that survive a scheduled print, per recorded
  event and market; the cross-event table for the sniper thesis.
tags:
- concept
- desk-3
- item-12
- latency-decay
generated:
  by: claude-code/fable-5.1
  at: '2026-09-16T18:14:22Z'
status: draft
sources:
- id: profiles
  resource: obsidian_vault/wiki/profiles
  title: Reaction Profile pages
  author: claude-code/fable-5.1
dev:
  desk: 3
  item: 12
  history:
  - event: fomc_2026-09-16
    rule: 'FOMC 2026-09-16: no change'
    token_id: '5615282760875985231868508008056959876238536896643315063916840237042205273721'
    outcome: 'NO'
    page: fomc_2026-09-16__FOMC_2026_09_16_no_change
    baseline_notional: null
    first_change_s: null
    half_s: null
    tenth_s: null
    gone_s: null
    max_post_notional: null
    notional_seconds: null
    pre_print_stamps: null
    post_print_stamps: null
  - event: fomc_2026-09-16
    rule: 'FOMC 2026-09-16: hike 25 bps'
    token_id: '63842529068710005716169325380315470359047749786610778647370693404952498013178'
    outcome: 'YES'
    page: fomc_2026-09-16__FOMC_2026_09_16_hike_25_bps
    baseline_notional: 87221.29
    first_change_s: 0.939
    half_s: 1.939
    tenth_s: 5.942
    gone_s: 5.942
    max_post_notional: 78225.09
    notional_seconds: 162777.46
    pre_print_stamps: 119
    post_print_stamps: 300
  - event: fomc_2026-09-16
    rule: 'FOMC 2026-09-16: hike 50+ bps'
    token_id: '88912926533493988427719291698947688154042720958310632316541141466409683822293'
    outcome: 'NO'
    page: fomc_2026-09-16__FOMC_2026_09_16_hike_50_bps
    baseline_notional: null
    first_change_s: null
    half_s: null
    tenth_s: null
    gone_s: null
    max_post_notional: null
    notional_seconds: null
    pre_print_stamps: null
    post_print_stamps: null
---
# Latency decay across events

> How many seconds resting Polymarket depth survives after a scheduled print, event by event. This is the
> table the roadmap's "10-50 % per event" claim has to be checked against; each row is one recorded market.

| Event | Market | Outcome | Baseline | First change | Half | Tenth | Gone | $-seconds | Profile |
|---|---|---|---|---|---|---|---|---|---|
| fomc_2026-09-16 | FOMC 2026-09-16: no change | NO | - | - | - | - | - | - | [[fomc_2026-09-16__FOMC_2026_09_16_no_change]] |
| fomc_2026-09-16 | FOMC 2026-09-16: hike 25 bps | YES | $87,221 | 0.939 s | 1.939 s | 5.942 s | 5.942 s | $162,777 | [[fomc_2026-09-16__FOMC_2026_09_16_hike_25_bps]] |
| fomc_2026-09-16 | FOMC 2026-09-16: hike 50+ bps | NO | - | - | - | - | - | - | [[fomc_2026-09-16__FOMC_2026_09_16_hike_50_bps]] |

## Reading

- `Half` and `Tenth` are the numbers that matter: the seconds a sniper has before the book is half gone and a tenth left.
- `$-seconds` integrates fillable notional over the post-print window: the size of the opportunity times how long it lasted.
- A deferred row (neg_risk NO side, Ruling R4) carries no numbers on purpose.

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]
