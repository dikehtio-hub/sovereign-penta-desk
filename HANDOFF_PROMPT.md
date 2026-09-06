# Round 112 Handoff: Architectural Cross-Check & Directives

**To**: Claude Code (Implementer / Desk Architect)  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-06T13:25:00Z  
**Subject**: Round 111 Cross-Check Audit (`84d0f70` & `cde570f`), Rulings on the Out-of-Band N=50 Experiment Finding, and Directives for Round 112  

---

## 1. Executive Summary & Verification of Round 111 (`84d0f70` & `cde570f`)

- **Commits Inspected**: `84d0f70` (*feat: Round 111 - query filing, opt-in usage counting, register summary column*) and `cde570f` (*fix: Round 111b - remove smoke-test artifacts*).
- **Test Telemetry**:
  - `knowledge/tests`: **233 passed in 142.45s** (+21 tests). All green offline.
  - `python -m knowledge.lint`: **491 pages + constitution · 0 error(s) · 0 warning(s) · CLEAN**.
  - All desk test suites (HyperLiquid, Cross-Market, Sports, Polymarket, Tax) pass cleanly offline.
- **Working Tree**: Pristine. Zero daemons touched or restarted.
- **Architectural Findings**:
  - **T-2 Window Crash Averted**: Claude correctly diagnosed that unconditional usage counting inside `write_page` would raise `WriteRefused` on the FOMC Event page inside its active window (`17:58Z–18:05Z`), crashing the drill card with a traceback two minutes before a Fed statement. Scoping usage counting behind `--count-usage`, and skipping windowed pages even when flagged, preserves the foundational Round 107 zero-write read guarantee.
  - **Pipe-Escaping Hardening in `registers._cell`**: `md_cell` was moved to `pages.py` and pipe-escaping applied across all ten registers, preventing phantom column growth.
  - **Smoke-Test Hygiene (111b)**: Invented query and test usage counts cleanly removed from the real vault before handoff.
  - **Single-Writer Summary Column**: `description` successfully populated in `digests_register.md` via the generic `SPECS` path.
  - **Durable Truncation Warning**: Clipped digest entries now log a durable `**Warning**` bullet to `obsidian_vault/log.md`.

---

## 2. Architectural Rulings on Round 111 Inquiries

### Ruling R111-1.A — Ratification of Opt-In Usage Counting (`--count-usage`)
- **Ratification**: **Formally Ratified & Praised**.
  - A query that mutates during a live drill is a fatal architectural hazard. The rule established in Round 107 stands: the drill card must **never** write.
  - Narrowing the directive from unconditional counting to `--count-usage`—and fail-closing by skipping windowed pages—was the correct decision.
  - Counting is strictly an offline maintenance tool, not a real-time side effect of operator queries.

### Ruling R111-1.B — In-Frontmatter `dev.usage` vs Sidecar Ledger
- **Ratification**: **In-Frontmatter Placement Retained**.
  - Keeping `dev.usage` in page frontmatter conforms to OKF v0.2 and allows Obsidian Bases views and static lint rules to read usage without querying a sidecar ledger or database.
  - Because `--count-usage` is strictly opt-in, page mtimes and git working trees remain untouched during standard query invocations.

### Ruling R111-1.C — Register Consolidation (Master Catalogue Hub)
- **Ratification**: **Approved for Round 112**.
  - Ten register links at the top of every Desk note is visual bloat.
  - In Round 112, introduce a master catalogue hub `obsidian_vault/wiki/concepts/registers_register.md` that indexes all 10 individual registers (`experiments`, `rulings`, `computations`, `events`, `markets`, `crm`, `journal`, `theses`, `digests`, `queries`).
  - Desk pages can then link `[[registers_register|Registers catalogue]]` in a single line (or a compact 2-column table), satisfying Lint L3 while keeping Desk pages focused on trading items.

### Ruling R111-1.D — Filed-Query Slug Collision Prevention
- **Ratification**: **Approved for Round 112**.
  - Truncating query slugs at 60 characters risks filename collisions for questions with identical opening phrasing.
  - **Directive for Round 112**: Update `knowledge/query.py:file_query` to append a deterministic 4-character SHA-256 hash suffix based on the entire question string:
    `query_{slug_prefix}_{hash4}.md`.
  - This guarantees collision-free uniqueness while preserving readable human prefixes.

### Ruling R111-1.E — `dev.usage.window_days: 90` Policy
- **Ratification**: **Confirmed as Self-Documenting Metadata**.
  - `window_days: 90` is preserved as standard schema metadata.
  - Automated deprecation linting is deferred until post-FOMC drill operational runtime has accumulated.

---

## 3. Architectural Rulings on Out-of-Band Finding (The Stalled N=50 Experiment)

### Context & Diagnosis
- `regime_filtered_v1` was pre-registered on `2026-09-01T04:40:14Z` with an acceptance bar requiring `min_closed_trades: 50`.
- Telemetry audit confirms `closed_trades: 0`, `trade_history: []`, and `paper_trading_state.json` last modified 122.9 hours ago (80 minutes post-registration).
- The strategy has a documented structural flaw in `known_defect_not_fixed` (`FADE_POSITION_MAX_HOLD_SECONDS = 600s` vs median 1,224s to reach 1.0×ATR target, forcing >50% of trades into time-stop coin flips).
- Furthermore, Round 104's historical cascade replay over 28,500+ excursions already issued an `INSUFFICIENT` / `FAIL` verdict on the cascade fade thesis (momentum persists; fade ratio 0.2787, P=0.0103).
- Launching an unmonitored paper trader now for 50 trades would burn compute and distract from the Sep 16 FOMC drill on a mathematically defective configuration.

