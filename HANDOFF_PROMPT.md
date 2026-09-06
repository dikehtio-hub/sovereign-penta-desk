# Round 114 Handoff: Cross-Check Request & Inquiries for Round 115

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-06 (commit `c7b70b7` at 18:22 EDT)
**Subject**: Round 114 delivered; the reopening verdict is INSUFFICIENT over the REGISTERED population, which Round 113 had got wrong; seven rulings requested

---

## 1. What was delivered (commit `c7b70b7`, 21 files)

- **D2 - the reopening question, answered (Ruling R113-1.C option 3)**. New engine runner `HyperLiquid/HL_Monarch/analytics/fade_rebenchmark.py` asks the registration's question of the persisted excursions read-only and writes `data/experiments/passive_fade_rebenchmark.verdict.json` beside the registration, **tracked**. New adapter `knowledge/ingest/fade_rebenchmark.py` grades the artifact INDEPENDENTLY (gates re-checked from the registration's own numbers, the bar parsed from its own rule text, the population checked against `population.source`) and compares with the engine's verdict. **Verdict: INSUFFICIENT; engine and page agree.**
- **D1 - the drill's entry point is under version control (R113-1.F)**. `cross_market/scripts/fomc_drill_2026-09-16.bat`; `Monarch_FOMC_Drill`'s action re-pointed with `Set-ScheduledTask -Action` only; trigger, battery flags, logon type, MultipleInstances and Enabled compared before/after as JSON and identical. Battery flags untouched (operator decision). The pre-flight now FAILs if the batch is ever untracked.
- **D3 - pre-flight hardening**: 29 checks (was 22). New: W32Time service state, NTP offset via `w32tm /stripchart` (WARN when unmeasured), books-dir writability by a probe file written and removed in the nearest existing ancestor, stamp path length (182 of 240), MultipleInstances policy, orphan `record-loop` processes. Real run: **0 FAIL, 3 WARN** (battery flags; interactive logon; **W32Time is STOPPED on this machine**, offset +0.37 s).
- **D4 - docs**: AGENTS.md status + "Round 114 findings" (every statistic filled from the artifact by script, none typed), COMMANDS.txt, HOMEWORK.md; digest `round_114.md` compiled.

**Telemetry, all offline:** knowledge **302 passed** (+16); HL **1,108** (+5); no other desk source changed. Lint **496 pages, CLEAN**. Idempotent across `fade_rebenchmark` / `experiments --force` / `digests` / `seed` by per-file sha256. No daemon touched; W32Time deliberately left as found.

**Timing:** clock read 18:59:02Z; ~10 min audit; quoted 65 (55-75) for the build; commit 22:22:03Z. Wall 203 min, of which ~138 min was the session idle after the 20,000-draw bootstrap finished at 19:44Z, waiting for the operator's "resume". **Effective 65 min.**

---

## 2. Where I deviated from the directive, and the evidence

### (a) The registered population is `trade_sweep`, not the table - and Round 113 got this wrong.
`cascade_excursions` holds two treatment sources: `trade_sweep` (13,645 rows, 46 coins) and `trade_flow` (5,363 rows, 28 coins). `storage/measurement_schema.py` keeps the `source` column because "the two event sources answer different questions and must never be pooled". The fade's events are sweeps (the registration's status line: "sweeps accumulate"); `wick_benchmark.benchmark()` and the `excursion` command default to `trade_sweep` ("the strategy's"). Round 113's progress mirror pooled every treatment row (19,008; top coin ZEC 19.84%) and marked the registration `ready` - which you ratified in R113-1.B on my report. Over `trade_sweep` at the same instant: **top coin ZEC 26.8% against a 20% ceiling, span 5.49 days against 7 required**. Two gates fail.
- The registration's own `state_at_registration` numbers (492 events, 15 coins) match NEITHER persisted source at that instant (48 and 274 rows): they came from the snapshot-based benchmark, a different pipeline. The population could not be inferred from counts; it had to come from the code the registration binds to.
- Recorded as a dated `population` block on the registration (`recorded_utc`, `source`, `basis`, `finding`, `bars_unchanged: true`) - a clarification of what the code always measured, with the Round 113 error stated in it. **No bar changed.** `git show c7b70b7 -- HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json` shows only that block added.
- The mirror now filters by `population.source` when a registration names one and pools only when none does (the cascade-replay engine pools by design, so `whale_sweeper_cascade_replay` stays pooled).

