---
type: Constitution
title: WIKI_SCHEMA - the knowledge layer constitution
description: How the DEV trading wiki is laid out, what a page must carry, who may write where, and the ingest, query, journal and lint protocols an agent follows. Ratified R95-A to R95-G.
tags: [constitution, schema, okf, round-96]
generated:
  by: claude-code/fable-5.1
  at: 2026-09-05T20:45:00Z
verified:
  - by: antigravity/architect
    at: 2026-09-05T20:30:00Z   # Round 97 ruling 8: the constitution TEXT was read and approved
  - by: antigravity/architect
    at: 2026-09-06T07:15:00Z   # Round 108: s.7 lint table amended with L8 and L9 verified & ratified
  - by: antigravity/architect
    at: 2026-09-06T07:40:00Z   # Round 109: s.4 page types amended with Digest verified & ratified
status: stable
sources:
  - id: round-95-blueprint
    resource: LLM_WIKI_BLUEPRINT.md
    title: Round 95 blueprint (ratified R95-A..G)
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format SPEC.md v0.2
  - id: karpathy-llm-wiki
    resource: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
    title: llm-wiki (gist)
dev:
  round: 97
  ruling_ids: [R95-A, R95-B, R95-C, R95-D, R95-E, R95-F, R95-G, R96-1, R96-2, R96-3, R96-4, R96-5, R96-6, R96-7, R96-8, R96-9, R96-10, R96-11, R96-12, R96-13]
---

# WIKI_SCHEMA: the knowledge layer constitution

This file is authoritative for everything under `obsidian_vault/wiki/`,
`crm/`, `journal/` and `raw/` and for `index.md` and `log.md` (Ruling
R95-B). `AGENTS.md` stays the operational handoff log. Where this file and a
habit disagree, this file wins; where this file and a ratified Ruling page
disagree, the Ruling wins and this file is amended in the next round.

An agent opening this vault reads this file first, then `index.md`, then the
pages the index names. It never reads a dashboard to learn a rule.

## 1. Three layers and who owns what

| Layer | Where | Owner | Rule |
|---|---|---|---|
| raw (immutable truth) | the desk `data/` folders, stamped drops, CLOB books, SQLite, `*.meta.json`; plus `obsidian_vault/raw/` for human-authored sources (statements, memos, post-mortems) | the daemons; the operator | read-only for every agent. Federated in place (R95-A): nothing is copied or moved. `raw/index.md` is the manifest of every raw stream by path and schema. |
| wiki (compiled) | `wiki/`, `crm/`, `journal/` | the knowledge agent, through `knowledge.pages.write_page` | every file carries OKF frontmatter; every claim names its source; no mutable value is copied (s.6). |
| schema (constitution) | this file | the operator and Antigravity | amended only between rounds, never inside an event window. |

**Exporter property, never written by the knowledge layer**: the root
dashboards (`Monarch_Hub.md`, `Cross_Market_Titans.md`, `Risk_Sentinel.md`
and the rest), `Whales/`, `Wallets/`, `Trading_Taxes/`, `Canvases/`. The
package refuses those paths by construction (`WriteRefused`). Dashboards may
link INTO the wiki (Phase 4, a one-line exporter change per desk, ratified
separately); the wiki links into dashboards freely.

## 2. Actors

OKF actor strings, used in `generated.by`, `verified[].by` and
`sources[].author`:

| Actor | String | Meaning |
|---|---|---|
| Claude Code | `claude-code/fable-5.1` | compiled or generated the page |
| Antigravity | `antigravity/architect` | ratified; the only actor allowed in `verified` on Ruling, Directive and parameter pages (R95-D) |
| the operator | `human:operator` | hand-authored or hand-verified |
| a daemon or CLI | `process:<module>` e.g. `process:cross_market.lead_lag` | machine-produced source |

An agent never appends `verified` to a page it generated. `verified` on a
Ruling page means Antigravity ratified the text; on any other page it means
a human checked it.

