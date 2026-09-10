---
type: Digest
title: Round 125 digest
description: 'Round 125 (2026-09-09 14:00-14:45 EDT, Antigravity R125-1.A/B/C/D, operator-authorised):
  COLLECTOR HARDENING DEPLOYED, COLLECTOR RESTARTED, GAP #2 REGISTERED, RUN 3 VOID
  AND RE-BOUND, READINESS GATE NOW JUDGES THE PRICE STREAM'
tags:
- digest
- work-chain
- round-125
generated:
  by: claude-code/fable-5.1
  at: '2026-09-10T21:28:16Z'
status: draft
sources:
- id: agents-log
  resource: AGENTS.md#round-125-complete
  title: AGENTS.md - Round 125 complete
  author: claude-code/fable-5.1
dev:
  round: 125
  date: 2026-09-09 14:00-14:45 EDT, Antigravity R125-1.A/B/C/D, operator-authorised
  kind: round_digest
  truncated: false
  dropped_lines: 0
  asserts:
  - file: AGENTS.md
    pattern: ^Round 125 complete
    claim: the round heading this digest was compiled from is still in the log
---
# Round 125 digest

> 2026-09-09 14:00-14:45 EDT, Antigravity R125-1.A/B/C/D, operator-authorised · compiled from `AGENTS.md`. **The log is the record**; this page is an index into it, and loses to it wherever they disagree.

## What the log says

COLLECTOR

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

## Related

- [[digests_register|Digests register]]
