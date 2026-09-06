---
type: Market
title: Will the Fed increase interest rates by 25 bps after the January 2027 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed increase interest rates
  by 25 bps after the January 2027 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:00:50Z'
status: draft
resource: polymarket:token:58421987972100586826330616250690474504359298033602990223828098109695719571344
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260906T065828_873438Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '58421987972100586826330616250690474504359298033602990223828098109695719571344'
  family: FED-RATES
  condition_id: '0x50642b28be893e8752649e9ae6d687558fc5dcfeeecd10713cf59ef6ea0edce4'
  market_slug: will-the-fed-increase-interest-rates-by-25-bps-after-the-january-2027-meeting-20260729233815506
  event_slug: fed-decision-in-january-20260729233815502
  event_title: Fed Decision in January?
  start_time: '2026-07-30T00:49:40.350956Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed increase interest rates by 25 bps after the January 2027 meeting?

> Polymarket · family FED-RATES · token `584219879721…`

## Identity

- token_id: `58421987972100586826330616250690474504359298033602990223828098109695719571344`
- condition_id: `0x50642b28be893e8752649e9ae6d687558fc5dcfeeecd10713cf59ef6ea0edce4`
- market_slug: `will-the-fed-increase-interest-rates-by-25-bps-after-the-january-2027-meeting-20260729233815506`
- event: Fed Decision in January? (`fed-decision-in-january-20260729233815502`)
- start_time: `2026-07-30T00:49:40.350956Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
