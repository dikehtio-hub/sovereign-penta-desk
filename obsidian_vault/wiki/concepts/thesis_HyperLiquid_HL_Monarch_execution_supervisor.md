---
type: Concept
title: 'Thesis: HyperLiquid/HL_Monarch/execution/supervisor.py'
description: '`scheduleCancel` cancels EVERYTHING resting, across every strategy.
  If each executor armed its own switch, one strategy''s stalled heartbeat would cancel
  another strategy''s orders - and worse, a healthy strategy re-arming on its own
  timer would keep pushing the deadline out while …'
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
  resource: HyperLiquid/HL_Monarch/execution/supervisor.py
  title: HyperLiquid/HL_Monarch/execution/supervisor.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: HyperLiquid/HL_Monarch/execution/supervisor.py
  headings:
  - WHY OWNERSHIP MATTERS
  - THE PROTECTION IS THE DEADLINE, NOT THE HEARTBEAT
  - CANCELS ARE NEVER TAX-GATED
  - RENEWAL MARGIN
  asserts:
  - file: HyperLiquid/HL_Monarch/execution/supervisor.py
    pattern: WHY\ OWNERSHIP\ MATTERS
    claim: the docstring still carries the section 'WHY OWNERSHIP MATTERS'
  - file: HyperLiquid/HL_Monarch/execution/supervisor.py
    pattern: THE\ PROTECTION\ IS\ THE\ DEADLINE,\ NOT\ THE\ HEARTBEAT
    claim: the docstring still carries the section 'THE PROTECTION IS THE DEADLINE,
      NOT THE HEARTBEAT'
  - file: HyperLiquid/HL_Monarch/execution/supervisor.py
    pattern: CANCELS\ ARE\ NEVER\ TAX\-GATED
    claim: the docstring still carries the section 'CANCELS ARE NEVER TAX-GATED'
  - file: HyperLiquid/HL_Monarch/execution/supervisor.py
    pattern: RENEWAL\ MARGIN
    claim: the docstring still carries the section 'RENEWAL MARGIN'
  requires_files:
  - HyperLiquid/HL_Monarch/execution/supervisor.py
  desk: 1
---
# Thesis: HyperLiquid/HL_Monarch/execution/supervisor.py

> 4 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## Why Ownership Matters

`scheduleCancel` cancels EVERYTHING resting, across every strategy. If each executor armed its own switch, one strategy's stalled heartbeat would cancel another strategy's orders - and worse, a healthy strategy re-arming on its own timer would keep pushing the deadline out while the stalled one sat unprotected. One switch, one owner, one heartbeat.

## The Protection Is The Deadline, Not The Heartbeat

This is the property that makes the whole thing work: a supervisor that hangs, crashes, deadlocks, or loses its network stops re-arming, the deadline passes, and the EXCHANGE cancels the book without us. Every other design needs the dying process to notice it is dying and do something about it, which is exactly what a dying process cannot do.

 So the failure mode is deliberately asymmetric: * Supervisor healthy -> deadline keeps sliding forward, orders rest normally. * Supervisor stalls -> deadline passes, book is flattened, nothing is at risk. * Exchange unreachable-> arming fails, `armed` goes False, and `should_trade()` says no. We do not place new orders we cannot protect.

## Cancels Are Never Tax-Gated

`arm()` does not pass through `RiskManager`, and that is not an oversight: cancelling is risk-REDUCING, and an account that has exhausted its capital bucket is precisely the account that most needs to be able to flatten. Gating the exit behind the same check as the entry is how a risk limit becomes a trap.

## Renewal Margin

Re-arm at `ttl * renewal_fraction` (default a third). A 30s TTL renewed every 10s tolerates two consecutive failures before the book is cancelled; renewing at 28s means one slow round trip flattens everything. ================================================================================

## Related

- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]
- [[theses_register|Theses register]]
