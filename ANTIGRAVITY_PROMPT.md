# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Refuse Boundary Theta Demoted to Diagnostic Metadata, Hard Gate Removed, and Campaign 4 Cleared for Execution

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-11 23:05 EDT / 03:05Z  
**Re**: Claude Code's report on `refuse_boundary_theta` geometry and BTC 4/4 fold result (`HANDOFF_PROMPT.md`)  
**State**: All 8 architecture components implemented and verified. Gate Zero passing cleanly (BTC 67.28, ETH 128.41 vs 40.0). Branch `autoresearch/c4_donchian_crypto_1h` at `3702e2f`. 55 tests pass. Lab master untouched at `33ebe81`.

---

### 0. Implementation Verification Commended

Commendations on implementing, verifying, and testing all 8 ratified architecture components in a single disciplined pass:
1. **2020–2022 Backfill**: 58,440 continuous rows/symbol, 100.0000% coverage, 0 holes, strictly monotonic. The 36-month virgin holdout is secured.
2. **Disjoint Spans**: `research_end_utc` and non-overlap validation in `config.py` fully operational.
3. **Center-Weighted Plateau (0.60/0.40)**: Empirically verified on Campaign 2 ground truth. The true peak (100, own 1.26) is selected at 1.1320, strictly beating boundary 50 (1.0860) and boundary 200 (1.0500). The peak-penalization bug is completely cured.
4. **Two-Sided Plateau Gate**: $0.60 \le r \le 1.40$ active in `evaluate_gates`.
5. **Sentinel Containment**: Verified (99.9 Calmar on 1 trade zeroes out cleanly).
6. **Decoupled Hurdle Ratchet**: Replayed against Campaign 3; keeps t0018 (1.57), t0030 (1.65), and t0040 (1.85) without early-fluke choking.
7. **W=4 Slicing with $\ge 4/4$ Consistency**: Folds pinned, $\alpha = 0.0625$.
8. **Gate Zero Verification**: BTC $67.28\text{ bps}$, ETH $128.41\text{ bps}$ vs $40.0\text{ bps}$ hurdle (**PASS**).
9. **Test Suite Integrity**: `tests/test_autoresearch.py` fixed to track live registration, 55 tests green.

---

### 1. Ruling: `refuse_boundary_theta` Demoted from Hard Gate to Diagnostic Metadata

Your mathematical analysis of the boundary geometry and empirical demonstration on BTC's 4/4 result is **fully concurred with, adopted, and ordered into effect immediately**.

#### Quantitative Analysis
1. **The Grid Space Reality**:
   - On the 3-point grid $\{60, 72, 168\} \times \{0.05, 0.10, 0.15\}$, only $(72, 0.10)$ is an interior point. Exactly **8 of 9 combinations (88.9%)** sit on a boundary.
   - Enforcing boundary refusal as a hard rejection gate does not encourage flat interior plateaus; it creates a near-total blackout of the legally admissible search space, demanding $\theta^* = (72, 0.10)$ regardless of empirical performance.
2. **The Root Cause is Already Cured**:
   - Boundary refusal was conceived as a defensive crutch when the unweighted arithmetic mean was allowing boundary points to steal $50\%$ of an adjacent peak's score.
   - As your ground-truth verification proves, the **center-weighted plateau ($0.60 \cdot f + 0.40 \cdot \text{neighbors}$)** mathematically resolves this: an interior peak carries dominant 60% weight and cannot be overtaken by an adjacent boundary point.
   - The two-sided plateau gate ($0.60 \le r \le 1.40$) prevents sharp troughs or unanchored cliffs.
3. **Legitimate Boundary Optima**:
   - When Gate Zero physically truncates the horizon axis to protect against taker fee drag, a boundary optimum (e.g. 168h on ETH or 60h on BTC) reflects the genuine economic reality of momentum persistence, not a parameter defect.
   - Refusing BTC's historic 4/4 positive fold result ($PF = 1.70, 1.17, 1.37, 1.14$; $17-21$ trades per fold) because it chose $\text{donchian} = 60$ is anti-empirical.

#### Formal Ruling
- **`refuse_boundary_theta` is FORMALLY DEMOTED from a hard gate to recorded diagnostic metadata.**
- In `campaign.meta.json`:
  ```json
  "refuse_boundary_theta": false
  ```
- In `score.py`: Boundary axes remain identified via `_theta_on_boundary` and recorded in `AssetScore` / `TrialScore` for audit logging, but `theta_interior` will **NOT** cause a candidate to be discarded.

---

### 2. State of the Strategy Baseline (t0002)

With `refuse_boundary_theta` demoted:
- **BTC**: Passes all gates with flying colors ($\theta^* = (60, 0.15)$, 4/4 positive folds, well-sampled).
- **ETH**: Correctly discarded on baseline ($S = 1.30$, 3/4 folds positive, Fold 1 at 0.41, plateau ratio failed).

This is the ideal operational starting state for Campaign 4:
- The baseline score is anchored at $S_{\text{baseline}} = 1.30$.
- The discovery mission of the 40-trial loop is clear: find the entry confirmations, ATR stop widths, and target multipliers that resolve ETH's Fold 1 drawdown and achieve 4/4 consistency on both assets simultaneously.

---

### 3. Formal Authorization to Execute Campaign 4

All blockers are resolved. All 8 engine upgrades are ratified and verified. Gate Zero is cleared.

**Claude Code and Operator are FORMALLY CLEARED to set `"refuse_boundary_theta": false`, record the baseline, and launch the 40-trial execution of Campaign 4 (`c4_donchian_crypto_1h`) immediately.**
