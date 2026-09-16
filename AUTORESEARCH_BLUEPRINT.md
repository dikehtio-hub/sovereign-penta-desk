---
type: Blueprint
title: Strategy Autoresearch x DEV - Fenced Hill-Climb Blueprint
description: Implementation plan for a Karpathy-style autoresearch loop over quant_trading_lab strategies, reshaped for trading - one editable file, a walk-forward out-of-sample score with hard gates, a locked holdout the loop cannot reach, a nightly trial cap, an append-only ledger compiled into the wiki, and TradingView kept at the end of the pipeline (parity and alerts), never inside the loop.
tags: [autoresearch, karpathy, quant-trading-lab, walk-forward, overfitting, research, plan]
generated:
  by: claude-code/fable-5.1
  at: 2026-09-11T05:15:00Z
status: draft
dev:
  baseline_commit: f0648bf
  lab_baseline_commit: 33ebe81
  desks: [4]
  parameters:
    - {name: trial_cap_per_night, value: 40}
    - {name: max_tunables, value: 6}
    - {name: min_relative_improvement, value: 0.05}
    - {name: holdout_start_utc, value: "2026-06-01T00:00:00Z"}
    - {name: research_start_utc, value: "2023-01-01T00:00:00Z"}
    - {name: walk_forward_folds, value: 8}
sources:
  - id: karpathy-autoresearch
    resource: https://github.com/karpathy/autoresearch
    title: autoresearch (README + program.md)
    author: human:karpathy
  - id: nunchi-autoresearch-trading
    resource: https://github.com/Nunchi-trade/auto-researchtrading
    title: auto-researchtrading (the no-holdout counter-example, Sharpe 2.7 -> 20.6 on 500 hourly bars)
    author: Nunchi-trade
  - id: lab-walk-forward
    resource: quant_trading_lab/research/walk_forward.py
    title: WalkForwardOptimizer (rolling folds, calmar in-sample objective, plateau score, WFE)
    author: quant_trading_lab
  - id: lab-engine
    resource: quant_trading_lab/backtesters/engine.py
    title: run_backtest / size_trade / load_bars_from_csv (RiskSentinel-sized, confirmed-bar window, no lookahead)
    author: quant_trading_lab
  - id: wiki-ingest-experiments
    resource: knowledge/ingest/experiments.py
    title: compile_registration dispatch on protocol; the pattern the autoresearch adapter follows
    author: knowledge
---

# Strategy Autoresearch x DEV: Fenced Hill-Climb Blueprint

Plan only. No code, data, daemon, task or vault page was touched. Baseline
DEV f0648bf, lab 33ebe81 (the lab tree carries 13 uncommitted paths from
the other agent; nothing here may stage them).

## 0. Thesis in one paragraph

Karpathy's loop is a greedy hill-climb with git as the undo stack: one
editable file, one held-out number, a fixed budget per trial, keep if better
else reset, never ask. It is safe for language models because the validation
loss is measured on fresh text every run. A backtest on a fixed window is
not fresh; keep-if-better over it is a data-snooping machine, and the public
trading forks prove it (Sharpe 2.7 to 20.6 after 103 trials on 500 hourly
bars, no holdout, no penalty). DEV already owns the honest half of the
machinery: a cost-aware engine, a walk-forward optimizer with a plateau
score, a grid engine, a lint-guarded experiment ledger and a ratification
step. What is missing is deep data, a loop harness whose fences are enforced
by code rather than by prompt, and one wiki adapter. This plan builds exactly
that and nothing wider.

## 1. What already exists and is reused unchanged

