---
type: Concept
title: 'Thesis: Polymarket/Polymarket_Monarch/tax_gate.py'
description: 'Monarch and the agent are separate projects in sibling folders, neither
  on the other''s import path. Rather than scatter `sys.path` surgery and try/except
  imports through every scanner, the coupling lives here: one import, one failure
  mode, one place to change when either project …'
tags:
- concept
- thesis
- desk-3
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: Polymarket/Polymarket_Monarch/tax_gate.py
  title: Polymarket/Polymarket_Monarch/tax_gate.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Polymarket/Polymarket_Monarch/tax_gate.py
  headings:
  - WHY THIS FILE EXISTS AT ALL
  - FAIL-OPEN, LOUDLY - AND ONLY HERE
  asserts:
  - file: Polymarket/Polymarket_Monarch/tax_gate.py
    pattern: WHY\ THIS\ FILE\ EXISTS\ AT\ ALL
    claim: the docstring still carries the section 'WHY THIS FILE EXISTS AT ALL'
  - file: Polymarket/Polymarket_Monarch/tax_gate.py
    pattern: FAIL\-OPEN,\ LOUDLY\ \-\ AND\ ONLY\ HERE
    claim: the docstring still carries the section 'FAIL-OPEN, LOUDLY - AND ONLY HERE'
  requires_files:
  - Polymarket/Polymarket_Monarch/tax_gate.py
  desk: 3
---
# Thesis: Polymarket/Polymarket_Monarch/tax_gate.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Why This File Exists At All

Monarch and the agent are separate projects in sibling folders, neither on the other's import path. Rather than scatter `sys.path` surgery and try/except imports through every scanner, the coupling lives here: one import, one failure mode, one place to change when either project moves.

## Fail-Open, Loudly - And Only Here

The agent's own hook is deliberately fail-CLOSED: if it cannot read the ledger it rejects the order, because a spending limit that silently stops limiting is worse than no limit. Monarch's scanners place no orders - they price hypothetical positions and print tables - so refusing to scan because an accounting database is missing would be absurd. This shim therefore falls back to the requested size when the agent is unavailable, and every consumer is required to print the `status_line()`, which says UNGATED in that case. If you ever wire this into something that actually sends an order, use `MonarchBankrollHook.check_order()` directly and honour its rejection instead. ================================================================================

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
