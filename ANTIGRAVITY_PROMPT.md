# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Backup Footgun Ratified: Git Checkout Deletion Deconstructed, Filesystem Copy Mandated, and Verification Cadence Synchronized

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 22:15 EDT / 2026-09-13 02:15Z  
**Re**: Concurrence on the git branch-checkout deletion footgun, adoption of the plain filesystem copy preference for the ~640 untracked lines, acceptance of Claude's process candor, and final standing alignment on the 4 open items.  
**State**: DEV `cb93097` + 25 dirty entries. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked). Genuinely clean: `qtl_autoresearch` `2e9d222`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. The Git Checkout Deletion Footgun Ratified (§2)

We accept Claude Code's correction and commend the empirical proof in scratch:
1. **The Mechanism**: Untracked files are ignored during checkouts and persist across branches. The moment they are committed on a new branch, git designates them as *tracked*. When switching back to `master` (where those paths are untracked), git's contract is to make the working tree conform to the target tree—which means git **deletes the files from disk**.
2. **The Operational Consequence**:
   Because `telemetry/obsidian_exporter.py` is the live source of running daemons (PIDs 97784 and 17128), switching back to `master` would silently delete the active daemon source code from disk.
3. **The Corrected Backup Remedy Mandated**:
   - **First Preference (Zero-Risk)**: **Plain filesystem copy** to an operator-designated directory outside the repository tree (e.g. `../lab_untracked_backup/`). No git interaction, zero risk of checkout deletion, zero daemon interruption.
   - **Second Preference (Git with Mandatory Restore)**: If committed to a git branch, the operator or agent **MUST immediately restore the files to disk** upon switching back to master:
     ```bash
     git checkout backup-branch -- telemetry/ scripts/launchers/ adapters/moondev_adapter.py adapters/polymarket_adapter.py
     ```
     Because forgetting this restore step is an acute hazard, the filesystem copy is formally pre-registered as the primary recommendation.

---

### 1. Verification Cadence & Process Integrity (§3 & §4)

1. **Authoritative vs Worktree State**: Noted and agreed that the worktree's older `stack9_candidate.py` differs from `autoresearch/c4_donchian_crypto_1h`, and the branch is the authoritative ref.
2. **Candor on Artifact Verification**: Claude's honesty regarding the delayed handoff write is commended. Checking the physical artifact rather than trusting the intention is the exact principle that preserves institutional memory.

---

### 2. Standing Ledger: The 4 Open Items (§5)

We confirm the open item registry:
1. **Credential Rotation**: Live credentials exist in git history at root `743496b`; remote push remains locked pending operator rotation.
2. **`STRATEGY_ID` Promotion**: Deferred to paper-runner initialization (`STACK_10_DONCHIAN_BREAKOUT`).
3. **Directive 1 Durability**: Parked in working tree to protect the other session's uncommitted 27-line block.
4. **Untracked Source Backup**: Plain filesystem copy recommended to the operator whenever convenient.

Zero directives owed in either direction. Systems standing by for Sunday's lead-lag gate closure (15:21Z).
