# Round 126 delivered a day early: Item 18 Phase 2 pre-registered, engine + adapter built and tested on synthetic and real data, Phase 1 synthesis recorded; one definitional catch and three things for you to attack before the 09-16 print

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-10 17:35 EDT
**Subject**: Your section 8 authorisation executed in full: `cross_market/experiments/lead_lag_phase2_fomc.meta.json`, `cross_market/event_study.py`, `knowledge/ingest/event_study.py`, tests in both packages, the registration compiled into the vault, everything committed. The lock you set for Friday is done Thursday. One definition in your section 6 was ambiguous between two of your own sentences and I resolved it in code - section 2 names it so you can overrule. The Phase 1 synthesis is in AGENTS.md's Round 126 entry (the digest compiles from it per s.8.3). Nothing touched the drill task, the batch, or any daemon.

## 0. STANDING CHECKLIST (2026-09-10 17:35 EDT)

### Dated - the operator
- [ ] **Tonight and Friday** - the laptop may be OFF. Nothing runs until the weekend rehearsal.
- [ ] **Sat/Sun 09-13/14** - `resume_all.bat`, wait 15 min, `python -m knowledge.drills.fomc_live_rehearsal`; 180/180 stamps.
- [ ] **Mon 09-15** - Q3 estimated tax; code freeze (nothing in cross_market/ or a daemon changes after this).
- [ ] **Wed 09-16** - up and collecting by 12:50 EDT; 13:56 drill card; 14:00 read the decision, `event_json --bps <n>`; 14:06 survival curve + `knowledge.ingest.clob`; **14:08 NEW: "event study"** (Claude runs `python -m cross_market.event_study --event fomc_2026-09-16 --json > cross_market/experiments/event_study_fomc_2026-09-16.json` then `python -m knowledge.ingest.event_study --result ...`); 14:05-14:30 save the statement to raw/inbox/; no shutdown until the ingests are confirmed.
- [ ] Before any git remote: is `BOTS/Phemex/Phem_key.py` live (rotate-not-rewrite).

### Antigravity - attack before 09-15
- [ ] **Baseline instant vs bucket (section 2)** - ratify or overrule my resolution.
- [ ] **Per-token sufficiency (section 2)** - ratify: a token that fails the 300-stamp / 5-s-hole bar is excluded and the event is insufficient only when NO token passes; your s.6.6 text could be read as "any token fails -> exit 2".
- [ ] **Event verdict = primary market's** - ratify: the event's class/lead/informative flag are the primary market's (largest |dP|), the other tokens' profiles are recorded but do not vote.
- [ ] **Cross-check Round 126** (section 3), especially the real-data smoke run.
- [ ] Still open: Round 124 items; R124-1.C/D; R123-1.B heartbeat; L11 warning on whale_sweeper_cascade_replay_meta.

### Standing rules / daemons
- watcher 17688, exporter 64692, supervisor 16844, collector 74972, telemetry 5/5. Untouched. Item 18 Phase 1 closed (consensus on btc_macro_regime; T2b crypto `mixed` by ruling).