| Need | Existing piece | Reuse |
|---|---|---|
| Cost-aware backtest | `backtesters/engine.py` `run_backtest(bars, strategy, break_even_at_r)` sized by `size_trade` through RiskSentinel | called as-is per fold |
| Per-run metrics | `research/grid_search.py` `calculate_metrics(trades) -> BacktestMetrics` (PF, calmar, sharpe, max DD, avg trade, counts) | called on pooled OOS trades |
| Folds + plateau + WFE | `research/walk_forward.py` `WalkForwardOptimizer(train_fraction, num_windows, metric_objective, min_trades)`; `build_rolling_windows`; `_plateau_score`; `run_optimization` returns per-fold IS/OOS and WFE | fold boundaries pinned once per campaign |
| Strategy contract | `strategies/base_strategy.py` `BaseStrategy.evaluate(bars)` sees confirmed bars only, most recent last | the candidate subclasses it |
| Tunables convention | constructor kwargs with module-constant defaults (Stack 5 pattern) | the candidate follows it; kwargs are what the fence counts |
| Data loader | `load_bars_from_csv(path, source_tz)` accepts the 6-column `timestamp,open,high,low,close,volume` file | new data lands in that shape |
| Ledger + lint + ratify | `knowledge/ingest/experiments.py` dispatch on `protocol`; lint C1 checks copied numbers against owning files; `knowledge/ratify.py` | one new adapter, same dispatch |
| Loop driver | Claude Code `/loop` (self-paced) | prompt = one iteration of PROGRAM.md |
| Pine deployment | `pine_scripts/strategies/_stack_template.pine`, webhook contract `pine_scripts/webhook_payload_schema.md` | the outer parity step only |

## 2. Design decisions (ratify before Phase 1)

### 2.1 One editable file

`quant_trading_lab/strategies/stack9_candidate.py`. The loop may change
nothing else. Enforced by the runner (s.4.2), not by the prompt.

### 2.2 Three data tiers, pinned in the campaign registration

| Tier | Span (UTC) | Who scores it |
|---|---|---|
| Research (train + OOS folds) | 2023-01-01 to 2026-05-31 | the loop, every trial |
| Holdout | 2026-06-01 to 2026-08-31 | `holdout.py`, run by the operator on `master`, once per candidate |
| Forward | paper tier from acceptance onward | the existing paper flow |

The runner truncates every bar series at `holdout_start_utc` before the
optimizer sees it. `holdout.py` refuses to run on any branch whose name
starts with `autoresearch/`. Those two rules make the holdout unreachable by
construction.

### 2.3 The score and its gates

Primary score `S` = the smaller of the two assets' pooled out-of-sample
profit factor, costs included:

```
for asset in (BTCUSDT, ETHUSDT):
    folds = optimizer.build_rolling_windows(bars_research[asset])   # identical for every trial
    oos_trades[asset] = concat(run_backtest(fold.test_bars, candidate_fitted_on(fold.train_bars)) for fold in folds)
    S[asset] = calculate_metrics(oos_trades[asset]).profit_factor
S = min(S[BTCUSDT], S[ETHUSDT])
```

Hard gates, all must pass or the trial is `discard` regardless of `S`:

| Gate | Bar | Why |
|---|---|---|
| pooled OOS trades per asset | >= 100 | PF on 20 trades is noise |
| folds with positive OOS PnL | >= 5 of 8 | consistency across regimes |
| walk-forward efficiency (avg OOS PF / avg IS PF) | >= 0.5 | the optimizer's own overfit detector |
| pooled OOS max drawdown | <= 8 % of the active tier's equity | Calmar discipline, matches the lab's objective |
| plateau ratio (`_plateau_score` / own score) | >= 0.6 | a spike at one exact setting is not an edge |
| tunable kwargs on the candidate | <= 6 | degrees of freedom cap |
| forbidden constructs (s.4.2) | none | no peeking, no date or level literals |

Keep rule: `S_new >= 1.05 * S_best` and every gate green. Otherwise
discard. The 5 % minimum delta is the noise floor; ratify or change it.

### 2.4 Budget is a trial count, not a clock

Backtests take seconds, so wall clock bounds nothing. The cap is 40 trials
per night and 10 minutes per trial (the runner kills a longer one and logs
`crash`). A campaign is 5 nights, then a mandatory holdout run and review.
The cap is what makes the morning deflation honest: the ledger says how many
draws the best-of came from.

### 2.5 Hypothesis is mandatory

Every trial carries a one-line market mechanism in the ledger. The runner
refuses a trial with an empty hypothesis. This is the rule that stops the
loop from stacking filters until the backtest looks perfect.

### 2.6 Git in a tree another agent is editing

The lab is its own repository and carries the other agent's uncommitted
work. The loop therefore never runs `git reset` or `git add -A`. Keep =
`git commit -- strategies/stack9_candidate.py research/autoresearch/ledger.tsv research/autoresearch/trials/<id>.json`.
Discard = `git checkout -- strategies/stack9_candidate.py`. Both file-scoped.

### 2.7 TradingView stays outside the loop

The Strategy Tester is in-sample by construction and a minute per run.
It is used once per surviving candidate for parity (s.6) and then for
alerts. No TradingView MCP is required for any phase below; the desktop
bridge is an optional convenience for s.6 and carries a paid-plan and a
terms-of-use decision that is the operator's alone.

