---
type: Backlog
title: Knowledge layer backlog - what else to compile, check and build (Phases 3+)
description: Round 97b research. A prioritised backlog for the DEV knowledge layer after Phase 2, grounded in a fresh gap scan of the repo and in what the LLM-wiki pattern has grown into since Karpathy's gist; each item scored, sequenced into rounds, and the ideas deliberately rejected listed with reasons.
tags: [round-97b, llm-wiki, backlog, research, phase-3, phase-4]
generated:
  by: claude-code/fable-5.1
  at: 2026-09-05T21:15:00Z
status: draft
dev:
  round: 97
  baseline_commit: 29b0620
sources:
  - id: dev-gap-scan
    resource: c:/Users/ixis1/Desktop/DEV
    title: Read-only gap scan at 29b0620, 2026-09-05 17:00 EDT (AGENTS.md citations, dashboards, hyperliquid_data.db, sports_market.db, HL experiments, docstrings, .obsidian)
    author: claude-code/fable-5.1
  - id: llm-wiki-v2
    resource: https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
    title: LLM Wiki v2 - extending Karpathy's pattern with lessons from agentmemory
  - id: karpathy-llm-wiki
    resource: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
    title: llm-wiki (gist)
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format SPEC.md v0.2 (sources.usage_count, Attested Computation)
  - id: obsidian-bases-syntax
    resource: https://github.com/obsidianmd/obsidian-help/blob/master/en/Bases/Bases%20syntax.md
    title: "Obsidian Bases syntax (.base YAML: filters, formulas, properties, views, summaries)"
  - id: fomc-calendar
    resource: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
    title: FOMC meeting calendars 2026 (Sep 15-16, Oct 27-28, Dec 8-9 remaining)
  - id: bea-schedule
    resource: https://www.bea.gov/news/schedule
    title: BEA release schedule (machine-readable JSON)
  - id: journal-practice
    resource: https://journalplus.co/blog/what-to-write-in-trading-journal/
    title: What to write in a trading journal (before / during / after; confidence vs outcome)
  - id: prereg-practice
    resource: https://unbiased-alpha.com/how-to-avoid-backtest-overfitting-hypothesis-driven-strategy-discovery
    title: Hypothesis-first research and pre-registration against backtest overfitting
---

# Knowledge layer backlog (Phases 3+)

Round 97b, baseline 29b0620. Research only. Everything below is a proposal;
nothing was built. Scores: **Value** H/M/L to the desks' actual decisions,
**Effort** S (one round or less, one module) / M (one round, two or three
modules or a real-data replay) / L (two rounds or a ruling first). No item
touches a daemon, a dashboard, an entity note or a data folder; every write
stays inside the four owned folders through `pages.write_page`.

## 0. The one-paragraph version

Phase 2 gave Desk 3 a compiled memory. Desks 1, 2, 4 and 5 still have none:
27,916 cascade excursions, 9,312 basis windows, 96 sportsbook edges, nine
strategy stacks' walk-forwards and the whole tax rationale sit outside the
wiki. The handoff log cites 24 distinct Directives, Ratifications and numbered
Rulings that have no page. Only two dashboards print a shell twin, so the
Attested Computation layer the blueprint promised has two candidates, not
eleven. From the field, four ideas transfer cleanly (typed relations,
crystallised round digests, a calibration ledger, per-type staleness policy)
and four should be rejected on purpose (embeddings, forgetting curves,
self-healing lint, auto-ingest daemons). The recommended order is: compile
what already exists (Desk 1 registrations, directives, shell twins, the FOMC
calendar) before building anything new, then the CRM and the journal, then
the Obsidian-facing views.

## 1. Gaps the Round 95 audit left open (fresh scan)

