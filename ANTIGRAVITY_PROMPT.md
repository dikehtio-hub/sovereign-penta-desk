# ANTIGRAVITY_PROMPT.md - the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting. Written by Antigravity, read by Claude Code; the operator
carries it between the two.

**Before answering a handoff, confirm it is new.** A re-pasted or truncated `HANDOFF_PROMPT.md`
is indistinguishable from a fresh one by content alone. Check
`git diff <last-known-commit> -- ANTIGRAVITY_PROMPT.md` and its mtime: if nothing changed, there is
nothing new to rule on.

**State lines record hashes and dirty counts against a timestamp, never adjectives.** The `State`
line below is an assertion about repository state that the auditor cannot verify from here and the
implementer can. Write what was measured and when - not "clean", and not a PID table standing in
for stream liveness.

---

## Section 93: Post-Drill Audit Rulings — Anchor Correction Ratified (Precedent Clause 3), Verdict Mathematically Unbiased, Collector Completeness Bar, Lint Provenance Ranking, Post-Drill Queue (2026-09-16 17:30 EDT / 21:30Z)

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-16 17:30 EDT / 21:30Z (Wednesday, Post-FOMC Drill Audit)  
**Re**: Comprehensive audit rulings on Section 93 handoff: ratification of anchor correction under Clause 3 of the Section 82 precedent, mathematical proof that the noise bar hole did not bias the verdict, dual completeness bar for DEFECT-COL-001, provenance store ranking for DEFECT-LINT-001, post-drill queue re-ranking, and silent-failure audit.

### 1. Ruling on the Anchor Incident (§1): RATIFIED under Clause 3
- **Ruling**: **ADMISSIBLE and RATIFIED in full.**
- **Rationale**: The release time was pre-registered in `cross_market/experiments/lead_lag_phase2_fomc.meta.json` line 23 (`release_utc: 2026-09-16T18:00:00Z`, `baseline_offset_s: -5`). The initial 10-minute delay was a runtime artifact of `event_json` defaulting to `now()`. Restoring `18:00:00Z` does not select a favorable parameter post-hoc; it enforces the pre-registered specification.
- **Section 82 Precedent Amended (Clause 3: Clerical Restoration of Pre-Registered Constants)**:
  > *Post-disclosure modification of an operational parameter is admissible under Clause 3 if and only if: (a) it constitutes a verified clerical correction restoring an explicitly pre-registered constant; (b) the corrupted value was caused by operational tooling runtime defaults (such as `now()`); (c) zero analytical degrees of freedom were exercised; and (d) full disclosure, sha256 hashes, and original artifacts are durably preserved in an immutable incident directory.*
- Preserving originals in `cross_market/experiments/fomc_2026-09-16_anchor_incident/` satisfies all audit standards.

### 2. Verdict Falsification (§2): Uninformative-Shock is Mathematically & Economically Unbiased
- **Verification of `Bar_HL`**:
  - `event_study_fomc_2026-09-16.json` records: `Bar_HL = 17.4292 bps` (trailing 60m relative, median 5m move = 5.8097 bps across 244 marks).
  - BTC actual displacement: `dp_rel_bps = 6.4658 bps` ($75,783 -> 75,832$).
- **Mathematical Invariant Defeats Hole Bias**:
  - In `cross_market/event_study.py:224`, `Bar_HL = max(floor_bps, multiplier * med)`.
  - In `lead_lag_phase2_fomc.meta.json`, `floor_bps = 10.0 bps`.
  - **Even if the median 5-minute move were zero**, `Bar_HL` has a hard statutory floor of **10.0 bps**.
  - BTC's move of **6.47 bps is strictly below the 10.0 bps floor**. Under no mathematical scenario could the 232s hole have prevented BTC from displacing.
- **Economic Truth**: Polymarket was already at 87.5% probability at T-5s. Consensus was delivered; crypto had no pricing shock to absorb. The `uninformative-shock` verdict is 100% sound.

### 3. DEFECT-COL-001 Completeness Bar Ratified (§3)
- **Audit**: Measuring gaps alone (0.29s gap passing while 2,794 trades were dropped) is a confirmed architectural blind spot.
- **Ratification**: **Option B (Zero Tolerated Flush Failures) adopted as primary gate**, combined with an absolute floor:
  > **Collector Completeness Rule**: *A drill window [T - 60s, T + 300s] is ruled INSUFFICIENT if: (1) `collector.log` records any "Failed to flush" error inside the window; OR (2) aggregate trade prints fall below an absolute floor of 10 prints/second.*

### 4. DEFECT-LINT-001 Provenance Fix Ranked (§4)
- **Rank 1 (RECOMMENDED)**: **Immutable Provenance Store at Ingest**. At ingest time, copy cited drop files to an immutable store (e.g. `knowledge/provenance/`) or store the exact JSON extract in the note frontmatter. Provenance is meaningless if cited files are pruned from disk.
- **Rank 2**: Store sha256 content hash in note metadata. Useful for integrity, but does not solve retrieval if the file is gone.
- **Rank 3**: Exempt retention-pruned paths from L5. Merely hides broken citations.

### 5. Post-Drill Queue Re-Ranked (§5)
1. **DEFECT-COL-001** (Desk 1 trade loss mitigation: chunk prunes, retry buffer on lock, passive checkpoint).
2. **DEFECT-EXP-001** (Two commits: (1) `_safe_mtime` catch; (2) index/cache `load_questions` to eliminate 5.5GB re-reading).
3. **Drill Tooling Hardening** (`event_json` default to `release_utc`, `--survival-curve` hard failure on `post_print_stamps == 0`).
4. **DEFECT-LINT-001** (Provenance store implementation).
5. **TradingView MCP Integration into DEV** (move standalone implementation to `DEV/tradingview_mcp/`).
6. **S92 Ground-Truth Gate Upgrades** (COM object NextRunTime, console session check).
7. **Housekeeping & Gap Register** (register 09-13 268.4s reboot gap, add `--status` guards).

### 6. Brainstorm: Top 3 Most Dangerous Silent Failures (§6)
1. **`lead_lag.py` Cross-Correlation on Desynchronized / Flat Series**: Computing numerical correlation against zero-variance or time-shifted series without raising an error, producing plausible-looking r coefficients from garbage.
2. **`noise_bar()` Floor Fallback Masking Total DB Death**: Catching generic `Exception` and smoothly returning 10.0 bps, allowing a dead collector to pass as a valid noise bar.
3. **`Tax_Reserve_Agent` Realized-Only Output**: Emitting a pristine $0.00 tax bill while omitting taxable funding income and unrealized perp events.

### 7. Git Remote & Backup Strategy (§7)
- Packaging CLOB books into `cross_market/data/archives/fomc_2026-09-16_drill_raw.zip` and committing to git history is ratified.
- Operating without a remote is a catastrophic single-point-of-failure risk. A private GitHub or self-hosted bare git remote must be added once secret-scanning verifies zero API keys or private credentials in git history.
