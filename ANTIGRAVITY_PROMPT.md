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

## Section 105: The Pre-Move Protocol — File-Watched Relay Ratified, Pre-Transit Backup Mandated (Empty Remote Risk), Gen-1 Cleanup Scheduled Post-Move, and Dynamic Reversal Formula Adopted (2026-09-21 22:35 EDT / 2026-09-22 02:35Z)

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-21 22:35 EDT / 2026-09-22 02:35Z (Pre-Move Operational Check)  
**Re**: Audit rulings on Section 105 handoff: ratification of Option (i) file-watched relay protocol; codification of the authority text for file-relayed rulings; scheduling of the 5-step Gen-1 script cleanup for a post-move branch; critical finding of the empty git remote and mandatory pre-transit cold backup protocol; and adoption of the within-run dynamic reversal hurdle.

---

### 1. Choice 1 Ruling: The Relay Protocol & Authority Boundary

#### (a) Adoption of Option (i) (File-Watched Relay)
- **RATIFIED AS STANDING PROTOCOL**:
  - Claude Code watches `ANTIGRAVITY_PROMPT.md` by content hash.
  - Antigravity reads `HANDOFF_PROMPT.md` directly from disk and writes rulings to `ANTIGRAVITY_PROMPT.md`.
  - The operator does not copy-paste prompt bodies; the operator provides only a simple single-line trigger in Antigravity (e.g., `"read HANDOFF_PROMPT.md and rule"`).
  - External GitHub relay tools (`deaddrop`, `severally`, `vibe-kanban`) are rejected: because turn-based LLMs require a user keystroke to invoke, none eliminate the operator trigger, while adding fragile Node/npm dependencies.

#### (b) Authority Text for File-Relayed Decisions
- **CODIFIED AS BINDING INVARIANT**:
  > *"A ruling in `ANTIGRAVITY_PROMPT.md` that names a file and explicitly states 'commit authorized' authorizes a git commit of that file only. Launching any persistent daemon, deleting files, or touching master's collector-imported modules always requires the operator's plain, explicit consent in chat."*

---

### 2. Choice 2 Ruling: Gen-1 Lifecycle Scripts Cleanup

- **The Discovery**:
  - `shutdown_all.bat:53` calls `stop_all_ecosystem_sync.bat`, which attempts to kill by `WINDOWTITLE` and fails silently against detached `pythonw` processes.
  - `start_all_ecosystem_sync.bat` remains a live test assertion and is wired into `Bot_Control.md` buttons, where clicking it spawns duplicate windowed exporter instances.
- **RULING**:
  - **Do NOT touch these scripts tonight** before transport.
  - The proposed 5-step refactoring package is approved as **Work Package 4 (Lifecycle Unification)** to be executed on a dedicated branch `refactor/unify-lifecycle-scripts` after the house move is complete:
    1. Delegate `shutdown_all.bat:53` to command-line sweeping or `shutdown_dev_penta.ps1` tiers 2–3.
    2. Re-point test assertions to `telemetry_health.py` launch tables.
    3. Regenerate `Bot_Control.md` buttons to `resume_all.bat` / `shutdown_dev_penta.ps1`.
    4. Rewrite `MASTER_COMMANDS_GUIDE.txt:478-486`.
    5. Move `start_all_ecosystem_sync.bat` and `stop_all_ecosystem_sync.bat` to `legacy/`.
  - **Tonight's Shutdown**: Use `scripts/shutdown_dev_penta.ps1` (with the HOMEWORK.md 4-step command-line fallback) to ensure verified process count $= 0$.

---

### 3. Choice 3 Ruling: The Transit Backup Mandate (CRITICAL RISK)

- **The Critical Vulnerability**:
  - `git remote -v` returned **EMPTY**.
  - This laptop contains the **sole copy on Earth** of the repository, all commit history, and uncommitted research.
  - Untracked/git-ignored critical assets total $>8.5\text{ GB}$:
    - `hyperliquid_data.db` ($8.49\text{ GB}$ of tick data).
    - `funding_history_180d.db` ($2.6\text{ MB}$).
    - `book_depth_samples.db`.
    - `BOTS/HYPERLIQUID/dontshare.py` and API configurations.
  - Transporting an unbacked machine during a physical house move exposes the entire project to total loss from hardware shock, theft, water damage, or drive failure.

- **MANDATORY PRE-TRANSIT BACKUP PROCEDURE**:
  1. **Execute Graceful Daemon Shutdown**: Run `scripts/shutdown_dev_penta.ps1` and verify process count $= 0$ to guarantee clean WAL checkpoints.
  2. **Cold Media Backup**: Copy the entire `C:\Users\ixis1\Desktop\DEV` directory to an external USB drive, external SSD, or local cloud-sync folder (e.g. OneDrive).
  3. **Private Remote Push**:
     - Create a private repository (e.g. on GitHub/GitLab).
     - Add remote: `git remote add origin <private_repo_url>`
     - Push all branches (`git push -u origin master`, `git push origin --all`).
     - (Verify that `dontshare.py` and `.db` files remain gitignored as configured).

---

### 4. Reversal Hurdle Refinement (From §5)

- **Conceded and Ratified**:
  To eliminate parameter drift and arbitrary constant mismatch, the reversal hurdle is formally defined dynamically within the same simulator run:
  $$\mathbf{\Delta_{\text{Viability}}} = \text{Net APR}_{\text{P0\_gated}}(S=\$2,500, \text{empirical depth}) - \text{Net APR}_{\text{PASSIVE\_BTC}}(\text{measured}) \ge \mathbf{4.0\%}$$
  Both arms are priced simultaneously against measured friction. (Currently: $-3.58\% - (+4.99\%) = -8.57\%$, failing by $12.57\%$).

---

### Standing State & Pre-Transit Checklist

- **Pipeline Daemons**: 10/10 `pythonw` daemons LIVE since 02:04:43Z.
- **Repository State**: `DEV master` clean at `cd5bfac`.
- **Tonight's Pre-Move Sequence**:
  1. Run P4 read if desired before shutdown (truncated evening window noted).
  2. Execute `scripts/shutdown_dev_penta.ps1` (verify count $= 0$).
  3. Perform cold copy of `DEV` to external storage.
  4. Push git repository to a private remote.
  5. Power down laptop safely for the move.
