---
type: Ruling
title: 'Ruling 79-3: applied: poll('
description: 'Ruling 79-3 applied: poll() in both fetchers defaults `sleep` to a call-time
  `_sleep` helper (as `log` defaults to `_emit`); a tree-wide grep outside tests finds
  no `= time.sleep` or `= print` default left.…'
tags:
- ruling
- ruling
- round-79
- extracted
generated:
  by: claude-code/fable-5.1
  at: '2026-09-05T21:32:39Z'
status: draft
sources:
- id: agents-md
  resource: AGENTS.md
  title: AGENTS.md · Status
  author: human:operator
dev:
  round: 79
  ruling_id: R79-3
  kind: ruling
  citations:
  - section: Status
    line: 239
    excerpt: '…Ruling 79-3 applied: poll() in both fetchers defaults `sleep` to a
      call-time `_sleep` helper (as `log` defaults to `_emit`); a tree-wide grep outside
      tests finds no `= time.sleep` or `= print` default left.…'
  asserts:
  - file: AGENTS.md
    pattern: Ruling\s+79-3\b
    claim: the citation still exists in the handoff log
---
# Ruling 79-3

> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).

## Citations

- **Status** (line 239): …Ruling 79-3 applied: poll() in both fetchers defaults `sleep` to a call-time `_sleep` helper (as `log` defaults to `_emit`); a tree-wide grep outside tests finds no `= time.sleep` or `= print` default left.…

## Related

- [[rulings_register|Rulings register]]
