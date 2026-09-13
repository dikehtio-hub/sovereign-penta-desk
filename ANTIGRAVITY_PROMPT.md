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

## Section 51: Dynamic t0030 Regression Target, Engine Exit Path Booking, New Stack ID Mandate, and Capped Calmar Discriminator Codified

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-13 00:45 EDT / 2026-09-13 04:45Z  
**Re**: Ruling on three corrections, two architectural notes, and build authorization from Claude Code's handoff:  
(1) Condition 2 regression target codified as dynamically loaded full-precision fields directly from `t0030.json` at test time (retyped numbers retracted; verified exact pooled OOS values: BTC $3,924.52 net / 53 trades, ETH $8,484.25 net / 81 trades, $S = 2.09$);  
(2) Condition 1 boundary position booking codified strictly through the engine's canonical exit computation (`backtesters/engine.py:315` including 1-tick slippage and two-sided 0.05% taker fees), eliminating ad-hoc friction constants;  
(3) Tier 2 promotion stack ID corrected: `STACK_9_CANDIDATE` stricken (permanently disabled slot); promoted strategies must receive a newly minted stack ID (e.g. `STACK_11_<NAME>`);  
(4) Combined-curve gate discriminator rule codified: whenever the volatility weight is capped at $w_{\max} = 3.0$, the comparison is judged exclusively on Calmar (MaxDD pass is dilution by construction);  
(5) Host probing order confirmed (`data.binance.vision` probe first, fallback to `fapi.binance.com`);  
(6) AutoResearch Harness Changes 1–3 fully approved and queued for the Operator's Go-Ahead.  
**State**: DEV `061aa53` + 42 dirty (21 modified, 21 untracked), 0 staged, measured 2026-09-13 04:25:03Z. Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked), 0 staged. Genuinely clean: `qtl_autoresearch` `2e9d222` on `autoresearch/c4_donchian_crypto_1h`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. Concurrences & Protocol Verification (§0)

1. **Protocol Adherence Confirmed**: Exact HEAD `061aa53` and dirty count (42 entries) verified via runtime git query immediately prior to assembly.
2. **Acceptances Confirmed**: Full acceptance of Section 50's core architecture: wick $\ge 50\%$ of range as the canonical rule, 6.0 months / 50 trades Tier 2 floor, MTM series output, continuous root funding storage, and branch strategy.

---

### 1. Condition 2: Dynamic `t0030.json` Regression Target Formally Codified (§1)

1. **Retraction of Retyped Benchmarks**: Claude's audit of `qtl_autoresearch/research/autoresearch/trials/t0030.json` is accepted in full. Retyped figures from earlier calibrations are completely retracted.
2. **Dynamic File-Based Regression Target Mandated**:
   The regression acceptance test for Harness Change #3 must NOT use hardcoded numbers in test files. **The test suite must load `t0030.json` dynamically at test execution time and assert exact bit-identical equality** across all full-precision record fields:
   - **BTCUSDT Pooled OOS**: Gross Profit `$7,519.50`, Gross Loss `$3,594.97`, Net PnL `$3,924.52`, Max Drawdown `$687.49`, Total Trades `53`.
   - **ETHUSDT Pooled OOS**: Gross Profit `$14,349.49`, Gross Loss `$5,865.25`, Net PnL `$8,484.25`, Max Drawdown `$903.54`, Total Trades `81`.
   - **Overall Score**: $S = \min(2.09, 2.45) = 2.09$ (rounded ratio).
   - **Trade Counts**: Exactly `134` OOS trades ($53 + 81$) and `264` IS trades ($132 + 132$).
   Every dollar and cent must match identically between pre- and post-MTM backtests.

---

### 2. Condition 1: Boundary Position Booking via Canonical Engine Exit Path (§2)

1. **Retraction of Ad-Hoc Friction Constant**: The approximate "10 bps exit friction" formulation is retracted.
2. **Engine Canonical Closing Logic Codified**:
   At the final bar of each walk-forward fold test window, any open position must be booked into the MTM series **using the exact same closing computation executed by `backtesters/engine.py:315`**:
   $$\text{adj\_exit} = \text{Close} \pm (\text{slippage\_ticks} \times \text{tick\_size})$$
   $$\text{pct\_fee} = (\text{adj\_entry} + \text{adj\_exit}) \times \text{point\_val} \times \text{qty} \times \left(\frac{\text{taker\_fee\_pct}}{100.0}\right)$$
   This guarantees that entry/exit slippage and two-sided taker fees are accounted for to the exact cent, seamlessly handling perps and spot pairs via their respective `asset_specs.json` definitions without special cases.

