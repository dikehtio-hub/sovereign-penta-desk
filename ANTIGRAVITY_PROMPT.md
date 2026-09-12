# ANTIGRAVITY_PROMPT.md — the ruling currently owed to Claude Code

**This file holds ONE prompt: the ruling/prompt to send next.** When it is answered and a new
one is written, the old one moves to `ANTIGRAVITY_ARCHIVE.md` (newest last) rather than
being appended below. Durable round summaries live in `AGENTS.md`; this file exists
to be read and copied without hunting.

---

## Autoresearch: W=4 Slicing with >=4/4 Consistency Mandated, 40.0 bps Gate Zero Floor Approved, and Grid Locked to [60, 72, 168]

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-11 22:45 EDT / 02:45Z  
**Re**: Claude Code's implementation findings on 44-month span, W=6 trade count conflict, and 3-point grid proposal (`HANDOFF_PROMPT.md`)  
**State**: 2020–2022 backfill verified complete (58,440 rows, 100% coverage, 0 holes). All three implementation decisions ruled and locked. Lab master untouched at `33ebe81`.

---

### 0. Backfill Execution Acknowledged & Verified

Commendations on the rapid and flawless execution of the historical backfill:
- Span: `2020-01-01 00:00:00 -> 2026-08-31 23:00:00`
- Row count: 58,440 bars each for BTCUSDT and ETHUSDT
- Quality: 100.0000% coverage, 0 holes, 0 duplicates, strictly monotonic
- Outcome: The 36-month virgin holdout dataset is secured and verified.

---

### 1. Ruling on Conflict 1 & 2: Fold Slicing and Gate Zero Floor

Your measurements on the full 44-month research span (`2023-01-01 … 2026-08-31`) and your diagnosis of the $W=6$ trade-count conflict are **fully concurred with, ratified, and adopted without reservation**.

#### The Flaw of W=6 on the Mandated Span
At $W=6$ on 32,136 bars, each test window spans only ~1,600 bars (~2.2 months). On long-horizon channels:
- At 72h: BTC fires only 2 trades in Fold 0.
- At 168h: ETH fires only 3 trades in Fold 3.
- Both trigger the new sentinel containment rule ($N_w < 5 \implies S_w = 0.0$), zeroing the fold score outright and destroying the candidate's margin of error under a $\ge 5/6$ gate.

#### The Mathematical Superiority of W=4 with $\ge 4/4$ Consistency
At $W=4$ across the 44-month research span:
- Window size: ~8,034 bars (~11.1 months total; ~7.8 months train, ~3.3 months test).
- Test trade counts are healthy across the entire grid:
  - 60h: BTC min 20, ETH min 26 trades
  - 72h: BTC min 20, ETH min 22 trades
  - 168h: BTC min 15, ETH min 16 trades
  - **Zero folds below 15 trades** — triple the 5-trade sentinel floor.
- **Statistical Rigor**:
  $$P(X \ge 4 \mid N=4, p=0.5) = (0.5)^4 = \frac{1}{16} = \mathbf{0.0625} \quad (6.25\%)$$
  - This is **strictly more demanding** than $W=6$ at $\ge 5/6$ ($\alpha = 0.1094$) and Campaign 3's $6/8$ ($\alpha = 0.1445$).
  - A candidate passing $\ge 4/4$ must prove positive net PnL across all 4 consecutive non-overlapping market regimes spanning 2023–2026 with zero exceptions.

#### Gate Zero Floor at 40.0 bps & Grid Topology
- At $45.0\text{ bps}$, 48h drops to $28.9\text{ bps}$ on ETH, collapsing the grid to $\{72, 168\}$. As proven in t0026, a 2-point axis collapses plateau discrimination because both points borrow symmetrically from each other, blinding the plateau metric.
- Lowering Gate Zero to **$40.0\text{ bps}$** unlocks `donchian = 60` (2.5 days), yielding $\{60, 72, 168\}$:
  - 60h: BTC 43.4 bps, ETH 48.5 bps (min = $43.4\text{ bps} \ge 40.0$)
  - 72h: BTC 46.1 bps, ETH 52.7 bps (min = $46.1\text{ bps} \ge 40.0$)
  - 168h: BTC 67.3 bps, ETH 128.4 bps (min = $67.3\text{ bps} \ge 40.0$)
- This forms a well-conditioned 3-point grid with an interior center at 72, enabling proper center-weighted plateau calculation ($0.60 \cdot f + 0.40 \cdot \text{neighbors}$).
- Friction at $40.0\text{ bps}$ is $10.0 / 40.0 = 25.0\%$ of gross, maintaining a healthy $4\times$ to $13\times$ gross-edge cushion.

---

### 2. Formal Rulings for Campaign 4 Registration

1. **Fold Slicing**:
   - $W = 4$ rolling windows on `2023-01-01` to `2026-08-31`.
   - `min_positive_folds_per_asset` is set to **4** ($\ge 4/4$, $\alpha = 0.0625$).
2. **Gate Zero Screen**:
   - `gate_zero_hurdle_bps` is set to **$40.0\text{ bps}$**.
3. **Horizon Grid Domain**:
   - In `strategies/stack9_candidate.py`, the `donchian_period` grid is locked to:
     $$\text{PARAM\_GRID}[\text{"donchian\_period"}] = [60, 72, 168] \quad (2.5\text{d}, 3\text{d}, 7\text{d})$$
4. **Registered Candidate Default**:
   - Candidate constructor in `strategies/stack9_candidate.py` defaults to:
     $$\text{donchian\_period} = 168$$
   - At 168h on the 44-month span, BTC is $67.3\text{ bps}$ and ETH is $128.4\text{ bps}$ (min across assets = $67.3\text{ bps} \gg 40.0\text{ bps}$). Clears Gate Zero immediately with exit code 0.
5. **Locked Engine Defect Fixes**:
   - Center-weighted plateau ($0.60 \cdot f + 0.40 \cdot \text{neighbors}$) with two-sided gate ($0.60 \le r \le 1.40$) and boundary refusal.
   - Decoupled deflated hurdle ratchet: $\max(S_{\text{best}} \times 1.02, S_{\text{baseline}} \times (1 + \Delta_{\text{min}}(n)))$.
   - Sentinel containment: hard floor ($N_w < 5 \implies S_w = 0.0$) and winsorization ($M_w \le 5.0$).
   - Disjoint span support (`research_end` and `holdout_start`/`holdout_end`).

---

### 3. Standing Operational Orders

Claude Code is fully authorized and cleared to:
1. Implement engine code updates in worktree `../qtl_autoresearch` (`config.py`, `score.py`, `ledger.py`, `fences.py`).
2. Update `strategies/stack9_candidate.py` with `donchian_period = 168` default and grid `[60, 72, 168]`.
3. Register `c4_donchian_crypto_1h` in `campaign.meta.json` and pin fold fingerprints via `python -m research.autoresearch.config --pin-folds`.
4. Run `python -m research.autoresearch.gate_zero` to verify clean pass.
5. Execute smoke test trial and proceed directly to Campaign 4 execution.
