# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Rulings on Campaign 3 Calibration — Plateau Sum Floor, 6-Month Re-Slice, and Raw PF WFE

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-11 18:35 EDT / 22:35Z  
**Re**: Claude Code's Section 12 calibration response (`HANDOFF_PROMPT.md`)  
**State**: All 3 calibration points ruled and locked. Full Campaign 3 engine matrix pre-approved for single-pass implementation.

### 1. Ruling 1: Retain `MIN_OWN_SUM = 1.0` on Cross-Fold Sum $\sum_{w=1}^W S_w(\theta^*)$
- **Ruling**: **Apply `MIN_OWN_SUM = 1.0` to the cross-fold sum of in-sample scores.**
- **Specification for `score.py`**:
  For candidate $\theta^*$, let $S_w(\theta^*)$ be the penalized score on fold $w \in \{1, \dots, W\}$.
  Let $P_w(\theta^*) = \frac{1}{|\text{Neighbors}|} \sum_{\theta' \in \text{Neighbors}(\theta^*)} S_w(\theta')$ be the average neighbor score on fold $w$.
  Define:
  ```python
  sum_own = sum(max(0.0, S_w) for S_w in own_scores_by_fold)
  sum_plateau = sum(max(0.0, P_w) for P_w in neighbor_scores_by_fold)
  MIN_OWN_SUM = 1.0

  if sum_own < MIN_OWN_SUM:
      plateau_ratio = 0.0  # fail closed: unmeasurable aggregate edge
  else:
      plateau_ratio = round(sum_plateau / sum_own, 4)
  ```
- **Rationale**: For $W=8$, $\text{sum\_own} < 1.0 \iff \bar{S}(\theta^*) < 0.125$ per fold. Applying the floor to the cross-fold sum preserves the exact physical calibration of Section 11, measuring whether the strategy possessed aggregate in-sample substance across market regimes before scoring its neighborhood.

### 2. Ruling 2: Re-Slice to 6-Month Holdout (`2026-03-01` to `2026-08-31`)
- **Ruling**: **Re-slice approved and mandated for Campaign 3.**
- **Specification for `campaign.meta.json` & `config.py`**:
  - **Research Span**: `2023-01-01 00:00:00` to `2026-02-28 23:59:59` (38 months, 27,720 1h bars, ~93% of dataset).
  - **Holdout Span**: `2026-03-01 00:00:00` to `2026-08-31 23:59:59` (6 full calendar months, 4,416 1h bars).
  - **Folds**: Re-pin the 8 rolling walk-forward folds across the 38-month research span (new `fold_fingerprint`).
- **Rationale**:
  - Lowering the promotion floor to 3 months / ~20 trades is mathematically unviable ($\text{power} < 0.30$).
  - 38 months provides abundant training depth for 8 rolling folds (~4.75 months / ~3,400 bars per fold).
  - A 6-month holdout spans distinct macro regimes (spring expansion, late spring correction, summer consolidation) and delivers expected sample $N \approx 40-50$ trades per asset, conferring genuine statistical power to promote or reject.

### 3. Ruling 3: WFE Denominator is Raw In-Sample Mean Profit Factor $\mu_{\text{IS\_PF}}(\theta^*)$
- **Ruling**: **Divide by unpenalized raw in-sample mean Profit Factor $\mu_{\text{IS\_PF}}(\theta^*)$.**
- **Specification for `score.py`**:
  $$\text{WFE} = \frac{\text{Pooled\_OOS\_PF}(\theta^*)}{\mu_{\text{IS\_PF}}(\theta^*)} \ge 0.50$$
  where $\mu_{\text{IS\_PF}}(\theta^*) = \frac{1}{W} \sum_{w=1}^W \text{PF}_w(\theta^*)$.
- **Rationale**:
  1. *Dimensional Consistency*: Pure $PF / PF$ ratio.
  2. *Anti-Gaming Integrity*: Penalizing the in-sample denominator by trade count would *deflate* $\mu_{\text{IS}}$, which would perversely *inflate* WFE for sparse, over-filtered candidates. Demanding that out-of-sample PF retains $\ge 50\%$ of raw in-sample PF enforces true out-of-sample efficiency.

---

### 4. Locked Campaign 3 Engine Matrix (Ready for Implementation)
All 8 engine parameters are locked for Claude Code's single-pass implementation:
1. **Gate Zero**: Full-span $\text{Gross Edge}_{\text{IS}} \ge 15.0\text{ bps}$ over research span.
2. **Option (a) Selection**: Maximize regularized consensus $\text{Fitness}_{\text{IS}}(\theta) = \mu_{\text{IS}}(\theta) - 0.5 \cdot \sigma_{\text{IS}}(\theta)$ using penalized fold scores $S_w(\theta) = \text{Metric}_w(\theta) \times \min(1.0, \sqrt{N_w(\theta)/10})$. Select single robust $\theta^* = \arg\max_\theta \text{Plateau}(\text{Fitness}_{\text{IS}}(\theta))$.
3. **Plateau Gate**: Ratio of cross-fold sums on neighborhood vs own scores with `MIN_OWN_SUM = 1.0` floor ($\ge 0.60$, failing closed to 0.0 if $\sum S_w < 1.0$).
4. **WFE Gate**: $\text{Pooled\_OOS\_PF}(\theta^*) / \mu_{\text{IS\_PF}}(\theta^*) \ge 0.50$ (raw PF denominator).
5. **Fold Consistency Gate**: $\ge 6/8$ test folds producing positive net PnL under $\theta^*$ ($\alpha = 0.145$).
6. **AST Price Detector**: Price-scaled series comparison ban vs numeric constants $> 100.0$; normalized dimensionless bounds permitted.
7. **Deflated Hurdle Floor**: $\Delta_{\text{min}}(n) = \max(0.05, \; 0.05 \cdot \sqrt{\ln(1+n)})$.
8. **Holdout & Promotion**: 6-month holdout (`2026-03-01` .. `2026-08-31`); promotion floor $\ge 6$ months continuous AND $\ge 50$ trades per asset (or verdict `INCONCLUSIVE_INSUFFICIENT_SAMPLE`).

### 5. Authorization
Claude Code is cleared to proceed with the single-pass implementation of the Campaign 3 harness, tests, and registration.
