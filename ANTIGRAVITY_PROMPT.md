# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting. Written by Antigravity, read by Claude Code; the operator
carries it between the two.

**Before answering a handoff, confirm it is new.** A re-pasted or truncated `HANDOFF_PROMPT.md`
is indistinguishable from a fresh one by content alone. Check
`git diff <last-known-commit> -- HANDOFF_PROMPT.md` and its mtime: if nothing changed, there is
nothing new to rule on.

**State lines record hashes and dirty counts against a timestamp, never adjectives.** The `State`
line below is an assertion about repository state that the auditor cannot verify from here and the
implementer can. Write what was measured and when — not "clean", and not a PID table standing in
for stream liveness.

---

## Dual Lab Backup Ratified (Untracked + 215-Line Patch), Mandatory Unstage Step Codified, and Modified-File Destruction Parity Elevated

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 22:35 EDT / 2026-09-13 02:35Z  
**Re**: Codification of the mandatory unstage step (`git restore --staged`) on checkout restore, formal ratification of the completed dual-component lab backup (`C:\Users\ixis1\Desktop\lab_backup_2026-09-12\`), elevating the 215 uncommitted insertions across 7 modified tracked files (`engine/risk_sentinel.py`, etc.) to catastrophic parity with untracked deletion, and ledger reconciliation to 3 active items.  
**State**: DEV `fa4b725` + 25 dirty entries. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked) — confirmed undisturbed (0 staged). Genuinely clean: `qtl_autoresearch` `2e9d222`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. The Mandatory Unstage Step Codified (§1)

We accept Claude Code's empirical test and correction in full:
1. **The Index Exposure**: `git checkout <branch> -- <paths>` writes files to the worktree *and stages them in the index* (`status: A`). Leaving them staged creates an acute hazard: the next routine `git commit` sweeps ~640 lines of development scaffolding into `master`.
2. **The Corrected Git Protocol**:
   ```bash
   git checkout backup-branch -- telemetry/ scripts/launchers/ adapters/moondev_adapter.py adapters/polymarket_adapter.py
   git restore --staged telemetry/ scripts/launchers/ adapters/moondev_adapter.py adapters/polymarket_adapter.py
   ```
3. **Universal Rule of Restoration**:
   **A restore is not complete until `git status` matches the pre-operation state.** "The file is back on disk" and "the repository state is restored" are fundamentally different claims.

---

### 1. Lab Dual-Component Backup Ratified & Scoping Insight Formally Codified (§2)

1. **Backup Verification**:
   - Location: `C:\Users\ixis1\Desktop\lab_backup_2026-09-12\` (external to both git repositories).
   - Component 1: `untracked/` (25 files, byte-identical `cmp` 25/25).
   - Component 2: `working_tree_modified.patch` (349 lines, verified `git apply --check --reverse`).
   - Component 3: `MANIFEST.txt` (HEAD `82ffcba`, timestamp, porcelain status).
   - Lab tree verified undisturbed: HEAD `82ffcba`, 19 dirty, **0 staged**.
2. **The 215-Line Modified-File Exposure Autopsied**:
   Claude's scoping insight is profound and correct:
   - Framing the exposure as "untracked lines only" was an incomplete mental model.
   - The 7 modified tracked files contain **215 uncommitted insertions / 6 deletions** that exist in **zero git refs**.
   - Crucially, `engine/risk_sentinel.py` contains the `portfolio_config_path` argument extension. `config/paper_donchian_t0030.yaml` is committed on `82ffcba`, but **without this uncommitted diff, the paper config cannot even be loaded**.
   - `git checkout .` or `git reset --hard` would erase this constructor argument instantly, silently breaking paper execution while also wiping `main.py`, `adapters/hyperliquid_adapter.py`, `config/asset_specs.json`, and `config/portfolio_config.yaml` (holding the other session's 27 uncommitted lines + parked Directive 1).
3. **Ruling on Item 5 ("Is a warning label enough?")**:
   - **External Safety**: The external patch file (`working_tree_modified.patch`) permanently mitigates unrecoverable data loss.
   - **In-Tree Parity**: In `AGENTS.md`, `git checkout .` and `git reset --hard` are formally elevated to the **exact same catastrophic severity** as `git clean -fd`. They are not lesser hazards—they destroy live runtime bindings.
   - **Credential Hygiene Ratified**: The deliberate exclusion of `.env` from the unencrypted Desktop folder is ratified as sound operational security. In a disaster-recovery drill, manual re-population of `.env` is expected.

---

### 2. Standing Ledger: 3 Active Items Reconciled (§3)

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper launch. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Untracked & Diff Backup | **DONE** | Closed | `C:\Users\ixis1\Desktop\lab_backup_2026-09-12\` holds untracked + 349-line patch + manifest. |
| 5 | Modified-File Hazard | **CODIFIED** | Closed | `checkout .` / `reset --hard` elevated to equal catastrophic tier as `clean -fd`. |

Zero directives owed in either direction. Systems standing by for Sunday's lead-lag gate closure (15:21Z).
