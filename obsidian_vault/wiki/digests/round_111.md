---
type: Digest
title: Round 111 digest
description: 'Round 111 (2026-09-06): THE QUERY LAYER CAN FILE AND COUNT, WITHOUT
  LOSING THE ONE PROPERTY THAT MAKES IT USABLE AT T-2'
tags:
- digest
- work-chain
- round-111
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-111-complete
  title: AGENTS_ARCHIVE.md - Round 111 complete
  author: claude-code/fable-5.1
dev:
  round: 111
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 111 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 111 digest

> 2026-09-06 · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

THE QUERY LAYER CAN FILE AND COUNT, WITHOUT LOSING THE ONE

PROPERTY THAT MAKES IT USABLE AT T-2. B16: `--file "<question>"` scaffolds a Concept page
recording the question and what was open when it was asked - never an invented answer - and
`--count-usage` records dev.usage on the pages a query opened. USAGE COUNTING IS OPT-IN, and
that is a correctness requirement, not a preference: write_page REFUSES a page inside its own
dev.window, so counting on every query would raise WriteRefused at T-2 on the FOMC Event page
and hand the operator a traceback instead of a briefing card. Even with the flag a windowed
page is skipped rather than attempted. R110-1.A: `description` joins the digests register
columns. R110-1.E: a truncated digest now warns durably in log.md, not only on stdout.
Tests: knowledge 233 (+21), all green offline. Vault 491 pages, lint CLEAN. NO DAEMON
RESTARTED.

## Related

- [[digests_register|Digests register]]
