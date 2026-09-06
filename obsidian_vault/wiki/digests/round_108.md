---
type: Digest
title: Round 108 digest
description: 'Round 108 (2026-09-06): LINT L9 CLOSES THE HOLE ROUND 107 OPENED, AND
  THE DRILL CARD IS NOW COPY-PASTEABLE'
tags:
- digest
- work-chain
- round-108
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-108-complete
  title: AGENTS.md - Round 108 complete
  author: claude-code/fable-5.1
dev:
  round: 108
  date: '2026-09-06'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 108 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 108 digest

> 2026-09-06 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

LINT L9 CLOSES THE HOLE ROUND 107 OPENED, AND THE DRILL CARD

IS NOW COPY-PASTEABLE. L9 (Ruling R107-1.D): a wikilink whose only target is a git-ignored file
is an error - it lints clean locally and fails L8 on a FRESH CLONE, the worst shape of bug
because it is invisible to whoever introduces it. Blast radius audited read-only first: zero,
as expected, since Round 107 verified those three dashboards had no inbound links before
untracking them. R107-1.E: `dev.rules` is serialised into the registration's frontmatter and
the card reads it, so token ids print WHOLE - the card used to parse the rendered table, which
truncates them to 12 characters for readability, and an operator cannot paste `561528276087`.
R107-1.A: the post-print command is now exact and copy-pasteable. R107-1.B: an exact stem or
unambiguous prefix answers with one regime card; substring is the fallback and says when it is
ambiguous. Tests: knowledge 176 (+20), all green offline. Vault 423 pages, lint CLEAN.
NO DAEMON RESTARTED.

## Related

- [[digests_register|Digests register]]