### (b) D2 said "silencing Lint L11 permanently". An INSUFFICIENT verdict must not do that.
INSUFFICIENT means "come back when the sample qualifies". Round 113 flipped a registration to `evaluated` the moment any `_verdict` page existed; that would have hidden exactly the condition L11 exists to surface. Now only a PASS / FAIL / RETUNE grade (or a verdict page too old to carry one) closes the question. The `passive_fade_rebenchmark` page says **ACCUMULATING - 2/4 sample gates pass over population `trade_sweep`. Failing: max_single_coin_share 0.266 vs 0.2; window_days 5.49 vs 7.0. Last evaluation 2026-09-06: INSUFFICIENT**, and links the verdict.
- **Consequence you should know about:** `whale_sweeper_cascade_replay` (Round 104: INSUFFICIENT on PONS 22.5%) is no longer `evaluated`. Its pooled sample now passes every gate including `max_hhi` (0.1328 vs 0.15), so it reads **`ready` since today, and L11 will ask for a re-run on 2026-09-09**. That is the rule working, and it is a Round 115 item (see R114-1.B).

### (c) The verdict, exactly (from the artifact, `written_at` 2026-09-06T19:44:26Z, 38,016 rows in table)
- Population `trade_sweep`: 13,645 events, 46 coins, top coin ZEC 26.78%, span 5.49 d. Engine gate: `SAMPLE_TOO_NARROW: top coin 27% > 20%`; the adapter additionally fails the 7-day window (the engine's gate checks retention capacity, not the span actually covered - see R114-1.G).
- Decision horizon 30m: the longest the registration enumerates (5m/15m/30m; the engine's pre-registered read is "the longest usable horizon"); the persisted 60m column post-dates the registration and is reported only. Your "30m" holds, for that reason.
- `ratio_30m` = mean(MFE)/mean(MAE) = **0.7896** on 13,553 measurable events (below 1: the cascade kept going). Matched control 0.9498. **P(ratio_30m >= 1.25) = 0.0000** and P(>= 1.0) = 0.08 at 20,000 cluster-bootstrap draws, seed 7. Had the sample qualified this would be **FAIL**; it is stated on the page for completeness and is not a verdict.
- The fade stays retired and PASSIVE. Nothing was enabled.

### (d) A double writer, caught on the first real run - by the hash, not by lint.
The artifact lives beside the registrations, so the experiments ingest globbed `passive_fade_rebenchmark.verdict.json` and compiled it as a generic registration into `passive_fade_rebenchmark_verdict.md` - the very page the new adapter writes. Each run flipped the page between the two shapes; lint was CLEAN both ways and both adapters reported success. `compile_registration` now returns None for any JSON carrying the engine's `_artifact` envelope, with a test that runs both writers in both orders. Round 110's lesson, third occurrence.

### (e) W32Time is stopped. I did not start it.
`w32tm /query /status` fails with "the service has not been started"; the stripchart against time.windows.com still measured +0.371 s. Reported as WARN with the two-command remedy (`Start-Service W32Time; w32tm /resync`), in HOMEWORK as the operator's action. Starting a service is theirs.

### (f) Desk 4 packages: still not installed.
You approved `uvicorn` and `hyperliquid-python-sdk` conditional on a clean dry run (it is clean: no downgrades). I did not install them: the environment is the one the live desks run in, and HOMEWORK told the operator I would wait for their own word. If the operator relays this prompt with a yes, Round 115 installs and runs the four modules for the first time.

---

## 3. Rulings requested (R114-1.x)

- **R114-1.A** - Ratify the `population` block as a dated clarification (not an amendment of any bar) and the mirror's rule: named source -> filter; none -> pooled. Also ratify the correction of the R113-1.B record: the sample was NOT ready on 2026-09-06 under its registered population.
- **R114-1.B** - `whale_sweeper_cascade_replay` is `ready` (pooled gates all pass) and L11 fires 2026-09-09. Options: (1) re-run `analytics.cascade_replay --json` + `knowledge.ingest.cascade_replay` in Round 115 while the gates pass; (2) retire the registration; (3) leave it and let L11 warn. I recommend (1); it is the same shape as this round's D2 and the machinery exists.
- **R114-1.C** - Ratify INSUFFICIENT-is-not-terminal (`evaluated` only on PASS / FAIL / RETUNE, or a verdict page without a grade).
- **R114-1.D** - Ratify the artifact's home beside its registration under version control, and direct whether Round 104's artifact (`cross_market/data/whale_sweeper_cascade_replay_verdict.json`, git-ignored) should be re-run into `HyperLiquid/HL_Monarch/data/experiments/` so a clone can reproduce that page too.
- **R114-1.E** - When may the fade sample qualify? The window gate clears on ~2026-09-08 (first trade_sweep row 2026-09-01T05:xxZ + 7 d). The share gate depends on the coin mix and cannot be scheduled; the registration page shows all four gates on every ingest. Direct whether the runner should be re-run automatically the first day both pass, or only on your word.
- **R114-1.F** - The engine's `_reopening_sample_gate` checks n, coins and share, and `retention_covers_window` checks retention CAPACITY - neither checks the span the rows actually cover. The adapter does. Direct whether the engine should gain the span check (desk code, Round 115) so engine and page cannot disagree on it.
- **R114-1.G** - Confirm whether the operator wants the Desk 4 installs done on your approval alone, or on their explicit word (section 2f).

---

## 4. Independent cross-check requested

1. `git show --stat c7b70b7` -> 21 files; `git status --short` empty. `git show c7b70b7 -- HyperLiquid/HL_Monarch/data/experiments/passive_fade_rebenchmark.meta.json` -> only the `population` block added.
2. Population, by SQL (read-only): `SELECT source, COUNT(*), COUNT(DISTINCT coin) FROM cascade_excursions GROUP BY source` and, for trade_sweep, the top coin's share and `(MAX-MIN)(timestamp_utc)/86400000`. Compare with the four gates on `wiki/experiments/passive_fade_rebenchmark_meta.md` and with `sample_gates.metrics` in the artifact.
3. The verdict page's numbers equal the artifact's (`primary_metric`, `sample_gates.metrics`, `_artifact.written_at`). Nothing on the page should exist that is not in the JSON or the registration.
4. Double-writer fix: run `python -m knowledge.ingest.experiments --force` then `python -m knowledge.ingest.fade_rebenchmark`, hash the vault, run both again in the other order, hash again -> identical, and the verdict page's `dev.kind` is `rebenchmark_verdict` after both.
5. `python -m knowledge.drills.fomc_rehearsal` -> 29 checks, 0 FAIL, 3 WARN; `git status` unchanged; the books directory still does not exist afterwards (the probe is removed).
6. `Get-ScheduledTask Monarch_FOMC_Drill` -> action is `cross_market\scripts\fomc_drill_2026-09-16.bat`, trigger 2026-09-16T13:58:00, both battery flags still True, LogonType Interactive, MultipleInstances IgnoreNew.
7. Suites with the documented invocations (COMMANDS.txt Round 113 block): knowledge 302; HL 1,108 from its directory.
8. Brainstorm: which other registrations bind to a population their page does not name? Anything measuring "events" over `cascade_excursions` needs `population.source` or an explicit statement that pooling is the protocol.

---

## 5. Round 115 candidates (not started)

- R114-1.B: re-run the whale-sweeper cascade replay under its registration while every gate passes (L11 due 2026-09-09).
- **Live dress rehearsal (Sep 13-14)**: a `--live SECONDS` mode running the real recorder for 60 s into a scratch books dir, then survival curve and `knowledge.ingest.clob` over it. Needs the operator's go-ahead (network).
- R114-1.F: span check in the engine gate. R114-1.D: relocate Round 104's artifact.
- Desk 4 installs (on the operator's word) and cwd-independent config paths.

## 6. Operational reminders

- **Tonight 22:20 EDT the Tier 2b 24 h series closes** - laptop on, plugged in, logged in; it is 18:25 EDT as this is written.
- **W32Time is stopped**: `Start-Service W32Time; w32tm /resync` (elevated), then re-run the pre-flight.
- Battery flags on the drill task: still the operator's open decision; the pre-flight WARNs until it is made.
- Sep 15 tax escrow. Sep 16 13:58 EDT the drill; run the pre-flight that morning.
- Nothing was restarted this round; nothing should be until you direct it.
