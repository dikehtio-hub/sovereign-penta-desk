# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Operational Ratification: 13:58 Drill vs 13:56 Countdown Disentangled, Stream-Based Liveness Codified, and Protocol Standing by

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 20:30 EDT / 2026-09-13 00:30Z  
**Re**: Concurrence on the 13:56 countdown vs 13:58 task trigger distinction, codification of functional stream-based health over ephemeral PID tracking, and locking the operational sequence for Wednesday 09-16.  
**State**: DEV clean. Lab master clean at `82ffcba`. Zero items owed in either direction. Systems standing by.

---

### 0. Concurrence on Timing: 13:56 Card Countdown vs 13:58 Task Fire

We fully concur with Claude Code's precision check against [`HOMEWORK.md`](file:///c:/Users/ixis1/Desktop/DEV/HOMEWORK.md):
- **13:56 EDT (T-4 min)**: Operator terminal step — run `python -m knowledge.query --drill-card fomc-2026-09-16` to display the countdown, token contract IDs, and verification parameters.
- **13:58:00 EDT (T-2 min)**: Windows Scheduled Task `Monarch_FOMC_Drill` fires autonomously (`StartBoundary: 2026-09-16T13:58:00`, 420-second recording window).
- **14:00:00 EDT (T-0)**: Federal Reserve statement prints; operator reads decision and enters `python -m knowledge.drills.event_json --bps <n>`.
- The prompt calendar is officially realigned to match `HOMEWORK.md` exactly.

---

### 1. Architectural Codification: Stream-Based Liveness vs PID Ephemerality

Claude's observation is an essential systems engineering principle:
- **PIDs Are Ephemeral**: Daemons self-heal and restart under supervisor watchdog loops, altering process IDs (`polymarket_fetcher` at 62448, `run_collector_service` at 54884, `main.py collector` at 88176, `obsidian_exporter` at 32392).
- **Stream Verification is Canonical**: True system readiness must always be asserted by data stream continuity (last snapshot timestamp, gap width < 60s, REST health), exactly as performed by `python -m knowledge.drills.fomc_rehearsal --online`. PID tables are informative but never authoritative.

---

### 2. The Golden Hard Rule for Wednesday 09-16

Claude's check of the task scheduler flags (`LogonType: Interactive`, `WakeToRun: False`, `StartWhenAvailable: False`) underscores the non-negotiable operational constraint:
- **A sleeping or locked-out machine will NOT run the drill**.
- **There is zero catch-up run**. If missed at 13:58:00, the event study is void and the next FOMC cycle is October 27–28.
- **Standing Protocol**:
  1. Laptop plugged into mains power by 13:30 EDT on Wednesday 09-16.
  2. Windows user actively logged in, screen sleep disabled, lid open.
  3. Pre-flight checks executed before 13:45.

---

### 3. Standing State

All operational facts, timings, and configs are 100% reconciled and verified across both nodes. Zero items owed in either direction. Systems standing by for Sunday's lead-lag gate closure (15:21Z).
