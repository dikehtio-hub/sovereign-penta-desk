---
type: Market
title: Will the Fed increase interest rates by 50+ bps after the September 2026 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed increase interest rates
  by 50+ bps after the September 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T05:54:30Z'
status: draft
resource: polymarket:token:88912926533493988427719291698947688154042720958310632316541141466409683822293
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
  token_id: '88912926533493988427719291698947688154042720958310632316541141466409683822293'
  family: FED-RATES
  condition_id: '0x2e4b58fc18dbffd74d5275d89fb076943f21992763c45dcadd81391b83bde13c'
  market_slug: will-the-fed-increase-interest-rates-by-50-bps-after-the-september-2026-meeting-664
  event_slug: fed-decision-in-september-762
  event_title: Fed Decision in September?
  start_time: '2026-05-13T21:23:16.501737Z'
  first_seen: '2026-09-05T21:27:15Z'
  neg_risk: true
  rule_label: 'FOMC 2026-09-16: hike 50+ bps'
---
# Market: Will the Fed increase interest rates by 50+ bps after the September 2026 meeting?

> Polymarket · family FED-RATES · token `889129265334…`

## Identity

- token_id: `88912926533493988427719291698947688154042720958310632316541141466409683822293`
- condition_id: `0x2e4b58fc18dbffd74d5275d89fb076943f21992763c45dcadd81391b83bde13c`
- market_slug: `will-the-fed-increase-interest-rates-by-50-bps-after-the-september-2026-meeting-664`
- event: Fed Decision in September? (`fed-decision-in-september-762`)
- start_time: `2026-05-13T21:23:16.501737Z`
- neg_risk: True (from the rules registration; Ruling R4 applies)

## Bound by

- rule `FOMC 2026-09-16: hike 50+ bps` in `cross_market/experiments/fomc_2026-09-16.rules.json`

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
