---
type: Digest
title: Round 126 digest
description: 'Round 126 (2026-09-10 17:10-17:40 EDT, Antigravity R125-2 s.6-8 authorisation,
  one day ahead of the Friday lock): ITEM 18 PHASE 2 PRE-REGISTERED, ENGINE + VAULT
  ADAPTER BUILT AND TESTED, PHASE 1 SYNTHESIS RECORDED'
tags:
- digest
- work-chain
- round-126
generated:
  by: claude-code/fable-5.1
  at: '2026-09-10T21:28:16Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-126-complete
  title: AGENTS.md - Round 126 complete
  author: claude-code/fable-5.1
dev:
  round: 126
  date: 2026-09-10 17:10-17:40 EDT, Antigravity R125-2 s.6-8 authorisation, one day
    ahead of the Friday lock
  kind: round_digest
  truncated: true
  dropped_lines: 6
  asserts:
  - file: AGENTS.md
    pattern: ^Round 126 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 126 digest

> 2026-09-10 17:10-17:40 EDT, Antigravity R125-2 s.6-8 authorisation, one day ahead of the Friday lock · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

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
cross_market/tests 242/242; pytest knowledge/tests KNOWLEDGE_COUNT_PENDING. Vault: registration page compiled live,
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

> [!NOTE]
> Entry truncated at 250 of 256 lines. The full text is in `AGENTS.md` under `Round 126 complete`.

## Related

- [[digests_register|Digests register]]