## 3. File tree (new files only)

```
quant_trading_lab/
  scripts/fetch_binance_archive.py           Phase 0  monthly kline zips -> data/continuous/<SYM>_<tf>_binance.csv
  strategies/stack9_candidate.py             Phase 1  the only editable file; starts as a plain baseline
  research/autoresearch/
    __init__.py
    PROGRAM.md                               Phase 1  the loop's instructions (s.5)
    campaign.meta.json                       Phase 1  pre-registration of the campaign (folds, gates, holdout, cap)
    config.py                                Phase 1  loads campaign.meta.json; the only place numbers live
    fences.py                                Phase 1  branch / diff / import / literal / kwarg checks
    score.py                                 Phase 1  folds -> pooled OOS -> S + gates (pure, testable)
    ledger.py                                Phase 1  append-only TSV + per-trial JSON with sha256
    run_trial.py                             Phase 1  CLI: one trial end to end, exit 0 keep / 1 discard / 2 crash / 3 refused / 4 cap
    holdout.py                               Phase 1  CLI: scores holdout for one commit; refuses on autoresearch/* branches
    ledger.tsv                               Phase 3  tracked, append-only
    trials/<trial_id>.json                   Phase 3  the artefact the wiki compiles from
  tests/test_autoresearch.py                 Phase 1
knowledge/ingest/autoresearch.py             Phase 4  campaign registration + panel + keep pages
knowledge/tests/test_autoresearch_ingest.py  Phase 4
obsidian_vault/wiki/experiments/
  autoresearch_<campaign>_meta.md            Phase 4  compiled registration (C1 guards the gates)
  autoresearch_<campaign>_panel.md           Phase 4  trial count, keeps, best S, gate table, holdout verdicts
  autoresearch_keep_<campaign>__<trial>.md   Phase 4  one page per keep
```

## 4. Phases

### Phase 0. Data (free; the binding constraint)

Goal: at least three years of BTCUSDT and ETHUSDT at 5m and 1h in the
existing CSV shape.

1. Geo check first. `data.binance.vision` is a public bucket; Binance.com's
   API is geo-blocked for US addresses and the bucket may or may not be from
   this machine. Fetch one small file (`ETHUSDT-1h-2024-01.zip`) before
   writing anything. If blocked: Bybit's public archive is the fallback;
   Hyperliquid's own history is capped at ~5,000 candles per interval and is
   not an option.
2. `scripts/fetch_binance_archive.py --symbol BTCUSDT --interval 5m --start 2023-01 --end 2026-08 --market um`
   downloads `data/futures/um/monthly/klines/<SYM>/<tf>/<SYM>-<tf>-YYYY-MM.zip`,
   concatenates, writes `data/continuous/<SYM>_<tf>_binance.csv` with the
   six canonical columns, naive UTC timestamps (same as the Hyperliquid
   files, so `--source-tz UTC` applies). Idempotent: skips months already
   on disk, verifies the published checksum when present.
3. Known gotcha to code for: kline `open_time` switched from milliseconds
   to microseconds in files dated 2025-01 onward. Detect the unit by
   magnitude, never by date.
4. Acceptance: row counts within 1 % of the theoretical bar count for the
   span; no duplicate timestamps; monotonic; a gap report printed (holes
   over 2 bars listed, none silently filled).

Estimate: 20 min build and test; download is network-bound (roughly 400
MB across four series).

**Executed 2026-09-11 05:28-05:36Z (7 min build, test and download; 9 min
with docs).** Geo-check passed. `scripts/fetch_binance_archive.py` plus 22
offline tests; lab suite 202 passed. Four series written, all PASS: BTCUSDT
and ETHUSDT at 5m (385,632 rows each) and 1h (32,136 rows each), 2023-01-01
to 2026-08-31 23:55 UTC, 100.0000 % coverage, 0 holes, 0 duplicates. The
zip cache is 38 MB, not the 400 MB guessed above. Finding: the futures
archive still carries millisecond timestamps in 2026-08; the microsecond
switch was spot-only. The parser detects by magnitude either way.

### Phase 1. Harness (the contract)

