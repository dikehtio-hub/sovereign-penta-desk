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
  at: '2026-09-06T00:28:46Z'
status: stable
stale_after: '2027-03-05T00:28:46Z'
sources:
- id: agents-md
  resource: AGENTS.md
  title: AGENTS.md · Status
  author: human:operator
dev:
  round: 74
  ruling_id: D74-1
  kind: directive
  citations:
  - section: Status
    line: 366
    excerpt: '…Directive 74-1: cross_market/interfaces/obsidian_exporter.py holds
      cross_market/data/cross_market_exporter.pid for --watch (pid_lock, mark word
      "cross_market" so a Sports Desk exporter never passes as the holder), --status
      (exit 0 running / 3 stopped; also prints the Item 18 state: last lead-lag run
      from the Titans note, macro serie…'
  asserts:
  - file: AGENTS.md
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

- **Status** (line 366): …Directive 74-1: cross_market/interfaces/obsidian_exporter.py holds cross_market/data/cross_market_exporter.pid for --watch (pid_lock, mark word "cross_market" so a Sports Desk exporter never passes as the holder), --status (exit 0 running / 3 stopped; also prints the Item 18 state: last lead-lag run from the Titans note, macro serie…

## Related

- [[rulings_register|Rulings register]]
