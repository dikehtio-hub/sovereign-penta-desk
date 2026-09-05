---
type: Market
title: Will the Fed decrease interest rates by 25 bps after the December 2026 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed decrease interest rates
  by 25 bps after the December 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:24Z'
status: draft
resource: polymarket:token:77367448845023382525249480243608609306658725883285195065573683809293972009019
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260905T212715_501583Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '77367448845023382525249480243608609306658725883285195065573683809293972009019'
  family: FED-RATES
  condition_id: '0xf17ad24eb4ad57926495b114149c765b9b95bc286eadc91cbbfa901ceb10d0b8'
  market_slug: will-the-fed-decrease-interest-rates-by-25-bps-after-the-december-2026-meeting-20260729232808634
  event_slug: fed-decision-in-december-20260729232808632
  event_title: Fed Decision in December?
  start_time: '2026-07-30T00:58:46.257796Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed decrease interest rates by 25 bps after the December 2026 meeting?

> Polymarket · family FED-RATES · token `773674488450…`

## Identity

- token_id: `77367448845023382525249480243608609306658725883285195065573683809293972009019`
- condition_id: `0xf17ad24eb4ad57926495b114149c765b9b95bc286eadc91cbbfa901ceb10d0b8`
- market_slug: `will-the-fed-decrease-interest-rates-by-25-bps-after-the-december-2026-meeting-20260729232808634`
- event: Fed Decision in December? (`fed-decision-in-december-20260729232808632`)
- start_time: `2026-07-30T00:58:46.257796Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