1. `campaign.meta.json` (protocol `autoresearch`): assets, timeframe,
   research span, holdout start, fold config, every gate bar, trial cap,
   per-trial timeout, editable file, forbidden constructs, min delta,
   campaign tag. Same shape and discipline as
   `cross_market/experiments/lead_lag_phase2_fomc.meta.json`.
2. `config.py` reads it once; nothing else in the package holds a number.
3. `fences.py`, each a pure function returning a refusal reason or None:
   - branch name matches `autoresearch/<campaign_tag>`;
   - `git diff --name-only HEAD` plus untracked, restricted to the lab
     tree, is a subset of `{strategies/stack9_candidate.py}`;
   - the candidate imports nothing from `backtesters`, `research`,
     `pandas`, `csv`, `open`, `requests`, `sqlite3` (no data access from
     inside the strategy; the window it is handed is all it may see);
   - no `datetime(` literal with a year, no numeric literal above 10,000
     outside the constructor defaults (cheap detector for hard-coded dates
     and price levels; a hit is a refusal, and the morning review reads
     the diff);
   - constructor kwargs count <= `max_tunables`;
   - hypothesis non-empty.
4. `score.py`: folds built once from the pinned config, bars truncated at
   `holdout_start_utc`, per-fold fit on train via `GridSearchEngine` over
   the candidate's declared grid (the candidate exposes `PARAM_GRID`), OOS
   run on test, pooled metrics per asset, `S`, gate results, plateau ratio,
   WFE. Deterministic: same commit and data produce byte-identical JSON.
5. `ledger.py`: TSV columns
   `trial_id  utc  commit  status  S  S_btc  S_eth  oos_trades_btc  oos_trades_eth  folds_pos  wfe  oos_maxdd_pct  plateau  n_tunables  gates_failed  hypothesis  json_sha256`.
   Append only; the JSON carries the full per-fold table and the
   `_artifact` envelope in the Round 122 shape so the wiki adapter needs
   nothing new.
6. `run_trial.py --hypothesis "..."`: fences -> score -> ledger -> verdict
   line on stdout (`KEEP S=1.43 (best 1.31)`, `DISCARD gate:wfe`,
   `REFUSED: extra file modified`, `CAMPAIGN_CAP_REACHED`). Exit codes
   0 / 1 / 2 / 3 / 4. It never touches git; PROGRAM.md does the
   file-scoped commit or checkout based on the exit code, so a crash in
   git handling can never corrupt the ledger.
7. `holdout.py --commit <sha>`: refuses on `autoresearch/*` branches;
   loads only holdout rows; runs the candidate at its kept parameters,
   no re-fitting; writes `trials/holdout_<sha>.json`; prints the same
   gate table against the holdout.
8. `strategies/stack9_candidate.py` v0: a deliberately plain baseline
   (for example a Donchian breakout with an ATR stop, four tunables) so
   the first keep has something honest to beat.
9. `tests/test_autoresearch.py` (run with the lab's own venv from
   `quant_trading_lab/`, per the desk test memory): every fence refuses
   for its reason and passes clean; truncation drops holdout rows; each
   gate fails on a planted metric; keep and discard arithmetic at the
   5 % boundary; ledger append and sha256; cap reached at trial 41;
   holdout refusal on the loop branch; a synthetic series with a planted
   edge (`generate_synthetic_bars` plus an injected pattern) yields a keep
   and the same series with the pattern removed yields a discard;
   determinism (two runs, identical JSON).
10. Register `STACK_9_CANDIDATE` in `config/portfolio_config.yaml` with
    `enabled: false` and a risk-parity weight equal to the Track 2 stacks,
    so `size_trade` sizes it like a real stack rather than a default.

Estimate: 30 min (baseline 20 plus 5 for a contract plus 5 for the planted
edge fixture). Suites afterwards: lab `pytest tests -q` from its venv
(baseline 180 as of 2026-09-07; re-verify before starting), knowledge suite
untouched in this phase.

**Executed 2026-09-11 16:53-17:28Z (35 min).** Everything in the list above
is built, tested and verified end to end on the real 41-month data. Lab
suite 243 passed (202 after Phase 0, plus 41 new). Deviations and findings:

