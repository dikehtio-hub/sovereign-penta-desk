---
type: Concept
title: 'Thesis: cross_market/interfaces/c2_bot.py'
description: 'One detached loop that long-polls Telegram (outbound HTTPS only - no
  inbound port, no webhook on a laptop) and answers five commands from an allowlist
  of admin user ids: /status, /bankroll, /positions, /halt (alias /killall) and /help.'
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
  resource: cross_market/interfaces/c2_bot.py
  title: cross_market/interfaces/c2_bot.py module docstring
  author: human:operator
dev:
  kind: thesis
  module: cross_market/interfaces/c2_bot.py
  headings:
  - WHAT IT IS
  - WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS
  - THE NETWORK IS ONE INJECTABLE CALLABLE
  asserts:
  - file: cross_market/interfaces/c2_bot.py
    pattern: WHAT\ IT\ IS
    claim: the docstring still carries the section 'WHAT IT IS'
  - file: cross_market/interfaces/c2_bot.py
    pattern: WHAT\ IT\ REFUSES,\ FAIL\-CLOSED\ ON\ EVERY\ AXIS
    claim: the docstring still carries the section 'WHAT IT REFUSES, FAIL-CLOSED ON
      EVERY AXIS'
  - file: cross_market/interfaces/c2_bot.py
    pattern: THE\ NETWORK\ IS\ ONE\ INJECTABLE\ CALLABLE
    claim: the docstring still carries the section 'THE NETWORK IS ONE INJECTABLE
      CALLABLE'
  requires_files:
  - cross_market/interfaces/c2_bot.py
  desk: 3
---
# Thesis: cross_market/interfaces/c2_bot.py

> 3 titled section(s) compiled from the module docstring; each heading is pinned to the source (lint C1).

## What It Is

One detached loop that long-polls Telegram (outbound HTTPS only - no inbound port, no webhook on a laptop) and answers five commands from an allowlist of admin user ids: /status, /bankroll, /positions, /halt (alias /killall) and /help.

## What It Refuses, Fail-Closed On Every Axis

No token or no allowlist: it does not start. A message from a group chat, from an unlisted user, or older than STALE_UPDATE_SECONDS (a restart must never replay a /halt sent hours ago) is logged and never answered. /resume is console-only. The only thing it can change on the machine is the HALT.flag sentinel that HL_Monarch's dynamic config already reads as the emergency kill switch; it never terminates a process - the data daemons hold no risk and killing them breaks the stamped series.

## The Network Is One Injectable Callable

`http(method, params) -> dict` is the whole surface; tests pass a fake and never open a socket. The bot token is never printed, logged or echoed: `redact` scrubs it from anything that could carry it, and --status reports only "set" / "unset".

## Related

- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]
- [[theses_register|Theses register]]
