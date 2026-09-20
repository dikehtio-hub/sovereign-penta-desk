---
type: Ruling
title: 'Directive 75-1: python -m cross_market.maiden_protocol (exit 0 all checks
  / 3 not yet / 1 a check failed) runs (lock, READY…'
description: '`python -m cross_market.maiden_protocol` (exit 0 all checks / 3 not
  yet / 1 a check failed) runs Directive 75-1 (lock, READY, last run, the `lead-lag:
  RAN` log line, the run-at marker under the Item 18 header, the cooldown count-down)
  and, ONLY once Tier 1 has written its verdict, Directive 75-2 (bo'
tags:
- ruling
- directive
- round-75
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
  round: 75
  ruling_id: D75-1
  kind: directive
  citations:
  - file: AGENTS_ARCHIVE.md
    section: AGENTS_ARCHIVE.md — Superseded Handoff History and Operational Archive
    line: 2067
    excerpt: '…`python -m cross_market.maiden_protocol` (exit 0 all checks / 3 not
      yet / 1 a check failed) runs Directive 75-1 (lock, READY, last run, the `lead-lag:
      RAN` log line, the run-at marker under the Item 18 header, the cooldown count-down)
      and, ONLY once Tier 1 has written its verdict, Directive 75-2 (both subfamilies
      under the registered bars, the meta file read, never written).…'
  - file: AGENTS_ARCHIVE.md
    section: Round 75 findings
    line: 3883
    excerpt: …- **Directive 75-1's four steps are one command with exit codes**, so
      the 01:40Z check can be pasted by whoever is at the keyboard; Tier 2 cannot
      be run early by mistake - the protocol refuses until the run-at marker exists.
  asserts:
  - file: AGENTS_ARCHIVE.md
    pattern: Directive\s+75-1\b
    claim: the citation still exists in the handoff log
  ratified_by: 98-1
verified:
- by: antigravity/architect
  at: '2026-09-05T21:52:47Z'
---
# Directive 75-1

> Extracted from the handoff log by number; `status: draft` until Antigravity ratifies the text (R95-D).

## Citations

- **AGENTS_ARCHIVE.md — Superseded Handoff History and Operational Archive** (`AGENTS_ARCHIVE.md` line 2067): …`python -m cross_market.maiden_protocol` (exit 0 all checks / 3 not yet / 1 a check failed) runs Directive 75-1 (lock, READY, last run, the `lead-lag: RAN` log line, the run-at marker under the Item 18 header, the cooldown count-down) and, ONLY once Tier 1 has written its verdict, Directive 75-2 (both subfamilies under the registered bars, the meta file read, never written).…
- **Round 75 findings** (`AGENTS_ARCHIVE.md` line 3883): …- **Directive 75-1's four steps are one command with exit codes**, so the 01:40Z check can be pasted by whoever is at the keyboard; Tier 2 cannot be run early by mistake - the protocol refuses until the run-at marker exists.

## Related

- [[rulings_register|Rulings register]]