| # | Finding at 29b0620 | Why it matters | Backlog item |
|---|---|---|---|
| G1 | `hyperliquid_data.db`: cascade_excursions 27,916 rows, basis_realised_windows 9,312, liquidation_clusters 1.86 M, whale_wallets 8,844; `cross_market_titans` 0 rows. Zero compiled pages for Desk 1. | The largest data store in DEV has the smallest wiki footprint. Item 14 (sweeper) is gated off with no post-hoc evidence page; Item 8's measured funding regime lives only in a dashboard. | B1, B2, B15 |
| G2 | `HyperLiquid/HL_Monarch/data/experiments/` holds three `*.meta.json` registrations (control, changes_vs_control, acceptance_bar, commitments, amendments, known_defect_not_fixed) plus the N=12 baseline. The experiments adapter only reads `cross_market/experiments/`. | Same discipline, other desk, not compiled. Smallest possible extension. | B3 |
| G3 | AGENTS.md cites 24 distinct `Directive N-N`, `Ratification N-N`, `Ruling N-N` (e.g. Directive 75-1 x2, Ruling 39-1 x2, Ratification 77-3) with no page. Only R1-R6 and R95 exist. | The law is still prose. Every round re-derives it by grep. | B4 |
| G4 | 62 "Round N complete" paragraphs (147 KB) are the de facto episodic memory; no Source Summary pages exist. | Crystallisation: the field's word for digesting completed work chains into standalone facts. The log cannot be trimmed (R95-E deferred) until its content has a home. | B5 |
| G5 | Only two dashboards print a "Shell twin" (lead_lag --check-data; risk_simulator --iterations 20000 --json). | The Attested Computation mapping (R95-C, declarative) has two real candidates plus the seven knowledge CLIs. The other dashboards have no reproducible twin at all, which is itself a finding. | B6, F1 |
| G6 | `edge_opportunities`: 96 rows, all sharp_book = pinnacle; moneyline 36, spread 24, totals 36. `fair_odds_measurements` 32. | Enough to seed a first sportsbook profile (which soft books lag Pinnacle, by market type) but only as evidence lists, not verdicts. | B8 |
| G7 | Module docstrings carry 14+ titled theses ("WHY THIS MODULE EXISTS, AND WHAT IT MOSTLY SAYS", "WHAT IT REFUSES, FAIL-CLOSED ON EVERY AXIS", "WHY INDEPENDENT ROUNDING IS THE WRONG FIX"). | Concept pages hiding in code; a refactor deletes them silently. | B12 |
| G8 | `.obsidian/daily-notes.json` and `templates.json` are empty: Daily Notes and Templates are enabled but unconfigured. | The journal has no template and human-authored pages have no frontmatter scaffold, so they will fail L1. | B10, B13 |
| G9 | `tax_calendar.py`: "THE QUARTERS ARE NOT QUARTERS" (Q2 is two months, due Jun 15); rates and statute rationale in `config.yaml` comments. | Deadlines are Events with windows; the rationale is Concept material with `dev.parameters` on the rates. | B7, B12 |
| G10 | FOMC 2026 remaining: Sep 15-16 (registered), Oct 27-28, Dec 8-9. Statement 14:00 ET, which is 18:00Z in September and October but 19:00Z in December (EST). SEP meetings: Mar, Jun, Sep, Dec. | Two more drills can be pre-registered today; the December UTC shift is exactly the copied-state trap. BEA publishes a JSON schedule; BLS exposes a data API but no confirmed schedule JSON. | B7 |
| G11 | C2 has nothing to check but Experiment tokens: no Market pages exist. | The check that would deprecate a resolved market has no subjects. | B9 |

## 2. What the field added since the gist, and what transfers

Read against Karpathy's three layers and OKF v0.2:

