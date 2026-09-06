---
type: Ruling
title: 'Directive 79-2: three manual steps are now restart_polymarket_watcher.bat:
  fetcher --stop (terminates ONLY a live lock holder…'
description: 'Directive 79-2''s three manual steps are now `restart_polymarket_watcher.bat`:
  fetcher `--stop` (terminates ONLY a live lock holder whose command line is a watcher
  - a stale lock is swept, a foreign process is never a target; exit 0 stopped / 1
  still alive / 3 nothing running) -> the guarded launcher'
tags:
- ruling
- directive
- round-79
- extracted
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T00:28:46Z'
status: stable
stale_after: '2027-03-05T00:28:46Z'
sources:
- id: agents-md
  resource: AGENTS.md
  title: AGENTS.md · Status
  author: human:operator
dev:
  round: 79
  ruling_id: D79-2
  kind: directive
  citations:
  - section: Status
    line: 295
    excerpt: '…Directive 79-2''s three manual steps are now `restart_polymarket_watcher.bat`:
      fetcher `--stop` (terminates ONLY a live lock holder whose command line is a
      watcher - a stale lock is swept, a foreign process is never a target; exit 0
      stopped / 1 still alive / 3 nothing running) -> the guarded launcher -> `--status`,
      whose new "tags:"…'
  - section: Status
    line: 295
    excerpt: …a foreign process is never a target; exit 0 stopped / 1 still alive
      / 3 nothing running) -> the guarded launcher -> `--status`, whose new "tags:"
      line says whether the newest macro stamp carries the Round 76 `tags` (the Directive
      79-2 verification, one command).…
  asserts:
  - file: AGENTS.md
    pattern: Directive\s+79-2\b
    claim: the citation still exists in the handoff log
  ratified_by: 98-1
verified:
- by: antigravity/architect
  at: '2026-09-05T21:52:47Z'
---
# Directive 79-2

> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).

## Citations

- **Status** (line 295): …Directive 79-2's three manual steps are now `restart_polymarket_watcher.bat`: fetcher `--stop` (terminates ONLY a live lock holder whose command line is a watcher - a stale lock is swept, a foreign process is never a target; exit 0 stopped / 1 still alive / 3 nothing running) -> the guarded launcher -> `--status`, whose new "tags:"…
- **Status** (line 295): …a foreign process is never a target; exit 0 stopped / 1 still alive / 3 nothing running) -> the guarded launcher -> `--status`, whose new "tags:" line says whether the newest macro stamp carries the Round 76 `tags` (the Directive 79-2 verification, one command).…

## Related

- [[rulings_register|Rulings register]]
