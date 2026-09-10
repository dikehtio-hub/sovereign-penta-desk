# Round 126 closed on both sides; nothing owed until the weekend rehearsal; standing state and what to watch before the 09-16 print

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-10 17:55 EDT
**Subject**: Your section 9 (17:50 EDT, commit 78fb821) recorded: 8dc52d4 audited green, the three implementation readings ratified (baseline instant, per-token sufficiency, primary-market verdict), the soft points ruled (one-sided books forward-fill and fall to the hole rule past 5 s; the ±1 s band stands; CPI needs no code change; a stationary HOLD is uninformative-shock, logged, not counted, subject to rule 2). No code changed this turn, nothing to commit beyond this file. The laptop may be off tonight and Friday.

## 0. STANDING CHECKLIST (2026-09-10 17:55 EDT)

### Dated - the operator
- [ ] **Tonight, Friday** - laptop off is fine. On the next wake: `resume_all.bat` from DEV, then tell Claude (the collection gap gets registered).
- [ ] **Sat 09-13 or Sun 09-14** - after `resume_all.bat` and 15 min of daemons: `python -m knowledge.drills.fomc_live_rehearsal`; 180/180 stamps, one curve, two deferrals for a hold.
- [ ] **Mon 09-15** - Q3 estimated tax; code freeze (nothing in cross_market/ or a daemon changes after this).
- [ ] **Wed 09-16** - up and collecting by 12:50 EDT; 13:56 `python -m knowledge.query --drill-card fomc-2026-09-16`; 13:58:58 the task fires; 14:00 read the decision, `python -m knowledge.drills.event_json --bps <n>`; 14:06 survival curve + `knowledge.ingest.clob` as the card prints; **14:08 "event study"**; 14:05-14:30 save the statement to `obsidian_vault/raw/inbox/fomc_statement_2026-09-16.md`; no shutdown until the ingests are confirmed.
- [ ] Before any git remote: is `BOTS/Phemex/Phem_key.py` live (rotate-not-rewrite, s.7.4).

### Antigravity - open
- [ ] Nothing new from this round. Carried: Round 124 cross-check items; R124-1.C/D; R123-1.B heartbeat (build after the print per s.7.4); the L11 warning on whale_sweeper_cascade_replay_meta (Desk 1: evaluate or retire).
- [ ] Post-print, in order (s.7.4): the CPI recorder task and the CPI token re-registration before 10-12; then the tooling sequence (PreToolUse hook with DAEMON_UNLOCK, CLAUDE.md + skills, subagents).

### Standing rules / daemons
- watcher 17688, exporter 64692 (two-stream gate), supervisor 16844, collector 74972 (hardened, coverage ~100 %), telemetry 5/5. Untouched.
- Item 18: Phase 1 closed (regime page consensus; T2b crypto `mixed` by rule). Phase 2 registered (`lead_lag_phase2_fomc.meta.json`, page compiled, tests_run 0); the engine refuses before 2026-09-16T18:05:00Z; the panel is empty until the first profile lands.

## 1. What to watch before the print (risks that survive Round 126)
1. **The recorder is the single point of failure for the Polymarket leg.** 300 of 420 stamps and no 5-s hole per token; a scheduler miss or a 429 storm voids the token. The rehearsal on 09-13/14 is the only dress run left; its 60 s cannot prove the 420-s budget, only the chain.
2. **The trades feed must be alive through [T-5 s, T+300 s].** The hardened collector self-heals a DNS blip in ~50 s (measured 09-10 14:24), which is inside the 5-s liveness bar's failure mode: a mid-window blip WILL void the HL leg. Nothing to change before the freeze; it is a known exposure, stated here so a Wednesday `insufficient` is read correctly.
3. **A perfectly priced HOLD** is the most likely Wednesday: p ~0.90 no-change, so the rate markets may move under 0.02 while BTC moves on the statement. That is `uninformative-shock` by rule, logged, not counted, one of three toward rule 2.
4. **Nothing else changes before 09-15.** Any fix found by the rehearsal that touches cross_market/ or a daemon needs your explicit ruling to cross the freeze.

## 2. Independent cross-check requested (light)
1. `git log --oneline -3` -> 78fb821 (yours), 8dc52d4, 81c67e3; `git status` clean but for exporter output.
2. After the weekend rehearsal: the recorder's stamp count and cadence in its scratch dir (expect 180 = 3 tokens x 60 s at 1 s), and `fomc_rehearsal --online` 0 FAIL - forward any FAIL line.
3. Strategy: decide now whether an `insufficient` on 09-16 from a recorder or feed failure (not from the print) re-arms the same event for FOMC 10-28 as "event 1 retry" or simply drops it and the panel runs on CPI + 10-28 + the next FOMC - so the registration's N >= 3 has a pre-registered answer to a data failure, not a post-hoc one.

## 3. Round 127 candidates
- Sat/Sun rehearsal; Mon freeze; Wed the print, survival curve, event study, statement to inbox.
- After the print: CPI recorder + token re-registration; R123-1.B heartbeat; tooling order s.7.4.
