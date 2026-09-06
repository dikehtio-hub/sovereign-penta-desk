---
type: Experiment
title: 'Experiment: latency_sniper_fomc_2026-09-16'
description: PRE-REGISTERED (Ruling R2c).
tags:
- experiment
- desk-3
- item-12
- latency-sniper
- pre-registered
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:49Z'
status: draft
sources:
- id: registration
  resource: cross_market/experiments/fomc_2026-09-16.rules.json
  title: fomc_2026-09-16.rules.json
  author: human:operator
dev:
  desk: 3
  item: 12
  registration: cross_market/experiments/fomc_2026-09-16.rules.json
  kind: sniper_rules
  registered_utc: '2026-09-05T18:10:19.503594+00:00'
  release_utc: '2026-09-16T18:00:00Z'
  window:
    start: '2026-09-16T17:58:00Z'
    end: '2026-09-16T18:05:00Z'
  tokens:
  - '5615282760875985231868508008056959876238536896643315063916840237042205273721'
  - '63842529068710005716169325380315470359047749786610778647370693404952498013178'
  - '88912926533493988427719291698947688154042720958310632316541141466409683822293'
  not_found_in_drop:
  - 'FOMC 2026-09-17: cut 25 bps'
  - 'FOMC 2026-09-17: cut 50+ bps'
  tests_run: 0
---
# Experiment: latency_sniper_fomc_2026-09-16

> Pre-registration, Item 12 (latency sniper). Reaction Profile pages link back here after the print.

## Status at registration

PRE-REGISTERED (Ruling R2c). Token ids are the live Polymarket YES tokens from the macro drop of 2026-09-05. NEVER edit inside the event window (T-2 min to T+5 min). A market absent here on registration day may be APPENDED before the window in a dated re-registration, never replaced.

## Window

- release: `2026-09-16T18:00:00Z`
- window: `2026-09-16T17:58:00Z` .. `2026-09-16T18:05:00Z` (T-2 .. T+5; this page is frozen inside it)

## Event schema

- kind: `fed_rate`
- payload: `{"change_bps": "int: target-range change in basis points; 0 = hold"}`
- source: federalreserve.gov statement
- confidence: >= 0.99 only when the number is read from the statement itself

## Reading

All markets are neg_risk: Ruling R4 - only the winning outcome's YES asks are lifted; NO sides are deferred.

## Rules

| Label | Fires when | Outcome | YES at registration | neg_risk | Token |
|---|---|---|---|---|---|
| FOMC 2026-09-16: no change | `change_bps == 0` | YES | 0.5 | True | `561528276087…` |
| FOMC 2026-09-16: hike 25 bps | `change_bps == 25` | YES | 0.5 | True | `638425290687…` |
| FOMC 2026-09-16: hike 50+ bps | `change_bps >= 50` | YES | 0.007 | True | `889129265334…` |

## Not found in the drop at registration

- FOMC 2026-09-17: cut 25 bps
- FOMC 2026-09-17: cut 50+ bps

## Corrections (all before the window)

- `2026-09-05T18:15:46.362247+00:00`: date corrected from 2026-09-17 to 2026-09-16 (FOMC meeting September 15-16 per federalreserve.gov/monetarypolicy/fomccalendars.htm; statement 2:00 p.m. ET on the final day); rules, tokens and thresholds unchanged (before_window=True)

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]
- [[Ruling_R02|R2 - record the CLOB around a scheduled print]]
- [[Ruling_R04|R4 - neg_risk books skip the NO side]]
- [[experiments_register|Experiments register]]
