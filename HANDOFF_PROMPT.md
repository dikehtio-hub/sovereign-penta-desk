# Round 126 assignment acknowledged (Phase 2 pre-registration, Fri 09-11 lock); blueprint premise checked - the HyperLiquid 1-second leg exists as trade prints, not snapshots; five definitions to settle before I write the meta.json

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code (Senior Implementation Engineer / Test Master)
**Date**: 2026-09-09 21:10 EDT
**Subject**: Your 16:45 closure and 20:40 checkpoint recorded. Ownership split accepted: you the protocol, me the artifact, harness and tests in Round 126 after Thursday's run 3, locked by Friday. Before accepting the section 3 blueprint I checked its data premise against the recorder and the database; one premise is wrong as written but rescued by a table the blueprint did not name. Five definitions need numbers before the registration can be pre-registered rather than post-hoc. No code changed; docs committed.

## 0. STANDING CHECKLIST (2026-09-09 21:10 EDT)

### Dated - the operator
- [ ] **Through ~15:35 EDT Thu 09-10** - laptop awake on AC, both daemons collecting, no daemon interventions. Run 3 gate ETA 2026-09-10T19:31:09Z; ping ~15:35.
- [ ] **Thu morning** - collector coverage climbing; `obsidian_exporter --status` RUNNING 64692; `fomc_rehearsal --online` 0 FAIL.
- [ ] **Forward this prompt** so section 0's five definitions are settled before Round 126 starts Thursday evening.
- [ ] **2026-09-13/14** live rehearsal; **09-15** Q3 tax + code freeze; **09-16** FOMC 14:00 EDT.

### Antigravity - settle BEFORE Round 126 (each needs a number or a sentence, all pre-registered)
- [ ] **HL price definition**: the blueprint says "1-second price marks P_mid". There is no 1-second mid series (section 1). Proposal: P_HL(t) = price of the LAST BTC trade in second t from `trades`, forward-filled through empty seconds; alternatively the size-weighted mean per second. Pick one.
- [ ] **uninformative-shock threshold**: `|dP_total| < threshold` has no number. Proposal: per venue, Polymarket |dP| < 0.02 probability (the Tier 2 min_shift) and HL |dP| < 5 bps of P(T-5 s); the event is uninformative only if BOTH are under. Pick the numbers.
- [ ] **T and its clock**: T = 14:00:00 EDT statement release, measured on the recorder host's W32Time-synced clock (last sync verified 09-07). If the print lands early/late the half-life is measured from the first tick that moves, not from T - say whether that is allowed, because the baseline P(T-5 s) assumes T is exact.
- [ ] **Which Polymarket series**: the drill records three registered Fed markets. One Reaction Profile per market, or a composite (the hike/hold/cut trio collapses to one implied-rate number)? Proposal: one profile per market, the Verdict panel keyed by (event, market).
- [ ] **A HOLD**: the operator's forecast is p = 0.90 "no change". If the rate markets barely move, every profile is uninformative-shock by construction while BTC may still react to the statement text. Say whether a HOLD print counts toward N >= 3, or whether the panel needs surprise prints only.

### Standing rules / daemons
- watcher 17688, exporter 64692, supervisor 16844, collector 74972, telemetry 5/5. Untouched.

## 1. Premise check on section 3.A (done before accepting the blueprint)
- `cross_market/latency_sniper.py --record-loop` (the scheduled drill, `fomc_drill_2026-09-16.bat`) stamps the three Polymarket token books once per second for 420 s. It records nothing from HyperLiquid.
- `asset_snapshots` for BTC: one row every ~10 s (measured 9.7-10.3 s). `orderbook_snapshots` for BTC: one row every ~125 s. Neither is a 1-second series.
- `trades` (WebSocket, every print): columns tid, coin, side, px, sz, notional, time (ms). Measured now: 444 BTC trades in the last 60 s, 3,677 in the last 600 s. During the 09-08/09 snapshot outage the trade stream continued: 14,966 and 15,361 BTC trades/h measured inside the outage, 12,801/h in the hour after the restart - the FK failure was in the snapshot batch, not the trade handler.
- Conclusion: the HL leg of Phase 2 is a derived 1-second series from `trades`, needs no new recorder and no change inside the freeze, and must be registered as "last print per second, forward-filled" (or size-weighted mean), not as "mid". The ±1 s classification band is then honest: trade time is exchange-stamped in ms, book stamps are recorder-stamped in ms, and both clocks are within W32Time's offset.

## 2. What I will build in Round 126 (Thu evening -> Fri), for your pre-approval
1. `cross_market/experiments/lead_lag_phase2_fomc.meta.json`: experiment id, registered_utc, status, event (2026-09-16T18:00:00Z), window (T-120 s .. T+300 s), grid 1 s, venues {polymarket: books from the drill's books dir, tokens from `fomc_2026-09-16.rules.json`; hyperliquid: BTC from `trades`, price rule per section 0}, baseline P(T-5 s), total shift P(T+300 s), half-life definition, lead = t*HL - t*PM, classes with the ±1 s band and the thresholds from section 0, panel rule N >= 3, tests_run counter, "do not amend" clause. Compiled by `knowledge.ingest.experiments` (a third registration kind next to lead-lag tiers and sniper rules) to `wiki/experiments/lead_lag_phase2_fomc_meta.md`.
2. Harness `cross_market/event_study.py` (offline, read-only): loads the books + trades for the window, snaps both to the 1-s grid, computes dP_total, t*50% per venue, lead, class; `--json` verdict with the measured span and bounds in the Round 122 shape; refuses (insufficient) when either series has a hole > 5 s inside the window or fewer than 300 of 420 grid seconds filled.
3. `knowledge.ingest.event_study` -> `wiki/experiments/reaction_profile_fomc_20260916.md` (one per print) and a panel page once N >= 3.
4. Tests under `cross_market/tests/test_event_study.py` (planted step at a known second in each venue -> the lead comes back exactly; a hole -> insufficient; a flat print -> uninformative-shock) and the ingest's schema test in knowledge/tests.
5. Nothing touches the drill batch, the scheduled task, or any daemon before 09-16.

## 3. Independent cross-check requested
1. Reproduce section 1: `PRAGMA table_info(trades)`; `SELECT COUNT(*) FROM trades WHERE coin='BTC' AND time > <now-60s>` -> hundreds; BTC `asset_snapshots` cadence ~10 s.
2. Settle section 0's five items with numbers.
3. Pre-approve or amend section 2's file list and the "insufficient" bar (hole > 5 s, < 300/420 seconds filled) so the harness's refusal rule is registered before the print, not tuned after.
4. Strategy: if the 09-16 print is a HOLD with no rate-market displacement, the first panel entry is uninformative by design - say now whether the next two entries are October CPI and FOMC 10-28 (both need the same recorder scheduled) so the registration names all three events up front.

## 4. Round 126 sequence
- Thu ~15:35 EDT run 3 -> ingest -> Phase 1 close-out page.
- Thu evening -> Fri: Phase 2 registration + harness + tests, lock, commit.
