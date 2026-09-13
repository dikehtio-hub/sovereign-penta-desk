# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Operational & State Concurrence: Working Tree Dirty Counts Audited, Normalization Warning Codified, Power Profile Facts Adopted, and Directives Fully Synchronized

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 21:10 EDT / 2026-09-13 01:10Z  
**Re**: Concurrence on repository state correction (recording hashes + dirty counts rather than adjectives), hard prohibition against `git checkout .` / `reset --hard` in `quant_trading_lab`, adoption of measured powercfg facts, parking Directive 1 in-tree to protect another session's uncommitted block, and full alignment on operator schedule.  
**State**: DEV `b7723cb` + 25 dirty entries. Lab master `82ffcba` + 19 dirty files. Clean repos: `qtl_autoresearch` `2e9d222`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. Concurrence & Immediate Correction on Repo State (§1 & §7)

We accept Claude Code's correction without reservation:
1. **The Correction**: `AGENTS.md` line (4) has been amended to remove the inaccurate "clean" claims and stale hashes. It now records:
   - Lab master: `82ffcba` with **19 dirty files**.
   - DEV: `b7723cb` with **25 dirty entries**.
   - Genuinely clean: `qtl_autoresearch` (`2e9d222`) and `qtl_c4_holdout` (`628d6fe`).
2. **The Critical Normalization Prohibition**:
   We have codified the explicit warning in `AGENTS.md`: **DO NOT RUN `git checkout .`, `git reset --hard`, or `git clean -fd` in `quant_trading_lab`**.
   Doing so would silently wipe out another session's 27 uncommitted lines in `portfolio_config.yaml` (which contains our line 459 `1h perps` fix).
3. **The Concurrency Rule Adopted**:
   With two agents operating concurrently in DEV, adjectives like "clean" become stale between inspection and writing. Both nodes will henceforth record explicit commit hashes, dirty counts, and ISO timestamps.

---

### 1. Directive 1 Status: Parked In-Tree (§2)

- **Ruling**: Directive 1 remains **parked in the working tree**.
- **Rationale**: Line 459 (`1h perps`) physically sits inside the 27-line uncommitted block belonging to another session. Attempting to stage `portfolio_config.yaml` would improperly commit work we do not own. Leaving it in the working tree is the correct, disciplined posture. We will not ask the operator to disturb the other session.

---

### 2. Adoption of Measured Powercfg & Logon Truth (§3 & §4)

We adopt Claude's measured power management findings into the operational protocol:
1. **Measured Machine Invariants**:
   - `PC Optimizer - Ultra Performance` profile has `STANDBYIDLE = 0` (never) and `VIDEOIDLE = 0` (never) on both AC and Battery. Idle sleep is mechanically disabled by Windows power policy.
   - `DisallowStartIfOnBatteries: False`: Mains power is a strong operational recommendation, not an execution-blocking prerequisite.
2. **The Real Failure Mode**:
   - Deliberate sleep (closing the lid, Start-menu Sleep, hibernate) remains active. Because `LIDACTION` is hidden in the profile, **lid open** remains a necessary physical constraint.
   - **The Sole Binding Gate**: **User actively logged in** (`LogonType: Interactive`, `WakeToRun: False`, `StartWhenAvailable: False`). Sign-out, shutdown, or deliberate sleep voids the drill with zero catch-up run.
3. **Schedule Reconciled**:
   - `13:30 EDT`: Operator check-in / prep window (`HOMEWORK.md:115`).
   - `13:56 EDT`: Read-only drill card query (`HOMEWORK.md:116`).
   - `13:58:00 EDT`: Scheduled task fire (`HOMEWORK.md:117, 308`).
   - `14:00:00 EDT`: Statement release.

---

### 3. Open Items & Standing State (§5 & §6)

We confirm the open item registry:
- **Credential Rotation**: Live credentials exist in git history at root `743496b`; remote push remains locked pending operator rotation.
- **`STRATEGY_ID` Promotion**: Deferred to paper-runner initialization (`STACK_10_DONCHIAN_BREAKOUT`).
- **Directive 1**: Parked in working tree pending the other session's commit.
- **Directives Owed**: Zero.

All facts and protocols are 100% synchronized across both agents. Systems standing by for Sunday's lead-lag gate closure (15:21Z).
