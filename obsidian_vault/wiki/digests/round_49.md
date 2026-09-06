---
type: Digest
title: Round 49 digest
description: 'Round 49: DASHBOARD LIFECYCLE LOG, 2-HOUR STATUS WINDOW, PERPDEXS CHECK
  AT START-UP'
tags:
- digest
- work-chain
- round-49
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-49-complete
  title: AGENTS.md - Round 49 complete
  author: claude-code/fable-5.1
dev:
  round: 49
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 49 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 49 digest

> date not recorded in the log · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

DASHBOARD LIFECYCLE LOG, 2-HOUR STATUS WINDOW, PERPDEXS

CHECK AT START-UP. The dashboard appends start / stop / frame_error / crash
(with traceback) to `data/dashboard.jsonl`, so the next unexplained death has
a cause. `read_collector_status` trusts the collector's status file for two
hours by default (COLLECTOR_STATUS_MAX_AGE_SECONDS), so a dead collector's
last write cannot keep a NOVEL DEX badge alive. `_check_perp_dexs()` runs on
the collector's start-up (before the loops) and hourly, so the status file
exists from minute 0. hyna's future as a MIXED dex with its own allow-list is
ratified ahead of time. 2 new tests, 1 extended.

## Related

- [[digests_register|Digests register]]