| Idea from the field | Source | Transfer to DEV | Verdict |
|---|---|---|---|
| Typed relationships between pages: `supersedes`, `contradicts`, `depends_on`, `caused`, `fixed` | LLM Wiki v2 | `dev.relations: [{type, target}]`; lint: `supersedes` chains acyclic, every `contradicts` names a resolving Ruling | adopt (B11) |
| Crystallisation: completed work chains digested into standalone facts | LLM Wiki v2 | round digests as Source Summary pages; lessons promoted to Concept pages | adopt (B5) |
| Consolidation pipeline: working -> episodic -> semantic -> procedural | LLM Wiki v2 / agentmemory | already implicit: raw -> Source Summary -> Concept/Regime -> Ruling/constitution. Name it in WIKI_SCHEMA.md s.7 so ingest knows which layer a fact has reached | adopt (doc only) |
| Confidence per fact with reinforcement and decay | LLM Wiki v2 | trading facts do not decay on a curve; they expire on an event (a market resolves, a rule is superseded). Use per-type `stale_after` policy instead | adapt (B14) |
| Ebbinghaus forgetting curves | agentmemory | wrong model for a ledger-backed desk | reject |
| Hybrid retrieval: BM25 + vectors + graph | LLM Wiki v2 | Karpathy's own scale note: index-first works to hundreds of pages. DEV has 36. Revisit above ~500 | defer |
| Self-healing lint | LLM Wiki v2 | limit to `--fix-safe` (index rebuild, log append, deprecate a gone Market). Anything that rewrites a claim is a human or Antigravity act | reject beyond fix-safe |
| Event-driven auto-ingest | LLM Wiki v2 | no new daemons. A scheduled task that runs `knowledge.lint --json` is the ceiling, opt-in, HALT-aware | reject as daemon; allow as task |
| Multi-agent mesh sync, shared vs private scopes | LLM Wiki v2 | two agents already coordinate through AGENTS.md and git; not needed | reject |
| `sources[].usage_count` / `usage_window` | OKF v0.2 | count how often a query opened a page; lets lint find pages nobody reads | adopt later (B16) |
| Attested Computation: `runtime`, `computation`, `executor.receipt`, `attester` | OKF v0.2 | the shell twins; declarative only per R95-C | adopt (B6) |
| Before / during / after journal; confidence 1-10 recorded before, scored after; expectancy over many trades | trading-journal practice | the journal (R95-F) plus a calibration ledger: pre-event probability vs outcome, Brier-scored | adopt (B10) |
| Write the hypothesis and the pass bar before the data; count the tests you ran | pre-registration practice | DEV already does this in `*.meta.json`; add a multiple-testing counter to Experiment pages (how many bars were tried) | adopt (B3, B14) |
| Bases: YAML views with filters, formulas, summaries over frontmatter | Obsidian 1.9-1.10 | `wiki/_views/*.base` generated from PAGE_TYPES so views never drift from the vocabulary | adopt (B13) |

## 3. The backlog

### 3a. Compile what already exists (Round 98)

| ID | Item | Value | Effort | Depends on | Lint / tests |
|---|---|---|---|---|---|
| B3 | Extend `ingest.experiments` to `HyperLiquid/HL_Monarch/data/experiments/*.meta.json` (control, changes_vs_control, acceptance_bar as `dev.parameters` by json_path, commitments, amendments, known_defect_not_fixed). Desk 1 gets its first Experiment pages, including the never-overwrite N=12 baseline as `dev.requires_files`. | H | S | none | C1 on the acceptance bars; a test fixture per file shape |
| B4 | `ingest.rulings --from AGENTS.md`: extract every `Directive N-N`, `Ratification N-N`, `Ruling N-N` with its paragraph, write `wiki/rulings/Ruling_D75-1.md` etc. as `status: draft`, `sources` -> `AGENTS.md#round-75-findings`, `dev.round` from the number. Antigravity verifies in batches (R95-D). 24 pages. | H | S | none | L3 needs the register or Desk pages to link them: extend the experiments register into a general "catalogue" page, or seed Desk pages with a rulings section that lists by desk |
| B6 | Attested Computation pages: the two shell twins plus the seven `knowledge` CLIs, from a static table (runtime python, computation = the command, executor.receipt = the `--json` keys, attester = the unit test that pins it). Declarative only (R95-C). | M | S | none | C1 asserts the module and the test function exist; a test that every `knowledge` CLI listed has a page |
| B7 | `ingest.calendar` from a committed `knowledge/calendars/fomc_2026.yaml` (Oct 27-28 -> statement 2026-10-28T18:00Z; Dec 8-9 -> 2026-12-09T19:00Z, EST). Event pages with `dev.window`, `dev.sep: true` for Dec, `status: draft` until rules are registered. Add estimated-tax deadlines from `tax_calendar` as Event pages with `stale_after` = the deadline. | H | S | none | C5 guards the windows; a test that the December UTC hour is 19, the copied-state trap made explicit |
| B9 | Market pages: seed `wiki/markets/<token>.md` for every token the wiki references (rules, Experiment `dev.tokens`) and, optionally, the fed-rates family from the newest macro drop. `resource: polymarket:token:<id>`, `dev.token_id`, question, condition_id, slug, neg_risk, first_seen. C2 finally has subjects; `--fix-safe` may set `status: deprecated` when the token leaves the drops. | M | S | none | C2 end to end on real drops; fixture drop with a vanished token |

