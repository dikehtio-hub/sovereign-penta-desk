---
type: Market
title: Will there be no change in Fed interest rates after the October 2026 meeting?
description: 'Polymarket market (FED-RATES): Will there be no change in Fed interest
  rates after the October 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T05:54:30Z'
status: draft
resource: polymarket:token:111061902544814266207267295505639408607400625795891618462682726460921782993748
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260906T055238_875025Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '111061902544814266207267295505639408607400625795891618462682726460921782993748'
  family: FED-RATES
  condition_id: '0xdf9bf27ee5757c55b44b8b9826ddc9ec3a8809aa3278634c45edbb7fc8f1a3e3'
  market_slug: will-there-be-no-change-in-fed-interest-rates-after-the-october-2026-meeting-20260617190324031
  event_slug: fed-decision-in-october-20260617190323537
  event_title: Fed Decision in October?
  start_time: '2026-06-18T00:02:51.727205Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will there be no change in Fed interest rates after the October 2026 meeting?

> Polymarket · family FED-RATES · token `111061902544…`

## Identity

- token_id: `111061902544814266207267295505639408607400625795891618462682726460921782993748`
- condition_id: `0xdf9bf27ee5757c55b44b8b9826ddc9ec3a8809aa3278634c45edbb7fc8f1a3e3`
- market_slug: `will-there-be-no-change-in-fed-interest-rates-after-the-october-2026-meeting-20260617190324031`
- event: Fed Decision in October? (`fed-decision-in-october-20260617190323537`)
- start_time: `2026-06-18T00:02:51.727205Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
