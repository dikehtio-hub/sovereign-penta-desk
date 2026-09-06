---
type: Concept
title: 'Thesis: Tax_Reserve_Agent/engine/lot_engine.py'
description: "Which open lot a sale consumes is a policy choice, set by `config.yaml\
  \ -> accounting.method`:\n\n FIFO Oldest lot first. The conservative default, and\
  \ the method the IRS assumes when no adequate identification was made. HIFO Highest\
  \ cost basis first - a form of specific identificat…"
tags:
- concept
- thesis
- desk-5
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:57:17Z'
status: draft
stale_after: '2026-12-05T00:57:17Z'
sources:
- id: module
  resource: Tax_Reserve_Agent/engine/lot_engine.py
  title: Tax_Reserve_Agent/engine/lot_engine.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Tax_Reserve_Agent/engine/lot_engine.py
  headings:
  - ACCOUNTING METHOD
  - SWITCHING METHODS DOES NOT REWRITE HISTORY
  asserts:
  - file: Tax_Reserve_Agent/engine/lot_engine.py
    pattern: ACCOUNTING\ METHOD
    claim: the docstring still carries the section 'ACCOUNTING METHOD'
  - file: Tax_Reserve_Agent/engine/lot_engine.py
    pattern: SWITCHING\ METHODS\ DOES\ NOT\ REWRITE\ HISTORY
    claim: the docstring still carries the section 'SWITCHING METHODS DOES NOT REWRITE
      HISTORY'
  requires_files:
  - Tax_Reserve_Agent/engine/lot_engine.py
  desk: 5
---
# Thesis: Tax_Reserve_Agent/engine/lot_engine.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Accounting Method

Which open lot a sale consumes is a policy choice, set by `config.yaml -> accounting.method`:

 FIFO Oldest lot first. The conservative default, and the method the IRS assumes when no adequate identification was made. HIFO Highest cost basis first - a form of specific identification that minimises the gain realised on each sale, and therefore the escrow. It is not free: consuming the expensive lot first tends to leave the CHEAP, OLD lots open, so it can convert what would have been long-term gains into short-term ones and simply defer tax rather than avoid it. Using it requires that you can actually identify the lots sold - keep this ledger as that record.

## Switching Methods Does Not Rewrite History

Lots already consumed stay consumed, so flipping the config mid-year leaves a ledger that is half one method and half the other - which is both wrong and not a position any method permits. The method the lots were built with is recorded in `agent_meta`, `calculate_tax_summary()` warns when it no longer matches the config, and `rebuild_lots()` (exposed as `python -m Tax_Reserve_Agent.main rebuild`) replays the whole ledger from the `transactions` table, which is the immutable source of truth.

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
- [[theses_register|Theses register]]
