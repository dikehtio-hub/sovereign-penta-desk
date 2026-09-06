---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/execution/wallet_manager.py'
description: Hyperliquid lets a main account authorise a separate "agent" key that
  can trade but CANNOT withdraw. That is the only key that should ever be in reach
  of this process. A compromised agent key costs you bad trades; a compromised main
  key costs you the account.
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
  resource: HyperLiquid/HL_Monarch/execution/wallet_manager.py
  title: HyperLiquid/HL_Monarch/execution/wallet_manager.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/execution/wallet_manager.py
  headings:
  - WHY AN AGENT WALLET
  - KEY HANDLING RULES ENFORCED HERE
  asserts:
  - file: HyperLiquid/HL_Monarch/execution/wallet_manager.py
    pattern: WHY\ AN\ AGENT\ WALLET
    claim: the docstring still carries the section 'WHY AN AGENT WALLET'
  - file: HyperLiquid/HL_Monarch/execution/wallet_manager.py
    pattern: KEY\ HANDLING\ RULES\ ENFORCED\ HERE
    claim: the docstring still carries the section 'KEY HANDLING RULES ENFORCED HERE'
  requires_files:
  - HyperLiquid/HL_Monarch/execution/wallet_manager.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/execution/wallet_manager.py

> 2 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Why An Agent Wallet

Hyperliquid lets a main account authorise a separate "agent" key that can trade but CANNOT withdraw. That is the only key that should ever be in reach of this process. A compromised agent key costs you bad trades; a compromised main key costs you the account.

## Key Handling Rules Enforced Here

* The key is read from the environment and never written anywhere - not to disk, not to logs, not into an exception message, not into a receipt. * `__repr__` and `__str__` return the ADDRESS only. A stack trace or a debugger that prints this object must not spill the key. * No accessor returns the raw key. If you need it, you have the environment. ================================================================================

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
