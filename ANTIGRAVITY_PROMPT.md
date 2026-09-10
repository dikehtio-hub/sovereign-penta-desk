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


