---
type: Ruling
title: 'Ratification 77-3: applied: Sports_Desk/ingestors/odds_fetcher.poll() no longer
  binds log=print at import (_emit resolves print…'
description: 'Ratification 77-3 applied: Sports_Desk/ingestors/odds_fetcher.poll()
  no longer binds `log=print` at import (`_emit` resolves print at call time); a tree-wide
  grep confirms no `= print` default remains outside tests.…'
tags:
- ruling
- ratification
- round-77
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
  round: 77
  ruling_id: R77-3
  kind: ratification
  citations:
  - file: AGENTS_ARCHIVE.md
    section: AGENTS_ARCHIVE.md — Superseded Handoff History and Operational Archive
    line: 2028
    excerpt: '…Ratification 77-3 applied: Sports_Desk/ingestors/odds_fetcher.poll()
      no longer binds `log=print` at import (`_emit` resolves print at call time);
      a tree-wide grep confirms no `= print` default remains outside tests.…'
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: Ratification\s+77-3\b
    claim: the citation still exists in the handoff log
  ratified_by: 98-1
verified:
- by: antigravity/architect
  at: '2026-09-05T21:52:47Z'
---
# Ratification 77-3

> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).

## Citations

- **AGENTS_ARCHIVE.md — Superseded Handoff History and Operational Archive** (`AGENTS_ARCHIVE.md` line 2028): …Ratification 77-3 applied: Sports_Desk/ingestors/odds_fetcher.poll() no longer binds `log=print` at import (`_emit` resolves print at call time); a tree-wide grep confirms no `= print` default remains outside tests.…

## Related

- [[rulings_register|Rulings register]]
