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
  at: '2026-09-06T00:57:10Z'
status: stable
stale_after: '2027-03-05T00:28:46Z'
sources:
- id: agents-md
  resource: AGENTS.md
  title: AGENTS.md · Status
  author: human:operator
dev:
  round: 75
  ruling_id: D75-1
  kind: directive
  citations:
  - section: Status
    line: 372
    excerpt: '…`python -m cross_market.maiden_protocol` (exit 0 all checks / 3 not
      yet / 1 a check failed) runs Directive 75-1 (lock, READY, last run, the `lead-lag:
      RAN` log line, the run-at marker under the Item 18 header, the cooldown count-down)
      and, ONLY once Tier 1 has written its verdict, Directive 75-2 (both subfamilies
      under the registered bars, the meta file read, never written).…'
  - section: Round 75 findings
    line: 1288
    excerpt: …- **Directive 75-1's four steps are one command with exit codes**, so
      the 01:40Z check can be pasted by whoever is at the keyboard; Tier 2 cannot
      be run early by mistake - the protocol refuses until the run-at marker exists.
  asserts:
  - file: AGENTS.md
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

- **Status** (line 372): …`python -m cross_market.maiden_protocol` (exit 0 all checks / 3 not yet / 1 a check failed) runs Directive 75-1 (lock, READY, last run, the `lead-lag: RAN` log line, the run-at marker under the Item 18 header, the cooldown count-down) and, ONLY once Tier 1 has written its verdict, Directive 75-2 (both subfamilies under the registered bars, the meta file read, never written).…
- **Round 75 findings** (line 1288): …- **Directive 75-1's four steps are one command with exit codes**, so the 01:40Z check can be pasted by whoever is at the keyboard; Tier 2 cannot be run early by mistake - the protocol refuses until the run-at marker exists.

## Related

- [[rulings_register|Rulings register]]