## 3. Frontmatter contract (OKF v0.2 + `dev:`)

Every non-reserved `.md` under the owned folders starts with a YAML block.

- **Required**: `type` (a short string from the vocabulary in s.4; OKF
  consumers must not reject unknown types, so new types may be added here).
- **Recommended**: `title`, `description` (one sentence; it becomes the
  index line), `tags` (list of strings), `resource` (a URI, for pages bound
  to one asset such as a market token).
- **Trust**: `generated {by, at}`; `verified` (one mapping or a list of
  `{by, at}`).
- **Lifecycle**: `status` in `draft | stable | deprecated` (absent means
  stable); `stale_after` (ISO 8601 instant after which lint L4 asks for a
  review).
- **Provenance**: `sources`, a list; each entry REQUIRES `resource` (a path
  relative to the DEV root, a `file://` URI, `git:<sha>`, or an https URL)
  and may carry `id`, `title`, `author`, `last_modified`.
- **DEV namespace** `dev:` (all optional): `desk` (1-5), `item` (1-20),
  `round`, `ruling_id`, `tier`, `registry_checked`, `supersedes`,
  `asserts`, `parameters`, `requires_files`, `window`, `token_id`,
  `tokens`, `history`, `evidence`.

```yaml
---
type: Ruling
title: R4 - neg_risk books skip the NO side
description: On a negative-risk Polymarket book only the winning outcome's YES asks are lifted.
tags: [ruling, desk-3, r4]
generated: {by: claude-code/fable-5.1, at: 2026-09-05T20:00:00Z}
verified:
  - {by: antigravity/architect, at: 2026-09-05T20:00:00Z}
status: stable
sources:
  - {id: commit-da48cf3, resource: "git:da48cf3", title: commit da48cf3}
dev:
  desk: 3
  ruling_id: R4
  asserts:
    - {file: cross_market/latency_sniper.py, pattern: neg_risk, claim: the field is read and acted on}
---
```

`dev.asserts[]` = `{file, pattern, claim}`: the page claims something about
a source file and names the regex that must still match (lint C1).
`dev.parameters[]` = `{name, value, file, pattern | json_path}`: the page
states a number; the regex's first group, or the value at the dotted
`json_path` when the owning file is JSON, must still equal it (lint C1). Use
`json_path` for JSON sources: the same key can occur in several blocks (the
Tier 2b registration has `series.readiness.min_points` 200 and
`bars.min_points` 60). Values compare as floats when both sides parse as numbers after
stripping commas, `$` and spaces, else as normalised strings (Round 97
ruling 2). The same `name` on two pages must carry the same value (lint C3):
`kelly_fraction` is declared on Desks 2, 3 and 5 for exactly that reason.
`dev.requires_files[]`: paths that must exist (lint C1); the Phase 1 idiom
of an assert with pattern `.` is retired (ruling 10).
`dev.window` = `{start, end}`: a registration window; the page may not be
written inside it (`write_page` refuses; lint C5 reports).
`dev.token_id` / `dev.tokens[]`: Polymarket YES token ids the page is bound
to; lint C2 checks them against the newest drops.
`dev.history[]`: machine-managed rows on Regime and Concept pages (one per
verdict or per event x market); the body table is rendered from it, never
hand-edited.

## 4. Page types and folders

