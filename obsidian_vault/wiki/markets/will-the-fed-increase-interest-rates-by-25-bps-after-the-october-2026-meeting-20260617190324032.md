---
type: Market
title: Will the Fed increase interest rates by 25 bps after the October 2026 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed increase interest rates
  by 25 bps after the October 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:00:50Z'
status: draft
resource: polymarket:token:55159722761418013044126414276680602270318000841690689684819994448621694923050
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260906T065828_873438Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '55159722761418013044126414276680602270318000841690689684819994448621694923050'
  family: FED-RATES
  condition_id: '0x12aa13b3da17ceae1b0a59b5d5b77121e91bb79b4bb0b52bf6543ed3f8d0953b'
  market_slug: will-the-fed-increase-interest-rates-by-25-bps-after-the-october-2026-meeting-20260617190324032
  event_slug: fed-decision-in-october-20260617190323537
  event_title: Fed Decision in October?
  start_time: '2026-06-17T23:34:28.470106Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed increase interest rates by 25 bps after the October 2026 meeting?

> Polymarket · family FED-RATES · token `551597227614…`

## Identity

- token_id: `55159722761418013044126414276680602270318000841690689684819994448621694923050`
- condition_id: `0x12aa13b3da17ceae1b0a59b5d5b77121e91bb79b4bb0b52bf6543ed3f8d0953b`
- market_slug: `will-the-fed-increase-interest-rates-by-25-bps-after-the-october-2026-meeting-20260617190324032`
- event: Fed Decision in October? (`fed-decision-in-october-20260617190323537`)
- start_time: `2026-06-17T23:34:28.470106Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
