---
type: Blueprint
title: LLM Wiki x DEV - Trading Knowledge Compiler Blueprint
description: Round 95 research report. How to evolve the DEV Obsidian vault from a one-way dashboard sink into a compiled, compounding trading knowledge base (raw / wiki / schema) with a counterparty CRM, a reflective journal and an autonomous lint pass, without touching a running daemon.
tags: [round-95, llm-wiki, okf, obsidian, architecture, research]
generated:
  by: claude-code/fable-5.1
  at: 2026-09-05T19:45:00Z
status: draft
dev:
  round: 95
  baseline_commit: ec98342
  desks: [1, 2, 3, 4, 5]
sources:
  - id: karpathy-llm-wiki
    resource: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
    title: llm-wiki (gist)
    author: human:karpathy
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format SPEC.md (v0.2 current, v0.1 legacy)
    author: GoogleCloudPlatform/knowledge-catalog
  - id: dev-audit
    resource: c:/Users/ixis1/Desktop/DEV
    title: Read-only audit of the DEV workspace at ec98342, 2026-09-05 15:24-15:32 EDT
    author: claude-code/fable-5.1
---

# LLM Wiki x DEV: Trading Knowledge Compiler Blueprint

Round 95. Baseline commit ec98342. Research only: no code, no daemon, no
scheduled task and no vault dashboard was touched. Every figure below was read
from disk or from a read-only SQLite handle during the audit window.

## 0. Thesis in one paragraph

DEV already has all three layers of the LLM Wiki pattern, but under other
names and in the wrong containers. The **raw layer** is the desk `data/`
folders: 4.9 GB of Hyperliquid snapshots, 422 stamped Polymarket drops, eight
CLOB books, four pre-registration files, a tax ledger. The **schema layer** is
split across `AGENTS.md`, the quant lab `CLAUDE.md`, the Top 20 registry in
`MASTER_COMMAND_LIST.txt` and `.agents/rules/dual_agent_workflow.md`. The
**wiki layer** does not exist: what should be compiled, durable, cross-linked
pages is instead 563 KB of chronological handoff prose across six `AGENTS.md`
files, plus essay-length module docstrings, plus rationale buried in YAML
comments. The vault, meanwhile, is a set of eleven dashboards and 120 entity
notes that six exporters overwrite every cycle, so it holds the present and
forgets everything else. The proposal is to add the missing wiki layer inside
the vault, keep the exporters exactly as they are, make the raw folders the
immutable truth they already behave as, and write one constitution that tells
an agent how to ingest, query and lint. Google's Open Knowledge Format (OKF
v0.2) supplies the frontmatter vocabulary, and one of its types, *Attested
Computation*, is a near-exact match for the ecosystem's existing "shell twin"
convention.

## 1. DEV audit and knowledge assets

### 1.1 What each desk produces today

| Desk | Durable stores (read-only audit) | Live telemetry | Vault surface | Compiled knowledge today |
|---|---|---|---|---|
| 1 HyperLiquid Monarch | `hyperliquid_data.db` 4.9 GB, 13 tables (asset_snapshots, orderbook_snapshots, trades, liquidation_events, liquidation_clusters, cascade_excursions, basis_realised_windows, whale_wallets, cross_market_titans, measurement_watermarks); `data/experiments/` N=12 baseline + 3 meta files | `collector_service.jsonl` (329 coverage reports, 99.98 % coverage over 24 h), `dashboard.jsonl`, `basis_paper_state.json`, `paper_trading_state.json` | `HyperLiquid_Monarch.md`, `Trading_Terminal.md`, `Bot_Control.md`, `Bot_Config.md`, 79 `Whales/*.md` | none outside `HyperLiquid/AGENTS.md` (75 KB) and `HL_Monarch/AGENTS.md` |
| 2 Sports Desk | `sports_market.db` 8 tables: fair_odds_measurements 32 rows, edge_opportunities 96, placed_bets 0, settled_results 0, brier_snapshots 0; `polymarket_drops/` 211 macro + 211 sports stamps (94 MB) | `polymarket_watcher.log` | `Sports_Desk.md` (2 KB) | `Sports_Desk/AGENTS.md` (19 KB) |
| 3 Cross-Market | `clob_books/` 8 stamps (bids/asks/hash/neg_risk/observed_at); `experiments/` 4 registrations (tier2, tier2b, fomc_2026-09-16 rules, sniper sample); `titan_identities_cache.json` 8 EOA-to-proxy mappings; `paper_receipts/` (empty, gitignored) | `cross_market_exporter.log` 2,401 lines, `maiden_protocol_2026-09-06.log`, `fomc_drill_2026-09-16.log` | `Cross_Market_Arb.md`, `Cross_Market_Titans.md` (marker blocks), `Risk_Sentinel.md` | Rulings R1-R6, Directives 51-2 to 75-2, Ratifications 76-2/76-3: all prose in top-level `AGENTS.md` (147 KB, 62 round entries) |
| 4 Quant Trading Lab | `data/continuous/` 30 stitched OHLCV CSVs + 31 others (81 MB); `state/runtime_state.json` (Risk Sentinel state, ticket seq) | none running | `Quant_Trading_Lab.md` | `quant_trading_lab/AGENTS.md` (239 KB), `CLAUDE.md` spec (risk invariants), `ICT Quantlab notes/` PDFs |
| 5 Tax Reserve Agent | `tax_ledger.db` (transactions, tax_lots, realized_pnl: 0 rows, paper phase); `config.yaml` with statute rationale in comments | `data/imports/` watcher | `Trading_Taxes/Tax_Reserve_<date>.md` x3 (the only dated series in the vault) | `Tax_Reserve_Agent/AGENTS.md` (70 KB), README |
| Polymarket Monarch (Desk 3 adjunct) | `polymarket_whales.db`: sharp_traders 79, tracked_wallets 97, whale_trades 0 | none | `Polymarket_Monarch.md`, 41 `Wallets/*.md` | `Polymarket_Monarch/AGENTS.md` |

