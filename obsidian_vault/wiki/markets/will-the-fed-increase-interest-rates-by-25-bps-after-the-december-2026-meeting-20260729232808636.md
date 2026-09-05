---
type: Market
title: Will the Fed increase interest rates by 25 bps after the December 2026 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed increase interest rates
  by 25 bps after the December 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:24Z'
status: draft
resource: polymarket:token:111662129652828266889360374468657435151479595863413519836161861837506140152890
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260905T212715_501583Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '111662129652828266889360374468657435151479595863413519836161861837506140152890'
  family: FED-RATES
  condition_id: '0x8a4196617dcb703e49d9bb36d3847bf6a75fd364dbd19f8d408ac944bf1a03d8'
  market_slug: will-the-fed-increase-interest-rates-by-25-bps-after-the-december-2026-meeting-20260729232808636
  event_slug: fed-decision-in-december-20260729232808632
  event_title: Fed Decision in December?
  start_time: '2026-07-30T00:55:13.207782Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed increase interest rates by 25 bps after the December 2026 meeting?

> Polymarket · family FED-RATES · token `111662129652…`

## Identity

- token_id: `111662129652828266889360374468657435151479595863413519836161861837506140152890`
- condition_id: `0x8a4196617dcb703e49d9bb36d3847bf6a75fd364dbd19f8d408ac944bf1a03d8`
- market_slug: `will-the-fed-increase-interest-rates-by-25-bps-after-the-december-2026-meeting-20260729232808636`
- event: Fed Decision in December? (`fed-decision-in-december-20260729232808632`)
- start_time: `2026-07-30T00:55:13.207782Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
