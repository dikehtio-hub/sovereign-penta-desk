---
type: Concept
title: 'Thesis: Tax_Reserve_Agent/interfaces/receipts.py'
description: Two separate trading projects (Polymarket Monarch and HL Monarch) now
  write receipts, and the CSV contract - column order, tag format, filename shape
  - belongs to whoever ingests them. Duplicating the writer per bot is how the two
  drift until one of them silently stops being attr…
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
  resource: Tax_Reserve_Agent/interfaces/receipts.py
  title: Tax_Reserve_Agent/interfaces/receipts.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: Tax_Reserve_Agent/interfaces/receipts.py
  headings:
  - THIS LIVES IN THE TAX AGENT, NOT IN A BOT
  - NEVER RAISES
  asserts:
  - file: Tax_Reserve_Agent/interfaces/receipts.py
    pattern: THIS\ LIVES\ IN\ THE\ TAX\ AGENT,\ NOT\ IN\ A\ BOT
    claim: the docstring still carries the section 'THIS LIVES IN THE TAX AGENT, NOT
      IN A BOT'
  - file: Tax_Reserve_Agent/interfaces/receipts.py
    pattern: NEVER\ RAISES
    claim: the docstring still carries the section 'NEVER RAISES'
  requires_files:
  - Tax_Reserve_Agent/interfaces/receipts.py
  desk: 5
---
# Thesis: Tax_Reserve_Agent/interfaces/receipts.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## This Lives In The Tax Agent, Not In A Bot

Two separate trading projects (Polymarket Monarch and HL Monarch) now write receipts, and the CSV contract - column order, tag format, filename shape - belongs to whoever ingests them. Duplicating the writer per bot is how the two drift until one of them silently stops being attributed.

## Never Raises

A bookkeeping failure must not take down an execution path, so every problem is reported and swallowed. The caller gets None and can log it.

## Related

- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
- [[theses_register|Theses register]]
