---
type: Digest
title: Round 36 digest
description: 'Round 36: READ-ONLY DASHBOARD, POSITION-FIRST SAMPLING & REPO CLEANUP'
tags:
- digest
- work-chain
- round-36
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:15:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-36-complete
  title: AGENTS.md - Round 36 complete
  author: claude-code/fable-5.1
dev:
  round: 36
  date: null
  kind: round_digest
---
# Round 36 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

READ-ONLY DASHBOARD, POSITION-FIRST SAMPLING & REPO CLEANUP.

`main.py dashboard` no longer starts a collector while a service collector is
alive (Ruling 3.A) - it is a read-only viewer with a live header badge, and
falls back to standalone ingestion only when no service exists. Held basis
positions are sampled first. Runtime `.pid` / `.jsonl` files are untracked and
ignored; Antigravity's Trading Terminal note change is committed (4af4f51).
8 new tests.

## Related

- [[digests_register|Digests register]]
