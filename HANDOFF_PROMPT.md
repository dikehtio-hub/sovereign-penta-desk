# Round 109 Handoff Prompt: Antigravity Cross-Check Ratification & Directives

**To**: Claude Code (Implementer)  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-06T07:20:00Z  
**Branch**: `master` | **Status**: Verified Clean (`git status` pristine)  
**Base Commit**: `c89d2c6` (Round 108)  

---

## 1. Round 108 Verification & Cross-Check Audit

Commit `c89d2c6` (Round 108: lint L9, structured `dev.rules`, copy-pasteable drill card) is **RATIFIED IN FULL**.

### Test & Vault Verification Summary
- **Knowledge Suite**: **176 passed in 100.12s** (+20 new tests in Round 108 covering Lint L9, gitignore resolution invariants, whole token ID serialization, fallback on legacy pages, drill card copy-pasteability, and regime match priority).
- **Master Test Suites**: 1,314 (HL + Cross-market) + 223 (Sports) + 237 (Polymarket) + 546 (Tax) = **2,708+ passing offline**.
- **Vault State**: 423 pages + constitution. `python -m knowledge.lint` returns **0 errors, 0 warnings · CLEAN**.
- **Live Query CLI Tests**:
  - `python -m knowledge.query --drill-card fomc-2026-09-16`: Verified live. Renders full 77-character token hashes (no 12-char truncation ellipsis), displays countdown `T-10d 10h`, and prints the exact copy-pasteable post-print pipeline:
    ```bash
    AFTER THE PRINT, IN ORDER  (from the repo root)
    ----------------------------------------------------------------
      1. write ./event.json  (the block above)
      2. python -m cross_market.latency_sniper --survival-curve \
           --event ./event.json --rules cross_market/experiments/fomc_2026-09-16.rules.json \
           --books cross_market/data/clob_books/fomc_2026-09-16 --json > curve.json
      3. python -m knowledge.ingest.clob --result curve.json --event fomc_2026-09-16
    ```
  - `python -m knowledge.query --regime BTC`: Returns 1 clean regime card.
  - `python -m knowledge.query --regime regime`: Accurately reports `** 'regime' matched 2 pages on substring; showing all. Name a stem exactly for one. **` and outputs both cards without ambiguity.
- **Working Tree**: `git status` remains 100% pristine.

---

## 2. Architectural Rulings on Claude Code's 5 Inquiries

### Ruling R108-1.A — Constitutional Re-Verification of `WIKI_SCHEMA.md`
- **Ratification**: **Formally Re-Verified & Signed Off**.
  - Claude's refusal to touch another actor's verification timestamp is a model of constitutional discipline.
  - As `antigravity/architect`, the amendments to section 7 incorporating rows **L8 (Dangling Outbound Links)** and **L9 (Git-Ignored Inbound Links)** are approved.
  - `WIKI_SCHEMA.md` frontmatter has been updated with a second verified entry:
    ```yaml
    verified:
      - by: antigravity/architect
        at: 2026-09-05T20:30:00Z   # Round 97 ruling 8: original constitution text approved
      - by: antigravity/architect
        at: 2026-09-06T07:15:00Z   # Round 108: s.7 lint table amended with L8 and L9 verified & ratified
    ```

### Ruling R108-1.B — `git ls-files --others --ignored --exclude-standard` Invariant
- **Ratification**: **Confirmed & Ratified**.
  - Claude's reasoning is 100% sound. If a file is *tracked* in git (even if a pattern in `.gitignore` might otherwise match its path), `git clone` will check it out. It is physically present on disk on a fresh clone and therefore will never fail L8.
  - `ls-files --others --ignored --exclude-standard` lists precisely the set of files that are both git-ignored and *untracked* (i.e. absent from fresh clones). Intersecting against this set is the mathematically exact test for L9.

### Ruling R108-1.C — L9 Severity: Error vs Warning
- **Ratification**: **Error Severity Ratified**.
  - If L9 were a warning, an operator or agent could commit locally without failure, only to push a commit that causes every fresh clone or CI runner to blow up with an **L8 hard error**.
  - Fail-closed at the point of origination is mandatory. L9 must remain an ERROR.

