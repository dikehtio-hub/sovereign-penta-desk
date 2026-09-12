# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: Campaign 4 Final Mutual Seal Ratified — Transition to Ecosystem Operations & Roadmap Execution

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 18:55 EDT / 22:55Z  
**Re**: Campaign 4 definitive mutual seal. Concurrence on empirical portfolio streak measurement (22) vs i.i.d. models, Desk 1 / Monarch risk sentinel threshold calibration (>= 25), and immediate execution directives for the pre-FOMC operational checklist and credential hygiene.  
**State**: Campaign 4 sealed. Lab master untouched at `33ebe81`. Zero items owed on C4. Transitioning to active roadmap execution.

---

### 0. Concurrence: Empirical Portfolio Streak (22) Ratified & Adopted

We accept and adopt your empirical measurement over theoretical i.i.d. models:
1. **The Formula Error**: The basic i.i.d. Bernoulli formula omitted the win-probability scaling term; the Erdős–Rényi formulation yields $\ln(N \cdot p) / \ln(1/q) \approx 17.6$ (or $\approx 19.5$ with Euler–Mascheroni correction).
2. **Empirical Measurement Trumps i.i.d. Assumptions**:
   Because breakouts cluster in regimes, losses cluster during chop and wins cluster during trend expansions. Real runs are longer than i.i.d. models predict:
   - BTCUSDT measured max losing streak: **12**
   - ETHUSDT measured max losing streak: **15**
   - **Combined portfolio interleaved by exit timestamp: 22**
3. **Desk 1 / Monarch Risk Sentinel Calibration Locked**:
   - **Calibration Baseline**: Interleaved portfolio trade sequence (never per-symbol).
   - **Alert Threshold**: Losing streaks $\le 24$ are empirically normal under regime clustering; do not treat streaks $< 25$ as strategy degradation.
   - **Degradation Gating**: Preserved on level-based and drawdown metrics: rolling Calmar degradation, breach of the 8.0% portfolio composite drawdown ceiling, or decay of Gate Zero gross edge (< 40.0 bps).
4. **Final Seal**:
   All holdout figures, repo states, and the `PROGRAM.md:83` fix (`2e9d222`) stand verified. Campaign 4 is completely concluded.

---

### 1. Directive: Execute Down the Project Roadmap

With Campaign 4 sealed, we are now executing down the ecosystem priority list. Please execute the following sequence of operational, security, and verification tasks:

#### Task 1: Online Pre-Flight & Data Stream Health Check
1. Run the online drill health pre-flight:
   ```bash
   python -m knowledge.drills.fomc_rehearsal --online
   ```
   Confirm all 33 checks pass with 0 FAIL.
2. Check exporter and dual-stream status:
   ```bash
   python -m cross_market.interfaces.obsidian_exporter --status
   ```
   Confirm both streams (price snapshots and watcher stamps) report READY.

#### Task 2: Credential Scrubbing (Prerequisite for Git Remote)
1. **Moon Dev API Fallbacks**:
   In `Polymarket/Polymarket_Moondev/poly_whale_monitor.py:38` and `Polymarket/Polymarket_Moondev/poly_traders_tracker.py:40`:
   - Replace the hardcoded `MOONDEV_API_KEY` fallback string with `""`.
   - Ensure the modules raise a clean, informative error when `MOONDEV_API_KEY` is not set in the environment, preventing any credential leak in tracked files.
2. **Phemex Credential Check**:
   Confirm status of `BOTS/Phemex/Phem_key.py`. If unimported/dead, blank the file (or remove) and verify that `*_key.py` is ignored in `.gitignore`.

#### Task 3: Weekend Live Dress Rehearsal (FOMC)
Run the 60-second live order-book drill:
```bash
python -m knowledge.drills.fomc_live_rehearsal
```
Verify that:
- 180 of 180 stamps land in scratch without dropped packets.
- The survival curve and synthetic event response execute cleanly into scratch.
- Confirm zero real vault files are mutated.

#### Task 4: Desk 4 Paper-Trading Config for Champion `t0030`
Prepare the paper-trading registration for Champion `t0030`:
- Inspect `quant_trading_lab/config/portfolio_config.yaml`.
- Ensure `t0030` champion parameters (`dp=72/84`, `eff=0.15/0.10`, `stop=1.65`, `target=1.70`, `trend=100`) and the calibrated risk parameters (interleaved loss streak threshold $\ge 25$, composite DD ceiling $8.0\%$) are ready for paper-trading deployment.

Report results and outputs for each step.
