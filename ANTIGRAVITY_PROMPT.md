# Round 125 Closed: Phase 2 Ownership, Registration Architecture, and High-Resolution Event-Study Blueprint

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-09 16:45 EDT  
**Subject**: Round 125 formal closure acknowledged; Commit `21f1f0e` audited green; Run 3 schedule confirmed (~15:35 EDT Thursday); Phase 2 Pre-Registration ownership assigned; Directory convention fixed; Quantitative solutions for 1-second resolution, single-event statistics, and sub-minute latency established.

---

## 1. Commit Audit & Standing Schedule

1. **Commit Audit (`21f1f0e`):**
   - Verified clean: 4 doc files (`AGENTS.md`, `HOMEWORK.md`, `HANDOFF_PROMPT.md`, `ANTIGRAVITY_PROMPT.md`), 0 code churn.
   - Rulings R125-2.C (sentinel card scope extension) and R125-2.D (daemon loop cumulative gating confirmed) accurately archived in `AGENTS.md`.
2. **Standing Schedule for Run 3:**
   - **Gate ETA:** `2026-09-10T19:31:09Z` ($\approx$ **15:31 EDT Thursday, Sept 10**).
   - **Ping Time:** **~15:35 EDT Thursday** (giving the 24.0h span clock a 4-minute buffer beyond the first tagged stamp).
   - **Operator:** Maintain laptop awake on AC with zero daemon interventions until Run 3 execution.
   - **Thursday Morning Sanity (09-10):**
     - `HyperLiquid/HL_Monarch/data/collector_service.jsonl`: `coverage_pct` climbing toward 100%.
     - `python -m cross_market.interfaces.obsidian_exporter --status`: RUNNING (PID 64692).
     - `python -m knowledge.drills.fomc_rehearsal --online`: 33 checks, 0 FAIL, 1 WARN (W32Time).

---

## 2. Phase 2 Pre-Registration Ownership & Directory Architecture

1. **Directory Convention: Maintain Proven Experiment Path:**
   - **Decision:** Do **NOT** create a new `knowledge/registrations/` directory.
   - The established, battle-tested pattern in this codebase is:
     - Pre-registration source: `cross_market/experiments/<name>.meta.json` (or `.rules.json`).
     - Vault compilation: `wiki/experiments/<name>_meta.md` (via `knowledge.ingest.experiments`).
     - Ingest linkage: `knowledge.ingest.lead_lag` / `knowledge.ingest.clob`.
   - Phase 2 will be registered at:  
     `cross_market/experiments/lead_lag_phase2_fomc.meta.json`  
     compiling to `wiki/experiments/lead_lag_phase2_fomc_meta.md`.
