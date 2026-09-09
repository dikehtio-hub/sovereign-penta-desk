# Round 125 Rulings & Incident Directives: Collector Outage Audit, Hardening Deployment Mandate, Run 3 Declared Void, and Gate Hardening Directive

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-09 14:30 EDT  
**Subject**: Collector outage audited (26.3h stale, 11,613 FK errors, missing coins identified); Hardening deployment mandated for today's maintenance window; Run 3 declared VOID due to 67% missing price data; Gate hardening approved as directive; Data gap #2 registered.

---

## 1. Independent Incident Audit & Cross-Check Verification

Every verification check requested in Section C of the handoff has been audited and confirmed against the live environment:

1. **Collector Staleness & FK Error Count:**
   - Executed: `SELECT MAX(timestamp) FROM asset_snapshots` on `HyperLiquid/HL_Monarch/data/hyperliquid_data.db`.
   - Result: `1788883282392` = **`2026-09-08T16:01:22.392Z`** (**1,576.9 minutes = 26.28 hours stale**).
   - Scanned `HyperLiquid/HL_Monarch/data/collector.log`: **11,613 total lines** of `FOREIGN KEY constraint failed` (8,206 new errors since the Round 119 restart).
2. **Identification of Missing Exchange Listings:**
   - Queried live exchange metadata across all active DEXes and compared against the `assets` table:
     - **Database Assets:** 442 coins.
     - **Live Exchange Universe:** 444 coins.
     - **Missing Listings Causing FK Failure:** Exactly 2 coins: **`USELESS`** (main DEX) and **`para:TREAD`** (para DEX).
3. **Run 3 Price Series Truncation:**
   - Audited `cross_market/experiments/lead_lag_tier2b_crypto_verdict_run3.json`:
     - **Polymarket Shifts:** `09-08T03:32:30Z` $\to$ `09-09T18:00:12Z` (38.5 hours).
     - **Sought Price Window:** `09-08T02:31:30Z` $\to$ `09-09T19:01:12Z` (38.5 hours).
     - **Returned Prices:** `09-08T02:32:49Z` $\to$ **`09-08T16:01:22Z`** (**only 12.48 hours**).
     - **Missing Data:** **26.0 hours (67.5% of the evaluation window)** had zero forward BTC price points.

---

## 2. Formal Architectural Rulings for Round 125

### Ruling R125-1.A: Status of Run 3 Execution
* **Verdict:** **DECLARED VOID (OPTION ii)**.
* **Quantitative Rationale:**
  - Evaluating 4,980 Polymarket shifts across a 38.5h window where 26.0 hours (67.5%) of corresponding price series are missing produces invalid, truncated cross-correlations.
  - In Run 1, the 9.3h hole was an unperceived retrospective anomaly that taught us severe selection bias occurs when shifts lack continuous price pairings. Knowing *in advance* that 26 hours are missing and still ingesting would knowingly compromise the integrity of the scientific registry.
  - Fed-rates and crypto Tier 2 were already locked `no-lead` by Runs 1 and 2 under the $\ge 2$ of 3 consensus rule. The sole remaining empirical question of Run 3 was to adjudicate crypto Tier 2b on a clean series. A 67% missing series cannot adjudicate anything.
* **Directive:**
  - Do NOT ingest Run 3. Discard the four `_run3.json` artifacts.
  - Run 3 will be re-bound to a fresh, clean, independent 24-hour disjoint window starting immediately after the collector is hardened and restarted: `--since <restart_timestamp_utc>`.

---

### Ruling R125-1.B: Collector Hardening Deployment (Operator Decision)
* **Verdict:** **DEPLOY HARDENING IMMEDIATELY (`feat/collector-hardening`, commit `70bd232`)**.
* **Rationale:**
  - The "dead-alive" collector bug has struck twice in 3 days (`para:CIFR` on 09-06, `USELESS` and `para:TREAD` on 09-08). A plain restart only resets the clock until the next token listing.
  - Today (Wednesday, September 9) is the exact pre-planned deployment window recommended in Round 121 and `HOMEWORK.md`.
  - The branch `feat/collector-hardening` is clean (+209 lines across 4 files), has 0 merge conflicts against master, and includes 8 dedicated unit tests.
  - Deploying today gives a full 7-day soak before the September 16 FOMC print.
* **Deployment Sequence (Operator Authorized):**
  1. Merge `feat/collector-hardening` into `master`.
  2. Run suite: `python -m pytest HyperLiquid/HL_Monarch/tests/test_round121_hardening.py`.
  3. Execute `stop_collector.bat` $\to$ verify old PIDs `24504` and `60756` are terminated $\to$ execute `start_collector.bat`.
  4. Verify newest `asset_snapshots` row $< 60$s old and `assets` updated to 444 rows.

---

### Ruling R125-1.C: Gate Hardening (`lead_lag --check-data`)
* **Verdict:** **APPROVED AS MANDATORY PRE-REGISTRATION REQUIREMENT**.
* **Problem Statement:**
  For the second time, `lead_lag --check-data` declared `READY` over a dead price stream because it only inspected the Polymarket tagged event series. A lead-lag test fundamentally requires both events AND target asset prices.
* **Directive & Specification:**
  Update `cross_market.lead_lag --check-data` to validate BOTH streams before emitting `ready: true`:
  1. **Polymarket Tagged Shifts:** Span $\ge 24\text{h}$, points $\ge 200$, largest gap $\le 60\text{min}$.
  2. **HyperLiquid BTC Price Snapshots:**
     - Newest snapshot age $\le 15\text{min}$.
     - Zero continuous price gaps $> 60\text{min}$ inside the sought evaluation window `[since - max_lag - 1, now]`.
  3. If either fails, emit `ready: false` and explicitly name the failing stream (e.g. `price stream stale (1576 min) - collector down`).

---

### Ruling R125-1.D: Second Data Gap Registration
* **Verdict:** **REGISTER GAP #2 IN THE KNOWLEDGE VAULT**.
* **Action:**
  - Register gap `wiki/events/data_gap_2026-09-08_hl_asset_snapshots_2.md` (and `knowledge/data_gaps.json`):
    - **ID:** `2026-09-08_hl_asset_snapshots_2`
    - **Desk:** 1 (HyperLiquid)
    - **Start UTC:** `2026-09-08T16:01:22Z`
    - **End UTC:** `<collector_restart_utc>`
    - **Cause:** Foreign key constraint failure on newly listed coins `USELESS` and `para:TREAD`.
    - **Affected Evaluations:** Lead-Lag Run 3 (voided), Basis Windows, Fade Re-benchmark.

---

## 3. Forward Execution Queue

1. **Step 1 (Now):** Operator approves deployment $\to$ Claude merges `feat/collector-hardening`, runs unit tests, and restarts the collector.
2. **Step 2:** Register Data Gap #2 with exact restart timestamp.
3. **Step 3:** Implement Gate Hardening in `cross_market/lead_lag.py` (Rule R125-1.C).
4. **Step 4:** Re-bind Run 3 in `HOMEWORK.md` to `--since <restart_timestamp_utc>` (Run 3 will close 24h later, ~Thursday 15:00 EDT).
