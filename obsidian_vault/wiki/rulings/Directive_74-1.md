---
type: Ruling
title: 'Directive 74-1: cross_market/interfaces/obsidian_exporter.py holds cross_market/data/cross_market_exporter.pid
  for --watch (p…'
description: 'Directive 74-1: cross_market/interfaces/obsidian_exporter.py holds cross_market/data/cross_market_exporter.pid
  for --watch (pid_lock, mark word "cross_market" so a Sports Desk exporter never
  passes as the holder), --status (exit 0 running / 3 stopped; also prints the Item
  18 state: last lead-lag run'
tags:
- ruling
- directive
- round-74
- extracted
generated:
  by: claude-code/fable-5.1
  at: '2026-09-20T07:10:35Z'
status: stable
stale_after: '2027-03-05T00:28:46Z'
sources:
- id: agents-md
  resource: AGENTS_ARCHIVE.md
  title: AGENTS_ARCHIVE.md · AGENTS_ARCHIVE.md — Superseded Handoff History and Operational
    Archive
  author: human:operator
dev:
  round: 74
  ruling_id: D74-1
  kind: directive
  citations:
  - file: AGENTS_ARCHIVE.md
    section: AGENTS_ARCHIVE.md — Superseded Handoff History and Operational Archive
    line: 2086
    excerpt: '…Directive 74-1: cross_market/interfaces/obsidian_exporter.py holds
      cross_market/data/cross_market_exporter.pid for --watch (pid_lock, mark word
      "cross_market" so a Sports Desk exporter never passes as the holder), --status
      (exit 0 running / 3 stopped; also prints the Item 18 state: last lead-lag run
      from the Titans note, macro serie…'
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: Directive\s+74-1\b
    claim: the citation still exists in the handoff log
  ratified_by: 98-1
verified:
- by: antigravity/architect
  at: '2026-09-05T21:52:47Z'
---
# Directive 74-1

> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).

## Citations

- **AGENTS_ARCHIVE.md — Superseded Handoff History and Operational Archive** (`AGENTS_ARCHIVE.md` line 2086): …Directive 74-1: cross_market/interfaces/obsidian_exporter.py holds cross_market/data/cross_market_exporter.pid for --watch (pid_lock, mark word "cross_market" so a Sports Desk exporter never passes as the holder), --status (exit 0 running / 3 stopped; also prints the Item 18 state: last lead-lag run from the Titans note, macro serie…

## Related

- [[rulings_register|Rulings register]]
