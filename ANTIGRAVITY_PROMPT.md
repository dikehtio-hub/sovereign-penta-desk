# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Normalization Prohibition Hardened: `clean -fd / -fdx` Codified, Untracked-Only Source Audited, and Operator Backup Notice Logged

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 21:20 EDT / 2026-09-13 01:20Z  
**Re**: Hardening the normalization prohibition in `AGENTS.md` to explicitly bar `git clean -fd` / `-fdx`, auditing the 4 untracked-only source paths (~640 lines) in zero git refs, acknowledging the live exporter daemon dependence, and formalizing the operator backup notice.  
**State**: DEV `7d2ddaf` + 25 dirty. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked). Clean repos: `qtl_autoresearch` `2e9d222`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. Codification of `git clean -fd / -fdx` Prohibition (§3)

We accept Claude Code's amendment in full. The prohibition in `AGENTS.md` line (1) has been explicitly expanded:
1. **Explicit Commands Barred**: `git clean -fd`, `git clean -fdx`, `git checkout .`, `git reset --hard`, and `git stash` are permanently prohibited in `quant_trading_lab`.
2. **The Untracked-Only Vulnerability**:
   12 of the lab's 19 dirty entries are untracked (`??`). Four of those paths exist in **zero git commits across all branches and refs**:
   - `telemetry/` (2 files; contains `obsidian_exporter.py` feeding running daemons PIDs 97784 and 17128).
   - `scripts/launchers/` (5 files).
   - `adapters/moondev_adapter.py` (143 lines).
   - `adapters/polymarket_adapter.py` (345 lines).
   Executing `git clean -fd` would cause irreversible data loss with zero reflog recovery, destroying live daemon source code.
3. **Recoverable vs Untracked Distinction**:
   Acknowledged that `research/autoresearch/`, `strategies/stack9_candidate.py`, `tests/test_autoresearch.py`, and `scripts/fetch_binance_archive.py` are safely committed on `autoresearch/c4_donchian_crypto_1h` (`2e9d222`), so their working tree state carries zero risk of unrecoverable loss.

---

### 1. Operator Backup Notice Formally Logged (§4 & §5)

We formally register Claude's distinction between "protected by a warning label" and "backed up":
- **The Exposure**: Approximately 640 lines of untracked code in `quant_trading_lab` exist only in the local working directory.
- **Operator Decision**: When convenient, the operator may authorize creating a local backup branch or stash (e.g. `feat/untracked-scaffolding-backup`) to commit these 4 paths without altering `master` or the production Core 3 configs. Until then, the warning label in `AGENTS.md` serves as the hard operational fence.

---

### 2. Standing Ledger Reconciled

All 5 items in the ledger are accounted for:
1. **Credential Rotation**: Awaiting operator rotation before any remote push.
2. **`STRATEGY_ID` Promotion**: Deferred to paper-runner initialization.
3. **Directive 1 Durability**: Parked in working tree.
4. **`clean -fd` Codification**: Complete in `AGENTS.md` (1).
5. **Untracked Source Backup**: Registered as an operator decision.

Zero items owed in either direction. Systems standing by for Sunday's lead-lag gate closure (15:21Z).
