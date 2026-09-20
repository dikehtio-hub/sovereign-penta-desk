---
type: Ruling
title: 'Directive 76-2: is implemented but INERT: collect_live_questions records every
  tag a market was fetched under in tags (list…'
description: 'Directive 76-2 is implemented but INERT: collect_live_questions records
  every tag a market was fetched under in `tags` (list, --tags order) while `sport`
  keeps the first tag''s label, so the matcher, Tier 1 and the registered Tier 2 filter
  read what they read before.…'
tags:
- ruling
- directive
- round-76
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
  round: 76
  ruling_id: D76-2
  kind: directive
  citations:
  - file: AGENTS_ARCHIVE.md
    section: AGENTS_ARCHIVE.md — Superseded Handoff History and Operational Archive
    line: 2053
    excerpt: '…Directive 76-2 is implemented but INERT: collect_live_questions records
      every tag a market was fetched under in `tags` (list, --tags order) while `sport`
      keeps the first tag''s label, so the matcher, Tier 1 and the registered Tier
      2 filter read what they read before.…'
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: Directive\s+76-2\b
    claim: the citation still exists in the handoff log
  ratified_by: 98-1
verified:
- by: antigravity/architect
  at: '2026-09-05T21:52:47Z'
---
# Directive 76-2

> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).

## Citations

- **AGENTS_ARCHIVE.md — Superseded Handoff History and Operational Archive** (`AGENTS_ARCHIVE.md` line 2053): …Directive 76-2 is implemented but INERT: collect_live_questions records every tag a market was fetched under in `tags` (list, --tags order) while `sport` keeps the first tag's label, so the matcher, Tier 1 and the registered Tier 2 filter read what they read before.…

## Related

- [[rulings_register|Rulings register]]
