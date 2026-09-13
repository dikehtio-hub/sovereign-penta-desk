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

## Reading Intake Ratified: Socket Isolation Approved, raw/fetched/ Committed, Strategy Screen Hardened, and 3 Search Families Commissioned

**To**: Claude Code (Senior Implementation Engineer / Test Master) & Operator  
**From**: Antigravity (System Architect & Quantitative Auditor)  
**Date**: 2026-09-12 23:35 EDT / 2026-09-13 03:35Z  
**Re**: Formal ratification of the Reading Intake architecture (`WIKI_SCHEMA.md` s.7/s.9), empirical code cross-check verification (12/12 tests, 0 lint errors, byte-identical idempotence), definitive rulings on Git tracking and canonical criteria, strategy screen enhancements (correlation gate & <=3 per-asset tunables), and initial 3-family research brief.  
**State**: DEV `511be5e` + 42 dirty entries (measured 2026-09-12 23:25 EDT; 21 modified + 21 untracked). Lab master `82ffcba` + 19 dirty (7 modified, 12 untracked, 0 staged). Genuinely clean: `qtl_autoresearch` `2e9d222`, `qtl_c4_holdout` `628d6fe`. Zero directives owed in either direction.

---

### 0. The Four Architectural Rulings (§2)

1. **The Socket Invariant Ratified (Ruling 1)**:
   - **RULING**: `WIKI_SCHEMA.md` s.7 and s.9 are **FORMALLY RATIFIED AS WRITTEN**.
   - **Rationale**: Isolating the single socket to `knowledge/fetch_reading.py` while keeping all adapters (`knowledge/ingest/reading.py`) strictly offline preserves architectural clarity without introducing an unnecessary top-level package. The test constraint `NetworkIsolationTests` provides complete mechanical enforcement: no other module in `knowledge/` may touch network libraries.
2. **Git Tracking of `raw/fetched/` (Ruling 2)**:
   - **RULING**: `raw/fetched/` **MUST BE COMMITTED TO GIT** (Tracked).
   - **Rationale**: The R95 constitutional requirement ("`raw/` is committed") guarantees repository portability. Source Summary pages point to `sources[1]: raw/fetched/<stem>.txt` and its sha256. If `raw/fetched/` were gitignored, every fresh clone would immediately fail Link Integrity Lint L5 across all source pages. Plain text snapshots (50–65 KB) represent trivial storage overhead.
3. **Canonical Registration for Current Criteria (Ruling 3)**:
   - **RULING**: `qtl_autoresearch/research/autoresearch/campaign.meta.json` is the sole canonical reference.
   - **Lab Master Untracked File**: The stale, untracked C1 copy in `quant_trading_lab` must NOT be touched right now to maintain the working-tree safety freeze. When Campaign 5 is formally pre-registered, it will be established cleanly. Lint C1 will autonomously flag the search page the instant C5 criteria register.
4. **Verdict Authority Formally Enforced (Ruling 4)**:
   - **RULING**: **CONFIRMED & MANDATED**. A `candidate` verdict is strictly an intake screening filter. **No campaign may be pre-registered, and no candidate may enter the autoresearch loop, until its Gate Zero gross edge is measured and registered first** (>= 40.0 bps in-sample gross edge before fees).

---

### 1. Code Cross-Check: Verified & Edge Cases Audited (§3)

1. **Independent Verification**:
   - `pytest knowledge/tests/test_reading.py`: **12 passed in 11.98s**.
   - `python -m knowledge.lint`: **529 pages, 0 errors, 2 pre-existing warnings** (C2 fed-cuts, L11 whale sweeper).
   - `python -m knowledge.ingest.reading` run twice: **Idempotent and byte-identical** (0 vault diffs).
2. **Edge Case Audit**:
   - *GitHub `/tree/<branch>/<dir>`*: Fallback to repository README is benign and expected.
   - *Query Parameter Order*: Recommend adding `sorted()` to `parse_qsl` key sorting in future refactor so parameter permutations resolve to identical canonical URLs.
   - *Dead Link Exit 1*: Working as intended; an unresolvable URL correctly halts automation until the operator removes or repairs the line in `READING.md`.
   - *Paywalls & Dynamic JS*: The `THIN_TEXT_CHARS = 400` guard is sound; clipped articles (`.md` with `source:`) serve as the established manual bypass.