### Ruling R112-OOB.1 — Disposition of `regime_filtered_v1` (Option 2: Formally Park)
- **Ruling**: **Option 2 (Formally Park) Approved & Mandated**.
  - Update `obsidian_vault/wiki/experiments/regime_filtered_v1_meta.md` and `regime_filtered_v1.meta.json`:
    - `status: parked`
    - Add an explicit callout note:
      ```markdown
      > [!NOTE]
      > **PARKED (2026-09-06)**: Pre-registered 2026-09-01. Zero closed trades accumulated (N=0). Formally parked unflown due to documented `known_defect_not_fixed` (600s force-close vs 1,224s ATR reach) and historical cascade replay failure (Round 104: momentum persists). Archived N=12 control preserved; any retuned trial requires a fresh pre-registration.
      ```
  - This honestly halts the illusion of an active trial while keeping the pre-registration record and N=12 control intact.

### Ruling R112-OOB.2 — Progress Tracking & Stalled Pre-Registration Linting
- **Ruling**: **Approved for Experiment Ingest & Linting**.
  1. **Page Schema**: Experiment pages with sample size requirements shall carry:
     ```yaml
     dev:
       progress:
         accumulated: 0
         target: 50
         unit: closed_trades
         status: parked # values: accumulating, completed, parked, insufficient
         measured_at: '2026-09-06T04:55:00Z'
     ```
  2. **Register Column**: Add `progress` to `SPECS["Experiment"]` in `knowledge/registers.py` so `experiments_register.md` renders `0/50 (0%) · PARKED` or `12/12 (control)` or `PASS/FAIL`.
  3. **Lint Rule L10 (Stalled Pre-Registration Warning)**:
     - An Experiment page registered $>3$ days ago with `dev.progress.accumulated == 0` and `status == "draft"` (unparked) emits a **Lint L10 Warning**:
       `Experiment registration has 0 recorded progress after N days; park, retire, or accumulate.`
     - Warning only (non-blocking), ensuring silent stalls are impossible in the future.

### Ruling R112-OOB.3 — Scope across Other Registrations
- `passive_fade_rebenchmark` is explicitly `status: PASSIVE` (sweeps accumulate in DB without trading) and was already evaluated in Round 104 (`whale_sweeper_cascade_replay_verdict.md`). Mark its `dev.progress.status` as `evaluated (Round 104)`.

### Ruling R112-OOB.4 — Sequencing with Round 112
- Incorporate this resolution directly into Round 112 as **Deliverable 4**. This packages the structural fix immediately without derailing the 3 planned deliverables.

---

## 4. Scope & Deliverables for Round 112

### Deliverable 1: Collision-Free Filed-Query Slugs
- In `knowledge/query.py`:
  - Update `file_query` slug generator to append a 4-character hex hash: `f"{slug[:54]}_{hash4}"`.
  - Add test coverage in `knowledge/tests/test_knowledge.py` verifying that two questions identical for the first 60 characters file to separate pages.

### Deliverable 2: Master Register Catalogue Hub
- Build `wiki/concepts/registers_register.md` indexing the 10 registers.
- Update `knowledge/registers.py` and `knowledge/seed.py` so Desk pages link the master catalogue hub cleanly (`[[registers_register|Registers catalogue]]`).
- Verify `python -m knowledge.seed` and full test suite remain 100% green with zero L3/L8 findings.

### Deliverable 3: Pre-FOMC Drill Query Card Verification Test
- Add an explicit unit test in `knowledge/tests/test_knowledge.py` verifying:
  - `knowledge.query.drill_card("fomc-2026-09-16")` renders in under 60 lines.
  - Output contains the full 128-bit/hex token IDs.
  - Zero files are written (working tree remains pristine).

### Deliverable 4: Formally Park Stalled Experiment & Wire `dev.progress`
- Update `regime_filtered_v1_meta.md` and `regime_filtered_v1.meta.json` to `status: parked` with the dated explanation callout.
- Add `dev.progress` support in `knowledge/ingest/experiments.py` and add `progress` column to `SPECS["Experiment"]`.
- Implement Lint L10 warning for unparked stalled experiments $>3$ days old.
- Update tests to verify L10 warning behavior.

### Deliverable 5: Documentation & Log Sync
- Record Round 112 findings in `AGENTS.md` and `COMMANDS.txt`.
- Verify `python -m knowledge.lint` returns **0 error(s), 0 warning(s), CLEAN**.
- Maintain pristine git working tree.

---

## 5. Operational Reminders & Milestones

1. **Monarch_FOMC_Drill Battery Setting (Crucial Operator Note)**:
   - `Monarch_FOMC_Drill` has `DisallowStartIfOnBatteries: True` and `StopIfGoingOnBatteries: True`.
   - `HOMEWORK.md` is updated. Keep AC adapter plugged in on Sep 16, or run:
     ```powershell
     Set-ScheduledTask -TaskName "Monarch_FOMC_Drill" -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries)
     ```
2. **Upcoming Calendar Milestones**:
   - **Tonight ~22:20 EDT**: Tier 2b 24h unbroken series check (watcher PID 17688).
   - **Sep 13–14**: Full Dress Rehearsal for FOMC Drill.
   - **Sep 15**: Q3 Estimated Tax Escrow Settlement ($2,700 NJ / $8,400 Federal).
   - **Sep 16 (13:58 EDT / 17:58Z)**: Live FOMC Drill (`python -m knowledge.query --drill-card fomc-2026-09-16`).
3. **Pristine Working Tree**: Keep git status clean between rounds.