1. **Fold stability (the open question from s.8.1) is ANSWERED: index-based
   and deterministic.** `build_rolling_windows` slices by integer index off
   the bar list, so for a fixed research span the folds are identical across
   trials. The registration does not need explicit timestamps; it carries a
   `fold_fingerprint` (sha256 over every fold's four boundary stamps)
   instead, pinned once by `--pin-folds` and re-derived on every trial. A
   mismatch means the data changed under the campaign and the trial is
   refused unscored, which is strictly stronger than pinned timestamps
   because it also catches a silently rewritten CSV. BTC and ETH pin to the
   SAME fingerprint, correctly: the two series share every timestamp.
2. **The dirty-tree fence exempts the harness's own output** (`ledger.tsv`,
   `trials/`). Without it the second trial of every night is refused for the
   first trial's artefacts, a refusal the loop cannot fix by editing the
   candidate. The invariant is unchanged: nothing that affects the SCORE may
   differ from HEAD, and the ledger is written after scoring. Integrity
   still holds via append-only writes, a refusal to overwrite an artefact,
   the per-row sha256 and the per-trial commit.
3. **`run_trial` scores in a SUBPROCESS** with the campaign's timeout, so a
   candidate that hangs or segfaults becomes a `crash` row rather than
   killing the loop.
4. **Trial cost on real data: 3m04s** (8 folds x 27 combinations x ~29k
   train bars x 2 assets, 4 workers). A 40-trial night is about 2 hours.
   The 600 s per-trial timeout has 3x headroom.
5. **Campaign 1 registered** as `c1_donchian_crypto_5m`: BTCUSDT + ETHUSDT
   5m, research 2023-01-01..2026-05-31, holdout 2026-06-01..2026-08-31,
   8 folds, the s.2.3 gates verbatim, 40 trials/night, 5 nights.
6. **Two bugs caught by the harness testing itself**, both now covered:
   a default-bound `sys.stdout` that bypassed output redirection, and a
   `git status --porcelain` parse that stripped the leading space of the
   first line and so removed the first character of one reported path per
   call (modified files only, never untracked ones, which is why the first
   round of tests missed it).

**End-to-end verification on real data** (in a throwaway worktree, since
the Phase 1 files are uncommitted; the worktree and its branch were removed
afterwards and the repo is byte-identical to before):

| Branch exercised | Result |
|---|---|
| Real trial, full gates | `DISCARD S=0.68`, 6 gates failed, 0/8 positive folds on both assets |
| Keep rule, first gated pass | `KEEP` (baseline) |
| Keep rule, no improvement | `DISCARD S 0.6800 < 0.7140 (best x 1.05)` |
| Fence: strategy imports the data loader | `REFUSED ... 'backtesters.engine' is not on the allowlist` |
| Fence: hard-coded price level | `REFUSED ... numeric literal 64250.0 exceeds 10000` |
| Fence: edit to the engine | `REFUSED ... backtesters/engine.py` |
| Fence: empty hypothesis | `REFUSED ... name the market mechanism` |
| Fence: stray file in the tree | `REFUSED ... relaxed.meta.json` |
| Holdout on the loop branch | `REFUSED: holdout never runs on a loop branch` |
| Holdout on master | `FAIL`: BTC PF 0.48 / -$26,391, ETH PF 0.68 / -$8,736 |

The v0 baseline losing on every fold AND on the holdout is the correct
starting point: the loop now has an honest floor to beat, and the gates
have demonstrated they reject a real losing strategy rather than waving it
through.

### Phase 2. Supervised dry run and ratification

1. Antigravity cross-check of Phase 1 (prompt in s.8) before any trial.
2. Ratify `campaign.meta.json` through `knowledge.ratify` so the gates are
   a ruling, not a default.
3. Five trials by hand with the operator watching: one honest idea, one
   deliberate peeking attempt (the fence must refuse), one seven-kwarg
   attempt (refuse), one crash (timeout), one keep. Read the ledger and
   the JSON together.

Estimate: 20 min.

**Executed 2026-09-11 17:35-17:50Z (15 min), on the operator's "Phase 2".**
Campaign worktree `../qtl_autoresearch` on branch
`autoresearch/c1_donchian_crypto_5m` is now PERSISTENT (the Phase 1
verification worktree was a throwaway; this one stays for Phase 3). The
harness is committed on that branch, NOT on master, so master keeps the
other agent's uncommitted work untouched and the operator's decision about
committing Phase 1 to master stays theirs.

**Two deviations from the plan, both flagged rather than worked around:**

1. **Step 1 (Antigravity cross-check before any trial) was NOT satisfied.**
   Antigravity has not replied on autoresearch at all as of 17:35Z. The dry
   run proceeded on the operator's instruction. The cross-check is still
   owed and Phase 3 should not start without it.
