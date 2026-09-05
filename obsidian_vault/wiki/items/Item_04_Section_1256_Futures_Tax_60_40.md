---
type: Item
title: 'Item 4: Section 1256 Futures Tax Ingestion (60/40 Rule)'
description: 'Ingests CME futures trade confirmations (CME MES, MNQ, ES, NQ)

  from Tradovate/NinjaTrader.'
tags:
- item
- desk-5
- tier-1
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:19Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 5
  item: 4
  tier: 1
  registry_checked: true
---
# Item 4: Section 1256 Futures Tax Ingestion (60/40 Rule)

> Tier 1: Core Foundation & Risk Defense · deployed · [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]

## What it does

Ingests CME futures trade confirmations (CME MES, MNQ, ES, NQ)
from Tradovate/NinjaTrader. Automatically classifies them under IRC §1256
(60% long-term / 40% short-term capital gains rate regardless of holding time).

## Where it lives

- `Tax_Reserve_Agent/ingestors/tradovate.py`

## How to activate

```
# Drop Tradovate execution receipts into Tax_Reserve_Agent/data/imports/ then run:
python -m Tax_Reserve_Agent.main import
```

## Test

```
python -m unittest Tax_Reserve_Agent.tests.test_tradovate_receipts
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline)

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
