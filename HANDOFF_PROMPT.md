# Round 113 Handoff: Architectural Cross-Check & Directives

**To**: Claude Code (Senior Implementation Engineer / Test Master)  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-06T14:15:00Z  
**Subject**: Round 112 Independent Cross-Check, Formal Ratification of Rulings (R112-1.A – R112-1.F), and Directives for Round 113  

---

## 1. Executive Summary & Verification of Round 112 (`9c87c5c` & `ce190c0`)

- **Commits Inspected**: `9c87c5c` (*feat: Round 112 - dev.progress + lint L10, registers hub, slug digest, regime_filtered_v1 parked*) and `ce190c0` (*docs: Round 112b*).
- **Independent Cross-Check Results**:
  1. **Commit Statistics**: Matched exactly (25 files, +637 / −126).
  2. **Test Suite Telemetry**:
     - `knowledge/tests`: **263 passed in 193.46s** (+30 tests). All green offline.
     - `python -m knowledge.lint`: **493 pages + constitution · 0 error(s) · 0 warning(s) · CLEAN**.
  3. **Idempotence Verified**: Ran two full cycles of `knowledge.seed`, `knowledge.ingest.experiments --force`, and `knowledge.ingest.digests`. A single transient timestamp sync on `registers_register.md` was caught and aligned (`b3c4493`); subsequent passes produced **zero changed files**.
  4. **L10 Positive Probe**: In-memory test confirmed:
     - Baseline vault: 0 L10 warnings.
     - Setting `dev.progress.status: accumulating` on `regime_filtered_v1` in memory fired exactly **1 L10 warning**:
       `[L10] WARNING: wiki/experiments/regime_filtered_v1_meta.md: registered 5 day(s) ago with 0 recorded progress toward 50 closed_trades; park, retire, or accumulate`.
     - Setting `accumulated: 7` completely silenced the warning.
  5. **Drill Card Contract Test**: `python -m knowledge.query --drill-card fomc-2026-09-16` outputs exactly 37 lines (<60 lines), renders full 76-digit decimal tokens, and leaves `git status` 100% pristine (zero writes).
  6. **Working Tree**: Pristine. Zero daemons touched or restarted.

---

## 2. Formal Architectural Rulings (R112-1.A through R112-1.F)

### Ruling R112-1.A — Parking Mechanism (Amendment + `dev.progress.status`)
- **Ratification**: **Formally Ratified**.
- OKF v0.2 `frontmatter.STATUSES` is strictly `draft | stable | deprecated`. Setting a top-level `status: parked` would have violated WIKI_SCHEMA and failed Lint L1.
- Recording the park as an explicit, dated `action: parked` entry in the registration's own `amendments` list, alongside `dev.progress.status: parked`, maintains document lifecycle compliance while honestly declaring experiment lifecycle status.

### Ruling R112-1.B — Parking Rationale & `not_cited_as_evidence`
- **Ratification**: **Formally Ratified & Commended**.
- The previous draft rationale conflated Item 14's liquidation-cascade sweeper with `regime_filtered_v1`'s passive fade with trend-gate, misread an `INSUFFICIENT` verdict as `FAIL`, and cited a sub-sample side split.
- The amendment in `regime_filtered_v1.meta.json` now grounds the park in factual truth: 5 days at N=0, no daemon process running, the documented 600s vs 1,224s ATR hold-time mismatch, and zero calendar space before the FOMC drill.
- The `not_cited_as_evidence` block is an exemplary standard of audit integrity.

### Ruling R112-1.C — `passive_fade_rebenchmark` & the "Ready / Unevaluated" State
- **Ratification**: **Option 2 Approved for Round 113**.
- `passive_fade_rebenchmark` has accumulated 19,008 events against a 500-event floor.
- An experiment sitting indefinitely above its required sample floor without an evaluation verdict is the exact mirror image of L10 (the same "silence" failure mode).
- **Directive for Round 113**:
  1. In `knowledge/ingest/experiments.py`, set `dev.progress.status: ready` when `accumulated >= target` and no verdict page exists.
  2. Implement **Lint Rule L11 (Warning)**: An Experiment page whose sample floor has been met for $>3$ days without a linked verdict page emits:
     `[L11] WARNING: sample floor met (X >= Y) N day(s) ago without recorded verdict; evaluate or retire.`

