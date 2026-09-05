---
type: Market
title: Will the Fed decrease interest rates by 50+ bps after the January 2027 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed decrease interest rates
  by 50+ bps after the January 2027 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:24Z'
status: draft
resource: polymarket:token:45053521911672808043600263178798111402897730682087979734684574823004307023433
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260905T212715_501583Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '45053521911672808043600263178798111402897730682087979734684574823004307023433'
  family: FED-RATES
  condition_id: '0xfd0fb47daa40f79ed1bd8a0645d028c4583391b70860e4447f93b3b9fe797865'
  market_slug: will-the-fed-decrease-interest-rates-by-50-bps-after-the-january-2027-meeting-20260729233815503
  event_slug: fed-decision-in-january-20260729233815502
  event_title: Fed Decision in January?
  start_time: '2026-07-30T00:56:07.392315Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed decrease interest rates by 50+ bps after the January 2027 meeting?

> Polymarket · family FED-RATES · token `450535219116…`

## Identity

- token_id: `45053521911672808043600263178798111402897730682087979734684574823004307023433`
- condition_id: `0xfd0fb47daa40f79ed1bd8a0645d028c4583391b70860e4447f93b3b9fe797865`
- market_slug: `will-the-fed-decrease-interest-rates-by-50-bps-after-the-january-2027-meeting-20260729233815503`
- event: Fed Decision in January? (`fed-decision-in-january-20260729233815502`)
- start_time: `2026-07-30T00:56:07.392315Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
