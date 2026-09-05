---
type: Market
title: Will the Fed increase interest rates by 50+ bps after the December 2026 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed increase interest rates
  by 50+ bps after the December 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:24Z'
status: draft
resource: polymarket:token:35090254409399344650860070211816464534198960801264823587796928404808383727584
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260905T212715_501583Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '35090254409399344650860070211816464534198960801264823587796928404808383727584'
  family: FED-RATES
  condition_id: '0xa5f8a44504de30fa36fff2406b2b27b3d15476ed50448e4fc3ead4861d8a5e3e'
  market_slug: will-the-fed-increase-interest-rates-by-50-bps-after-the-december-2026-meeting-20260729232808637
  event_slug: fed-decision-in-december-20260729232808632
  event_title: Fed Decision in December?
  start_time: '2026-07-30T01:01:52.935105Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed increase interest rates by 50+ bps after the December 2026 meeting?

> Polymarket · family FED-RATES · token `350902544093…`

## Identity

- token_id: `35090254409399344650860070211816464534198960801264823587796928404808383727584`
- condition_id: `0xa5f8a44504de30fa36fff2406b2b27b3d15476ed50448e4fc3ead4861d8a5e3e`
- market_slug: `will-the-fed-increase-interest-rates-by-50-bps-after-the-december-2026-meeting-20260729232808637`
- event: Fed Decision in December? (`fed-decision-in-december-20260729232808632`)
- start_time: `2026-07-30T01:01:52.935105Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
