---
type: Item
title: 'Item 3: Multi-Market Bankroll Hurdle & Gating Hook'
description: Centralized pre-flight gate.
tags:
- item
- desk-5
- tier-1
- deployed
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:42Z'
status: draft
sources:
- id: top20-registry
  resource: MASTER_COMMAND_LIST.txt
  title: Top 20 ecosystem registry (MASTER_COMMAND_LIST.txt lines 80-484)
  author: human:operator
dev:
  desk: 5
  item: 3
  tier: 1
  registry_checked: true
  requires_files:
  - Tax_Reserve_Agent/interfaces/monarch_hook.py
  - Tax_Reserve_Agent/main.py
---
# Item 3: Multi-Market Bankroll Hurdle & Gating Hook

> Tier 1: Core Foundation & Risk Defense · deployed · [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]

## What it does

Centralized pre-flight gate. Recomputes the required after-tax
break-even edge before any wager or trade is executed. Fails closed (rejects
orders) if the tax ledger is uninitialized or if available unreserved cash is $0.

## Where it lives

- `Tax_Reserve_Agent/interfaces/monarch_hook.py`
- `Tax_Reserve_Agent/main.py`

## How to activate

```
# Check if bankroll gate approves a proposed bet or position size:
python -m Tax_Reserve_Agent.main bankroll --check 1000
# Seed paper bankroll deposit (never do this on live IRS ledger):
python -m Tax_Reserve_Agent.main seed-bankroll --paper-bankroll 10000
```

## Test

```
python -m unittest Tax_Reserve_Agent.tests.test_empty_ledger
```

## Status

Deployed (registry checkbox [x])

Added: 2026-09-03 21:53 EDT (Round 26L Baseline; hardened Round 33: 2026-09-04 00:05 EDT)

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
