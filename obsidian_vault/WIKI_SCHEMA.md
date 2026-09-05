---
type: Constitution
title: WIKI_SCHEMA - the knowledge layer constitution
description: How the DEV trading wiki is laid out, what a page must carry, who may write where, and the ingest, query, journal and lint protocols an agent follows. Ratified R95-A to R95-G.
tags: [constitution, schema, okf, round-96]
generated:
  by: claude-code/fable-5.1
  at: 2026-09-05T20:10:00Z
status: draft   # becomes stable, with a verified block, only when Antigravity has read THIS text (s.2)
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
  round: 96
  ruling_ids: [R95-A, R95-B, R95-C, R95-D, R95-E, R95-F, R95-G]
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
  `asserts`, `parameters`, `window`, `evidence`.

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
`dev.parameters[]` = `{name, value, file, pattern}`: the page states a
number; the regex's first group must still equal it in the owning file
(lint C1; commas, `$` and spaces are ignored in the comparison).
`dev.window` = `{start, end}`: a registration window; the page may not be
written inside it (`write_page` refuses; lint C5 reports).

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
| Source Summary | wiki/sources | one per raw source ingested |
| Attested Computation | wiki/computations | every dashboard "Shell twin"; declarative only (R95-C) |
| Entity/Whale, Entity/Sharp Trader, Entity/Titan, Entity/Sportsbook, Entity/Market Maker, Entity/Official, Contact | crm/whales, crm/sharps, crm/titans, crm/books, crm/makers, crm/officials, crm/contacts | databases, the identity cache, edge_opportunities, book Q, humans |
| Journal Entry, Debrief | journal, journal/debriefs | receipts, Risk Sentinel state, escrow note, the operator's plan |
| Lint Report | wiki/lint | `knowledge.lint --json` |
| Blueprint, Constitution | wiki/concepts, vault root | this layer's own design documents |

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
hand-edited.

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

### Journal (R95-F)

One `journal/YYYY-MM-DD.md` per trading day: **Plan** (operator), **Executions**
(machine, from PAPER receipts only, `paper:1`), **Debrief** (agent, checks each
execution against the Tax Reserve Agent after-tax hurdle and the Risk Sentinel
drawdown limits; `generated.by` the agent, never `verified` by it), **Open**.
The debrief places no orders and changes no threshold.

### Lint

`python -m knowledge.lint [--json]` (exit 0 clean, 1 findings, 3 refused).

| Code | Check |
|---|---|
| L1 | frontmatter parses; `type` present; OKF shapes hold |
| L2 | `index.md` / `log.md` on the reserved formats; index paths exist; every page listed; log newest first |
| L3 | orphan: no inbound link from another page (`index.md` does not count) |
| L4 | `stale_after` passed and not `deprecated` |
| L5 | a local `sources[].resource` no longer on disk |
| C1 | `dev.asserts` pattern no longer matches, or `dev.parameters` value drifted from its file |
| C5 | a page modified inside its own `dev.window` |
| C2 C3 C4 C6 | Phase 2-3: expired market tokens, cross-desk parameter conflicts, unhedged tax liability, the weekly LLM contradiction pass |

Lint writes nothing. `--fix-safe` (Phase 2) may only regenerate `index.md`,
append to `log.md`, and set `status: deprecated` on a Market page whose
token is gone.

## 8. Refusals (fail closed, exit 3)

- `DEV/HALT.flag` present: every `knowledge` command refuses.
- a write outside `wiki/ crm/ journal/ raw/`, `WIKI_SCHEMA.md`, `index.md`,
  `log.md`: `WriteRefused`.
- a page without a valid frontmatter block: `write_page` refuses.
- a page whose `dev.window` contains now: refused; registrations are
  appended before a window in a dated re-registration, never edited inside.
- a registry, vault or raw path that is missing: refuse, do not create.

## 9. Commands (Phase 1)

```
python -m knowledge.seed  [--vault DIR] [--dev-root DIR] [--registry FILE] [--force] [--dry-run] [--at ISO]
python -m knowledge.lint  [--vault DIR] [--dev-root DIR] [--json]
python -m unittest knowledge.tests.test_knowledge          (Master Module 23)
```

The seed skips pages that already exist unless `--force`, so a re-run never
clobbers a page an ingest or a human improved.

## 10. Amendment

This file changes only between rounds, in a commit whose message names the
Ruling that motivated it, with `generated.at` and the `dev.round` bumped.
Inside any registered event window (T-2 to T+5) it is frozen.
