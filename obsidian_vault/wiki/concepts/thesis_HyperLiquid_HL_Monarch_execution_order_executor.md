---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/execution/order_executor.py'
description: '`submit_fn` is None unless someone passes one, and this module contains
  no HTTP client, no URL and no socket. A signed payload is produced and returned;
  sending it is a separate act that has to be written deliberately. The signing constants
  are verified against the official SDK a…'
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
  resource: HyperLiquid/HL_Monarch/execution/order_executor.py
  title: HyperLiquid/HL_Monarch/execution/order_executor.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/execution/order_executor.py
  headings:
  - DRY RUN BY DEFAULT, AND THERE IS NO SUBMITTER
  - TWO LEGS, ONE SIZING DECISION
  asserts:
  - file: HyperLiquid/HL_Monarch/execution/order_executor.py
    pattern: DRY\ RUN\ BY\ DEFAULT,\ AND\ THERE\ IS\ NO\ SUBMITTER
    claim: the docstring still carries the section 'DRY RUN BY DEFAULT, AND THERE
      IS NO SUBMITTER'
  - file: HyperLiquid/HL_Monarch/execution/order_executor.py
    pattern: TWO\ LEGS,\ ONE\ SIZING\ DECISION
    claim: the docstring still carries the section 'TWO LEGS, ONE SIZING DECISION'
  requires_files:
  - HyperLiquid/HL_Monarch/execution/order_executor.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/execution/order_executor.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Dry Run By Default, And There Is No Submitter

`submit_fn` is None unless someone passes one, and this module contains no HTTP client, no URL and no socket. A signed payload is produced and returned; sending it is a separate act that has to be written deliberately. The signing constants are verified against the official SDK and pinned by a golden vector - see `wallet_manager.domain_verified()`.

## Two Legs, One Sizing Decision

`execute_basis_pair()` gates the WHOLE pair before either leg is placed, so the gate can never clamp one leg and leave the book directionally exposed. Both legs then use the same agreed size.

 What the gate cannot control is the fill. If one leg fills 0.1 and the other 0.04, the ledger is told 0.1 and 0.04 - never a tidy symmetric pair that did not happen, because a phantom hedge is worse than a visible gap nobody can miss. ================================================================================

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
