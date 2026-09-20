---
type: Digest
title: Round 70 digest
description: 'Round 70: OPTIONAL WRITE THROTTLE FOR HyperLiquid_Monarch.md'
tags:
- digest
- work-chain
- round-70
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-70-complete
  title: AGENTS_ARCHIVE.md - Round 70 complete
  author: claude-code/fable-5.1
dev:
  round: 70
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 70 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 70 digest

> date not recorded in the log · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

OPTIONAL WRITE THROTTLE FOR HyperLiquid_Monarch.md.

`main.py obsidian --watch --throttle-seconds N` (and the module CLI) skips
rewriting the market dashboard while its last write is younger than N
seconds, judged on the file's mtime so it holds across processes; every
other note and every number are untouched (Ruling 69-2: no coarsening).
Default 0 = unthrottled; the loop logs "(market dashboard throttled)".
1 new test.

## Related

- [[digests_register|Digests register]]
