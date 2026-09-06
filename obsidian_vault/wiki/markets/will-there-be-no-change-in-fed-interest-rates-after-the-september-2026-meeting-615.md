---
type: Market
title: Will there be no change in Fed interest rates after the September 2026 meeting?
description: 'Polymarket market (FED-RATES): Will there be no change in Fed interest
  rates after the September 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T05:54:30Z'
status: draft
resource: polymarket:token:5615282760875985231868508008056959876238536896643315063916840237042205273721
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260906T055238_875025Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
- id: rules
  resource: cross_market/experiments/fomc_2026-09-16.rules.json
  title: sniper rules registration
  author: human:operator
dev:
  desk: 3
  token_id: '5615282760875985231868508008056959876238536896643315063916840237042205273721'
  family: FED-RATES
  condition_id: '0xa3b36b2d6104d34af4e6c6215fc818e43352e78a748fbfb0b85e3a35f71dec9a'
  market_slug: will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615
  event_slug: fed-decision-in-september-762
  event_title: Fed Decision in September?
  start_time: '2026-05-13T21:23:13.517067Z'
  first_seen: '2026-09-05T21:27:15Z'
  neg_risk: true
  rule_label: 'FOMC 2026-09-16: no change'
---
# Market: Will there be no change in Fed interest rates after the September 2026 meeting?

> Polymarket · family FED-RATES · token `561528276087…`

## Identity

- token_id: `5615282760875985231868508008056959876238536896643315063916840237042205273721`
- condition_id: `0xa3b36b2d6104d34af4e6c6215fc818e43352e78a748fbfb0b85e3a35f71dec9a`
- market_slug: `will-there-be-no-change-in-fed-interest-rates-after-the-september-2026-meeting-615`
- event: Fed Decision in September? (`fed-decision-in-september-762`)
- start_time: `2026-05-13T21:23:13.517067Z`
- neg_risk: True (from the rules registration; Ruling R4 applies)

## Bound by

- rule `FOMC 2026-09-16: no change` in `cross_market/experiments/fomc_2026-09-16.rules.json`

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
