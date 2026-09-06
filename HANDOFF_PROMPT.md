# Round 108 Handoff Prompt: Antigravity Cross-Check Ratification & Directives

**To**: Claude Code (Implementer)  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-06T06:50:00Z  
**Branch**: `master` | **Status**: Verified Clean (`git status` pristine)  
**Base Commit**: `eb49ae2` (Round 107)  

---

## 1. Round 107 Verification & Cross-Check Audit

Commit `eb49ae2` (Round 107: query cards, `rank_at_seed` frozen, volatile dashboards untracked) is **RATIFIED**.

### Test & Vault Verification Summary
- **Knowledge Suite**: 156 passed in 79.88s (11 new tests covering immutability, line budget, countdown units, missing event refusal, standing forecast surfacing, and `rank_at_seed` freezing).
- **Orderbook Sampler**: 20 passed in 0.56s.
- **Master Test Suites**: 1,314 (HL + Cross-market) + 223 (Sports) + 237 (Polymarket) + 546 (Tax) = **2,708+ passing offline**.
- **Vault State**: 423 pages + constitution. `python -m knowledge.lint` returns **0 errors, 0 warnings, CLEAN**.
- **Live Query CLI Tests**:
  - `python -m knowledge.query --drill-card fomc-2026-09-16` ran cleanly in 32 lines (budget < 60), verified immutability (vault SHA unchanged), surfaced standing forecast `p=0.90, change_bps == 0`.
  - `python -m knowledge.query --regime BTC` verified live, returning Tier 1 macro consensus and history.
  - `python -m knowledge.query --drill-card nonexistent` cleanly refused with exit 3, naming all 5 registered events.
- **Working Tree**: `git status` is 100% pristine. The untracking of `Cross_Market_Arb.md`, `Cross_Market_Titans.md`, and `Risk_Sentinel.md` eliminated exporter churn.

---

## 2. Architectural Rulings on Claude Code's 5 Inquiries

### Ruling R107-1.A — Drill Card Scope & Post-Print Copy-Paste Command
- **Scope Ratification**: **Approved**. Deliberately omitting live market prices and dynamic L2 depth is strictly compliant with `WIKI_SCHEMA.md` s.6. Dashboards carry live market numbers; rendering stale static quotes in a terminal card at T-2 would induce cognitive confusion during high-pressure execution.
- **Copy-Paste Ergonomics**:
  - In Step 2 of "AFTER THE PRINT, IN ORDER", the command contains an ellipsis:
    `2. python -m cross_market.latency_sniper --survival-curve ... --json > curve.json`
  - At T+1, an operator with elevated adrenaline should not have to recall flags.
  - **Directive**: Replace `...` with the exact, copy-pasteable CLI invocation:
    `python -m cross_market.latency_sniper --survival-curve --event event.json --rules <rules_rel_path> --books cross_market/data/clob_drill/<event_stem> --json > curve.json`
    (resolved directly from `rules.meta['dev']['registration']` or `cross_market/experiments/<event>.rules.json`).
  - In Step 1, explicitly state that `event.json` is to be written in the repository root (`./event.json`).

### Ruling R107-1.B — `--regime` Match Ambiguity & Exact-Match Priority
- **Ratification**: For read-only query cards, multi-page returns for exploratory queries are acceptable, but **exact-match priority must be enforced**:
  - If `want` matches an exact page stem (`p.path.stem == want`) or an unambiguous symbol prefix (e.g. `p.path.stem.startswith(want + "_")`), return **only that specific card**.
  - Fall back to substring matching across multiple pages only if zero exact matches are found.
  - If multiple partial matches exist without an exact match, display matches or note ambiguity.

### Ruling R107-1.C — Metadata Placement of `dev.rank_now`
- **Ratification**: **Ratified as standard OKF schema**.
  - `dev.rank_now` is a current scalar state attribute, completely distinct from `dev.rank_at_seed` (an immutable historical anchor) and `dev.evidence` (a time-series observation list).
  - Placing `rank_now` directly in `dev` allows `crm_register.md` to cleanly column on ranking drift across all tracked whales without array traversal.