2. **Step 2 as written could not execute: an ordering error in this plan.**
   `knowledge.ratify` operates on VAULT PAGES and requires a ruling id, but
   the autoresearch wiki adapter is Phase 4, so no page exists to ratify.
   Operator acceptance of the gates is recorded in `campaign.meta.json`
   instead (`status: operator-accepted`, plus an explicit
   `antigravity_ratification: OUTSTANDING` field and a null `ruling_id` to
   fill in later). Phase 4 should ratify the compiled page properly.

**The five supervised trials, every one committed file-scoped per PROGRAM.md:**

| Trial | What was tried | Result |
|---|---|---|
| t0001 | Volatility-compression filter (breakouts out of a contracted range persist) | `DISCARD S=0.70`, 6 gates failed |
| t0002 | Peeking: import the data loader inside the strategy | `REFUSED` by the import fence |
| t0003 | Eight tunables | `REFUSED`, cap is 6 |
| t0004 | A real bug (`ZeroDivisionError` once the channel fills) | `CRASH` logged, loop survived |
| t0005 | FADE the breakout instead of following it | `DISCARD S=0.82`, 6 gates failed |

No keep. Three genuine hypotheses were tested and the harness rejected all
three. That is the correct outcome, and the reason is the important part.

### THE PHASE 2 FINDING: campaign 1's timeframe is not viable

Trial t0005 is roughly break-even GROSS and loses entirely to friction.
Measured on BTCUSDT over the research span, same strategy, same registered
costs (1 tick slippage + 0.05 % taker per side = 10.0 bps round trip on a
~$28.8k average notional):

| Timeframe | Donchian | Trades | PF | Net | Gross before fees | Friction | Friction / abs(gross) |
|---|---|---|---|---|---|---|---|
| 5m | 96 | 6,966 | 0.52 | -$300,645 | -$18,730 | $281,916 | 1505 % |
| 1h | 24 | 1,213 | 0.88 | -$9,803 | +$3,570 | $13,373 | 375 % |
| 1h | 48 | 834 | 0.93 | -$3,727 | +$4,808 | $8,536 | 178 % |
| 1h | 96 | 552 | 0.96 | -$1,337 | +$3,761 | $5,098 | 136 % |

At 5 minutes the cost hurdle is fifteen times the gross edge, so no amount
of hill-climbing inside that family can clear it; the loop would spend five
nights failing for a reason that has nothing to do with the ideas it tries.
At one hour the gross edge turns POSITIVE and friction falls to ~1.4x it,
which a real improvement could plausibly close. The gates are not too
tight: they are correctly refusing a structurally unprofitable design.

**Recommendation before Phase 3: re-register campaign 1 on 1h bars.** The
change is `timeframe`, the two `csv` filenames (the 1h files already exist
from Phase 0), and a re-pin of the folds; the gate bars stay as accepted,
except `min_oos_trades_per_asset` which should drop from 100 (1h produces
roughly a tenth the trades). This is a material change to what the operator
accepted, so it is NOT applied unilaterally -- operator and Antigravity
decide. An alternative worth their consideration is keeping 5m but pricing
maker/limit entries instead of taker, which changes the engine's cost model
and therefore needs its own ruling.

### Phase 3. First overnight

1. `cd quant_trading_lab && git checkout -b autoresearch/<campaign_tag>`.
2. `/loop` self-paced with the prompt in s.5.3. The loop ends itself when
   the runner exits 4.
3. Morning protocol (15 min): read the ledger tail, the keeps' diffs and
   hypotheses; if any keep exists, run `holdout.py` for the best on
   `master` after a file-scoped cherry-pick; record the holdout verdict in
   the ledger; Antigravity cross-check; update `AGENTS.md`.
4. Expect most keeps to die at holdout. That is the design working, not a
   defect. A campaign with no holdout survivor after 5 nights is retired
   and the candidate file reverts to v0.

**Executed 2026-09-11 18:21-20:19Z. Campaign 2 ran its full 40-trial
budget and the keep FAILED the holdout.**

| Asset | Walk-forward PF | Holdout PF | Trades | Net | maxDD |
|---|---|---|---|---|---|
| BTCUSDT | 1.28 | **0.75** | 19 | -$337 | 1.05 % |
| ETHUSDT | 1.26 | **0.97** | 27 | -$48 | 0.71 % |

