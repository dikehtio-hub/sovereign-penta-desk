---
type: Item
title: 'Item 2: Sports Gambling Tax & Loss Deduction Module'
description: 'Computes statutory tax liability under IRC §61 and §165(d).

  Implements New Jersey state tax netting (Union NJ 07083: 24% Fed + 6.37% NJ + 2%

  buffer = 32.37% composite).'
tags:
- item
- desk-5
- tier-1
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:06Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 5
  item: 2
  tier: 1
  registry_checked: true
  requires_files:
  - Tax_Reserve_Agent/engine/gambling_tax.py
  - Tax_Reserve_Agent/ingestors/sports_betting.py
---
# Item 2: Sports Gambling Tax & Loss Deduction Module

> Tier 1: Core Foundation & Risk Defense · deployed · [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]

## What it does

Computes statutory tax liability under IRC §61 and §165(d).
Implements New Jersey state tax netting (Union NJ 07083: 24% Fed + 6.37% NJ + 2%
buffer = 32.37% composite). Avoids the federal standard deduction trap (losses
non-deductible federally without itemizing on Schedule A) and tracks Form W-2G
withholding credits.

## Where it lives

- `Tax_Reserve_Agent/engine/gambling_tax.py`
- `Tax_Reserve_Agent/ingestors/sports_betting.py`

## How to activate

```
# Ingest settled sportsbook bet slips from CSV drop directory:
python -m Tax_Reserve_Agent.main import
# View current gambling escrow vs net winnings:
python -m Tax_Reserve_Agent.main status
```

## Test

```
python -m unittest Tax_Reserve_Agent.tests.test_sports_tax
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline)

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
