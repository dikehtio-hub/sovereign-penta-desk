---
type: Digest
title: Round 55 digest
description: 'Round 55: WATCHER PID LOCK, WATCHDOG GAVE UP BADGE'
tags:
- digest
- work-chain
- round-55
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:30Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS_ARCHIVE.md#round-55-complete
  title: AGENTS_ARCHIVE.md - Round 55 complete
  author: claude-code/fable-5.1
dev:
  round: 55
  date: null
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: ^Round 55 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 55 digest

> date not recorded in the log · compiled from `AGENTS_ARCHIVE.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

WATCHER PID LOCK, WATCHDOG GAVE UP BADGE. The Polymarket

watcher (--watch) takes a single-instance lock keyed to its drop folder
(<folder>/polymarket_watcher.pid, or --pid-file); dead / corrupt / not-a-
watcher pid files are swept, a live watcher makes the newcomer print
already_running and exit 0, orderly exits release (atexit + SIGINT/SIGTERM/
SIGBREAK). cross_market/ingestors/pid_lock.py mirrors the supervisor's
semantics without importing across trees, and its liveness probe never uses
os.kill(pid, 0). The read-only dashboard header shows a red WATCHDOG GAVE UP
badge (relaunch count, the launcher to run) while the Round 54 ceiling is
reached; it clears on service_back. The claim is an exclusive create, so two
starters that both saw a stale file cannot both run. Watcher restarted under
the lock and a second watcher proved to refuse. 8 new tests.

## Related

- [[digests_register|Digests register]]