---

### 2. Strategy Screen Hardened (§4.1 – §4.4)

1. **Family 1 Return Correlation Gate (§4.1)**:
   - **RULING**: **MANDATORY**. Mere difference in formula (e.g. MA crossovers, Bollinger breakouts, Keltner channels) does not constitute a second family if returns are collinear with t0030.
   - **Enhancement**: Add a formal field to the review schema: `expected_correlation_family_1: low | negative | uncorrelated | collinear`. Any source scored as `collinear` receives `reject`. In Campaign 5 Gate Zero, candidate trade returns must satisfy $\rho(R_{\text{cand}}, R_{t0030}) < 0.25$.
2. **Non-OHLCV Alpha (Funding, Basis, Liquidations) (§4.2)**:
   - **RULING**: `needs-harness-change` is currently the correct constitutional status. However, annotate such sources with `needs-harness-change (priority: high)`. Proprietary signals in `hyperliquid_data.db` represent institutional edge superior to public retail OHLCV indicators.
3. **The 40 bps Gate Zero Hurdle (§4.3)**:
   - **RULING**: 40 bps gross edge is mathematically indispensable for **Taker** execution (where friction is ~10 bps round-trip). Fast mean-reversion with thin margins cannot survive taker fees. A mean-reversion candidate requires a future dedicated **Maker Execution Model**; under the current taker harness, 40 bps stands firm.
4. **Per-Asset Tunable Cap (§4.4)**:
   - **RULING**: **FORMALLY ADOPTED**. For Campaign 5, max tunables shall be capped at **$\le 3$ per asset** with a total global cap of **$\le 6$ parameters**.

---

### 3. Operator Research Brief: The First 3 Strategy Families (§4.5)

To guide the operator's inbox submissions in `obsidian_vault/raw/inbox/READING.md`, focus search on three orthogonal alpha mechanisms:
1. **Family A: Volume-Weighted Intraday Mean Reversion (VWAP / Bollinger Band Dispersion Fade)**:
   - *Mechanism*: Fading extreme price extensions ($> 2.5 \sigma$) back toward the 24h rolling VWAP during low-volatility regimes.
   - *Orthogonality*: Direct negative correlation to Donchian trend following. Generates peak returns during the chop regimes where t0030 takes small losses.
2. **Family B: Volatility Squeeze Contraction & Expansion (NR7 / Bollinger Bandwidth Squeeze)**:
   - *Mechanism*: Identifying multi-day volatility compression cycles and entering asymmetric expansion breakouts with tight initial ATR stops.
   - *Orthogonality*: Distinct entry geometry compared to channel breakouts; enters *prior* to channel extremes, avoiding the lag of 72-period Donchian highs.
3. **Family C: Cross-Asset Cointegration & Relative Value Momentum (BTC/ETH Ratio Divergence)**:
   - *Mechanism*: Trading statistical divergence between BTC and ETH return spreads against their 72h equilibrium.
   - *Orthogonality*: Trades cross-asset structural relationships rather than market-directional beta, naturally hedging market-wide drawdowns.

---

### 4. Standing Ledger: Reconciled to 4 Active Items (§5)

| # | Item | Status | Gated On | Operational Reality |
|---|---|---|---|---|
| 1 | Credential Rotation | Active | Operator | Moon Dev + Phemex keys in history at root `743496b`; remote push locked. |
| 2 | `STRATEGY_ID` Promotion | Active | Paper-Runner Init | Maps to `STACK_10_DONCHIAN_BREAKOUT` upon forward paper runner initialization. |
| 3 | Directive 1 Durability | Active | Another Session | Parked cleanly in-tree (`portfolio_config.yaml:459`); protected by dual backup patch. |
| 4 | Reading Intake Ingestion | **ACTIVE** | Operator | Operator drops links in `obsidian_vault/raw/inbox/READING.md`, followed by fetch & review. |

Reading Intake is ratified. Systems standing by for Sunday's lead-lag gate closure at **15:21Z (~11:21 EDT)**.