### 1.2 What evaporates, ranked by value lost

1. **Post-print order-book decay.** The survival curve (Round 94) and depth
   report (Round 92) print to the console. The FOMC drill on 2026-09-16 will
   write 1,260 one-second stamps for three tokens and the single most valuable
   number the sniper thesis needs, seconds-to-half-depth per market, will exist
   only in a terminal unless it is filed. Same for the eight stamps already
   recorded: their depth report is in `AGENTS.md` prose ("thin books offer
   $400-$3,300"), not in a page that the next event can be compared against.
2. **Lead-lag verdicts.** Tier 1 lands in `Cross_Market_Titans.md` inside a
   marker block; the exporter regenerates the note every 15 s. There is no
   history of verdicts, no page that says "as of date D the fed-rates
   subfamily showed corr c at lag L", and therefore nothing for a regime
   classification to compound over.
3. **Rulings and directives.** Ruling R4 (neg-risk books skip the NO side),
   the Round 29 IRC 1234A characterisation, the 0.99 confidence floor, the
   quarter-Kelly cap, the 60-minute gap rule: each is cited by number across
   rounds, and each lives only as a sentence in a 147 KB log. A new session
   has to grep prose to learn the law.
4. **Cascade and liquidation events.** `cascade_excursions` and
   `liquidation_clusters` accumulate rows and roll off dashboards. No event
   ever becomes a narrative ("the 2026-09-02 ETH cascade: $X notional, MAE
   5 m, what the sweeper would have done").
5. **Entity identity.** Every whale note carries a callout asking the operator
   to "link its Polymarket trader note here by hand". Eight resolved
   EOA-to-proxy pairs sit in `titan_identities_cache.json` and never reach
   either note. The `cross_market_titans` table exists for exactly this and
   the Titans roster on the dashboard reads "0 institutional actors".
6. **Edge opportunities without review.** 96 `edge_opportunities` rows and 32
   fair-odds measurements were never revisited: which sharp book led, which
   soft book lagged, which market types produced edges. That is the raw
   material of a sportsbook vulnerability profile and it is unread.
7. **Experiment meta files.** The four pre-registrations are the best
   provenance discipline in the repo (registered_utc, bars, decision,
   caveats, enforced_in_code) and they are invisible from the vault.
8. **Statute rationale in YAML comments.** `config.yaml` explains why NJ
   marginal is 6.37 %, why IRC 165(d) makes losses a deduction, why the old
   composite double-counted state tax. A wiki concept page is the natural
   home; a comment block is where it will be lost on the next refactor.
9. **The journal.** `obsidian_vault/2026-09-02.md` exists and is empty. Daily
   Notes is enabled. The habit was started and had nothing to feed it.

### 1.3 The vault today: a passive display

- Eleven dashboard notes, 52 KB total, regenerated by six exporters with
  whole-file writes. Only `Cross_Market_Titans.md` uses marker blocks
  (`lead-lag-sentinel:start/end`) to let two writers share one file.
- 120 entity notes (79 whales, 41 sharp traders) with good YAML frontmatter
  (address, equity, leverage, pnl_7d, tags) but no history: each sync
  replaces the file, so last week's leverage is gone.
- Three dated tax notes: the only append-only series.
- Two canvases, Bases enabled (`Untitled.base` was created today), Properties,
  Daily Notes, Templates, Backlinks and Graph all on. Every core plugin a
  frontmatter-driven wiki needs is already switched on.
- Everything links to `Monarch_Hub.md`; nothing links to a durable claim,
  because there are none.

### 1.4 The three layers, already present and unnamed

| LLM Wiki layer | What Karpathy specifies | What DEV already has | Gap |
|---|---|---|---|
| raw (immutable) | curated sources the LLM reads and never edits | desk `data/` drops, stamped JSON, CLOB books, SQLite, experiment meta, Fed statement (future), `.gitignore` already treats them as runtime truth | no manifest; human-authored sources (statements, memos, post-mortems) have no home |
| wiki (LLM-owned) | entity, concept, source-summary and synthesis pages, `index.md`, `log.md` | none; the closest are docstring essays and AGENTS prose | the whole layer |
| schema (constitution) | one file defining page types, conventions, workflows | `AGENTS.md` (log + rules fused), `CLAUDE.md` (quant lab), `dual_agent_workflow.md`, registry | fused with the log; no page types, no ingest/lint procedure |

The gist's central warning applies to DEV verbatim. Karpathy calls it copied
state drift: "a quote without its dependent named is a copy waiting to go
stale with nothing watching it." DEV has already paid for this twice this
week. Round 94 found the `MASTER_COMMAND_LIST.txt` header claiming Round 72
since commit 9fd5ef1 because a replace targeted a string that was no longer
there, and Round 93b re-dated the FOMC drill after a date was copied wrong.
Both are exactly the class of defect a lint pass with declared dependencies
catches.

## 2. Architecture tailored for trading

### 2.1 Placement decision

The wiki, CRM and journal go **inside `obsidian_vault/`** so Obsidian's graph,
backlinks, Bases and Daily Notes render them without any bridge. The raw
layer stays **federated**: the desk `data/` folders remain where the daemons
write them, and a small `raw/` folder in the vault holds only human-authored
sources plus a manifest that names every machine-written raw stream by path
and schema. Nothing is copied: 4.9 GB does not move, and the daemons never
learn the wiki exists.

The constitution is one new file, `obsidian_vault/WIKI_SCHEMA.md`. It does not
replace `AGENTS.md`; it takes the durable-rules role away from it so that
`AGENTS.md` can go back to being what its header says it is, a terse handoff
log.

### 2.2 File tree

```
obsidian_vault/
  WIKI_SCHEMA.md                 the constitution (schema layer)
  index.md                       OKF reserved: every page, one line each
  log.md                         OKF reserved: newest-first, date-grouped
  raw/                           human-authored immutable sources only
    index.md                     manifest of ALL raw streams incl. federated
    statements/                  fomc_2026-09-16.txt (pasted statement text)
    memos/                       2026-09-05_operator_voice.md (transcripts)
    postmortems/                 2026-09-0x_<event>.md
  wiki/
    desks/                       one page per desk (type: Desk)
    items/                       item-01 .. item-20 (type: Item) from the registry
    rulings/                     R1..R6, directives, ratifications (type: Ruling)
    experiments/                 one page per pre-registration (type: Experiment)
    events/                      fomc-2026-09-16.md (type: Event)
    profiles/                    reaction profiles per event x market (type: Reaction Profile)
    regimes/                     btc-macro-current.md + history (type: Regime)
    markets/                     one page per Polymarket condition tracked (type: Market)
    concepts/                    latency-decay, neg-risk-parity, asymmetric-tax, ... (type: Concept)
    sources/                     one summary per raw source ingested (type: Source Summary)
    computations/                shell twins as OKF Attested Computation
    lint/                        YYYY-MM-DD.md lint reports
    _views/                      Bases files: rulings.base, markets.base, experiments.base
  crm/
    whales/                      compiled HL whale profiles (type: Entity/Whale)
    sharps/                      compiled Polymarket sharp profiles (type: Entity/Sharp Trader)
    titans/                      resolved cross-venue identities (type: Entity/Titan)
    books/                       sportsbook soft-line profiles (type: Entity/Sportsbook)
    makers/                      Polymarket market makers by resting-Q signature
    officials/                   Fed officials (human-ingested; low priority)
    contacts/                    desk contacts (human-authored)
  journal/
    2026-09-05.md                daily: plan / executions / debrief / open
    debriefs/                    LLM-written risk debriefs (type: Debrief), linked from the day
  Whales/  Wallets/  Trading_Taxes/  Canvases/   (exporter-owned, untouched)
  *.md dashboards                                 (exporter-owned, untouched)

knowledge/                       new Python package, master module 23
  __init__.py
  frontmatter.py                 OKF v0.2 validator + dev: extension
  pages.py                       templates, index/log writers (append-only log)
  raw_manifest.py                enumerates federated streams, read-only
  ingest/
    clob_profile.py              survival_curve --json  -> Reaction Profile page
    lead_lag_verdict.py          lead_lag --json         -> Experiment + Regime pages
    receipts.py                  paper receipts          -> journal execution rows
    entities.py                  whales.db / sharp_traders / titan cache -> crm pages
    statements.py                raw/statements/*.txt    -> Source Summary + Event update
  lint.py                        structural + DEV-specific checks, --json, exit 0/1/3
  query.py                       index-first retrieval; files answers as pages on request
  tests/
    test_frontmatter.py  test_lint.py  test_ingest_clob_profile.py
    test_ingest_lead_lag.py  test_entities.py  test_pages.py   (all offline, fixtures)
```

### 2.3 Frontmatter schema (OKF v0.2 aligned, `dev:` extension)

OKF v0.2 requires exactly one field, `type`. It recommends `title`,
`description`, `tags`, `resource`; it defines optional families `sources`
(each with a required `resource`), `generated {by, at}`, `verified [{by, at}]`,
`status draft|stable|deprecated`, `stale_after`; and it reserves `index.md`
and `log.md` with fixed line formats. Consumers must not reject unknown keys,
so DEV extensions live under one namespaced key.

```yaml
---
type: Ruling                       # REQUIRED (OKF). Vocabulary in 2.4
title: R4 - neg_risk books skip the NO side
description: On a negative-risk Polymarket book only the winning outcome's YES asks are lifted; the NO side is deferred.
tags: [ruling, desk-3, latency-sniper, neg-risk]
generated:                         # OKF trust family
  by: claude-code/fable-5.1        # actor convention: <producer>/<version> | human:<id> | process:<id>
  at: 2026-09-05T19:40:00Z
verified:
  - by: human:antigravity          # Antigravity's ratification IS the verification event
    at: 2026-09-05T02:10:00Z
status: stable                     # draft | stable | deprecated
stale_after: 2026-12-31T00:00:00Z  # rulings get a review horizon, not forever
sources:                           # OKF provenance family; resource REQUIRED per entry
  - id: agents-md-r88
    resource: file:///c:/Users/ixis1/Desktop/DEV/AGENTS.md#round-88-findings
    title: Round 88 findings
    author: human:antigravity
  - id: commit-da48cf3
    resource: git:da48cf3
    title: feat Round 88 Ruling R4
dev:                               # DEV namespace (OKF: unknown keys tolerated)
  desk: 3
  item: 12
  round: 88
  ruling_id: R4
  supersedes: []
  asserts:                         # copied-state guards: lint greps these
    - file: cross_market/latency_sniper.py
      pattern: "neg_risk"
      claim: "NO side deferred on neg_risk"
  parameters: []                   # named numbers this page states (see lint C3)
---
```

Two DEV-specific rules sit on top of OKF:

- **No copied mutable state.** A wiki page never quotes a PID, a row count,
  a last-synced time or a live price. Those belong to dashboards. A page
  that must mention a number declares it under `dev:parameters` with the
  file and pattern that owns it, so lint can check the copy against its
  dependent. This is the gist's remedy applied literally.
- **Verification is a human or Antigravity act.** `generated.by` is the
  agent that wrote the page; `verified` is appended only by an operator or
  by Antigravity's ratification. An LLM never verifies its own page.

### 2.4 Page-type vocabulary

| `type` | Folder | Compiled from | Update trigger |
|---|---|---|---|
| Desk | wiki/desks | AGENTS status, registry, module docstrings | ingest of any round |
| Item | wiki/items | Top 20 registry lines 80-484 | registry change |
| Ruling | wiki/rulings | rulings, directives, ratifications in AGENTS | each ratified round |
| Experiment | wiki/experiments | `*.meta.json` pre-registrations + later verdict JSON | registration; verdict |
| Event | wiki/events | rules file + statement text + drill log | pre-registration; T+5 |
| Reaction Profile | wiki/profiles | `latency_sniper --survival-curve --json` | after each recorded event |
| Regime | wiki/regimes | Tier 1/2/2b verdict pages | after each verdict |
| Market | wiki/markets | newest macro/sports drop record (token, condition, slug, neg_risk) | token first seen; expiry |
| Concept | wiki/concepts | docstring theses, YAML rationale, operator explanations | ingest; query filing |
| Source Summary | wiki/sources | one per raw source | ingest |
| Attested Computation | wiki/computations | every "Shell twin:" line the dashboards already print | when a CLI changes |
| Entity/Whale, Entity/Sharp Trader, Entity/Titan, Entity/Sportsbook, Entity/Market Maker, Entity/Official, Contact | crm/* | DBs, identity cache, edge_opportunities, book Q measurements, humans | ingest; lint |
| Journal Entry, Debrief | journal/* | receipts, Risk Sentinel state, escrow note, operator plan | daily |
| Lint Report | wiki/lint | `knowledge.lint --json` | scheduled or manual |

The **Attested Computation** mapping deserves a sentence. Every dashboard
already prints a "Shell twin" (`python -m cross_market.lead_lag --check-data`,
exit 0 ready / 3 not) so the operator can reproduce the card from a shell.
OKF v0.2 defines a type for exactly that: `runtime: python`, `computation:`
the command, `executor.receipt:` the `--json` fields it returns, `attester:`
the unit test that pins the behaviour. Filing the shell twins as pages of
this type gives the wiki a machine-checkable spine without inventing a
format.

### 2.5 The constitution: `WIKI_SCHEMA.md`

Contents, in order: the three-layer boundary and the ownership rule
(exporters own dashboards and entity notes; the knowledge agent owns
`wiki/ crm/ journal/ raw/`; neither writes the other's files); the actor
convention; the frontmatter contract above; the page-type table; the
**Ingest protocol** (read source, discuss takeaways, write or update the
Source Summary, touch every entity, concept, event and regime page the
source bears on, append `log.md`, regenerate `index.md`, one source may touch
10-15 pages); the **Query protocol** (read `index.md` first, drill into
pages, answer with wikilinks to pages and `sources` to raw, file the answer
as a Concept or Synthesis page when the operator says so); the **Lint
protocol** (section 3.3); the **Journal protocol** (section 2.7); the
**Refusals** (HALT.flag present, a raw path missing, a page without `type`,
a write outside the four owned folders: all refuse, exit 3 like the rest of
the ecosystem). Pre-registration discipline carries over unchanged: an
Experiment page may be appended before a window and never edited inside one.

### 2.6 `index.md` and `log.md`

OKF fixes both formats and DEV adopts them verbatim so any OKF consumer can
read the vault.

```
# Rulings
* [R4 - neg_risk books skip the NO side](wiki/rulings/R4.md) - only the winning outcome's YES asks are lifted
* [R6 - competitor Q measured from recorded books](wiki/rulings/R6.md) - pool rate stays the one input until R5 records it
```

```
## 2026-09-16
* **Ingest**: FOMC statement -> [fomc-2026-09-16](wiki/events/fomc-2026-09-16.md); three [reaction profiles](wiki/profiles/) filed; [latency-decay](wiki/concepts/latency-decay.md) table extended.
* **Lint**: 2 stale tokens flagged, 0 contradictions -> [report](wiki/lint/2026-09-16.md).
```

`log.md` is append-only and machine-written by `knowledge.pages`; a human
edit to it is a lint error.

### 2.7 Special modules

**Counterparty and whale CRM (`crm/`).** A CRM page is a compiled judgement,
not a metrics mirror. The exporter-owned `Whales/0x...md` keeps the live
numbers; the CRM page beside it holds what does not change every 15 s:
confirmed cross-venue identity (both addresses, the proxy, the pseudonym,
how the link was established), behavioural reads accumulated over ingests
("adds to ETH longs into funding spikes", "quotes both sides of Fed markets
inside the 3-cent window with Q about 29k"), first-seen and notable events
with links to Event and Source pages, and a `dev:evidence` list of the raw
rows behind each claim. Sources per entity type:

| Entity | Seeded from (read-only) | What the CRM adds |
|---|---|---|
| Whale | `whale_wallets`, `cascade_excursions`, `liquidation_events` filtered by address | cascade participation history, liquidator flag rationale |
| Sharp Trader | `sharp_traders` (79), `tracked_wallets` (97), `whale_trades` | market families traded, consensus-scanner hits, Brier when settled data exists |
| Titan | `cross_market_titans` + `titan_identities_cache.json` (8 pairs) | the identity page both suites' notes were asking the operator to write by hand |
| Sportsbook | `edge_opportunities` (96) grouped by `sharp_book` and soft book, `fair_odds_measurements` | soft-line vulnerability profile: which market types lag, by how much, how long |
| Market Maker | `amm_rewards --replay-books` book Q signatures per token | resting-size signature, window discipline (no names: the data has none) |
| Official / Contact | human-authored only | statement tone history; accountant, prop firm, broker contacts |

**Trader reflective journal (`journal/`).** One page per trading day, four
sections, in the order the day happens:

1. *Plan* (operator, pre-market): intent, the Risk Sentinel buffer from the
   newest `Risk_Sentinel.md` verdict, the desks in play, the events
   registered today.
2. *Executions* (machine, appended through the day): every receipt the
   ecosystem produces, read-only: `cross_market/data/paper_receipts/*.json`,
   `paper_trading_state.json`, `placed_bets`, `Tax_Reserve_Agent/data/imports/`
   results. One row per fill: time, desk, strategy, size, the gating
   decision that allowed it (`MonarchBankrollHook.check_order` result if
   logged), paper flag.
3. *Debrief* (LLM, after close, `knowledge journal --debrief`): each
   execution checked against the rule set the desks already encode: the
   quant lab invariants (1 % single-trade risk, $3,500 daily killswitch,
   NQ+ES combined 6 contracts), the Tax Reserve hurdle (after-tax breakeven
   at the fee-adjusted odds), the quarter-Kelly cap, the 0.99 confidence
   floor, the neg-risk R4 rule. Output is a table of executions with
   pass/flag and a short narrative; it is `generated.by` the agent and
   never `verified` by it.
4. *Open* (both): questions that became Concept pages, rulings requested of
   Antigravity, lint items assigned.

The debrief exists to turn "the rules" from a scattered list into a daily
applied test. It places no orders and changes no threshold.

## 3. Workflow integration and alpha applications

### 3.1 Ingest adapters (all read-only on their source)

| Raw stream (owner) | Adapter | Produces / updates | Cadence |
|---|---|---|---|
| `clob_books/<event>/*.json` (sniper record-loop) | `ingest.clob_profile` runs `survival_curve --json` | Reaction Profile per market; Event page summary; `concepts/latency-decay.md` cross-event table | after each recorded event (first: 2026-09-16 T+5) |
| `lead_lag --json` output, `lead_lag_tier2*.meta.json` | `ingest.lead_lag_verdict` | Experiment page (bar, points, span, peak lag, corr, verdict), Regime page history row | after Tier 1 (2026-09-06), Tier 2, Tier 2b |
| `paper_receipts/`, `paper_trading_state.json`, `placed_bets` | `ingest.receipts` | journal Executions rows | daily, or on demand |
| `polymarket_whales.db`, `whale_wallets`, `cross_market_titans`, `titan_identities_cache.json` | `ingest.entities` | crm pages (create or append evidence; never overwrite judgement text) | weekly, or after `--resolve` |
| newest macro/sports drop | `ingest.markets` | Market pages; expiry check feeds lint | daily |
| `raw/statements/*.txt`, `raw/memos/*.md`, `raw/postmortems/*.md` | `ingest.statements` (text), manual ingest (memos) | Source Summary; Event page; Concept pages; crm/officials | on arrival |
| `*.meta.json` registrations | `ingest.experiments` | Experiment page in `status: draft` until the verdict | on registration |
| `AGENTS.md` round entries | manual ingest via the constitution | Ruling, Desk and Item pages | each ratified round |

### 3.2 Query

Index-first, as the gist prescribes: the agent reads `index.md`, opens the
handful of pages it names, answers with wikilinks and `sources`, and files
the answer as a page when the operator says "keep that". At DEV's scale
(low hundreds of pages for a year) this needs no embeddings. The two
queries the ecosystem will actually ask are pre-baked as commands:

- `knowledge query --drill-card fomc-2026-09-16` at T-2: one page under 60
  lines, assembled from the Event page, the registered rules, the last
  Reaction Profile for a fed_rate event (none yet; the card says so), the
  current Regime page and the Tax Reserve breakeven. Context for the
  operator's eyes and the paper path. It never reaches the executor.
- `knowledge query --regime BTC` : the current classification, the verdict
  pages behind it, and the disagreements Tier 2b recorded.

### 3.3 Autonomous lint engine

`python -m knowledge.lint [--json] [--fix-safe]`. Exit 0 clean, 1 findings,
3 refused (HALT.flag or a missing owned folder). Deterministic checks are
code; only the contradiction check needs an LLM, and it runs as a Claude
Code session under the constitution, never as a daemon.

| ID | Check | DEV-specific detail |
|---|---|---|
| L1 | Frontmatter parses, `type` present, actor strings well-formed | OKF conformance |
| L2 | `index.md` and `log.md` follow the reserved formats; `log.md` unmodified except by append | grep-able history |
| L3 | Orphans: page with no inbound wikilink | Karpathy's orphan rule |
| L4 | `stale_after` passed, `status` not deprecated | rulings review horizon |
| L5 | `sources[].resource` paths exist on disk (federated raw) | catches a moved drop folder or purged stamps |
| C1 | **Stale risk thresholds**: every `dev:parameters` and `dev:asserts` entry greps its owning file | 0.20 corr bar, 5 min latency, quarter-Kelly, 0.99 floor, $3,500 killswitch, 6-contract cap, 60 min gap |
| C2 | **Expired market tokens**: each Market page's `token_id` present in the newest drop and not resolved | the two cut markets that were `not_found_in_drop`; the September 6 BTC ladders that expire tomorrow |
| C3 | **Conflicting rule definitions across desks**: same parameter name, different values on two pages | fee assumptions (fee_rate 0 vs taker_base_fee_raw 1000), two Kelly fractions, two hurdle definitions |
| C4 | **Unhedged tax liability**: journal day with realised P&L rows but the same day's `Trading_Taxes` note shows escrow unchanged | `realized_pnl` vs `Tax_Reserve_<date>.md` |
| C5 | **Registration inside a window**: an Experiment or Event page edited between T-2 and T+5 of its own event | enforces the standing constraint mechanically |
| C6 | Contradictions between pages (LLM pass, weekly) | reports, never auto-fixes |

`--fix-safe` may only regenerate `index.md`, append to `log.md`, and set
`status: deprecated` on a Market page whose token is gone. Everything else is
a report.

### 3.4 Polymarket oracle and latency sniping

Today the sniper thesis has one measurement (eight resting books) and one
scheduled experiment. The wiki turns each event into three compounding
pages: the **Event** (pre-registered rules, statement text once ingested,
observed_at, lag to release_utc), one **Reaction Profile** per market
(baseline notional, first-change second, seconds to half and to a tenth,
dollar-seconds after the print, all straight from `--survival-curve --json`),
and a row in the **latency-decay** Concept page's cross-event table. After
three or four events the table answers the roadmap's open question, whether
"10-50 % per event" survives past the first second, with numbers rather
than a claim. The drill card (3.2) is how that history reaches the operator
at T-2 next time. Nothing here changes `latency_sniper.py`; the adapter
consumes its existing JSON.

### 3.5 Titan macro-crypto predictive horizon

Each Tier verdict becomes an Experiment page with the bar it was judged
against and the numbers it produced. The **Regime** page classifies the
result under a fixed vocabulary that the constitution defines once:
`no-lead` (|corr| < 0.20 everywhere), `contemporaneous` (peak inside the
5-minute poll interval: repricing, not prediction, per the Tier 2 latency
rule), `fed-leads-btc` and `btc-leads-fed` (peak outside the interval and
above the bar, with sign). A history table accumulates one row per verdict
with date, subfamily, membership rule (Tier 2 vs 2b), peak lag, corr and
class. Where Tier 2 and Tier 2b disagree, the disagreement is itself filed
as a finding, exactly as `lead_lag_tier2b.meta.json`'s reading rule already
demands. Over weeks the page shows whether the regime is stable, which is
the only form in which a lead-lag result is tradeable.

## 4. Safety constraints and non-interference

- **Read-only on every daemon-owned artifact.** SQLite is opened with the
  `file:...?mode=ro` URI (as this audit did); drop folders, CLOB stamps,
  PID files, logs and `paper_receipts` are read, never written or moved.
  Dashboards and `Whales/ Wallets/ Trading_Taxes/` remain exporter property
  in every phase.
- **Writes confined** to `obsidian_vault/{wiki,crm,journal,raw}/`,
  `WIKI_SCHEMA.md`, `index.md`, `log.md`, the `knowledge/` package and its
  tests. A write anywhere else is a refusal (exit 3), and the test suite
  asserts the allow-list.
- **HALT.flag honoured** by every `knowledge` command, matching the sniper,
  AMM and C2 bot.
- **No execution path.** The wiki informs the operator and the paper path;
  no module in `knowledge/` imports an executor.
- **Test integrity.** Module 23 ships with fixtures (a sample drop, three
  CLOB stamps, a survival-curve JSON, a meta file, a receipts folder) and
  runs offline; the three-suite total rises from 2,575 by the module's count
  and the other two suites are untouched.
- **Registration discipline** carries into the wiki: lint C5 refuses edits
  to an Event or Experiment page inside its own window.
- **Git.** `wiki/ crm/ journal/ raw/` are committed: they are small text and
  they are the product. Whether the exporter dashboards should stop being
  tracked (they show as modified in every `git status`) is a ruling for
  Antigravity, not a change this proposal makes.

## 5. Implementation phases

| Phase | Rounds | Deliverables | Tests | Touches daemons |
|---|---|---|---|---|
| 0 | 95 (this) | this blueprint; rulings requested below | none | no |
| 1 Constitution and seed | 96-97 | `WIKI_SCHEMA.md`; `knowledge/frontmatter.py`, `pages.py`, `lint.py` (L1-L5, C1, C5); seed pages: 5 Desk, 20 Item, all Rulings and Directives, 4 Experiment, 11 Attested Computation (the shell twins), first Concepts (latency-decay, neg-risk parity, asymmetric tax, copied-state drift); `index.md`, `log.md`, `raw/index.md` manifest | module 23 opens: frontmatter, pages, lint | no |
| 2 Ingest | 98-100 | `ingest.clob_profile` (ready before 2026-09-16), `ingest.lead_lag_verdict` (ready before the 2026-09-06 Tier 1 verdict), `ingest.experiments`, `ingest.markets`; lint C2, C3 | fixtures per adapter | no |
| 3 CRM and journal | 101-103 | `ingest.entities` and the Titan identity pages; sportsbook profiles from `edge_opportunities`; `journal` command with Plan/Executions/Debrief; lint C4 | fixtures: whales.db copy, receipts | no |
| 4 Views and backlinks | 104+ | Bases files in `wiki/_views/`; one wikilink per dashboard to its wiki Desk page (a one-line exporter change per desk, ratified separately); optional scheduled lint task, opt-in, HALT-aware | exporter tests re-run | exporter code only, after ratification |
| 5 Voice and query filing | later | `raw/memos/` transcript intake; `query --file` | | no |

Phase ordering is driven by two dates already on the calendar: Tier 1 at
about 9:39 PM EDT on 2026-09-05 and the FOMC drill at 1:58 PM EDT on
2026-09-16. Both produce the first raw artifacts the wiki exists to compile,
so the two adapters that consume them come first.

## 6. Rulings requested from Antigravity

1. **Placement**: wiki/crm/journal inside `obsidian_vault/` (recommended)
   versus a sibling `knowledge_vault/`.
2. **Constitution file**: new `obsidian_vault/WIKI_SCHEMA.md` (recommended)
   versus a section in the 147 KB `AGENTS.md`.
3. **OKF adoption depth**: frontmatter families and reserved files only
   (recommended), or also the Attested Computation `executor`/`attester`
   fields wired to the unit tests.
4. **Verification actor**: is Antigravity's ratification the `verified` event
   for Ruling pages, and who may append it.
5. **Git tracking of dashboards**: keep tracking exporter-written notes, or
   ignore them now that the wiki holds the durable content.
6. **Journal debrief scope**: paper receipts only (recommended, nothing live
   exists), and which rule set the debrief checks in Phase 3.
7. **Module numbering**: `knowledge` as master module 23 in the 22-module
   unittest run.

## 7. Sources

- Karpathy, A. *llm-wiki* gist: <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- Google Cloud, *Open Knowledge Format SPEC.md* (v0.2 current; v0.1 legacy): <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>
- Google Cloud blog, *How the Open Knowledge Format can improve data sharing*: <https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing>
- Secondary reads consulted for the wiki/CRM/journal three-pillar pattern: <https://www.mindstudio.ai/blog/obsidian-ai-second-brain-wiki-crm-journal-three-pillars>, <https://github.com/NicholasSpisak/second-brain>, <https://cozypet.github.io/llm-wiki-schema/>
- DEV workspace at ec98342, read-only audit 2026-09-05 15:24-15:32 EDT (this document's `dev-audit` source).