| `type` | Folder | Compiled from |
|---|---|---|
| Desk | wiki/desks | the Round 95 audit; registry; module docstrings |
| Item | wiki/items | the Top 20 registry (`MASTER_COMMAND_LIST.txt` lines 80-484) |
| Ruling | wiki/rulings | rulings, directives and ratifications; `verified` by Antigravity |
| Experiment | wiki/experiments | `*.meta.json` pre-registrations, later the verdict JSON |
| Event | wiki/events | a rules file + statement text + drill log |
| Reaction Profile | wiki/profiles | `latency_sniper --survival-curve --json` |
| Regime | wiki/regimes | Tier 1/2/2b verdict pages |
| Market | wiki/markets | the newest macro or sports drop record |
| Concept | wiki/concepts | docstring theses, YAML rationale, filed answers |
| Digest | wiki/digests | one round of the sovereign work chain (`AGENTS.md`) |
| Source Summary | wiki/sources | one per raw source ingested |
| Attested Computation | wiki/computations | every dashboard "Shell twin"; declarative only (R95-C) |
| Entity/Whale, Entity/Sharp Trader, Entity/Titan, Entity/Sportsbook, Entity/Market Maker, Entity/Official, Contact | crm/whales, crm/sharps, crm/titans, crm/books, crm/makers, crm/officials, crm/contacts | databases, the identity cache, edge_opportunities, book Q, humans |
| Journal Entry, Debrief | journal, journal/debriefs | receipts, Risk Sentinel state, escrow note, the operator's plan |
| Lint Report | wiki/lint | `knowledge.lint --json` |
| Blueprint, Constitution | wiki/concepts, vault root | this layer's own design documents |
| Register (a Concept) | wiki/concepts/*_register.md | machine-maintained lists of every page of one compiled type (experiments, rulings, computations, events, markets, crm, journal, theses); every Desk page links every register, so nothing compiled is an orphan; hand edits are overwritten |
| Thesis (a Concept) | wiki/concepts/thesis_*.md | the titled ALL-CAPS sections of a desk module's docstring, each heading pinned with `dev.asserts` so a silent deletion is a lint C1 finding (Round 101, B12) |
| tooling, not pages | wiki/_views/*.base, wiki/_templates/*.md | Obsidian Bases views and human page templates; any folder whose name starts with `_` is skipped by the index and by lint |

File names are `Type_NN_Slug.md` for numbered things (`Desk_03_Cross_Market_Desk.md`,
`Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper.md`, `Ruling_R04.md`),
dated `YYYY-MM-DD.md` for journal and lint pages, and the address for
entities (`crm/whales/0x004e...1bb8.md`).

## 5. Reserved files (OKF sections 8-9, adopted verbatim)

`index.md`, at the vault root, no frontmatter, one section per type in the
order of s.4, one line per page:

```
# Ruling
* [R4 - neg_risk books skip the NO side](wiki/rulings/Ruling_R04.md) - On a negative-risk book only the winning outcome's YES asks are lifted.
```

`log.md`, at the vault root, no frontmatter, newest day first, append-only,
written only by `knowledge.pages.append_log`:

```
## 2026-09-05
* **Seed**: Round 96 seed from the Top 20 registry: 32 page(s) written; [index](index.md) rebuilt.
```

A human edit to `log.md` is a lint error. `index.md` is regenerated, never
hand-edited. A nested `index.md` (OKF allows one per folder) follows the same
grammar; `raw/index.md` is the manifest of federated raw streams, with paths
relative to `raw/`, and may carry `> note` lines for streams that are
expected but not present on the current machine.

## 6. The two DEV rules on top of OKF

**No copied mutable state.** A wiki page never quotes a PID, a row count, a
last-synced time, a live price or a live balance. Those belong to
dashboards. A page that must state a number declares it under
`dev.parameters` with the file and regex that own it. "A quote without its
dependent named is a copy waiting to go stale with nothing watching it."

**Verification is a human or Antigravity act.** `generated.by` is whoever
wrote the page. `verified` is appended by `human:operator` or by
`antigravity/architect`, never by the generating agent.

## 7. Protocols

### Ingest

1. Read the raw source. Discuss the takeaways with the operator when the
   source is human-authored; compile silently when it is machine output
   consumed by an adapter.
2. Write or update the Source Summary page (`sources[0]` points at the raw
   artifact).
3. Touch every Entity, Concept, Event, Regime and Desk page the source bears
   on. One source may touch 10-15 pages. Never overwrite a page's judgement
   text; append evidence and revise the synthesis paragraph.
4. Append one bullet to `log.md` (`**Ingest**`), regenerate `index.md`.
5. Run lint. A red lint blocks the commit.

### Query

Read `index.md` first, open the pages it names, answer with `[[wikilinks]]`
to pages and `sources` to raw. File the answer as a Concept page when the
operator says "keep that". Two queries are pre-baked as commands in Phase 2:
`--drill-card <event>` (one page under 60 lines at T-2) and `--regime BTC`.

### Journal (R95-F; built Round 100, B10)

`python -m knowledge.journal --date D` writes `journal/YYYY-MM-DD.md` when
paper receipts exist for that day, or on `--create`. Five sections: **Plan**
(human, preserved across re-runs like a CRM judgement), **Executions**
(machine: every CSV receipt under `cross_market/data/paper_receipts/`, one
row per fill with notional = quantity x price and the `edge:` / `hurdle:`
the writer stamped into `notes`, Ruling 100-b), **Calibration ledger**
(machine-managed rows from `dev.predictions`), **Debrief** (machine: the
day's **Daily Paper Notional Turnover** with the quant lab's killswitch as a
reference only, because the killswitch is a realised-loss budget and fills
are not realised loss, so the drawdown check is UNCHECKED until paired
closes exist, Ruling 100-c; the after-tax hurdle check per fill is PASS when
edge >= hurdle, FLAG below it, UNCHECKED when the receipt carries neither),
**Open** (human, preserved). Journal pages are never stale.

**Calibration ledger.** `--predict --event E --field F --op OP --value V --p P`
records a mechanical prediction BEFORE an event (`by: human:operator`);
`--predict --event E --claim "..." --p P` records a free-text one (Ruling
100-a). `--score` resolves every unscored mechanical prediction against the
Event page's `dev.payload` (written by the recording adapter after the
print): outcome = 1 if `F OP V` holds. A free-text claim is scored only by
hand: `--score --event E --outcome 0|1`, recorded as `scored_by:
human:operator`. Brier = (p - outcome)^2. `wiki/concepts/calibration.md`
aggregates every scored prediction: count, mean Brier (0.25 is the
always-0.5 baseline), and a reliability table by probability bin. A
prediction is never edited after it is written; a wrong one stays wrong.

### Typed relations (Round 100, B11)

`dev.relations: [{type, target}]` with `type` in `supersedes | contradicts |
resolved_by | depends_on | measured_by | enforced_in`. Targets are page stems,
or a repository path for `enforced_in`. Lint L6: a `supersedes` target must
exist and be `deprecated`, chains must be acyclic; a `contradicts` must be
accompanied by `resolved_by` naming an existing Ruling page (a contradiction
is owed a ruling); `measured_by` must name an Experiment page; `enforced_in`
must name a file that exists.

### Staleness policy (Round 100, B14)

| Type | stale_after | Why |
|---|---|---|
| Ruling | 180 days from generation | the law is reviewed twice a year |
| Concept | 90 days | a synthesis is re-read each quarter |
| Market | none: lint C2 deprecates it when the token leaves the drops | resolution is the clock |
| Reaction Profile, Event, Journal Entry | never | historical facts |
| Registers and history pages (`dev.register_for`, `dev.history`) | exempt | regenerated wholesale |

Lint L7 warns when a policed page lacks `stale_after`; lint L4 warns once it
has passed. `dev.tests_run` on Experiment pages counts how many times a
registration's scope has been evaluated (0 at registration; each verdict
page carries the running count), so multiple testing is visible.

### CRM (Round 99, B8)

A `crm/` page is a compiled judgement about a counterparty, never a metrics
mirror: the exporter-owned `Whales/` and `Wallets/` notes keep the live
numbers and the CRM page links to them. Every CRM page has three parts:
**Identity** (addresses, pseudonym, how the identity was resolved),
**Judgement** (human-written; the adapter never touches it) and **Evidence**
(dated rows the adapter appends, one per distinct scan time, newest 50 kept).
Re-ingest also preserves `verified`, `stale_after` and any status a human
promoted past `draft`. A Titan is a cached EOA-to-proxy identity that ALSO
appears in the whale table or as a sharp trader's resolved EOA; the cache
alone (1,685 pairs) is not a titan. Whales are the top N by account equity.
Databases are opened `file:...?mode=ro`, always.

### Ratification

`python -m knowledge.ratify --type T [--tag TAG] --ruling N-N` records an
Antigravity ratification: it appends `{by: antigravity/architect, at}` to
`verified`, sets `status: stable`, writes `dev.ratified_by`, rebuilds the
type's register and logs one `**Ratify**` bullet. It is the only way an
agent writes a `verified` entry, and the entry names a ruling.

### Lint

`python -m knowledge.lint [--json]` (exit 0 clean, 1 findings, 3 refused).

| Code | Check |
|---|---|
| L1 | frontmatter parses; `type` present; OKF shapes hold. The constitution is in scope (ruling 5) |
| L2 | root `index.md` / `log.md` on the reserved formats; index paths exist; every page listed (the constitution is not a page); log newest first; every nested `index.md` (e.g. `raw/index.md`) format-checked with paths resolved against its own folder |
| L3 | orphan: no inbound link from another page (`index.md` does not count; the constitution is exempt) |
| L4 | `stale_after` passed and not `deprecated` |
| L5 | a local `sources[].resource` no longer on disk |
| C1 | `dev.asserts` pattern no longer matches; `dev.parameters` value drifted (float comparison when both sides parse, ruling 2); `dev.requires_files` entry gone |
| C2 | a `dev.token_id` / `dev.tokens[]` entry on a non-deprecated page that is absent from the newest macro and sports drops (warning: resolved, delisted, or never listed); a missing drops folder is itself one warning. `lint --fix-safe` sets `status: deprecated` on a Market page so flagged and logs it (Round 97 ruling A5) |
| C3 | the same `dev.parameters[].name` with different values on two or more pages (error) |
| C5 | `generated.at` inside the page's own `dev.window` is an error; only the file mtime inside it is a warning, because a checkout can do that (ruling 3) |
| L6 | typed relations: `supersedes` target exists and is deprecated, chains acyclic; `contradicts` carries `resolved_by` -> an existing Ruling; `measured_by` -> an Experiment page; `enforced_in` -> a file in the repo |
| L7 | a Ruling or Concept page without `stale_after` (policy above), unless machine-maintained or deprecated |
| L8 | a dangling outbound wikilink: `[[target]]` naming a page that does not exist (Round 105). Links inside code fences and code spans are not links, so this document can describe the syntax |
| L9 | a wikilink whose only target is a file git IGNORES (Round 108, Ruling R107-1.D). The page lints clean here and fails L8 on a fresh clone, where the file was never committed. L5's git half and L9 are both SKIPPED, not passed, outside a repository |
| C4 C6 | Phase 3+: unhedged tax liability; the weekly LLM contradiction pass |

Lint writes nothing without `--fix-safe`, and with it may only set
`status: deprecated` on a Market page whose token is gone, regenerate
`index.md` (Ruling 98-5) and append one `**Lint**` bullet to `log.md`.
Anything else stays a report.

## 8. Refusals (fail closed, exit 3)

- `DEV/HALT.flag` present: every `knowledge` command refuses.
- a write outside `wiki/ crm/ journal/ raw/`, `WIKI_SCHEMA.md`, `index.md`,
  `log.md`: `WriteRefused`.
- a page without a valid frontmatter block: `write_page` refuses.
- a page whose `dev.window` contains now: refused; registrations are
  appended before a window in a dated re-registration, never edited inside.
- a registry, vault or raw path that is missing: refuse, do not create.

## 9. Commands (Phases 1-2)

```
python -m knowledge.seed  [--vault DIR] [--dev-root DIR] [--registry FILE] [--force] [--dry-run] [--at ISO]
python -m knowledge.lint  [--vault DIR] [--dev-root DIR] [--drops DIR] [--json]
python -m knowledge.raw_manifest [--dry-run]                       -> raw/index.md
python -m knowledge.ingest.experiments [--dir DIR] [--force]       -> wiki/experiments/ (pre-registrations)
python -m knowledge.ingest.lead_lag --result verdict.json --tier 1|2|2b
                                                                   -> wiki/experiments/ verdict + wiki/regimes/btc_macro_regime.md
python -m knowledge.ingest.clob --result curve.json --event fomc_2026-09-16
                                                                   -> wiki/profiles/, wiki/events/, wiki/concepts/latency_decay.md
python -m knowledge.ingest.rulings [--agents AGENTS.md] [--force]  -> wiki/rulings/ Directive_/Ratification_/Ruling_N-N (draft)
python -m knowledge.computations [--force]                         -> wiki/computations/ (shell twins + knowledge CLIs, declarative)
python -m knowledge.ingest.calendar [--dir knowledge/calendars]    -> wiki/events/ (FOMC statements with windows; tax deadlines)
python -m knowledge.ingest.markets [--family FED-RATES ...]        -> wiki/markets/ (tokens from rules, Experiments, the newest drop)
python -m knowledge.lint --fix-safe                                deprecates Market pages whose token left the drops, rebuilds index.md
python -m knowledge.ingest.entities [--limit-whales 100] [--limit-titans 100]
                                                                   -> crm/{titans,whales,sharps,books}/ (judgement kept, evidence appended)
python -m knowledge.ratify --type Ruling --tag extracted --ruling 98-1
                                                                   records a ratification: verified + status stable on the selected pages
python -m knowledge.journal --date 2026-09-05 [--create]           -> journal/2026-09-05.md (executions from paper receipts, debrief)
python -m knowledge.journal --predict --event fomc_2026-09-16 --field change_bps --op == --value 0 --p 0.9
python -m knowledge.journal --score [--event E --outcome 0|1]          scores predictions (hand outcome for free-text claims); rebuilds calibration.md
python -m knowledge.views [--force]                                -> wiki/_views/*.base (Obsidian Bases) and wiki/_templates/*.md
python -m knowledge.ingest.theses [--root DIR ...] [--force]       -> wiki/concepts/thesis_*.md from desk module docstrings (pinned by C1)
python -m unittest knowledge.tests.test_knowledge                  (Master Module 23)
```

Registers: `wiki/concepts/{experiments,rulings,computations,events,markets,crm,journal,theses}_register.md`
are rebuilt by the adapter that owns the type; every Desk page links all eight.
Dashboards link back (Round 101, F1): every exporter prints a `Desk:` wikilink to
its Desk page and a `Shell twin:` command that reproduces the card; the quant lab
exporter lives in its own repository and is the one exception until that repo is
touched.
Every adapter carries `verified`, `stale_after`, a promoted status and
`dev.ratified_by` across a `--force` rewrite (Ruling 99-2, `pages.carry_human_fields`).
Calendars are committed YAML under `knowledge/calendars/` (FOMC from
federalreserve.gov by hand; the December statement is 19:00Z, not 18:00Z).

The seed skips pages that already exist unless `--force`, so a re-run never
clobbers a page an ingest or a human improved. Its default `generated.at` is
the registry file's mtime (ruling 12), so `--force` on an unchanged registry
is byte-idempotent. Every ingest command reads an EXISTING `--json` output
or registration file; none imports a desk module or opens a socket.

Primed for the calendar: after the Tier 1 verdict (about 2026-09-06T01:39Z)
run `python -m cross_market.lead_lag --coin BTC --family macro --json > verdict.json`
then `knowledge.ingest.lead_lag --result verdict.json --tier 1`. After the
2026-09-16 FOMC drill run the survival curve with `--json > curve.json`
then `knowledge.ingest.clob --result curve.json --event fomc_2026-09-16`.

## 10. Amendment

This file changes only between rounds, in a commit whose message names the
Ruling that motivated it, with `generated.at` and the `dev.round` bumped.
Inside any registered event window (T-2 to T+5) it is frozen.
