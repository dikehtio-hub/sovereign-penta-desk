---
type: Market
title: Will the Fed increase interest rates by 50+ bps after the January 2027 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed increase interest rates
  by 50+ bps after the January 2027 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:00:50Z'
status: draft
resource: polymarket:token:42452047366442275682382090045397807109079755041679563479952649068752467853296
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260906T065828_873438Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '42452047366442275682382090045397807109079755041679563479952649068752467853296'
  family: FED-RATES
  condition_id: '0x21cd6160d9de634104b719d50afa4a8ebfa3d0cd10609bf752c77b66f7bbd6a7'
  market_slug: will-the-fed-increase-interest-rates-by-50-bps-after-the-january-2027-meeting-20260729233815507
  event_slug: fed-decision-in-january-20260729233815502
  event_title: Fed Decision in January?
  start_time: '2026-07-30T00:48:09.895382Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed increase interest rates by 50+ bps after the January 2027 meeting?

> Polymarket · family FED-RATES · token `424520473664…`

## Identity

- token_id: `42452047366442275682382090045397807109079755041679563479952649068752467853296`
- condition_id: `0x21cd6160d9de634104b719d50afa4a8ebfa3d0cd10609bf752c77b66f7bbd6a7`
- market_slug: `will-the-fed-increase-interest-rates-by-50-bps-after-the-january-2027-meeting-20260729233815507`
- event: Fed Decision in January? (`fed-decision-in-january-20260729233815502`)
- start_time: `2026-07-30T00:48:09.895382Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
