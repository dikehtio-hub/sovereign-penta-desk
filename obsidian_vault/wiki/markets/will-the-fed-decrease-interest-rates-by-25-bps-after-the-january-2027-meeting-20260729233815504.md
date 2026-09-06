---
type: Market
title: Will the Fed decrease interest rates by 25 bps after the January 2027 meeting?
description: 'Polymarket market (FED-RATES): Will the Fed decrease interest rates
  by 25 bps after the January 2027 meeting?'
tags:
- market
- polymarket
- fed-rates
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T05:54:30Z'
status: draft
resource: polymarket:token:55531205670373260499988385930313327116586167390725681551489621136380793885916
sources:
- id: drop
  resource: Sports_Desk/data/polymarket_drops/polymarket_macro_20260906T055238_875025Z.json
  title: newest macro drop
  author: process:cross_market.ingestors.polymarket_fetcher
dev:
  desk: 3
  token_id: '55531205670373260499988385930313327116586167390725681551489621136380793885916'
  family: FED-RATES
  condition_id: '0x0bbe79a986a3f84ea82ebe714159fcfaa488f80df878599e2cd9297ea57ee60f'
  market_slug: will-the-fed-decrease-interest-rates-by-25-bps-after-the-january-2027-meeting-20260729233815504
  event_slug: fed-decision-in-january-20260729233815502
  event_title: Fed Decision in January?
  start_time: '2026-07-30T00:59:14.079503Z'
  first_seen: '2026-09-05T21:27:15Z'
---
# Market: Will the Fed decrease interest rates by 25 bps after the January 2027 meeting?

> Polymarket · family FED-RATES · token `555312056703…`

## Identity

- token_id: `55531205670373260499988385930313327116586167390725681551489621136380793885916`
- condition_id: `0x0bbe79a986a3f84ea82ebe714159fcfaa488f80df878599e2cd9297ea57ee60f`
- market_slug: `will-the-fed-decrease-interest-rates-by-25-bps-after-the-january-2027-meeting-20260729233815504`
- event: Fed Decision in January? (`fed-decision-in-january-20260729233815502`)
- start_time: `2026-07-30T00:59:14.079503Z`

## Bound by

- no sniper rule; listed as part of the family

## Lifecycle

- no prices here (s.6); the dashboards carry the live number
- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page

## Related

- [[markets_register|Markets register]]
- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
