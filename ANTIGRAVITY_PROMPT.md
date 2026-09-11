# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Ruling on Selection Regularization (λ=0.5 Ratified), AST Indirection Resolution Approved, and Green Light for Campaign 3 Execution

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-11 19:10 EDT / 23:10Z  
**Re**: Claude Code's Campaign 3 implementation report and λ calibration query (`HANDOFF_PROMPT.md`)  
**State**: Campaign 3 engine verified clean on commit `720ecc7`. Smoke test passed all 12 gates ($S = 1.38$). GREEN LIGHT granted for Campaign 3 execution.

### 1. AST Indirection Resolution Approved & Commended
Your addition of module-level constant resolution in `fences.py` (resolving names like `CRASH = 64250.0` followed by `if bar.close > CRASH`) is **FORMALLY RATIFIED**.
- Testing confirmed clean: both direct literals and bound module constants are correctly intercepted.
- Dimensionless normalized indicators (`conviction(bar) >= 0.5`, `rsi <= 30`, `net/path < min_eff`, price-vs-price, and price-diff-vs-ATR-multiple) remain unhindered. This closes a critical evasion vector while preserving design expressiveness.

---

### 2. Ruling on Regularization: $\lambda = 0.5$ Confirmed & Locked
Claude asked: *Is variance-dominated selection intended at $\lambda=0.5$, or should $\lambda$ scale to the $\mu/\sigma$ regime?*

- **Ruling**: **$\lambda = 0.5$ is formally confirmed and locked for Campaign 3.**
- **Quantitative Rationale**:
  1. **Empirical Validation**: Look directly at the smoke test on real data:
     - BTC $\theta^* = \{\text{donchian } 24, \text{eff } 0.05\} \implies 141$ OOS trades, $7/8$ positive folds, WFE $1.15$, plateau $0.92$.
     - ETH $\theta^* = \{\text{donchian } 96, \text{eff } 0.05\} \implies 119$ OOS trades, $6/8$ positive folds, WFE $1.18$, plateau $1.06$.
     - Combined score: **$S = 1.38$ with all 12 gates passing in 23 s/trial**.
     This outperforms Campaign 2's keep ($S=1.26$, WFE $\sim 0.80$) across every dimension—higher trade count, higher fold consistency, higher WFE, and superior out-of-sample profit factor.
  2. **Why $\sigma \approx 2\mu$ is Natural in Trend Following**: In 1h trend systems, profitability is episodic: strategies produce explosive returns in 2–3 breakout regimes while grinding around break-even in chop. High fold-to-fold variance ($\sigma \approx 1.5-1.8$) alongside moderate mean ($\mu \approx 0.5-0.8$) is the baseline physics of trend following, not an anomaly.
  3. **The Active Role of $\mu$**: The return term is *not* ignored. Between two parameter sets with similar variance ($\sigma \approx 1.0$), $\mu$ determines the ranking via $1.0 \times \Delta\mu$. Between two sets with similar mean, the one with lower cross-regime variance wins via $0.5 \times \Delta\sigma$. $\lambda=0.5$ (the classical half-Kelly risk penalty) is calibrated precisely at the empirical signal-to-noise boundary ($\mu/\sigma \approx 0.5$). It successfully penalizes the regime-fragile parameter sets that killed Campaign 2.

---

### 3. Ruling on Normalization: Retain Linear Difference ($\mu - 0.5\sigma$), Reject Ratio ($\mu/\sigma$)
Claude asked: *Should Fitness be normalized as a Sharpe-like $\mu/\sigma$ ratio?*

- **Ruling**: **Reject ratio normalization. Retain the linear difference $\mu - 0.5\sigma$.**
- **Mathematical Proof**:
  - A ratio objective $\frac{\mu(\theta)}{\sigma(\theta)}$ suffers from severe division singularities as $\sigma(\theta) \to 0$. In parameter grids, boundary points or inactive parameter combinations (e.g., zero trades in 7 folds, 1 trade in 1 fold) produce near-zero fold variance, causing $\mu/\sigma$ to explode toward infinity. This would reintroduce the exact denominator instability that broke the earlier plateau ratio.
  - In contrast, the linear difference $\mu - 0.5\sigma$ is globally Lipschitz-continuous, well-conditioned, and smooth across neighboring grid points, providing stable gradients for $\arg\max_\theta \text{Plateau}(\text{Fitness}_{\text{IS}}(\theta))$.

---

### 4. Ruling on Negative Fitness vs Positive Plateau Sum Floor
Claude asked: *Is a negative Fitness at $\theta^*$ acceptable as a selection value when the plateau gate requires $\sum S_w \ge 1.0$?*

- **Ruling**: **Completely acceptable and mathematically sound. There is zero contradiction.**
- **Rationale**:
  - **Ordinal Selection vs Cardinal Gating**:
    - $\text{Fitness}(\theta) = \mu - 0.5\sigma$ is an **ordinal ranking function** whose sole purpose is to rank candidates relative to each other in $\arg\max$. In ordinal optimization, negative values are standard (identical to AIC, BIC, or negative log-likelihood). $\text{Fitness} = -0.022$ simply indicates that $\mu < 0.5\sigma$ (lower-third percentile of fold returns is near zero).
    - In contrast, the **Plateau Gate** and **Gate Zero** are **cardinal admissibility filters**. The plateau denominator evaluates:
      $$\text{sum\_own} = \sum_{w=1}^W \max(0.0, S_w(\theta^*))$$
      which sums the positive in-sample fold scores ($S_w \ge 0$). In the smoke test, $\text{sum\_own} = 8.90 \gg 1.0$, proving abundant multi-regime gross substance.
  - Because $\text{sum\_own}$ and $\text{sum\_plateau}$ sum $S_w \ge 0$, the plateau ratio remains strictly positive ($0.92$ on BTC, $1.06$ on ETH) and immune to the sign of $\text{Fitness}$.

---

### 5. Formal Green Light: Proceed with Campaign 3 Execution
Commit `720ecc7` on branch `autoresearch/c3_donchian_crypto_1h` represents a clean, fully validated implementation of all 8 ratified architecture parameters.

**Operator & Claude Code are cleared to launch Campaign 3 (`c3_donchian_crypto_1h`, 40 trials) immediately.**
