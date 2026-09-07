# Round 123 Directive: Telemetry Layer Supervision, Exporter Resilience, and Pre-Flight Hash Scoping

**To**: Claude Code (Senior Implementation Engineer / Test Master)  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-07 12:50 EDT  
**Subject**: Status update received; workspace health sweep and probe results commended; **Ruling R123-1.A approved** (Telemetry Supervision & Exporter Resilience); **Critical Root-Cause Finding & Directive on `hash_vault` in Pre-Flights**; Run 2 remains on track for ~22:22 EDT tonight (14.4h accumulated, 0 breaks).

---

## 1. Status Update Review & Quantitative Telemetry Audit

1. **Replication Run 2 Data Accumulation (12:47 EDT Live Audit):**
   - Executed `lead_lag --check-data --family macro --subfamily-from tags --since 2026-09-07T02:22:00Z`.
   - **Segment:** `2026-09-07T02:22:37Z` $\to$ `2026-09-07T16:46:04Z` (span **14.4h**, 172 points, rate 11.88/h).
   - **Continuity:** Largest gap **5.1 min**, **0 breaks > 60 min**. Flawless continuity overnight.
   - **Gate Closure ETA:** `2026-09-08T02:22:37Z` ($\approx$ **22:22 EDT tonight**). Exactly on schedule.
2. **Workspace Health Sweep:** All core suites verified green (Knowledge 386, Cross-Market 215, HyperLiquid 1,110, Sports 223, Polymarket 237, Tax 546, Desk 4 180). Secondary suites (Dexter, STRATS) compiling cleanly.
3. **Scheduler Probe & W32Time:** Verified (`PROBE OK`, 60/60 stamps). W32Time is locked to `time.windows.com` (`+0.107s` offset).
4. **Telemetry Exporters Active:** All 5 exporters are actively streaming. Real vault lint: **509 pages · 0 errors · 0 warnings · CLEAN**.

---

## 2. Architectural Rulings & Directives for Round 123

### Ruling R123-1.A: Telemetry Layer Supervision, Exporter Resilience, and Pre-Flight Hash Scoping
* **Verdict:** **APPROVED AS PRIMARY OBJECTIVE FOR ROUND 123**.
* **Problem Statement:**
  1. The five per-desk Obsidian telemetry exporters experienced a silent, multi-day presentation-layer outage (dashboards stale up to ~2 days) while the data collection pipeline continued unaffected.
  2. `resume_all.bat` relies on "watcher running" as a proxy for "ecosystem running," meaning a surviving watcher causes `resume_all.bat` to skip recovering dead telemetry exporters.
  3. **New Pre-Flight Incident Diagnosed at 12:48 EDT:** `python -m knowledge.drills.fomc_rehearsal --online` failed with:
     `[FAIL] card wrote nothing: vault sha256 identical before and after the card`.

### Architectural Directives & Implementation Constraints:

1. **Pre-Flight Scoping Gotcha — Fix `hash_vault()` in `fomc_rehearsal.py` & `fomc_live_rehearsal.py` (URGENT):**
   - **Root Cause:** `hash_vault(vault)` computes a single SHA-256 hash over *every* `.md` file in `obsidian_vault/` (`vault.rglob("*.md")`).
   - Why it passed previously: When the 5 telemetry exporters were dead, the vault root was completely static.
   - Why it failed today: Now that the exporters were restarted, they write active updates every 15s to `HyperLiquid_Monarch.md`, `Quant_Trading_Lab.md`, `Bot_Config.md`, `Tax_Reserve_*.md`, etc. Between `before = hash_vault(vault)` and `hash_vault(vault) == before`, an exporter ticked, causing `card wrote nothing` to fail!
   - In `fomc_live_rehearsal.py` (which runs a 60s loop), `ok("real vault untouched", hash_vault(vault) == before_vault)` is **guaranteed to fail 100% of the time** because live exporters tick ~4 times during the test.
   - **Directive:** Scope `hash_vault` so it does not hash files managed by live telemetry exporters. It should hash `vault / "wiki"` (where knowledge pages, event pages, rules, and drill artifacts live), or explicitly filter out root dashboards and exporter directories (`Whales/`, `Trading_Taxes/`, `Canvases/`).

2. **Separation of Drill Pre-Flight vs. Telemetry Monitoring:**
   - `fomc_rehearsal --online` is an operational execution gate for the September 16 FOMC rate print drill. It tests the latency sniper, CLOB liquidity depth, target Fed market tokens, NTP synchronization, and core execution data daemons (`collector`, `watcher`, `exporter`).
   - Telemetry exporters generate Markdown dashboards for human viewing; they are non-critical to order-book depth recording at T-2.
   - **Directive:** A dead or lagging telemetry exporter must never trigger a blocking FAIL on the FOMC drill. Telemetry health checks should live in a dedicated module (e.g., `python -m knowledge.drills.telemetry_health` or `pipeline_health.py`), or be checked in `resume_all.bat`, keeping `fomc_rehearsal --online` focused on the drill.

3. **Liveness vs. File Modification Times (`write_note_if_changed`):**
   - Quantitative & Systems Gotcha: Exporters for `Quant_Trading_Lab`, `Sports_Desk`, and `Tax_Reserve` use `write_note_if_changed()` with SHA-256 hash checking to prevent unnecessary disk wear.
   - Consequently, notes for desks whose state does not tick on every pass **will not update their file modification timestamp (`mtime`) unless market or trade state changes**.
   - **Directive:** A health check that measures markdown file `mtime` will emit false-positive staleness alerts overnight, on weekends, or during low-volatility periods. Exporter health MUST judge **process liveness** (PID lockfile, single-instance `--status` command, or process command-line inspection), not purely note file mtime.

4. **Decouple Exporter Recovery in `resume_all.bat`:**
   - `resume_all.bat` must not treat the Polymarket watcher as a proxy for the 5 telemetry exporters.
   - Each exporter should either support a lightweight `--status` check (similar to Directive 74-1 for `cross_market.interfaces.obsidian_exporter`), or `resume_all.bat` should check per-exporter PID/liveness before launching detached processes via `Start-Process`, preventing duplicate instances.

---

## 3. Forward Calendar & Execution Queue

1. **Round 123 (Daytime today, 2026-09-07):**
   - Scope `hash_vault()` in `fomc_rehearsal.py` and `fomc_live_rehearsal.py` to `vault / "wiki"` to eliminate the live telemetry race condition.
   - Implement Ruling R123-1.A (Telemetry health monitoring + `resume_all.bat` decoupling).
   - Verify all tests and pre-flight (`--online`) are 100% clean.
2. **Tonight (~22:20–22:25 EDT, 2026-09-07):**
   - **Replication Run 2 of 3 (Ruling R122-1.B):**
     - Verify readiness: `python -m cross_market.lead_lag --check-data --family macro --subfamily-from tags --since 2026-09-07T02:22:00Z` $\to$ `ready: true`.
     - Execute 4 pre-registered commands with `--since 2026-09-07T02:22:00Z --json` into `_run2.json`.
     - Ingest into vault via `knowledge.ingest.lead_lag --tier 2|2b`.
3. **Standing Operator Requirements:**
   - Keep laptop awake on AC through ~22:25 EDT tonight (Run 2) and tomorrow night (Run 3).
   - Collector hardening deployment scheduled for operator maintenance window (09-08 or 09-09 evening).
