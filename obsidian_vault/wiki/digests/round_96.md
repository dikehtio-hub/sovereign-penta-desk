---
type: Digest
title: Round 96 digest
description: 'Round 96 (2026-09-05): PHASE 1 - WIKI CONSTITUTION, SEED PAGES, MASTER
  MODULE 23 (Ratification R95-A..G)'
tags:
- digest
- work-chain
- round-96
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T07:43:40Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-96-complete
  title: AGENTS.md - Round 96 complete
  author: claude-code/fable-5.1
dev:
  round: 96
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  asserts:
  - file: AGENTS.md
    pattern: ^Round 96 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 96 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

PHASE 1 - WIKI CONSTITUTION, SEED PAGES, MASTER

MODULE 23 (Ratification R95-A..G). NEW obsidian_vault/WIKI_SCHEMA.md (the
constitution: layers and ownership, actors, OKF v0.2 frontmatter + dev:
namespace, page types and folders, reserved index.md/log.md formats, the two
DEV rules, ingest/query/journal/lint protocols, refusals). NEW package
knowledge/: frontmatter.py (parse/validate/serialize; type required; actor
regex; generated/verified/status/stale_after/sources; dev.asserts,
dev.parameters, dev.window), pages.py (write_page is the ONLY writer and
refuses anything outside wiki/ crm/ journal/ raw/ + WIKI_SCHEMA.md index.md
log.md, refuses reserved names and in-window pages; index/log builders and
parsers; wikilink extraction), lint.py (L1-L5, C1 copied-state drift via
declared dependents, C5 in-window mtime; CLI exit 0/1/3; writes nothing),
seed.py (parses the Top 20 registry blocks read-only; 5 Desk + 20 Item + 7
Ruling pages; skips existing pages unless --force; rebuilds index.md; appends
log.md). SEEDED the real vault: 32 pages, index.md, log.md; lint CLEAN.
Rulings catalogue is honest about the record: R2, R4, R6 carry commit
provenance and verified by antigravity/architect; R5 is draft (pending, named
by amm_rewards.py); R1 and R3 have NO text anywhere in the repo or git
history and are draft placeholders that say so; R95 records the seven
ratifications. Desk pages carry dev:parameters checked by C1 against their
owning files (lead-lag 0.20 bar and 5 min latency, quant-lab $3,500
killswitch and 1.0 % risk, tax 0.24 federal and 0.0637 NJ). Tests: module 23
= 42 (frontmatter, ownership, index/log, every lint code, seed parse/build/
idempotence/force/dry-run/HALT/no-write-outside); master suite 23 modules 978;
total 1,093 + 978 + 546 = 2,617, all green offline. Daemons and tonight's
tasks untouched; no dashboard, entity note or data folder written.

## Related

- [[digests_register|Digests register]]
