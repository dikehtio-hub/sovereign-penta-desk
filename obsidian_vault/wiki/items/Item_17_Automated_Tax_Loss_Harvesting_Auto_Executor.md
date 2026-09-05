---
type: Item
title: 'Item 17: Automated Tax-Loss Harvesting Auto-Executor'
description: 'Scans tax lot ledgers across crypto and prediction markets to

  identify underwater positions, calculate exact tax alpha, and recommend

  statutory loss harvesting while avoiding wash-sale pitfalls.'
tags:
- item
- desk-5
- tier-4
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T20:05:15Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 5
  item: 17
  tier: 4
  registry_checked: true
  asserts:
  - file: Tax_Reserve_Agent/main.py
    pattern: .
    claim: primary code present at the registered path
---
# Item 17: Automated Tax-Loss Harvesting Auto-Executor

> Tier 4: Analytics, Optimization & Master Cockpit · deployed · [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]

## What it does

Scans tax lot ledgers across crypto and prediction markets to
identify underwater positions, calculate exact tax alpha, and recommend
statutory loss harvesting while avoiding wash-sale pitfalls.

## Where it lives

- `Tax_Reserve_Agent/main.py`

## How to activate

```
# Generate tax-loss harvesting recommendations:
python -m Tax_Reserve_Agent.main harvest
# Rebuild lot ledger from raw transaction imports:
python -m Tax_Reserve_Agent.main rebuild
```

## Test

```
python -m unittest Tax_Reserve_Agent.tests.test_new_features
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline)

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