### Ruling R107-1.D — Forward Enforcement: Lint L9 (Gitignore Wikilink Invariant)
- **Problem**: Untracking dashboards that have zero inbound links was safe, but nothing prevented future commits from linking to an ignored dashboard, which would silently break fresh clones during Lint L8.
- **Directive**: Implement **Lint L9 (Gitignore Wikilink Invariant)** in `knowledge/lint.py`:
  - Verify that no tracked/owned wiki page contains an inbound wikilink `[[target]]` that resolves exclusively to a file ignored by git (`git check-ignore`).
  - Flag as error: `[L9] ERROR <page>: [[<target>]] targets git-ignored file '<path>'; fresh clones will fail L8`.
  - Guard with `is_git_repo(dev_root)` to skip cleanly in non-git test fixtures (mirroring L5).

### Ruling R107-1.E — Structured `dev.rules` Schema & Token Truncation Fix
- **Problem**: In Round 107, `query.py` parsed rules from the rendered markdown table. The markdown table truncates token IDs to 12 chars (`561528276087…`), causing `query.py` to display truncated tokens at T-2. Parsing pipe tables is also fragile against future layout edits.
- **Directive**:
  1. In `knowledge/ingest/experiments.py:compile_rules_registration`, serialize `dev["rules"]` into frontmatter:
     ```python
     dev["rules"] = [
         {
             "label": r.get("label"),
             "condition": f"{r.get('field')} {r.get('op')} {r.get('value')}",
             "market": str(r.get("market", "")),
             "outcome": r.get("outcome_if_true"),
             "neg_risk": r.get("neg_risk", False),
         }
         for r in rules if isinstance(r, dict)
     ]
     ```
  2. In `knowledge/query.py:drill_card`, read `dev.get("rules")` directly. Print the full token ID without truncation. Fall back to markdown table parsing only if `dev.rules` is absent on legacy pages.
  3. Re-ingest experiments (`python -m knowledge.ingest.experiments`) to update `obsidian_vault/wiki/experiments/fomc_2026-09-16_rules.md`.

---

## 3. Scope & Deliverables for Round 108

### Deliverable 1: Implement Lint L9 in `knowledge/lint.py` & Test Suite
- Add `check_l9(docs, vault, dev_root)` to `knowledge/lint.py`.
- Run `git check-ignore` on resolved link targets; report any git-ignored target linked by a vault page.
- Add test coverage in `knowledge/tests/test_knowledge.py` verifying that linking to an ignored file fails L9 while untracked unlinked dashboards pass.

### Deliverable 2: Structured `dev.rules` Ingest & Token Display in Drill Card
- Modify `knowledge/ingest/experiments.py` to write `dev.rules` in pre-registration pages.
- Re-run `knowledge/ingest/experiments.py` so `fomc_2026-09-16_rules.md` receives `dev.rules`.
- Update `knowledge/query.py:drill_card` to consume `dev.rules` directly, displaying full token IDs.

### Deliverable 3: Polish Drill Card & Regime Query Ergonomics
- In `knowledge/query.py:drill_card`:
  - Provide the exact post-print command line for `latency_sniper --survival-curve` with `--event event.json`, `--rules <rules_path>`, and `--books <books_path>`.
  - Clarify that `event.json` is written to the repo root (`./event.json`).
- In `knowledge/query.py:regime_card`:
  - Prioritize exact stem/title matches before falling back to substring search.

### Deliverable 4: Documentation & Invariant Updates
- Update `WIKI_SCHEMA.md` s.7 to document Lint L9.
- Record Round 108 in `AGENTS.md` and `COMMANDS.txt`.
- Keep `HOMEWORK.md` updated.

---

## 4. Operational Reminders & Milestones

1. **Desk 1 Collector (`38548`)**:
   - Running pre-Round-106 code (5 ungated candidates/pass).
   - Operator can execute `restart_basis_collector.bat` at their leisure to activate the 25% gross spread gate.
2. **Calendar Milestones**:
   - **Sep 13–14**: Full Dress Rehearsal for FOMC Drill.
   - **Sep 15**: Q3 Estimated Tax Escrow Settlement ($2,700 NJ / $8,400 Federal).
   - **Sep 16 (13:58 EDT / 17:58Z)**: Live FOMC Drill. First command: `python -m knowledge.query --drill-card fomc-2026-09-16`.
3. **Pristine Working Tree**: Maintain zero uncommitted/untracked churn between rounds.
