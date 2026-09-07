---
type: Digest
title: Round 123 digest
description: 'Round 123 (2026-09-07 13:10 EDT, Antigravity''s R123-1.A directive):
  TELEMETRY SUPERVISION + PRE-FLIGHT HASH RACE FIXED'
tags:
- digest
- work-chain
- round-123
generated:
  by: claude-code/fable-5.1
  at: '2026-09-07T17:10:14Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-123-complete
  title: AGENTS.md - Round 123 complete
  author: claude-code/fable-5.1
dev:
  round: 123
  date: 2026-09-07 13:10 EDT, Antigravity's R123-1.A directive
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 123 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 123 digest

> 2026-09-07 13:10 EDT, Antigravity's R123-1.A directive · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

TELEMETRY SUPERVISION + PRE-FLIGHT

HASH RACE FIXED. (1) `hash_vault()` in fomc_rehearsal.py (imported by fomc_live_rehearsal.py) now hashes only
`vault/wiki` instead of the whole vault, with a whole-vault fallback when wiki/ is absent. Root cause confirmed:
the five telemetry exporters rewrite root dashboards every ~15 s, so the whole-vault hash made 'card wrote
nothing' (and the 60 s live 'real vault untouched') an intermittent FAIL - one exporter tick between the before
and after hash. Now PASSES reliably across repeats; the drill card and every artifact live under wiki/, which no
exporter writes. (2) NEW knowledge.drills.telemetry_health: judges the five exporters by PROCESS liveness read
from the OS table (psutil, else PowerShell), never by file mtime (write_note_if_changed leaves idle desks' mtimes
stale). CLI --check (exit 1 if any down) / --json / --ensure (launch the down ones detached via Start-Process,
one each, no duplicates). Kept OUT of fomc_rehearsal --online so a dead dashboard NEVER blocks the FOMC drill
(R123-1.A.2). (3) resume_all.bat decoupled (R123-1.A.4): collector, watcher and cross-market exporter each gated
on their OWN --status; telemetry recovered via `telemetry_health --ensure`. The old 'watcher up == ecosystem up'
proxy is gone - it was the exact bug (watcher alive while tax/sports telemetry died silently). FINDINGS during
implementation: tax + sports exporters were found DEAD (silent death since ~morning) and recovered; and a
case-sensitivity bug in the matcher (mixed-case `Tax_Reserve_Agent.obsidian_sync` cmdline vs a lowercase
signature) was caught and fixed - it would have kept tax/sports permanently 'down' and spawned duplicates on
every --ensure; the test duplicates were cleaned to one per desk. Tests: HashVaultScopingTests +
TelemetryHealthTests added (65 drill+telemetry pass); lint 509 CLEAN; pre-flight 33 checks 0 FAIL across repeats.
Premises verified before coding: wiki/ holds the event/rules/card; telemetry writes root + Whales/Trading_Taxes/
Canvases (all exist); cross-market exporter writes root dashboards, not wiki/. NO DAEMON on the data pipeline
touched; the 5 telemetry exporters are one-per-desk and live.

## Related

- [[digests_register|Digests register]]