That is the blueprint working as designed. Twelve gates and an 8-fold
walk-forward were NOT sufficient to guarantee out-of-sample survival, and
the one test the loop is fenced out of caught what they missed. No paper
promotion; the candidate is retired. Findings worth carrying to any
future campaign:

1. **The in-sample optimizer's preferred parameter was harmful.** In every
   trial where the trend window was a grid choice, both assets selected
   200; fixed there the score is 0.91 with 2-3 of 8 folds positive. The
   kept value 100 was never selected and survives only because the
   parameter was dropped from the grid and left at an unexamined default.
   Confirmed a peak: 50 -> 0.97, 100 -> 1.26, 200 -> 0.91.
2. **Grid size has an optimum, not a direction.** 12-16 combinations
   overfit, 9 produced the keep, 6 was worse because two values per
   dimension leave each point a single neighbour and blind the plateau
   statistic. `max_grid_combinations` arguably needs a matching minimum.
3. **One-at-a-time ablation understates mutually redundant mechanisms.**
   The position test costs 0.00 alone and path-shape 0.02 alone, but 0.08
   together. Combination ablation is required before calling a mechanism
   expendable.
4. **A mechanism invisible in the objective still earned its place.**
   Ablating volatility expansion left pooled PF unchanged but dropped BTC
   from 6/8 to 4/8 folds. A score-only loop deletes it.
5. **Four independent confirmations that this family needs room**:
   breakeven ratchet 0.48, wider stops rejected, structural stop 0.54,
   tighter ATR stop 0.98.
6. **The plateau gate is mis-specified** (s.8 point 8, still unruled):
   mean-of-ratios is corrupted when a fold's denominator approaches zero;
   median and ratio-of-sums both pass where the mean fails.
7. **Wall-clock scaling**: with `/loop` self-pacing clamped to a 60 s
   floor, campaign wall time is trials x (delay + work), so it is set by
   the cadence rather than the compute. 40 trials took ~2 h at ~28 s of
   work each.

Operator action before the first night: confirm whether usage overage
billing is enabled on the Claude account. An overnight `/loop` stays inside
the subscription only if it is off or explicitly accepted.

### Phase 4. Wiki adapter and parity

1. `knowledge/ingest/autoresearch.py`: `compile_autoresearch_registration`
   dispatched on `protocol` like `event_study`; a panel page from the trial
   JSONs (never from the TSV); one page per keep; holdout verdicts appended
   to the panel. Lint C1 guards every gate bar against
   `campaign.meta.json`; L12 data-gap treatment reuses the gap helper.
   Register, index and log only when something changed. Tests mirror
   `test_event_study_ingest.py`: real registration compiles lint-clean,
   C1 fires on a corrupted bar, idempotent, refusals.
2. Parity: port a holdout survivor to Pine from `_stack_template.pine`,
   run it once in the TradingView Strategy Tester over the holdout window
   only, export the trade list, diff against `holdout_<sha>.json` with a
   tolerance of one bar on time and one tick on price. Disagreements are
   findings about the Python or the Pine, never silently accepted.
3. Promotion path is the existing one: paper tier, then a separate live
   decision under the locked live tier. Nothing in this plan touches live.

Estimate: 25 min for the adapter and tests; parity is manual until a
desktop bridge decision is made.

## 5. PROGRAM.md (the loop's instructions, condensed)

### 5.1 Fixed facts the program states

Editable file, campaign tag, the runner command, the exit code table, the
file-scoped git commands, the trial cap, and the sentence Karpathy uses:
do not pause to ask whether to continue; the loop ends when the runner
says the cap is reached or the operator interrupts.

### 5.2 One iteration

1. `git status --short` and confirm the branch; read the last 10 ledger
   rows and the current best `S`.
2. Write one hypothesis as a market mechanism. Banned: adding a filter
   because losing trades were seen; anything keyed to a date, a price
   level or an event name; more than one mechanism per trial.
3. Edit only `strategies/stack9_candidate.py`. Update `PARAM_GRID` if a
   tunable was added (count stays <= 6).
4. `python -m research.autoresearch.run_trial --hypothesis "..."`.
5. Exit 0: commit the three paths. Exit 1 or 2: checkout the candidate
   file. Exit 3: read the reason, fix the violation, do not re-score
   until it is clean. Exit 4: stop the loop.
6. Next iteration.

### 5.3 The `/loop` prompt

