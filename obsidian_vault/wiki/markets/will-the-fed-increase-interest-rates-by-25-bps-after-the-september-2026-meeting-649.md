---
type: Market
title: Will the Fed increase interest rates by 25 bps after the September 2026 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed increase interest rates
  by 25 bps after the September 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:24Z'
status: draft
resource: polymarket:token:63842529068710005716169325380315470359047749786610778647370693404952498013178
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260905T212715_501583Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
- id: rules
  resource: cross_market/experiments/fomc_2026-09-16.rules.json
  title: sniper rules registration
  author: human:operator
dev:
  desk: 3
  token_id: '63842529068710005716169325380315470359047749786610778647370693404952498013178'
  family: FED-RATES
  condition_id: '0x876506d8b2bd7a0d3fa4fe18c024eee6e1dd81ee24c26795dadd6cfe4a7b5d0d'
  market_slug: will-the-fed-increase-interest-rates-by-25-bps-after-the-september-2026-meeting-649
  event_slug: fed-decision-in-september-762
  event_title: Fed Decision in September?
  start_time: '2026-05-13T21:23:15.981841Z'
  first_seen: '2026-09-05T21:27:15Z'
  neg_risk: true
  rule_label: 'FOMC 2026-09-16: hike 25 bps'
---
# Market: Will the Fed increase interest rates by 25 bps after the September 2026 meeting?

> Polymarket · family FED-RATES · token `638425290687…`

## Identity

- token_id: `63842529068710005716169325380315470359047749786610778647370693404952498013178`
- condition_id: `0x876506d8b2bd7a0d3fa4fe18c024eee6e1dd81ee24c26795dadd6cfe4a7b5d0d`
- market_slug: `will-the-fed-increase-interest-rates-by-25-bps-after-the-september-2026-meeting-649`
- event: Fed Decision in September? (`fed-decision-in-september-762`)
- start_time: `2026-05-13T21:23:15.981841Z`
- neg_risk: True (from the rules registration; Ruling R4 applies)

## Bound by

- rule `FOMC 2026-09-16: hike 25 bps` in `cross_market/experiments/fomc_2026-09-16.rules.json`

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
