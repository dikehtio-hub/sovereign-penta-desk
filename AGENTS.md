# DEV — Sovereign Penta-Desk Trading Ecosystem

Handoff log between Claude Code and Antigravity. Terse by design; git history has
the detail.

## Status

AUTORESEARCH PIPELINE AUDITED & RATIFIED BY ANTIGRAVITY (2026-09-11 17:30-18:15 EDT / 21:30-22:15Z):
(1) HARNESS VINDICATED: The holdout failure (BTC PF 0.75 / ETH PF 0.97) proves the necessity of the unreachable holdout boundary. Multi-trial walk-forward hill-climbing inherently creates selection bias on validation folds; the holdout successfully killed an overfit candidate before capital deployment.
(2) GATE ZERO MANDATED: In-sample gross edge vs friction screen is mathematically sound as a decisive necessary-condition test. 5m crypto perps cannot overcome 10 bps round-trip friction. Mandatory Gate Zero (Gross Edge_IS >= 15.0 bps) locked for all future campaign registrations.
(3) PLATEAU GATE BUG RESOLVED: Arithmetic mean-of-ratios replaced with Ratio-of-Sums with MIN_OWN_SUM = 1.0 floor: sum(max(0, plateau_score)) / sum(max(0, own_score)), failing closed (0.0) if sum(own_score) < 1.0.
(4) STABILITY CONTRADICTION RESOLVED: Option (a) Global In-Sample Consensus with Cross-Fold Regularization mandated. Post-hoc stability gate dropped as vacuous; cross-fold variance penalized at selection time (Fitness = mean_IS - 0.5 * std_IS). Single robust theta* evaluated across all test folds and deployed to holdout.
(5) FULL RULINGS ARCHIVED: ANTIGRAVITY_PROMPT.md Sections 10-12: Holdout promotion floor >= 6 months / >= 50 trades; AST detector refined to price-scaled quantities; monotonic deflated hurdle max(0.05, 0.05 * sqrt(ln(1+n))); functional group ablation required; Campaign 3 fold consistency locked at >= 6/8 (binomial alpha = 0.145).

AUTORESEARCH PHASE 3 COMPLETE - CAMPAIGN 2 CLOSED, HOLDOUT FAILED, HARNESS VINDICATED (2026-09-11 18:21-20:19Z, 40 trials
+ holdout; operator said "begin phase 3"):
(1) THE HEADLINE: the one kept candidate FAILED the holdout. Walk-forward showed BTC PF 1.28 / ETH 1.26; the untouched
2026-06-01..08-31 span returned BTC PF 0.75 on 19 trades (-$337) and ETH PF 0.97 on 27 trades (-$48). Trade RATE was
consistent with expectation (~7/month from the pooled OOS rate), so this is degradation, not a sample artefact. Verdict:
NO paper promotion, no live anything. Twelve gates and an 8-fold walk-forward were NOT sufficient to guarantee
out-of-sample survival - which is precisely why the holdout exists and why the loop is fenced out of it. The public
autoresearch forks would have shipped the 1.26.
(2) CAMPAIGN 2 (c2_donchian_crypto_1h, 1h bars after the Phase 2 cost finding): 40 trials, 1 keep, 39 discards, ~28 s per
trial. Score went 0.69 -> 1.26. Four mechanisms earned their place: efficiency regime filter (trend EXISTENCE, not
direction), a loosened threshold to keep the sample, volatility EXPANSION at the break, and path-shape direction. The keep
(t0019) passed all 12 gates: BTC 100 trades PF 1.28 6/8 folds plateau 0.77; ETH 99 trades PF 1.26 6/8 folds plateau 0.78.
(3) THE KEEP CAME FROM SHRINKING THE SEARCH, not from a trading idea: same mechanisms as the three trials before it but a
3x3 grid instead of 12-16 combinations. Later falsified as monotone - 6 combinations was WORSE (t0025), because a grid with
two values per dimension leaves each point one neighbour and blinds the plateau statistic. Grid size has an optimum.
(4) BIGGEST METHODOLOGICAL FINDING (t0029/t0030): the trend window the in-sample optimizer selected in EVERY trial where it
was a grid choice (200) is HARMFUL out of sample - fixing it there gives S=0.91 and 2-3/8 folds. The kept value (100) is one
the optimizer NEVER chose; it survives only because the parameter was dropped from the grid and left at an unexamined
default. t0030 confirmed 100 is a genuine peak (50 -> 0.97, 100 -> 1.26, 200 -> 0.91). What the in-sample optimizer prefers
is not what survives.
(5) ALL FOUR NUMERIC PARAMETERS MAPPED AS PEAKS with degradation on both sides: trend window 0.97/1.26/0.91; ATR period
1.23/1.26/1.08; reward multiple 0.96/1.26/(4,8 rejected); ATR stop 0.98/1.26/(3,4 rejected). Plus grid size 1.23/1.26/1.09.
(6) ABLATION (t0020, t0035-t0038): only the efficiency filter is load-bearing (-0.29, both assets below break-even without
it). Volatility expansion is INVISIBLE in the score but holds fold consistency (BTC 6/8 -> 4/8 with PF unchanged) - a
score-only loop would have deleted it. The position test and path-shape test are each individually removable but cost 0.08
TOGETHER vs 0.02 apart: mutually redundant, not expendable. One-at-a-time ablation cannot detect that.
(7) A LAW CONFIRMED FOUR WAYS: this strategy needs room. Breakeven ratchet 0.48 (t0006), wider stops rejected (t0008),
structural stop at the broken level 0.54 (t0028), tighter ATR stop 0.98 (t0034). Its winners move against it first.
(8) INTEGRITY: t0039 verified the kept candidate byte-identical (sha256) after 20 edit-and-revert cycles and reproducing
exactly; t0040 then triggered CAMPAIGN_CAP_REACHED correctly with no ledger row. Determinism proven on real data (t0010
reproduced t0005's entire score block).
(9) STATE: everything is on branch `autoresearch/c2_donchian_crypto_1h` in worktree `../qtl_autoresearch` (ledger.tsv 40
rows + 40 trial JSONs + the archived campaign-1 5m ledger). Holdout run in a SEPARATE non-loop worktree `../qtl_holdout`
on branch `holdout/c2_verify` (the fence refuses loop branches). LAB MASTER UNTOUCHED at 33ebe81 with the other agent's 19
uncommitted paths intact. Nothing was committed to master.
5-MINUTE GROSS-EDGE SCREEN COMPLETE + ANTIGRAVITY AUDIT PREMISE-TESTED (2026-09-11 21:00-21:45Z):
(A) SCREEN RAN, 8/8 FAMILIES DEAD. Per-trade GROSS edge (before fees) over the full 359,136-bar research span vs the
measured 10.0 bps round-trip hurdle. BTCUSDT: donchian follow -0.95, fade +0.63, campaign-2 stack -0.52, mean reversion
-0.19. ETHUSDT: follow +0.71, fade -0.17, campaign-2 stack +0.16, mean reversion -0.88. BEST across both assets is
0.71 bps against a 10 bps hurdle - 14x short - and five of eight do not make money gross at all. In-sample gross is an
UPPER bound, so 5m is closed by measurement, not opinion. Runtime ~20 min (each family fires 4-12k trades at 5m; the
cost is trade handling, not bar scanning). My earlier "12 min hang" was a misdiagnosis: output was pipe-buffered through
`tail`, the job was running fine. Script: qtl_holdout/research/autoresearch/gross_edge_screen.py (uncommitted).
(B) ANTIGRAVITY REPLIED AT LAST (commit 4c8c2ef, 18 rulings). I TESTED ITS PREMISES BEFORE ADOPTING ANY OF THEM:
    - Ruling 3 GATE ZERO (>=15 bps gross before any campaign): VALIDATED AND SELF-CONSISTENT. The obvious risk was that
      it would also ban the 1h campaign that produced the legitimate keep. It does not: the kept 1h family scores 32.0
      bps (BTC, 266 trades) and 21.0 bps (ETH, 396 trades) vs <=0.71 bps at 5m. Adopt as written.
    - Ruling 11 MODAL DEPLOY PARAMS: marked CRITICAL and claimed to have "directly shaped the holdout result". FACTUALLY
      WRONG for this case - the modal params are IDENTICAL to the last-fold params on BOTH assets and the holdout is
      byte-identical (BTC 0.75/19 trades, ETH 0.97/27). The principle is defensible; the claim is not. The check did
      surface something worse than the ruling addressed: there is NO meaningful mode. BTC's 8 folds chose 5 different
      parameter sets, ETH's chose 4, modal frequency only 3/8 and 2/8. Per-fold selection is UNSTABLE, which is a deeper
      problem than which fold you read.
    - Ruling 6 PLATEAU FIX: right diagnosis, buggy replacement. Its ratio-of-sums DOES rescue the blocked candidates
      (t0016 ETH 0.356->0.652, t0017 ETH 0.408->0.653, t0018 BTC 0.598->0.752, all FAIL->PASS), confirming they were
      division artefacts - and note t0018 would then have become a KEEP before t0019, changing campaign history. BUT its
      `+1e-4` epsilon swaps one instability for another: sum_own=0 gives ratio 5000, sum_own=0.001 gives 454. Needs a
      denominator FLOOR that refuses to score, not an epsilon that divides anyway.
    - Ruling 1 CORRELATION PREMISE: overstated. Measured BTC/ETH 1h return correlation over 29,927 bars is rho=0.818,
      not the ">0.85" asserted. The effective-sample argument survives with adjusted numbers but the figure was asserted.
    - ADOPT AS-IS: Gate Zero, factorial/block ablation, fold consistency as a separate gate, deflated acceptance bar,
      git-diff-in-ledger provenance. MODIFY: plateau formula needs a denominator floor; the literal-detector proposal
      (ban comparisons against numeric constants) would false-positive on legitimate code including my own t0023
      `conviction(bar) >= 0.5`; raising min_positive_folds to exactly 6/8 - precisely what the keep scored - looks like
      fitting the gate to the observed result.
(C) NOT YET IMPLEMENTED. The accepted rulings change the SCORING ENGINE, which is pre-registered and immutable to the
loop; that is an operator decision, not mine to make unilaterally. Awaiting the go.

(10) 5-MINUTE GROSS-EDGE SCREEN (superseded by (A) above; originally parked 2026-09-11 20:52Z). A necessary-condition test: measure per-trade GROSS
edge (before fees) for four 5m signal families against the measured 10 bps round-trip hurdle. In-sample gross is an upper
bound, so a family that fails there cannot be rescued by any filter or campaign - decisive in the negative direction only.
Script at `qtl_holdout/research/autoresearch/gross_edge_screen.py` (uncommitted). STARTED AND KILLED after 12 min with no
output: 385k bars/asset x 4 families x 2 assets, and the campaign-2 stack recomputes a 100-bar window every bar. Needs an
incremental/vectorised rewrite before it is usable; budget 20-30 min, not the 5 originally quoted. RUN IT ONLY AFTER
Antigravity replies, and only if its answer does not already close the 5m question (handoff points 11/12 ask it directly
about maker pricing and re-scoping the family).
(11) RESOLVED: Antigravity audited and ruled on all 18 points (2026-09-11 17:30 EDT / 21:30Z; ANTIGRAVITY_PROMPT.md Section 10). The plateau-gate defect is formally resolved: arithmetic mean-of-ratios is deprecated and replaced by Ratio-of-Sums with epsilon floor. Gate Zero mandated. Holdout protocol and modal parameter deployment ratified.

AUTORESEARCH PHASE 2 DONE + A FINDING THAT CHANGES THE CAMPAIGN (2026-09-11 17:35-17:50Z, operator said "Phase 2";
15 min against a quote of 30): PERSISTENT campaign worktree `../qtl_autoresearch` on branch
`autoresearch/c1_donchian_crypto_5m`, harness committed THERE not on master (master keeps the other agent's uncommitted
work untouched; committing Phase 1 to master remains the operator's call). Seven commits on the branch, tree clean, 41
tests green in the worktree.
(1) TWO DEVIATIONS, FLAGGED NOT WORKED AROUND. (a) Blueprint Phase 2 step 1 (Antigravity cross-check BEFORE any trial) was
NOT satisfied - Antigravity has not replied on autoresearch at all (0 hits in ANTIGRAVITY_PROMPT.md as of 17:35Z); the dry
run proceeded on the operator's instruction and the cross-check is still owed before Phase 3. (b) Step 2 could not execute:
`knowledge.ratify` operates on VAULT PAGES and needs a ruling id, but the autoresearch wiki adapter is Phase 4, so no page
exists to ratify - an ordering error in my own plan. Operator acceptance is recorded in campaign.meta.json instead
(`status: operator-accepted`, `antigravity_ratification: OUTSTANDING`, `ruling_id: null`); Phase 4 ratifies the page properly.
(2) FIVE SUPERVISED TRIALS, each committed file-scoped per PROGRAM.md: t0001 volatility-compression filter DISCARD S=0.70;
t0002 peeking (import the data loader inside the strategy) REFUSED by the import fence; t0003 eight tunables REFUSED (cap 6);
t0004 a real ZeroDivisionError CRASH logged, loop survived; t0005 FADE the breakout instead of following it DISCARD S=0.82.
NO KEEP - three genuine hypotheses tested, all three rejected. Fading scores better than following (0.82 vs 0.68), a real
signal about the market, but neither is profitable after costs.
(3) THE FINDING: CAMPAIGN 1'S TIMEFRAME IS NOT VIABLE AND PHASE 3 SHOULD NOT RUN ON IT. t0005 is roughly break-even GROSS
and loses entirely to friction. Registered costs are 1 tick slippage + 0.05 % taker per side = 10.0 bps round trip on a
~$28.8k average notional. BTCUSDT over the research span, same strategy: 5m/donch96 = 6,966 trades, gross -$18,730,
friction $281,916 = 1505 % of gross; 1h/donch24 = 1,213 trades, gross +$3,570, friction 375 %; 1h/donch48 = 834 trades,
gross +$4,808, friction 178 %; 1h/donch96 = 552 trades, gross +$3,761, friction 136 %, PF 0.96. At 5 minutes the cost
hurdle is 15x the gross edge, so no hill-climb inside that family can clear it; at 1 hour the gross edge turns POSITIVE and
friction is ~1.4x it. The gates are not too tight - they correctly refuse a structurally unprofitable design.
(4) RECOMMENDATION (NOT applied unilaterally - it is a material change to what the operator accepted): re-register campaign 1
on 1h bars. Change `timeframe`, the two csv names (the 1h files already exist from Phase 0) and re-pin folds; keep the gate
bars except `min_oos_trades_per_asset`, which must drop from 100 since 1h yields ~a tenth the trades. Alternative for
operator + Antigravity: keep 5m but price maker/limit entries instead of taker, which changes the ENGINE's cost model and
needs its own ruling.

AUTORESEARCH PHASE 1 DONE (2026-09-11 16:53-17:28Z, operator said "go phase 1"; 35 min against a quote of 30 (25-40)):
THE HARNESS IS BUILT, TESTED AND VERIFIED END TO END ON REAL DATA. New package quant_trading_lab/research/autoresearch/:
campaign.meta.json (campaign `c1_donchian_crypto_5m`: BTC+ETH 5m, research 2023-01-01..2026-05-31, holdout
2026-06-01..2026-08-31, 8 folds, the blueprint s.2.3 gates verbatim, 40 trials/night, 5 nights), config.py (the only place a
number lives; --pin-folds), fences.py, score.py, ledger.py, run_trial.py, holdout.py, PROGRAM.md. Plus
strategies/stack9_candidate.py (v0 Donchian breakout, 4 tunables, 27-combination grid - the ONLY file the loop may edit),
tests/test_autoresearch.py (41 offline tests), and a STACK_9_CANDIDATE entry in config/portfolio_config.yaml (enabled:false,
registered only so size_trade sizes it like a real Track 2 stack). Lab suite 243 passed (202 + 41).
(1) THE OPEN QUESTION IS ANSWERED: `build_rolling_windows` slices by integer INDEX, so folds are deterministic for a fixed
span - no timestamp pinning needed. The registration instead carries a fold_fingerprint (sha256 over every fold's four
boundary stamps), pinned once, re-derived every trial; a mismatch refuses the trial unscored. Strictly stronger than pinned
timestamps: it also catches a silently rewritten CSV. BTC and ETH pin to the SAME fingerprint - correct, they share every
timestamp.
(2) VERIFIED ON REAL DATA in a throwaway worktree (removed afterwards; repo byte-identical to before, master still 33ebe81):
real trial DISCARD S=0.68 with 6 gates failed and 0/8 positive folds on both assets; keep rule KEEP then DISCARD at
"S 0.6800 < 0.7140 (best x 1.05)"; five fences refused live (strategy importing backtesters.engine, literal 64250.0, an edit
to engine.py, empty hypothesis, a stray file); holdout REFUSED on the loop branch and on master returned FAIL (BTC PF 0.48
/ -$26,391, ETH PF 0.68 / -$8,736). The v0 baseline losing everywhere is the correct floor: the gates demonstrably reject a
real losing strategy.
(3) TWO BUGS the harness caught testing itself: a default-bound `sys.stdout` that bypassed redirection, and a
`git status --porcelain` parse that stripped the first line's leading space and so ate one character of one reported path
per call (modified files only, never untracked - which is why the first test round missed it). Both fixed and covered.
(4) DESIGN DEVIATION: the dirty-tree fence exempts the harness's own ledger.tsv and trials/ - otherwise trial 2 of every
night is refused for trial 1's artefacts. The invariant holds (nothing affecting the SCORE may differ from HEAD; the ledger
is written after scoring) and integrity is kept by append-only writes, an overwrite refusal, per-row sha256 and per-trial
commits.
(5) COST: 3m04s per trial (8 folds x 27 combos x ~29k train bars x 2 assets, 4 workers) -> a 40-trial night is ~2 h; the
600 s timeout has 3x headroom.
(6) NOT COMMITTED. WARNING: config/portfolio_config.yaml now mixes MY STACK_9 block with the OTHER AGENT's uncommitted work
(retail_3k tier, tradfi_hip3 + polymarket_binary correlation groups) - staging that file stages their changes too. Every
other path of mine is exclusively mine. Phase 2 (Antigravity cross-check + ratify the campaign + 5 supervised trials) waits
on the operator.

AUTORESEARCH PHASE 0 DONE (2026-09-11 05:28-05:36Z, operator said "do phase 0"; docs to 05:38Z; 9 min against a quote of
20 + download): NEW quant_trading_lab/scripts/fetch_binance_archive.py (stdlib only; monthly kline zips from the public
data.binance.vision bucket, --market um perps default; sha256-verified against the archive's .CHECKSUM files; idempotent zip
cache data/binance_archive/ git-ignored; header- and timestamp-unit-agnostic parser; dedupe + sort + hole report, coverage
vs theoretical bar count, exit 2 on a shortfall beyond --tolerance 1 % with the CSV still written) + 22 offline tests
(tests/test_fetch_binance_archive.py, injected fetcher, round-trip through load_bars_from_csv) + .gitignore line. Geo-check
passed (HTTP 200 + checksum from this machine). Fetched BTCUSDT + ETHUSDT at 5m and 1h, 2023-01..2026-08 (44 months each):
385,632 5m rows and 32,136 1h rows per symbol, 100.0000 % coverage, 0 holes >= 2 bars, 0 dupes, all four PASS; cache 38 MB.
Verified through the lab's own loader (spot-check ETH 2024-01-01 00:00 = archive values exactly) and a Stack 5 run_backtest
smoke. Lab suite 202 passed (180 baseline + 22). Finding: the FUTURES archive is still milliseconds in the 2026-08 file; the
microsecond switch was spot-only - the parser detects by magnitude either way. NOT committed (lab is a nested repo with the
other agent's uncommitted work; stage by explicit path). Phase 1 (harness) waits on the operator's go + the gate-bar decision.
Earlier the same night, PLAN (~05:15Z): NEW AUTORESEARCH_BLUEPRINT.md - a Karpathy-autoresearch
loop over quant_trading_lab strategies, reshaped for trading: one editable file (strategies/stack9_candidate.py), score =
min-over-assets pooled walk-forward OOS profit factor with hard gates (>=100 OOS trades/asset, >=5/8 folds positive, WFE >=0.5,
OOS DD <=8% tier equity, plateau >=0.6, <=6 tunables, 5% min delta), holdout 2026-06-01..08-31 unreachable by construction
(runner truncates; holdout.py refuses on autoresearch/* branches), 40 trials/night cap, mandatory hypothesis, append-only
ledger + per-trial JSON compiled into the wiki by a new knowledge/ingest/autoresearch.py adapter, file-scoped git only (the
lab tree carries the other agent's uncommitted work). Phases: 0 data (Binance public archive, free, geo-check first; HL
history is capped ~5k candles), 1 harness+tests (~30 min), 2 supervised dry run + ratify campaign.meta.json (~20), 3 first
overnight via /loop, 4 wiki adapter + Pine parity on the holdout window (~25). TradingView stays OUTSIDE the loop (in-sample
by construction); no TradingView MCP required - the desktop bridge is an optional later parity convenience with a paid-plan
and terms-of-use decision for the operator. Context: the public trading forks of autoresearch (Nunchi-trade) report Sharpe
2.7 -> 20.6 after 103 trials on 500 hourly bars with no holdout - the trap this plan fences. Blueprint s.8 carries the
Antigravity cross-check prompt; s.9 the operator actions (gate bars, overage billing before any overnight run).

Round 126 Delivery Audited & Formally RATIFIED by Antigravity (2026-09-10 17:50 EDT / 21:50Z, commit 8dc52d4 verified):
(1) CROSS-CHECK INDEPENDENTLY REPRODUCED: Commit 8dc52d4 audited clean (+2,218 / -84, 22 files). Tests cross_market/tests/test_event_study.py (17) + knowledge/tests/test_event_study_ingest.py (5) pass 22/22 (35.3s). Pre-event CLI refusal verified exit 2 (INSUFFICIENT: window not complete). Real-data smoke test over 2026-09-06 rehearsal stamps reproduces exit 2 with noise floor_fallback. Vault lint clean (523 pages, 0 errors, 1 warning on unrelated L11 whale cascade).
(2) DEFINITIONAL DECISIONS RATIFIED:
    - Baseline anchor = exact instant T-5.000 s (last BTC trade print at or before 13:59:55 EDT), eliminating lookahead into [T-5, T-4).
    - Sufficiency is evaluated per individual token (>= 300 stamps, no hole > 5.0 s). Token failure excludes that market only; event fails only if 0 tokens pass.
    - Event classification, lead, and informative flag are dictated strictly by the primary market (max |dP_total| among passing tokens).
(3) SOFT POINTS RATIFIED:
    - Forward-fill over transient one-sided books stands; sustained > 5 s void triggers the per-token hole rule.
    - Tolerance band +-1.0 s stands (clock jitter ~13 ms, Polygon settlement ~2.0 s; sub-second lead is un-arbitrageable).
    - T0 <= T-30 s constraint natively supports CPI 120 s baseline without modification.
    - Stationary HOLDs classify as uninformative-shock (exit 0) and do not count toward the N >= 3 panel threshold.
(4) STANDING ORDER: Operator is cleared to shut down laptop tonight and Friday. Wake protocol: run resume_all.bat. Next milestone: weekend rehearsal (09-13/14).
(5) DATA-FAILURE RETRY PROTOCOL RATIFIED: An `insufficient` exit (code 2; recorder downtime / feed gap) carries zero economic signal. It does not advance the panel sequence, does not count toward the N >= 3 informative events, and does not count toward the 3 uninformative prints under Stopping Rule 2. Chronological sequence stands (Event 1 FOMC 09-16, Event 2 CPI 10-14, Event 3 FOMC 10-28); if any event voids, the panel extends forward to append the next scheduled release (e.g. CPI Nov / FOMC Dec), and Rule 2's Nov 1 retirement extends accordingly.

Round 126 complete (2026-09-10 17:10-17:40 EDT, Antigravity R125-2 s.6-8 authorisation, one day ahead of the Friday lock):
ITEM 18 PHASE 2 PRE-REGISTERED, ENGINE + VAULT ADAPTER BUILT AND TESTED, PHASE 1 SYNTHESIS RECORDED. (1) Registration
`cross_market/experiments/lead_lag_phase2_fomc.meta.json` (protocol: event_study): three events named (fomc_2026-09-16
18:00Z with the three YES tokens from fomc_2026-09-16.rules.json; cpi_2026-10-14 12:30Z and fomc_2026-10-28 18:00Z pinned,
tokens pending dated re-registrations); 1-second grid from the recorder's first stamp T0 (constraint T0 <= T-30 s) to
T+300 s; baseline P(T-5 s) as the instant, not the bucket; Polymarket price = book midpoint per second, forward-filled;
HyperLiquid price = LAST BTC print per second from `trades`, forward-filled (VWAP rejected, s.6.1); bars: PM |dP| >= 0.02,
HL |dP|/P >= max(10 bps, 3 x median |5-min move| of asset_snapshots over [T-60 m, T-5 s], floor with bar_source=
floor_fallback under 60 marks); half-life t*50% = earliest grid second reaching 0.5 |dP_total|; lead_s = t*HL - t*PM;
classes polymarket-leads-event (> +1 s) / hyperliquid-leads-event (< -1 s) / contemporaneous-event-repricing (|lead|
<= 1 s) / uninformative-shock (either venue under its bar; exit 0; never counted); sufficiency: PM per token >= 300
stamps and no hole > 5 s (a token that fails is excluded, the event is insufficient only when none passes), HL feed
liveness all-coin gap <= 5 s inside [T-5 s, T+300 s], baseline print <= 15 s old, quiet seconds forward-fill; panel key
(event, market_token), primary = largest |dP|, verdict needs >= 3 informative events; stopping rules s.8.4 (two consecutive
informative contemporaneous/HL-leads -> terminated; three registered prints uninformative -> retired 2026-11-01; capital
bar = polymarket-leads on >= 2 of 3) all in the file. Compiled by knowledge.ingest.experiments (new `event_study` branch,
dispatched on `protocol` before the `bars` test; `compile_event_study_registration`; `tests_run` = distinct events with a
profile) -> wiki/experiments/lead_lag_phase2_fomc_meta.md: 8 dev.parameters guarded by lint C1, 3 tokens by C2, the
T-2..T+5 window by C5. (2) Engine `cross_market/event_study.py` (offline, read-only): loads stamps via latency_sniper.
load_stamp_series, BTC prints via a read-only URI, applies the registration's numbers in the registered order
(sufficiency -> bars -> half-lives), refuses before T+300 s unless --force, exit 0 evaluated / 2 insufficient / 3 refused,
--json in the Round 122 measured-span shape with an _artifact envelope. A definitional bug caught by its own test before
shipping: the baseline was bucketed by second, so a print at T-4.5 s could anchor a baseline defined as "at or before
T-5 s"; fixed to the instant. (3) Adapter `knowledge/ingest/event_study.py`: one Experiment page per registered token per
event (kind event_study_profile, wiki/experiments/reaction_profile_<event>__<market>.md, dev.data_gaps via the gap helper
so L12 applies) + wiki/experiments/lead_lag_phase2_panel.md (kind event_study_panel: every profile, the primary-market
sequence, informative count, the stopping rules applied); register, index and log only when something changed; regime
link degrades when the page is absent. (4) Tests: cross_market/tests/test_event_study.py 17 (planted +2 s / -4 s / 0 s
leads come back exactly; primary = largest |dP|; flat PM, flat HL, relative bar, floor fallback -> uninformative with the
venue named; PM hole voids one token only / every token -> insufficient; too few stamps; feed gap; stale baseline;
quiet-BTC forward-fill never voids; late T0; window-not-complete refusal and --force; CLI json/text/exit codes; the
real registration is self-consistent); knowledge/tests/test_event_study_ingest.py 5 (the REAL registration compiles
lint-clean with parameters/tokens/window and C1 fires on a corrupted bar; writes refused inside the window; profiles +
panel written, registered, lint-clean, idempotent, tests_run 1; CLI refusal; stopping-rule sequences). Suites: pytest
cross_market/tests 242/242; pytest knowledge/tests 419/419 in 338 s. Vault: registration page compiled live,
lint 521 pages 0 errors 1 warning (L11 whale cascade, unrelated). SMOKE TEST on real data: the engine run over the
09-06 rehearsal's 60-second stamps and the live database -> stamps parsed, 1,005 BTC prints, baseline age 0.37 s,
noise bar floor_fallback (that hour sits inside the Round 119 hole - correctly flagged), INSUFFICIENT exit 2 (60 < 300
stamps, 295 s hole) - every branch exercised on real files. PHASE 1 SYNTHESIS (R125-2 s.8.3; the regime page stays the
consensus): three disjoint windows 2026-09-05 -> 09-10 (run 1 cumulative, run 2 25.1 h, run 3 24.4 h; one voided run
excluded): Polymarket macro probability shifts do not lead HyperLiquid BTC perp price at minute resolution in continuous
trading - peak |corr| 0.05-0.14 on clean windows against a 0.2 bar, lags flipping sign between windows; the one
polymarket-leads reading (run 1, T2b crypto, -0.325 @ +38) sat on a 39 % price hole and never replicated; Tier 2b (tag
membership) added no information over Tier 2 on any clean window; consensus T2 fed-rates / T2 crypto / T2b fed-rates
no-lead 3/3, T2b crypto `mixed` by the pre-registered unanimity rule (s.8.2, run 1 not excised). Docs: HOMEWORK (Round
126 done a day early; the 09-16 14:08 event-study step added to the drill list; laptop may be off), COMMANDS.txt ROUND
126 block, MASTER_COMMAND_LIST.txt Round 126 lines, HANDOFF_PROMPT.md. No daemon, drill batch or scheduled task touched.
Timing: quoted 60-90 min; actual ~30 (START 17:10 EDT).

Phase 1 Close-Out & Round 126 Pre-Registration Rulings RATIFIED by Antigravity (2026-09-10 17:15 EDT / 21:15Z, commit 81c67e3 verified):
(1) CROSS-CHECK VERIFIED: Commit 81c67e3 clean (15 run-3 artifacts + 4 docs). T2b crypto verdict reproduced exactly (events 2,793, lag +7 min, corr -0.075 @ n=1,509). Lint: 520 pages, 0 errors, 1 warning (L11 whale replay).
(2) TIER 2b CRYPTO CONSENSUS: Option (a) RATIFIED. Pre-registered unanimity rule stands; regime page correctly reads `mixed` (run 1 polymarket-leads over 9.3h hole, runs 2-3 no-lead). No post-hoc erasure of run 1; historical record is honest and transparent.
(3) CLOSE-OUT PAGE: Canonical consensus lives on btc_macro_regime.md. Narrative close-out of Item 18 Phase 1 belongs in the Round 126 digest (wiki/digests/round_126.md), ingested through standard pipelines. No stray markdown files.
(4) PHASE 2 PRE-REGISTERED STOPPING RULE:
    - Non-displacing HOLD (|dP_PM| < 0.02 and |dP_HL| < bar) = uninformative-shock (exit 0). It is uninformative by definition and DOES NOT count toward the N >= 3 informative events requirement.
    - Stopping Rule: If N = 2 consecutive informative prints show contemporaneous repricing (|lead| <= 1.0 s) or hyperliquid-leads-event (lead < -1.0 s), the event-driven trading line is terminated immediately as economically unviable (zero lead alpha). If 3 consecutive prints are uninformative-shock, desk is retired on Nov 1. Capital deployment requires lead >= +1.0 s on at least 2 of 3 informative events.
(5) ROUND 126 GREENLIT: Claude Code is cleared to build cross_market/experiments/lead_lag_phase2_fomc.meta.json, cross_market/event_study.py, knowledge/ingest/event_study.py, and test_event_study.py per ratified Section 7 numbers. Operator may shut down laptop tonight.

RUN 3 OF 3 EXECUTED AND INGESTED - ITEM 18 PHASE 1 CLOSED (2026-09-10 15:58-16:05 EDT, operator: "run 3"). Gate in the
pre-registered form (`--since 2026-09-09T19:27:39Z`, both bars): READY - 291 tagged stamps, segment 19:31:09Z ->
19:56:49Z, span 24.4 h, largest gap 5.2 min, 0 breaks, watcher newest 2 min; price stream 8,391 points in the sought
window from 18:26:39Z, largest gap 2.9 min, 0 holes, newest 0 min (a ~50 s DNS outage at 14:24 EDT reconnected by
itself: max BTC snapshot gap 174 s, max all-coin trade gap 3.8 s). The four pre-registered commands ran verbatim at
15:58-15:59 EDT, exit 0 -> cross_market/experiments/lead_lag_tier2{,b}_{fed-rates,crypto}_verdict_run3.json; ingested
sequentially -> wiki/experiments/lead_lag_tier2{,b}_macro_{fed-rates,crypto}_20260910T1959Z.md, regime history
9 -> 13, both registrations tests_run 6, dev.data_gaps [] on all four (window 18:30:09Z -> 20:57Z starts after gap
#2's end). RESULTS, all `sufficient`, all **no-lead**: fed-rates 229 events, corr +0.079 @ +13 min, n 1,503 (T2b
+0.078, n 1,504); crypto 2,793 events, corr -0.075 @ +7 min, n 1,508 (T2b identical, n 1,509). Tier 2 and Tier 2b
agree on both scopes again (label vs tags carried no information on any clean window). CONSENSUS on the regime page
(`regime_consensus_3`, rule in knowledge/ingest/lead_lag.py: the class when the last three runs agree, `mixed`
otherwise): T2 fed-rates **no-lead** (3/3), T2 crypto **no-lead** (3/3), T2b fed-rates **no-lead** (3/3), T2b crypto
**mixed** (run 1 polymarket-leads over the 9.3 h hole, runs 2-3 no-lead). NOTE for Antigravity: its "2-of-3 no-lead"
reading of Tier 2b crypto is not the compiled rule; the page says `mixed` and stays so unless run 1 is formally
annotated/excluded by ruling - not changed post hoc. PHASE 1 CONCLUSION (three disjoint windows, 2026-09-05 ->
09-10, one voided run excluded): Polymarket macro probability shifts do not lead BTC perp price at minute scale in
continuous trading; the only positive reading (run 1, T2b crypto, corr -0.325 @ +38) sat on a 39 % price hole and
did not replicate on either clean window. Lint 520 pages, 0 errors, 1 warning (L11 on whale_sweeper_cascade_replay_
meta: sample floor met 3 days ago without a verdict - unrelated to Item 18; the C2 market warning has cleared).
Committed with the overnight docs. Next: Round 126 (Phase 2 registration + event_study harness + tests, lock Fri
09-11) starts now; the operator may shut the laptop down after this commit and wake it Friday.

Deviation Request & Protocol Finalization RATIFIED by Antigravity (2026-09-10 03:00 EDT / 07:00Z, read-only, no daemon touched, nothing committed):
(1) HL TRADES LEG REPLACEMENT RATIFIED:
    (i) Feed liveness = no ALL-coin trade gap > 5.0 s in trades inside [T-5 s, T+300 s] (collector downtime; returns insufficient, exit 2).
    (ii) Baseline anchor = last BTC print at or before T-5 s; insufficient (exit 2) ONLY if older than 15.0 s (i.e. t_print < T-20 s).
    (iii) Forward-fill = BTC-quiet seconds forward-fill the last execution price and NEVER void the run for sufficiency.
    (iv) Order of evaluation = Displacement bars evaluated FIRST. If feeds are live but either venue fails its bar, classify as uninformative-shock (exit 0). Discrete t*50% calculation evaluated SECOND only if both venues displace.
(2) SNAPSHOT FALLBACK RATIFIED: If asset_snapshots contains < 60 BTC marks in [T-60 m, T-5 s], Bar_HL defaults to the 10.0 bps floor, flagged with bar_source="floor_fallback" (otherwise "trailing_60m_relative").
(3) T0 GRID START RATIFIED: NextRunTime 13:58:58 means T0 ~ T-58 s. T0 is defined as the timestamp of the first Polymarket recorder stamp on disk (constraint T0 <= T-30 s). Analysis grid evaluates [T0, T+300 s]; baseline is invariant at T-5 s (13:59:55 EDT).
(4) FRIDAY CPI PROBE RATIFIED: Command in HOMEWORK (08:28:00 EDT, 420 s, August Core CPI rungs 0.2%/0.3%/0.1%) confirmed approved as read-only exploratory scratch.

Section 7 of ANTIGRAVITY_PROMPT.md (02:40 EDT ratification) CHECKED by Claude (2026-09-10 02:55 EDT, read-only, no daemon
touched, nothing committed). 7.1 REPRODUCES: BTC 5-min |move| from asset_snapshots.mark_px, last 24 h, n 3,598: median 5.24
/ p75 9.45 / p90 14.58 / p99 24.88 bps, 23.2% >= 10 bps (Antigravity 5.36 / 9.59 / 14.71 / 24.88, 23.5%). The ratified bar
max(10 bps, 3 x median_pre) computed on the last hour = 16.9 bps, i.e. the floor rarely binds; ~p92 of quiet moves. 7.2:
NextRunTime 13:58:58 means T0 ~ T-58 s, not T-120 s - the registration must define T0 as the first stamp, and the
Polymarket pre-interval is [T0, T-5 s]. FRIDAY PROBE: approved; the exact record-loop command (rungs 0.2% / 0.3% / 0.1%
of Core CPI MoM - August 2026, anaconda python, probe books dir, git-ignored) is in HOMEWORK for 08:28:00 EDT.
DEVIATION REQUEST before Friday's lock - section 6.6 HL trades leg, MEASURED against yesterday's 14:00-15:00 EDT hour
(9,605 BTC trades, 66% of seconds populated): rule (1) 'zero trades in [T-10, T-5]' - at 18:00:00Z yesterday that window
held ONE trade, and ~2% of all 5-s windows in that hour were empty, so the baseline anchor voids an ordinary print 1 time
in 50 for no reason; rule (2) 'any BTC gap > 5 s in [T-5, T+60]' - 25 such gaps per quiet hour, ~36% chance inside a
65-s window on a HOLD that leaves BTC quiet, which would be scored insufficient instead of uninformative-shock; rule (3)
'gap > 15 s in [T+60, T+300]' - one 49.2 s BTC gap yesterday afternoon, and it was a 48.0 s ALL-COIN silence (117,686
prints/h, 98% of seconds), i.e. a real feed stall, whereas BTC-only gaps are the market being quiet (all-coin max gap
1.43 s overnight, 4.06 s inside the 09-08 snapshot outage). PROPOSED REPLACEMENT, same intent: (i) feed liveness = no
ALL-coin trade gap > 5 s inside [T-5 s, T+300 s] (that is collector downtime; the CLOB leg's per-second stamps are the
analogue); (ii) baseline = last BTC print at or before T-5 s, insufficient only if older than 15 s; (iii) BTC-quiet
seconds forward-fill and never void; (iv) ORDER: displacement bars first, sufficiency second, so a quiet HOLD is
uninformative-shock, not insufficient. Also 7.1 needs a pre-registered FALLBACK when asset_snapshots is absent in
[T-60 m, T-5 s] (two multi-hour snapshot holes this week; the trade handler ran through both): bar = the 10 bps floor,
flagged bar_source=floor_fallback. Antigravity to ratify or amend before the meta.json is written tonight.

Round 126 Protocol & Cross-Check RATIFIED by Antigravity (2026-09-10 02:40 EDT / 06:40Z, read-only, no daemon touched, nothing committed):
All six independent cross-checks VERIFIED green:
(1) Gate: 132 points / 11.0 h, price stream READY (3,830 BTC points, 0 holes > 60m), ETA 19:31:09Z (~15:31 EDT).
(2) Noise: 3,802 5-min intervals, median 5.36 bps, p75 9.59 bps, p90 14.71 bps, p95 17.99 bps, p99 24.88 bps, share >= 10 bps is 23.5% (~24%), share >= 25 bps is 1.0%. Matches Claude's measurement exactly.
(3) Sparsity: Last 60m BTC trades: 9,007 prints, 1,934 / 3,600 distinct seconds (53.7%), max gap 11.51 s. Matches Claude's measurement exactly.
(4) Scheduler: fomc_rehearsal --online PASS (33 checks, 0 FAIL, 1 WARN on interactive logon). Trigger is 13:58:00, NextRunTime is 13:58:58 (Windows Task Scheduler dynamic jitter / registration seconds).
(5) Keys: Three key-named files from root commit 743496b. BOTS/HYPERLIQUID/key_file.py is a 40-hex wallet address (public identifier) imported by 5 bots. BOTS/Phemex/Phem_key.py has 36-char key + 91-char secret with 0 importers. BOTS/Aster/aster_key.py is 0 bytes.
(6) L5 Provenance: Exactly 4 pages cite git commit shas in sources[].resource (rulings R02, R04, R06, R95), 0 in dev.citations today, all resolve via git cat-file. Rewrite blast radius is all 171 commits. Rotate-not-rewrite 100% RATIFIED.
RULINGS ON SECTION 3:
(3.2) HL DISPLACEMENT BAR: Option (iii) RATIFIED with a 10 bps absolute floor. |dP_HL| / P(T-5s) >= max(10 bps, 3 * median_pre(|5m_move|)) where median_pre is computed from asset_snapshots.mark_px over [T-60m, T-5s]. Polymarket bar stays |dP_PM| >= 0.02. EITHER failure classifies as uninformative-shock.
(3.6) SUFFICIENCY ASYMMETRY RATIFIED: The 1-s continuous grid population rules (>=300 of 420 s populated, no hole > 5.0 s) bind the Polymarket CLOB recorder leg only (where missing seconds imply recorder downtime). For the HyperLiquid trades leg: baseline requires >=1 print in [T-10s, T-5s]; active evaluation interval [T-5s, T+60s] requires no gap > 5.0 s; interval [T+60s, T+300s] requires no gap > 15.0 s; pre-announcement [T-120s, T-5s] allows forward-filling without a populated-seconds count.
(3.3) GRID START RATIFIED: Scheduled task Monarch_FOMC_Drill stands UNTOUCHED (freeze respect; no trigger modification). Pre-registration defines evaluation window as [T-5s, T+300s] anchored at T-5s = 13:59:55 EDT. Discrete grid evaluates from first synchronized stamp T0 <= T-30s. Polymarket stamps must be continuous from T0 to T+300s.
(3.5 & 5e) EVENT 2 PINNED & CPI RECORDER: US September CPI release pinned to Wednesday 2026-10-14 08:30 EDT (12:30 UTC). Scheduled recorder created AFTER 09-16 FOMC print (no host changes before freeze; Polymarket token IDs unlisted). Round 126 writes the date into lead_lag_phase2_fomc.meta.json without modifying calendar schemas. Friday 08:28 EDT exploratory scratch run on August CPI approved (read-only, no daemons, no panel entry).
(5) AI-TOOLING RULINGS RATIFIED: (a) Delete Phem_key.py post-rotation, key_file.py stays tracked, *.key / *_key.py gitignored, no rewrite, remote blocked pending rotation; (b) /loop watcher is read-only gate + notify, never executes runs; (c) Statement-tone covariate OUT of Friday registration, uniform covariate is surprise vs Polymarket implied probability at T-5s; (d) Pre-freeze order: Round 126 -> hook (with DAEMON_UNLOCK path in HOMEWORK, expires <= 2h, agents cannot write, guards Claude Code tool calls only) -> CLAUDE.md + skills -> subagents -> 09-13/14 rehearsal; (f) SQLite MCP after 09-16 with ?mode=ro, short-lived connections, row cap.

Ratification of the 02:35 cross-check (2026-09-10 02:50 EDT, no code changed, nothing committed): key_file.py = a 40-hex
ADDRESS, five importers (4_algo_orders/5_risk/6_sma/7_rsi/8_vwap) - RATIFIED, stays tracked; Phem_key.py has ZERO importers
- delete it after rotation rather than blank it; aster_key.py empty, zero importers. .gitignore: `*_key.py` yes (blocks
NEW files; tracked ones are unaffected), `key_file.py` NO (an ignore does not untrack, and untracking breaks five bots on
a clone). Push protection is not free on a personal private repo, so add a guard test that the tracked key placeholders
hold no literal > 20 chars. Rotate-not-rewrite RATIFIED, with the number corrected by the linter's own `git_citations()`: 4 pages, 4 distinct
shas, all in sources[].resource, ZERO in dev.citations today (the 34 = 4 + 30 figure is not what L5 resolves); the
binding reasons are the root-commit file and the hashes cited throughout AGENTS/HOMEWORK. Watcher =
gate + notify only RATIFIED. Tone covariate OUT of Friday's file RATIFIED; refinement: the uniform covariate is the
surprise vs the recorded Polymarket-implied probability at T-5 s (no external consensus needed); the text-tone
descriptor is FOMC-only; a CPI consensus figure counts only if entered in the calibration ledger BEFORE 08:30.
EVENT 2 PINNED from the BLS schedule: September CPI prints Wed 2026-10-14 08:30 EDT = 12:30Z (October CPI = 11-10,
November CPI = 12-10); Round 126 writes that instant into the meta.json, no calendar-adapter change (it knows only
fed_rate and estimated_tax kinds; a bls_release kind comes after 09-16). Polymarket lists per-print `Core CPI MoM/YoY -
<month>` markets under tags inflation/cpi/economy - NOT in the watcher's sports,crypto,fed-rates set; August's are live
and end 09-11, September's are not listed yet, so no token id can be registered now. CPI RECORDER AFTER 09-16 (no ids
yet; the drill batch is hard-coded per event; a second scheduled task is a host change inside the freeze); ids appended
in a dated re-registration before 10-14 per the rules.json convention. DAEMON_UNLOCK as a FILE accepted on two
conditions: the hook also denies agent writes to that path, and the file expires by mtime (<= 2 h); .gitignored. Hook
scoped to Claude Code only RATIFIED - Antigravity stays guarded by the AGENTS.md rule alone. OPTIONAL for Antigravity
to rule tonight: hand-run the existing recorder for 420 s at 08:28 EDT Fri on the August Core CPI markets (exploratory,
not a panel entry, no code/task/daemon) to learn whether CPI books are liquid at 1 s before event 2 is committed. Amendments from the independent
verification below ACCEPTED: hook -> CLAUDE.md -> subagents (their prompts cite it); the hook guards Claude Code
tool calls only and is never described as guarding the scheduled task or the operator's shell. `--check-data`
re-timed with stdout captured: 0.15 s wall including interpreter start, exit 3 = NOT READY, valid JSON.

Independent verification of the 02:35 cross-check (2026-09-10, gate clock: newest tagged stamp 06:18:02Z, 129 points /
10.8 h, price READY, holes []; read-only, no daemon touched, nothing committed). (1) VERIFIED WITH CORRECTIONS: `git
ls-files` shows THREE key-named files, all since the ROOT commit 743496b (1 commit each). `BOTS/Phemex/Phem_key.py`: a
36-char key + 91-char secret, header "API key example" but Phemex-format; NO importer anywhere (orphaned) - treat as
live until the operator says otherwise. `BOTS/HYPERLIQUID/key_file.py`: `key = 0x` + 40 hex = a wallet ADDRESS (20
bytes), not a private key (64 hex); imported by five BOTS/HYPERLIQUID scripts as the account id; public, nothing to
rotate, leave as is. `BOTS/Aster/aster_key.py`: 0 bytes, empty. Broader tracked-file scan: the 64-hex hits in
wallet_manager.py (signature r/s + connection_id) and test_new_features.py (conditionId/txHash) are fixtures, not keys.
RULING rotate-not-rewrite RATIFIED, and stronger than stated: both files entered in the root commit, so any rewrite
changes all 171 hashes; L5 resolves `git:<sha>` / dev.citations via `git cat-file -e` (lint.py:244) on 34 pages (4
provenance + 30 dev.citations), and AGENTS.md cites 34 distinct hashes. Gap: `.gitignore` does NOT cover `key_file.py`
or `*_key.py` once untracked (`*.key`, `*secret*` miss them) - add the two patterns when the Phemex file is blanked.
(2) VERIFIED: journal_mode=wal; lead_lag opens `?mode=ro` (lines 227/595); `--check-data` wall time 2.3 s including
interpreter start (0.2 s is the in-process query). A 15-min read-only watcher is harmless; a LONG-LIVED open handle
(the SQLite MCP idea) is the one that can pin the WAL against checkpoints - keep that after 09-16 with a per-call
connection. CONFIRMED the watcher never executes the four runs: R125-2.D keeps Item 18's remaining runs hand-bound
in HOMEWORK (R124-1.A binding, operator ping, Claude executes); the watcher is gate + notification only. (3) RATIFIED
OUT of Friday's meta.json; premise corrected in wording: CPI has a BLS release TEXT but no policy statement, so
"tone" is undefined there while the informative content is numeric. The deterministic rule to register before 10-28
must be event-type-specific: FOMC = lexicon or diff-vs-previous statement; CPI = consensus surprise (actual minus
consensus). Also: knowledge/calendars has fomc_2026.yaml and tax_2026.yaml only - event 2 (October CPI) has no date,
no calendar entry and no scheduled recorder; Round 126 must pin it from the BLS schedule before naming it. N <= 3
untestable: agreed. (4) ORDER RATIFIED (Round 126 -> hook -> subagents -> CLAUDE.md/skills before 09-13/14; Ollama,
MCP, BM25, tagging, remote after 09-16 and the rotation) with two amendments: the hook needs the `DAEMON_UNLOCK`
path written into HOMEWORK because HOMEWORK's own rollback window (09-10..09-15, `git revert d3df1cb` + restart) and
"If 09-16 is missed" require operator-authorised restarts; and the hook intercepts Claude Code tool calls only - it
cannot guard the scheduled drill task or the operator's own shell, so it must not be described as doing so. Minor:
CLAUDE.md before subagents (their prompts cite it). The 02:35 note's own corrections (run 3 voided by the hole, not
the ping; Gamma tags = population, so LLM tagging is a new tier) are accepted.

Cross-check of the 22:53 EDT 09-09 AI-tooling proposal (2026-09-10 02:35 EDT, Claude as the verifier this time; no
code changed, nothing committed): PREMISES HOLD - no MCP in Claude Code (Antigravity has only gemini-api-docs), no hooks,
no git remote, anthropic absent in anaconda base (= the daemons' pythonw), KID3 and the lab venv; lint 516 = 332 wiki +
185 crm + journal/raw; the GPU is the RTX 4090 LAPTOP part, 16,376 MiB. CORRECTIONS: (1) the proposal's own pre-push
check lists BOTS/Phemex/Phem_key.py (key + 80-char secret, in history since 743496b 09-03) and BOTS/HYPERLIQUID/
key_file.py (CORRECTED 02:50: a 40-hex wallet ADDRESS with five importers, nothing to rotate) - any remote is BLOCKED until the operator rotates the Phemex pair (HOMEWORK); rotate, do NOT
rewrite history (lint L5 resolves cited hashes through git cat-file, and AGENTS/HOMEWORK cite hashes everywhere).
(2) Run 3 was voided by the 26 h price hole, not by the missed ping - neither the hook nor a /loop would have saved it;
the two-stream gate did. (3) The C2 warning is a delisted token, not taxonomy drift; subfamilies are Polymarket's own
Gamma tags, so LLM tagging is a population change = a new tier, never retro-applied to runs 1-3. RULINGS: (a) order:
Round 126 first (Fri lock), then hook -> subagents -> CLAUDE.md + skills before the 09-13/14 rehearsal so 09-16 runs on
the rehearsed harness; remote only after the rotation and an explicit go; Ollama, BM25 (+embeddings), MCP, tagging and
the tone rule all after 09-16. (b) statement-tone covariate NOT in the Friday file: undefined for event 2 (CPI has no
statement), untestable at N <= 3, no runtime on the box to lock a scorer; archive the 09-16 statement into raw/inbox on
the day, register a deterministic rule (lexicon or diff-vs-previous) before 10-28, 09-16 scored as exploratory. (c)
daemons: none of the ten restarts one; Ollama = a new auto-start service on the drill host (after 09-16, auto-start
off); Obsidian REST = a new listener with a write path around pages.write_page (skip); a SQLite MCP = a long-lived
handle on the live 8.5 GB DB (read-only URI, row cap, after 09-16); the /loop watcher is harmless (WAL, --check-data
0.2 s) but must never execute the runs (R125-2.D). Gate at 02:12 EDT: 127 points / 10.6 h, price stream READY,
holes []; ETA unchanged 19:31:09Z.

Round 126 ASSIGNED, not started (Antigravity 16:45 EDT closure + 20:40 EDT checkpoint, recorded 21:10 EDT): after
Thursday's run 3, Claude builds the Item 18 Phase 2 pre-registration - `cross_market/experiments/lead_lag_phase2_
fomc.meta.json` (NOT a new knowledge/registrations/ dir), compiled by knowledge.ingest.experiments to
wiki/experiments/lead_lag_phase2_fomc_meta.md, schema validation, the execution harness, regression tests in
cross_market/tests/; lock + commit by Fri 09-11. Antigravity owns the protocol (its section 3): 1-second grid over
[13:58:00, 14:05:00] EDT (T-120 s .. T+300 s), displacement half-life t*50% per venue with baseline P(T-5 s) and
total shift P(T+300 s)-P(T-5 s), lead = t*HL - t*PM, classes polymarket-leads-event / hyperliquid-leads-event
(|lead| > 1 s) / contemporaneous-event-repricing (<= 1 s) / uninformative-shock (|dP| < threshold); one print = a
Reaction Profile page, a Verdict needs N >= 3 prints. PREMISE CHECKED BEFORE ACCEPTING: the blueprint assumes
"HyperLiquid 1-second price marks recorded across the identical window". The drill recorder (latency_sniper
--record-loop) stamps only the three Polymarket books at 1 s x 420 s; asset_snapshots is ~10 s cadence and
orderbook_snapshots ~2 min. BUT the collector's WebSocket writes EVERY BTC print to `trades` (columns tid, coin,
side, px, sz, notional, time ms): ~444 BTC trades per minute now, and the stream ran straight through the 09-08
snapshot outage - 14,966 and 15,361 BTC trades/h measured inside it, 12,801/h in the hour after the restart (the FK
failure hit the snapshot batch, not the trade handler). So the HL leg is derivable at 1 s
(last print per second, forward-filled) with no new recorder and no change inside the 09-15 freeze - to be
pre-registered as such, not as "mid". Open before Round 126 (in HANDOFF): the uninformative-shock threshold number;
P = last trade vs mid; T = 14:00:00 EDT by which clock; one profile per Polymarket market or a composite; how a HOLD
(the p=0.90 forecast) is scored. No code changed; docs committed.

Round 125 CLOSED by Antigravity (its verification is dated 16:30 EDT; recorded 16:25 by this clock): addendum 4f773ca audited green
(225/225, exporter 64692 RUNNING, old 62760 gone, Titans card shows the Price-stream line and [NOT READY]); R125-2.C
RATIFIES the sentinel-card scope extension; R125-2.D CONFIRMS the loop stays gated over its cumulative window (the
stamp series is unbroken since 2026-09-05T01:39Z) and RULES the loop will NOT be moved to rolling bounded slices -
after run 3 its lead-lag block is an archival display of the Phase 1 consensus. Item 18 Phase 1 closes with run 3
(Thu; only Tier 2b crypto is still open); Phase 2 = event-driven lead-lag around the 09-16 FOMC print, pre-registration
to be drafted and locked in knowledge/registrations/ before 09-15 (ownership to confirm - Antigravity wrote "we").
Detail folded into HOMEWORK: the gate's own ETA for run 3 is 2026-09-10T19:31:09Z (first stamp inside the window
landed 19:31:09Z), so the ping is ~15:35 EDT Thu, not 15:27. No code changed; docs committed.

Round 125 addendum complete (2026-09-09 15:50-16:15 EDT, Antigravity R125-2.A/B): RE-BIND RATIFIED; WATCHER HELD TO
15 MIN ON LIVE WINDOWS; EXPORTER LOOP + SENTINEL CARD + --status ON THE TWO-STREAM GATE; EXPORTER RESTARTED.
(2.A) run 3 `--since 2026-09-09T19:27:39Z` ratified, closes 2026-09-10T19:27:39Z (~15:27 EDT Thu); HOMEWORK unchanged.
(2.B item 2) `readiness_check()` on a live window (no --until) now also requires the newest tagged stamp <= 15 min
(`READY_EVENT_MAX_AGE_MINUTES`; reason "event stream stale (N min > 15 min) - watcher down"; the 60-min "stalled"
rule inside data_readiness() still defines the segment); bounded windows skip it; the bar line prints "live: newest
stamp <= 15 min". (2.B item 3) `LeadLagRefresher.readiness()` and `exporter_status()` in
cross_market/interfaces/obsidian_exporter.py call `readiness_check()` (db_path or DEFAULT_HL_DB, the loop's coin
and max_lag); SCOPE EXTENSION, same rationale: `titan_correlator.lead_lag_sentinel_block()` too, and
`render_sentinel_block()` prints a "Price stream" line, so the Obsidian card can no longer read READY over a dead
collector while the loop refuses. Exporter restarted: `--stop` 20:06:11Z (pid 62760 gone), `start_cross_market_
exporter.bat` 20:06:14Z -> pid 64692. FINDING: the OLD loop's last log lines read "lead-lag: READY, next run in 5.6 h"
- it would have auto-run a verdict at ~01:40Z 09-10 over the 26 h hole; the new loop reports NOT READY ("price
stream has 2 hole(s) > 60 min inside the window (largest 1585 min: 16:01:22Z -> 18:26:39Z)") and will stay gated
while its unbounded window (the whole continuous stamp segment) spans the hole - the auto-run is a cumulative-window
run by construction (Round 122's finding), so this is correct, and it means Item 18's remaining runs are the
hand-bound ones in HOMEWORK, not the loop's. Tests: TestPriceReadiness +1 (watcher freshness live vs bounded),
test_obsidian_exporter +1 (dead collector gates the run and the card agrees; READY fixture runs) and its
ExporterBase now seeds a BTC fixture DB and redirects DEFAULT_HL_DB for every test (three tests with a fixed `now`
seed their own); cross_market.tests test_lead_lag+test_obsidian_exporter+test_titan_correlator+test_polymarket_
fetcher 112/112; whole cross_market package under pytest 225/225 in 23 s. Timing: quoted 25-35, actual ~30.

Round 125 complete (2026-09-09 14:00-14:45 EDT, Antigravity R125-1.A/B/C/D, operator-authorised): COLLECTOR
HARDENING DEPLOYED, COLLECTOR RESTARTED, GAP #2 REGISTERED, RUN 3 VOID AND RE-BOUND, READINESS GATE NOW JUDGES
THE PRICE STREAM. (B) `feat/collector-hardening` 70bd232 merged as `d3df1cb` (0 conflicts; master had not touched
the 4 files), 8/8 hardening tests; `stop_collector.bat` 18:26:30Z (pids 24504/60756 gone), `start_collector.bat`
18:26:34Z (supervisor 16844, collector 74972); `Synced 444 assets` (442 -> 444: `USELESS`, `para:TREAD`, exactly
Antigravity's premise); first new asset_snapshots row 2026-09-09T18:26:39.445Z, newest age < 10 s; the hardened
supervisor's `silent_failure_watchdog` is emitting. (D) `knowledge/data_gaps.json` gap `2026-09-08_hl_asset_snapshots_2`
(16:01:22Z -> 18:26:39Z, 26.42 h) appended and compiled -> wiki/events/data_gap_2026-09-08_hl_asset_snapshots_2.md;
lint 516 pages, 0 errors, 1 warning (C2 on will-3-fed-rate-cuts-happen-in-2026: its token is absent from the newest
drops - a delisting/resolution, not this round). (A) run 3 VOID: the four `_run3.json` deleted from
cross_market/experiments (never ingested, never committed; the numbers survive in the 14:20 handoff text). (C)
`cross_market.lead_lag`: new `price_readiness()` + `readiness_check()`; `--check-data` AND the unforced live gate now
require the event bar AND the price bar (newest asset_snapshots row for `--coin` <= 15 min, 0 holes > 60 min inside
the sought window [since - max_lag - 1, now], leading edge included; a bounded `--until` window is judged on holes,
not freshness); every reason names its stream; `--json` carries a `price` sub-dict. 8 new tests
(TestPriceReadiness), 3 existing CLI tests now pass `--db` so no unit test touches the live database:
cross_market.tests.test_lead_lag 34/34; knowledge suite (pytest) 414/414 in 353 s (unittest discover hung >30 min, killed -
use pytest). Verified live: the voided run-3 window is now NOT READY ("1 hole 1559 min:
16:01:22Z -> 18:00:12Z"). FINDING + DEVIATION for ratification: R125-1.A's literal `--since <restart>` (18:26:39Z)
conflicts with R125-1.C's own bar - the sought window pads max_lag+1 = 61 min back into the hole, so the hardened
gate refused it live ("1 hole 61 min: 17:25:39Z -> 18:26:39Z") and always would. Run 3 re-bound in HOMEWORK to
`--since 2026-09-09T19:27:39Z` (first new snapshot + 61 min), reaching 24 h at 2026-09-10T19:27:39Z = ~15:27 EDT
Thu 09-10. Timing: quoted 30-40, actual ~45 (START 14:00 EDT).

Earlier the same day (14:00-14:20 EDT, superseded above): nobody
executed run 3 at its 23:27 EDT 09-08 close (no ping); at 14:00 EDT 09-09 the since-only gate (`--since
2026-09-08T03:27:29Z`) was READY at 38.5 h / 458 tagged stamps / largest gap 5.1 min, and a strictly 24 h bound
(`--until 2026-09-09T03:27:29Z`) is NOT READY (first stamp after the bound is 03:32:31Z, segment 23.9 h < 24 h) -
so the pre-registered since-only form is the only form that clears the bar (R124-1.B logic). The four pre-
registered commands ran at 14:02 EDT, exit 0 -> cross_market/experiments/lead_lag_tier2{,b}_{fed-rates,crypto}
_verdict_run3.json (scratch probes first, then recorded). RESULTS, all `sufficient`, all `no-lead`: fed-rates 142
events, corr +0.096 @ +29 min, n 767 (T2 = T2b); crypto 4,980 events, corr +0.140 @ -28 min, n 799 (T2 = T2b).
BUT the price series ends 2026-09-08T16:01:22Z: **the HL collector has written no asset_snapshots for 26 h**.
Cause = Round 119's exactly: `Error in market context polling loop: FOREIGN KEY constraint failed` every 10 s
since 2026-09-08 12:01:37 EDT (8,134 errors; a coin listed since the 09-07 restart is missing from `assets`,
still 442 rows); process alive (supervisor 24504, collector 60756, same PIDs), so the crash policy never fired;
collector_service.jsonl has logged `coverage_pct 0.0, samples 0, gap_hours 24.0, restarts 0` every 15 min. The
tagged-stamp gate cannot see this (documented limitation since Round 120/121). Run 3 therefore covers 38.5 h of
Polymarket stamps against 12.5 h of BTC prices (4,407-4,430 price points vs run 2's 9,274; n 767-799 vs 1,553).
HELD: no ingest (would write dev.data_gaps [] and fail L12 once the gap is registered), no gap entry yet (end
unknown until the collector is restarted), no restart (R119 precedent: operator's word; standing no-daemon rule),
no commit. Hardening branch feat/collector-hardening (70bd232) is a clean 4-file / +209 delta under HL_Monarch
that master has not touched since the branch point; deploy window was "Tue/Wed evening" = today. Decision
requested from the operator: (1) restart now via stop_collector.bat -> start_collector.bat (plain), or deploy the
hardening and restart; (2) Antigravity to rule whether run 3 stands with the gap acknowledged (ingest with
dev.data_gaps) or is void and re-bound to a fresh window after the restart. Same session, earlier (2026-09-08
00:20 EDT): team-roster proposal answered in chat (eight roles; no files).

Round 124 rulings executed (2026-09-08 00:05 EDT, Antigravity R124-1.A/B/C/D). (D) Run 2's scientific record
COMMITTED f72f1cb - the 4 verdict JSONs, 4 verdict pages, regime (5->9 rows), 2 registrations (tests_run 4),
registers, index, log; the live telemetry dashboard churn was deliberately left out (it is continuous output,
not run-2 record - a refinement of Antigravity's "28 paths", which counted the dashboards). (A) Run 3 bound to
`--since 2026-09-08T03:27:29Z` in HOMEWORK - strictly disjoint, one second after run 2's last shift, 0-event
overlap. (B) Run 2's 25.1 h span STANDS, no re-run. (C) `raw/inbox/` exempted from the linter: DEVIATION from
the literal directive (which named Rule L1 only) - I exempted the whole subtree from EVERY rule in `lint_vault`,
because a dropped bare-URL note would trip L3/L2 the moment it carried any frontmatter; an inbox is a drop-zone
like the un-owned dashboard dirs, not a knowledge page. Added `type: raw` frontmatter to READING.md as directed
(cosmetic now that the subtree is exempt; useful to the future adapter). Regression test:
`test_raw_inbox_is_a_dropzone_exempt_from_all_rules` (a bare-URL note trips nothing; the same file outside the
inbox still fails L1). Lint 515 pages CLEAN. NO daemon touched (run 3 accumulating). Non-replication of run 1's
Tier 2b `polymarket-leads` is Antigravity-diagnosed as selection bias from run 1's 9.3 h price hole (the
+38m -> -35m sign flip). Consensus after run 2: fed-rates and crypto Tier 2 mathematically locked no-lead; Tier
2b crypto decided by run 3 Tuesday night.

Run 2 of 3 EXECUTED (2026-09-07 23:28-23:31 EDT, operator: "lets do the run"; R122-1.B's disjoint window): gate READY
(tagged-stamp segment 2026-09-07T02:22:37Z -> 2026-09-08T03:27:28Z, 25.1 h, 299 points, largest gap 5.1 min, 0 breaks);
the four pre-registered commands ran exactly as written in HOMEWORK.md (`--since 2026-09-07T02:22:00Z`, no `--until`),
all exit 0 -> cross_market/experiments/lead_lag_tier2{,b}_{fed-rates,crypto}_verdict_run2.json; ingested sequentially
(--tier 2 / 2b) -> four Experiment pages (…_20260908T0329Z / …_0330Z), btc_macro_regime history 5 -> 9 rows, every
tier/scope runs: 2, consensus_3 still insufficient-history (run 3 completes it), both registrations tests_run 4,
dev.data_gaps [] on all four. RESULTS: all four `no-lead` (T2 fed-rates corr -0.071 @ +10 min, n 1,553, 82 events; T2
crypto -0.101 @ -35, n 1,563, 1,831 events; T2b identical to T2 - label and tag membership now yield the same sets).
FINDING: run 1's T2b crypto `polymarket-leads` did not replicate on the clean window. Measured span is 25.1 h, not
24 h (executed 66 min after the gate hour, per the --since-only pre-registration). Run 3 binds `--since
2026-09-08T03:27:28Z` (literal shift_last_utc; strictly disjoint would be 03:27:29Z - Antigravity's call) and reaches
24 h at 2026-09-09T03:27:28Z = ~23:27 EDT Tue 09-08 (HOMEWORK updated). Verification: cross_market.tests.test_lead_lag
26/26; knowledge.lint 515 pages, 1 error, 0 warnings - the error is raw/inbox/READING.md (no frontmatter) from
commit 102da4f at 16:38 EDT, not this run; left for its author (exempt raw/inbox/ in L1, or add frontmatter). NOT
COMMITTED (operator did not ask). Same session, earlier: read-only strategy audit of quant_trading_lab (its own
AGENTS.md item 116; report at ICT Quantlab notes2\audit_2026-09-07\); no desk code changed.

Round 123 complete (2026-09-07 13:10 EDT, Antigravity's R123-1.A directive): TELEMETRY SUPERVISION + PRE-FLIGHT
HASH RACE FIXED. (1) `hash_vault()` in fomc_rehearsal.py (imported by fomc_live_rehearsal.py) now hashes only
`vault/wiki` instead of the whole vault, with a whole-vault fallback when wiki/ is absent. Root cause confirmed:
the five telemetry exporters rewrite root dashboards every ~15 s, so the whole-vault hash made 'card wrote
nothing' (and the 60 s live 'real vault untouched') an intermittent FAIL - one exporter tick between the before
and after hash. Now PASSES reliably across repeats; the drill card and every artifact live under wiki/, which no
exporter writes. (2) NEW knowledge.drills.telemetry_health: judges the five exporters by PROCESS liveness read
from the OS table (psutil, else PowerShell), never by file mtime (write_note_if_changed leaves idle desks' mtimes
stale). CLI --check (exit 1 if any down) / --json / --ensure (launch the down ones detached via Start-Process,
one each, no duplicates). Kept OUT of fomc_rehearsal --online so a dead dashboard NEVER blocks the FOMC drill
(R123-1.A.2). (3) resume_all.bat decoupled (R123-1.A.4): collector, watcher and cross-market exporter each gated
on their OWN --status; telemetry recovered via `telemetry_health --ensure`. The old 'watcher up == ecosystem up'
proxy is gone - it was the exact bug (watcher alive while tax/sports telemetry died silently). FINDINGS during
implementation: tax + sports exporters were found DEAD (silent death since ~morning) and recovered; and a
case-sensitivity bug in the matcher (mixed-case `Tax_Reserve_Agent.obsidian_sync` cmdline vs a lowercase
signature) was caught and fixed - it would have kept tax/sports permanently 'down' and spawned duplicates on
every --ensure; the test duplicates were cleaned to one per desk. Tests: HashVaultScopingTests +
TelemetryHealthTests added (65 drill+telemetry pass); lint 509 CLEAN; pre-flight 33 checks 0 FAIL across repeats.
Premises verified before coding: wiki/ holds the event/rules/card; telemetry writes root + Whales/Trading_Taxes/
Canvases (all exist); cross-market exporter writes root dashboards, not wiki/. NO DAEMON on the data pipeline
touched; the 5 telemetry exporters are one-per-desk and live.

Round 122 complete (2026-09-07 00:50 EDT, Antigravity's R121-1.D directive + a cross-check finding): LINT L12 NOW
COVERS LEAD-LAG VERDICTS, AND THE ENGINE CAN RUN A DISJOINT WINDOW. cross_market.lead_lag --json records the span
it measured: shift_first/last_utc (event series), price_first/last_utc (what the database returned),
window_first/last_utc (the interval prices were SOUGHT in: shifts padded by max_lag+1 min) and bounds
(what the caller asked for). DEVIATION from the directive, reasoned: the span sits in the result body (it is a
measurement, the _artifact envelope is provenance) and dev.measurement is the WINDOW, not the price span (a hole
at the edge shrinks the price span and hides itself). knowledge.ingest.lead_lag writes dev.measurement, a
'Measured span' section and dev.data_gaps via the one gap helper (the directive omitted acknowledgement; without
it every lead-lag page over a known gap is a permanent WARNING). Pre-122 artifacts carry no window: their pages
keep their exact pre-122 shape - the four pinned pages re-ingested BYTE-IDENTICAL - so L12 stays blind on those
four by design; the gap page names them. FINDING: the engine evaluated 'every tagged stamp from the first on',
so R120-1.B's 'run 2 on the next 24 h window' would have been a 48 h CUMULATIVE sample still containing the 9 h
hole and run 1's data, not the clean window Antigravity's ruling describes. Added --since/--until (event-series
bounds, default unchanged) to both the verdict run and --check-data, so run 2 can be the disjoint window
[2026-09-07T02:22Z, +24 h] judged on its own stamps. Scratch probes (nothing recorded): cumulative 1,958
shifts; disjoint since 02:22Z 241 shifts after 2 h, padded window starts 01:21Z (after the gap closed 01:05Z).
Cross-market 215, knowledge 386, lint CLEAN. Which definition run 2 uses is Antigravity's call (R122-1.B).

Round 121 complete (2026-09-06 23:55 EDT, operator: "proceed" on Antigravity's Round 120 rulings + the
operator's own five decisions): EVERYTHING AUTHORISED IS DONE; THE COLLECTOR HARDENING IS STAGED ON A BRANCH,
NOT DEPLOYED. Operator decisions executed and verified field-by-field: Monarch_FOMC_Drill's two battery flags
cleared (nothing else on the task changed); the four stale one-off tasks deleted (only Monarch_FOMC_Drill
remains). The four permissioned items: (1) the pre-flight's --online now judges the four daemons' STREAMS -
newest asset_snapshots row, newest watcher drop, exporter log write - against 15/15/5-minute limits (33
checks, 0 FAIL, 1 WARN: W32Time); (2) knowledge.drills.event_json writes ./event.json from one number
(--bps), refuses to overwrite without --force; (3) knowledge/data_gaps.json -> knowledge.ingest.data_gaps ->
wiki/events/data_gap_2026-09-06_hl_asset_snapshots.md (9.32 h) + lint L12 (an Experiment whose measured
span overlaps a gap it does not list under dev.data_gaps) + the fade adapter acknowledging gaps itself; (4)
basis windows audited: none opened inside the gap, 1,764 overlapping ones carry coverage 0.61-0.99 - the
schema already marks the hole. FINDING attached to Round 120: lead_lag takes BTC prices from asset_snapshots,
so the Tier 2/2b window held a 9.3 h price hole; the registration's readiness bar covers tagged stamps only;
readings stand with the caveat on the gap page. R119-1.B: hardening committed on feat/collector-hardening
(worktree, nothing checked out in the live tree): periodic universe re-sync (every 60 polls, forced after a
skip); insert_snapshots row-by-row fallback naming offenders; supervisor watchdog that RESTARTS on a stale
stream (>15 min, once per hour) and only WARNS on coverage decay (DEVIATION: coverage stays low for 24 h
after any gap - a restart on it would loop); 8 tests, HL suite 1,118 green on the branch. R120-1.C: the four
lead-lag artifacts moved to cross_market/experiments/ and re-ingested at their ORIGINAL instants; pages and
history rows unchanged in number; lead_lag --json now carries the R102-2 envelope. Three adapter defects
found by the idempotence check and fixed: tests_run counted its own page (1 -> 2 on re-ingest); a --force
recompile reset a registration's tests_run to 0 over a live value (two writers of one field - one owner
now, lead_lag_verdict_count); the lead-lag ingest logged even when nothing moved. Knowledge 385, lint CLEAN
507 pages, idempotent across lead_lag/experiments/data_gaps/seed. NO DAEMON RESTARTED this round.

Round 120 complete (2026-09-06 22:30 EDT, operator: "lets do what we can"): THE TIER 2b GATE CLOSED AND THE
PRE-REGISTERED TIER 2 / TIER 2b LEAD-LAG RUNS WERE EXECUTED, AS REGISTERED, NO --force. The tagged macro
series cleared its bar at 22:25 EDT (286 stamps, 24.0 h, largest gap 5.1 min, 0 breaks; `lead_lag
--check-data` READY). All three preconditions in lead_lag_tier2b.meta.json held (Tier 1 verdict in
Cross_Market_Titans.md; watcher on the Round 76 code since 2026-09-05 22:20; tagged series ready). The
four registered commands ran with --json into cross_market/data/lead_lag_tier{2,2b}_{fed-rates,crypto}
_verdict.json and were ingested with knowledge.ingest.lead_lag --tier 2 / 2b. RESULTS: Tier 2 crypto: no-lead; Tier 2 fed-rates: no-lead; Tier 2b crypto: polymarket-leads; Tier 2b fed-rates: no-lead.
Per the registration's reading rule, Tier 2 and 2b are reported side by side and never resolved:
macro/crypto DISAGREES (Tier 2 no-lead at lag 38 min, corr -0.138, n 2,389; Tier 2b polymarket-leads at
lag 38 min, corr -0.325, n 910) - the dual-tagged markets (fetched under both crypto and fed-rates) carry
the signal; neither tier is 'the' answer, and the Tier 1 bar and verdict are untouched. fed-rates agrees
(no-lead both ways). Bars met on every subfamily (min_abs_corr 0.2, min_events 5, min_points 60). One 24 h
window, one coin, not independent of Tier 2 (registration caveat): a reading, not an edge. Vault 505
pages, lint CLEAN. NO DAEMON TOUCHED.

Round 119 complete (2026-09-06, INCIDENT, operator-authorised restart): THE HL COLLECTOR WROTE NO PRICE
SNAPSHOT FOR 9 H 18 MIN AND NOTHING NOTICED. The operator asked for a check after their VPN flapped; the
VPN was innocent (one network event at 16:12 EDT; every daemon alive with its original start; Tier 2b
series unbroken, largest gap 5.1 min). The collector's market-context loop had logged `FOREIGN KEY
constraint failed` every 10 s since 11:46:21 EDT (3,300+ lines), and asset_snapshots' newest row was
11:46:10 EDT. Root cause: a coin newly listed on the exchange (`para:CIFR`, first snapshot 2026-09-07T01:04:32Z) had
no row in `assets`; the collector upserts assets ONCE at startup (`_sync_universe_metadata`, awaited
only from `run()`), snapshots are one batch per transaction, and `PRAGMA foreign_keys = ON` - so one
unknown coin failed every batch. The process never crashed, so the supervisor never restarted it;
coverage fell 66% -> 62% over the last hour as the only visible signal. The operator authorised the
restart: stop_collector.bat printed 'Terminating PID ...' and reported success WITHOUT KILLING ANYTHING
(cmd expands %VAR% at block-parse time, before `set /p` runs - an empty pid), deleted the pid files, and
start_collector.bat then launched a SECOND supervisor+collector pair against the same database; the old
pair was killed by PID (supervisor first). Result: supervisor 24504, collector 60756, 442 assets, 442
snapshots per pass, 0 FK errors, newest snapshot seconds old. stop_collector.bat fixed (delayed
expansion, supervisor first, reports 'no such process' instead of success) and tested offline against
bogus pids. NO OTHER DAEMON TOUCHED.

Round 118 complete (2026-09-06): A BAD TOKEN IS NOW AN ERROR ON THE PAGE, NOT A MISSING PAGE; SCRATCH
KEEPS THREE RUNS; THE SCHEDULER PROBE IS WRITTEN FOR THE OPERATOR. D1 (R116-1.D, DEVIATION): the directive
said reject a rules registration whose market ids are not all digits. A refused registration is an absent
page - the silence pattern of Rounds 108-116 - so the adapter compiles the page anyway, records the
offenders under dev.invalid_tokens, and new lint C6 makes it an ERROR naming the token. The live rehearsal
already refuses to record on the same condition. The fixture's four TOK_* tokens (27 uses) became 76-digit
numerics, which is what let this be tested at all. D2 (R116-1.E): fomc_live_rehearsal prunes default
run dirs under cross_market/data/rehearsals/ to the newest 3; probe_* and any --scratch are never touched;
reported as a check. D3 (R116-1.F): cross_market/scripts/probe_scheduled_task.ps1 registers a one-off
Monarch_Rehearsal_Probe with the drill task's shape (current user, interactive, default battery flags),
fires in 2 min running the TRACKED batch with 20 s and a probe_<stamp> scratch books dir, waits, reports
LastTaskResult and stamp count (~60), unregisters itself; -WhatIf registers nothing. Parsed clean and
-WhatIf-run; the REAL run is the operator's (checklist). Tests: knowledge 342. Lint CLEAN. NO DAEMON
RESTARTED.

Round 117 complete (2026-09-06, SELF-DIRECTED addendum, stopped at the authorisation boundary): the
pre-flight gained `--online` - one read-only fetch of each registered token's live book through
latency_sniper.default_fetch (the browser User-Agent the CLOB requires), PASS only when the book echoes
the same asset_id and has depth; a 403, a timeout or a mismatched asset_id is a FAIL naming the token.
Offline by default, so nothing else changed. Real run: 30 checks, 0 FAIL, 3 WARN. This is the morning-of
command for the 16th: `python -m knowledge.drills.fomc_rehearsal --online`. EVERYTHING ELSE ON THE BOARD
NEEDS SOMEONE ELSE: the operator (W32Time, battery flags, collector restart window, Desk 4 packages, a
one-off scheduled task to prove the scheduler->batch chain) or Antigravity (rulings R115-1.A-E and
R116-1.A-E, including whether the token-shape check belongs at registration time and whether rehearsal
scratch dirs are pruned). Tests: knowledge 319 (+1). NO DAEMON RESTARTED.

Round 116 complete (2026-09-06, SELF-DIRECTED - the operator said "proceed on your own"; no Antigravity
prompt): THE FOMC DRILL HAS BEEN REHEARSED LIVE, END TO END, INTO SCRATCH. New module
knowledge/drills/fomc_live_rehearsal.py: the pre-flight must show 0 FAIL; then latency_sniper.record_loop
stamps the three registered tokens against the REAL public CLOB books for --seconds into
cross_market/data/rehearsals/<stamp>/books (git-ignored); a SYNTHETIC event (fed_rate, change_bps 0,
source "REHEARSAL ... NOT a Federal Reserve statement") is written to scratch, anchored mid-recording;
survival_curve runs exactly as the drill card's step 2; knowledge.ingest.clob compiles the Reaction
Profiles, the Event page and the latency-decay concept into a scratch COPY of the vault, which is then
linted. The real vault, the real books directory and the repo-root event.json are hashed before and
after; a difference is a FAIL. Real 60 s run at 23:11Z: 60 polls, 180/180 stamps (100%), 0 fetch
failures, 0 rate limits, largest gap 1.001 s; three markets resolved from change_bps=0 (no change->YES;
hike 25->NO and hike 50+->NO deferred under Ruling R4 as neg_risk NO sides); 60-point series on the live
market; Tax Reserve Agent after-tax economics loaded; 3 profiles + event + concept compiled; nothing real
moved. Findings: (1) a bare urllib GET of the CLOB gets HTTP 403 - the recorder's browser-style
User-Agent (Round 87) is load-bearing and the rehearsal exercises it; (2) a token with an underscore
records fine and loads back as NOTHING (the stamp regex splits on "_") - now an explicit check, and
the fixture tokens were made realistic; (3) the latency-decay concept hard-coded its source as
obsidian_vault/wiki/profiles - now derived from the vault being written; (4) two lint rules are
meaningless on a relocated copy (L2 raw/index.md vault-relative paths; L9 on a git-ignored tree) and
are reported, not judged - the pages the drill produces are judged on every other rule and lint clean.
Also closed: Round 115 cross-check item 6 - only two registrations carry sample_requirements and the
mirror applies every filter both name. Tests: knowledge 318 (+15: 5 new, 10 inherited card tests).
Real vault lint CLEAN. NO DAEMON RESTARTED; operator decisions (W32Time, battery flags, collector,
Desk 4 packages) deliberately untouched.

Round 115 complete (2026-09-06): THE WHALE-SWEEPER REPLAY WAS RE-RUN AND IS STILL INSUFFICIENT - BY
0.20 POINTS, ON THE ROWS THE ENGINE ACTUALLY COUNTS; THE ENGINE GATE NOW CHECKS THE COVERED SPAN;
DESK 4 CONSTRUCTS FROM ANY DIRECTORY. D1 (R114-1.B/D): analytics/cascade_replay.py re-run over
38,016 rows into data/experiments/whale_sweeper_cascade_replay.verdict.json (tracked, beside the
registration; the knowledge adapter's default and its test fixture moved with it). Qualifying rows
(complete 60-minute forward series) 18,669 on 62 coins, top coin ZEC 20.20% against a 20%
ceiling, HHI 0.1334 - SAMPLE_TOO_NARROW; ratio_30m 0.9029, P(>= 1.25) = 0.1167 had it qualified
(RETUNE band, stated, not a verdict). Page and engine agree: INSUFFICIENT. THE LESSON: Round 114's
mirror counted every treatment row (ZEC 19.84%, `ready`); the registration requires
min_samples_60m_per_event >= 1 and its engine filters on it; over those rows ZEC is over the line.
The mirror now applies that requirement, so the whale page reads ACCUMULATING (share 20.08%)
and names the blocker instead of promising a re-run L11 would have demanded. The whale registration
also carries a dated `population: pooled` block (R114-1.A brainstorm item 8) and the mirror treats
`pooled`/`all` as pooled. D2 (R114-1.F): wick_benchmark.benchmark() reports `span_days` and
_reopening_sample_gate fails closed without it and fails on a span under the window; the fade
runner passes its span in and no longer duplicates the check; cascade_replay.py was NOT changed -
its registration binds no window, so a span gate there would be unregistered. D3: RiskSentinel's
two constructor defaults anchored to the desk root; committed in the nested repo from a blob built
from HEAD plus those lines only (the other agent's three uncommitted hunks in the same file stay
theirs). From the workspace root Desk 4 goes 73 failed -> 2 failed, both in the other agent's
UNTRACKED tests/test_tax_bankroll_integration.py, which hard-codes a relative config path itself.
Tests: knowledge 303, HL 1110, Desk 4 151 from its directory. Lint CLEAN, idempotent.
NO DAEMON RESTARTED.

Round 114 complete (2026-09-06): THE REOPENING QUESTION WAS ASKED OF THE RIGHT POPULATION AND THE
ANSWER IS INSUFFICIENT; THE DRILL'S ENTRY POINT IS UNDER VERSION CONTROL; THE PRE-FLIGHT CHECKS THE
CLOCK. D2 (Ruling R113-1.C option 3): a new engine runner, analytics/fade_rebenchmark.py, asks the
registration's question of the persisted excursions read-only and writes a JSON artifact next to the
registration (tracked); knowledge/ingest/fade_rebenchmark.py grades it INDEPENDENTLY against the
registration's own gates and its own rule text. THE POPULATION WAS THE FINDING: cascade_excursions
holds two treatment sources the desk's schema says must never be pooled; the fade's is trade_sweep
(the engine default, the registration's own 'sweeps accumulate'). Round 113 pooled both and read the
sample as ready. Over trade_sweep alone: 13,645 events on 46 coins, top coin ZEC 26.8%
against a 20% ceiling, 5.49-day span against 7 required - two gates fail, verdict INSUFFICIENT,
engine and page agree. Had the sample qualified, ratio_30m 0.7896 with P(>= 1.25) = 0.0000 at
20,000 draws would have been FAIL; stated for completeness, not a verdict. The registration now
carries a dated `population` block (bars unchanged); the progress mirror measures the named
population, gains the max_hhi gate, and no longer treats an INSUFFICIENT verdict as terminal - the
page says ACCUMULATING and names the blocking gates. D1 (R113-1.F): the batch file moved to
cross_market/scripts/ and is tracked; the task's action re-pointed with trigger, battery flags,
logon and instance policy verified identical before and after; the pre-flight FAILS if the batch is
ever untracked. D3: the pre-flight grew to 29 checks - W32Time service state (STOPPED on this
machine; +0.37 s measured against time.windows.com, so a HOMEWORK line, not an emergency), NTP offset,
books-dir writability by a removed probe, stamp path length (182 of 240), MultipleInstances policy,
orphan record-loop processes. Real run: 0 FAIL, 3 WARN. A DOUBLE WRITER was caught on the first real
run: the experiments ingest compiled the new *.verdict.json as a registration into the same page the
adapter writes; JSON carrying the engine's `_artifact` envelope is now skipped there. Tests: knowledge
302 (+16), HL 1,108 (+5). Lint CLEAN at 496 pages; idempotent across fade/experiments/digests/seed.
NO DAEMON RESTARTED; W32Time deliberately left as found.

Round 113 complete (2026-09-06): THE FOMC DRILL HAS A PRE-FLIGHT, THE HUB CAN NO LONGER LAG A
REGISTER, AND `ready` MEANS EVERY GATE. D4: `python -m knowledge.drills.fomc_rehearsal` checks the
five things the 2026-09-16 drill needs to agree on (Event page, rules registration + raw JSON, the
drill card, the git-ignored batch file the task runs, the scheduled task itself via one injectable
PowerShell query) - 22 checks on the real setup, read-only by construction (vault hashed before and
after). Real result: 0 FAIL, 2 WARN (battery flags; interactive-only logon), tokens agree three ways,
trigger 13:58:00 local = T-2. The one FAIL on first run was the module's OWN regex reading `set
BOOKS=%2` instead of the default line beneath it - fixed, and now a test. Out of band, Antigravity's
b3c4493 hand-fix showed the registers hub one pass behind whenever an adapter rewrote a register
without a following seed: `registers.write_register` now writes the register AND the hub in one
call, wired into all 12 adapter call sites (seed untouched; it writes the hub last anyway). D2:
`ready` is set only when EVERY sample requirement the registration wrote down passes - for
passive_fade_rebenchmark that is four gates mirrored read-only from cascade_excursions (19,008 vs
500 events; 62 vs 20 coins; top coin ZEC 19.84% vs 20% ceiling; 7.49 vs 7 days) - with each gate
recorded on the page. `ready_since` is the first run that OBSERVED every gate passing, carried over
like measured_at; lint L11 (warning) fires STALL_DAYS after that with no verdict page. Dating
readiness from the day the count crossed 500 (2026-09-01) would have fired L11 today on a sample
the registration itself called inadequate at Round 104 (PONS 22.5%). D1 REVERSED: lint owns
STALL_DAYS - the adapters already import from lint, so lint importing from experiments would be a
circular import; the experiments copy was dead code and is gone. D3: the four Desk 4 collection
errors were THREE different missing packages (hyperliquid-python-sdk x2, uvicorn, fastapi), not one;
each module now skips on the one it lacks, naming the install; fastapi was installed after a clean
dry run (no upgrades) but the webhook module still skips because `main` imports the Hyperliquid
adapter at module level. Desk 4 from its own directory: 151 passed, 10 skipped, 0 errors. Tests:
knowledge 286 (+23), all green offline. Vault 493 pages, lint CLEAN, idempotent across
experiments/digests/seed by hash. NO DAEMON RESTARTED.

Round 112 complete (2026-09-06): A PRE-REGISTRATION CAN NO LONGER SIT AT N=0 IN SILENCE, AND
THE ONE THAT DID IS PARKED ON TRUE GROUNDS. R112-OOB.2: registrations carry `dev.progress`
{accumulated, target, unit, status, measured_at}, measured read-only from the paper state
or the excursion table; the experiments register renders it as `0/50 (0%) · parked`; lint
L10 warns on a registration 3+ days old still at zero and still `accumulating`. regime_
filtered_v1 is PARKED via a dated amendment in its own file (the registration's protocol),
NOT via `status: parked`, which is outside frontmatter.STATUSES and would have failed L1 -
the directive's schema block and its status line contradicted each other. THE PARKING
RATIONALE WAS REWRITTEN: the directive cited the Round 104 cascade replay as a fade-thesis
FAILURE with Side A's ratio and P; that verdict was INSUFFICIENT (never to be read as FAIL,
per its own ratified registration), Side A is a side split the registration does not grade,
and the replay tested a liquidation-cascade sweeper while this is a passive fade with a trend
gate - three errors, two of them already corrected in Round 104b. The amendment parks on
what is true: N=0 after 5 days, no process running, the documented 600 s / 1,224 s defect,
and no calendar before the FOMC drill. R111-1.C: desks link ONE registers hub, itself a
SPECS entry (no second builder). R111-1.D: filed-query slugs carry a 4-hex digest of the
whole question. D3: the drill-card contract is one explicit test with a real 76-digit token.
Tests: knowledge 263 (+30), all green offline. Vault 493 pages, lint CLEAN. NO DAEMON
RESTARTED; nothing was started either.

Round 111 complete (2026-09-06): THE QUERY LAYER CAN FILE AND COUNT, WITHOUT LOSING THE ONE
PROPERTY THAT MAKES IT USABLE AT T-2. B16: `--file "<question>"` scaffolds a Concept page
recording the question and what was open when it was asked - never an invented answer - and
`--count-usage` records dev.usage on the pages a query opened. USAGE COUNTING IS OPT-IN, and
that is a correctness requirement, not a preference: write_page REFUSES a page inside its own
dev.window, so counting on every query would raise WriteRefused at T-2 on the FOMC Event page
and hand the operator a traceback instead of a briefing card. Even with the flag a windowed
page is skipped rather than attempted. R110-1.A: `description` joins the digests register
columns. R110-1.E: a truncated digest now warns durably in log.md, not only on stdout.
Tests: knowledge 233 (+21), all green offline. Vault 491 pages, lint CLEAN. NO DAEMON
RESTARTED.

Round 110 complete (2026-09-06): THE DIGESTS ARE NOW GUARDED, REGISTERED AND HONEST ABOUT
WHAT THEY DROP. R109-1.F: `Digest` is a registers.SPECS type, so seed writes an EMPTY digests
register from the first run and every desk can link it - fixing the CAUSE of the 27 test
failures Round 109 worked around rather than the symptom. That exposed a real conflict the
directive did not anticipate: seed and the digests adapter were BOTH building that page, with
different content, silently overwriting each other every run. There is now one writer.
R109-1.E: every digest pins `^Round <N> complete` in AGENTS.md with dev.asserts, so renaming
or deleting a round heading trips C1 on the page that quotes it instead of leaving 210 KB of
prose pointing at a section that is gone. R109-1.C: MAX_BODY_LINES 120 -> 250, and a clipped
entry now SAYS it was clipped and warns at compile time. Tests: knowledge 212 (+10), all green
offline. Vault 488 pages, lint CLEAN. NO DAEMON RESTARTED.

Round 109 complete (2026-09-06): THE WORK CHAIN IS ADDRESSABLE, AND THE PRE-REGISTERED RULES
NOW HAVE A GUARD ON BOTH COPIES. B5: knowledge/ingest/digests.py compiles one Digest page per
round from this log - 63 of them - so answering "what happened in Round 97?" is a lookup
rather than a scan of 210 KB. THE LOG REMAINS THE RECORD; the digests cite it and lose to it.
R108-1.E: lint C1 now compares `dev.rules` against the raw registration JSON field by field, so
the second copy Round 108 created cannot drift - a token id that slips there is the card
telling an operator to trade a different market than the one registered before the data was
seen. The compiler and the checker SHARE one transform, because two transcriptions would drift
exactly the way the check exists to catch. R108-1.D: Event pages declare `dev.books_dir` and
the card reads it instead of constructing a path. Tests: knowledge 202 (+26), all green
offline. Vault 487 pages (+64), lint CLEAN. NO DAEMON RESTARTED.

Round 108 complete (2026-09-06): LINT L9 CLOSES THE HOLE ROUND 107 OPENED, AND THE DRILL CARD
IS NOW COPY-PASTEABLE. L9 (Ruling R107-1.D): a wikilink whose only target is a git-ignored file
is an error - it lints clean locally and fails L8 on a FRESH CLONE, the worst shape of bug
because it is invisible to whoever introduces it. Blast radius audited read-only first: zero,
as expected, since Round 107 verified those three dashboards had no inbound links before
untracking them. R107-1.E: `dev.rules` is serialised into the registration's frontmatter and
the card reads it, so token ids print WHOLE - the card used to parse the rendered table, which
truncates them to 12 characters for readability, and an operator cannot paste `561528276087`.
R107-1.A: the post-print command is now exact and copy-pasteable. R107-1.B: an exact stem or
unambiguous prefix answers with one regime card; substring is the fallback and says when it is
ambiguous. Tests: knowledge 176 (+20), all green offline. Vault 423 pages, lint CLEAN.
NO DAEMON RESTARTED.

Round 107 complete (2026-09-06): THE OPERATOR CAN NOW ASK THE VAULT A QUESTION.
knowledge/query.py answers the two queries the constitution pre-baked in s.Query:
`--drill-card <event>` and `--regime BTC`. The drill card is read at T-2 with a clock running,
and every design choice follows from that: it NEVER WRITES (not a log bullet, not a usage
counter - inside its own window the pages it describes are frozen), it fits in under 60 lines
with a test asserting it, it COMPUTES the countdown rather than restating the release instant,
and it assembles from compiled PAGES rather than going back to the raw JSON. A missing Event
page refuses with the list of known events: a blank card two minutes before a print is worse
than no card. R106-1.E: `rank_at_seed` is frozen and a new `rank_now` carries the live figure -
Round 106 made whale pages refreshable, which put that field in the same trap `first_seen`
fell into on markets. R95-E: the three volatile exporter-written dashboards are untracked;
`git status` is now pristine between rounds. Tests: knowledge 156 (+11), HyperLiquid +
cross-market 1,314, all green offline. Vault 423 pages, lint CLEAN, adapters idempotent by
hash. NO DAEMON RESTARTED.

Round 106 complete (2026-09-06): THE ADAPTER LIFECYCLE INVARIANT ENFORCED, DESK 1 SPREAD
SAMPLING GATED ON THE ENTRY BAR, AND GIT PROVENANCE NOW CHECKED. R105-2: titans are
re-admitted when they fall below the cap, and pages whose SOURCE ROW is gone (a pruned sharp)
are NAMED in report.unmaintained rather than silently frozen - an adapter that cannot rebuild
a page should say so, not pretend. Markets re-admit every token that already has a page, but
NOT the way the ruling sketched it: a naive union would have written a degraded duplicate,
because with no drop record compile_market falls back to a placeholder question AND a
token-derived slug, so an aged-out market would get a second page at a new path while the good
one was orphaned. Identity is recovered from the page's own dev block instead. R104-1: the
spread gate went into collectors/orderbook_sampler.py, NOT incremental_persistence.py as
directed - the latter is a RETROSPECTIVE grid over historical instants and cannot sample L2 for
a window that opened days ago; it only reads orderbook_snapshots. B19/B20: lint L5 now resolves
`git:<sha>` sources and dev.citations with `git cat-file`, SKIPPING (not passing) outside a
repository. Tests: knowledge 145 (+8), HyperLiquid + cross-market 1,314 (+3), all green
offline. Vault 423 pages, lint CLEAN, adapters idempotent by hash. NO DAEMON RESTARTED.

Round 105 complete (2026-09-06): ALL FOUR R104 RULINGS IMPLEMENTED, AND LINT L8 FOUND 86
BROKEN LINKS THE MOMENT IT WAS SWITCHED ON. R104-4: lint L8 flags a dangling outbound
wikilink - the mirror of L3, which only ever caught the opposite failure. Links inside code
fences and code spans are excluded, so the constitution can document `[[wikilinks]]` without
tripping it. R104-2: cascade_replay.py now emits an `_artifact` envelope (written_at, writer,
rows_in_table, seed) and writes --out atomically; the ingest reads written_at from it and
falls back to the file mtime only for pre-Round-105 artifacts, SAYING WHICH on the page.
R104-3: the guard went into pages.write_page rather than the eight named adapters - 31 call
sites already funnel through it, so one guard covers every adapter present and future. A page
whose content has not moved is not rewritten and keeps the generated.at it earned; the log
line and the entities 'updated' count are now conditional on a real change too. VERIFIED BY
HASH: running every adapter twice over unchanged data changes ZERO files. B1: new
wiki/concepts/cascade_anatomy.md. Tests: module 23 = 137 (+17), HyperLiquid + cross-market
1,311, all green offline. Vault 423 pages + constitution, lint CLEAN. No daemon touched.

Round 104 complete (2026-09-06, corrected in 104b): TWO NEW COMPILED PAGES ON DESK 1, AND
FOUR REAL DEFECTS FOUND IN OUR OWN TOOLING WHILE BUILDING THEM. Deliverables 1-2 (the wall-clock
test fix and the exporter --stop) landed earlier in the round at 25 green exporter tests.
B2: knowledge/ingest/funding.py compiles wiki/regimes/hl_funding_regime.md from
basis_realised_windows, read-only. B1/F3: knowledge/ingest/cascade_replay.py compiles
wiki/experiments/whale_sweeper_cascade_replay_verdict.md from the engine's own --json
artifact and RE-GRADES it against the pre-registration rather than copying the engine's
verdict string; the two agree (INSUFFICIENT), and a disagreement would be recorded as a
finding in both voices. Both pages pin their bars as dev.parameters (settings.py by regex,
the registration meta.json by json_path), so editing an acceptance bar after the data was
seen is a lint C1 error. Tests all green offline: module 23 = 119 (+17), HyperLiquid 1,100,
Sports 223, Polymarket 237, Tax 546, cross-market 211, Desk 4 151 (+6 skipped) = 2,587.
Desk 4 leaves 4 modules uncollectable for a missing `fastapi` - PRE-EXISTING, unrelated to
this round and unchanged by it. Vault 420 pages + constitution, lint CLEAN. No daemon was
touched and no desk module edited.

104b (same round, second commit): THE FUNDING PAGE OVERSTATED ITS OWN SECOND POPULATION
AND I CAUGHT IT BY READING THE HARVESTER INSTEAD OF ASSUMING IT. 104a labelled the 473
windows clearing the gross bar 'entry-qualifying ... the ones the harvester's own entry rule
would have taken'. That is false. `scan_basis_opportunities` requires the gross bar AND the
net bar AND a spread ceiling, with check_spreads=True by default, and its own docstring says
'a basis trade whose cost has not been measured has not been evaluated' - so the live rule
REFUSES an unmeasured-spread trade, while the measurement grid opens a window on a stride
regardless. The 28.05% median is therefore an UPPER BOUND on a superset, not a backtest, and
the page now says so in a call-out. Renamed the key entry_qualifying -> gross_bar_only, with
a compatibility reader so history rows written before the rename still render rather than
KeyError-ing an existing page. Two more facts settled by reading the writer rather than
guessing: realised_apr IS annualised (accrual_rate_hours/observed * HOURS_PER_YEAR * 100), so
it compares directly against the bars; and the 3,839 NULL rows are NULL because coverage fell
under MEASUREMENT_MIN_COVERAGE = 0.60, an observability exclusion, not an outcome one - so the
distribution is not survivorship-biased in the way I had flagged as an open question.
Module 23 = 120. The net bar is NOT decorative, as 104a's homework note wrongly implied: it is
enforced live and merely unevaluable retrospectively. HOMEWORK.md corrected.

Round 103 complete (2026-09-06): MAIDEN NIGHT CLOSED, ALL FOUR ENTRIES GREEN; THE
LEAD-LAG TOOLING DEFECT IS FIXED. Committed in two halves on purpose: 103a (dbe37df)
before the scheduled tasks, 103b after them, because maiden_protocol imports FOUR desk
modules in fresh processes (lead_lag, both obsidian_exporters, titan_correlator) and the
maiden record is not the place for an untested edit. 103a: the Item 14 sweeper acceptance
bar PRE-REGISTERED before any replay (B15) and knowledge.ingest.lead_lag defaulted to the
exporter artifact. 103b: RULING R102-1 - cross_market/lead_lag.py --json now covers the
ANALYSIS branch, not just --check-data, so the pipeline this repo has published since
Round 97 finally works; verified live (parsed, best_lag -45, corr +0.069, n=1551) and
pinned by two tests, one asserting the verdict schema and one asserting --check-data
--json still returns readiness. RULING R102-2 - LeadLagRefresher._write_verdict_artifact
serialises the run that wrote Cross_Market_Titans.md to
cross_market/data/lead_lag_latest_verdict.json, atomically (temp then os.replace) with an
_artifact envelope naming the writer and instant; a write failure returns None and never
breaks the export. Two tests cover the happy path and the failure. Tests: module 23 = 101,
master 23 modules 1,039, total 1,093 + 1,039 + 546 = 2,678, all green offline. Vault 418
pages + constitution, lint CLEAN. NEW HOMEWORK.md at the repo root: the operator's own
task list, human-required actions only. Daemons: watcher is now 17688 (restarted 22:20 by
its scheduled task, tags live); exporter 56412, supervisor 46740, collector 38548 unchanged
and NOT restarted - the R102-2 artifact will not appear until 56412 is restarted, which is
the operator's call.

EXPORTER RESTARTED (the first daemon restart this project has performed itself): 56412
stopped, start_cross_market_exporter.bat relaunched it as 62760 at 02:44:06Z, and the new
process took the pid lock and began cycling. Verified by WAITING for the lock rather than
checking immediately - the mistake tonight's watcher script makes. Cross_Market_Arb.md now
carries the Round 101 line '> **Desk**: [[Desk_03_Cross_Market_Desk]] · Shell twin: ...'.
Sports_Desk.md does not yet: it is written by a different exporter that is not a daemon and
will pick the line up on its next --once run. CONSEQUENCE WORTH KNOWING: the R102-2 artifact
still does not exist, because the lead-lag cooldown runs from the note's run-at marker and
the next run is 2026-09-07T01:40:34Z (~23 h out). A restarted exporter honours the same
cooldown by design, so restarting did not and could not produce the file early.
ITEM 14 PRE-REGISTRATION RATIFIED (status stable, verified antigravity/architect, ratified_by
103-B15) via a new `knowledge.ratify --stem` that targets exactly one page instead of a whole
tag group. Antigravity independently BUILT AND RAN the replay engine
(HyperLiquid/HL_Monarch/analytics/cascade_replay.py, +7 tests) while this round was in
flight; its verdict under the registered bar is INSUFFICIENT (top coin PONS 22.5% > the 20%
ceiling), which is the pre-registration doing exactly its job - Side B's eye-catching 1.7378
ratio is NOT a finding, and at P=0.5020 it would have been RETUNE at best even had the
sample qualified. Side A is a clean FAIL (ratio 0.2784, P=0.0090): fading forced selling
does not work, momentum persists.
[CORRECTED IN ROUND 104, TWICE OVER. Those two P-values were transcribed from a handoff
message rather than read from an artifact, and both the number and the reasoning were wrong.
(1) The artifact now puts side B at P=0.4808 and side A at P=0.0103, not 0.5020 and 0.0090.
Nobody mistyped: cascade_excursions is written by a live collector and grew from 28,544 to
29,350 rows between the two runs. 0.5020 and 0.4808 are on OPPOSITE SIDES of the registered
0.50 band edge, so the transcription changed the stated band. (2) Worse, the sentence applied
the POOLED primary-metric bands to a SIDE SPLIT, which the registration does not authorise at
all - the bands govern fade_ratio_30m pooled, and the sides are a required separate report
(commitment 5), not separately graded. Either error alone invalidates 'RETUNE at best'. The
verdict page now compiles from the JSON and re-grades from the registration; see Round 104.]

Round 102 complete (2026-09-06): THE ITEM 18 MAIDEN RUN HAPPENED AND THE VERDICT IS IN
THE WIKI. The 24 h gate opened at 01:40:33Z (21:40:33 EDT); the exporter's own cycle ran
the analysis two seconds later and wrote Cross_Market_Titans.md. `python -m
cross_market.maiden_protocol` at 01:41:00Z returned ALL SIX CHECKS PASS, exit 0:
loop_running (pid 56412), series_ready, status_last_run, log_ran_line,
note_run_at_inside_block, cooldown_observed. TIER 1 VERDICT: **no measurable lead-lag**
(peak |corr| 0.07 < the registered 0.20 bar; best lag -45 min, n=1497, 1,465 probability
shifts over 617 markets against 8,927 BTC price points). Tier 2 diagnostics under the
registered bars agree: crypto -45 min +0.07, fed-rates -10 min +0.08, both below the bar.
The 24-hour series therefore says Polymarket macro repricing does not lead HyperLiquid
BTC at any lag inside an hour. Ingested with knowledge.ingest.lead_lag --tier 1 ->
wiki/experiments/lead_lag_tier1_macro_20260906T0142Z.md (class `no-lead`, tests_run 1)
and wiki/regimes/btc_macro_regime.md (history 1 row; regime_consensus_3
insufficient-history until three runs). Ruling 99-2 ratified (status stable, verified
antigravity/architect at 01:33:00Z, dev.ratified_by 99-2); the other 28 extracted rulings
kept their 98-1 verification, as the Round 101 round-guard intends. REAL VAULT: 417 pages
+ constitution, lint CLEAN. Tests: 1,093 + 1,036 + 546 = 2,675, all green offline.
NOTHING WAS RESTARTED: daemons 49812/56412/46740/38548 hold their original start times and
no desk module was modified tonight (see the findings).

Round 101 complete (2026-09-05): KNOWLEDGE PHASE 4 - BASES VIEWS + TEMPLATES (B13),
DASHBOARD SHELL TWINS + DESK BACKLINKS (F1), DOCSTRING THESES (B12), RECEIPT EDGE/HURDLE
(Ruling 100-b) + Rulings 100-a/c/e/f. NEW knowledge/views.py: seven wiki/_views/*.base
(Obsidian Bases; filters file.inFolder, table views) and four wiki/_templates/*.md whose
frontmatter is OKF-valid before a placeholder is filled; `_` folders are tooling, skipped
by index and lint. NEW knowledge/ingest/theses.py: ALL-CAPS docstring sections of the desk
modules -> wiki/concepts/thesis_*.md (35 pages), every heading pinned with dev:asserts
so a silent deletion is a C1 finding; eighth register theses_register. F1: Sports_Desk,
cross_market, HL_Monarch (three notes), Polymarket_Monarch and Tax_Reserve_Agent exporters
now print a `Desk:` wikilink and a `Shell twin:` --once command; SOURCE-ONLY - the running
exporter (56412) does not reload and is unaffected until restarted; quant_trading_lab's
exporter is its own repo with a dirty tree and was not touched. Receipts:
log_execution_receipt(gross_edge=, after_tax_hurdle=) stamps `edge:`/`hurdle:` into notes;
latency_sniper.record_paper passes edge = event confidence and hurdle = the worst fill
breakeven (both probabilities, so edge >= hurdle IS the sniper's rule), falling back for
older writer doubles. Journal: --claim free-text predictions scored by hand (--score --event
E --outcome 0|1, scored_by human:operator); debrief reports Daily Paper Notional Turnover,
drawdown vs killswitch UNCHECKED (fills are not realised loss, 100-c), per-fill hurdle
PASS/FLAG/UNCHECKED. tests_run written back onto the registration PAGE per tier (100-e; the
raw meta file untouched). Ruling_98-1.md ratified under 98-1 and its page lists the 27
pages it ratified (## Effect in this wiki). REAL VAULT: 415 pages + constitution, lint
CLEAN. Tests: module 23 = 100; master 23 modules 1,036; total 2,675, all green
offline (exporter, sniper and receipt suites re-run). Daemons and tonight's tasks untouched.

Round 100 complete (2026-09-05): KNOWLEDGE PHASE 3 - JOURNAL + CALIBRATION LEDGER (B10),
TYPED RELATIONS (B11, lint L6), STALENESS POLICY (B14, lint L7), UNIVERSAL CARRY-OVER
(Ruling 99-2). NEW knowledge/journal.py: journal/YYYY-MM-DD.md on receipts or --create;
Plan and Open are human and preserved across re-runs; Executions come from the CSV
paper receipts (Tax Reserve Agent writer columns; strategy from notes or filename);
Debrief checks the day's paper notional against the quant lab's $3,500 daily killswitch
(a guarded dev:parameter) and reports the after-tax hurdle as UNCHECKED because the
receipt writer records no edge - the honest state, written on the page. Calibration
ledger: --predict records {event, field, op, value, p, at, by human:operator} BEFORE an
event; --score resolves against the Event page's dev:payload (written by ingest.clob
after the print), Brier = (p - outcome)^2, and rebuilds wiki/concepts/calibration.md
(count, mean Brier vs 0.25, reliability by p-bin). Predictions are never edited. Seventh
register journal_register, linked from every Desk. LINT L6: dev:relations with
supersedes (exists + deprecated, acyclic), contradicts (must carry resolved_by -> an
existing Ruling), measured_by (-> Experiment), enforced_in (-> repo file), depends_on.
LINT L7: Ruling 180 d / Concept 90 d must carry stale_after unless machine-maintained
(dev:register_for or dev:history) or deprecated; seeds and ingest.rulings stamp it;
Market is policed by C2, Reaction Profile/Event/Journal never stale. dev:tests_run: 0 on
registrations, the running verdict count per tier/scope on verdicts. carry_human_fields
now in experiments, computations, calendar, markets, clob Event, lead_lag Regime,
rulings, entities, journal (tested end to end with a forced rewrite of four types).
REAL VAULT: 375 pages + constitution, lint CLEAN (first quiet-day journal written for
2026-09-05). Tests: module 23 = 91; master 23 modules 1,027; total 2,666, all green
offline. Daemons and tonight's tasks untouched.

Round 99 complete (2026-09-05): KNOWLEDGE - CRM SEEDS (B8) + DIRECTIVES RATIFIED (B4,
Ruling 98-1). NEW knowledge/ingest/entities.py: crm/titans, crm/whales (top N by
account_value), crm/sharps (sharp_traders + tracked_wallets), crm/books (pinnacle as
the sharp reference, one page per retail_book with per sport/market-type evidence from
edge_opportunities); all SQLite opened file:...?mode=ro. THE INVARIANT: the `## Judgement`
section, `verified`, `stale_after` and a status promoted past draft are never
overwritten on re-ingest; evidence rows append (dedup by scan time, newest 50). TITAN
DEFINITION CORRECTED: the identity cache has 1,685 entries (the Round 95 audit printed
the first eight keys and called them eight pairs), every one a whale EOA by
construction, and none of their proxies appears in the Polymarket trader tables. A
titan therefore requires presence on BOTH venues (proxy or EOA in sharp_traders /
tracked_wallets, or a sharp's resolved EOA in whale_wallets): 0 today, which
agrees with the dashboard's 0 institutional actors and the empty cross_market_titans
table. NEW knowledge/ratify.py records a ratification (verified + status + dev:
ratified_by, register rebuilt, one Ratify log bullet, idempotent); ingest.rulings titles
are now the whole cleaned sentence; all 27 extracted pages re-titled and ratified under
98-1. Also: lint --fix-safe rebuilds index.md (98-5); HL experiments dev:item 14 with
related_items [8]; sixth register crm_register linked from every Desk. REAL VAULT:
370 pages + constitution (100 whales, 79 sharps, 4 books, 0 titans), lint
CLEAN. Tests: module 23 = 82; master 23 modules 1,018; total 2,657, all green offline.
Daemons and tonight's tasks untouched.

Round 98 complete (2026-09-05): KNOWLEDGE - COMPILE WHAT EXISTS (backlog B3, B4, B6, B7,
B9; Antigravity's Round 97/97b rulings applied). B3: ingest.experiments now reads
HyperLiquid/HL_Monarch/data/experiments/*.meta.json too - registrations (acceptance_bar
and other numeric blocks as json_path dev:parameters; the control as dev:requires_files)
and archived controls (result numbers guarded, so overwriting the N=12 baseline is a C1
finding). B4: NEW ingest/rulings.py extracts every distinct Directive/Ratification/Ruling
N-N from AGENTS.md (27 pages, status draft, dev:citations with section+line+sentence
window, dev:asserts pins the citation) and maintains rulings_register. B6: NEW
knowledge/computations.py files the two dashboard shell twins and the knowledge CLIs as
OKF Attested Computation pages (runtime, computation, executor.receipt, attester;
declarative per R95-C). B7: committed knowledge/calendars/fomc_2026.yaml (Sep 16 18:00Z,
Oct 28 18:00Z, Dec 9 19:00Z after the clock change, SEP flags) and tax_2026.yaml (Q3 due
2026-09-15, Q4 due 2027-01-15); NEW ingest/calendar.py -> Event pages with T-2..T+5
dev:window (FOMC) or stale_after = due (tax); clob ingest now ENRICHES a calendar Event
(keeps window/sep/meeting). B9: NEW ingest/markets.py -> 97 Market pages from the
rules tokens, Experiment dev:tokens and the newest macro drop's FED-RATES family (identity
only, no prices); lint --fix-safe now deprecates a Market whose token left the drops
(ruling A5). NEW knowledge/registers.py: five machine-maintained register pages, all
linked from every Desk page (seed --force). Regime page carries latest_verdict +
regime_consensus_3 (ruling A3). Desk parameters for C3 (ruling A6): confidence_floor
0.99, fee_rate 0.0 x2 (after_tax_edge_hurdle is a method, not a constant - no parameter).
REAL VAULT: 184 pages + constitution, lint CLEAN. Tests: module 23 = 75; master 23
modules 1,011; total 1,093 + 1,011 + 546 = 2,650, all green offline. Daemons and tonight's
tasks untouched.

Round 97 complete (2026-09-05): KNOWLEDGE PHASE 2 - CONSTITUTION RATIFIED, INGEST
ADAPTERS, RAW MANIFEST, LINT C2/C3 (Antigravity rulings 1-13 on Round 96 applied).
WIKI_SCHEMA.md now carries verified: antigravity/architect and status stable
(ruling 8) and documents every change below. NEW knowledge/ingest/: experiments.py
(cross_market/experiments/*.json -> Experiment pages; bars become dev:parameters
addressed by json_path, rules tokens become dev:tokens, release-2m..+5m becomes
dev:window; maintains wiki/concepts/experiments_register.md so no Experiment is
an orphan), lead_lag.py (lead_lag --json -> verdict Experiment page + wiki/regimes/
btc_macro_regime.md with a dev:history row per verdict and a fixed class
vocabulary insufficient|no-lead|contemporaneous|polymarket-leads|hyperliquid-
leads|coincident; Tier 2 vs 2b disagreements listed, never resolved; PRIMED for
the Tier 1 verdict ~2026-09-06T01:39Z), clob.py (survival-curve --json -> one
Reaction Profile per market, the Event page, wiki/concepts/latency_decay.md cross-
event table; the per-second series is NOT copied; PRIMED for 2026-09-16). NEW
knowledge/raw_manifest.py -> raw/index.md (17 federated streams present, OKF index
lines relative to raw/, absent streams as `> not present` notes). LINT: C2 expired
tokens vs the newest macro+sports drops (warning; missing drops folder = one
warning), C3 same dev:parameters name with different values across pages (error;
kelly_fraction 0.25 now declared on Desks 2/3/5 and checked against
fair_value.py, latency_sniper.py, monarch_hook.py), C1 float-aware comparison +
dev:requires_files + json_path for JSON sources, C5 generated.at-in-window =
error / mtime-only = warning, constitution in scope for L1/L4/L5/C1 and exempt
from L2-listing/L3, nested index.md files validated. SEED: Item_04_Section_1256_
Futures_Tax_60_40 and Item_19_Multi_Desk_Monte_Carlo_Risk_Of_Ruin (old files git
rm'd), rulings verified.at = the ratifying commit instants (R4 17:15:05Z, R6
17:48:20Z, R2 18:13:11Z, R95 20:10:31Z), R1/R3 deprecated (never issued), --at
defaults to the registry mtime so --force is byte-idempotent, Desk 3 links the
compiled pages. REAL VAULT: 36 pages + constitution + raw/index.md, lint CLEAN.
Lint C1 fired on real data during the round: the Tier 2b registration has
min_points twice (readiness 200, bars 60) and a regex takes the first; hence
json_path. Tests: module 23 = 61; master 23 modules 997; total 1,093 + 997 + 546
= 2,636, all green offline. Daemons and tonight's tasks untouched.

Round 96 complete (2026-09-05): PHASE 1 - WIKI CONSTITUTION, SEED PAGES, MASTER
MODULE 23 (Ratification R95-A..G). NEW obsidian_vault/WIKI_SCHEMA.md (the
constitution: layers and ownership, actors, OKF v0.2 frontmatter + dev:
namespace, page types and folders, reserved index.md/log.md formats, the two
DEV rules, ingest/query/journal/lint protocols, refusals). NEW package
knowledge/: frontmatter.py (parse/validate/serialize; type required; actor
regex; generated/verified/status/stale_after/sources; dev.asserts,
dev.parameters, dev.window), pages.py (write_page is the ONLY writer and
refuses anything outside wiki/ crm/ journal/ raw/ + WIKI_SCHEMA.md index.md
log.md, refuses reserved names and in-window pages; index/log builders and
parsers; wikilink extraction), lint.py (L1-L5, C1 copied-state drift via
declared dependents, C5 in-window mtime; CLI exit 0/1/3; writes nothing),
seed.py (parses the Top 20 registry blocks read-only; 5 Desk + 20 Item + 7
Ruling pages; skips existing pages unless --force; rebuilds index.md; appends
log.md). SEEDED the real vault: 32 pages, index.md, log.md; lint CLEAN.
Rulings catalogue is honest about the record: R2, R4, R6 carry commit
provenance and verified by antigravity/architect; R5 is draft (pending, named
by amm_rewards.py); R1 and R3 have NO text anywhere in the repo or git
history and are draft placeholders that say so; R95 records the seven
ratifications. Desk pages carry dev:parameters checked by C1 against their
owning files (lead-lag 0.20 bar and 5 min latency, quant-lab $3,500
killswitch and 1.0 % risk, tax 0.24 federal and 0.0637 NJ). Tests: module 23
= 42 (frontmatter, ownership, index/log, every lint code, seed parse/build/
idempotence/force/dry-run/HALT/no-write-outside); master suite 23 modules 978;
total 1,093 + 978 + 546 = 2,617, all green offline. Daemons and tonight's
tasks untouched; no dashboard, entity note or data folder written.

Round 95 complete (2026-09-05): RESEARCH ROUND - LLM WIKI x DEV SYNTHESIS
BLUEPRINT (no code, no daemon, no dashboard touched). NEW LLM_WIKI_BLUEPRINT.md
(OKF-shaped frontmatter on the document itself): read-only audit of the five
desks' knowledge assets (what is stored, what evaporates, what the vault
shows); the finding that DEV already has Karpathy's three layers unnamed -
raw = desk data/ folders, schema = AGENTS.md + CLAUDE.md + registry, wiki =
missing (563 KB of AGENTS prose and docstring essays stand in for it); a
design that adds wiki/ crm/ journal/ raw/ INSIDE obsidian_vault (exporters
keep owning dashboards and Whales/ Wallets/ Trading_Taxes/), federates raw in
place (4.9 GB does not move), and puts the constitution in a new
obsidian_vault/WIKI_SCHEMA.md; OKF v0.2 frontmatter (type required; generated,
verified, status, stale_after, sources) plus a dev: namespace with
dev:asserts / dev:parameters so lint can check every copied number against
its owning file (copied-state drift, the Round 94 header defect class); the
dashboards' "shell twins" map to OKF's Attested Computation type; ingest
adapters over EXISTING --json outputs (survival curve -> Reaction Profile,
lead_lag verdict -> Experiment + Regime, receipts -> journal, whales/sharps/
titan cache -> crm); lint L1-L5 structural + C1-C6 DEV-specific (stale
thresholds, expired tokens, cross-desk conflicts, unhedged tax, in-window
edits, contradictions); phases 1-5 ordered by the 2026-09-06 Tier 1 verdict
and the 2026-09-16 FOMC drill; seven rulings requested (placement,
constitution file, OKF depth, verification actor, dashboard git tracking,
debrief scope, module 23). Tests unchanged: 1,093 + 936 + 546 = 2,575, all
green this session. Daemons and tonight's tasks untouched.

Round 94 complete (2026-09-05): SURVIVAL-CURVE HARNESS + FOMC DRILL SCHEDULED.
latency_sniper --survival-curve --event event.json --rules
cross_market\experiments\fomc_2026-09-16.rules.json --books DIR [--step-seconds 1]
[--assume-defaults] [--json]: EVERY stamp of a --record-loop drill (not the newest
per token) replayed through the uncapped depth walk for each market the rules
resolve, indexed by seconds from the event's observed_at (the rules file's
release_utc is printed beside it with the lag). Per market a summary: pre-print
baseline notional, the first post-print second the book changed (CLOB hash, else
the levels), seconds to half and to a tenth of baseline, seconds until nothing
clears, and dollar-seconds of fillable notional after the print (size x
survival). Uncapped on purpose - a Kelly-capped figure sits flat at the cap and
hides the decay. Neg_risk NO sides deferred (R4). Exit 1 = no stamps for the
rules' tokens. THE DRILL IS SCHEDULED: Windows task Monarch_FOMC_Drill fires
2026-09-16 13:58 EDT (= 17:58Z, T-2 min) and runs
cross_market\data\fomc_drill_2026-09-16.bat (operator file, untracked, CRLF):
record-loop on the three registered tokens, 1 s x 420 s, into
cross_market\data\clob_books\fomc_2026-09-16\, log
cross_market\data\fomc_drill_2026-09-16.log. Dry run today (3 s) wrote 9
stamps and the curve replayed them end to end with the Tax Reserve Agent
breakeven. LAPTOP ON AND LOGGED IN at 13:58 EDT on the 16th. After the print the
operator writes event.json {kind fed_rate, payload.change_bps <int from the
statement>, source, confidence >= 0.99, observed_at} and runs the curve.
Docs defect fixed: MASTER_COMMAND_LIST.txt's "Last Update" header had said Round
72 since 9fd5ef1 - the docs scripts replaced a string that was not there, and a
silent replace is a no-op; the script now asserts the anchor. Tests: module 21
now 14. Daemons and tonight's tasks untouched.

Round 93 complete (2026-09-05): RULING R2 INSTRUMENT + FOMC RULES REGISTERED.
latency_sniper.record_loop() / CLI --record-loop --tokens T[,..] --interval 1
--duration 420 [--books DIR]: one read-only GET per token per interval,
sleeping interval minus fetch time; stops at the duration, on HALT.flag
(exit 3) or Ctrl-C; an HTTP 429 is counted and answered with a growing
pause (5 s x n, max 30 s). cross_market/experiments/fomc_2026-09-16.rules.json
PRE-REGISTERED with the REAL YES token ids from the 2026-09-05 macro drop:
no change (== 0), hike 25 (== 25), hike 50+ (>= 50); the two cut markets do
not exist in the drop today and are listed under not_found_in_drop (may be
APPENDED before the window in a dated re-registration, never edited inside
T-2..T+5). Event schema: kind fed_rate, payload.change_bps int, confidence
>= 0.99 only from the statement itself. All three markets are neg_risk:
YES side only (R4). Tests: module 21 now 13. Daemons and tonight's tasks
untouched. THE DRILL COMMAND for 2026-09-16 17:58Z:
  python -m cross_market.latency_sniper --record-loop --tokens <the three token ids from the rules file> --interval 1 --duration 420

Round 92 complete (2026-09-05): OPTION 2 - DEPTH REPORT OVER REAL BOOKS.
latency_sniper.depth_report(book, outcome, confidence, breakeven) walks a
recorded book best-first and reports, per level, price (NO: 1 - bid),
fee-adjusted odds, the after-tax breakeven, edge/share and cumulative
shares / notional / VWAP - no cap: the upper bound the book offers before
anyone pulls; NO on a neg_risk book is deferred (Ruling R4). CLI:
latency_sniper --depth-report --books DIR [--confidence 0.995]
[--assume-defaults] [--json]; uses the Tax Reserve Agent breakeven when the
hook loads. MEASUREMENT: 8 live stamps recorded (4 thin Fed-governance
markets, 4 thick: two BTC-dip, two FOMC neg_risk) into
cross_market/data/clob_books/ (ignored). With the outcome known at 0.995
EVERY level below ~0.99 clears the after-tax breakeven, so the "fillable"
upper bound is simply the resting depth: thin books offer $400-$3,300 of
YES depth (15-29 levels) and $1.3k-$41k of NO depth; thick books offer
$50k-$3M. The number that matters is therefore not depth at rest but how
many seconds it survives after the print - which only Ruling R2's T-2/T+5
recording at the 2026-09-16 FOMC can measure. Registry extent corrected:
the Top 20 spans lines 80-484 (Items 19 and 20 at ~447 and ~465), not
80-415; the docs scripts' byte-identical check now covers 80-484. Tests:
module 21 now 12. Daemons and tonight's tasks untouched.

Round 91 complete (2026-09-05): RULING R6 - COMPETITOR Q MEASURED FROM
RECORDED BOOKS. amm_rewards.book_q() scores every resting level of a
recorded CLOB stamp inside the programme window (per side, Q_min by the
band rule); replay_rewards() runs it over a stamps folder and adds the
share a hypothetical two-sided quote (--size at mid +/- --quote-offset)
would earn; the pool rate stays the ONE input (--pool, printed ASSUMED,
until Ruling R5 records it). CLI: amm_rewards --replay-books DIR --pool X.
FIRST MEASUREMENT (the Fed "no change in Sept 2026" market, one real stamp
at 16:59Z): mid 0.505, book Q bid 28,828 / ask 93,337 / Q_min 28,828 over 6
levels in the 3-cent window; a 100-share quote at +/-1 cent earns a 0.09%
share. Retail-sized quoting on a heavily-made market earns a rounding
error of the pool; the module says so rather than an APY. Tests: module 22
now 5 tests. Daemons and tonight's tasks untouched.

Round 90 complete (2026-09-05): ITEM 13 PHASE 1 - AMM QUOTING ENGINE + REWARDS
SIMULATOR (registry line 279). NEW cross_market/amm_rewards.py: Avellaneda-
Stoikov quotes (reservation = fair - q*gamma*sigma^2*tau; half-spread = risk
term + (1/gamma) ln(1 + gamma/k); tick grid; never cross fair; an inventory
limit removes the growing side; a volatility spike widens, a larger one
pulls; event windows pull; optional pull inside the rewards window), the
programme's order score ((v - s)/v)^2 * size inside the max spread and above
the min size, Q_min two-sided in the 0.10-0.90 band and one-sided outside,
pool share against a competitor Q INPUT; a per-minute simulator over a
synthetic or supplied fair path with Poisson retail fills
(A*exp(-k*cents)); PAPER maker receipts (strategy polymarket_amm, fee 0)
under cross_market/data/paper_receipts; HALT.flag refuses (exit 3). The
roadmap's "20-40% APY" is unmeasured and the module says so in its output:
pool size and competitor liquidity are inputs, not measurements. Tests:
master MODULE 22 (4 tests, no network). Daemons and tonight's tasks
untouched.

Round 87 complete (2026-09-05): ITEM 12 PHASE 1 - OFFLINE ENGINE + MEASUREMENT
INSTRUMENT (registry line 273, not 181 as the prompt said). NEW
cross_market/latency_sniper.py: pre-registered RULES map an event payload to
one market's YES/NO (kind + field + op + value; a numeric rule needs a
numeric payload, anything else says nothing); a CLOB BOOK snapshot is walked
best-first taking each level only while the event's confidence clears the
Tax Reserve Agent's after-tax BREAKEVEN at that level's fee-adjusted odds
(hook.after_tax_edge_hurdle), capped by quarter-Kelly of the safe bankroll
and hook.max_position_size; a NO outcome hits YES bids at (1 - bid).
Fail-closed: HALT.flag refuses everything (exit 3), confidence < 0.99
refuses everything, a book older than 10 s or from the future is skipped,
a market without a rule is never touched. The ONLY execution is PAPER
receipts (strategy latency_sniper, paper:1) under
cross_market/data/paper_receipts; there is no live path in the module.
`--record --tokens` stamps CLOB depth (the one read-only GET) into
cross_market/data/clob_books/ (ignored) so the roadmap's "10-50% per event"
can be MEASURED by replaying rules against stamps (`--now`) before anything
else is built. Sample rules with placeholder tokens:
cross_market/experiments/sniper_rules.sample.json. Tests: master MODULE 21
(9 tests, no network). Daemons and tonight's tasks untouched.

Round 85 complete (2026-09-05): ITEM 10 PHASE 1 BUILT AS RATIFIED (5d39bf6).
cross_market/interfaces/c2_bot.py - Telegram long polling (outbound only),
fail-closed: no TELEGRAM_BOT_TOKEN or empty C2_ADMIN_IDS -> refuses to start
(exit 2); group chats, unlisted senders and updates older than
--stale-seconds (120) are logged and never answered; every update is
acknowledged (offset persisted to cross_market/data/c2_bot_offset.json)
BEFORE it is acted on, so a crash can never replay a /halt. Commands:
/status, /bankroll, /positions (PAPER), /halt|/killall (two-step CONFIRM ->
writes DEV/HALT.flag JSON {who, when, reason}; never kills a process),
/help; /resume is console-only. Transport is one injectable http callable;
the token is redacted from every log line and --status prints set/unset.
pid lock cross_market/data/c2_bot.pid (mark c2_bot), --status/--json,
--once, --dry-run, --interval, --log-file. start_c2_bot.bat guarded and
detached (interval 25 s long poll). Tests: cross_market/tests/test_c2_bot.py
= MASTER MODULE 20 (11 tests, no network). .gitignore: the offset file and
HALT.flag. NOT STARTED LIVE: the launcher is ready; starting it is the
operator's call once the two env vars exist. Daemons untouched. Live 16:2xZ: `c2_bot --status` on the real machine: STOPPED, token unset, admins 0, HALT.flag absent (exit 3) - correct fail-closed state; nothing started.

ROUNDS 81-83 (2026-09-05, 15:14Z-15:32Z): HOLDS, LOOP SUSPENDED. Antigravity
ratified suspending rounds until the Item 18 maiden protocol output exists.
Gate opens 2026-09-06T01:39:49Z = 9:39 PM Eastern 2026-09-05; the exporter
(pid 56412) runs the regression by itself. NEXT SESSION STARTS WITH, from DEV:
  python -m cross_market.maiden_protocol          (paste all of it)
  restart_polymarket_watcher.bat                  (inside 60 min; sweeps a dead lock too)
  python -m cross_market.ingestors.polymarket_fetcher --status   (must end: carries tags)
If the laptop was shut down after ALL CHECKS PASSED, the morning protocol shows
[FAIL] loop_running and [FAIL] series_ready as shutdown artifacts: run
start_cross_market_exporter.bat, then the two lines above, then the protocol
again after the next poll. Tier 2b needs 24 continuous hours after the restart.

Round 80 PREPARED (2026-09-05): IMPORT-TIME DEFAULTS CLOSED OUT. Ruling
79-3 applied: poll() in both fetchers defaults `sleep` to a call-time
`_sleep` helper (as `log` defaults to `_emit`); a tree-wide grep outside
tests finds no `= time.sleep` or `= print` default left. Directives
80-1/2/3 (the maiden protocol ~01:40Z 2026-09-06, restart_polymarket_
watcher.bat inside the hour after it, Tier 2b ~24 h later) are time-gated
and were not run. 2 new tests. Watcher pid 49812 and exporter pid 56412
untouched.

Round 79 PREPARED (2026-09-05): THE POST-MAIDEN RESTART IS ONE COMMAND.
Directives 79-1/2/3 are all time-gated (protocol ~01:40Z 2026-09-06, the
watcher restart inside the hour after it, Tier 2b ~24 h later) and were
not run. Directive 79-2's three manual steps are now
`restart_polymarket_watcher.bat`: fetcher `--stop` (terminates ONLY a live
lock holder whose command line is a watcher - a stale lock is swept, a
foreign process is never a target; exit 0 stopped / 1 still alive / 3
nothing running) -> the guarded launcher -> `--status`, whose new
"tags:" line says whether the newest macro stamp carries the Round 76
`tags` (the Directive 79-2 verification, one command). No if-blocks in
the new bat. 2 new tests. Watcher pid 49812 and exporter pid 56412
untouched; the restart itself waits for the verdict.

Round 78 PREPARED (2026-09-05): AUDIT ITEM CLOSED, NOTHING LIVE TOUCHED. The
Round 78 prompt again reached this session truncated after Directive 78-1
(the protocol at ~01:40Z 2026-09-06, time-gated, not run) - both times the
cut lands at a ```cmd fence, so the paste is losing everything after it.
Ratification 77-3 applied: Sports_Desk/ingestors/odds_fetcher.poll() no
longer binds `log=print` at import (`_emit` resolves print at call time);
a tree-wide grep confirms no `= print` default remains outside tests.
1 new test. Exporter pid 56412 and watcher pid 49812 untouched.

Round 77 PREPARED (2026-09-05): TIER 2b PRE-REGISTERED IN A NEW FILE. The
Round 77 prompt reached this session truncated after Directive 77-1 (the
protocol at ~01:40Z 2026-09-06, time-gated, not run); Decision 3 of that
prompt was executed: cross_market/experiments/lead_lag_tier2b.meta.json
registers membership analysis (a market in BOTH subfamilies when its Round
76 `tags` list names both) with the Tier 2 bars copied verbatim, its own
series (tagged macro stamps only, same 24 h / 200 / 60 min bar, counted from
the first tagged stamp - i.e. after the post-maiden watcher restart), and a
reading rule: report Tier 2 and Tier 2b side by side; a disagreement is
the finding, Tier 2b never overrides Tier 2. Code: lead_lag
load_drop_records(subfamily_from="label"|"tags"), record_tags,
tagged_stamped_moments, CLI --subfamily-from tags (untagged records are
skipped, never inferred from `sport`; --check-data and the gate count
tagged stamps only). lead_lag_tier2.meta.json untouched (asserted). No
live process touched. 1 new test.

Round 76 PREPARED (2026-09-05): TAGS RECORDED ON DISK, WATCHER NOT RESTARTED.
Directive 76-1 (the protocol at ~01:40Z 2026-09-06) is time-gated and was
not run - `python -m cross_market.maiden_protocol` is the command. Directive
76-2 is implemented but INERT: collect_live_questions records every tag a
market was fetched under in `tags` (list, --tags order) while `sport` keeps
the first tag's label, so the matcher, Tier 1 and the registered Tier 2
filter read what they read before. The running watcher (pid 49812) still
executes the Round 75 code and its drops carry no `tags` field until it is
restarted - deliberately left for AFTER the maiden verdict (Ratification
75-3): `taskkill /F /PID <pid>` then start_polymarket_watcher.bat, inside
60 min so the series stays continuous. Using `tags` in the Tier 2 filter
would let a dual-tagged market count in both subfamilies - a change to the
registered analysis, left for Round 77. 1 new test.

Round 75 PREPARED (2026-09-05): the two execution directives are time-gated
to the maiden run (~2026-09-06T01:39:49Z) and were NOT executed - they are now
ONE command, and two flaws that could have buried the maiden run are fixed.
`python -m cross_market.maiden_protocol` (exit 0 all checks / 3 not yet /
1 a check failed) runs Directive 75-1 (lock, READY, last run, the `lead-lag:
RAN` log line, the run-at marker under the Item 18 header, the cooldown
count-down) and, ONLY once Tier 1 has written its verdict, Directive 75-2
(both subfamilies under the registered bars, the meta file read, never
written). Safety: lead_lag.run reports a database it could not read as
`price_error` ("price series unreadable") and the refresher does NOT record
it - no note, no cooldown, the next 15 s cycle retries (before: a locked DB
became an "insufficient" verdict with a 24 h cooldown). An "insufficient"
result is still recorded but retried after `--lead-lag-retry-hours` (default
1) rather than 24 h; the block states its own cooldown ("next run after
`N h`", titan_correlator.lead_lag_next_run_hours) and the refresher honours
what was written. NEEDS RATIFICATION: the 1 h retry (set 24 to restore).
4 new tests. Nothing in polymarket_fetcher.py was touched (Ratification 74-2).
Live 10:28Z: `python -m cross_market.maiden_protocol` against the real loop printed [PASS] loop_running, five [WAIT] checks, series NOT READY (span 8.7h, points 104), ETA 2026-09-06T01:39:49Z, log 293 gated / 0 failed / 0 runs, "tier 2: skipped - Tier 1 has not run yet", exit 3. The exporter was then restarted through the guarded launcher so the Round 75 safety code is the code that runs the maiden run: pythonw pid 56412 holds the lock (35080 terminated first); watcher pid 49812 untouched.

Round 74 complete (2026-09-05): ONE EXPORTER LOOP, TIER 2 PRE-REGISTERED.
Directive 74-1: cross_market/interfaces/obsidian_exporter.py holds
cross_market/data/cross_market_exporter.pid for --watch (pid_lock, mark word
"cross_market" so a Sports Desk exporter never passes as the holder), --status
(exit 0 running / 3 stopped; also prints the Item 18 state: last lead-lag run
from the Titans note, macro series readiness, ETA), --json, --pid-file.
start_cross_market_exporter.bat is guarded by --status like the watcher's
launcher, and start_all_ecosystem_sync.bat calls it behind `if errorlevel 3`
instead of opening a console loop - every loop the sync bat starts for the
arb desk is now detached and single-instance. Ruling 74-2: Tier 1 untouched;
Tier 2 pre-registered in cross_market/experiments/lead_lag_tier2.meta.json
(counts only, no subfamily correlation run) and enforced in code:
lead_lag --subfamily fed-rates|crypto reads the `sport` label the fetcher
stamped (drops carry no tag_slug), --latency-minutes 5 reports a peak inside
the poll interval as "contemporaneous repricing ... latency, not a lead".
4 new tests. Live 10:01Z: Arb exporter restarted through the guarded launcher - pythonw pid 35080 holds cross_market/data/cross_market_exporter.pid (the pre-lock loop 3556 was terminated first); a second launcher run printed "already running - kept"; --status: RUNNING, last run never, macro series NOT READY (span 8.3h, points 100), ETA 2026-09-06T01:39:49Z. Watcher pid 49812 untouched.

Round 73 REVIEW (end of 2026-09-05): MAIDEN RUN READS THE MACRO FAMILY, LOOPS
DETACHED. Research showed the forced maiden run was already "sufficient" -
but it correlated every drop (1,084 markets incl. 400 NFL questions) while
the gate counts macro stamps. lead_lag.load_drop_records/run/--family now
filter by tag family and LeadLagRefresher passes family="macro"; the macro-
only preview: 413 markets, 384 shifts, best lag -33 min, corr -0.195 -> "no
measurable lead-lag" (|corr| < 0.2). That is the likely honest verdict
tomorrow. Resilience: cross_market/console_log.tee_stdout + --log-file on
the watcher and the Arb exporter; start_polymarket_watcher.bat and
start_cross_market_exporter.bat launch both DETACHED (pythonw,
Start-Process) with logs under data/ (ignored); the sync bat calls the
watcher launcher. Both loops were restarted detached tonight, so the
01:39:49Z opening is unattended. 3 new tests. Live 09:19Z: watcher pythonw pid 49812 (lock 49812, stamp 09:18:49Z, 12 min after the last console stamp - series continuous), Arb exporter pythonw pid 3556 (log: lead-lag gated NOT READY), maiden regression due ~2026-09-06T01:39:49Z on macro drops.

Round 73 complete: ITEM 18 MAIDEN RUN AUTOMATED BEHIND THE SENTINEL GATE.
The Cross-Market Arb exporter's loop carries a LeadLagRefresher: every
cycle it re-reads data_readiness on the stamped drops; while NOT READY it
does nothing; when READY it runs lead_lag.run() for --lead-lag-coin (BTC)
once, writes the result into Cross_Market_Titans.md between
<!-- lead-lag-horizon --> markers as "## ⚡ Lead-Lag Predictive Horizon
(Item 18)" (after the sentinel card; user notes untouched), and then waits
--lead-lag-cooldown-hours (24) measured from the run-at comment INSIDE the
block, so a restarted exporter honours the same cooldown. Insufficient
results are rendered honestly and still count as a run. --no-lead-lag
disables it. Round 72 was verification only. 3 new tests. The 01:39:49Z
opening tomorrow now needs no operator - only a running sync bat.

Round 71 complete: THE 24/7 LAUNCHERS THROTTLE THE MARKET DASHBOARD.
start_all_ecosystem_sync.bat and HL_Monarch/scripts/launchers/
start_obsidian_sync.bat start the HL obsidian watcher with
--throttle-seconds 60 (Ruling 70-1); the code default stays 0 for
on-demand calls. A test pins both launcher lines and the default. The
running "Monarch Obsidian Sync" window (if any) predates the flag - restart
it from the launcher to pick it up.

Round 70 complete: OPTIONAL WRITE THROTTLE FOR HyperLiquid_Monarch.md.
`main.py obsidian --watch --throttle-seconds N` (and the module CLI) skips
rewriting the market dashboard while its last write is younger than N
seconds, judged on the file's mtime so it holds across processes; every
other note and every number are untouched (Ruling 69-2: no coarsening).
Default 0 = unthrottled; the loop logs "(market dashboard throttled)".
1 new test.

Round 69 complete: CLOCK FRAGMENTS VOLATILE IN THE HL COCKPIT NOTES.
analytics/obsidian_links.normalize_for_hash (shared by HyperLiquid_Monarch,
Trading_Terminal, Bot_Control, the whale notes and the hub) now substitutes
clock-derived FRAGMENTS inside substantive lines before hashing: "Ns ago"
(DB / Polymarket engine freshness), backticked "NN.Nh" (position Duration)
and the Realised APR cell (accrued / notional / hours held, which ticks with
the clock); PIDs, equity, accrued funding, entry APRs, prices and config
stay hashed. 1 new test. Live: two HL syncs 16 s apart: HyperLiquid_Monarch REWRITTEN, Trading_Terminal unchanged, Bot_Control unchanged, Monarch_Hub unchanged.

Round 68 complete: TICKING AGES ARE VOLATILE IN Sports_Desk.md. The sports
exporter's change hash now replaces every elapsed-age fragment (Feed
Liveness `X ago`, "newest quote X ago", "newest X min ago, lookback", a
hit's "Ns old") with <VOLATILE_TIME> while keeping the verdicts and counts,
so a note whose only change is its clocks is not rewritten, and a flip
[ACTIVE] -> [STALE], a new move or a hit ageing out still rewrites at once.
1 new test.

Round 67 complete: FEED LIVENESS IN THE Sports_Desk.md HEADER, SECTION CAP
WITH OVERFLOW, KNOBS DOCUMENTED. The Desk Snapshot callout carries
"**Feed Liveness**: `X ago` [ACTIVE|STALE]" (or `none` [NO QUOTES] /
`unavailable`), judged on the newest quote in the whole table against
FEED_STALE_SECONDS. The stale section shows at most 8 moves and 8 hits and
appends "*(and N more sharp move(s) / M more stale hit(s)... run
`monarch_shark --stale` for the full list)*" when more exist.
FEED_STALE_SECONDS (pipeline alive?) and MAX_QUOTE_AGE_SECONDS (quote
actionable?) are documented as separate knobs that share a value today.
2 new tests. Live note header: `15.7h ago` [STALE] - the sports feed is
deliberately idle until real odds drops arrive (Ruling 66-1).

Round 66 complete: STALE-PANEL FEED LIVENESS, --json, Sports_Desk.md SECTION.
scan_market_db measures the newest quote in the WHOLE measurements table
(newest_quote_at / newest_quote_age_seconds) and sets feed_warning when it
is older than 15 min or older than the lookback ("feed stale / ..."); the
panel header reads "[STALE] newest quote: X min ago | lookback: N min |
sharp moves: M | stale retail: K" and prints "[WARN] ..." beneath (CLI and
menu [t]). scan_to_dict + `monarch_shark --stale --json`. Sports_Desk.md
carries "## 🕒 Stale Quotes & Market Consensus Latency" from collect()
(display only; an empty feed says "No sharp moves detected in last 180m
(newest quote none)" under a feed warning). 3 new tests.

Round 65 complete: STALE-QUOTE PANEL IN THE MONARCH SHARK (display only).
Betslip.show_stale(lookback_minutes, **thresholds) scans the desk's own
fair_odds_measurements through Sports_Desk.engine.stale_quotes and renders
the sharp moves and the retail quotes still priced off the old consensus;
CLI `monarch_shark --stale [--lookback-minutes 180]`; menu [t]. Nothing
stakes from the panel and it says so. 3 new tests.

Round 64 complete: PAPER ARB CLOSED-LOOP DRILL, STALE-QUOTE ENGINE GROUNDWORK.
cross_market/paper_drill.py drives Betslip.stake_cross_market(paper=True)
over synthetic equal-payout pairs, writes two paper receipts per dutch
(tagged drill:1), shows the arb desk flip from "assumed (< 10 arb fills)"
to "measured (paper_receipts receipts, N fills / E arbs ...)" through the
risk simulator's own loader and --calibration-report, then REMOVES its
receipts unless --keep (synthetic history must not be "measured" later).
Sports_Desk/engine/stale_quotes.py is the Item-11-style core (sharp move =
>= 2 pts at >= 0.5 pt/min; stale retail = latest quote >= 60 s before the
move's end, <= 15 min old, >= 2 pts cheap vs the sharp post-move price;
drifts counted as overpriced), pure functions + a fair_odds_measurements
scanner, no execution. 7 new tests; master suite is 19 modules.

Round 63 complete: MONARCH SHARK CROSS-MARKET STAKING WIRED TO THE DUTCH
RECORDER, PAPER MODE, PATH REFUSAL, ARB LEGS OUT OF SPORTS HISTORY. Betslip.
stake_cross_market(result, pair) records an executed cross-market dutch via
cross_market.execution_log.record_dutch (refused wholesale when
worst_after_tax < capital, or without exactly one Polymarket leg; confirm
prompt; the slip's clock stamps both legs); menu entry [x]. record_dutch
(paper=True) writes BOTH legs as receipts under cross_market/data/paper_receipts
(ignored by git) with paper:1 notes and touches neither the Tax imports nor
placed_bets (Ruling 34-D). The recorder CLI refuses explicit --sports-db /
--imports-dir paths that do not exist (exit 2, Ruling 63-4).
_measure_sports_history excludes bet_kind "arbitrage" (Ruling 63-1). 7 new
tests; the suite crossed 2,500.

Round 62 complete: CROSS-MARKET DUTCH RECORDER, RECEIPT READER TOLERANCE,
COMPACT CALIBRATION REPORT. New cross_market/execution_log.py: record_dutch()
writes the Polymarket leg as an execution receipt (strategy dutched_arb, venue
polymarket, ONE shared timestamp, notes carry arb_group / gross / cost / legs /
book_leg) and the sportsbook leg into Sports_Desk placed_bets (bet_kind
arbitrage, same arb_group); never raises; CLI `python -m
cross_market.execution_log --pm-market ... --book ... --odds ... --stake ...`
for today's manual executions, exit 0 complete / 1 incomplete / 2 refused.
risk_simulator._measure_arb_history reads fills_*_dutched_arb*.csv (any
venue), groups by arb_group note first and a 60 s timestamp window second,
prices from a gross: note (cost: for capital) before falling back to
1/sum(BUY prices) - 1. --calibration-report shows the last 7 daily rows per
coin (--last-days N, --all). 7 new tests; master suite is 18 modules. Live:
still no receipts, no settled wagers, 3 usable days per coin.

Round 61 complete: PER-COIN SHOCK MEDIANS, CALENDAR-DAY CADENCE, ARB RECEIPT
HISTORY, --calibration-report. stress_calibration() judges each held perp
against its OWN median daily vol (shock = > 3x it), qualifies a coin at >= 14
distinct days, and averages shock probability / multiplier over qualifying
coins (Ruling 61-1). Sports cadence = settled / calendar days spanned
(Ruling 61-3). _measure_arb_history reads fills_polymarket_dutched_arb*.csv
receipts in Tax_Reserve_Agent/data/imports (+ processed/): fills sharing a
timestamp are one execution, >= 2 BUY legs price a dutch (1/sum - 1), >= 10
fills replace arb_per_day / gross return / std / capital, else "assumed (< 10
arb fills)". `python -m cross_market.risk_simulator --calibration-report
[--json]` prints the per-coin daily vol table with shock days, the sports
settlement line and the arb receipt line for auditing before the 14-day mark.
3 new tests. Live: no coin qualifies yet (4 days), no settled wagers, no arb
receipts - every calibration says so.

Round 60 complete: STRESS CALIBRATION FROM REALIZED VOL, SPORTS SETTLEMENT
HISTORY, FRACTIONAL CADENCE. load_live_inputs now measures stress_day_prob
and stress_vol_multiplier from hyperliquid_data.db when >= 14 distinct days
of hourly marks exist for the held perps (shock coin-day = daily realized
vol > 3x the pooled median; multiplier = mean shock vol / median), else
"assumed (< 14 days of marks)"; and reads placed_bets for >= 20 settled
wagers (cadence = settled / active days, win rate = wins / (wins + losses),
pushes excluded, mean odds), else "assumed (< 20 settled wagers)". Fractional
bets per day place the remainder as one extra wager with that probability.
start_all_ecosystem_sync.bat passes --risk-stress 0.5 to the Arb exporter so
the card always carries the stress table. 3 new tests. Live: both
calibrations fall back today (3.9 days of marks, 0 settled wagers) and say so.

Round 59 complete: RISK SENTINEL AUTO-REFRESH, SYSTEMIC STRESS FACTOR. The
Cross-Market Arb Obsidian exporter carries a RiskRefresher: Risk_Sentinel.md
is re-simulated on the first cycle, every --risk-every cycles (60 = 15 min at
15 s) or as soon as the paper book's signature (equity, positions, coins)
moves; 20,000 paths + a 5,000-path grid (~5 s) so the loop is not stalled for
the CLI's 25 s; write_note_if_changed keeps unchanged cards off disk.
risk_simulator gained --stress-correlation (0..1) with --stress-day-prob
(0.02) and --stress-vol-multiplier (3): on a shock day perp vol is
multiplied, funding compresses and flips negative, arb leg failures double,
all together; the report and card show baseline vs stressed VaR99, practical
ruin, cash buffer and desk P&Ls. Zero correlation is bit-identical to an
unstressed run. 3 new tests.

Round 58 complete: ITEM 19 MULTI-DESK MONTE CARLO RISK-OF-RUIN SIMULATOR.
cross_market/risk_simulator.py runs one joint numpy simulation of the trading
bankroll across the basis book (funding level decaying from the measured mean
toward a long-run APR, hourly AR(1) noise, Student-t perp moves, liquidation
past 1/leverage - maintenance), quarter-Kelly sports wagers, Poisson arb
arrivals with leg failures, and quarterly tax escrow (NJ 32.37%). 100,000
paths x 365 d in ~10 s (only running equity / peak / drawdown are kept).
Reports hard ruin (equity <= 0) AND practical ruin (-50% drawdown), max-
drawdown VaR 95/99 at 30 d and the horizon, terminal equity, escrow, per-desk
P&L, and a Kelly shrinkage grid (max median log growth s.t. practical ruin
<= 5% and allocation <= 100%) with the binding constraint named. Inputs are
measured from basis_paper_state.json, hyperliquid_data.db (funding mean/std/
persistence, realized vol of the held coins), sports_market.db edge rows and
Tax_Reserve_Agent.config, else labelled assumed. CLI --iterations/--json/
--inputs/--assume-defaults/--no-grid/--no-vault; writes
obsidian_vault/Risk_Sentinel.md. 12 tests; master suite is 17 modules now.

Round 57 complete: SENTINEL CARD IN Cross_Market_Titans.md, LEAD-LAG LIVE GATE.
The Titan correlator renders a "Lead-Lag Data Readiness Sentinel (Item 18)"
callout between HTML markers (verdict, segment points/span/rate, blocking
reasons, ETA, checked time) from data_readiness over its own drop dirs; the
Cross-Market Arb Obsidian exporter refreshes JUST that block every cycle
(refresh_titans_sentinel; a missing note is never created by it). The
block's clock line is excluded from the change hash, so the note is
rewritten only when the numbers move. lead_lag without --drops/--events now
runs the sentinel first and refuses (exit 3) until READY unless --force.
3 new tests. Live: NOT READY, 16 points / 1.1h @ 13.2/h since 01:39Z, ETA
2026-09-06T01:39Z.

Round 56 complete: WATCHER --status, SYNC-BAT GUARD, LEAD-LAG READINESS
SENTINEL. polymarket_fetcher --status [--json] reports the lock holder (pid,
start, command), a stale lock, and the newest stamped drop per family; exit 0
running / 3 stopped. start_all_ecosystem_sync.bat runs it first and keeps a
running watcher instead of spawning a refused twin. lead_lag --check-data
(alias --status) [--family macro|sports|any] [--json] measures the LATEST
CONTINUOUS SEGMENT of stamped drops (no gap > 60 min) against the bar (span
>= 24h and >= 200 points, watcher still adding) and prints the ETA as the
later of the span clock and the points clock; exit 0 ready / 3 not. 9 new
tests. Item 18's first live run stays queued until the sentinel says READY.

Round 55 complete: WATCHER PID LOCK, WATCHDOG GAVE UP BADGE. The Polymarket
watcher (--watch) takes a single-instance lock keyed to its drop folder
(<folder>/polymarket_watcher.pid, or --pid-file); dead / corrupt / not-a-
watcher pid files are swept, a live watcher makes the newcomer print
already_running and exit 0, orderly exits release (atexit + SIGINT/SIGTERM/
SIGBREAK). cross_market/ingestors/pid_lock.py mirrors the supervisor's
semantics without importing across trees, and its liveness probe never uses
os.kill(pid, 0). The read-only dashboard header shows a red WATCHDOG GAVE UP
badge (relaunch count, the launcher to run) while the Round 54 ceiling is
reached; it clears on service_back. The claim is an exclusive create, so two
starters that both saw a stale file cannot both run. Watcher restarted under
the lock and a second watcher proved to refuse. 8 new tests.

Round 54 complete: WATCHDOG CEILING + ABANDONMENT ALERT, USER-LEVEL WEBHOOK
FALLBACK, LAUNCHER DETACHMENT ROOT CAUSE FIXED. The dashboard watchdog gives
up after SERVICE_WATCHDOG_MAX_RELAUNCHES (3) relaunches that left the service
dead, logs service_abandoned and alerts once (own cooldown key); the service
coming back resets it. WebhookAlerter.user_env reads DISCORD_WEBHOOK_URL /
TELEGRAM_* from os.environ and then from the USER-level registry value, so a
process born before the variable existed still alerts (tests neutralise the
fallback via tests/conftest.py). start_collector.bat launches the supervisor
with PowerShell Start-Process: a caller that captures the launcher's output
returns at once instead of blocking for the service's lifetime. Service and
the multi-tag Polymarket watcher restarted with the variable exported; the
dashboard runs without it and alerts through the registry fallback (proved
from a fresh variable-less process). 2 new tests.

Round 53 complete: DETACHED SUPERVISOR, DASHBOARD WATCHDOG + ALERTS, TAG-FAMILY
DROPS, LIVE WATCHER WIRED. start_collector.bat now launches the supervisor
under pythonw (no console window to close; the logger skips its console
handler when there is none); a fresh supervisor removes stale pid files
before claiming the lock. A read-only dashboard whose service dies logs it,
alerts through WebhookAlerter, and issues the detached relaunch at most once
per 5 min; a status file older than 2h alerts once per episode. The
Polymarket watcher writes polymarket_sports.json and polymarket_macro.json
separately (stamped copies carry the family); start_all_ecosystem_sync.bat
starts it with --tags sports,crypto,fed-rates. The real drop dir now holds
LIVE sports + macro questions (one-shot). 5 new tests.

Round 52 complete: STAMPED POLYMARKET DROPS, MULTI-TAG WATCHER, LEAK FIX, VAULT
TRACKED. `--watch` now writes a stamped copy (`polymarket_<UTC stamp>Z.json`)
beside the canonical file on every price change and prunes copies older than
192h by the stamp in their name, so Item 18 gets its probability series.
`--tags sports,crypto,fed-rates` fetches several Gamma tags in one watcher
(non-sports by verified `tag_slug`, labelled by slug, narrowed by `--keywords`).
The unclosed read-only connection in find_market_probability is closed on the
no-table path. open_dashboard.bat (Antigravity's root launcher) and the five
new whale dossiers are tracked. 5 new tests. No collector code; no restart.

Round 51 complete: MEASURED MACRO SIGNALS & ITEM 18 LEAD-LAG (OFFLINE). The
Titan note's macro block is no longer three hard-coded narratives: Polymarket
probabilities are looked up in whale_trades and in drop files (keyword groups
for a Fed cut and a BTC $100k milestone), HyperLiquid flow is measured from
latest_snapshots/asset_snapshots (OI-weighted funding APR, total OI, 24h OI
change) and every signal carries measured/source; a missing input is
"[NO LIVE MARKET FOUND]" or "[UNMEASURED: reason]", never a number. New
`cross_market/lead_lag.py` (Item 18) finds the lag at which probability shifts
and perp returns line up, from timestamped drops and a READ-ONLY snapshot DB,
and refuses to name one on thin evidence. 11 new tests; master suite is 16
modules. No collector code changed; no restart.

Round 50 complete - MILESTONE. Titan correlator gains `--scan` / `--report` CLI
with a printed summary (its macro block is labelled as the static placeholder
it is); all five desk notes, the hub, the canvas and today's tax note were
regenerated from their exporters and checked against the live book; the
milestone log below records the round series and the day. 1 new test.

Round 49 complete: DASHBOARD LIFECYCLE LOG, 2-HOUR STATUS WINDOW, PERPDEXS
CHECK AT START-UP. The dashboard appends start / stop / frame_error / crash
(with traceback) to `data/dashboard.jsonl`, so the next unexplained death has
a cause. `read_collector_status` trusts the collector's status file for two
hours by default (COLLECTOR_STATUS_MAX_AGE_SECONDS), so a dead collector's
last write cannot keep a NOVEL DEX badge alive. `_check_perp_dexs()` runs on
the collector's start-up (before the loops) and hourly, so the status file
exists from minute 0. hyna's future as a MIXED dex with its own allow-list is
ratified ahead of time. 2 new tests, 1 extended.

Round 48 complete: MIXED-DEX CRYPTO ALLOW-LIST, NOVEL-DEX DASHBOARD BADGE,
CANDIDATE ROTATION LOG. `CRYPTO_DEXES = {main}`, `MIXED_DEXES = {para}`, and a
perp on a mixed dex is TradFi unless its base is on `MIXED_DEX_CRYPTO_ALLOWLIST`
(para: ANSEM, TOTAL2, BTCD, OTHERS) - para:NEWSTOCK is refused the day it lists.
The hourly cycle writes `data/collector_status.json`; the dashboard header shows
an amber `⚠ NOVEL DEX: ...` badge when it names a dex no settings set knows.
`_sample_pass` logs "Candidate set rotated: [prev] -> [new]" on change. 4 new
tests.

Round 47 complete: STRUCTURAL DEX FAIL-CLOSED, HOURLY DRIFT DETECTOR, ONE
CANDIDATE SLOT PER UNDERLYING. `CRYPTO_DEXES = {main, para}`; a perp on any dex
in neither CRYPTO_DEXES nor TRADFI_DEXES is refused as unclassified before
anyone has heard of the dex. The hourly cycle reads perpDexs and WARNS on any
name no settings set knows. `top_funding_candidates` keeps one slot per
`perp_base_symbol` (best-ranked listing wins) and skips bases already held.
hyna joins the deliberately-refused list so the detector stays quiet. 1 new
test, 2 extended.

Round 46 complete: vntl CLASSIFIED TRADFI, hyna DOCUMENTED MIXED, PRESET-AWARE
CONFIG FALLBACK. `TRADFI_DEXES` gains vntl (Ventuals: ANTHROPIC, OPENAI, SPACEX,
MAG7, SOY, WHEAT...), `UNCLASSIFIED_DEXES` shrinks to abcd, hyna is documented
as mixed crypto + GOLD/SILVER and stays unpolled. A corrupt Bot_Config field now
falls back to the ACTIVE PRESET's value (a "conservative" typo lands on $5k, not
the dataclass's $10k); custom/unknown presets and preset-less fields keep the
dataclass/settings default. Safety-flags-fail-armed ratified. 1 new test.

Round 45 complete: PER-FIELD CONFIG FALLBACK FOR EVERY FIELD & UNCLASSIFIED-DEX
FAIL-CLOSED. Every Bot_Config field now parses on its own through
`_config_number` / `_config_int` / `_config_flag`: a corrupt value warns and
takes that field's default while its neighbours load; the whole-file kill-switch
path fires only when the note cannot be read or yields no fields. The two safety
flags fail ARMED on a malformed value (deviation, see findings).
`UNCLASSIFIED_DEXES` (vntl, hyna, abcd) is documented as excluded from
ACTIVE_DEXES and `spot_symbol_candidates` returns [] for a perp on one, with no
runtime switch. 3 new tests.

Round 44 complete: TRADFI_DEXES GAINS mkts AND io; CONFIG CLAMP FLOOR $10k;
MALFORMED FIELDS FALL BACK WITH A WARNING. `TRADFI_DEXES` now covers xyz, km,
cash, flx, mkts (Markets By Kinetiq) and io (EntropyIO pre-IPO equities), all
verified against the live perpDexs payload. `spot_min_day_volume` clamps to
$10k minimum; a Bot_Config field that will not parse falls back to its settings
default with a logged warning instead of failing the whole reload. The
Penta-Desk header was already in place from Round 43. 1 new test, 1 extended.

Round 43 complete: DEX-LEVEL TRADFI QUARANTINE, CANONICAL DUPLICATE GUARD, ONE
VOLUME MAP PER CYCLE, VAULT FIX & HOT-RELOADED THRESHOLDS. `TRADFI_DEXES`
(xyz, km, cash, flx) quarantines whatever lists there; the symbol set covers
para: and main. `canonical_spot_base` makes ANSEM/UANSEM and FARTCOIN/UFART one
underlying for the duplicate guard, and the guard compares perp bases too. The
hourly cycle builds ONE engine whose volume map feeds the sweep, the scan and
the sampler cache. The Trading Terminal's closed-trades table read keys the
harvester never writes (every swept trade showed $0.00 / 0.0h) - fixed and the
vault refreshed. `allow_synthetic_tradfi_basis`, `spot_min_volume_notional_
multiple` and `spot_min_day_volume` are Bot_Config fields now. 6 new tests.

Round 42 complete: PERP-LEVEL TRADFI QUARANTINE, ILLIQUID-LEG SWEEP & 10x ADV
FLOOR. `ALLOW_SYNTHETIC_TRADFI_BASIS = False` with `SYNTHETIC_TRADFI_SYMBOLS`
(the ruled set plus every TradFi base observed live across the cash/flx/km/xyz/
para dexes): a quarantined perp has NO spot candidates - bare, wrapper or alias.
SPX -> UUUSPX ("Unit SPX6900", the memecoin). `BasisHarvester.sweep_illiquid_
exits` closes positions whose spot leg is under the floor or whose perp is
quarantined; hooked into the hourly accrual cycle and `basis --sweep-illiquid`
(refuses while a service collector is alive). The three dead-leg paper positions
were swept with the service stopped. Floor multiple 5x -> 10x ($100k at $10k).
3 new tests.

Round 41 complete: SYNTHETIC EQUITY QUARANTINE, DYNAMIC SPOT FLOOR, ILLIQUID-LEG
REPORTING & UNMAPPED-SPOT TELEMETRY. Tokenised equities (NVDAX, TSLAX, EQ*)
live in `SYNTHETIC_EQUITY_ALIASES` and are ignored while
`ALLOW_SYNTHETIC_EQUITY_BASIS = False`; the spot floor is
`effective_spot_min_volume() = max($50k, 5 x basis_notional_usd)`; the "U"
wrapper now outranks the bare name on ties and in no-volume calls; the paper
book tags positions whose spot leg is under the floor `[ILLIQUID SPOT]` (three
of five live); `python main.py basis --unmapped-spot` lists liquid spot tokens
no perp resolves to (13 live). 4 new tests.

Round 40 complete: SPOT ALIASES, LIQUIDITY-MAXIMISING HEDGE SELECTION & SPOT
DECIMALS FIX. `SPOT_SYMBOL_ALIASES` (hand-kept, verified against live
fullNames) lets `spot_symbol_for` see wrappers that are not "U" + name (UFART,
XMR1, NVDAX...); with `spot_volumes` it picks the MOST LIQUID of several hedges
(para:ANSEM -> UANSEM $928k/day, not ANSEM $1.5k); the spot leg's szDecimals
is now read for the spot symbol itself (every wrapped hedge came back None
before); SPOT_MIN_DAY_VOLUME raised to $50k (32 of 499 tokens). The paper
state's para:ANSEM spot leg was rewritten to UANSEM while the service was
stopped. 3 new tests.

Round 39 complete: SPOT LIQUIDITY GROUNDING & NET-APR CANDIDATE RANKING. A
spot TOKEN is no longer a spot MARKET: `get_spot_universe` keeps only tokens
whose best spot pair turned over >= SPOT_MIN_DAY_VOLUME ($10k) in 24h, read
from spotMetaAndAssetCtxs (46 of 499 tokens live). TSLA/AVGO spot did $0 while
their HIP-3 perps traded tens of millions; COIN/NVDA have a token and no pair.
Sampler candidates with a spread on record rank on net APR. 5 new tests.

Round 38 complete: SPOT-GROUNDED CANDIDATES, SPREAD CEILING & CONCENTRATION
GUARD. Funding candidates for the spread sampler are now decided by
`spot_symbol_for` against the live spot universe (the ':' prefix rule was wrong
both ways) and pre-filtered by the OI/volume floors; the basis spread ceiling
now reaches every costed row in the scan AND the harvester's own gate (para:AVGO
had entered at 35 bps against 25); one paper position per spot symbol
(para:AVGO + xyz:AVGO were both hedged with AVGO); the stalled-service threshold
is derived from REST_POLL_INTERVAL with a 45s floor; Bot_Config.md's preset label
is "custom" to match its 5 slots. 12 new tests.

Round 37 complete: STALLED-SERVICE DETECTION, CANDIDATE SPREAD SAMPLING & REPO
UNTRACKING. The dashboard header has a fifth state - a live service that has
written nothing for 45s shows STALLED in red; order book sampling now runs
held positions > top-5 positive-funding candidates > rotated > core, so a
spread exists before an entry instant; five more runtime/cache/backup files
are untracked and ignored. A latent Round 34 flake (same-second drop filenames
overwriting) is fixed. 5 new tests.

Round 36 complete: READ-ONLY DASHBOARD, POSITION-FIRST SAMPLING & REPO CLEANUP.
`main.py dashboard` no longer starts a collector while a service collector is
alive (Ruling 3.A) - it is a read-only viewer with a live header badge, and
falls back to standalone ingestion only when no service exists. Held basis
positions are sampled first. Runtime `.pid` / `.jsonl` files are untracked and
ignored; Antigravity's Trading Terminal note change is committed (4af4f51).
8 new tests.

Round 35 complete: SPREAD ALIGNMENT, L2 SPREAD SAMPLING & SUPERVISOR HARDENING.
Each spread leg is stored under its OWN signed handicap (Ruling 5.B) and the
cross-market sample now matches 7 of 7 questions; the collector that owns
maintenance samples top-of-book spreads for a bounded coin set into
`orderbook_snapshots` (Ruling 5.C), which joins the fail-closed set; the
supervisor holds the host awake (Ruling 5.A); a live PID counts as the service
only if its command line says "collector", and the dashboard's embedded
collector re-decides ownership every cycle. 21 new tests.

Round 34 complete: INCREMENTAL PERSISTENCE & DATA INGESTION. The pruner now
reduces raw rows to `basis_realised_windows` and `cascade_excursions` BEFORE
deleting them (never pruned; Ruling D's 720h standard is now reachable);
Polymarket sports questions flow into `Sports_Desk/data/polymarket_drops/`
(`Cross_Market_Arb.md` shows 6 matched pairs, 0 clearing); the odds fetcher
polls and drops only on price change; `Canvases/Sovereign_Penta_Cockpit.canvas`
renders all six notes around the tax reserve. **The collector was restarted** -
it had been pruning at 72h for 15 hours after Round 33 said 192 (see findings).
58 new tests.

Round 33 complete: DATA GROUNDING. Retention raised to 192h; the bankroll gate
now FAILS CLOSED on an empty ledger (config placeholder removed, DEPOSIT rows
are the measured balance); Sports_Desk has a real `sports_market.db` for the
first time; Obsidian is a penta-desk cockpit (Sports_Desk.md, Cross_Market_Arb.md,
hub regenerated). 62 new tests.

Round 31 complete: Targets D (exit hysteresis) and E (leverage policy) applied,
and **Item 14 built as a GATED, NON-TRADING module** - see findings. 38 new tests.

Round 29 before it: Item 8, the funding harvester's BUCKET GATE and after-tax
economics (`HL_Monarch/strategies/funding_harvester.py`). The delta-neutral
engine already existed and was left alone; what was missing was the layer
between it and the bankroll. 24 new tests.

Round 27 before it: Item 6, cross-market arbitrage (`cross_market/hybrid_arb.py`,
`matcher.py`, `hud.py`, `--cross-market` on Monarch_Shark). 52 new tests.

Round 26m before it. **The repository now has version history** — it had none
through ~12 rounds of work. Two commits: the baseline (`743496b`, 526 files) and
the reconcile alias (`5e188a5`).

Suites, all offline:

| suite | count |
|---|---|
| master + bridges + cross-market + exporters + ingestors (22 modules, incl. test_titan_correlator, test_lead_lag, test_risk_simulator, test_execution_log, test_stale_quotes, test_c2_bot, test_latency_sniper, test_amm_rewards) | 936 OK |
| HL_Monarch (pytest) | 1083 passed |
| Tax_Reserve_Agent (5 modules) | 546 OK |

Tax config is **New Jersey resident** (Union, 07083): composite 32.37% =
24% federal + 6.37% NJ + 2% buffer, `casual_standard_deduction`.

## What changed

- **`.gitignore` written before the first commit, not after.** `Keys/` holds a
  *screenshot of a HyperLiquid API key*; two live `.env` files; `*.db` carries a
  real tax position. A committed secret survives deletion — it stays in every
  clone — so these never entered history.
- **`quant_trading_lab/` is excluded and that is deliberate.** It has its own
  git repo. Staged from the parent it becomes a bare gitlink: it *looks*
  version-controlled while tracking nothing. It versions itself; the outer repo
  stays out of its way.
- **Three secret-scan hits were checked, not assumed.** The `connection_id` and
  `r`/`s` values in `HyperLiquid/HL_Monarch/execution/wallet_manager.py` are
  EIP-712 test vectors sitting beside `"private_key": "0x" + "11" * 32`. The
  base64 hits in `MoonDev_Quant_Strats/.../chart_benchmark_*.html` are chart
  image data. All false positives.
- **`--reconcile` added as an alias of `--check-sync`** on `monarch_shark`, with
  a test — an argparse alias regresses silently.

## Item 13 plan - AMM and rewards bot (designed and Phase 1 built 2026-09-05, Round 90)

- **What is measurable and what is not.** Spread capture and inventory
  risk are simulated from a fair path and a fill model; the rewards share
  depends on the market's pool and on competing liquidity, neither of which
  this module can observe. Both are INPUTS and the output labels them
  "ASSUMED". No APY is claimed until pools and competitor Q are recorded
  from live markets.
- **Quoting is Avellaneda-Stoikov, clamped for a bounded price.** Long
  inventory shades both quotes down; the growing side is withdrawn at the
  inventory limit; quotes never cross fair and sit on the tick grid.
- **Rewards follow the programme's published shape**: distance-squared score
  inside the max spread, min size, both sides required in the 0.10-0.90
  band. The parameters (rewardsMaxSpread, rewardsMinSize, daily rate) exist
  on Gamma market objects but are NOT recorded by the fetcher yet.
- **Fail-closed**: HALT.flag, event windows, volatility pull, inventory
  limit - each counted with a reason. Paper only; no order path.
- **Phase 2 (not built, needs rulings):** record rewards fields additively
  in the fetcher (post-maiden, it is frozen), record live mids and fills to
  calibrate A and k, then a paper quoting loop against live books before any
  execution decision.

## Item 12 plan - latency sniper (designed and Phase 1 built 2026-09-05, Round 87)

- **What the roadmap claims vs what exists.** "10-50% per event" is
  unmeasured. Phase 1 therefore ships the instrument before the weapon:
  `--record` stamps CLOB depth around a scheduled release; a replay of the
  pre-registered rules against those stamps (`--now <ISO>`) says what was
  actually resting, at what price, for how many seconds. No ROI is claimed
  until that replay has been run on real releases.
- **Rules are pre-registered, never interpreted.** One JSON rule per
  market (kind, field, op, value, outcome_if_true), written BEFORE the
  release and never edited in the event window. A market without a rule is
  invisible to the engine; an event of another kind is ignored; a
  wrong-typed payload resolves to nothing, never to NO.
- **Economics are the Tax Reserve Agent's.** A level is taken only while
  confidence >= after_tax_edge_hurdle(odds)["breakeven_win_probability"] at
  the level's fee-adjusted odds (fee on profit); size = min(quarter-Kelly of
  the safe bankroll at the best level's odds, hook.max_position_size()).
  `--assume-defaults` (fair breakeven, nominal $1,000) exists for research
  without a ledger and says so in its output.
- **Fail-closed.** HALT.flag, confidence < 0.99, stale (> 10 s) or future
  books, missing rules - each refuses or skips with a reason in the output.
- **Paper only.** Receipts under cross_market/data/paper_receipts tagged
  latency_sniper; never the tax imports; no order path exists.
- **Phase 2 (not built, needs decisions):** an event source (scheduled
  releases: FOMC/BLS pages, or a paid feed), a live book poller around
  release times, and only after measured evidence, an execution path with
  its own gate. Latency of the ingestion is the real product; Phase 1
  cannot measure that.

## Item 10 plan - C2 bot (proposed 2026-09-05, ratified unamended, BUILT in Round 85)

Registry line 179: "CENTRALIZED TELEGRAM / DISCORD COMMAND & CONTROL (C2) BOT".
- Transport: Telegram long polling (getUpdates), outbound HTTPS only - no
  inbound port, no webhook on a laptop. Discord commands need a gateway
  websocket + a dependency: Phase 2. Existing outbound Discord webhook may
  mirror replies.
- Process: its own detached pythonw loop (start_c2_bot.bat), pid lock
  cross_market/data/c2_bot.pid via pid_lock (mark "c2_bot"), --status,
  --log-file, --once, --dry-run. Never inside the exporter loop.
- Auth, fail-closed: TELEGRAM_BOT_TOKEN (already read by the HL alerter's
  user_env) + C2_ADMIN_IDS (comma-separated Telegram USER ids, user-level
  env var). Empty allowlist = every message rejected and logged. Private
  chats only (chat.type == private AND from.id allowlisted). Token never
  printed; --status says set/unset.
- Replay safety: persist the last update_id in cross_market/data/
  c2_bot_offset.json; on start drop updates older than 120 s so a /halt
  sent hours ago never fires on a restart.
- Commands (Phase 1): /status (collector_status.json + pid liveness,
  watcher_status, exporter_status incl. the Item 18 line, drop ages,
  memory per pid), /bankroll (MonarchHook get_safe_bankroll,
  get_tax_escrow, after_tax_arbitrage_hurdle, status_line), /positions
  (basis_paper_state.json + Sports_Desk query_placed_bets, labelled
  PAPER), /halt [CONFIRM] alias /killall (two-step; creates DEV/HALT.flag
  with {who, when, reason} - the sentinel dynamic_config already turns
  into emergency_killswitch and the supervisor honours; data daemons are
  NOT killed: they hold no risk and killing them breaks series), /help.
  /resume is CONSOLE-ONLY (delete the flag at the machine): chat can halt,
  only the operator can resume.
- Tests (cross_market/tests/test_c2_bot.py, master module 20): parsing,
  allowlist fail-closed, group chat rejected, stale updates dropped,
  offset persisted, /halt two-step in a temp root, transport injectable
  (no network), replies <= 4,000 chars, token never in output.
- Estimate: Phase 1 ~40 min in one round. Open for ratification: Telegram
  first; HALT.flag-only kill semantics; C2_ADMIN_IDS naming; 120 s stale
  window; console-only /resume.

## Round 123 findings

### The pre-flight hash was whole-vault; telemetry made it a race

- `hash_vault` hashed every `.md` under `obsidian_vault/`. While the 5 exporters were dead (Round 122 night)
  the vault root was static and the guard passed. Once they were restarted, a root-dashboard write every ~15 s
  landed between the before/after hash and failed 'card wrote nothing' intermittently - and the 60 s live loop
  essentially always. Scoping to `wiki/` (no exporter writes there) makes it deterministic without weakening it:
  the card and any accidental real-vault ingest write both land in wiki/.

### Liveness, not mtime, and the case bug behind it

- A dashboard's mtime is not liveness: `write_note_if_changed` skips the write when a desk is idle, so a healthy
  exporter can leave an hours-old file. `telemetry_health` reads the process table instead. Building it surfaced
  that tax and sports had died silently, and that matching a lowercase signature against a mixed-case Windows
  cmdline needs both sides lower-cased - without it the two capitalised desks read as always-down.

### resume_all's proxy was the reported bug, now removed

- R123-1.A.4: each component is recovered on its own signal. The watcher being up says nothing about the five
  telemetry exporters, which is exactly how tax/sports stayed dead behind a live watcher.

## Round 122 findings

### 'The next 24 h window' was not a window

- `cross_market.lead_lag` had no start bound: a run at 22:20 EDT 09-07 would have correlated every tagged
  stamp since 02:25Z 09-06 (48 h), overlapping run 1 by construction and still containing the 9.3 h price
  hole. A 3-run consensus over nested samples is not three observations. `--since`/`--until` filter the
  shifts AFTER detection (a shift is stamped at its later observation, so the first shift inside the bound
  still sees its predecessor); `--check-data` clips its stamps the same way and reports `bounds`.

### What the measurement span is

- The engine loads prices only inside [first shift - (max_lag+1) min, last shift + (max_lag+1) min]. That
  interval is what was MEASURED; the first/last price row is what was FOUND. A gap at the interval's edge
  removes rows without moving the interval, so `dev.measurement` carries the interval and the page shows
  price coverage beside it. On the live probe the two differ by an hour at each end - the padding.

## Round 121 findings

### The 9 h hole reaches Round 120

- `cross_market.lead_lag` reads BTC marks from `asset_snapshots`. The Tier 2/2b window (02:20Z 09-06 to
  02:22Z 09-07) contains the 15:46Z-01:05Z gap: ~39% of the price series was absent. The registration's
  readiness bar (span, points, gap) is about the TAGGED STAMPS; nothing in it looks at the price side. The
  readings stand as recorded; the gap page lists them under `affected_evaluations`, and R120-1.B's
  3-run consensus is the right remedy - the next two windows will not have the hole.

### Two writers of one field, found by hashing twice

- `dev.tests_run` on a lead-lag registration was written by `knowledge.ingest.lead_lag` (count of verdict
  pages) and reset to 0 by `knowledge.ingest.experiments --force` (`setdefault` on a fresh dict). Either
  adapter alone looked right. One definition now: `lead_lag_verdict_count`, imported by both.
- The verdict page's own `tests_run` counted itself once it existed: 1 became 2 on the first re-ingest.
  Excluding the page's own stem fixes it; the relocation would have inflated all four.
- The lead-lag ingest appended a log line on every run. Now only when the page moved (R104-3, the last
  adapter still doing it).

### The watchdog deviation, stated

- R119-1.B item 3 asked for alert/restart on coverage decay (>5 pts drop or <60%). `coverage_pct` is a 24 h
  window: after today's gap it read 62% while the restarted collector was healthy and will stay under 60%
  for most of tomorrow. A restart trigger on it would have restarted a healthy collector hourly. The branch
  therefore restarts on the DIRECT signal - newest snapshot older than 15 min while the child is alive -
  and logs coverage decay as a warning. Antigravity to ratify (R121-1.A).

## Round 120 findings

### The regime page's own table (compiled by knowledge.ingest.lead_lag, not transcribed)

| tier | scope | from | class | regime | lag min | corr | n | at |
|---|---|---|---|---|---|---|---|---|
| 2b | macro_crypto | tags | **polymarket-leads** | insufficient-history | 38 | -0.325 | 910 | 2026-09-07T02:30:34Z |
| 2b | macro_fed-rates | tags | **no-lead** | insufficient-history | 58 | +0.135 | 890 | 2026-09-07T02:30:29Z |
| 2 | macro_crypto | label | **no-lead** | insufficient-history | 38 | -0.138 | 2389 | 2026-09-07T02:30:23Z |
| 2 | macro_fed-rates | label | **no-lead** | insufficient-history | -10 | +0.052 | 2416 | 2026-09-07T02:30:18Z |

### Disagreements (from the same page)

- **macro_crypto**: Tier 2 says no-lead, Tier 2b says polymarket-leads

- How to read it, in the registration's words: "Where they disagree, that disagreement IS the finding: the
  dual-tagged markets carry it, and neither tier is 'the' answer. Tier 2b never overrides Tier 2." The
  crypto subfamily under tag membership is 910 minutes of overlap against 2,389 under first-tag-wins, so
  the dual-tagged markets are a minority of the crypto set and move the peak from -0.138 to -0.325.
- Same lag (38 min) in both tiers for crypto; the sign is negative in both. That the lag survives the
  membership change while the magnitude does not is the one structural detail worth a ruling.
- Caveats that stand: one 24 h window; the crypto subfamily is endogenous to BTC by construction
  (registration: 'the question is a function of the BTC price'); the 5-minute latency floor was applied
  and 38 min clears it; B14's tests_run counter is now 2 per tier-scope.

## Round 119 findings (incident)

### Timeline (EDT, 2026-09-06)

- 11:46:10 last asset_snapshots row; 11:46:21 first `FOREIGN KEY constraint failed`; then ~360/h.
- 16:12 the only network-profile event (the VPN); unrelated - five hours after onset.
- 20:55 operator asks for a check; 21:04 restart authorised; 21:04:28 new pair launched; 21:05:10 first
  'Persisted 442 market snapshots'; 21:06 old pair killed by PID; 21:07 0 FK errors in the last minute.

### Root cause, precisely

- `asset_snapshots.coin` REFERENCES `assets.coin`; `storage/db.py` sets `PRAGMA foreign_keys = ON`.
- `MarketCollector._sync_universe_metadata` (the only `upsert_assets` call) is awaited once in `run()`.
  A coin listed after startup is in every REST context but never in `assets`.
- `insert_snapshots` writes the whole pass in one transaction; SQLite rejects the transaction on the
  first violating row, so 441 good rows were lost with the 1 bad one, every 10 s, for 9 hours.
- Exchange universe today: 514 instruments across 11 DEXes; the collector tracks 442. The 73 it does not
  track (a whole `hyna` DEX, new `mkts`/`vntl`/`io` listings) are not the cause - the one newly listed
  coin on a TRACKED DEX was.

### Consequences of the gap

- Incremental persistence measured no excursions for 9 h ('persisted 0 windows / 0 events'), so the
  whale and fade samples did not grow and the fade's window gate (expected ~09-08) is delayed by the gap.
- `latest_snapshots` was 9 h stale for anything reading it. Basis windows opening in the gap have no
  price series.

### The stop script reported success on failure

- `set /p PID=<file` inside `if exist (...)` then `taskkill /PID %PID%`: `%PID%` is expanded when cmd parses
  the block, i.e. empty. taskkill got no pid, failed silently (`>nul 2>&1`), the pid files were deleted,
  '✓ Collector daemon stopped' printed. Round 102/103 found the inverse (a restart script reporting
  failure on success). Rule, now in memory: after ANY stop script, verify the old PIDs are gone with
  Get-Process before starting the replacement.

### Hardening proposed to Antigravity (not implemented: desk-daemon code, needs ratification + a restart)

1. `_sync_universe_metadata` on a schedule (each context poll, or every N minutes), not only at startup.
2. `insert_snapshots`: upsert any unknown coin before the batch, or on IntegrityError fall back to
   row-by-row and log the offenders by name - one new listing must never zero the stream again.
3. Supervisor: alert (and optionally restart) when coverage decays while restarts == 0 and the child is
   alive - the failure mode the current 'restart on crash' policy cannot see.
4. The pre-flight or a daily check: newest asset_snapshots age; a FAIL over, say, 15 minutes.

## Round 118 findings

### Reject vs mark: the same argument as parking, as INSUFFICIENT, as the hub

- Every silent failure this project has caught had the shape 'the thing looked fine because it was not
  there'. A registration refused at compile time is not there. So a non-digit token compiles, is marked
  (`dev.invalid_tokens`), and lint C6 reports an ERROR that names it - the page and the report both say
  what is wrong. The drill-time guard stays too: the live rehearsal refuses to record.
- The fixture refactor was the real cost, and it was worth it: `TOK_NOCHANGE` had passed through 15
  assertions for many rounds while being a token the recorder could never load back.

### The probe is the operator's to run, by construction

- Registering even a temporary scheduled task is a system change on the operator's list. The script is
  written so that `-WhatIf` proves its wiring without registering anything, and so that a failure is
  informative: a probe that never runs on battery is the battery-flag decision made visible.

## Round 116 findings

### The path works. Here is what it took to prove it without writing anything real

- Every write goes under `cross_market/data/rehearsals/<stamp>/` (git-ignored): the books, a copy of the
  vault, the synthetic event, the curve. The three things the drill card would touch for real - the vault,
  the books directory, `./event.json` - are hashed before and after and must not move.
- The synthetic event carries confidence 0.995 because the curve and the pages gate on it. That is why
  its `source` says in words that it is not a statement, and why it never leaves scratch.
- One live market, two deferred: with change_bps 0 the hike markets resolve to NO, and both are neg_risk
  books, so Ruling R4 defers their NO side. On the 16th, if the Fed holds, the drill will produce exactly
  this shape: one curve, two deferrals. If it hikes 25, the shape flips. Worth knowing in advance.

### Three things the rehearsal caught that the pre-flight could not

- **The User-Agent is load-bearing.** A plain Python GET of `clob.polymarket.com/book` returns 403; the
  recorder's browser-style header gets 43 bids and 46 asks in 0.22 s. The pre-flight is offline by
  design, so only the live path exercises this. It is the Round 87 finding, re-confirmed on the day.
- **Stamp filenames cannot carry a token with an underscore.** `clob_<token>_<stamp>Z.json` is parsed with
  `[^_]+` for the token. The fixture tokens (`TOK_NOCHANGE`) recorded 30 stamps and loaded 0. Real tokens
  are 76-digit decimals, so the drill is safe - and the rehearsal now FAILs on any non-numeric token
  before recording, so a future registration cannot walk into it.
- **A hard-coded source path.** `knowledge.ingest.clob.update_concept` cited `obsidian_vault/wiki/profiles`
  regardless of the vault it wrote into. Derived from the target vault now; identical in production.

### What lint means on a relocated vault

- The copy sits three directories deeper than the real vault: `raw/index.md`'s entries are
  vault-relative (`../../HyperLiquid/...`) and stop resolving - ~1,540 L2 findings. And the scratch root
  is git-ignored, so L9 (link to an ignored file) fires on every link in the copy. Neither says anything
  about the drill. The rehearsal lints the whole copy (link rules need the graph) but JUDGES only the
  pages it wrote, on every rule but L9, and reports the rest as relocation findings. The real vault is
  linted in place every round and is CLEAN.

### Self-direction, and where its edge is

- Chosen because it was the top Round 116 candidate in the Round 115 handoff and needs nothing but a
  network read. NOT done, because they are the operator's: starting W32Time, clearing the battery flags,
  restarting the collector, installing Desk 4 packages. The live recording is 60 s of public GETs, the
  same call the collector makes all day.

## Round 115 findings

### Two populations that differ by 0.36 points, and the rule that follows

- The whale registration's sample_requirements include `min_samples_60m_per_event: 1`; the engine
  filters to rows with a complete forward series (data_audit: 339 truncated of 19,008). Over ALL
  treatment rows ZEC is 19.84% (Round 114: `ready`); over qualifying rows it is ZEC 20.20% - over the
  20% ceiling. Round 114's `ready` was therefore wrong for the same reason Round 113's was: the
  mirror counted a population the registration does not define. Rule: every requirement in
  `sample_requirements` that names a row filter is part of the population, and the mirror applies
  it (population.source; min_samples_60m_per_event). Anything the mirror cannot apply must be
  reported as `unmeasured`, never approximated.
- This is not a case for hysteresis (rejected in R113-1.C): the registration says >20% is not a
  qualifying sample, and 20.08% is over 20%. The page now says so and names the coin.

### R114-1.F was implemented in one engine, declined in the other

- `_reopening_sample_gate` reads `span_days` from the result; `benchmark()` now reports it from
  the events' timestamps; a result without it fails closed (`covered span not reported`). Four HL
  gate tests updated to carry a span; two added (short span; missing span).
- `cascade_replay.py` untouched: `whale_sweeper_cascade_replay.meta.json` has no window requirement.
  A span gate there would be a gate the registration never wrote, applied after the data was seen.

### Committing one hunk out of a file another agent is editing

- `engine/risk_sentinel.py` carries three uncommitted hunks from the other agent, the first on the
  very signature D3 changes. `git add` would have committed their work under my name. Instead:
  `git show HEAD:file` (as BYTES - a text-mode pipe on Windows rewrote every line ending and
  produced a 520-line diff on the first attempt), apply only my replacement, `git hash-object -w`,
  `git update-index --cacheinfo`. The commit diff is +4/-2; the working tree still carries their
  33 lines against the new HEAD.

### Smaller things

- The replay engine's own verdict string and the page's independent grade agree (INSUFFICIENT);
  the page's History table gains its second row (`_artifact.written_at` 2026-09-06T22:39:27.484923Z), keyed by the
  artifact, not by the ingest run.
- The old artifact in cross_market/data/ (git-ignored) is left in place; the page no longer reads
  it and nothing else does.

## Round 114 findings

### The registered population was not the table, and Round 113 got it wrong

- `cascade_excursions` holds `trade_sweep` (13,645 rows, 46 coins) and `trade_flow` (5,363 rows, 28
  coins). `measurement_schema.sql`: "the two event sources answer different questions and must never
  be pooled". The fade's events are sweeps; `benchmark()` and the `excursion` command default to
  trade_sweep. Round 113's gates were computed over every treatment row (19,008; top coin 19.84%) and
  said `ready`. Over trade_sweep the top coin is ZEC 26.8% and the span is 5.49 days.
- Recorded as a dated `population` block on the registration - a clarification of the population the
  code always used, with the Round 113 error stated in it. No bar changed. The mirror now filters by
  `population.source` when a registration names one and pools only when none does (the cascade-replay
  engine pools by design).
- The registration's own state_at_registration numbers (492 events, 15 coins) match NEITHER source in
  the persisted table at that instant (48 and 274 rows): they came from the snapshot-based benchmark,
  a different pipeline. So the population could not be inferred from counts; it had to come from the
  code the registration binds to.

### INSUFFICIENT is not terminal

- Round 113 flipped a registration to `evaluated` the moment any `_verdict` page existed. An
  INSUFFICIENT verdict says "come back when the sample qualifies"; treating it as closed would have
  hidden exactly the condition L11 exists to surface. Now only a PASS/FAIL/RETUNE grade (or a verdict
  page too old to carry one) closes the question; the registration page shows the last evaluation
  and the gates that block. This also re-opens `whale_sweeper_cascade_replay` (Round 104:
  INSUFFICIENT on PONS 22.5%) - its pooled sample now passes the share gate, so it reads `ready` and
  L11 will ask for a re-run in three days. That is the rule working, not a regression.

### The verdict, exactly

- Engine artifact written 2026-09-06T19:44:26.500127Z over 38,016 rows in the table; population trade_sweep;
  13,645 events, 46 coins, top ZEC 26.8%, span 5.49 d. Decision horizon 30m (the longest
  the registration enumerates; 60m reported only). ratio_30m 0.7896 (below 1: the cascade kept
  going); P(ratio >= 1.25) 0.0000, P(ratio >= 1.0) 0.0677, 20,000 cluster-bootstrap draws.
  Page grade INSUFFICIENT; engine INSUFFICIENT; agree. The fade stays retired; the question stays open.

### A double writer, caught by the idempotence check and by nothing else

- The artifact lives beside the registrations (tracked, unlike Round 104's in cross_market/data). The
  experiments ingest globs `*.json` there and compiled `passive_fade_rebenchmark.verdict.json` as a
  generic registration - into `passive_fade_rebenchmark_verdict.md`, the very page the new adapter
  writes. Each run flipped the page between the two shapes; lint was CLEAN both ways and both adapters
  reported success. Only hashing the vault across two passes showed it (Round 110's lesson, again).
  `compile_registration` now returns None for any JSON carrying an `_artifact` envelope, with a test
  that runs both writers in both orders.

### The pre-flight found the clock unattended

- W32Time is Stopped. `w32tm /query /status` says so; the stripchart against time.windows.com still
  measured +0.37 s. Reported as WARN with the two-command remedy; not started, because starting a
  service is the operator's call. Everything else the 16th needs is consistent: tracked batch, 182-char
  stamp paths, writable books parent, IgnoreNew, no orphan recorder.

### Smaller things

- Re-pointing the task used Set-ScheduledTask -Action only; a before/after JSON of trigger, battery
  flags, logon type, MultipleInstances and Enabled was compared and matched. The battery flags stay
  set: that decision is still the operator's.
- The runner's smoke at 50 draws took 6 s; the full 20,000-draw run is minutes of pure Python because
  the engine's `_aggregate` sorts for medians on every resample. Left as is: the registered code path
  is the registered code path.

## Round 113 findings

### The directive's premises, checked before quoting (about 12 minutes; changed 3 of 5 deliverables)

- **D1 direction was backwards.** `knowledge/ingest/experiments.py:37` already imports
  `rules_from_raw` from lint, and markets.py imports `DEFAULT_DROPS`; lint importing `STALL_DAYS` from
  experiments would have been a circular import. The experiments copy was never read by anything.
  Lint owns it; experiments imports it for the READY callout text.
- **D2 would have claimed `ready` on one count.** The registration names four sample requirements and
  says they are enforced by `wick_benchmark.reopening_gate()`. Round 104's sibling failed the SHARE
  gate at 38x the count floor. A read-only probe showed all four pass today - narrowly (ZEC 19.84%
  against a 20% ceiling), so `ready` is true, but it can flip back as events land. Each gate is on
  the page as {value, bar, pass}; a page past its count floor but failing another gate stays
  `accumulating` and names the blocker.
- **D2 would have dated readiness wrong.** The directive offered `registered_utc or floor_met_utc`.
  The 500th treatment event landed 2026-09-01T08:13Z (from timestamp_utc), 2.5 h after registration,
  while the share gate was still failing. `ready_since` = first observation of ALL gates passing,
  carried over while it stays ready and dropped when it does not. L11 fires 2026-09-09 if nobody
  evaluates or retires passive_fade_rebenchmark - which is the rule doing its job, not a defect.
- **D3 named the wrong package three times out of four.** `pytest --collect-only` says: hyperliquid
  (x2), uvicorn, fastapi. Installing fastapi alone would have fixed one module and left the operator
  believing the webhook path was tested. It still is not: `main.py` imports the Hyperliquid adapter
  at module level, so the webhook tests need hyperliquid-python-sdk (dry run: eth-utils, msgpack).
  Not installed - that is a dependency decision, recorded in HOMEWORK.
- **D5's "0 warnings" and D2's L11 would have contradicted each other** under the directive's own
  dating; under first-observation dating they do not, for three days.

### The rehearsal found its own bug before it found anyone else's

- First real run: 21 PASS, 1 FAIL - `batch books dir == event books_dir: %2 vs cross_market/...`.
  The regex `set BOOKS=(\S+)` matched the argument line `set BOOKS=%2`, not the default line under
  it. `set DUR=(\d+)` had skipped `%1` only because `%` is not a digit. Both now `(?!%)`. The test
  fixture reproduces the two-line batch shape, so the test would have caught it had it run first.
- Real findings, all now on the record: the batch file is GIT-IGNORED (.gitignore:137) - a fresh
  clone has no drill; the task is interactive-only (logged-in session required; screen lock is fine);
  both battery flags are set (the HOMEWORK decision); NextRunTime shows 13:58:58 against a 13:58:00
  trigger (scheduler jitter, reported not judged). Tokens agree across rules.json, the vault page
  and the batch; duration 420 s = window; python path exists; 124.8 GB free; on mains.
- The Task Scheduler query goes through `-EncodedCommand` (base64 UTF-16LE) so no quoting crosses
  argv, and was probed live against the real task before the module was written around it.

### Hub staleness (Antigravity's b3c4493)

- Every adapter wrote its register with `write_page(update_register(...))` and nothing but seed ever
  wrote the hub. A hub row carries the register's `generated.at`, so the Round 112b digest recompile
  left the hub showing 17:32Z for a register stamped 17:54Z. `write_register` writes both; the test
  drives a real adapter (ingest_experiments) and asserts the hub row moved in the same call, and
  that an unchanged register moves neither.

### Test-writing lesson

- A helper named `run(self, **kw)` on a TestCase subclass shadows `unittest.TestCase.run`, so
  `setUp` never executes and every test in the class - including the inherited ones - fails with
  AttributeError on the first fixture attribute. Renamed `checks`. Cost: one fix cycle.
- Desk 4 run from the WORKSPACE root shows 73 failures that are relative-path reads of
  `config/asset_specs.json`; from its own directory it is 151 passed. Pre-existing, unchanged, and
  the reason COMMANDS.txt says to run it from the desk directory.

## Round 112 findings

### The parking rationale as directed would have written three false claims into the vault

- **INSUFFICIENT is not FAIL.** The directive cited Round 104's cascade replay as a "failure
  on the cascade fade thesis". Its verdict was INSUFFICIENT, and its own registration - which
  Antigravity ratified - says an insufficient sample is never reported as a weak PASS or a FAIL.
  Round 104b corrected exactly this misreading in the handoff log.
- **Side A is not the verdict.** "fade ratio 0.2787, P=0.0103" is the Side A split; the
  registration grades the POOLED metric only and names the sides as a separate report.
  Round 104b corrected exactly this too.
- **Wrong strategy.** `regime_filtered_v1` is a passive fade with an EMA-50/RSI-14 trend gate,
  ATR-scaled offsets and TP/SL. The cascade replay tested Item 14's liquidation-cascade
  sweeper. Adjacent, not the same mechanism.
- The amendment that parks it records these as `not_cited_as_evidence`, so nobody later
  reaches for the wrong reason. It parks on N=0 after 5 days, no process, the documented
  600 s force-close vs 1,224 s median-to-target defect, and the FOMC calendar.

### `status: parked` fails L1; the ruling contradicted itself

- `frontmatter.STATUSES` is `draft | stable | deprecated`. The directive's text asked for a
  top-level `status: parked`; its own schema block put `parked` under `dev.progress.status`.
  The schema block is right and is what was built. OKF status stays in vocabulary; the
  experiment's lifecycle lives in `dev.progress`.
- The park itself is a dated entry in the registration's OWN `amendments` list, at
  `closed_trades_at_amendment: 0` - the mechanism the file already had for exactly this.

### `passive_fade_rebenchmark` was never evaluated

- The directive asked to mark it `evaluated (Round 104)`. Its meta has no verdict, no
  evaluated_utc, no result. Round 104 evaluated `whale_sweeper_cascade_replay`, a sibling that
  INHERITED its gates. It is marked `accumulating` at 19,008 events against a 500 floor, which
  is what its own status line says it is doing. `whale_sweeper_cascade_replay_meta` is the one
  marked `evaluated`, because its `_verdict` page exists.

### L10 was probed positively before being trusted

- On the real vault L10 returns zero, because both stalled registrations are disposed of this
  round. That is what a broken rule looks like too. Un-parking regime_filtered_v1 in memory
  fires exactly one warning; setting its progress to 7 silences it. Both directions checked.

### Smaller things

- The registers hub is a SPECS entry with a `matches()` branch selecting pages that carry
  `dev.register_for` (excluding itself), LAST in the dict so seed writes it after the ten it
  lists. One builder, per the Round 110 double-writer lesson.
- `_cell` renders a progress dict as `0/50 (0%) · parked`; a dict repr in a register column
  would have been the phantom-column bug's cousin.

## Round 111 findings

### The usage counter as directed would have broken the drill card at T-2

- R110-1.E's directive was to increment `dev.usage.count` on pages a query opens. But
  `write_page` RAISES WriteRefused for a page inside its own `dev.window` (pages.py), and the
  FOMC Event page's window is 17:58Z-18:05Z on 2026-09-16. A drill card counting usage would
  therefore have crashed in the ONE window it exists for, handing the operator a traceback two
  minutes before a Fed print.
- It also breaks the Round 107 guarantee - and its test - that every query mode writes nothing,
  which is precisely what makes the card safe to run inside a frozen window.
- Counting is therefore OPT-IN (`--count-usage`), and even then a windowed page is SKIPPED
  rather than attempted and reported as skipped. The counter is never worth breaking the thing
  it is counting. Flagged for ratification rather than assumed.
- Found in the pre-quote check, not in testing: one grep for `in_window` in write_page.

### The summary column put free prose in a table cell for the first time

- The pre-quote check said it was safe: 65 digest descriptions, none containing a `|`. That was
  true and not sufficient. `registers._cell` did not ESCAPE pipes, so one future round entry
  with a pipe in its first sentence would silently grow a phantom column - the Round 104
  regime-table bug, in a new place, waiting.
- Caught by a test written for the general case rather than the current data. The fix is in
  `_cell`, so all TEN registers are hardened, not just the digests one: every register renders
  values it does not control.
- `md_cell` moved from `ingest/__init__.py` to `pages.py` for this - registers should not import
  from ingest - and is re-exported so the adapters' imports are unchanged.

### Two smaller honesty fixes

- The card's footer said "this card is read-only and wrote nothing". With `--file` in the same
  run that is false. It now says "the CARD is read-only; nothing above was written", which is
  true in both cases.
- A filed query is a Concept page, so L7 wants a review clock and L3 wants an inbound link. It
  carries `stale_after` (90 d) and lands in a new `queries_register` - a question nobody can
  find is the same as an unfiled one. Tenth register; REGISTER_STEMS is now 10.

## Round 110 findings

### Making Digest a SPECS type exposed a double writer

- Ruling R109-1.F is right that the fix belongs in `registers.SPECS` rather than in a link
  filter. But adding it there gave `digests_register.md` TWO builders: `registers.update_register`
  (generic, columns from dev) and the digests adapter's own bespoke table. Both wrote the same
  path with different content, so seed and the adapter silently overwrote each other on every
  run - the page's contents depended on which command happened to run last.
- Caught by hashing the file across seed -> adapter -> seed. Neither run errored, neither
  reported a write, and lint was clean throughout: the only symptom was a hash that moved.
- The bespoke builder is gone; the generic register renders `round` and `date` from `dev`,
  which is what the SPECS columns are for. One writer, stable across any command order.

### The directive's truncation callout would have failed lint

- R109-1.C specifies the callout as `[[AGENTS.md#round-<N>-complete]]`. **AGENTS.md is at the
  repository root, not in the vault**, and lint L8 resolves wikilinks against vault files - so
  every truncated digest would have failed lint on the exact line telling the reader where the
  rest of the text is. Rendered as a code span instead, which resolves for a human either way.
- Caught before writing it, by checking whether `obsidian_vault/AGENTS.md` exists. It does not.
- No entry truncates today - Round 85 is the longest at 110 lines against the new 250 - so the
  path is exercised only by a synthetic 400-line test. A branch that never runs in production
  is exactly the one that has to be tested.

### Smaller things

- C1 already memoises file reads, so 64 digests asserting against the same 210 KB log cost one
  read rather than 64. Checked before adding the asserts rather than assumed.
- The assert pattern `^Round <N> complete` matches all three log formats (dated, undated and
  the dash form), because the difference between them is what follows the word `complete`.

## Round 109 findings

### The digest regex silently covered a third of the log

- The first version parsed 22 rounds. `grep -c '^Round [0-9]+ complete'` says 63. **The log has
  three entry formats**, written at different times: rounds 74+ carry a date
  (`Round 104 complete (2026-09-06): ...`), rounds 31-73 carry none
  (`Round 73 complete: ...`), and Round 50 uses a dash. A regex for only the newest shape looks
  exactly like a working one - it produces pages, they lint clean, nothing errors.
- Caught by counting what the log contains against what parsed, BEFORE shipping. That check
  cost one command and is the same discipline that caught L9's three failures last round: a
  compiler that silently drops two thirds of its input is indistinguishable from a correct one
  unless you count both sides.
- Undated rounds record `date: null` and render `date not recorded in the log`, rather than a
  guessed or inferred date. 41 of the 63 are undated.

### The log quotes wikilink syntax, and quoting is not linking

- AGENTS.md discusses link syntax as subject matter: `[[Whales/<addr>]]`, `[[page\\|alias]]`,
  `[[wikilinks]]`, `[[Cross_Market_Titans]]`. Copied verbatim into a page, four of those become
  dangling links (L8) and one points at a git-ignored dashboard (L9) - the digests would have
  tripped the exact rules the rounds they describe were spent building. They are neutralised
  into code spans, which both checks correctly skip.
- A digest's only real outbound link is its register. Asserted by a test.

### Two small things the directive did not anticipate

- **`Source Summary` could not be the type.** The directive asks for type `Source Summary` at
  path `wiki/digests/`, but s.4 maps that type to `wiki/sources`, so `page_path` and the
  constitution would have disagreed. A Source Summary condenses an EXTERNAL document; a Digest
  condenses one round of this project's own work chain. A new `Digest` type was added instead -
  which s.3 explicitly anticipates ("new types may be added here") - and the s.4 vocabulary
  addition is flagged for ratification rather than assumed.
- **L5 would have rejected the source anchor.** `AGENTS.md#round-109-complete` was resolved as
  a whole filename, reporting a missing file that is sitting in the repo root. A `#fragment`
  names a SECTION, not a different file; `_local_path` now strips it, which brings `sources`
  into line with `extract_links`, which already did.

## Round 108 findings

### `git check-ignore` lied three different ways, and a linter that is lied to says "all clear"

The obvious tool for L9 is `git check-ignore`. It failed three times at this vault's size, and
not one of the failures announced itself:

1. **On argv it blows the Windows command-line limit** - `WinError 206` at 519 paths. Found by
   running the blast-radius audit BEFORE writing the check, which is the only reason it was a
   two-minute detour instead of a confusing failure late in the round.
2. **`--stdin` SILENTLY TRUNCATES.** At 568 paths the tail was simply dropped: git reported
   nothing ignored, with an empty stderr and a clean exit. A check that answers "all clear"
   because it never saw the question is worse than no check at all.
3. **Even inside a 100-path batch it emitted only the FIRST match.** All three ignored
   dashboards went in; exactly one came back. Chunking did not fix this and could not.

The question is now asked the other way round: `git ls-files --others --ignored
--exclude-standard` enumerates what git ignores, completely, in ONE call, and the caller
intersects. **The only reason any of this surfaced is that the rule was probed against a
known-ignored file before being trusted.** A new lint rule that returns zero findings on its
first run looks identical whether it is correct or broken; the probe is what tells them apart,
and it should be standard practice for every future check.

### And then it compared the wrong kind of path

- L9 passed my manual probe on the real vault and FAILED in the test fixture, because git speaks
  repo-relative paths while the fixture's vault is an absolute temp path. My probe happened to
  pass relative paths, so it hid the bug. Comparison now goes through `_repo_rel`. The lesson is
  the same one: the probe was necessary but a probe that shares an assumption with the code
  cannot test that assumption - the fixture, which differed, is what caught it.

### The directive's command would have sent the operator to an empty directory

- Ruling R107-1.A specifies `--books cross_market/data/clob_drill/<event_stem>`. That path does
  not exist. The drill's own recorder (`fomc_drill_2026-09-16.bat`) writes to
  `cross_market\\data\\clob_books\\fomc_2026-09-16`, and latency_sniper's bare default is the
  clob_books ROOT with no event subdirectory - so the obvious guess is wrong twice over. A
  survival curve pointed at an empty directory reports an empty result rather than an error,
  one minute after the print. The card now emits the path the recorder actually uses, and every
  flag was checked against `latency_sniper --help` before being printed.

### Smaller things

- The constitution's s.7 lint table was a full round behind: it documented L1-L7 and C1-C5 with
  no L8. Both L8 and L9 are now in it. The `verified` block predates those rows, so the
  amendment is dated and scoped in a comment rather than left to imply coverage it does not have.
- `--regime macro` now says "matched 2 pages on substring" instead of silently answering with
  two cards as though that were the question.

## Round 107 findings

### What a card read under time pressure has to be

- **The unit on the clock is the unit the decision is made in.** The first render said
  `T-251h 29m`. Nobody converts that at 13:58 with a statement about to print. Past 48 hours
  the card shows days; inside two days it shows hours and minutes; near the window it shows
  minutes. The countdown is computed at run time, never restated from the page.
- **A missing Event page is an ERROR, not an empty card.** An operator holding a blank sheet
  two minutes before a print has been actively misled, so the refusal names every event that
  does exist and exits 3.
- **The card writes nothing, and that is a property rather than a mode.** Inside its own
  window the Event page and the rules registration are frozen; a query that mutated what it
  describes is one nobody should run at T-2. A test hashes the whole vault before and after
  all three query modes and asserts nothing moved. HALT still refuses, because HALT means the
  pipeline behind the card has stopped and answering normally would imply otherwise.
- The standing forecast is surfaced from the journal's calibration ledger (p=0.90,
  `change_bps == 0`), because it scores itself against the payload the operator is about to
  write - T-2 is the last moment it can be checked against what they actually believe.

### A field that had to be fixed in two places, not one

- `rank_at_seed` was directed to be preserved in the frontmatter. The BODY printed the same
  number from the live rank, so preserving only the metadata would have produced a page whose
  frontmatter said 1 and whose text said 12 - worse than either number alone. The value is
  resolved once, before the body is built, and both read from it. A new `rank_now` carries the
  live figure, and the body shows `at seed: 1 (now 12)` when they differ.

### Untracking the dashboards needed a check first

- Lint L8 resolves wikilinks against files ON DISK, so untracking a dashboard would break a
  fresh clone if anything linked it. Verified before running `git rm --cached`: the three named
  files have ZERO inbound wikilinks. `Monarch_Hub.md` is also exporter-written and has FIVE,
  so it stays tracked - Antigravity's list was exactly right, but the reason is worth recording
  because the next dashboard added to that list has to pass the same test.
- Past versions remain in git history; only future churn is ignored. The files stay on disk and
  the exporter keeps writing them.

## Round 106 findings

### Two directives that were right in intent and wrong in target

- **R104-1 named the wrong file, and the difference matters.** The directive says to implement
  gated L2 spread recording in `storage/incremental_persistence.py`. That module is the
  RETROSPECTIVE measurement grid: it walks a grid of PAST entry instants and reads spreads via
  `spread_bps_at`, which is a pure reader of `orderbook_snapshots`. Polling L2 now cannot tell
  you the spread at a window that opened three days ago, so no amount of sampling there would
  ever measure a historical window. The gate belongs in `collectors/orderbook_sampler.py`, the
  LIVE caller, which is where it went. The gate condition itself was exactly right.
- **THE FIX COSTS ZERO EXTRA REST WEIGHT, which is the part worth knowing.**
  `ORDERBOOK_SAMPLE_MAX_COINS = 24` caps the TOTAL coins per pass and carries explicit budget
  arithmetic in its comment; `select_sample_coins` enforces it with the priority held >
  candidates > rotated > core. So raising the candidate slots from 5 to 12 does not enlarge the
  budget - it REALLOCATES it away from the rotated/core watchlist toward coins the harvester
  could actually enter. The guardrail "zero unconditional polling across 440 coins" is
  satisfied structurally, not by promise.
- **The markets re-admission sketch would have been destructive.** With no drop record,
  `compile_market` degrades the question to "Polymarket token abc123…", the family to
  "unknown", and - critically - computes a TOKEN-DERIVED SLUG instead of the market slug. A
  naive `wanted |= existing tokens` therefore writes a placeholder page at a NEW path and
  leaves the real page orphaned. Verified before shipping: 97 tokens, 0 new pages.

### A regression I introduced and caught in the same round

- Removing the `skipped` guard so market pages could be refreshed meant `first_seen` was
  overwritten with the newest drop's `fetched_at` on EVERY run. That field was accidentally
  correct before only because the page was written once and then skipped forever. It is now
  explicitly preserved as the EARLIEST sighting. Caught by reading the diff of the first live
  run - 97 pages showing a changed `first_seen` is not a plausible refresh.

### The provenance audit came back empty, and that is the finding

- Lint L5 now resolves git citations, and the read-only audit BEFORE building found 5 commit
  hashes cited across the vault, all 5 resolving. Blast radius zero - the opposite of L8 last
  round, which found 86 broken links on first run. Running the audit first (the lesson recorded
  after Round 105) turned an open-ended estimate into a known-small one within two minutes.
- The check SKIPS rather than passes outside a git repository. Reporting "valid" where
  `git cat-file` cannot answer would be a lie, and reporting "missing" would be a false alarm.

### Smaller things

- `typing.Any` was used in lint.py without being imported; it only worked because
  `from __future__ import annotations` defers evaluation. Anything calling `get_type_hints`
  would have broken. Imported properly.
- A sharp pruned from `sharp_traders` has NO live row to rebuild from, so it genuinely cannot be
  maintained. Rather than freeze it silently or invent a deprecation (Ruling 99-2 makes
  counterparty judgement human), the adapter reports it in `report.unmaintained`.

## Round 105 findings

### L8 found 86 broken links on its first run, in three groups

- **47 CRM whale pages and 38 sharp pages linked exporter-owned notes that do not exist.**
  The CRM seeds the top 100 whales by equity; the exporter writes notes for a different, live
  set of 79. They overlap by 53. Every page emitted `[[Whales/<addr>]]` unconditionally, so
  roughly half resolved and half did not - and a link that works for some rows and not others
  is worse than no link, because the reader cannot tell which. The pages now SAY when no
  exporter note exists, which is also the honest statement about that counterparty.
- **Desk 3 pointed at `latency_decay`**, which knowledge.ingest.clob will not write until the
  FOMC drill. Round 104's own comment in seed.py called a stem listed before its adapter had
  run "a dangling link, not an error". That comment was wrong and L8 proved it in one run.
- **Every desk pointed at eight registers a fresh vault has not built yet.** Filtering those
  links broke the design invariant that every desk links every register, so the fix is the
  other way round: seed now WRITES all eight (an empty register is a valid register, it says
  "0 page(s)"). Both L3 and L8 are satisfied without weakening the invariant.

### The adapter that stops maintaining a page freezes it

- One whale page kept its dangling link through a fix that reached the other 182, because it
  had dropped out of the top-100 window and the adapter only ever rebuilt its current
  selection. A page outside the window is frozen at whatever the code emitted the last time it
  was selected - so every future fix leaves a growing tail of stale pages. load_whales now
  re-admits any address that already has a page: an adapter maintains every page it created,
  or it does not own them.

### Smaller things worth knowing

- **The `_artifact` envelope justified itself immediately.** Between Round 104's run and this
  one the table grew 29,350 -> 29,612 rows, and side B moved from ratio 1.7378 / P 0.4808 to
  1.7135 / 0.4823. Same seed, same code, different data. The verdict is unchanged
  (INSUFFICIENT) and the anatomy page records both readings side by side.
- **Side B's median/mean divergence is the real microstructure finding.** Median ratio 1.71
  against a MEAN ratio of 0.72: the typical buy cascade reverts modestly, the tail runs
  violently against the fade. That single fact reconciles a median above the 1.25 threshold
  with a negative dollar expectancy, and it is the strongest argument for the pre-
  registration's clustered, pooled metric over a headline median.
- The 1-to-1 control identity is now CHECKED rather than described: treatment share 0.5
  against an expected 1/(1+EXCURSION_CONTROL_MULTIPLE), with the constant pinned by
  dev:parameters so C1 fires if it changes. The page also states, derived from the counts,
  that every truncated row is also a null-30m row - the two filters are not independent.
- The test fixture had no constitution, though WIKI_SCHEMA.md is in OWNED_FILES and every
  register links it. That is not a smaller vault, it is an impossible one; 30 tests failed L8
  on `[[WIKI_SCHEMA]]` until the fixture got one.
- Adapters now degrade a link to readable plain text when its target is not compiled yet
  (`link_if_exists`), rather than emitting a link to nothing. The link returns on the next seed.
- **THE ESTIMATE WAS WRONG BY A WIDE MARGIN**: 25-35 minutes predicted, ~2 hours actual. The
  four deliverables were about as expected; what was not was L8's blast radius. Adding a rule
  that has never run to a vault of 423 pages surfaced latent breakage in six modules and 31
  tests. Worth recording for the next time a lint rule is proposed as a small task.

## Round 104 findings

### The correction that matters most (104b)

- **I labelled a population by what I assumed the strategy did, then checked.** The gross-bar
  subset is a SUPERSET of what the harvester would trade, because the live scanner also
  requires the net bar and a measured spread under a ceiling. Calling it 'entry-qualifying'
  would have put a 28.05% median in front of a desk decision as though it were achievable.
  It is an upper bound. The lesson generalises: a compiled page that names a population after
  a STRATEGY rather than after its FILTER is a copied-state violation in prose form.
- Worth noting the shape of the error - it was not in the arithmetic, which was right, but in
  the label on the arithmetic. Lint cannot catch that; only reading the source can.

### The measurements themselves

- **The basis book's entry rule is doing real work, and the headline number nobody should
  quote is the pooled one.** Across 10,635 recorded windows on 441 assets, median realised
  APR is 6.40%. Across the 473 windows whose QUOTED apr cleared the 25% entry bar - the only
  ones the harvester would have taken - median realised is 28.05%. Reporting the first as
  'what the strategy earns' understates it by a factor of four; reporting only the second
  hides that just 1 window in 22 qualifies. The page carries both, labelled.
- **But entering on a quoted rate is not the same as earning it.** Of those 473 qualifying
  windows only 53.5% actually realised at or above 25%, and 12.3% went NEGATIVE. p10 to p90
  is -3.52% to +96.65%. This is a wide, fat-tailed distribution, not an annuity.
- **BASIS_MIN_NET_APR = 20.0 CANNOT BE EVALUATED ON THIS DATA.** net_apr_after_fees is
  measured on 197 of 10,635 rows (1.9%); the other 10,438 have fee_basis = 'unmeasured'
  because spreads were not recorded when the window closed. The page says UNMEASURABLE and
  does NOT substitute the gross figure. If the net hurdle is meant to govern anything, the
  window writer has to start recording both legs' spreads; a ruling is requested.
- Two stale counts corrected against live reads: basis_realised_windows is 10,635 rows, not
  the 9,312 the Round 104 directive cites; cascade_excursions is 29,350, not 28,544.
- **The cascade replay verdict is INSUFFICIENT and every horizon says the same thing.**
  fade_ratio_30m 0.6124 with cluster P(>=1.25) = 0.0000. 5m 0.5576, 15m 0.5990, 30m 0.6124,
  60m 0.7520; all four below 1.0, all four dollar expectancies negative. Fading cascades did
  not pay at any horizon, so the pre-committed choice of 30m is not carrying the result.
  One gate fails (PONS 22.48% > the 20% ceiling) so NO verdict is issued; the FAIL band the
  probability would have landed in is stated as explicitly not a verdict. Item 14 stays gated.
- The sample is narrow on two axes, not one: HHI is 0.14299 against a 0.15 ceiling. A single
  active microcap would fail that gate too.

### Three defects found in our own tooling

1. **`seed --force` restamped 30 unchanged pages, because generated.at comes from the
   REGISTRY FILE'S MTIME.** MASTER_COMMAND_LIST.txt was touched (not edited - content is
   byte-identical at HEAD) during the maiden night, so its mtime moved from 00:57:06Z to
   01:10:25Z, and the first --force this round wrote 'freshly generated' onto 30 pages whose
   content had not moved at all. Caught in git diff before committing. seed now compares the
   built page against the one on disk field by field and keeps the earned stamp when only
   generated.at would differ; the re-run wrote exactly 1 page (Desk 1, which really did gain
   a section) and reported 31 unchanged.
2. **`seed` was the only writer in the package that did NOT carry human fields.** Every
   ingest adapter calls pages.carry_human_fields; seed never did, so a --force would have
   silently stripped a `verified` block, a status past draft, or a dev.ratified_by from any
   Desk or Ruling page the architect had signed. Nothing had been ratified on a seeded page
   yet, so NOTHING WAS LOST - verified against the diff. The guard is now in, with a test
   that ratifies a desk page and forces a reseed three days later.
3. **A raw `|` in a regime tag split a markdown table.** regime_tag values are literally
   'VOL_MID|FUND_FLAT', and the verdict page's regime table rendered them as an extra phantom
   column. pages.safe_title exists but SUBSTITUTES a pipe with '/', which would have silently
   changed a database key into something that does not exist. New ingest.md_cell ESCAPES
   instead, so the reader sees the real tag.

### Smaller things worth knowing

- **The replay is deterministic; its INPUT is not.** Two back-to-back runs are byte-identical
  (seed 7 is honoured). The drift from Round 103's numbers is entirely the live collector
  adding ~800 rows. Any figure from this engine is meaningless without the row count beside it.
- **The artifact carries NO run timestamp**, though the registration's must_report list asks
  for rows_at_run. Two runs over a growing table therefore cannot be ordered from their
  contents alone. The ingest records the file mtime as an OBSERVATION and says so. The clean
  fix is an `_artifact` envelope like the one Ruling R102-2 put on the lead-lag exporter;
  NOT done here because cascade_replay.py is Antigravity's module and shipped this round.
  A ruling is requested.
- The registration page's stem is `whale_sweeper_cascade_replay_meta`, not the raw filename
  minus '_verdict'. Guessing it produced a dangling link that lint L3 does not catch (L3 is
  orphans, i.e. no INBOUND link; nothing checks that an outbound link resolves). Worth a lint
  code for unresolved wiki links - proposed, not built.
- A crash between write_page and append_log left a phantom history row on the verdict page.
  The adapter now treats THE ARTIFACT, not the ingest run, as the unit of observation:
  re-ingesting an unchanged file replaces the row instead of appending a second one.
- seed's per-desk 'Compiled pages' block was an `if d.number == 3` branch; it is now a
  COMPILED_PAGES table, so the next adapter adds a row instead of a branch. Desk 3's page is
  byte-identical after the refactor, which is how we know it changed nothing.

## Round 103 findings

### The six-point maiden-night arbitration (HANDOFF_PROMPT.md), answered

1. **Entry A and B timing and verdicts.** A at 21:50:00 EDT: six PASS, exit 0. B at
   22:10:00: six PASS, exit 0. The Round 95 prediction that A would show series_ready
   PASS with the other five WAITing did NOT hold, and the reason is benign: the gate
   opened at 01:40:33Z and the exporter's own 15 s cycle ran the analysis at 01:40:34Z,
   so by the first protocol run at 01:41:00Z the RAN line, the note marker and the
   cooldown were all already present. The prediction assumed a slower loop.
2. **Exporter log summary.** `log lines 3976 · gated 3769 · failed 0 · runs 1` at Entry C.
   failed 0 and runs >= 1: PASS. The Round 75 price-read guard never fired.
3. **Tier 1 verdict audit.** Peak |corr| 0.070 at lag -45 min against the registered 0.20
   bar: NO measurable lead-lag. The 0.20 hurdle is not cleared, so the 5-minute latency
   rule never has to be applied - there is no peak to characterise.
4. **Tier 2 subfamily audit.** crypto (latency rule 5 min): -45 min, +0.069, n=1549.
   fed-rates (latency rule 0 min): -10 min, +0.073, n=1538. Both below the bar, both
   therefore 'no measurable lead-lag'. Neither is an alpha finding and neither is an
   'insufficient' non-verdict: the samples were ample, the correlation simply is not there.
5. **Restart telemetry and Entry C.** The 22:20 restart printed the literal
   '[STOP] watcher pid 49812 terminated' and 'Polymarket watcher launched DETACHED, no
   window'. Entry C at 22:35:00 is the definitive arbiter and PASSES on both counts: the
   watcher is pid 17688 (!= 49812) and the status line ends 'carries tags (Round 76 code
   is live)'. Six PASS, exit 0.
6. **Tier 2b timeline anchoring.** The laptop stayed on; the tagged series begins at the
   restart, first tagged stamp 02:20:07Z. Tier 2b is therefore due no earlier than
   2026-09-07T02:20Z (~22:20 EDT Sunday). The 24-hour continuous span binds first, as
   registered: at ~12 tagged stamps/hour the 200-point floor is reached in ~17 h.

### Other findings

- **restart_polymarket_watcher.bat EXITS 3 ON A SUCCESSFUL RESTART.** It runs `--status`
  about two seconds after a detached launch, before the new process has taken its pid
  lock, so it printed 'watcher STOPPED - no lock' and returned 3 while pid 17688 was
  already alive and polling. The restart was completely successful. Anything treating
  that exit code as failure - a human, a future task chain - would wrongly conclude the
  restart broke. Directive 79-2's script needs a short wait-for-lock loop before the
  status call. NOT FIXED tonight (it is an operator batch file and the maiden night was
  still running); a ruling is requested.
- Series continuity across the restart: 4.1 min gap (02:15:59Z -> 02:20:07Z) against a
  60 min break threshold, and the largest gap anywhere in the 24.7 h series is 12.2 min.
  47.8 minutes of margin.
- The R102-2 artifact cannot exist until exporter 56412 restarts, because the running
  process keeps its loaded module. Until then `knowledge.ingest.lead_lag` with no
  --result refuses with a message naming the exporter. Honest, but it puts the exporter
  restart on the critical path for the next ingest.
- Checklist corrections reported to Antigravity: Items 10, 12, 13 are [x] in the
  Antigravity checklist and [ ] in the registry (Round 88 asked for this ruling and never
  got one); Item 16 is described as parquet and there is no parquet in the codebase;
  cascade_excursions is 28,544 rows not 27,916 (our own copied-state drift); and the
  registry's Item 14 Primary Code cites analytics/excursions.py, WHICH DOES NOT EXIST -
  the writer is storage/incremental_persistence.py. Registry lines 80-484 untouched.
  One check came back clean: Item 19's '100,000-path' claim is correct
  (DEFAULT_ITERATIONS = 100_000; the exporter merely invokes it with 20,000).
- **The sweeper replay verdict is NOT in the vault yet.** Antigravity ran it and reported the
  numbers in a handoff message; the registration says a result is written to the wiki as a
  verdict page. cascade_replay.py has --json/--out, so the honest fix is to run it once,
  keep the JSON as the raw artifact, and ingest THAT rather than transcribing numbers out of
  a chat message. Proposed for Round 104; not done tonight because transcribed numbers would
  be a copied-state violation on the very page that exists to prevent one.
- The exporter has no `--stop` flag (the fetcher does) and
  stop_all_ecosystem_sync.bat matches on WINDOW TITLES, which a detached pythonw daemon does
  not have - so neither can stop it. The only route is a kill by pid. Worth a `--stop` on the
  exporter to match the fetcher's interface.

## Round 102 findings

- **DEFECT, not fixed tonight: `lead_lag --json` does not cover the analysis branch.**
  The flag's own help says "with --check-data: print JSON instead of lines", and main()
  ends with an unconditional `print(format_report(...))`. So the pipeline this project has
  documented since Round 97 - in WIKI_SCHEMA.md s.9, COMMANDS.txt, MASTER_COMMAND_LIST.txt
  and every handoff prompt - `lead_lag --coin BTC --family macro --json > verdict.json`
  CANNOT WORK; it writes the human report and the ingest adapter rejects it. The adapter
  was only ever exercised against a fixture, so nothing caught it. TONIGHT IT WAS NOT
  PATCHED: four scheduled tasks import cross_market/lead_lag.py in fresh processes between
  21:50 and 22:35 EDT, and the maiden-night record is not the place to mutate that module.
  The verdict JSON was produced read-only by calling lead_lag.run() with main()'s exact
  defaults. The one-line fix (print json.dumps(result) when args.json) plus a test is a
  Round 103 item and needs Antigravity's ruling on the flag's contract.
- The wiki verdict and the dashboard verdict come from two different runs a minute apart
  (exporter 01:40:34Z n=1495, this run 01:42:14Z n=1497) because the watcher added stamps
  in between. Same class, same peak lag, same interpretation; the difference is honest
  sampling, not disagreement. A future ingest should read the exporter's own result rather
  than re-running the correlation.
- The protocol passed on the first attempt, which the Round 95 handoff did not expect: it
  predicted series_ready PASS with the other five WAITing for the exporter cycle. The
  exporter's 15 s loop closed that gap in two seconds, so the cooldown line was already
  present by 01:41:00Z.
- Zero titans, zero receipts, no-lead: three honest nulls in a row. The knowledge layer
  now records all three as measurements rather than as absences.

## Round 101 findings

- The exporter change is the first knowledge-layer commit that touches daemon SOURCE.
  A pythonw process does not reload a module, so 56412 keeps printing the old header
  until its next restart; the maiden-night marker block is unaffected. The change is
  one string element per note, and the exporter suites pass.
- The sniper's receipt carries `edge` = confidence and `hurdle` = worst breakeven, both
  probabilities. That is the only pair of numbers for which "edge >= hurdle" reproduces
  the module's actual placement rule; a dollar edge would not.
- Bases filters use file.inFolder(...) rather than a property test because a nested
  `dev:` mapping is opaque to Bases; the folder-per-type layout carries the type.
- Templates omit stale_after on purpose with a comment: a fresh Concept page then
  draws a lint L7 warning until the human sets the review date, which is the nudge.
- The killswitch is a realised-loss budget (100-c); with fills only, the drawdown check
  is UNCHECKED and the page says why. Pairing closes is the unlock, not a heuristic.

## Round 100 findings

- Paper receipts are CSV, not JSON: latency_sniper, execution_log and amm_rewards all
  call Tax_Reserve_Agent.interfaces.receipts.log_execution_receipt, so the journal
  parses the writer's nine columns and takes the strategy tag from `notes` or the
  fills_<venue>_<strategy>_ filename. The folder is empty today; the journal exists
  for the quiet days too.
- The debrief cannot check the after-tax hurdle from a receipt: the writer records
  no edge, hurdle or breakeven. The page says UNCHECKED with the reason; stamping the
  hurdle on the receipt at write time is the backlog item that unlocks it.
- Scoring is mechanical on purpose: a prediction is a rule (field, op, value) over the
  Event page's recorded payload, the same shape as the sniper's registered rules, so
  the operator's forecast and the sniper's rule can be compared line for line.
- L7 exempts machine-maintained Concept pages (registers, history tables) or every
  register would warn forever; the exemption is structural (dev:register_for or
  dev:history), not a list of names.
- No prediction was recorded this round: a forecast is the operator's act, and the
  agent must not invent one to exercise the ledger. The tests do that with fixtures.

## Round 99 findings

- The "8 resolved EOA-to-proxy pairs" of Rounds 95-98 was an audit artifact: a
  `list(d.keys())[:8]` print. The cache holds 1,685 pairs. Corrected in the CRM
  docstring, the constitution (s.7 CRM) and this log; Antigravity's Round 99 prompt
  inherited the number and should be re-read with 1,685 in mind.
- A cache entry is not a titan. All 1,685 EOAs are whale addresses (the correlator
  resolved them from the whale table), and zero of their proxies are in
  sharp_traders / tracked_wallets. Presence on both venues is the test; today it
  yields 0 page(s).
- Judgement preservation is a body-section contract, not a frontmatter flag: the
  adapter re-reads `## Judgement` from the existing page and re-emits it verbatim.
  The test edits a page by hand, changes the database, re-ingests, and checks the
  hand text, `verified` and `status: stable` survived while evidence grew by one row.
- Epoch-millisecond timestamps (HL) and `YYYY-MM-DD HH:MM:SS` strings (PM) both
  render as ISO Z on the page; the first test expectation for the conversion was
  wrong and the code was right.
- The old title rule ("text after the citation") produced `Ratification 74-2: ).…`
  whenever a citation closed a parenthetical; titles are now the cleaned sentence
  that contains the citation, with the citation and its parentheses removed.

## Round 98 findings

- Every compiled type now has a register page and every Desk page links all five;
  that is the whole answer to L3 for adapter-written pages, and it means a new
  adapter needs exactly one line in registers.SPECS to be orphan-safe.
- The archived N=12 control's result numbers are dev:parameters on its own page:
  the memory rule "never overwrite the baseline" is now a lint C1 finding, not a
  sentence in a notes file.
- A calendar Event and a recorded Event are the same page: clob.compile_event merges
  window/sep/meeting from the registered page and keeps the recording's release_utc.
- Attested Computation pages cite their module as a source only when the file exists
  (L5 otherwise); requires_files likewise. The fixture proved both.
- The December FOMC statement is 19:00Z. It is asserted in a test, written in the
  YAML comment, and rendered on the page; three places for one copied-state trap.

## Round 97 findings

- C1 caught a real ambiguity on the first real run: `"min_points"` occurs twice
  in lead_lag_tier2b.meta.json (series.readiness 200, bars 60). Regexes cannot
  scope JSON; `dev.parameters[].json_path` (dotted path) now addresses JSON
  sources and the experiments adapter emits it instead of a pattern.
- Registration pages had no inbound link (L3). Rather than editing seed-owned
  pages from an adapter, a machine-maintained wiki/concepts/experiments_register.md
  lists every Experiment page (registrations and verdicts) and Desk 3 links it,
  the Regime page and the latency-decay Concept.
- Table cells need `[[page\|alias]]`; the wikilink extractor now strips the
  escaping backslash, otherwise every table link is an orphan-maker.
- `raw/index.md` lists absent streams as `> not present` notes; parse_index
  accepts `> ` lines so the reserved grammar stays strict for entries.
- The seed's log text no longer names a round; log.md was restored from HEAD and
  regenerated so this round's bullets are accurate (Seed with generated.at, Ingest).
- lead_lag verdict JSON has no explicit tier: the adapter takes --tier from the
  operator, and refuses a --check-data payload (no `sufficient` key).
- Round 97b (research, no code): LLM_WIKI_BACKLOG.md. Fresh gap scan: Desk 1 has
  zero compiled pages against 27,916 cascade_excursions, 9,312 basis windows,
  8,844 whale_wallets and 3 HL *.meta.json registrations; AGENTS.md cites 24
  distinct Directives/Ratifications/numbered Rulings with no page; only 2
  dashboards print a Shell twin; edge_opportunities are 96 rows all vs pinnacle
  (moneyline 36 / spread 24 / totals 36); Daily Notes and Templates enabled but
  unconfigured; FOMC Oct 27-28 (18:00Z) and Dec 8-9 (19:00Z, EST shift) can be
  pre-registered now. From the field (LLM Wiki v2 / agentmemory, OKF v0.2, Bases,
  trading-journal and pre-registration practice): adopt typed relations,
  crystallised round digests, a calibration ledger, per-type stale_after policy,
  Bases views, usage_count; reject embeddings, forgetting curves, self-healing
  lint, auto-ingest daemons, mesh sync. 20 scored items sequenced: Round 98 =
  compile what exists (HL registrations, directives catalogue, Attested
  Computation pages, FOMC calendar, Market pages); 99-100 = CRM + journal +
  relations + staleness; 101 = views/templates/backlinks; 102+ = cascade Events,
  sweeper post-hoc evaluation behind a pre-registered bar, funding regime,
  counterfactual paper P&L, quant-lab digests. Eight rulings requested.

## Round 96 findings

- The seed is a compiler, not a template filler: Item pages are parsed from
  the registry's `[x] ITEM N:` blocks and their `- Key:` fields; a change to
  the registry re-seeds with --force. The registry itself is untouched.
- R1 and R3 do not exist in the record. Whole-word search of AGENTS.md,
  COMMANDS.txt, module docstrings and `git log` finds R2 (49f85f8), R4
  (da48cf3), R6 (fe40a1a) and a pending R5 only. Antigravity to supply R1/R3.
- The literal `verified.by: antigravity` in R95-D is not an OKF actor string
  (needs human:/process:/producer-slash-version); the canonical spelling is
  `antigravity/architect`, defined in WIKI_SCHEMA.md s.2.
- Orphan check needs every Desk reachable without items: Desk pages link
  their sibling desks, so a small fixture (or a desk with no registry items)
  is not an L3 finding.
- Seeds only emit dev:asserts/parameters whose file exists under --dev-root,
  so the same seed is lint-clean in a fixture and fully guarded in DEV.
- pyyaml is already a dependency (Tax_Reserve_Agent/config.py, quant lab);
  python-markdown is present but not used by the package.
- Round 96b: WIKI_SCHEMA.md had shipped with a `verified: antigravity/architect`
  block the generating agent wrote itself, on the strength of R95-B ratifying
  the BLUEPRINT, not this text. That breaks the constitution's own s.2.
  Removed; status draft until Antigravity verifies the constitution explicitly.
  Ruling pages R2/R4/R6/R95 keep `verified` because their text IS Antigravity's
  ratification; note `verified.at` there is the seed time, not the ratification
  time (question 6b in the cross-check).

## Round 95 findings

- Read-only audit, 15:24-15:32 EDT. SQLite opened with `file:...?mode=ro`.
- Highest-value evaporating streams, ranked: post-print book decay (survival
  curve prints to console; 1,260 stamps due 2026-09-16), lead-lag verdicts
  (overwritten in a marker block every 15 s), rulings R1-R6 as prose only,
  cascade/liquidation events, entity identity (8 resolved EOA->proxy pairs in
  titan_identities_cache.json never reach the 120 entity notes), 96 unreviewed
  edge_opportunities, the 4 experiment meta files, statute rationale in
  config.yaml comments, the empty 2026-09-02.md daily note.
- Vault: 11 dashboards (52 KB) + 79 whale + 41 wallet notes, all whole-file
  overwrites; only Cross_Market_Titans.md uses marker blocks; Bases, Daily
  Notes, Properties, Templates, Graph, Backlinks all enabled.
- OKF v0.2 verified from the spec (June 2026, GoogleCloudPlatform/
  knowledge-catalog): only `type` is required; reserved index.md / log.md
  formats adopted verbatim; unknown keys must be tolerated (hence `dev:`).
- No repo file other than LLM_WIKI_BLUEPRINT.md and this log was written.

## Round 94 findings

- **Dollar-seconds is the number.** A $3M book that dies in one second and a
  $3k book that survives twenty minutes are both small; fillable notional
  integrated over the seconds after the print ranks targets by size times
  survival, which is what Round 92 said the edge actually is.
- **A change is not a kill.** The first-change second comes from the CLOB book
  hash, and a new resting order changes the hash too; so half_s / tenth_s /
  gone_s measure depletion, and first_change_s is only the earliest the book
  could have been touched.
- **A silent replace is a bug.** Twenty commits of docs scripts "updated" a
  MASTER_COMMAND_LIST header line that did not exist in the form they searched
  for; every docs replace now asserts its anchor first.

## Round 93 findings

- **The date was wrong by a day, everywhere.** Every reference this week said
  "September 17"; the Fed calendar says the meeting is September 15-16 and the
  statement lands on the 16th at 18:00Z. Corrected before any window as a dated
  re-registration (the file records the correction); tokens and thresholds
  unchanged. Lesson: a scheduled-release drill is anchored to the issuer's
  calendar, not to a date repeated in prompts.

- **The cut markets do not exist yet.** The drop holds "no change", "hike
  25" and "hike 50+" for September 2026 - and the hold/hike pair is priced
  50/50. Registering what exists today with real token ids, and listing
  what does not, is what makes the file a registration instead of a
  template; anything new is appended before the window, dated.
- **Cadence is measured against a clock the test controls.** Fetch time
  is subtracted from the interval, so a 0.3 s fetch pair on a 1 s cadence
  sleeps 0.4 s; the test asserts that number.
- **429 is expected, not exceptional.** Seven minutes of one-second polling
  on three tokens is 1,260 GETs; the loop backs off and keeps the stamps it
  has rather than dying at the moment that matters.

## Round 92 findings

- **Knowing the outcome makes every level profitable, so depth at rest is
  not the edge.** At confidence 0.995 the after-tax breakeven at odds 1.96
  is 0.606, at odds 1.02 it is 0.986 - both cleared - so the walk takes the
  whole book. The sniper's real variable is the seconds between the print
  and the cancels, measurable only during a live release (R2).
- **Thin vs thick is a 1,000x range in resting depth** ($400 vs $3M of YES
  depth) at the same moment; any Phase 2 target list must be chosen by
  depth-times-survival, not by volume.
- **The registry is 80-484, not 80-415.** Items 19 and 20 live past 415;
  earlier byte-identical assertions covered a subset and were never wrong,
  but the constraint text should say 80-484.

## Round 91 findings

- **Competitor Q is not an assumption any more.** One real stamp gives
  Q_min 28,828 against a 100-share quote's 25: a 0.09% share. The
  simulator's default competitor_q of 1,000 was optimistic by ~30x for
  this market. The pool rate is now the only unmeasured input.
- **Scoring a price level equals scoring its orders** because the
  programme's score is linear in size; a depth snapshot is therefore
  sufficient, no per-order data needed.
- **Live mid, not fair.** The replay uses (best bid + best ask)/2 as the
  programme does; the simulator's mid = fair is now the documented
  difference between the two tools.

## Round 90 findings

- **The APY claim reduces to two inputs the module cannot observe.** Making
  pool size and competitor Q explicit parameters, printed as "ASSUMED" in
  every result, is what keeps the simulator from becoming a forecast.
- **A bounded price needs clamps the textbook model does not have.** The
  reservation price and spread come from Avellaneda-Stoikov; the tick grid,
  the (0, 1) bounds, never crossing fair, and the one-sided inventory limit
  are the prediction-market additions.
- **Accounting is asserted, not trusted**: cash and inventory are recomputed
  from the fills in the test and must equal the simulator's own totals.

## Round 88 findings

- **Ruling R4 is enforced in code, not in prose.** Book carries `neg_risk`
  (from the live stamp's field); evaluate() skips a NO outcome on a
  neg_risk book with the reason "NO side deferred to Phase 2 (Ruling R4)"
  and still lifts the winning outcome's YES asks. A standalone market's NO
  side is unchanged.
- **Registry reconciliation.** Antigravity reports "17 of 20 complete";
  lines 80-415 show Items 7, 10, 11, 12, 13 unchecked. Items 10 and 12 have
  Phase 1 built (modules 20 and 21) but are not complete; their checkboxes
  were NOT changed (lines 80-415 preserved). A ruling is needed on whether
  a Phase 1 build checks the box or the Status line reads "Phase 1 built".

## Round 87 findings

- **The one untested path was broken, and the probe found it.** The
  recorder's live GET (the only network call in Item 12) got HTTP 403 /
  Cloudflare error 1010 with Python's default User-Agent; a browser-style
  User-Agent returns the book (43 bids / 47 asks on the live "no change in
  Fed rates" market, price/size as strings, plus asset_id, hash,
  last_trade_price, min_order_size, neg_risk). Fixed (FETCH_HEADERS); the
  extra fields are kept on each stamp as provenance. Lesson: a test that
  injects the transport proves the parser, never the wire - probe the wire
  once, read-only, before anyone relies on it.

- **Rules must fail to nothing, not to NO.** "twenty-five" == -25 is False,
  which would have resolved the market to NO and hit the bids. A numeric
  rule now requires a numeric payload; anything else says nothing about the
  market. Found by the test, fixed in the engine.
- **A NO outcome is a BUY of the other side.** Hitting a YES bid at b is
  buying NO at (1 - b), so the walk uses (1 - bid) as the price and the same
  breakeven test; no second code path.
- **The cap is fixed at the best level's odds** and spent down the book, so
  a deep second level cannot grow the position past what the first level
  justified.

## Round 85 findings

- **Acknowledge before acting.** The offset is saved for each update before
  the command runs, so a crash mid-/halt cannot replay it on restart; the
  stale window (120 s) is the second guard for the same failure.
- **The token has three exits and all are closed**: it never enters argv
  (env var only), every log line passes through redact(), and --status
  reports set/unset. The transport's own error text is redacted too, since
  the API URL embeds the token.
- **Fail-closed means not starting.** An empty allowlist does not "reject
  everything at runtime" - it refuses to claim the lock at all, so a
  misconfigured bot cannot even consume the update queue.
- **/halt writes the sentinel the HL config already reads**
  (dynamic_config.is_halt_flag_present checks DEV/HALT.flag), so the bot
  adds no new code path to the execution guard - only a new way to trip it.

## Round 79 findings

- **`--stop` reuses the lock's own liveness test**, so it can only ever
  terminate a process that the lock names AND whose command line is a
  watcher. A reused pid belonging to something else reads as a stale lock:
  swept, not killed. `taskkill /F /PID <pid>` had no such guard.
- **The verification is in the probe, not in the operator's eyes**: the
  newest macro stamp either carries `tags` or it does not, and `--status`
  now says which. The first stamp after the restart lands within one poll
  (5 min).
- **The restart bat has no if-blocks by design** - the two cmd traps of
  Round 73 cannot recur in a straight-line script; the guard lives in the
  launcher it calls.

## Round 77 findings

- **Membership is a different experiment, not a different filter.** The
  same two subfamily names under Tier 2 and Tier 2b select different
  markets, so the mode is a first-class parameter (`subfamily_from`) that
  the report carries and the CLI header shows as "(tags)". A run cannot be
  mistaken for the other tier after the fact.
- **Untagged records are skipped, never guessed.** Inferring a `tags` list
  from `sport` for pre-restart stamps would reproduce first-tag-wins and
  call it membership. Tier 2b's series therefore starts at the watcher
  restart, and its readiness is measured on tagged stamps alone.
- **The registration copies the bars and adds only what differs.** The
  bars dict is asserted equal to Tier 2's; the file is new; Tier 2's file is
  asserted not to mention Tier 2b.
- **A latent test-order hazard surfaced.** polymarket_fetcher bound
  `log=print` as a default at import; test_lead_lag imports the fetcher
  lazily inside mock.patch("builtins.print"), so when it ran FIRST the
  poll's default log was a dead mock for the rest of the process and the
  tee test lost its [DROP] line. The master suite never saw it (exporter
  before lead_lag). Fix: `_emit` resolves print at call time. On-disk only,
  inert for the running watcher.

## Round 76 findings

- **An on-disk edit and a live process are different things.** The
  ratification gates the fetcher change to protect the continuous series
  from a watcher restart; the edit itself touches nothing that runs. The
  code is committed and tested now, and the only post-maiden step is the
  restart that activates it. A failed restart before READY could have reset
  the 24 h clock; after the verdict it costs nothing.
- **Provenance and precedence are separate fields.** `sport` stays the
  first-tag label (what every consumer reads today); `tags` is the union.
  Nothing downstream changes until someone chooses to read `tags`.
- **The registered Tier 2 filter deliberately ignores `tags`**: under
  first-tag-wins a dual-tagged market sits in exactly one subfamily, which
  is what lead_lag_tier2.meta.json registered. Counting it twice would be a
  new analysis, to be registered as such.

## Round 75 findings

- **A transient read failure would have become the maiden verdict.**
  lead_lag.run swallowed any exception from load_mark_series as "no prices";
  the report then read "fewer than 60 overlapping minutes", the refresher
  wrote that as an honest-looking "insufficient" block and started a 24 h
  cooldown. The HL database is in WAL mode, so a lock is unlikely - but a
  missing file, a permissions blip or a collector migration at 01:40Z would
  have cost the day. Now `price_error` is its own outcome and is never
  recorded.
- **An "insufficient" verdict at the maiden minute is a data hole, not a
  finding.** The pre-registered bar is about the stamp series and the
  correlation threshold; how soon the loop retries a non-verdict is
  operations. Default 1 h, flagged for ratification.
- **The note is the single clock.** The block already carried the run-at;
  it now also states the cooldown it was written with, so a restarted
  exporter (or one started with a different flag) honours the length that
  was actually promised.
- **Directive 75-1's four steps are one command with exit codes**, so the
  01:40Z check can be pasted by whoever is at the keyboard; Tier 2 cannot be
  run early by mistake - the protocol refuses until the run-at marker exists.

## Round 74 findings

- **The running exporter predated its lock.** Deploying a lock does not
  retrofit a holder: pid 3556 held nothing, so `--status` would have said
  STOPPED and the guarded sync bat would have started a second loop. The
  loop was restarted through the launcher the moment the code landed; the
  cooldown lives in the note and readiness in the stamps, so a restart costs
  nothing.
- **The mark word is the lock's identity.** `is_stale` treats a live process
  whose command line lacks the mark as a stale holder. "obsidian_exporter"
  would have accepted a Sports Desk exporter after pid reuse; "cross_market"
  is in every way this loop can be started (-m or path) and in no other
  exporter.
- **Tier 2 reads a label that already exists.** Antigravity's `tag_slug` is
  not a drop field; Round 52 stored the Gamma tag as the question's `sport`
  (CRYPTO 212 / FED-RATES 97 in the newest drop). First tag wins in the
  fetcher's dedupe, so a market tagged both ways is CRYPTO - recorded as a
  caveat, not fixed, because changing the fetcher's labelling before the
  maiden run would change the Tier 1 series.
- **The latency rule is a reading rule, not a bar.** A crypto milestone
  question re-marks because BTC moved, and the watcher sees it up to one
  poll later; a peak within 5 min is reported as repricing. Tier 1 passes
  latency 0 and keeps its wording; a planted 3-min lag reads "leads by 3 min"
  under Tier 1 and "contemporaneous repricing" under Tier 2 - both true.
- **Verification protocol strings checked against the code**: the loop
  prints `lead-lag: RAN BTC -> Cross_Market_Titans.md written (<verdict>)`
  once, then `lead-lag: READY, next run in 24.0 h` counting down each cycle;
  `--status` shows `last run <ISO>` from the note's run-at marker.

## Round 73 review findings

- **The regression and the gate read different series.** The sentinel
  counts macro stamps; load_drop_records read every *.json in the folder,
  sports included. Forced today: all drops 1,084 markets / 2,263 shifts /
  corr -0.178; macro only 413 / 384 / corr -0.195. Both "no measurable
  lead-lag" - and both already "sufficient", so the maiden run will not say
  "insufficient" as feared; it will say there is no lead-lag at |corr| 0.2.
  The refresher now reads family="macro"; research CLI default unchanged.
- **A batch-file trap cost the watcher a minute**: `for /f ... set PYW`
  inside `if errorlevel 3 ( ... )` is expanded at parse time, so
  Start-Process got an empty path (rc 255). The lookup now precedes the
  block (start_collector.bat had it at top level all along).
- **Detached loops log to files** because pythonw has no stdout: tee_stdout
  routes prints to the console when there is one and always to the file.
- **Two exporters on one vault are safe**: hash-skip on notes, the lead-lag
  cooldown in the note, the risk card judged by mtime - so the operator's
  sync bat may start a second console loop without a double maiden run.

## Round 73 findings

- **The note is the cooldown state.** A state file would drift from the
  note and a restart would rerun early; the run-at comment inside the
  lead-lag block is read back by the refresher, so one run per 24 h holds
  across restarts and even across two exporters on the same vault.
- **The gate is the sentinel's own function** (data_readiness over
  stamped_moments), so the card and the trigger cannot disagree; the
  refresher is a file-name scan per cycle until READY.
- **A run that says "insufficient" is still a run.** The block shows the
  reason and the cooldown applies; by the next attempt there is a day more
  of data. The runner is injectable, so the tests never open a database.
- **refresh_sentinel_block became a wrapper over refresh_marked_block** so
  a third block can join later without a third copy of the splice logic.
- **Round 72 shipped nothing** (verification only; readings matched).

## Round 71 findings

- **Launcher lines are configuration nobody else tests**, so the flag is
  pinned by a test that reads both bats and checks every HL watcher line;
  the same test pins the code default at 0 so a future "helpful" default
  cannot throttle on-demand exports silently.
- **Two launchers, not one**: the HL tree's own start_obsidian_sync.bat
  starts the same watcher; the HL-tree start_all_ecosystem_sync.bat does
  not (it delegates), so it was left alone.

## Round 70 findings

- **The throttle is judged on mtime, not on in-process state**, so a second
  exporter (or a manual --once) sees the same cooldown, and a restart does
  not reset it. It gates only the market note; Bot_Control, the terminal,
  the config note, the hub and the whale dossiers keep their own hash-based
  skip.
- **Throttle and hash compose**: past the cooldown, unchanged content is
  still skipped by the hash; inside it, even changed content waits. The
  test pins both orders.
- **Not wired into start_all_ecosystem_sync.bat** - the ruling made it
  optional; the operator adds --throttle-seconds to the HL sync line if the
  git churn of the live dashboard matters more than its 15 s freshness.

## Round 69 findings

- **Most of the churn in those notes is real.** The diff between HEAD and the
  working tree showed equity, accrued funding, the funding-pair census,
  perp prices and the collector's PID all changed: that is state, not
  clocks, and it stays hashed. The clock-only fragments were three: "Ns
  ago" freshness badges, the Duration column, and the Realised APR cell.
- **Realised APR is a clock in disguise**: accrued / notional / hours_held
  moves every sync even when nothing accrued, because hours_held is
  fractional. Its information is the Funding Accrued cell beside it, which
  stays hashed, so hiding the APR cell loses nothing substantive. The
  Entry APR is a parameter and stays hashed (the pattern targets the
  seventh cell of a position row only).
- **Fragments, not lines**: a Bot_Control line carries the PID and the "Ns
  ago" together; dropping the line would hide a collector restart.

## Round 68 findings

- **The header line was not the only clock.** Normalising only "Feed
  Liveness: X ago" would have left the section's "newest quote X ago" and
  every hit's "Ns old" ticking, and the note would still have rewritten
  each minute. Four substitution patterns cover every age fragment; each
  keeps the verdict or count next to it so state changes still hash
  differently (test: +1 min -> unchanged, +16 min -> STALE -> rewritten).
- **Substitute, do not strip**: the existing _VOLATILE patterns delete whole
  lines; these replace only the number so the verdict survives.

## Round 67 findings

- **The header verdict and the section warning are the same measurement**
  (newest quote in the whole table vs FEED_STALE_SECONDS), rendered twice
  on purpose: the header answers at a glance, the section explains.
- **The cap keeps the note readable on a busy Sunday and says what it hid**;
  the Shark's --stale (and --json) remain the complete list.
- **Two knobs, one value**: separating pipeline liveness from quote
  actionability lets a slow drop cadence widen the feed window without
  making a 20-minute-old retail price actionable.

## Round 66 findings

- **Feed liveness is measured over the whole table, not the window.** With
  the window alone, "no quotes in the last 180 min" and "no quotes ever"
  read the same; the newest-quote-anywhere figure separates a paused
  collector (newest 200 min ago -> "no recent quotes in window") from an
  empty database ("no quotes in the database") from a live but quiet
  market (no warning, 0 moves).
- **The directive's exporter path was wrong**: there is no
  Sports_Desk/reports/; the note is written by
  Sports_Desk/interfaces/obsidian_exporter.py, where the section now lives,
  built from the same scan_to_dict the CLI prints.
- **JSON mode prints no prose**: the display-only sentence is for humans;
  tools get the dict (thresholds included) and nothing else on stdout.

## Round 65 findings

- **The panel is the engine's renderer, nothing more**: show_stale calls
  scan_market_db on the slip's DB with the slip's clock (tests pin the
  clock through `now`), so the HUD and the engine cannot disagree. The
  live sports_market.db holds sample quotes and reports 0 sharp moves.
- **Display-only is stated in the panel itself**, next to the edges,
  because a latency edge is measured before vig and tax and decays by the
  minute; the Shark's staking paths remain the only way to record anything.
- **Registry synchronised**: Antigravity regenerated its Top 20 from the
  master list (15 of 20; Items 7, 10, 11, 12, 13 on the roadmap; stale
  quotes under the Sports Desk). The three-round disagreement is closed.

## Round 64 findings

- **The drill cleans up after itself by default.** Ten synthetic dutches left
  in cross_market/data/paper_receipts would make the simulator "measure" a
  desk that never traded; every drill receipt carries drill:1 and the drill
  removes exactly those (a hand-written paper receipt survives - tested).
  Reproduce in seconds: python -m cross_market.paper_drill.
- **"Item 11" in the directive is not the master list's Item 11.** The
  registry in MASTER_COMMAND_LIST.txt has Item 11 = Automated Prop Firm /
  CME Futures Execution Gateway; "Multi-Bookmaker Stale Quote & Latency
  Arbitrage" comes from Antigravity's divergent checklist (flagged twice).
  The engine was built because it is useful groundwork, filed under the
  Sports Desk with no item renumbering. The registry disagreement is still
  open for the operator to settle.
- **Velocity, not size, separates information from drift**: the same 5.6-pt
  move counts in 4 minutes and is ignored over 175; staleness is judged
  against the move's END, so a retail quote 30 s before the end is "not
  yet stale" and a re-quote after it is "re-quoted", never a false hit.
- **Live at close**: before: arb desk assumed (< 10 arb fills);after:  arb desk measured (paper_receipts receipts, 20 fills / 10 arbs over 10 calendar days);closed loop: PROVEN (10/10 dutches recorded, 0 fills -> 20, receipts cleaned).

## Round 63 findings

- **Paper fills must never reach the ledger.** The directive asked that paper
  or live fills both drop a Polymarket receipt; a receipt in the Tax imports
  is ingested into the live ledger that Ruling 34-D keeps at $0.00. Paper
  mode therefore writes both legs as receipts into a paper folder the watcher
  never reads, and skips placed_bets, whose rows are the desk's live exposure.
  The paper folder is still measurable by _measure_arb_history (the gross:
  note prices the dutch; the book leg's price is odds, not a share price).
- **The Shark is a recorder, not an executor**: stake_cross_market records
  what the operator executed by hand, exactly as stake_arbitrage does for
  book-vs-book, with the same wholesale refusal shape. There is still no
  automated cross-market execution; when one exists it calls record_dutch.
- **Path refusal is a CLI rule only.** record_dutch() still creates a fresh
  desk DB or folder when called from code (a first execution on a clean
  install must work); the CLI refuses explicit paths that do not exist so a
  typo cannot spawn a stray ledger.
- **The exclusion of arbitrage legs keeps the sports desk's win rate
  directional**: 30 settled hedged legs beside 24 directional wagers leave
  cadence and win rate at the 24 - tested.

## Round 62 findings

- **There is no executor to wire, so the seam is the deliverable.** The
  cross-market desk is scanner-only; record_dutch() is what an executor (or
  the operator, via the CLI) calls at fill time. It is proven end to end: ten
  recorded dutches make _measure_arb_history report 10 fills / 10 arbs and
  load_live_inputs switch the arb desk to "measured".
- **A cross-market dutch has one receipt and one wager.** The book leg is a
  placed_bets row (its own arb_group column, bet_kind "arbitrage" as
  monarch_shark already uses), not a Polymarket receipt, so a receipt alone
  cannot price the dutch. The recorder writes gross / cost into the receipt's
  notes and the reader prefers them; the worse branch prices the dutch
  (payout = min(shares x $1, stake x odds)).
- **Ruling 62-1 both sides**: the writer passes one timestamp to both legs;
  the reader clusters loose receipts within 60 s of a group's first fill
  (59 s apart = one dutch, 61 s = two) and groups by arb_group first.
- **The book legs also land in placed_bets as wagers**; below 20 settled the
  sports desk stays assumed, and a settled arb leg will count toward the
  sports cadence later - by design, since it IS a wager the desk placed.
- **Live at close**: stress calibration - shock = daily realized vol > 3.0x the COIN's median; a coin qualifies with >= 14 days;XPL           3 day(s) with >= 12 hourly returns - not enough (< 14);para:ANSEM    3 day(s) with >= 12 hourly returns - not enough (< 14);portfolio: nothing qualifies yet - stress inputs stay assumed (0.02 / 3.0x);sports settlement: < 20 settled wagers - cadence and win rate stay assumed;arb receipts: < 10 fills matching fills_*_dutched_arb*.csv - arb inputs stay assumed;held coins: para:AN.

## Round 61 findings

- **Per-coin medians, per-coin gates, unweighted means.** A coin with fewer
  than 14 days is skipped rather than diluting the pool; the portfolio
  shock probability is the mean over qualifying coins, the multiplier the
  mean over coins that had a shock day. Test: ANSEM at 3x XPL's baseline vol
  with one 9% day reads 1 shock in 20 per coin; pooled it would have read
  every ANSEM day as a shock.
- **Calendar-day cadence only lowers the number**: 20 wagers on two dates
  two weeks apart are 1.43 a day, not 10. A one-day history has a one-day
  span by the ruling's own formula.
- **Arb executions are receipts grouped by timestamp.** The receipt contract
  (Tax_Reserve_Agent/interfaces/receipts.py, Polymarket strategies/base.py)
  writes ONE FILE PER LEG named fills_polymarket_<strategy>_<stamp>_<uuid>.csv
  with the strategy in `notes`; the two legs of a dutch share the second.
  Gross return per execution = 1 / sum(BUY leg prices) - 1; capital =
  sum(price x qty). Receipts say nothing about leg failures or desync, so
  arb_leg_fail_prob / arb_desync_loss_max stay assumed even when the rate
  and return are measured.
- **The audit report is the calibration's own view**, not a re-derivation:
  it calls the same functions the loader calls and prints their inputs, so
  what it shows on 15 September is exactly what the simulator will use.
- **Live at close**: stress calibration - shock = daily realized vol > 3.0x the COIN's median; a coin qualifies with >= 14 days;XPL           3 day(s) with >= 12 hourly returns - not enough (< 14);para:ANSEM    3 day(s) with >= 12 hourly returns - not enough (< 14);portfolio: nothing qualifies yet - stress inputs stay assumed (0.02 / 3.0x);sports settlement: < 20 settled wagers - cadence and win rate stay assumed;arb receipts: < 10 fills matching fills_polymarket_dutched_arb*.csv - arb inputs stay assumed;held coins: para:ANSEM, XPL.

## Round 60 findings

- **"95th percentile" would have measured nothing.** Defining shock days as
  the top 5% of days sets the probability to 5% by construction. The
  directive's alternative, 3x the pooled median daily vol, is the criterion
  used; the multiplier is mean shock vol / median. Days need >= 12 hourly
  returns to count, the pool is coin-days across the held perps, and the
  gate is 14 DISTINCT days. The live DB has 3.9 days, so today both stress
  inputs are "assumed (< 14 days of marks)" - the measured path is proven on
  synthetic 20-day histories (2 shock days -> prob 0.10, multiplier ~6).
- **Pushes are neither wins nor losses.** Win rate = wins / (wins + losses);
  cadence counts pushes (a wager was placed); the provenance names the
  pushes excluded. The live placed_bets table is empty, so sports stays on
  the edge-table probabilities and the assumed 3/day, labelled.
- **Cadence is now fractional without touching integer behaviour**: 2.4/day
  is 2 wagers plus a 40% chance of a third; an integer rate consumes the
  same random stream as before, so every earlier result reproduces.
- **Live at close**: systemic stress: correlation 0.50, shock-day prob 0.020 (7.3 days/path), vol x3.0 on shock days; inputs measured: basis_capital_per_position, basis_daily_vol, basis_funding_apr, basis_funding_autocorr, basis_funding_hourly_std, basis_positions, equity, sports_decimal_odds, sports_win_prob_mean, sports_win_prob_std, tax_rate; inputs assumed:  arb_capital, arb_desync_loss_max, arb_gross_return, arb_leg_fail_prob, arb_per_day, basis_funding_half_life_days, basis_funding_long_run_apr, basis_leverage, basis_liquidation_cost, basis_rebalance_days, basis_tail_df, sports_bankroll_fraction, sports_bets_per_day, sports_kelly_fraction, sports_max_stake_fraction, stress_day_prob, stress_vol_multiplier.

## Round 59 findings

- **Refresh cadence and cost were traded explicitly.** The CLI's 100,000
  paths plus the 7 x 20,000 grid take ~25 s; inside a 15 s loop that would
  freeze the arb export and the Titans sentinel for the whole refresh. The
  loop refresh uses 20,000 paths and a 5,000-path grid (~5 s) and the card
  prints its path count, so the CLI run stays the reference figure.
- **"Significant shift" is the paper book's signature**, read from the small
  JSON every cycle: equity to the HUNDRED dollars, position count, coin set.
  Hundreds because basis_harvester.accrue adds every hourly funding accrual
  to cash (my handoff first assumed it did not); dollar rounding would have
  re-simulated every few hours on accruals alone. A position opening or
  closing moves equity by thousands and re-simulates at once; the databases
  are read only when a refresh runs. The signature is taken AFTER the run so
  a book that moves during the simulation triggers again next cycle.
- **Stress is a correlation applied to three levers on the same day**: perp
  vol x(1 + c(mult - 1)), funding x(1 - c) minus c x |daily mean| (flips at
  c = 1), arb leg-fail x(1 + c). The shock mask is drawn every day whatever c
  is, so c = 0 reproduces the unstressed run bit for bit under the same seed.
  Sports wagers are untouched: nothing links a moneyline to a crypto squeeze.
- **Live at close**: systemic stress: correlation 0.50, shock-day prob 0.020 (7.3 days/path), vol x3.0 on shock days;VaR99 365d baseline 3.49% -> stressed 3.51% (+0.01 pp); practical ruin 0.0000 -> 0.0000;buffer $3,505 -> $3,519 (+15); basis P&L -156; arb P&L -10; liquidations/path 0.153 -> 0.172
 | exporter --once: risk: Risk_Sentinel.md unchanged (20,000 paths).

## Round 58 findings

- **The first live run was wrong by 40x and the inputs said why.** With the
  book's entry funding APR as a year-long mean, the basis desk earned $295k
  on $40k: para:ANSEM was opened at 2,924.7% APR and the 69 h snapshot mean
  is still 589.6%. No desk earns that for a year, and the harvester's own
  gate rotates such positions out. The model now starts the funding level at
  the DB-measured mean and decays it toward basis_funding_long_run_apr (25%,
  the entry gate, assumed) with basis_funding_half_life_days (7 d, assumed);
  the entry APR is kept in the provenance text as context. Basis P&L became
  $6.4k / yr.
- **Ruin never binds for a spot-backed book, so the grid needed a second
  constraint.** Without it the shrinkage always pointed at the top of the
  grid. Allocation (basis capital + sports bankroll + one arb) must fit inside
  the equity; rows over 100% are marked and excluded. The result names its
  binding constraint - today "allocation": x2.00 fits (92%) with zero ruin,
  which means risk is not the limit at these sizes, not "double the book".
- **Two ruins, both honest.** Hard ruin (equity <= 0) is 0.0000 everywhere
  and would stay so; practical ruin (-50%) is the number to watch. Tax
  escrow leaves the trading bankroll and counts as drawdown by design.
- **Liquidations at 1x are real but rare**: Student-t(3) daily moves at the
  measured 12% vol (XPL 8%, ANSEM 16%) liquidate the short leg ~0.16 times a
  year; the test bound was loosened to that reality.
- **Live at close (measured inputs, 100k paths, seed 7)**: ruin: practical (-50%)   30d 0.0000 | 365d 0.0000; max drawdown VaR: 95% 30d 0.71% | 99% 30d 1.13% | 95% 365d 2.94% | 99% 365d 3.51% (median 365d 2.03%); terminal equity p05 $105,928 | p50 $109,238 | p95 $112,544; median log growth +0.0852; escrow median $4,261; desk mean P&L: basis $6,437 | sports $2,285 | arb $4,470 | tax -$4,273; liquidations/path 0.156; buffer: keep $3,524 unallocated (VaR99 365d drawdown = 3.5% of equity); size every desk at x2.00.
- **Test premises fixed, not the engine**: the "doom" wager used 1.05 odds
  where Kelly is negative (nothing staked); the 1x liquidation bound ignored
  fat tails.

## Round 57 findings

- **Directive path corrected**: there is no cross_market/exporters/; the
  exporter is cross_market/interfaces/obsidian_exporter.py and the Titans
  note is written by titan_correlator.export_to_obsidian (manual --scan). A
  block that only a manual scan refreshes would go stale at once, so the
  15 s Arb exporter loop refreshes the marked block; the correlator still
  owns the note and its creation.
- **Two writers, one file, no fight**: refresh_sentinel_block replaces only
  the text between <!-- lead-lag-sentinel:start/end -->; an older note gets
  the block inserted before the architecture section; a missing note is left
  missing. Both writers go through write_note_if_changed, and the sentinel's
  **Checked** line joined _VOLATILE_PATTERNS, so a refresh with the same
  numbers is a no-op. Proved live: `exporter --once` right after `--scan`
  reported "sentinel: Cross_Market_Titans.md unchanged".
- **The gate is code, not a note.** `python -m cross_market.lead_lag` with no
  --drops / --events runs data_readiness on DEFAULT_DROP_DIRS first and exits
  3 with the sentinel text and a [GATE] line; --force runs anyway; explicit
  --drops / --events (research data, the Round 51 tests) are never gated.
- **Fixture clocks vs the real clock**: the exporter test first anchored its
  stamps at the fixture NOW (2026-09-04); the CLI run uses the real clock,
  saw a 15 h-old series, and correctly rewrote the block as stalled. The test
  now writes real-clock stamps for the CLI part. The sentinel's behaviour was
  right; the test's premise was wrong.
- **Refresh cadence depends on the operator session**: the block updates
  while "Cross-Market Arb Obsidian Sync" (start_all_ecosystem_sync.bat) runs;
  no exporter was running at close, so the note shows the 02:49Z scan until
  the sync bat is started. The correlator's --scan also refreshes it.

## Round 56 findings

- **--status is read-only and speaks in exit codes.** It never sweeps,
  starts or stops anything (the stale lock it reports is left for the next
  start to sweep). 0 = a live watcher holds the folder lock, 3 = none does,
  so start_all_ecosystem_sync.bat decides with `if errorlevel 3` and no text
  parsing. Unprefixed stamps (single-tag runs, Round 52) are reported as
  sports because that is what they were. Holder start time and command line
  come from psutil, best effort; the holder pid does not depend on it.
- **"Continuous" got a number.** Stamps are written only on price change and
  a dead watcher leaves a hole, so the sentinel counts only the latest
  segment whose consecutive stamps are <= 60 min apart (--max-gap-minutes).
  A newest stamp older than that gap means nothing is accumulating: NOT
  READY with no ETA and "restart the watcher". Otherwise the ETA is the LATER
  of segment_start + 24h and now + (200 - points) / observed rate.
  --min-ready-points is deliberately not --min-points, which lead_lag already
  uses for the correlation overlap.
- **Live reading at close**: fetcher --status: RUNNING pid 29420 (exit 0); lead_lag --check-data: NOT READY, 12 points over 0.8h since 2026-09-05T01:39:49.923098+00:00, newest age 2 min, ETA 2026-09-06T01:39:49.923098+00:00 (exit 3). Antigravity's "after 2026-09-06T02:00Z" and
  the sentinel's ETA agree within the restart drift of Round 55.
- **The guard was exercised in isolation** (a scratch bat with the same
  `if errorlevel 3` block took the "kept" branch against the live watcher);
  the full sync bat was not run because it opens eight consoles.

## Round 55 findings

- **The lock is keyed to the drop folder, not the machine.** The harm is two
  watchers rewriting ONE folder's canonical files and doubling its stamped
  series; two watchers on two folders are legitimate. So the file lives at
  <folder>/polymarket_watcher.pid (override: --pid-file), inside a data dir
  git already ignores. Semantics copied from the supervisor, not imported
  (HL_Monarch is not a package from the DEV root): dead, corrupt or live-but-
  not-a-watcher pids are swept; a live watcher wins; psutil absent -> assume
  the holder. A newcomer prints `[LOCK] already_running: watcher pid N holds
  ...` and returns 0, as directed.
- **Cleanup is best effort, the sweep is the guarantee.** atexit plus
  SIGINT/SIGTERM/SIGBREAK handlers that release and raise SystemExit(128+n)
  cover Ctrl+C and orderly stops. A closed console window or a task-kill runs
  none of them on Windows; the next watcher's stale sweep handles that.
- **The liveness probe is tested for not killing.** pid_is_alive goes through
  OpenProcess + GetExitCodeProcess on Windows (os.kill(pid, 0) would
  TerminateProcess, the trap the supervisor documented in Round 36); the test
  spawns a sleeper, probes it, and asserts it is still running.
- **The claim is an exclusive create (O_EXCL), not sweep-then-write.** Two
  watchers starting within the same second both find the predecessor's stale
  file and both sweep it; with a plain write both would run. Now exactly one
  creates the file; the loser re-reads it and refuses the live winner (or
  reports -1 while the winner's pid is not readable yet, treated as running;
  a dead pid that reappears is swept on a retry). Observed live while proving
  the lock: my restart launched the "second" watcher before the first had
  claimed, the second claimed first and the FIRST refused - the lock held, my
  script's ordering was the bug. Two restart attempts were also lost to the
  tool: a heredoc-passed kill filter matched the calling shell's own command
  line (self-kill), and escaped newlines inside heredoc strings arrived
  unescaped. Patch scripts now go through files; kill filters match argv
  structure and exclude the caller's ancestors.
- **The badge needs no new state.** _header_status composes service badge,
  watchdog badge (from _service_abandoned / _watchdog_attempts set by the
  Round 54 watchdog) and the NOVEL DEX badge; service_back already resets the
  flag, so the badge clears with the episode.
- **Live**: watcher pid 29420 started 02:07:23Z holds polymarket_watcher.pid; a second watcher exited 0 with already_running in 0.1 s; 1 watcher(s) alive after. The restart adds one extra stamped point to the macro series
  (harmless). Lead-lag stays queued until >24h of stamps: earliest honest run
  after 2026-09-06T02:00Z.

## Round 54 findings

- **Ceiling semantics**: an attempt is a relaunch issued while the service is
  dead; it counts as failed when the service is still dead at the NEXT
  cooldown. So three relaunches get their full 300 s each, and only at the
  fourth due time does the watchdog log service_abandoned (relaunches,
  dead_for_s), alert through alert_service_abandoned (cooldown key
  abandoned:COLLECTOR, so the service-down alert of the same episode cannot
  swallow it) and go quiet. service_back resets the counter; a failed spawn
  consumes an attempt; max_attempts <= 0 restores Round 53's unlimited loop.
- **The Round 53 hang explanation was wrong and is corrected here.** Under a
  non-console stdin `timeout /t 3` exits at once ("Input redirection is not
  supported"), and every launcher already had `>nul`. The real cause was
  measured: `start "" pythonw ...` hands the caller's stdout/stderr pipe to the
  detached child, so any caller that captures the launcher's output waits for
  the child's whole life (12.3 s for a 12 s sleeper; forever for a supervisor).
  PowerShell Start-Process (ShellExecute, no handle inheritance) returned in
  0.4 s. start_collector.bat now uses it. The ratified `2>&1` sweep was applied
  to 13 launchers anyway; it is cosmetic.
- **The webhook was invisible to every running process.** DISCORD_WEBHOOK_URL
  is set at USER level (121 chars) but none of supervisor 31800, collector
  10180, dashboard 48792 or its shim saw it: a process keeps the environment
  it was born with, and all four predate the variable. Whale alerts, service
  alerts and the Round 53 watchdog alerts were all silent. Fix in two layers:
  user_env() falls back to HKCU\Environment (never raises; strips), and this
  round's restart exported the value into the supervisor, collector and
  watcher. The dashboard alive now was opened at 01:36:27Z by the Round 53
  PowerShell launcher call, which had been blocked since 00:59 on the old
  supervisor's inherited pipe and resumed the instant that supervisor was
  killed - a second, independent confirmation of the inheritance cause. It
  has no variable in its environment and alerts through the fallback, which
  a fresh variable-less process proved (discord_url found). tests/conftest.py
  (new) neutralises the fallback for every test so no suite posts to Discord.
- **The watchdog's relaunch path was fired once against the live service**
  (TerminalDashboard.relaunch_service(): cmd with CREATE_NO_WINDOW -> the bat
  -> powershell Start-Process -> pythonw). The spawned supervisor logged
  `already_running` holder_pid 46740 at 01:44:34Z and exited; one supervisor
  remained. So a watchdog firing while a live lock holder exists leaves
  exactly that ERROR line in collector_service.jsonl - it is the expected
  signature, not a fault. The new supervisor also logged its keep_awake hold.
- **Only HL_Monarch reads DISCORD_WEBHOOK_URL / TELEGRAM_***: no other desk
  has a reader, so no other suite can post to Discord from a shell that has
  the user-level variable. The fallback is read at alerter construction:
  rotating the webhook needs a restart of long-lived processes.
- **Lead-lag has no data yet.** One-shot fetcher runs do not stamp (stamping
  is a --watch feature), the drop dir held only the two family files, and no
  watcher process existed, so the ">24h of stamped macro drops" clock had not
  started. The multi-tag watcher was started in its own console this round;
  stamped polymarket_macro_<stamp>Z.json copies accumulate from now
  (every 300 s when prices change). Item 3 stays queued until >24h exist.

## Round 53 findings

- **pythonw is safe for the supervisor**: sys.stdout is None there, so
  build_logger now adds its console handler only when a console exists; the
  jsonl file handler is unchanged and the child's output goes to
  collector.log regardless. The bat resolves pythonw.exe beside whatever
  `python` resolves to (the WindowsApps shim's own pythonw is a different
  interpreter) and falls back to `pythonw` on PATH.
- **The watchdog is a pure method** (`service_watchdog(alive, now, relaunch,
  alerter, log, enabled, cooldown)`) so the whole state machine is tested
  without spawning anything: dead -> log + one alert + relaunch; still dead
  inside the cooldown -> nothing; cooldown passed -> relaunch again; back ->
  log with dead_for_s; standalone dashboards never relaunch. The relaunch
  itself runs the bat with CREATE_NO_WINDOW.
- **Alerts are no-ops until a webhook is configured** (DISCORD_WEBHOOK_URL or
  the Telegram pair); the events still land in dashboard.jsonl.
- **Family split only when several tags are requested**; the single-tag
  path keeps one canonical file and unprefixed stamps, so Round 34-52
  behaviour and tests stand. Empty families write no file until they have
  had content once.
- **Live activation**: the real drop dir now carries live sports (410) and
  macro (300) questions from a one-shot run; the WATCHER itself is an
  operator-session process in start_all_ecosystem_sync.bat (Ruling 50-3).
  Drop files are not tracked (data rules), so the live fetch did not dirty git.
- **The macro block measured 3 of 3 for the first time**: Fed cut PM 93%
  (polymarket_macro.json) against longs paying +7.5% APR with OI -0.6%/24h
  -> DIVERGENT (PM yes; perps not confirming); Bitcoin $100k PM 5% ->
  DIVERGENT (PM no; perps long); flow LONGS PAYING, OI FLAT OR SHRINKING.
  `--scan --resolve` seeded 1,685 Gamma identities into the cache, yet 0
  titans match: no HyperLiquid whale wallet in the DB resolves to a Polymarket
  sharp trader. The cache file was TRACKED (a9c547d) - untracked now so the
  ignore rule applies.
- **The launcher hangs its caller**: `cmd /c start_collector.bat` from a
  non-interactive shell blocked after starting the service (the bat's
  `timeout /t 3` waits on a console that is not there). Harmless when double-
  clicked; the dashboard watchdog runs it with CREATE_NO_WINDOW and does not
  wait. Trailing `timeout` calls in launchers are worth a `>nul 2>&1` or
  removal - noted, not changed.

## Round 52 findings

- **THIRD service death, found by the research pass, not by an alert.** The
  supervisor's last coverage report is 23:44:25 UTC (uptime 4506s); the next
  three never came. At 23:52:59 a dashboard started in STANDALONE mode from the
  new root open_dashboard.bat (dashboard.jsonl: mode standalone, service_pid
  8820 read from a stale pid file) and its embedded collector carried
  ingestion for 44 minutes (newest snapshot 00:36:36 UTC, accruals 52 -> 53,
  cash +$3.51). All three deaths today (20:43, ~22:00 dashboard, 23:44-23:52)
  coincide with someone operating console windows. Restored 00:4x UTC: stale
  pid files removed, standalone dashboard killed, service + read-only
  dashboard relaunched.
- **The service collector's log lines went to DEVNULL.** run_collector_service
  spawned the child with stdout=DEVNULL, so "Basis position opened",
  "Candidate set rotated", the perpDexs warning and every refusal reason
  existed only in a console nobody keeps open. The child now writes
  data/collector.log (append across restarts, rotated once to .1 past
  COLLECTOR_LOG_MAX_BYTES = 20 MB); the supervisor logs a child_log event
  with the path. Tested end to end with a real subprocess.
- **The morning checklist changes**: `tail data/collector.log` is now step 1b.
- cross_market/titan_identities_cache.json (written by --scan) is ignored.

- **The multi-tag watcher works live** (one-shot into a temp folder, NOT the
  real drop dir): 717 questions - sports 417 (MLB 276, NFL 117, NBA 24),
  crypto 203, fed-rates 97 - and among them a real "Will Bitcoin reach
  $100,000 in September?" at 5% and a $76k-$82k daily ladder. Pointing the
  real watcher at these tags would replace the SAMPLE drop the arb note has
  shown since Round 34 with live sports questions; that is Antigravity's call.
- **Gamma `tag_slug` is real**: /events?tag_slug=crypto pages exactly like
  tag_id, and /tags/slug/crypto resolves to id 21. Round 34's "?tag=sports is
  ignored" stands - the parameter name is tag_slug, not tag.
- **The ResourceWarning was mine** (Round 51's find_market_probability opened
  a connection and raised past its close when whale_trades was absent), not
  lead_lag.load_mark_series as the handoff guessed - tracemalloc placed it.
  Now try/finally. The three cross-market modules run clean under
  -W error::ResourceWarning.
- **Non-sports questions carry sport = the tag slug upper-cased** (CRYPTO,
  FED-RATES). The arb matcher never pairs them with a sportsbook fixture; the
  cross-market exporter will LIST them as unmatched if they land in the real
  drop dir. A separate canonical file per tag family would avoid that - not
  built, asked.
- Stamped copies and the exporter: load_questions dedups by token with the
  newest FILE (mtime) winning, and a stamped copy is written right after the
  canonical one with identical content, so "latest" is unaffected.

## Round 51 findings

- **Live macro block today: 1 measured, 2 unmeasured.** HyperLiquid flow across
  BTC/ETH/SOL: longs paying, OI-weighted funding +9.7% APR, OI $5.74B, -0.1%
  over 24h -> "LONGS PAYING, OI FLAT OR SHRINKING". Fed-cut and BTC-$100k
  markets: NO LIVE MARKET FOUND - polymarket_whales.db has no market table
  (whale_trades is empty; the other tables are wallets) and the only local drop
  is the sports sample. The tags are the truth; the old 88% / 64% were not.
- **Item 18 cannot measure anything on today's data**: 7 markets, 0 shifts.
  The Polymarket fetcher overwrites ONE drop file in place, so no probability
  time series exists on disk. The correlator is verified on planted lags
  (+10 and -15 minutes found exactly; noise -> "no measurable lead-lag"; two
  events -> refused). To measure for real, the fetcher must keep timestamped
  drops (polymarket_<stamp>.json, like the odds fetcher) - the exporter already
  dedups by token across files, so that is a fetcher-only change. Ruling asked.
- Co-positioning is now RULES, not narrative: CONVERGENT / DIVERGENT / NEUTRAL /
  UNMEASURED from (PM probability, weighted funding sign, OI change sign);
  strength from probability distance and OI change magnitude. All pinned.
- Safety: both tools read drops and a read-only sqlite URI; neither opens a
  socket or touches the harvester. The bankroll gate and quarantine sets are
  untouched.

## Round 50 closeout (session end, 2026-09-04 ~23:05 UTC)

Antigravity's independent audit, re-derived from basis_paper_state.json and
live spot contexts, not from Claude's summaries:
- Invariant: equity $100,310.41 - starting $100,000.00 - realised $310.41 =
  $0.000000. PASS.
- Every open hedge liquid at the $100k floor: UANSEM $898,154/day (8.98x),
  UXPL $1,291,837/day (12.92x). PASS.

Settled at closeout (no longer carrying):
- R44-Q2 polling mkts/io: NO - ~150 weight/min per dex against the 1,200
  ceiling, and their perps cannot be basis legs.
- R49-Q1 dashboard stop signal: KeyboardInterrupt vs unhandled exception in
  dashboard.jsonl is sufficient on Windows.
- R49-Q2 dual-mode status write: only the collector that OWNS maintenance
  writes collector_status.json (implemented at closeout: `_check_perp_dexs`
  checks `_owns_maintenance()`; an embedded collector a service has joined
  still warns, but leaves the file). Code on disk is newer than the running
  processes; the changed path is not exercised by a service collector or a
  read-only dashboard, so no restart was taken. The next restart picks it up.
- R48(b) sampler 6h refresh: kept as the cold-start fallback (0 weight warm).
- Macro placeholder labelling: RATIFIED.

Queued for Round 51 / next session:
- Measure the Titan note's macro block from real sources: Fed-cut and BTC
  milestone probabilities from Polymarket markets in polymarket_whales.db;
  equity/crypto bias from latest_snapshots funding and OI momentum.
- Item 18, lead-lag event correlator (offline research): event drops from
  Sports_Desk/data/polymarket_drops/ and cross_market/data/ against historical
  asset_snapshots. The titan-resolution module stays the production component.

Overnight policy: HL_Monarch collector + supervisor run 24/7 (keep-awake held);
Sports and Cross-Market desks stay static (their watchers are an operator
session workflow, start_all_ecosystem_sync.bat). Morning checklist: the
Round 50 handoff, section 5.

## Round 50 milestone log

THREE NUMBERING SERIES MEET HERE, and the log says which is which:
- HL_Monarch rounds 1-25 (to 2026-09-02) predate version control - the repo was
  initialised at "Round 26L" (743496b, 526 files, 2026-09-03). Their record is
  `HyperLiquid/HL_Monarch/AGENTS.md` and COMMANDS.txt, not git.
- The Tax Reserve Agent kept its own series (COMMANDS.txt "ROUND 15..36",
  2026-09-01..03: tax gate, HIFO, receipts, fee model validated on chain).
- The DEV series below is the one Antigravity and Claude Code have run since
  the penta-desk vault (Round 33). Rounds 34-50 were all on 2026-09-04.

| DEV round | commit | what it settled |
|---|---|---|
| 26L-31 | 743496b..027a3e1 | quad-desk baseline, sports desk, cross-market arb under asymmetric tax, harvester gated on the basis bucket |
| 33 | 5dbc12b | data grounding: 192h retention, fail-closed bankroll, real sports DB, penta-desk vault |
| 34 | 33111d7 | incremental measurement persistence (measure before prune), Polymarket ingestion, odds poller, cockpit canvas |
| 35 | 18b4989 | signed spread lines, L2 spread sampler, keep-awake, PID-reuse guard |
| 36 | a4b6c51 | read-only dashboard under a live service (one ingester), held positions sampled first |
| 37 | d80c937 | STALLED badge, candidate-first sampling, runtime files untracked |
| 38 | acff08d | spread ceiling on every costed row, one position per spot symbol, stall threshold from poll interval |
| 39 | a4f43b4 | spot universe = liquid pairs (spotMetaAndAssetCtxs), net-APR candidate ranking |
| 40 | 287b603 | alias table, most-liquid hedge, spot decimals fix, floor $50k, para:ANSEM -> UANSEM |
| 41 | 35b98ea | equity quarantine, floor scales with notional, [ILLIQUID SPOT] tags, --unmapped-spot |
| 42 | cfd137b | quarantine on the PERP, illiquid-leg sweep (3 dead legs closed, $60k freed), 10x ADV floor |
| 43 | 7068e40 | dex-level quarantine, canonical duplicate guard, one volume map per cycle, vault closed-trades fix |
| 44 | e7b2e54 | TRADFI_DEXES + mkts/io, config clamp floor, malformed-field fallback |
| 45 | 06c12d9 | per-field config fallback for every field (safety flags fail armed), unclassified dexes fail closed |
| 46 | 9e91818 | vntl TradFi, hyna mixed, abcd unclassified, preset-aware fallback |
| 47 | c84c150 | structural dex fail-closed, hourly drift detector, one candidate slot per underlying |
| 48 | 914c852 | mixed-dex crypto allow-list (para), NOVEL DEX dashboard badge, candidate rotation log |
| 49 | 2146012 | dashboard lifecycle log, 2h status window, perpDexs check at start-up |
| 50 | (this) | Titan CLI, five-desk vault regeneration, milestone log, command index |

THE DAY IN NUMBERS (2026-09-04): 17 rounds (34-50), 19 commits, 15 service
restarts, 2 unexplained dashboard deaths (now logged) and 1 unexplained
collector death (20:43, ~7.5 min lost). Tests 2,3xx -> 2,427. Paper book:
5 positions -> 2 after the sweep; cash $324 -> $60,310; every position's hedge
now verified liquid; invariant equity - starting == realised exact throughout.
UNCHANGED ALL DAY: FADE_STRATEGY_ENABLED False, WHALE_SWEEP_EXECUTION_ENABLED
False, the pre-registration bar, the live tax ledger at $0.00.

## Round 50 findings

- **`detect_macro_signals()` returns fixed narratives.** The Titan note's
  "Macro Co-Positioning" block (Fed cut 88%, BTC $100k 64%, /NQ divergence)
  is hard-coded, not measured. The new CLI report labels it STATIC
  PLACEHOLDERS; the vault note still renders it as before. Ruling asked.
- **The ruling described a different module** (lead-lag over event drops).
  What exists correlates HyperLiquid whale wallets with Polymarket sharp
  traders (EOA -> proxy, conviction score). The CLI was built for the module
  that exists; the lead-lag idea is recorded as an open item.
- Vault regeneration: HL `obsidian --once` rewrites HyperLiquid_Monarch.md,
  Trading_Terminal.md, the hub and the canvas; Sports_Desk.md and
  Cross_Market_Arb.md reported "unchanged" (no new drops since their last
  sync); Quant_Trading_Lab.md and Polymarket_Monarch.md (+41 trader notes)
  rewritten; today's Tax_Reserve note written by `Tax_Reserve_Agent.main
  export` (read-only: it computes the summary and writes the note).

## Round 49 findings

- **The dashboard's render loop swallowed every exception silently** - one
  bad frame slept a second and retried, forever, with nothing written. Now
  the first three frame errors are logged with tracebacks and counted; an
  exception that escapes the loop (Live itself failing) is logged as a crash
  and RE-RAISED, so the process still exits and main.py prints it; a clean
  exit logs stop with the frame-error count. The supervisor still does not
  manage the dashboard (Ruling 49-1: it is an optional viewer).
- **The 2h window is a default, not a hard rule**: read_collector_status(path,
  max_age_s=None) reads regardless of age; the dashboard uses the default.
- **Start-up check runs on the hl-l2 executor** after universe metadata sync
  and before the loops, so the first status file is written ~2s after start.
  If perpDexs fails at start, the hourly cycle retries; the previous file
  (if any) stands until then - and the 2h window expires it if the collector
  never comes back.
- Windows note: the collector's console cannot print the ⚠ glyph (cp1252);
  the dashboard reconfigures stdout to UTF-8 and Rich renders it. The
  rotation and drift log lines are ASCII on purpose.

## Round 48 findings

- **para verified live before inverting the rule**: 33 perps, four crypto
  (TOTAL2, OTHERS, BTCD, ANSEM), the rest equities (SMCI, RDDT, CRWD, MELI,
  SOFI, TTWO...), rates (2Y/10Y/30Y) and pre-IPO (ANTH). The allow-list of four
  is exactly the crypto set. is_mixed_dex_tradfi() is the new test, joined
  into is_synthetic_tradfi; the TradFi switch still opens it like the others.
- **The "dashboard status JSON payload" in the ruling did not exist** - the
  dashboard is a Rich terminal in its own read-only process. Built the channel:
  MarketCollector.write_collector_status(COLLECTOR_STATUS_PATH, {...}) from the
  hourly cycle (unclassified_dexs, dexes_listed, checked_at, pid), and
  ui.components.read_collector_status / novel_dex_badge on the dashboard side,
  composed into the header by TerminalDashboard._header_status. First write is
  one hour after a collector start; the file persists across restarts.
- **Rotation log lives in the collector's _sample_pass** (the sampler's
  function is pure); candidate_rotation_message() is the pure helper. The first
  pass after a start logs "[-] -> [...]" on purpose.
- The Round 47 dedup test needed para:BTC admitted; it now monkeypatches the
  allow-list for the fixture rather than weakening the rule.

## Round 47 findings

- **Fail-closed is now structural, not a list.** `is_unclassified_dex` is
  "dex not in CRYPTO_DEXES and not in TRADFI_DEXES". UNCLASSIFIED_DEXES no
  longer gates anything; it is the "known and deliberately refused" list the
  drift detector consults so abcd and hyna do not warn every hour. hyna was
  added to it for that reason (behaviour unchanged: refused either way).
- **hyna:HYPE no longer resolves** (Round 46 pinned it resolving). Under the
  structural rule a mixed dex that is not in CRYPTO_DEXES is refused whole;
  admitting hyna is a one-line settings edit once someone wants it polled.
- **Candidate dedup counts underlyings, not listings**: n=5 means five
  distinct bases. A held position's base is excluded from candidates outright
  (`exclude=held`) - it already has its spread series and a second listing
  could never be opened. A measured spread can flip which listing wins.
- Drift detector: `unclassified_dex_names(perpDexs names)`; the payload's
  first entry is null (the main dex) and is ignored. Live today: [] (all ten
  dexes are in some set).

## Round 46 findings

- **abcd is not an empty shell.** The ruling called it dormant with an empty
  asset list; the live meta for dex=abcd lists one perp, abcd:USA500. It stays
  in UNCLASSIFIED_DEXES as ruled (refused), and USA500 is in the symbol set, so
  it would be refused twice over if ever polled. Settings comment corrected.
- **Live universes verified before classifying**: vntl 15 perps, all pre-IPO
  equities, sector baskets or commodities; hyna 25 perps, crypto majors and
  memes plus GOLD and SILVER (mixed, exactly para's shape); neither is polled.
- **Preset-aware fallback reads active_preset FIRST**, then resolves each
  field's default from PRESETS[preset] when present, else the dataclass. A
  well-formed line under any preset is honoured as written - the preset only
  supplies fallbacks. Safety flags: malformed -> armed, absent -> the preset's
  False. Spot fields have no preset entry and keep the settings defaults.

## Round 45 findings

- **Safety flags fail armed, not off** (deviation from "fall back to the
  field's default"). `emergency_killswitch: maybe` or `pause_new_entries: 7`
  now reads as True with a warning; an ABSENT flag is still False, because
  absence is not corruption. A malformed safety value must stop trading, never
  enable it. The spot policy flag falls back to its default (False) as ruled.
- **Integers read through float**: `max_concurrent_positions: 3.0` is 3; "2.5"
  would be 2. Clamping is unchanged - `validate_and_clamp` still runs on the
  assembled config against BOUNDS, so per-field parsing and clamping are two
  passes, not one.
- **Unclassified dexes are refused with no switch**: `is_unclassified_dex`
  gates `spot_symbol_candidates` before the TradFi test, so the scan, the
  sampler and the resolver all see [] regardless of `allow_synthetic_tradfi`.
  Admission is a settings edit after a human looks at the dex.
- Ruling 45-3 named `sample_orderbooks()` / `_spot_universe_cache`; the real
  names are `_sample_pass` / `_spot_universe_cached`, and the cold-start path
  is already pinned by `test_the_spot_universe_is_cached_refreshed_and_never_
  guessed` (failed lookup -> zero candidates, retry, stale copy survives).

## Round 44 findings

- **Service found dead at 20:50 UTC.** Last DB write 20:43:49 (8 min after the
  Round 44 restart); supervisor log ends at its 20:35:18 coverage report with
  no shutdown or child-exit event; the dashboard died at the same moment; BOTH
  pid files still held the dead PIDs (so stop_collector.bat was not used - it
  deletes them). Signature of the console windows being closed or an external
  kill. Relaunched 20:51:21 (supervisor 10428, collector 51188). ~7.5 min lost.
  If the windows were closed deliberately, use stop_collector.bat instead; the
  supervisor cannot log or recover from a kill of itself.

- **perpDexs lists ten dexes**: xyz, flx, vntl (Ventuals), hyna (HyENA), km,
  abcd (ABCDEx), cash, para, mkts, io. Six are quarantined by name; para is
  mixed (symbol set); vntl, hyna and abcd are UNCLASSIFIED. None of mkts, io,
  vntl, hyna or abcd is in ACTIVE_DEXES, so nothing from them reaches the
  scan today - the dex quarantine on mkts/io is pre-emptive, and a future
  widening of ACTIVE_DEXES must classify the other three first.
- **Per-field fallback vs whole-reload failure.** Before this round a single
  unparseable number anywhere in Bot_Config raised inside reload(); get_config
  caught it and kept the last cached config silently. The three spot fields
  now fall back individually with a warning; the older fields still take the
  whole-reload path. Worth unifying - ruling asked.

## Round 43 findings

- **The vault had been wrong for every closed trade.** `generate_trading_
  terminal_note` read `realized_pnl` and `hold_duration_hours`; the harvester
  writes `net_pnl` and `hours_held`. No test covered the table. Now one does,
  and the three swept trades render +$4.09 / +$0.15 / -$7.28 with their hours
  and `ILLIQUID_SPOT_LEG` reasons.
- **canonical_spot_base is string logic with known edges.** Aliases map via the
  tables; a "U" prefix is stripped only when 3+ characters remain (UNI, UMA, UP
  stay themselves); USDC canonicalises to SDC, harmless for a quote asset. The
  harvester ALSO compares perp bases (`holds_spot(spot, coin=)`), which needs
  no table: para:AVGO and xyz:AVGO collide on AVGO whatever spot name resolved.
- **One engine per hourly cycle** (`FundingArbitrageEngine(client=rest_client)`)
  now serves the illiquid sweep, the scan (`scanner=`) and refreshes the
  sampler's universe + volume cache, so the 6h/1h divergence is gone and a pair
  that dies is swept within the hour.
- **Hot-reload boundary:** the three new Bot_Config fields take effect live
  through `_dynamic_value()` (a getattr on the cached config; the file is
  stat-ed per call). CODE changes still need a restart - this round restarted
  for the dex quarantine, the canonical guard and the unified volume map.
- Ruling 43-5 recorded in the harvester docstring: returns are right-tail
  heavy (one of five positions paid $322 of $350); report median and top share,
  hold the 25%/20% bar - baseline large-cap funding nets negative after drag.

## Round 42 findings

- **The TradFi perp list is much longer than the ruled set.** Live dexes carry
  cash:AMZN/INTC/KWEB/USA500/WTI, flx:COPPER/PALLADIUM/USA100, km:JPN225/
  USBOND/EUR/TENCENT, para:2Y/10Y/30Y and more. The ruled 21 symbols were kept
  as issued and extended with every TradFi base observed on 2026-09-04 (34
  more), labelled separately in settings. A hand-kept symbol set will drift as
  dexes list; a structural rule (dex metadata or an asset-class field) is the
  next question.
- **Sweep accounting, live:** capital returned $59,990.67 (HOOD $20,000.00,
  para:AVGO $19,995.58, xyz:AVGO $19,995.10), maker exit fees $6.00 (0.01% x
  notional x 2 legs x 3), cash $324.30 -> ~$60,309, realised $314.92 ->
  ~$308.92, invariant equity - starting == realised exact. Antigravity's
  estimate ($9.00 fees, $60,305.98) used a different fee assumption.
- **The sweep is a different KIND of exit.** Ruling 39-1 (spread is a cost, not
  a reason to leave) stands; a dead spot leg means the position was never
  delta-neutral. Fails closed on a missing/empty volume map.
- **Operational trap avoided:** the CLI sweep refuses while `collector.pid`
  names a live collector - the running harvester would overwrite the file on
  its next hourly save. The hourly cycle runs the same sweep from the sampler's
  cached volume map, so a future dead leg closes within the hour.

## Round 41 findings

- **Wrapper-first precedence applies everywhere, not only on volume ties**
  (deviation from the ruling's wording). A call without volumes is an all-ties
  call; two different orders would make the answer depend on whether volumes
  were supplied. para:ANSEM -> UANSEM even before volumes are known.
- **Live `--unmapped-spot` (floor $50k):** KNTQ $1.77M, XAUT0 $1.74M, FLOCK,
  DRV, SEDA, SPCXD, MUX, HSEI, HPL, UUUSPX, HFUN, KHYPE, LIQD. Most are assets
  with no perp. XAUT0 (gold) and UUUSPX (S&P) are commodity/index wrappers the
  xyz:GOLD / index perps could hedge with - the same 5-day-market question as
  the equity quarantine. Ruling asked; nothing added.
- **The quarantine covers aliases only.** A bare-named liquid equity token
  (none exists today: NVDA/TSLA bare tokens are dead Wagyu.xyz shells) would
  still resolve through the bare-name path. Noted, not built.
- `python main.py basis --harvest` now makes ONE spot-context request so dead
  legs are tagged; a failed lookup prints the book untagged. Live: xyz:HOOD
  ($402/day), para:AVGO and xyz:AVGO ($0/day) tagged; UANSEM and UXPL clean.
- Stablecoins (SPOT_NON_BASIS_TOKENS) are excluded from the telemetry so it
  reports missing aliases, not quote assets.

## Round 40 findings

- **Aliases verified before adoption** (live token list, 2026-09-04): UFART
  "Unit Fartcoin" $570k/day, HPENGU "Pudgy Penguins" $180k, XMR1 "XMR -
  Wagyu.xyz" $16M, FXMR "Freedom XMR" $10.7k, NVDAX "Wrapped NVIDIA xStock"
  $131k, TSLAX $0, FXRP $12k; EQNVDA/EQTSLA/IXRP/WXRP exist with no pair. The
  bare NVDA/TSLA tokens are "Wagyu.xyz" shells with no or dead pairs. Fuzzy
  fullName matching was ruled out: a wrong alias hedges one asset with another.
- **Decimals bug (Ruling 40-4).** `spot_sz_decimals` looked up the PERP base
  name in the spot table, so UBTC/UFART/UANSEM hedges all reported None and
  `matched_leg_size` sized off the perp leg alone. Fixed spot-first with an
  `is None` test - the suggested `or` would have treated 0 decimals (whole
  units) as missing.
- **`spot_volumes` in the sampler changes nothing about ranking** - it only
  decides which spot name would hedge; passed through for parity with the scan.
- Paper state: para:ANSEM `spot_symbol` ANSEM -> UANSEM, edited on disk between
  stop and start (the running harvester would have overwritten a live edit on
  its next hourly save). Sizing/decimals of the open position untouched.

## Round 39 findings

- **Four of the five paper positions are hedged on dead spot legs.** Live
  24h spot pair volume: ANSEM $1.5k, HOOD $402, AVGO $0 (both AVGO perps),
  UXPL $1.36M. Under the new rule xyz:HOOD, para:AVGO and xyz:AVGO resolve to
  no spot leg; para:ANSEM resolves to UANSEM (liquid) rather than the bare
  ANSEM it was booked against. Positions untouched per Ruling 39-1 (yield-only
  exits); no new entry can be classed spot-backed on those legs.
- **Two payload traps.** `universe[i].tokens` are token INDEX fields, not list
  positions (a positional parse raises IndexError); asset contexts are NOT
  aligned with the pair list (718 contexts for 326 pairs) and match by `coin`
  name. Both are pinned in tests. A failed lookup returns an empty universe
  and is not cached.
- **Alias gap in `spot_symbol_for` (open).** The U-prefix rule misses
  abbreviated wrappers: FARTCOIN's liquid spot is UFART ($570k/day), XMR's is
  XMR1/FXMR, NVDA has NVDAX. FARTCOIN is therefore spot-backed in fact and
  unmatched in code. Needs an alias table or a fullName match - ruling asked.
- **Net-APR ranking mixes measured and unmeasured on one scale** (deviation
  from the directive's "unmeasured behind measured"): an unmeasured coin ranks
  on gross, an upper bound that buys it one sample; ranking it behind five
  measured positives would never sample a new hot market before entry.
- Threshold note: a $10k leg into a $10k/day pair is the day's whole turnover;
  25 tokens survive at $100k. Ruling asked.

## Round 38 findings

- **The prefix rule was wrong both ways.** Live spot lookup: CHIP, PONS, XMR,
  FARTCOIN (four of Round 37's five candidates) have NO spot token; para:ANSEM
  (held against spot ANSEM) and xyz:TSLA (spot TSLA) were excluded. Candidates
  now go through `spot_symbol_for(coin, spot_universe)`, the same function the
  harvester's scan uses. The collector caches the universe (6h refresh); a
  FAILED lookup yields zero candidates, never the prefix guess; a stale copy
  outlives a failed refresh.
- **Two paper positions showed two missing gates.** `scan_basis_opportunities`
  costed rows on demand below the scanner's 8-row spread probe and judged them
  on the net bar alone: 77.9% gross at 35.05 bps amortised over 7 days still
  nets 41%, so para:AVGO entered against a 25 bps ceiling. The ceiling is now
  enforced on every costed row (reason `spread X.Xbps > Y.Ybps max`) and again
  in `BasisHarvester.open_position` - the last gate before capital moves must
  not rely on the caller. `can_open(spot_symbol=)` refuses a spot token already
  hedging an open position (para:AVGO + xyz:AVGO = $40k on AVGO). Refusals now
  carry a reason (`harvester.last_refusal`) and the accrual loop logs it.
- **The two existing over-ceiling / duplicate positions were NOT closed.** The
  guard is on entry; the paper book still holds them and the exits stay
  yield-driven (Ruling 34-B style: a gate change is not a reversal).
- **Stall threshold**: `STALLED_AFTER_SECONDS = max(45, (REST_POLL_INTERVAL + 2) x 4)`
  lives in settings (45s at the 8s poll; 88s at 20s); `ui/components` re-exports.
- Bot_Config.md: `active_preset: "custom"`, `max_concurrent_positions: 5` kept;
  the harvester report shows the cap in force ("Open n/5"), not the code's 2.

## Round 37 findings

- **Stalled is an ALIVE-service state.** The process probe cannot see a hung
  child or a dead socket; the newest row in latest_snapshots can. Built AFTER
  the snapshot fetch in the render path (the Round 36 order had the badge
  first), cached probe every 5s, badge rebuilt every frame. Stalled outranks
  the dual warning; a dead service is orphaned/standalone regardless of age.
- **Candidates before entries.** `top_funding_candidates` ranks POSITIVE
  funding on main-dex perps only - a HIP-3 perp has no spot leg to hedge, so
  its funding is not a candidate for the spot-backed harvester however high it
  prints. Ties break on the name. `_sample_pass` runs on the hl-l2 thread:
  latest_snapshots -> `_sample_coins` -> `sample_orderbooks`.
- **The ledger backup that was tracked held demo data** (8 option transactions
  from 2026-01-05, opt_buy_BTC-90K-CALL). Untracked and ignored; history keeps
  a demo file, not a real position. No rewrite needed.
- **A latent flake, found by the suite.** `write_drop`'s default filename had
  one-second resolution; two drops within a second overwrote each other. It
  surfaced as 1 file where a test expected 2. Microseconds now.
- Antigravity's own query: 13.2M rows, 82.2h span, 98.33% 60-minute continuity
  with one poller (Round 34 measured 78% with two).

## Round 36 findings

- **One ingester, measured.** With the dashboard's embedded collector polling
  beside the service, BTC had 119 snapshot rows per 10 minutes (two 8s pollers
  would give 150; the shortfall was throttling). Read-only dashboard beside the
  service: 59 rows per 10 minutes, the single-collector rate (8s sleep plus ~2s of request time gives ~60). The second
  900 weight/min is gone.
- **The header tells the truth in four states.** read_only (service alive),
  standalone (none at start), orphaned (started read-only, service since died:
  RED, "tables are going stale"), dual (started standalone, service since
  appeared: restart the dashboard). Re-checked every 5s from a file read and a
  process probe; nothing is spawned mid-run.
- **Sampling priority is positions > rotated > core**, via
  `MarketCollector._sample_coins`; the harvester is created lazily by the
  accrual loop, so a collector that has not accrued yet samples rotated/core.
- **Runtime files untracked.** `*.pid` and `*.jsonl` ignored; the three files the
  Round 26 baseline tracked are `git rm --cached`. `git status` is quiet apart
  from the vault notes the sync rewrites and the paper-state JSON.

## Round 35 findings

- **Ruling 5.B, as built.** `MarketQuote.line` is the selection's own handicap;
  the watcher keys a market by `market_line_key` = the UNSIGNED number, so both
  legs still devig together; `record_fair_value_measurement(lines=...)` stores
  one signed line per leg. A home-keyed file (Round 33's -3.5 / -3.5) still
  groups into one market but stores -3.5 on both legs, so it can never hedge a
  spread - the convention is "as the feed states each leg". RESULTS FILES MUST
  FOLLOW IT: `settle_placed_bets` joins on the `line` string, so a Ravens result
  is `+3.5`, not `-3.5`.
- **7 of 7 matched** on the real `sports_market.db` after re-dropping the sample:
  the Eagles -6.5 question hedges against Pinnacle Cowboys +6.5 at 1.909, book
  arb -2.33%, worst branch -8.78%. 0 clear the hurdle, as before.
- **The REST budget decides the sampler, not the wish list.** Context polling
  costs 6 dexes x 20 weight every 8s = 900 of the 960 weight/min the limiter
  allows. Sampling 24 coins every 120s costs 24/min. It runs ONLY in the
  collector that owns maintenance; the sampled spread is the PERP leg's and
  stands in for both legs of the drag formula.
- **The dashboard still ingests.** Its embedded collector yields maintenance and
  sampling now, but it still polls contexts and writes snapshots alongside the
  service: 727 snapshot rows per coin per hour where one collector at 8s would
  write ~450, and a second 900 weight/min against the same IP. That duplication
  is the most likely cause of the 429s behind the continuity gaps. Decision
  needed: the dashboard should read the database and not run a collector while
  the service is alive.
- **Keep-awake holds the IDLE timer only.** ES_CONTINUOUS|ES_SYSTEM_REQUIRED is
  set by the supervisor and released on exit; a user-chosen Sleep, a lid close,
  or a critical-battery shutdown still sleeps the host. `--allow-sleep` opts out.
- **Polymarket outcome 1 is priced off the mirrored bid** when that is worse than
  the posted price (1 - bestBid_0); basis recorded as `mirrored_bid`. Totals and
  spread outcomes are never rewritten as fixture questions.

## Round 34 findings

- **The Round 33 retention fix was not in effect on the machine.** Settings are
  read at import; the collector had been launched 2026-09-03 14:45, nine hours
  before `SNAPSHOT_RETENTION_HOURS` was edited, and the oldest snapshot was
  exactly 72.0h old 15 hours later. Its supervisor (`run_collector_service.py`)
  had died, leaving a bare child with **78% hour-continuity** over the retained
  window (12 of the last 24 hours had no rows for ANY coin). Restarted under the
  supervisor 2026-09-04 04:45 UTC, and again 05:20 UTC after the collector patch
  below. Ruling C's ~2026-09-08 for 168h of raw rows still holds; the first
  PERSISTED 168h windows (entry must carry a quote, window must complete) land
  ~2026-09-11, and Ruling D's 720h no earlier than ~2026-10-04.
- **A SECOND pruner: the dashboard.** `main.py dashboard` embeds a full
  `MarketCollector`, maintenance loop included. The dashboard launched 2026-09-03
  14:46 kept 72h in memory and pruned every five minutes AFTER the service was
  restarted with 192h - caught because rows older than 72.5h stayed at zero and
  the boundary moved at 05:02:34 UTC, a time no service pass could produce.
  The embedded collector now skips maintenance whenever `data/collector.pid`
  names a live process (`service_collector_alive`); the dashboard was restarted.
  Restart BOTH after any settings change.
- **What the persisted tables say after the first backfill** (6,670 windows,
  11,941 events + matched controls, 418s): entry-conditioned 24h, quote >= 20%:
  n=358 on 103 coins, median realised 25.7% vs 6.8% unconditional, **+18.9pp,
  coin-bootstrap P(median >= 20%) = 0.897**; >= 25%: +22.3pp, P 0.972; >= 40%:
  +28.6pp, P 1.000 - the Round 32 result reproduced from the summary tables.
  Cascade excursions, trade_sweep, 7,694 events on 31 coins: MFE/MAE 0.49 (5m)
  to 0.83 (60m) against a persisted control of ~1.05, cluster P(>= 1) 0.000-0.032
  - the fade retirement on 15x the sample. Regimes seen: VOL_MID|FUND_FLAT 18h,
  UNKNOWN 15h (BTC reference gaps); 168h hold: 0 windows until ~2026-09-11.
- **The machine sleeps, and the service does not survive it.** Windows entered
  sleep 2026-09-04 02:19 local (06:19 UTC) and resumed 11:12 local; on resume
  neither the supervisor nor its collector child existed, and the old dashboard
  was gone too (its 72h pruning stopped with it - oldest row is now 81h). The
  launcher was re-run 15:22 UTC and the dashboard restarted behind it so the
  service owns maintenance. A nightly nine-hour sleep caps continuity near 60%
  and puts an UNKNOWN regime across every gap; Ruling D's 720h cannot be met on
  a machine that sleeps. Decide: disable sleep for this box, or host the
  collector elsewhere.
- **The collector's one `hl-db` thread ran the snapshot poller, the buffer
  flusher AND maintenance.** A two-minute measurement pass queued behind it
  would have created the gaps the measurements are made from. Maintenance now
  has its own `hl-maint` thread; the per-pass budget is one grid instant per
  hold (~2 min across 440 coins for the 7-day scan, 0.25s per coin measured).
- **Fail closed on the measured tables.** If the persistence pass raises,
  `asset_snapshots` and `liquidation_events` are NOT pruned that cycle; the
  others prune as before. Tested by monkeypatching the pass to raise.
- **"No quote, no entry."** The first rule wrote 1,760 seven-day windows whose
  entry instant predated any row for the coin - entries nobody could have made.
  Deleted; a window is now recorded only if a funding quote was in force at the
  entry instant (one indexed lookup, asked first). Thin windows AFTER a real
  entry still record with a NULL rate, never a number.
- **`orderbook_snapshots` is empty and nothing writes it.** `net_apr_after_fees`
  is therefore NULL on every persisted window (`fee_basis = 'unmeasured'`); no
  default spread is substituted. The cost model that decides the 7-day hold has
  no measured spread anywhere in the repo.
- **Antigravity's Gamma URL does not filter.** `?tag=sports` returned a crypto IPO
  event and French politics; `tag_id=1` (the "Sports" tag per `/tags/slug/sports`)
  does. Fixture markets are team-vs-team, not yes/no, and are rewritten into two
  derived questions carrying `derived_from`. `takerBaseFee` has no documented
  unit and is NOT inferred into `fee_rate`.
- **Spread pairs never match, by convention conflict.** `odds_watcher` keys both
  spread legs under the home handicap (Round 33 fix); `matcher.hedge_leg_for`
  looks for the MIRRORED line on the opponent. The sample carries one spread
  question so the gap is visible: 7 questions loaded, 6 pairs matched. Needs a
  ruling on which convention wins before spreads can be hedged.
- A static odds source cannot fabricate line history: `--watch` fingerprints
  PRICES (not timestamps) and skips an unchanged poll. Brier scoring is fed by
  settled results (`results_watcher`), not by quotes - the poller does not
  touch it.
- The supervisor sends the collector's stdout to DEVNULL, so its maintenance
  log lines are invisible. `python main.py persist --status` and
  `measurement_watermarks.updated_at` are the evidence that passes run.

## Round 33 findings

- **Three of Antigravity's Round 33 rulings needed correction before building on
  them, all verified**: (1) Ruling B's cost-drag figures (3.13% / 21.90%) used
  `legs=1` for a two-leg spot-backed trade; correct values are **6.26% / 43.80%**
  - the conclusion (keep 7-day hold) is *strengthened*. (2) Ruling A's "unblocks
  7-day windows TODAY" is wrong: raising retention does not recreate pruned
  rows; snapshots spanned 69.1h, so a full 168h window first exists **~4.1 days
  after the change**. (3) Ruling D (720h across >=2 regimes) **cannot be met under
  Ruling A alone** - 192h retention can never hold 720h; incremental measurement
  persistence (option b) is required by D, not optional.
- **Target 2 path names were wrong** (`monarch_bankroll.py` does not exist; the
  hook is `interfaces/monarch_hook.py`). No `DEPOSIT` type existed in the ledger;
  one now does (`asset_class="cash"`, opens no lot, never summed into gains).
- **Precedence for liquid cash**: override (`--cash` / `--paper-bankroll`) >
  deposits (measured) > declared-in-config > **none = $0.00**. `config.yaml` now
  ships `default_cash_balance_usdc: null`. One HL test relied on the old
  placeholder and now declares its balance explicitly.
- **The odds watcher's own guard caught a defect in my sample**: I keyed the two
  spread legs under different lines (-3.5/+3.5), making two one-leg markets it
  correctly refused. Both legs now share one line key; 6/6 markets price.
- **`.gitignore` data rules were root-anchored** - `data/odds_drops/` never
  matched `Sports_Desk/data/odds_drops/`, and the first real drop showed up as
  untracked. All data rules now use `**/` prefixes; verified with `check-ignore`.
- The Sports exporter had a tz-aware `now` vs naive `placed_at` bug that silently
  disabled the >3-day un-exported warning; caught by the test that asked for the
  warning by name.

## Round 31 findings

- **Item 14 is the retired liquidation fade.** Same signal (liquidation
  clusters), same thesis (wick rebound), same mechanism (pre-positioned limits).
  It was measured and killed in Round 16: **MFE/MAE 0.513 vs a random-entry
  control of 1.092**, n=466, t=-10.52, MAE > MFE in 72.7% of events, 0/20,000
  bootstrap resamples non-negative. Below the control means *worse than random*.
  `config/settings.py` records: "no filter or geometry fixes a sign error" and
  "do not re-enable without a new pre-registered excursion result".
- **Forced liquidations are momentum drivers, not mean-reverting wicks.** The
  spec's "tight post-fill trailing stops" is the worst possible configuration
  against that - it converts adverse excursion from paper into realised loss,
  and is exactly what rounds 9-15 kept retrying.
- **A live pre-registration already exists**: `data/experiments/
  passive_fade_rebenchmark.meta.json`, status PASSIVE, reopening bar
  `P(ratio >= 1.25) > 0.90` under a **cluster** bootstrap, >=500 events, >=20
  coins, top coin <=20%. Building Item 14 as specified would have violated the
  project's own protocol.
- **The retirement is weaker than the headline**, and the registration says so:
  0.513 was substantially a two-microcap artifact (83% of events, HHI 0.360);
  broad-market effect was 0.849. Only the 30m horizon clears p<0.05. So: probably
  no edge, *not proven* across the broad market, under active re-measurement.
- **What I built instead**: `strategies/whale_sweeper.py` with cluster geometry,
  zone maths, the `hl_whale_sweep` bucket, and `EvidenceGate` holding execution
  shut until the pre-registered bar clears. Two independent locks; both must
  open. The path is wired and tested, not stubbed.

## Round 29 findings

- **Item 8 was ~90% already built.** `execution/basis_harvester.py` (delta-neutral,
  accrues at the CURRENT rate not the entry quote), `analytics/funding_arbitrage.py`
  (scan + spread amortisation), `BASIS_MIN_NET_APR = 20.0` already the *net* bar,
  and `hl_basis_harvest` already the bucket name in `risk_manager.py`.
- **The real gap: the harvester never asked the bankroll.** It imported
  `STRATEGY_BASIS_HARVEST` only to tag receipts and gated on its own paper cash;
  `market_collector.py` opened positions with no bucket check at all. Same defect
  as Monarch_Shark running 1.7x over its sports bucket. Now wired, and the live
  call site goes through it.
- **The quoted APR is double the return on capital.** Every APR in the system is
  per-*leg*; `capital_required()` is `notional x 2`. A position reporting 56%
  realised earns 28% on money committed. A gate asking for one leg's notional
  would authorise half what the position spends.
- **The honest restatement**: 20% quoted -> 10% on capital -> 6.8% after tax ->
  vs 3.7% for a T-bill after ITS tax (state-exempt, 31 USC 3124(a)). A three-point
  edge, not fifteen.
- The gate **fails closed**: an unreadable ledger rejects rather than waving
  through, and logs loudly so "gated off" is never mistaken for "no opportunities".

## Round 27 findings

- **Both deltas in the Round 27 spec were overstated.** `delta_state = 1.0` on
  the sportsbook leg reads as full relief; it is full relief *at the bare state
  rate*, an effective delta of 6.37/32.37 = **0.197**. And `delta = 1.0` on the
  Polymarket leg assumes capital gains exist to absorb the loss.
- **The structural reason**: each leg's loss is deductible only against a class
  of income the other leg does not produce. When the sportsbook leg loses the
  winner is a capital gain (nothing for NJ 54A:5-1(g) to net against); when the
  Polymarket leg loses the winner is ordinary income (IRC 1211(b) caps the
  offset at $3,000). Both reliefs are therefore *capacity*-dependent and default
  to zero.
- **Hurdles**: 8.83% with ample capacity, **16.75% with none**, 23.93% if the
  Polymarket leg is read as wagering. Real cross-book arbs pay 1-3%, so the
  engine's usual answer is REJECTED.
- Pinned against two closed forms: the known single-venue delta=0 hurdle
  (23.9317%, matches to 1e-6) and the trivially-zero fully-relieved case.

## Next / open questions

- `persist --status` will show `fees_measured` climbing from the next grid
  instant after a sampling pass; the first 7-day windows with a measured fee
  arrive with the first 168h windows (~2026-09-11).

- **Decision needed: the collector host sleeps.** Continuity was 78% before
  and a nightly sleep makes it worse; the service must be relaunched by hand
  after every resume (`start_collector.bat`). Either disable sleep on this
  machine or run the collector on one that stays up.
- **Ruling needed: spread line convention.** Store the selection's OWN handicap
  (away leg at +3.5) and group markets by |line|, or teach the matcher the
  home-keyed form. Until then no spread hedge can price.
- **Orderbook collection.** Nothing populates `orderbook_snapshots`; the cost
  drag on every basis decision rests on an assumed spread. Persisted windows
  will carry a measured `net_apr_after_fees` the moment it is written.
- `persist --status` daily. Ruling D precondition: 720h across >= 2 regime tags
  with >= 48h each; UNKNOWN never counts. First 168h persisted windows
  ~2026-09-11; first 24h walk-forward read `persist --hold 24` is available now.
- Polymarket live polling is the operator's call (network):
  `python -m cross_market.ingestors.polymarket_fetcher --live --watch`.

- **Incremental measurement persistence (option b)** is now *required* by Ruling
  D's 720h standard, not a follow-up. Design: persist per-event excursions and
  per-window realised funding as raw rows age out, so the analysis window is
  unbounded while storage stays flat.
- **7-day entry-conditioned re-run** once snapshots reach 168h (~2026-09-08).
  The 24h signal is validated (+17.7pp over control, coin-bootstrap 0.913-1.000);
  the 7-day hold the money is committed for is not.
- Run `python -m Tax_Reserve_Agent.main seed-bankroll --paper-bankroll <amt>`
  before any live desk starts, or every gate stays FAIL-CLOSED by design.

- **Is a Polymarket event contract capital or wagering?** Unsettled - the IRS has
  not ruled on retail-held CFTC-regulated binaries. IRC 1234A supports capital;
  a wagering characterisation collapses the leg into the same trap as the
  sportsbook and costs ~7 points of hurdle. `--prediction-as-wagering` prices it.
  This is the largest open legal question in the build.
- `matcher.TEAMS` is deliberately partial. An absent team produces NO MATCH,
  which is safe. Add teams on demand rather than loosening the matcher.

- **The drop path is `data/imports`, not `data/drop`.** Round 26m specified
  `Tax_Reserve_Agent/data/drop/`; that directory does not exist and nothing reads
  it. `config.yaml -> imports.drop_folder` and `csv_watcher.DEFAULT_IMPORTS_DIR`
  both resolve to `data/imports`. An export to `data/drop` would look like it
  worked and import nothing. A test now pins `TAX_DROP_DIR ==
  DEFAULT_IMPORTS_DIR` so they cannot drift.
- **No remote is configured.** Nothing is pushed anywhere. Before adding one,
  re-check `.gitignore` — the secrets argument only holds while the history is
  local.
- **The multi-state problem is not modelled.** A travelling contract worker
  resident in NJ owes roughly `max(NJ, work-state)` per dollar after the
  other-jurisdiction credit — higher in NY, lower in PA — and betting while
  physically in another state can source winnings there. The single 6.37% is the
  right approximation for a NJ resident; it is not a return.
- `professional_schedule_c` is permanently barred under *Groetzinger* while the
  x-ray contract work continues. Do not re-open it.