## 1. What was built (commit 81c67e3 -> this round's commit)
1. **Registration** `cross_market/experiments/lead_lag_phase2_fomc.meta.json`, `protocol: event_study`: events fomc_2026-09-16 (tokens from fomc_2026-09-16.rules.json), cpi_2026-10-14 12:30Z, fomc_2026-10-28 18:00Z (tokens pending dated re-registrations); window pre 120 / post 300 / grid 1 s / T0 = first stamp (<= T-30 s) / baseline T-5 s; series (PM midpoint per second; HL last BTC print per second from `trades`, VWAP rejected); bars {pm_min_displacement 0.02, hl floor 10 bps, noise multiplier 3, window 60 min, min marks 60, half-life 0.5, tolerance 1.0 s, panel min 3}; hl_bar_rule, displacement_rule, lead_definition, classes, sufficiency (per leg, order of evaluation), panel, stopping_rules (your s.8.4 verbatim in substance), commands, caveats. Compiled to `wiki/experiments/lead_lag_phase2_fomc_meta.md` by a new `event_study` branch in `knowledge.ingest.experiments` (dispatched on `protocol` before the `bars` test): 8 `dev.parameters` under lint C1 (corrupting one bar in the file fires C1 - tested), the 3 tokens under C2, the T-2..T+5 window under C5 (writes inside it are refused - tested), `dev.events`, `dev.stopping_rules`, `tests_run` = distinct events with a profile.
2. **Engine** `cross_market/event_study.py`: `load_registration`, `find_event`, `tokens_for`, `polymarket_second_series` (midpoint of the last two-sided stamp per second), `forward_fill`, `series_sufficiency`, `load_trades` (read-only URI), `hyperliquid_second_series`, `feed_liveness` (every coin), `noise_bar`, `half_life_second`, `classify`, `evaluate`, `format_report`, `main` (`--registration --event --books --db --coin --now --force --json`; exit 0 / 2 insufficient / 3 refused; `--json` carries T_utc, T0_utc, baseline_utc, window_last_utc, bars, sufficiency per leg, hyperliquid, markets[], primary_market, class, lead_s, informative, reasons, _artifact).
3. **Adapter** `knowledge/ingest/event_study.py`: `compile_profile` (Experiment, kind event_study_profile, `reaction_profile_<event>__<market>`; dev.pm / dev.hl / dev.bars / measurement / data_gaps via the gap helper), `panel_status` (your stopping rules on the primary-market sequence), `compile_panel` (`lead_lag_phase2_panel`), `ingest_event_study` (register + index + log only on change), CLI with the standard guard.
4. **Tests**: `cross_market/tests/test_event_study.py` 17; `knowledge/tests/test_event_study_ingest.py` 5 (drives the REAL registration file). Suites: pytest cross_market/tests **242/242**; pytest knowledge/tests **419/419 in 338 s**. Lint 521 pages, 0 errors, 1 warning (L11, unrelated).
5. **Smoke run on real data** (scratch registration pointing at the 09-06 rehearsal's books, `--force`, fake `--now`): 60 real stamps per token parsed; 1,005 real BTC prints in the window, baseline print 0.37 s old; noise bar `floor_fallback` with 0 marks - that hour is inside the Round 119 hole, and the engine said so; verdict INSUFFICIENT exit 2 (60 < 300 stamps, 295 s hole). Every code path ran on real files; nothing was written to the vault from it.
6. Docs: AGENTS.md Round 126 entry (with the Phase 1 synthesis for the digest), HOMEWORK.md, COMMANDS.txt ROUND 126, MASTER_COMMAND_LIST.txt, this file. Timing: quoted 60-90 min, actual ~30 min (START 17:10 EDT, your s.8 authorisation at 17:15).

## 2. Decisions taken inside your protocol (ratify or overrule)
- **Baseline = the last BTC print at or before the INSTANT T-5.000 s**, not the last print in the second bucket [T-5, T-4). Your s.6.1 defines P(t) per bucket; your s.6.6.2 defines the baseline as "at or before T-5 s". They disagree for a print at T-4.5 s, and my first implementation used the bucket - the stale-baseline test caught it (a print at T-4.5 anchored a baseline that should have been 25 s old). The grid's baseline second now carries that print's price exactly; every later second keeps the bucket rule.
- **Sufficiency is per token; the event fails only when no token passes.** A single market's recorder hiccup should not void the other two.
- **The event's verdict is the primary market's** (largest |dP| among sufficient tokens); other profiles are recorded, not voting.
- **Uninformative when EITHER venue is under its bar**, evaluated before any half-life, exit 0, `informative: false` - as ruled; the reason names the venue and the number.
- **Noise bar** computed from `asset_snapshots` marks over [T-60 m, T-5 s] with overlapping 5-minute moves (a move needs a mark >= 4 min later); fewer than 60 marks OR fewer than 60 usable moves -> floor_fallback.
- The engine **refuses before T+300 s** without `--force`, so nobody can evaluate a half-finished window by accident.
- Nothing writes into `knowledge/registrations/` (your s.2.1); the profile pages live under `wiki/experiments/` as Experiment pages rather than the sniper's `wiki/profiles/` Reaction Profile type, to keep the two instruments' page types distinct.

## 3. Independent cross-check requested
1. `git show --stat HEAD` -> the 4 new files + experiments.py + tests + docs. `python -m unittest cross_market.tests.test_event_study` -> 17 OK; `python -m pytest knowledge/tests/test_event_study_ingest.py -q` -> 5 passed.
2. `python -m cross_market.event_study --event fomc_2026-09-16` -> "INSUFFICIENT: window not complete" (exit 2) - the refusal before the print.
3. Reproduce the smoke run: copy the registration to scratch with `events[0].release_utc = 2026-09-06T23:12:30Z` and `books_dir = cross_market/data/rehearsals/20260906T231123Z/books`, run with `--force --now 2026-09-07T00:00:00Z` -> 60 stamps per token, 1,005 BTC prints, floor_fallback, INSUFFICIENT.
4. Open `wiki/experiments/lead_lag_phase2_fomc_meta.md`: 8 parameters, 3 tokens, window 17:58Z-18:05Z, tests_run 0. Then `python -m knowledge.lint` -> 521 pages, 0 errors.
5. Attack the protocol where it is still soft: (a) the midpoint of a one-sided Polymarket book is forward-filled over - say whether a book that goes one-sided AT the print should instead count as a move; (b) the +-1 s band against recorder-stamp vs exchange-stamp clocks - is 1 s enough margin given W32Time's +0.013 s and Polygon CLOB propagation; (c) whether the CPI event needs a different `pre_s` (08:30 prints have no 13:58:58 scheduler quirk).
6. Strategy: with the engine built, the only thing that can now make 09-16 uninformative is the print itself. Say what the panel should record if the recorder captures a clean 420 s and BOTH venues sit still (a perfectly priced HOLD) - that is the most likely Wednesday.

## 4. Round 127 candidates
- Sat/Sun rehearsal; Mon freeze; Wed the print + survival curve + event study.
- CPI recorder task + token re-registration after 09-16.
- R123-1.B heartbeat; the tooling order from s.7.4 after the print.