### Ruling R112-1.D — Lint L10 Semantics
- **Ratification**: **Formally Ratified**.
- Keying L10 strictly on `dev.progress.status == "accumulating"` and `accumulated in (0, 0.0)` ensures zero false alarms on parked or unmeasured registrations.
- Retaining L10 as a non-blocking `warning` ensures human operators retain agency over research decisions.

### Ruling R112-1.E — Preservation of `measured_at`
- **Ratification**: **Formally Ratified**.
- `measured_at` represents "when this value was last observed to CHANGE". Preserving it across identical measurements prevents the R104-3 restamp churn. A secondary `checked_at` field is explicitly rejected as unnecessary git noise.

### Ruling R112-1.F — STALL_DAYS Single Ownership
- **Ratification**: **Owned by `knowledge/ingest/experiments.py`**.
- The ingest adapter owns the domain lifecycle constants; `knowledge/lint.py` shall import `STALL_DAYS` from `knowledge.ingest.experiments`. (Scheduled for Round 113).

---

## 3. Scope & Deliverables for Round 113

### Deliverable 1: Deduplicate `STALL_DAYS` (R112-1.F)
- Export `STALL_DAYS = 3` from `knowledge/ingest/experiments.py`.
- Import `STALL_DAYS` in `knowledge/lint.py` and remove the duplicate definition.

### Deliverable 2: Implement "Ready" Status & Lint L11 (R112-1.C)
- Update `knowledge/ingest/experiments.py`:
  - When `accumulated >= target` and no corresponding `_verdict` page exists, mark `dev.progress.status: ready`.
  - Ensure `experiments_register.md` renders `19,008/500 (100%) · ready`.
- In `knowledge/lint.py`, implement **Lint L11 (Warning)**:
  - Check for registrations where `dev.progress.status == "ready"` whose `registered_utc` or `floor_met_utc` is $>3$ days old.
  - Add positive in-memory test coverage in `test_knowledge.py`.

### Deliverable 3: Desk 4 Debt Cleanup (`pytest.importorskip`)
- In `quant_trading_lab` tests currently failing collection due to missing `fastapi` in the local environment, add `pytest.importorskip("fastapi")` or clean conditional skips so running `pytest` across the entire workspace collects and executes cleanly.

### Deliverable 4: Pre-FOMC Drill Rehearsal Script
- Build `knowledge/drills/fomc_rehearsal.py`:
  - Validates `fomc_2026-09-16.rules.json` and `fomc_2026-09-16_rules.md`.
  - Simulates the T-2 drill execution (`python -m knowledge.query --drill-card fomc-2026-09-16`), asserting zero file writes, under 60 lines, and correct countdown calculation.
  - Queries Windows Task Scheduler via `Get-ScheduledTask -TaskName Monarch_FOMC_Drill` to verify battery settings and report whether AC power is guaranteed.

### Deliverable 5: Documentation & Log Sync
- Record Round 113 findings in `AGENTS.md` and `COMMANDS.txt`.
- Recompile digests with `python -m knowledge.ingest.digests`.
- Verify `python -m knowledge.lint` returns **0 error(s), 0 warning(s), CLEAN**.
- Maintain pristine git working tree.

---

## 4. Operational Reminders & Upcoming Milestones

1. **Tonight ~22:20 EDT**: Tier 2b 24-hour unbroken series gate closes (watcher PID 17688). Laptop must remain awake and plugged into AC.
2. **Sep 13–14**: Full dress rehearsal for the live FOMC drill.
3. **Sep 15**: Q3 Estimated Tax Escrow Settlement.
4. **Sep 16 (13:58 EDT / 17:58Z)**: Live FOMC Rate Decision CLOB Drill.
