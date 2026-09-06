---
type: Digest
title: Round 97 digest
description: 'Round 97 (2026-09-05): KNOWLEDGE PHASE 2 - CONSTITUTION RATIFIED, INGEST
  ADAPTERS, RAW MANIFEST, LINT C2/C3 (Antigravity rulings 1-13 on Round 96 applied)'
tags:
- digest
- work-chain
- round-97
generated:
  by: claude-code/fable-5.1
  at: '2026-09-06T08:12:49Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-97-complete
  title: AGENTS.md - Round 97 complete
  author: claude-code/fable-5.1
dev:
  round: 97
  date: '2026-09-05'
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 97 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 97 digest

> 2026-09-05 · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

KNOWLEDGE PHASE 2 - CONSTITUTION RATIFIED, INGEST

ADAPTERS, RAW MANIFEST, LINT C2/C3 (Antigravity rulings 1-13 on Round 96 applied).
WIKI_SCHEMA.md now carries verified: antigravity/architect and status stable
(ruling 8) and documents every change below. NEW knowledge/ingest/: experiments.py
(cross_market/experiments/*.json -> Experiment pages; bars become dev:parameters
addressed by json_path, rules tokens become dev:tokens, release-2m..+5m becomes
dev:window; maintains wiki/concepts/experiments_register.md so no Experiment is
an orphan), lead_lag.py (lead_lag --json -> verdict Experiment page + wiki/regimes/
btc_macro_regime.md with a dev:history row per verdict and a fixed class
vocabulary insufficient|no-lead|contemporaneous|polymarket-leads|hyperliquid-
leads|coincident; Tier 2 vs 2b disagreements listed, never resolved; PRIMED for
the Tier 1 verdict ~2026-09-06T01:39Z), clob.py (survival-curve --json -> one
Reaction Profile per market, the Event page, wiki/concepts/latency_decay.md cross-
event table; the per-second series is NOT copied; PRIMED for 2026-09-16). NEW
knowledge/raw_manifest.py -> raw/index.md (17 federated streams present, OKF index
lines relative to raw/, absent streams as `> not present` notes). LINT: C2 expired
tokens vs the newest macro+sports drops (warning; missing drops folder = one
warning), C3 same dev:parameters name with different values across pages (error;
kelly_fraction 0.25 now declared on Desks 2/3/5 and checked against
fair_value.py, latency_sniper.py, monarch_hook.py), C1 float-aware comparison +
dev:requires_files + json_path for JSON sources, C5 generated.at-in-window =
error / mtime-only = warning, constitution in scope for L1/L4/L5/C1 and exempt
from L2-listing/L3, nested index.md files validated. SEED: Item_04_Section_1256_
Futures_Tax_60_40 and Item_19_Multi_Desk_Monte_Carlo_Risk_Of_Ruin (old files git
rm'd), rulings verified.at = the ratifying commit instants (R4 17:15:05Z, R6
17:48:20Z, R2 18:13:11Z, R95 20:10:31Z), R1/R3 deprecated (never issued), --at
defaults to the registry mtime so --force is byte-idempotent, Desk 3 links the
compiled pages. REAL VAULT: 36 pages + constitution + raw/index.md, lint CLEAN.
Lint C1 fired on real data during the round: the Tier 2b registration has
min_points twice (readiness 200, bars 60) and a regex takes the first; hence
json_path. Tests: module 23 = 61; master 23 modules 997; total 1,093 + 997 + 546
= 2,636, all green offline. Daemons and tonight's tasks untouched.

## Related

- [[digests_register|Digests register]]
