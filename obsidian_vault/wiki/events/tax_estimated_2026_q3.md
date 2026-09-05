---
type: Event
title: 'Event: tax_estimated_2026_q3'
description: Estimated tax Q3 2026 due 2026-09-15.
tags:
- event
- estimated_tax
- desk-5
- deadline
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:27:23Z'
status: draft
stale_after: '2026-09-15T23:59:59Z'
sources:
- id: calendar
  resource: knowledge/calendars/tax_2026.yaml
  title: tax_2026.yaml
  author: human:operator
- id: tax-calendar-module
  resource: Tax_Reserve_Agent/interfaces/tax_calendar.py
  title: tax_calendar.py
dev:
  desk: 5
  kind: estimated_tax
  quarter: Q3
  tax_year: 2026
  period_start: '2026-06-01'
  period_end: '2026-08-31'
  due: '2026-09-15'
  calendar: knowledge/calendars/tax_2026.yaml
  asserts:
  - file: Tax_Reserve_Agent/interfaces/tax_calendar.py
    pattern: THE QUARTERS ARE NOT QUARTERS
    claim: the tax calendar module still documents the odd quarters
---
# Event: tax_estimated_2026_q3

> Federal estimated-tax payment Q3 for tax year 2026, due 2026-09-15.

## Period

- covers `2026-06-01` .. `2026-08-31` (3 months: the quarters are not quarters)
- due `2026-09-15`; this page goes stale at the deadline (lint L4) and is then deprecated

## What to do

- `python -m Tax_Reserve_Agent.main calendar` for the amount and the escrow release for this deadline

## Related

- [[events_register|Events register]]
- [[Desk_05_Tax_Reserve_Agent|Desk 5: Tax Reserve Agent]]
