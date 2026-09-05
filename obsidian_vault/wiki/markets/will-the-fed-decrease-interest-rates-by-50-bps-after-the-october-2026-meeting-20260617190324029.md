---
type: Market
title: Will the Fed decrease interest rates by 50+ bps after the October 2026 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed decrease interest rates
  by 50+ bps after the October 2026 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:24Z'
status: draft
resource: polymarket:token:17010377994663817312158123655937348199252960045746746128731746451645055725586
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260905T212715_501583Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '17010377994663817312158123655937348199252960045746746128731746451645055725586'
  family: FED-RATES
  condition_id: '0xa69ef420d8b4075ad8ba8611d02c63cb2ece46f5c8c643af223c272689b0c96f'
  market_slug: will-the-fed-decrease-interest-rates-by-50-bps-after-the-october-2026-meeting-20260617190324029
  event_slug: fed-decision-in-october-20260617190323537
  event_title: Fed Decision in October?
  start_time: '2026-06-18T00:33:16.217093Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed decrease interest rates by 50+ bps after the October 2026 meeting?

> Polymarket · family FED-RATES · token `170103779946…`

## Identity

- token_id: `17010377994663817312158123655937348199252960045746746128731746451645055725586`
- condition_id: `0xa69ef420d8b4075ad8ba8611d02c63cb2ece46f5c8c643af223c272689b0c96f`
- market_slug: `will-the-fed-decrease-interest-rates-by-50-bps-after-the-october-2026-meeting-20260617190324029`
- event: Fed Decision in October? (`fed-decision-in-october-20260617190323537`)
- start_time: `2026-06-18T00:33:16.217093Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