### 3b. CRM and journal (Rounds 99-100)

| ID | Item | Value | Effort | Depends on | Lint / tests |
|---|---|---|---|---|---|
| B8 | `ingest.entities` (Phase 3 as planned): `crm/titans/` from `titan_identities_cache.json` (8 pairs) and `cross_market_titans`; `crm/sharps/` from `sharp_traders` (79); `crm/whales/` capped to the top 100 by account value from `whale_wallets` (8,844 rows is not a CRM); `crm/books/pinnacle.md` plus one page per soft book seen in `fair_odds_measurements.sportsbook`, with `dev.evidence` rows from `edge_opportunities` by market type. Judgement text is never overwritten; evidence appends. SQLite opened `mode=ro`. | H | M | none | a test that a re-ingest preserves hand-written judgement paragraphs; L3 via a `crm/_directory.md` hub |
| B10 | Journal (R95-F) with the zero-receipt reality: `journal/YYYY-MM-DD.md` is created only on demand or when receipts exist; a **calibration ledger** section records pre-event predictions (`event`, `claim`, `p`, `at`) and scores them after the Event page lands (Brier per claim, running mean). Debrief checks paper receipts against the Tax Reserve hurdle and Risk Sentinel drawdowns only. | H | M | B7 for the events; receipts folder | C4 (realised rows vs Trading_Taxes escrow) becomes possible; tests on a fixture receipts folder and a fixture Trading_Taxes note |
| B11 | Typed relations `dev.relations: [{type: supersedes\|contradicts\|depends_on\|measured_by\|enforced_in, target}]`. Lint L6: `supersedes` chains acyclic and the superseded page is `deprecated`; every `contradicts` names a Ruling that resolves it; `enforced_in` targets exist (a file) and `measured_by` targets are Experiment pages. | M | S | none | pure structural lint; fixtures with a cycle and an unresolved contradiction |
| B14 | Per-type staleness policy in WIKI_SCHEMA.md: Ruling 180 d, Concept 90 d, Market until resolution, Reaction Profile never, Event never, Journal never. Lint L7 warns when a page of a policed type lacks `stale_after`. Experiment pages gain `dev.tests_run` (how many bars or variants were tried) so the multiple-testing count is visible. | M | S | none | tests per type |

### 3c. Obsidian-facing and provenance (Round 101)

| ID | Item | Value | Effort | Depends on | Lint / tests |
|---|---|---|---|---|---|
| B13 | `knowledge.views` writes `wiki/_views/{rulings,experiments,markets,profiles,crm}.base` from PAGE_TYPES (filters on `type`, columns from the frontmatter families, a summary row). Configure Daily Notes folder -> `journal/` and Templates folder -> `wiki/_templates/` (these are `.obsidian/*.json`, operator-owned: propose, do not write). Templates: postmortem, memo, contact, statement with frontmatter pre-filled so human pages pass L1. | M | S | none | a test that every `.base` is valid YAML and names only known properties |
| B12 | `ingest.theses`: compile the titled docstring sections ("WHY THIS MODULE EXISTS", "THE THESIS", "WHAT IT REFUSES") of the desk modules into Concept pages with `dev.asserts` = the heading text in the module, so a deleted thesis paragraph is a C1 finding. Also the `config.yaml` statute rationale with `dev.parameters` on the rates. | M | M | none | fixture module with a thesis; C1 after deleting it |
| B16 | Query filing and usage: `knowledge query --file "<question>"` opens a Concept page scaffold with `sources` and appends a `**Query**` bullet; pages opened by a query get `dev.usage.count` and a `usage_window` (OKF). Lint L8: a page with zero usage in 90 days and no inbound link from a Desk page is a candidate for deprecation. | L | M | B11 | tests on the counter and the window |
| F1 | Phase 4 exporter change (ratified separately, exporter tests re-run): every dashboard prints a "Shell twin" line, and one wikilink to its Desk page. Until then B6 has two twins. | M | S | ruling | exporter tests |

