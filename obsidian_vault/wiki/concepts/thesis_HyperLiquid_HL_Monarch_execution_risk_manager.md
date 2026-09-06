---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/execution/risk_manager.py'
description: If the Tax Reserve Agent is missing, uninitialised, or broken, the bankroll
  half is unavailable - and this class then falls back to the paper balance and says
  so in `reason`, on every single decision. It does not pretend the check happened.
  A caller that wants to refuse trading w…
tags:
- concept
- thesis
- desk-1
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: HyperLiquid/HL_Monarch/execution/risk_manager.py
  title: HyperLiquid/HL_Monarch/execution/risk_manager.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/execution/risk_manager.py
  headings:
  - DEGRADES, BUT NEVER SILENTLY
  asserts:
  - file: HyperLiquid/HL_Monarch/execution/risk_manager.py
    pattern: DEGRADES,\ BUT\ NEVER\ SILENTLY
    claim: the docstring still carries the section 'DEGRADES, BUT NEVER SILENTLY'
  requires_files:
  - HyperLiquid/HL_Monarch/execution/risk_manager.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/execution/risk_manager.py

> 1 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Degrades, But Never Silently

If the Tax Reserve Agent is missing, uninitialised, or broken, the bankroll half is unavailable - and this class then falls back to the paper balance and says so in `reason`, on every single decision. It does not pretend the check happened. A caller that wants to refuse trading without the tax gate can test `tax_gate_available`.

 WHY FALL BACK AT ALL rather than fail closed: HL Monarch is a paper simulator today. Refusing to simulate because an accounting database is absent would stop research for no risk reduction. THE MOMENT THIS DRIVES REAL ORDERS, the fallback should become a refusal - see `require_tax_gate`. ================================================================================

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