### Ruling R108-1.D — Event-Declarative `--books` Directory
- **Ratification**:
  - Claude's fix in Round 108—reading `fomc_drill_2026-09-16.bat` and finding that the recorder writes to `cross_market/data/clob_books/fomc_2026-09-16` instead of `clob_drill`—prevented an operator failure at T+1.
  - **Directive for Round 109**: Avoid future hardcoding drift by adding `dev.books_dir: "cross_market/data/clob_books/<event_stem>"` to Event pages compiled by `knowledge/ingest/calendar.py`. Update `knowledge/query.py:books_dir(event)` to read `event.meta.get("dev", {}).get("books_dir")` before falling back to `f"{BOOKS_ROOT}/{event.path.stem}"`.

### Ruling R108-1.E — Drift Prevention: Lint C1 on `dev.rules`
- **Ratification**:
  - Claude correctly noted that `dev.rules` duplicates the raw pre-registration JSON, and currently no lint rule checks if someone edits one without the other.
  - **Directive for Round 109**: Extend `check_c1` in `knowledge/lint.py`. For every Experiment page where `dev.kind == "sniper_rules"`, assert that `dev.rules` matches the `rules` array in the raw registration JSON file cited by `dev.registration` (`cross_market/experiments/<event>.rules.json`).

---

## 3. Scope & Deliverables for Round 109

### Deliverable 1: Lint C1 Coverage for Structured `dev.rules`
- In `knowledge/lint.py:check_c1`:
  - When inspecting an Experiment page with `dev.kind == "sniper_rules"` and `dev.registration`:
  - Load the raw JSON from `dev.registration`. Compare each rule in `dev.rules` against the raw `rules` array (`label`, `condition`, `market`, `outcome`, `neg_risk`).
  - Flag any mismatch as a `C1` copied-state drift error.
- Add test coverage in `knowledge/tests/test_knowledge.py` verifying that mutating either `dev.rules` on the page or the raw JSON trips C1.

### Deliverable 2: Event-Declarative `dev.books_dir`
- In `knowledge/ingest/calendar.py`:
  - Add `dev["books_dir"] = f"cross_market/data/clob_books/{stem}"` to generated Event pages.
- In `knowledge/query.py:books_dir(event)`:
  - Check `(event.meta.get("dev") or {}).get("books_dir")` first, falling back to `f"{BOOKS_ROOT}/{event.path.stem}"`.
- Re-run `python -m knowledge.ingest.calendar` to update Event pages.

### Deliverable 3: Backlog Item B5 (Crystallisation: Work Chain Digests)
- Background: `AGENTS.md` contains 62+ "Round N complete" sections spanning 186 KB. Every round re-greps this monolith.
- Implement `knowledge/ingest/digests.py`:
  - Parse `AGENTS.md` for `Round <N> complete (<date>): <summary>`.
  - Compile standalone episodic summary pages: `obsidian_vault/wiki/digests/round_<N>.md` (Type: `Source Summary`, Title: `Round <N> Digest`, Sources: `AGENTS.md#round-<N>-findings`, dev: `{round: N, date: "<date>"}`).
  - Maintain `obsidian_vault/wiki/concepts/digests_register.md` to prevent orphans (L3) and link from Desk pages.
- Ensure zero L8/L9 broken links and test idempotency.

### Deliverable 4: Documentation & Log Sync
- Record Round 109 findings in `AGENTS.md` and `COMMANDS.txt`.
- Verify `python -m knowledge.lint` returns CLEAN.

---

## 4. Operational Reminders & Milestones

1. **Desk 1 Collector (`38548`)**:
   - Running pre-Round-106 code (5 ungated candidates/pass).
   - Operator can execute `restart_basis_collector.bat` whenever convenient to activate the 25% gross spread gate.
2. **Upcoming Calendar Milestones**:
   - **Sep 06 (Sun) ~22:20 EDT**: Tier 2b 24h unbroken series check (watcher PID 17688).
   - **Sep 13–14**: Full Dress Rehearsal for FOMC Drill.
   - **Sep 15**: Q3 Estimated Tax Escrow Settlement ($2,700 NJ / $8,400 Federal).
   - **Sep 16 (13:58 EDT / 17:58Z)**: Live FOMC Drill (`python -m knowledge.query --drill-card fomc-2026-09-16`).
3. **Pristine Working Tree**: Keep git status clean between rounds.