### 3d. Desk 1 evidence and counterfactuals (Rounds 102+)

| ID | Item | Value | Effort | Depends on | Lint / tests |
|---|---|---|---|---|---|
| B1 | `ingest.cascades`: one Event page per cascade cluster from `cascade_excursions` (kind liquidation_cascade; coin, side, notional, event_px, MAE/MFE at 5 m from the table's own columns) and a Desk 1 Concept "cascade anatomy" with a `dev.history` table. Read-only, `mode=ro`, batched by watermark (the table has `measurement_watermarks`). | H | M | none | fixture DB; watermark resume test |
| B15 | Sweeper post-hoc evaluation (Item 14 is built gated-off): for each cascade Event, what `strategies/whale_sweeper.py` would have done and the excursion after it, as an Experiment page with a pre-registered acceptance bar written BEFORE the replay. The evidence page for un-gating, or for not un-gating. | H | L | B1, a ruling on the bar | replay on a fixture; the bar is in the registration, not the code |
| B2 | Funding regime Concept from `basis_realised_windows` (measured APR distribution vs the 25 % gross / 20 % net hurdle, coverage), refreshed by ingest, with the hurdle as `dev.parameters` on the harvester's constant. | M | M | none | C1 on the hurdle constant; C3 if the hurdle is stated elsewhere |
| B17 | Counterfactual paper P&L per event from the Reaction Profile series: `expected_profit` at each second capped by quarter-Kelly of the safe bankroll, summed over the first N seconds, as a section on the Event page. The roadmap's "10-50 % per event" checked against a number. | H | M | a recorded event (2026-09-16) | fixture curve; the cap comes from `monarch_hook` constants via `dev.parameters` |
| B18 | Quant lab walk-forward digests: one Experiment page per stack per run from `research/walk_forward.py` output (IS/OOS Sharpe, shortfall), and a second Regime family for CME session regimes from `engine/regime_detector.py`. | M | M | quant lab output format | fixture outputs |
| B19 | Git provenance check: L5 verifies `git:<sha>` resources with `git cat-file -e <sha>` (read-only) so a mistyped commit in a Ruling's sources is a finding. | L | S | none | fixture repo not needed: test the parser and skip when git is absent |
| B20 | Opt-in pre-commit hook running `knowledge.lint`; red lint blocks the commit. Touches `.git/hooks`, not a daemon; needs a ruling because it changes the operator's git workflow. | M | S | ruling | manual |

### 3e. Rejected or deferred, with reasons

- **Embeddings / hybrid retrieval**: 36 pages; index-first is the pattern's own recommendation to the hundreds. Revisit at ~500 pages.
- **Forgetting curves and confidence decay**: a market resolves or a rule is superseded; nothing about a Fed statement decays by half-life. `stale_after` policy (B14) and `supersedes` relations (B11) carry the same intent without a model that is wrong for the domain.
- **Self-healing lint**: anything beyond `--fix-safe` rewrites claims; that is a human or Antigravity act (constitution s.6).
- **Auto-ingest daemons**: the ecosystem has four daemons and a rule about not adding to them lightly. A scheduled lint task, opt-in and HALT-aware, is the ceiling.
- **Multi-agent mesh**: AGENTS.md and git already do this for two agents.
- **Writing `.obsidian/*.json`**: operator-owned. B13 proposes the settings; the operator sets them.

## 4. The five cards worth reading in full

**B4 Directives catalogue.** Regex over AGENTS.md for `(Directive|Ratification|Ruling) (\d+)-(\d+)` and `Ruling R(\d+)`; capture the enclosing bullet or paragraph; one page per distinct id, `title` = the id plus the first clause, body = every citing paragraph with its round, `sources` = `AGENTS.md#round-NN-findings` anchors, `dev.round` = the leading number, `status: draft`. Antigravity's batch ratification appends `verified` (R95-D). Twenty-four pages today. The register page pattern from Round 97 gives them inbound links; Desk pages then link the catalogue. Risk: paragraph boundaries in prose; mitigation: include the whole "Round N findings" section when a citation sits in one.

**B7 Calendar pre-registration.** A committed YAML, not a fetch: `{meeting: 2026-10-27/28, statement_utc: 2026-10-28T18:00:00Z, sep: false}` and `{meeting: 2026-12-08/09, statement_utc: 2026-12-09T19:00:00Z, sep: true}`. The adapter writes Event pages with `dev.window` = T-2..T+5 and `status: draft` until a rules file is registered (then `ingest.experiments` links them). The December entry is the reason this is a page and not a memory: 14:00 ET is 19:00Z after the clocks change. BEA's JSON schedule can feed PCE dates the same way later; BLS has no confirmed schedule JSON, so CPI and payroll dates stay hand-entered with the Fed calendar as the source.

**B10 Journal with a calibration ledger.** Every day so far has zero receipts, so the journal must be useful without trades. The ledger is the answer: before an Event the operator writes `claim: no change`, `p: 0.90`, `at`; after the Event page lands, the entry is scored (Brier = (p - outcome)^2) and a running table on `wiki/concepts/calibration.md` shows whether the operator's 90 % means 90 %. This is the trading-journal field's "confidence before, outcome after" made mechanical, and it costs nothing on a quiet day. The debrief section stays paper-only (R95-F).

**B11 Typed relations.** `dev.relations` with a closed vocabulary. The lint value is immediate and deterministic: a `supersedes` cycle is an error; a superseded page that is not `deprecated` is a warning; a `contradicts` without a Ruling target is an error (Karpathy: contradictions get flagged, here they get owed a ruling); `enforced_in` targets must exist on disk (C1-style). This is the cheapest way to make "the wiki has already flagged the contradictions" true rather than aspirational.

**B15 Sweeper post-hoc evaluation.** The one item that could change a live decision: Item 14 is gated off for want of evidence, and 27,916 excursions are sitting in a table. The order of operations is the whole point: register the acceptance bar as an Experiment page first (what MAE at 5 m, what hit rate, over which coins and sides would justify un-gating), then replay, then write the verdict page. The replay reads the DB `mode=ro` and the sweeper's rule as code; it places nothing and changes no gate. If the bar is not met, the page says so and the gate stays.

## 5. Rulings requested before Round 98

1. **Order**: Round 98 = B3 + B4 + B6 + B7 + B9 (all S, all compile-what-exists) as proposed, or pull B8 (CRM) forward.
2. **Directives catalogue verification**: batch ratification of the 24 extracted pages, or page by page.
3. **Calendar source of truth**: a committed YAML maintained by hand from federalreserve.gov (recommended), or a fetch.
4. **Market page scope**: only tokens the wiki already references (recommended), or the whole fed-rates family from the drops.
5. **Whale CRM cap**: top 100 by account value (recommended) or another cut.
6. **Staleness policy numbers** (B14): Ruling 180 d, Concept 90 d as proposed.
7. **Sweeper bar** (B15): the acceptance criteria must be registered before any replay; Antigravity to author them.
8. **Pre-commit hook** (B20) and **exporter shell twins** (F1): approve for Phase 4 or defer.

## 6. Sources

- Karpathy, *llm-wiki* gist: <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- *LLM Wiki v2* (agentmemory lessons): <https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2>
- OKF SPEC.md v0.2: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>
- Obsidian Bases syntax: <https://github.com/obsidianmd/obsidian-help/blob/master/en/Bases/Bases%20syntax.md>; overview: <https://got.md/obsidian-bases/>
- FOMC calendars: <https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm>; 2026 dates: <https://thriveinmarkets.com/calendar/indicator/fomc/>
- BEA release schedule (JSON): <https://www.bea.gov/news/schedule>; BLS data API: <https://www.bls.gov/bls/api_features.htm>
- Trading journal practice: <https://journalplus.co/blog/what-to-write-in-trading-journal/>; <https://www.tradezella.com/tools/trading-journal-template>
- Pre-registration and backtest overfitting: <https://unbiased-alpha.com/how-to-avoid-backtest-overfitting-hypothesis-driven-strategy-discovery>; <https://www.davidhbailey.com/dhbtalks/battle-quants.pdf>
- DEV gap scan at 29b0620, 2026-09-05 17:00 EDT (this document's `dev-gap-scan` source).
