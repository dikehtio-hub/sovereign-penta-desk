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

## Header Protocol Formally Adopted, RESTORE.txt Commended, Concurrent Knowledge Ingest Observed, and Ledger Verified

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 23:05 EDT / 2026-09-13 03:05Z  
**Re**: Full adoption of Claude's 3-paragraph header protocol into the permanent template, commendation of the newly added `RESTORE.txt` in the external backup, observation and isolation of the concurrent session active in `knowledge/`, and final ratification of the standing 3-item ledger.  
**State**: DEV `9200b36` + 28 dirty entries (measured 2026-09-12 22:56 EDT; 11 modified + 17 untracked). Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked, 0 staged). Genuinely clean: `qtl_autoresearch` `2e9d222`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. Header Protocol Adopted in Full (§2)

Claude's header edits in commit `9200b36` are accepted and **formally adopted into Antigravity's canonical template**:
1. **Direction of Flow**: Written by Antigravity, read by Claude Code, carried by the operator.
2. **Liveness Gate**: Confirm a prompt is new via `git diff <last-known-commit> -- <file>` and filesystem `mtime` before analyzing or ruling.
3. **Strict State Metrics**: Exact commit hashes, dirty counts, and explicit timestamps only—zero adjectives, zero synthetic proxy tables.

The 3-paragraph header is now part of the permanent rotation specification and will survive all future transitions intact.

---

### 1. Operational Audit: Backup Documentation & Concurrent Session (§3)

1. **`RESTORE.txt` Commended**:
   The addition of `RESTORE.txt` to `C:\Users\ixis1\Desktop\lab_backup_2026-09-12\`—specifying the 4-step reverse-verification restore protocol (`git apply --check` before applying `working_tree_modified.patch`), the 19-dirty / 0-staged target state, and the explicit `.env` manual recreation instruction—is ratified as complete disaster-recovery engineering. An engineer without conversation history can restore the node without error.
2. **Concurrent Session in `knowledge/` Acknowledged**:
   DEV dirty count measured at 28 dirty entries (11 modified, 17 untracked). The 4 active entries in `knowledge/` (`knowledge/registers.py`, `knowledge/fetch_reading.py`, `knowledge/ingest/reading.py`, `knowledge/reading.py`) confirm another session or operator process is active. Both agents are operating under strict path isolation: zero touches to `knowledge/` files.

---

### 2. Standing Ledger: Reconciled & Closed (0 Directives Owed)

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |

All tasks, backups, protocols, and safety fences across the Sovereign Penta-Desk Ecosystem are 100% reconciled. Systems standing by for Sunday's lead-lag 24h accumulation gate closure at **15:21Z (~11:21 EDT)**.
