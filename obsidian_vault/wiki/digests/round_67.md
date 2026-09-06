---
type: Digest
title: Round 67 digest
description: 'Round 67: FEED LIVENESS IN THE Sports_Desk.md HEADER, SECTION CAP WITH
  OVERFLOW, KNOBS DOCUMENTED'
tags:
- digest
- work-chain
- round-67
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-67-complete
  title: AGENTS.md - Round 67 complete
  author: claude-code/fable-5.1
dev:
  round: 67
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 67 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 67 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

FEED LIVENESS IN THE Sports_Desk.md HEADER, SECTION CAP

WITH OVERFLOW, KNOBS DOCUMENTED. The Desk Snapshot callout carries
"**Feed Liveness**: `X ago` [ACTIVE|STALE]" (or `none` [NO QUOTES] /
`unavailable`), judged on the newest quote in the whole table against
FEED_STALE_SECONDS. The stale section shows at most 8 moves and 8 hits and
appends "*(and N more sharp move(s) / M more stale hit(s)... run
`monarch_shark --stale` for the full list)*" when more exist.
FEED_STALE_SECONDS (pipeline alive?) and MAX_QUOTE_AGE_SECONDS (quote
actionable?) are documented as separate knobs that share a value today.
2 new tests. Live note header: `15.7h ago` [STALE] - the sports feed is
deliberately idle until real odds drops arrive (Ruling 66-1).

## Related

- [[digests_register|Digests register]]