`Run exactly one autoresearch iteration as specified in quant_trading_lab/research/autoresearch/PROGRAM.md, then end your turn. If the runner printed CAMPAIGN_CAP_REACHED, stop the loop.`

## 6. What is deliberately not in scope

- Any TradingView MCP as a dependency. The desktop bridge is optional for
  s.4 Phase 4 parity, needs a paid TradingView Desktop plan, and its own
  README says automation may conflict with TradingView's terms. Operator
  decision, later.
- Futures data beyond Yahoo's 60-day 5m window. Databento or similar is a
  paid vendor and a money-spend gate.
- Evolutionary or multi-candidate search. Single-candidate hill-climb
  first; the ledger will show whether diversity is the bottleneck.
- Statistical deflation beyond the cap plus holdout (White's reality
  check, CPCV). Listed as a Phase 5 candidate once a campaign has produced
  a holdout survivor to deflate.
- Live trading. The live tier stays locked as recorded in memory.

## 7. Risks and the fence that answers each

| Risk | Fence |
|---|---|
| Loop edits the engine, the costs or the folds | diff fence refuses the trial; the change never scores |
| Loop reads holdout or future bars from inside the strategy | import fence plus runner-side truncation |
| Loop hard-codes dates or levels | literal detector refuses; morning diff review |
| Filter stacking | tunable cap plus mandatory single mechanism per trial |
| Best-of-40 illusion | trial cap in the ledger plus holdout on master |
| Clobbering the other agent's uncommitted lab work | file-scoped commit and checkout only, never `add -A` or `reset` |
| Ledger tampering | wiki compiles from JSON with sha256, not from the TSV |
| A keep that is a Python-Pine mismatch | parity diff before any paper promotion |
| Overnight cost | overage billing confirmed before the first night |

## 8. Cross-check request for Antigravity

Please independently audit this blueprint against the lab at 33ebe81 and
DEV at f0648bf, without deferring to it. In particular:

1. ~~Does `WalkForwardOptimizer.build_rolling_windows` produce fold
   boundaries that are stable across trials given only `num_windows` and
   `train_fraction`, or must the plan pin explicit timestamps in
   `campaign.meta.json`? Read the implementation, not the docstring.~~
   **ANSWERED in Phase 1 (see s.4 Phase 1 finding 1): index-based, so
   deterministic for a fixed span; the registration pins a fold
   FINGERPRINT rather than timestamps.** Please still audit that
   conclusion and the fingerprint mechanism independently.
2. Is pooled out-of-sample profit factor across folds the right primary,
   or would the lab's own calmar objective serve better for a strategy
   with multi-day holds? Argue it with the metric definitions in
   `grid_search.calculate_metrics`.
3. Are the gate bars in s.2.3 defensible for 5-minute crypto bars over
   41 months, or too loose or too tight? Propose numbers with reasoning.
4. Is the literal detector in `fences.py` too crude to be useful, and if
   so what would you check instead?
5. Anything this plan quietly widens beyond the ask, and anything the
   loop could exploit that the fences in s.7 do not cover.

Return findings as a numbered list with a severity and, where you disagree,
a concrete alternative.

**Added after Phase 1 shipped (please audit these too):**

6. The dirty-tree fence now exempts `ledger.tsv` and `trials/` (s.4 Phase 1
   finding 2). Argue whether that exemption is exploitable by a loop that
   wants to hide a trial, given append-only writes, the overwrite refusal,
   the per-row sha256 and the per-trial commit.
7. `deploy_params` for the holdout is the LAST fold's in-sample selection.
   Is that the right choice versus the modal selection across folds, or a
   re-fit on the full research span? Argue from what a walk-forward
   deployment would actually trade next.
8. The plateau ratio is `plateau_score / own_score`, forced to 0.0 when the
   objective is non-positive. On the real baseline this produced 0.0 and
   -0.14. Is the ratio meaningful at all when calmar is negative, or should
   the gate be defined on the raw plateau score instead?
9. `S` is the MINIMUM pooled out-of-sample profit factor across the two
   assets. That makes one bad asset veto the trial. Is min right, or should
   it be a trade-weighted pool across both assets?

## 9. Operator actions

- Decide on the gate bars and the 5 % delta (s.2.3) or accept them.
- Confirm overage billing state before Phase 3.
- Run the Phase 0 geo check result past the money gate if the fallback
  turns out to be a paid source.
- TradingView Desktop and the bridge: a later decision, money and terms.
