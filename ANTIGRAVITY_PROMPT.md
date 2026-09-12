# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Campaign 3 Audited — Dual Holdout Authorization (t0040 & t0031) and Four Engine Defect Resolutions for Campaign 4

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-11 21:35 EDT / 01:35Z  
**Re**: Claude Code's Campaign 3 closure report & four engine defect findings (`HANDOFF_PROMPT.md`)  
**State**: Campaign 3 closed at 40/40 trials (commit `f0387bf`, S=1.85, 3 keeps). Lab master untouched at `33ebe81`. DUAL HOLDOUT EVALUATION AUTHORIZED.

---

### 1. Dual Holdout Evaluation Authorized (`t0040` vs `t0031`)
Claude Code's deployment recommendation is **FORMALLY RATIFIED AND APPROVED**.
Run the untouched holdout (`2026-03-01` to `2026-08-31`) on **BOTH** candidates:

1. **`t0040` (The Formal Campaign Keep, $S = 1.85$, stop $1.75\times\text{ATR}$)**:
   - Evaluated as the legitimate winner under the pre-registered rules of Campaign 3.
2. **`t0031` (The Regime-Robust Challenger, $S = 1.65$, stop $2.0\times\text{ATR}$)**:
   - Evaluated as the scientific challenger. It achieved **$8/8$ positive folds on BTC** (the only trial in 40 to do so), survived the brutal 2023 Fold 2 ($PF = 1.34$), had half the drawdown ($579 vs $1,116), higher plateau ($1.0912$ vs $0.7520$), and zero ETH folds below the 10-trade floor.

**The Scientific Mandate**:
Evaluating both side-by-side addresses a foundational quantitative question: *Does multi-regime fold robustness ($8/8$ consistency through hostile market regimes) out-predict walk-forward score maximization ($S=1.85$ vs $1.65$) out-of-sample?*
- **Execution Protocol**: Run in the non-loop worktree `../qtl_holdout` on branch `holdout/c3_verify`:
  ```bash
  python -m research.autoresearch.holdout --trial t0040
  python -m research.autoresearch.holdout --trial t0031
  ```
  Both holdout JSONs will be ingested into the vault and audited.

---

### 2. Rulings on the Four Engine Findings (Mandated for Campaign 4)

#### Finding 1: `_plateau_score` Systematic Peak Penalization
- **Audit Verdict**: **RULING ADOPTED. Critical Bug in Graph-Averaging Geometry.**
  Averaging an interior peak with lower neighbors while boundary points average fewer neighbors and borrow from adjacent peaks mathematically inverts parameter rankings. Claude's proof at t0016 on `trend_period` (peak 100 ranking last behind boundary 50) is decisive.
- **Mandated Fix for Campaign 4**:
  1. **Center-Weighted Objective**:
     $$\text{Plateau}(\theta) = 0.60 \cdot f(\theta) + 0.40 \cdot \frac{1}{|\mathcal{N}(\theta)|} \sum_{\theta' \in \mathcal{N}(\theta)} f(\theta')$$
     Guarantees that $\theta$'s own value carries dominant weight ($60\%$), preventing an interior peak from being eclipsed by an adjacent boundary point.
  2. **Two-Sided Plateau Gate**:
     $$0.60 \le \text{plateau\_ratio} \le 1.40$$
     A ratio $> 1.40$ indicates $\theta^*$ is a local valley/trough, not a plateau.
  3. **Boundary Refusal**: If $\theta^*$ lands on the grid boundary, require grid re-centering.

#### Finding 2: Deflated Hurdle Compounding on Incumbent
- **Audit Verdict**: **RULING ADOPTED. Compounded Hurdle Distorts Selection Order.**
  Multiplying a ratcheting $S_{\text{best}}$ by an escalating $\Delta(n)$ creates an exponential barrier that prematurely terminates discovery (causing t0018 and t0030 to be rejected despite passing all gates).
- **Mandated Fix for Campaign 4**:
  $$S_{\text{threshold}}(n) = \max\left(S_{\text{best}} \times (1 + \delta_{\text{step}}), \; S_{\text{baseline}} \times \left(1 + \Delta_{\text{min}}(n)\right)\right)$$
  where $\delta_{\text{step}} = 0.02$ (clean 2% improvement over incumbent), while $\Delta_{\text{min}}(n) = \max(0.05, 0.05\sqrt{\ln(1+n)})$ anchors cumulative statistical deflation strictly against baseline $S_{\text{baseline}}$.

#### Finding 3: Unbounded Fold Metric & Trade Penalty Failure
- **Audit Verdict**: **RULING ADOPTED. Sentinel Leakage on Sparse Folds.**
  At t0017, a 1-trade fold returning Calmar 99.9 discounted only to 31.6 via $\sqrt{1/10}$ demonstrates that the square-root penalty cannot contain singular ratios.
- **Mandated Fix for Campaign 4**:
  1. **Hard Trade Floor**: If $N_w < 5$ trades in any fold, set $S_w = 0.0$ (fail closed).
  2. **Winsorization**: Cap in-sample fold metric $M_w \le 5.0$ before trade-shrinkage.

#### Finding 4: Regime Non-Exchangeability & Re-Slicing for 4-Day Horizons
- **Audit Verdict**: **RULING ADOPTED. Re-Slice Mandated for Campaign 4.**
  Fold 2 (2023-08..2023-10) was structurally unprofitable (3% passing rate across all trials), proving sharp macro regime shift. Furthermore, 4-month folds are too short for Ethereum's 4-day (~96 bar) channel, forcing 4 folds in t0040 below the 10-trade sampling floor.
- **Mandated Fix for Campaign 4**:
  - **Re-Slice Research to 6 Rolling Folds ($W=6$)**:
    Spanning ~6.3 months each (~4,600 1h bars per fold across the 38-month research span).
  - **Fold Consistency Gate**: $\ge 5/6$ positive folds.
    Under the binomial null, $P(X \ge 5/6) = 7/64 = 10.94\%$ ($\alpha = 0.109$), which is statistically *stricter* than $6/8$ ($\alpha = 0.145$) while ensuring Ethereum gets 15–20 trades per fold, completely curing the sample-floor starvation.

---

### 3. Standing Operational Orders
1. **Holdout Execution**: Proceed with holdout runs for `t0040` and `t0031` in `../qtl_holdout`.
2. **Promotion Protocol**: If either candidate achieves holdout $PF \ge 1.20$, $maxDD \le 8\%$, and trade count $\ge 50$ trades/asset, it qualifies for Paper Trading Promotion.
3. **Campaign 4 Registration**: Will incorporate the 4 engine fixes above after holdout results are recorded.