---

### 3. Tier 2: Dedicated New Stack ID Mandated (§3)

1. **`STACK_9_CANDIDATE` Stricken**: As permanently codified in `portfolio_config.yaml:453–454`, `STACK_9_CANDIDATE` is `enabled: false permanently` and serves exclusively as a placeholder for the rotating autoresearch loop.
2. **New Stack ID Rule**:
   Any strategy passing Tier 1 Historical Invariance and entering Tier 2 Forward Paper Incubation must be assigned a **newly minted, unique stack ID** (e.g. `STACK_11_<FAMILY_NAME>`) in both its isolated paper configuration (`config/paper_<strategy_id>.yaml`) and subsequent production files.

---

### 4. Bounded-Volatility Combined-Curve Gate Discriminator (§4)

1. **Dilution Recognition**: Accepted Claude's mathematical proof: When the leverage cap $w = w_{\max} = 3.0$ binds, the candidate carries less realized volatility than t0030. Blending 50/50 dilutes t0030's risk, causing $\text{MaxDD}(R_{\text{comb}}) < \text{MaxDD}(R_{t0030})$ to pass by construction.
2. **Calmar as Sole Discriminator Under Cap**:
   We formally register that in any evaluation where $w_{\max} = 3.0$ binds:
   - A pass on the $\text{MaxDD}$ gate is considered a trivial artifact of scale dilution and is **inadmissible as evidence of diversification**.
   - The combined portfolio acceptance is decided **strictly and exclusively by the scale-invariant Calmar ratio**:
     $$\text{Calmar}(R_{\text{comb}}) > \text{Calmar}(R_{t0030})$$

---

### 5. Archive Host Probing Order Confirmed (§5)

1. **Probing Sequence Confirmed**:
   `fetch_binance_funding.py` will probe `https://data.binance.vision/data` with a lightweight probe at startup. If reachable, monthly funding archives will be downloaded directly; if unreachable or missing specific intervals, it falls back to the public `fapi.binance.com` REST endpoint. Both paths are keyless and cost $0.

---

### 6. AutoResearch Build Sequence: Formally Authorized (§6)

1. **Implementation Scope Confirmed**:
   - Repository & Branch: `qtl_autoresearch` on a new branch off `2e9d222`, keeping `autoresearch/c4_donchian_crypto_1h` sealed.
   - Sequence:
     1. Funding fetcher (`fetch_binance_funding.py` targeting `data/continuous/*funding_binance.csv`).
     2. Daily MTM series in `engine.py` with boundary booking and dynamic `t0030.json` regression validation.
     3. Funding PnL accounting.
   - Estimated duration: ~60–75 minutes ($0 cost).
2. **Sole Remaining Gate**:
   **The Operator's Go-Ahead is the sole trigger required to begin execution.**

---

### 7. Reconciled Standing Ledger

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Operator Choice: Remote Privacy | Active | Operator | "Will the remote be private?" determines Git tracking vs manifest for `raw/fetched/`. |
| 5 | Intake Hardening | **NEXT** | Intake Session | Injection defense clause, runtime socket guard, GitHub path fix, exit-code delta. |
| 6 | Harness Changes 1–3 Build | **READY** | **Operator Go-Ahead** | New branch off `2e9d222`; vision fetcher $\to$ continuous root $\to$ MTM $\to$ funding PnL. |
| 7 | Campaign 5 Registration | Queued | Harness Ready | Two-tier holdout, 468-day OOS MTM gates, matched-volatility combined curve. |
| 8 | Operator Reading Inbox | **READY** | Operator | Family A (50% range wick), Family B (funding carry), Family C (`ETHBTC` + `BNBBTC`). |

All corrections codified. Systems standing by for the **Operator's Go-Ahead** on Harness Changes 1–3 and Sunday's lead-lag gate closure at **15:21Z (~11:21 EDT)**.
