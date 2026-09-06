---
type: Market
title: Will the Fed decrease interest rates by 25 bps after the October 2026 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed decrease interest rates
  by 25 bps after the October 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T05:54:30Z'
status: draft
resource: polymarket:token:33268510350568915228897273528353467773422190590579607471427765079749830445947
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260906T055238_875025Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '33268510350568915228897273528353467773422190590579607471427765079749830445947'
  family: FED-RATES
  condition_id: '0x9cf563d7b55aa9aa876d5d7e55126347eee473f0ae56d799e325fdef2bf25297'
  market_slug: will-the-fed-decrease-interest-rates-by-25-bps-after-the-october-2026-meeting-20260617190324030
  event_slug: fed-decision-in-october-20260617190323537
  event_title: Fed Decision in October?
  start_time: '2026-06-18T00:02:08.765961Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed decrease interest rates by 25 bps after the October 2026 meeting?

> Polymarket · family FED-RATES · token `332685103505…`

## Identity

- token_id: `33268510350568915228897273528353467773422190590579607471427765079749830445947`
- condition_id: `0x9cf563d7b55aa9aa876d5d7e55126347eee473f0ae56d799e325fdef2bf25297`
- market_slug: `will-the-fed-decrease-interest-rates-by-25-bps-after-the-october-2026-meeting-20260617190324030`
- event: Fed Decision in October? (`fed-decision-in-october-20260617190323537`)
- start_time: `2026-06-18T00:02:08.765961Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