2. **Ownership Split:**
   - **Antigravity (Architect / Auditor):** Authors the scientific protocol, quantitative hypotheses, formal mathematical definitions, acceptance bars, and latency thresholds (detailed below in Section 3).
   - **Claude Code (Implementation Engineer):** Authors the `lead_lag_phase2_fomc.meta.json` artifact, wires schema validation into `knowledge.ingest.experiments`, binds the execution harness, and adds regression tests during **Round 126** (immediately following Thursday's Run 3 close-out).
   - **Target Lock Date:** Locked and committed by **Friday, September 11**, comfortably ahead of the September 15 code freeze and September 16 FOMC print.

---

## 3. Phase 2 Quantitative Blueprint: Solving the Three Core Methodological Risks

Claude Code correctly highlighted three pivotal design challenges for event-driven lead-lag. Here is the formal quantitative specification:

### A. Temporal Resolution: The 1-Second Discrete Grid
- **The Problem:** The standard Polymarket watcher polls every 300 seconds (5 min). High-impact macroeconomic releases (FOMC statements) trigger institutional algorithmic price discovery within 50–500 milliseconds, with primary order-book repricing complete within 5–30 seconds. A 5-minute polling interval is mathematically blind to the entire event dynamic.
- **The Solution:** Phase 2 decouples entirely from the 5-minute watcher drops and ingests the high-frequency stream from Item 17:
  1. **Polymarket CLOB Stream:** The scheduled drill task (`Monarch_FOMC_Drill` / `fomc_drill_2026-09-16.bat`) records **1-second L2 order-book depth** for the three registered Fed rate markets across $[13:58:00, 14:05:00]$ EDT (420 seconds total, $T - 120\text{s}$ to $T + 300\text{s}$).
  2. **HyperLiquid Tick/Snap Stream:** HyperLiquid 1-second price marks ($P_t^{\text{mid}}$) recorded across the identical 420-second window.
  3. **Evaluation Grid:** Both streams are snapped to a synchronized, discrete 1.0-second UTC timestamp grid: $t \in [T_0, T_0 + 420]$.

### B. Statistical Formulation: Event Study Displacement Half-Life ($t^*_{50\%}$)
- **The Problem:** A single macroeconomic announcement cannot support a continuous Pearson correlation test ($N$ independent intervals). In a 420-second window around a binary rate surprise, both venues experience a sharp step function, which trivially produces high correlation ($r > 0.80$) at whatever lag aligns the steps, masquerading as broad predictive lead.
- **The Solution:** Structure Phase 2 as a formal **Macroeconomic Event Study**:
  1. **Baseline Price Displacement:** Let $\Delta P_{\text{total}} = P(T+300\text{s}) - P(T-5\text{s})$ be the net post-event shift for both venues.
  2. **Displacement Half-Life ($t^*_{50\%}$):** Define $t^*_{50\%}$ as the earliest second $t$ where:
     $$|P(t) - P(T-5\text{s})| \ge 0.50 \cdot |\Delta P_{\text{total}}|$$
  3. **Lead Metric ($\Delta t_{\text{lead}}$):**
     $$\Delta t_{\text{lead}} = t^*_{50\%, \text{HL}} - t^*_{50\%, \text{PM}}$$
  4. **Multi-Event Panel Requirement:** A single print yields a single **Reaction Profile** (`wiki/experiments/reaction_profile_fomc_20260916.md`). A formal lead-lag **Verdict** requires a pooled panel across $N \ge 3$ major macroeconomic releases (e.g., FOMC 09-16, October CPI, FOMC 10-28).

### C. Sub-Minute Latency Classification Thresholds
- **The Problem:** Cross-venue arbitrage and latency between centralized crypto exchanges (HyperLiquid) and decentralized prediction markets (Polymarket on Polygon via CLOB) have characteristic network and settlement propagation delays of 500ms to 2.0s.
- **The Solution:** Classification vocabulary based on a $\pm 1.0$-second tolerance band:
  - **`polymarket-leads-event`:** $\Delta t_{\text{lead}} > +1.0\text{s}$ (Polymarket order book midpoint completes 50% displacement $> 1.0$ second before HyperLiquid spot/perp).
  - **`hyperliquid-leads-event`:** $\Delta t_{\text{lead}} < -1.0\text{s}$ (HyperLiquid completes 50% displacement $> 1.0$ second before Polymarket).
  - **`contemporaneous-event-repricing`:** $|\Delta t_{\text{lead}}| \le 1.0\text{s}$ (Both venues reprice within the identical 1-second window; transmission delay is indistinguishable from zero).
  - **`uninformative-shock`:** $|\Delta P_{\text{total}}| < \text{threshold}$ (The announcement was a non-event with no measurable order-book shift).

---

## 4. Next Actions (Round 126 Handoff)

1. **Thursday 15:35 EDT:** Execute Run 3, verify gate clearance, ingest four verdicts into vault, and finalize Item 18 Phase 1 close-out synthesis.
2. **Round 126 Implementation:** Claude Code compiles `lead_lag_phase2_fomc.meta.json` using the specification in Section 3 above, verified through unit tests in `cross_market/tests/`.

---

## 5. Live Accumulation Checkpoint (20:40 EDT / 5.1h Post-Rebind)

- **Gate Status:** `points: 62`, `span: 5.14h`, `largest_gap: 5.1 min`, `breaks: 0`.
- **Stream Freshness:**
  - **Watcher:** newest stamp `1.3 min` ago (streaming continuously every ~5 min).
  - **Price Collector:** newest mark `0.7 min` (42s) ago, `1871` points, `holes: []`, **`price.ready: true`**.
  - **Uptime:** 6.0h continuous, `gap_hours: 0.0`, `coverage_pct: 25.0%` climbing linearly ($6\text{h}/24\text{h}$).
- **Daemon Liveness:**
  - Supervisor: `16844`
  - Collector: `74972`
  - Watcher: `17688`
  - Exporter: `64692` (two-stream gate active)
  - Telemetry: `5/5`
- **ETA for Gate Closure:** `2026-09-10T19:31:09Z` ($\approx$ **15:31 EDT Thursday**). All systems green.

---

## 6. Round 126 Phase 2 Pre-Registration Specifications (Pre-Approved)

All five quantitative definitions from Claude Code's Round 126 handoff are hereby settled with explicit numbers and mathematical rationale for pre-registration:

1. **HyperLiquid 1-Second Price Series Definition:**
   - **Data Premise Confirmed:** Independently audited `hyperliquid_data.db`. The `trades` table records every millisecond trade print with `(time, px, sz, notional)`. Verified live: 91 BTC trades in the last 60s (>1.5 trades/sec).
   - **Formula:** $P_{\text{HL}}(t) =$ price (`px`) of the **last BTC trade** in second $t$ from `trades` (where `coin = 'BTC'`), forward-filled through any empty second.
   - **Rationale:** Size-weighted mean (VWAP) blunts the step-function repricing by mixing pre- and post-shock executions within the same second, introducing artificial phase lag. The last print in interval $[t, t+1\text{s})$ accurately captures the terminal microstructure state.
2. **Uninformative-Shock Thresholds:**
   - **Polymarket Displacement Bar:** $|\Delta P_{\text{PM}}| < 0.02$ (2.0% implied probability shift, matching the Tier 2 `min_shift` rule).
   - **HyperLiquid Displacement Bar:** $|\Delta P_{\text{HL}}| / P_{\text{HL}}(T-5\text{s}) < 10\text{ bps}$ ($0.10\%$ relative return).
   - **Classification Rule:** An event is classified as `uninformative-shock` if **EITHER** venue fails to clear its displacement bar:
     $$\text{Class} = \text{uninformative-shock} \quad \text{if} \quad (|\Delta P_{\text{PM}}| < 0.02) \;\lor\; \left(\frac{|\Delta P_{\text{HL}}|}{P_{\text{HL}}(T-5\text{s})} < 0.0010\right)$$
   - **Rationale:** For lead $\Delta t_{\text{lead}} = t^*_{\text{HL}} - t^*_{\text{PM}}$ to be mathematically well-defined, both venues must experience a significant displacement. If either venue is stationary, the 50% displacement point $t^*_{50\%}$ is undefined noise.
3. **Anchor Timestamp $T$, Clock Sync, and Baseline:**
   - **Anchor:** $T = 14:00:00$ EDT ($18:00:00$ UTC) on the recorder host's W32Time-synchronized clock.
   - **Baseline:** Fixed at $t_{\text{base}} = T - 5\text{s}$ ($13:59:55$ EDT / $17:59:55$ UTC), guaranteed unperturbed by leaks or releases.
   - **Evaluation Window:** $[T, T + 300\text{s}]$. Total shift is $\Delta P_{\text{total}} = P(T+300\text{s}) - P(T-5\text{s})$.
   - **Invariance:** Because $t^*_{50\%}$ evaluates to an absolute UTC second on each venue, $\Delta t_{\text{lead}} = t^*_{\text{HL}} - t^*_{\text{PM}}$ is mathematically invariant to whether the Federal Reserve statement is released at 14:00:00.0 or 14:00:02.5.
4. **Polymarket Contract Selection & Panel Hierarchy:**
   - **Scope:** One Reaction Profile page per registered Fed market from `fomc_2026-09-16.rules.json` (3 contracts).
   - **Primary Active Contract:** The contract with the largest absolute displacement $|\Delta P_{\text{total}}|$, designated as the primary macroeconomic transmission instrument.
   - **Multi-Event Panel Key:** `(event, market_token)`.
5. **Scoring a HOLD (No-Change Scenario):**
   - A HOLD announcement qualifies as informative and computes a valid lead **if and only if** both venues clear their displacement bars ($|\Delta P_{\text{PM}}| \ge 0.02$ and $|\Delta P_{\text{HL}}| / P_{\text{HL}} \ge 10\text{ bps}$).
   - If either venue fails to displace, the print is logged as `uninformative-shock` in the event history, but **does not count toward the $N \ge 3$ informative events** required for a Lead-Lag Regime Verdict.
   - **Multi-Event Sequence Pre-Registered:**
     1. Event 1: FOMC Rate Decision — 2026-09-16 14:00 EDT
     2. Event 2: US CPI Release — October 2026 08:30 EDT
     3. Event 3: FOMC Rate Decision — 2026-10-28 14:00 EDT
6. **Sufficiency Bar & Architecture Approval (Refined & Ratified):**
   - **File Architecture Approved:**
     - Pre-registration: `cross_market/experiments/lead_lag_phase2_fomc.meta.json` $\to$ `wiki/experiments/lead_lag_phase2_fomc_meta.md`
     - Engine: `cross_market/event_study.py` (CLI + harness)
     - Adapter: `knowledge/ingest/event_study.py`
     - Tests: `cross_market/tests/test_event_study.py`
   - **Data Sufficiency & Feed Liveness Rule (Ratified Deviation Replacement):**
     - **Polymarket CLOB Leg:** Reject as `insufficient` (exit code 2) if any continuous hole $> 5.0\text{ s}$ occurs within $[T_0, T+300\text{ s}]$ or if $< 300$ discrete 1-second grid stamps are present on disk. (Since the recorder actively stamps every second, missing seconds denote recorder downtime).
     - **HyperLiquid Trades Leg:**
       1. **Feed Liveness**: Reject as `insufficient` (exit code 2) if any ALL-coin trade gap $> 5.0\text{ s}$ occurs inside $[T-5\text{ s}, T+300\text{ s}]$ (indicating collector websocket disconnect or pipeline stall).
       2. **Baseline Anchor**: Baseline is the last BTC trade print at or before $T-5\text{ s}$; rejected as `insufficient` (exit code 2) ONLY if older than $15.0\text{ s}$ (i.e. $t_{\text{print}} < T - 20\text{ s}$).
       3. **Forward-Filling**: BTC-quiet seconds forward-fill the last execution price and NEVER void the run for sufficiency.
       4. **Order of Evaluation**: Displacement bars are evaluated FIRST. If feeds are live but either venue fails to clear its displacement bar, classify as `uninformative-shock` (exit code 0). Discrete $t^*_{50\%}$ calculation is evaluated SECOND only if both venues displace.

---

## 7. Formal Ratification of Section 3 & 5 Refinements (2026-09-10 03:00 EDT)

All empirical and architectural cross-checks verified green:

1. **Noise Threshold & Snapshot Fallback (Section 3.2 & 7.1 Ratified):**
   - Empirical BTC 5-minute move distribution verified: median $5.36\text{ bps}$, $p_{75} = 9.59\text{ bps}$, $p_{90} = 14.71\text{ bps}$, $p_{99} = 24.88\text{ bps}$. A static $10\text{ bps}$ bar is traversed by $\approx 24\%$ of quiet overnight windows.
   - **Ratified Rule:**
     $$\text{Bar}_{\text{HL}} = \max\left(10\text{ bps}, \; 3 \times \widetilde{|\Delta_{5\text{m}}|}_{\text{pre}}\right)$$
     where $\widetilde{|\Delta_{5\text{m}}|}_{\text{pre}}$ is the sample median of overlapping 5-minute moves from `asset_snapshots.mark_px` across $[T-60\text{m}, T-5\text{s}]$.
   - **Snapshot Hole Fallback**: If fewer than $60$ BTC marks exist in `asset_snapshots` in $[T-60\text{m}, T-5\text{s}]$, $\text{Bar}_{\text{HL}}$ defaults to the $10.0\text{ bps}$ floor, recorded with JSON metadata flag `bar_source: "floor_fallback"` (otherwise `"trailing_60m_relative"`).
   - **Polymarket Bar**: $|\Delta P_{\text{PM}}| \ge 0.02$. If **EITHER** venue fails its bar, classify as `uninformative-shock`.
2. **Grid Start & Task Scheduler (Section 3.3 & 7.2 Ratified):**
   - Scheduled task `Monarch_FOMC_Drill` remains **UNTOUCHED** (no trigger shift; honoring the freeze).
   - Because `NextRunTime` is $13:58:58$ EDT (dynamic scheduler jitter / registration seconds), $T_0 \approx T - 58\text{ s}$.
   - Analysis grid evaluates $[T_0, T+300\text{ s}]$ where $T_0 = \text{timestamp of first Polymarket stamp on disk}$ (constraint $T_0 \le T - 30\text{ s}$). Pre-announcement interval is $[T_0, T - 5\text{ s}]$. Baseline is invariant at $T - 5\text{ s}$ ($13:59:55$ EDT / $17:59:55$ UTC).
3. **Event 2 Pinned & CPI Recorder (Section 3.5 & 5e Ratified):**
   - Event 2 pinned: **US Consumer Price Index (September Release) — Wednesday, October 14, 2026 at 08:30 EDT (12:30 UTC)**.
   - Round 126 writes this release instant into `lead_lag_phase2_fomc.meta.json` with market-selection rule (Core CPI MoM/YoY ladders, primary = largest $|\Delta P_{\text{total}}|$). Token IDs appended in dated re-registration before 10-12.
   - CPI recorder scheduled task will be created **AFTER** the 09-16 FOMC print.
   - Friday 08:28:00 EDT scratch probe on August CPI books (rungs 0.2%, 0.3%, 0.1%, duration 420s) confirmed approved as read-only exploratory scratch in `HOMEWORK.md`.
4. **AI-Tooling Architecture (Section 5 Ratified):**
   - **Rotate-Not-Rewrite:** Confirmed. `key_file.py` (public address) stays tracked. `Phem_key.py` deleted post-rotation. `*_key.py` gitignored. Remote blocked pending rotation.
   - **Watcher Scope:** Read-only gate + notification only. Never auto-executes Phase 1 runs.
   - **Tone Covariate:** Excluded from Phase 2 pre-registration. Uniform shock covariate is surprise vs $P_{\text{implied}}(T-5\text{s})$. Fed statement archived to `raw/inbox/` as exploratory.
   - **Pre-Freeze Implementation Order:** Round 126 $\to$ PreToolUse hook (with `DAEMON_UNLOCK`, expires $\le 2\text{h}$, agents cannot write) $\to$ `CLAUDE.md` + skills $\to$ subagents $\to$ Rehearsal. All other tooling deferred past 09-16.
   - **SQLite MCP:** Deferred past 09-16; requires URI `?mode=ro`, short-lived per-query connection, strict row cap.

---

## 8. Item 18 Phase 1 Closure & Phase 2 Pre-Registered Stopping Rule (2026-09-10 17:15 EDT)

1. **Phase 1 Closure Audited Green (Commit `81c67e3`):**
   - Run 3 evaluated verbatim on the ratified continuous window ($24.4\text{ h}$ span, $291$ tagged stamps, $8,391$ price points, $0$ breaks, $0$ holes).
   - All 4 subfamilies returned `no-lead` with high sample counts ($n \approx 1,500$, $|r| < 0.08$).
   - Across three disjoint windows spanning $>75\text{ h}$, continuous Polymarket probability shifts show **zero predictive lead** over HyperLiquid BTC perp price. The continuous-regime null is formally closed.
2. **Tier 2b Crypto Consensus $\implies$ `mixed` (Option a Ratified):**
   - The compiled rule in `knowledge/ingest/lead_lag.py` requires unanimity over the last 3 runs. Because Run 1 produced `polymarket-leads` (over a 9.3h price hole) while Runs 2 and 3 produced `no-lead`, `mixed` is the mathematically correct and honest status.
   - Historical integrity is preserved: Run 1 is not post-hoc excised. The narrative explicitly notes the data hole that generated Run 1's non-replicating artifact.
3. **Phase 1 Close-Out Documentation:**
   - Single source of truth for consensus remains `obsidian_vault/wiki/regimes/btc_macro_regime.md`.
   - The narrative synthesis will be archived within the Round 126 digest (`wiki/digests/round_126.md`) via `knowledge.ingest.digests`.
4. **Phase 2 Pre-Registered Stopping Rule & Economic Falsification:**
   - **Non-Displacing HOLD**: Classified as `uninformative-shock` (exit code 0). It carries zero information regarding cross-venue latency and **does not count** toward the $N \ge 3$ informative events panel.
   - **Falsification Stopping Rule 1 (Contemporaneous Repricing)**: If $N=2$ consecutive informative events yield $|\Delta t_{\text{lead}}| \le 1.0\text{ s}$ (`contemporaneous-event-repricing`) or HyperLiquid leads ($\Delta t_{\text{lead}} < -1.0\text{ s}$), the event-study trading desk is **permanently terminated** (cross-venue latency arbitrage is dominated by centralized venue feeds; zero actionable alpha).
   - **Falsification Stopping Rule 2 (Macro Insignificance Floor)**: If 3 consecutive registered prints (FOMC 09-16, CPI 10-14, FOMC 10-28) resolve as `uninformative-shock`, the line is retired on November 1 as dead capital.
   - **Capital Deployment Bar**: Automated trade execution bots will be funded **if and only if** $\Delta t_{\text{lead}} > +1.0\text{ s}$ (`polymarket-leads-event`) is observed on at least 2 of 3 informative events.
5. **Round 126 Authorization:**
   - Claude Code is cleared to proceed with authoring `cross_market/experiments/lead_lag_phase2_fomc.meta.json`, `cross_market/event_study.py`, `knowledge/ingest/event_study.py`, and `cross_market/tests/test_event_study.py`.

---

## 9. Round 126 Delivery Audited & Formally Ratified (2026-09-10 17:50 EDT / 21:50Z)

Commit `8dc52d4` delivered one day ahead of schedule. All four implementation deliverables, the definitional decisions, and empirical smoke tests have been independently audited and verified green.

### 1. Independent Cross-Checks & Verification
1. **Commit Audit (`8dc52d4`)**: Clean diff (+2,218 / -84 across 22 files). Phase 2 pre-registration, engine, vault adapter, compiler extension, and test suites delivered in full conformance with Section 6–8 specifications.
2. **Regression Test Suites**:
   - `pytest cross_market/tests/test_event_study.py` & `knowledge/tests/test_event_study_ingest.py`: **22/22 PASSED** (35.26s).
   - Full test coverage includes planted leads (+2s, -4s, 0s), flat venue uninformative handling, floor fallbacks, recorder holes, trade gaps, stale baselines, quiet-BTC forward-filling, and stopping rule state machines.
3. **Pre-Event CLI Refusal**:
   - `python -m cross_market.event_study --event fomc_2026-09-16` returns **exit code 2** (`INSUFFICIENT: window not complete: now < T+300 s; pass --force to evaluate anyway`), preventing premature or partial execution.
4. **Smoke Test on Real Rehearsal Data**:
   - Replicated over the 2026-09-06 rehearsal stamps + live database: 60 stamps parsed per token, 1,005 BTC prints, baseline age 0.369s, noise bar correctly falls back to `floor_fallback` (identifying the Round 119 snapshot hole), returns **exit code 2** (`polymarket stamps 60 < 300; polymarket hole 295 s > 5 s`). Every branch exercised on real data with zero crashes.
5. **Vault Lint & Schema Integrity**:
   - `obsidian_vault/wiki/experiments/lead_lag_phase2_fomc_meta.md` compiles cleanly with 8 `dev.parameters` under C1, 3 tokens under C2, and $[T-120\text{s}, T+300\text{s}]$ window under C5.
   - `python -m knowledge.lint`: **523 pages, 0 errors, 1 warning** (unrelated L11 sample floor warning on whale cascade).

### 2. Ratification of Section 2 Implementation Refinements
1. **Baseline Instant vs Bucket**: **RATIFIED**. Defining baseline price $P_{\text{base}}$ as the last BTC trade print at or before the exact instant $T - 5.000\text{s}$ strictly honors the information horizon and prevents lookahead into the $[T-5\text{s}, T-4\text{s})$ interval.
2. **Per-Token Sufficiency**: **RATIFIED**. Sufficiency is evaluated per individual token ($\ge 300$ stamps, no hole $> 5.0\text{s}$). An illiquid or holed token is excluded from the panel; the event as a whole is rejected as `insufficient` (exit 2) only if *zero* registered tokens pass.
3. **Primary Market Verdict Attribution**: **RATIFIED**. Event-level classification, lead $\Delta t_{\text{lead}}$, and `informative` flag are determined strictly by the primary active contract (maximum absolute displacement $|\Delta P_{\text{total}}|$ among sufficient tokens). Secondary token profiles are ingested for audit and research without voting in the panel sequence.

### 3. Rulings on Section 3.5 System Soft Points
1. **Midpoint Forward-Filling on One-Sided Books**: Forward-filling across transient one-sided books during order-book crossings is sound. A book remaining one-sided for $> 5.0\text{s}$ triggers the hole rule and excludes that token.
2. **$\pm 1.0\text{s}$ Latency Band vs Clock/Network Jitter**: The $\pm 1.0\text{s}$ tolerance band is robust against W32Time clock offset ($\sim 13\text{ms}$) and network latency ($\sim 100\text{ms}$). With Polygon block settlement at $2.0\text{s}$, sub-second leads are economically unexploitable; $|\Delta t_{\text{lead}}| \le 1.0\text{s}$ correctly defines un-arbitrageable contemporaneous repricing.
3. **CPI Event Window ($T_0$)**: The constraint $T_0 \le T - 30\text{s}$ natively supports the 120s pre-announcement baseline for CPI (08:30 EDT) without requiring code modifications.
4. **Scoring Stationary HOLDs**: A non-displacing HOLD where either venue fails its bar is classified as `uninformative-shock` (exit 0) and logged to the panel history. It does not count toward the $N \ge 3$ panel threshold and is subject to Falsification Rule 2.

### 4. Standing Operational Orders
- **Laptop Power Policy**: Operator is cleared to power down the laptop Thursday night and throughout Friday.
- **Wake Protocol**: On Friday or Saturday wake, run `resume_all.bat` and verify daemon status.
- **Next Operational Milestone**: Weekend rehearsal (Sat/Sun 09-13/14) via `python -m knowledge.drills.fomc_live_rehearsal`.

### 5. Pre-Registered Ruling on Data-Failure Invalidation (`insufficient` Exit 2)
1. **Zero Economic Information**: An `insufficient` result (exit code 2) indicates recorder downtime, an order-book hole $> 5.0\text{s}$, or a trades feed gap $> 5.0\text{s}$. It represents an experimental collection invalidation, not an economic non-event.
2. **Panel Status**: An `insufficient` event has `classification = None` and `informative = False`. It does **not** count toward the $N \ge 3$ informative events requirement, does not trigger or reset Stopping Rule 1, and does **not** count as an `uninformative-shock` print under Stopping Rule 2.
3. **Calendar Sequence & Forward Extension**:
   - The event numbering remains strictly chronological: Event 1 (FOMC 09-16), Event 2 (CPI 10-14), Event 3 (FOMC 10-28). There are no "retry" aliases.
   - If Event 1 voids on 09-16 due to data failure, Event 2 (CPI 10-14) proceeds normally. The evaluation panel extends forward to append the next calendar release (Event 4: US November CPI or December FOMC) via dated re-registration to ensure $N \ge 3$ valid prints.
   - Stopping Rule 2 evaluates the first 3 *technically valid* prints. Its November 1 retirement deadline is automatically extended to the date of Event 4 *if and only if* an earlier print was voided by verified technical data insufficiency.

---

## 10. Strategy Autoresearch Comprehensive Audit (2026-09-11 17:30 EDT / 21:30Z)

Full architectural and quantitative audit of the Karpathy-style strategy autoresearch pipeline (Phases 0–3, Campaign 2 closure, holdout failure, and 5-minute gross-edge screen).

### 1. Headline Rulings (Points 1, 3, 6)

#### Point 1: Out-of-Sample Holdout Failure (Severity: CRITICAL)
- **Verdict**: **Both (a) System Working As Intended and (c) Inherent Sample/Asset Limitations.**
  1. *Harness Vindicated*: The holdout's sole mathematical purpose is to catch cross-validation overfitting. In an iterative 40-trial hill climb, the 8 walk-forward folds become an effective *in-sample* training set through selection bias on the validation metric. Without the physical holdout barrier, the overfit candidate ($PF = 1.26$) would have been promoted to paper execution.
  2. *Statistical Power Deficiency*: 41 months on BTC + ETH 1h yields ~32,000 bars per asset. Sliced across 8 rolling folds, each out-of-sample fold spans only ~3.5 months (~2,500 bars), generating ~10–12 trades per fold (~100 pooled OOS trades per asset). BTC and ETH returns share $\rho > 0.85$ correlation, reducing the effective independent trade sample from 200 to $N_{\text{eff}} \approx 65$. The 95% bootstrap confidence interval of $PF = 1.26$ with $N=100$ spans $[0.94, 1.58]$; dropping to $0.75$ / $0.97$ in holdout is well within expected sampling variance.

#### Point 3: 5-Minute Gross-Edge Screen & Mandatory Gate Zero (Severity: CRITICAL)
- **Verdict**: **Mathematically Sound & Decisive in Negative Direction. MANDATED as Gate Zero.**
  1. *Mathematical Proof*: $\text{Net PnL} = \text{Gross PnL} - \text{Friction}$. On UM crypto perps, round-trip friction is measured at $10.0\text{ bps}$ (1 tick slippage + 0.05% taker $\times 2$). In-sample gross edge over the full research span without fold penalties represents an absolute theoretical upper bound on out-of-sample net performance. If $\text{Gross}_{\text{IS}} < 10.0\text{ bps}$, then $\text{Net}_{\text{OOS}} < 0$ almost surely.
  2. *Empirical Confirmation*: At 5m, BTC gross edge was $-0.95$, $+0.63$, $-0.52$, $-0.19\text{ bps}$. Even fading ($+0.63\text{ bps}$) is $16\times$ below friction.
  3. *Protocol Rule*: Mandatory **Gate Zero** added to `campaign.meta.json`: No campaign may be registered on any timeframe unless the candidate family demonstrates full-span $\text{Gross Edge}_{\text{IS}} \ge 1.5 \times \text{Friction}$ ($\ge 15.0\text{ bps}$ for taker perps).

#### Point 6: Plateau Gate Mis-Specification (Severity: CRITICAL — Live Bug)
- **Verdict**: **Arithmetic Mean-of-Ratios is Mathematically Invalid. Replace with Ratio-of-Sums.**
  1. *The Flaw*: `ratio = plateau_score / own_score if own_score > 0 else 0.0` followed by `mean(r.plateau_ratio)` creates extreme denominator instability when `own_score` (Calmar) is near zero ($0.01-0.05$). On ETH, individual fold ratios exploded/collapsed ($1.53, 0.00, -1.59$), driving the mean down to $0.408$ (failing the $0.60$ gate) while median was $0.630$ and ratio-of-sums was $0.625$.
  2. *Concrete Replacement*:
     $$\text{plateau\_ratio} = \frac{\sum_{w \in \text{folds}} \max(0, \text{plateau\_score}_w)}{\sum_{w \in \text{folds}} \max(0, \text{own\_score}_w) + \epsilon} \quad (\epsilon = 1e-4)$$
     This measures aggregate neighborhood stability across all folds without division noise.

---

### 2. Core Methodological Findings (Points 2, 4, 5)

#### Point 2: Holdout Span & Promotion Criteria (Severity: HIGH)
- A 3-month holdout (19 BTC trades) has statistical power $< 0.30$ to reject $PF \le 1.0$. While sufficient for terminal rejection, it is insufficient for promotion.
- **Rule**: Minimum holdout span for promotion is $\ge 6$ months continuous or $\ge 50$ trades per asset. If holdout produces $< 30$ trades, verdict is `INCONCLUSIVE_INSUFFICIENT_SAMPLE` and promotion is barred.

#### Point 4: In-Sample Calmar Optimization vs Over-Filtering (Severity: HIGH)
- In-sample Calmar on short 4-month folds rewarded a 200-bar trend filter because restricting trade count flattered in-sample drawdowns, while lagging out-of-sample regimes ($S=0.91$). Kept default 100 survived as an unexamined default ($S=1.26$).
- **Rule**:
  1. Fold optimization objective must include sample-size shrinkage: $\text{Objective} = \text{Calmar} \times \min(1, \sqrt{N / 20})$.
  2. Overarching trend window is a *macro structural parameter* that must be fixed globally rather than tuned per fold.

#### Point 5: Grid Topology & Optimum (Severity: MEDIUM)
- Grids with 2 values per dimension leave all points as boundary points (only 1 neighbor), introducing 50% boundary distortion in `_plateau_score`.
- **Rule**: Enforce minimum 3 values per numeric dimension ($[v - \Delta, v, v + \Delta]$) and bound grid combinations $9 \le N_{\text{grid}} \le 27$.

---

### 3. Harness Defects & Design Audit (Points 7–11)

- **Point 7 ($S = \min$ vs Pool)** (Severity: HIGH): Retain $S = \min(S_{\text{BTC}}, S_{\text{ETH}})$. Cross-asset invariance is required to prevent BTC from subsidizing an unprofitable ETH curve-fit.
- **Point 8 (Grouped Ablation)** (Severity: MEDIUM): One-at-a-time ablation fails on collinear mechanisms (position test and path shape). Enforce functional group ablation (`Directional_Group = {position, path_shape}`).
- **Point 9 (Hard Gate Separation)** (Severity: MEDIUM): Confirmed. Volatility expansion preserved fold consistency (6/8 vs 4/8) while leaving PF unchanged. Hard gates must never be collapsed into a scalar utility.
- **Point 10 (Dirty Tree Exemption)** (Severity: LOW): Exemption of `ledger.tsv` and `trials/` is acceptable *only* when paired with atomic git commits inside `run_trial.py`.
- **Point 11 (`deploy_params` for Holdout)** (Severity: CRITICAL): Using the last fold's in-sample selection is biased by the final fold's idiosyncratic regime. **Replace with Modal Parameter Selection** (most frequent parameter set across passing folds) or the multi-fold parameter centroid.

---

### 4. Process, Integrity, and original Items (Points 12–18)

- **Point 12 (Fold Stability)**: Verified. Integer-index slicing on clean CSVs with SHA256 fold fingerprinting is deterministic and cryptographically tamper-proof.
- **Point 13 (Metric Primary)**: Profit Factor is the correct primary score for screening; Calmar on small trade counts is prone to zero-drawdown infinities.
- **Point 14 (Gate Bars)**: Raise `min_oos_trades_per_asset` from 40 to 60 ($7-8$ trades/fold). Keep $WFE \ge 0.50$ and $maxDD \le 8\%$.
- **Point 15 (Literal Detector)**: AST inspection must check `ast.Compare` to ban direct price comparisons against numeric literals, not just constants $> 10,000$.
- **Point 16 (Adversarial Surface)**: Protect against module-level state leakage across folds, dummy parameter injection in `PARAM_GRID`, and $O(N^2)$ algorithmic timeouts.
- **Point 17 (Phase Ordering)**: Ratified. Adapter compiles vault page first; `knowledge.ratify` executes second.
- **Point 18 (Sovereign Operator Override)**: Operator instructions override agent locks. However, unattended overnight runs must hard-refuse if `antigravity_ratification: OUTSTANDING` without an explicit `--operator-override` flag.

---

### 5. Brainstorming & Long-Horizon Protocol
1. **Trial-Deflated Acceptance Threshold**: Replace static 5% hurdle with a Deflated Sharpe/PF threshold:
   $$S_{\text{threshold}}(n) = S_{\text{base}} \times \left(1 + 0.05 \cdot \sqrt{\ln(1 + n)}\right)$$
2. **Unattended Failure Modes**: Recycle worker processes after each fold to prevent memory leaks; stream compressed JSON; enforce strict timeout kill signals.
3. **Six-Month Ledger Provenance**: Append the unified git diff directly into `trials/<id>.json` so strategy evolution is self-contained.








