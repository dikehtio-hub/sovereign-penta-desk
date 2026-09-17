# HOMEWORK — things only the operator can do

Everything in this file needs a human. Anything an agent can do is not here; that
lives in `LLM_WIKI_BACKLOG.md` (knowledge layer) and the Top 20 registry in
`MASTER_COMMAND_LIST.txt` (trading desks).

Last updated: 2026-09-16 15:00 EDT (**DRILL COMPLETE. Every automated step is done; three human items are left,
none urgent.** Recorder fired 13:58:00.80, exited clean 14:05:02.48, 419 polls / 1257 stamps / 0 failures /
0 rate-limits. Fed **HIKED 25 bps** to 3.75-4.00% - your registered p=0.90 "no change" was wrong, and the market
knew: Polymarket had the hike at **0.875** five seconds before the print. Verdict **uninformative-shock**: Polymarket
displaced hard (0.875 -> 0.975, +0.10 vs a 0.02 bar, at T+1 s) but BTC moved only 6.47 bps against a 17.43 bps noise
bar, and a lead needs both venues. Logged, not counted; the Phase 2 panel needs more events (0 of 3 informative).
Latency decay on the live market: baseline 87,221 notional at T-0.062 s, first change **+0.939 s**, half gone
**+1.939 s**, 90% gone **+5.942 s**. ONE INCIDENT, corrected and disclosed: the first curve was anchored at 18:10:24Z
(when you typed the command) instead of the print, and measured nothing - see
`cross_market/experiments/fomc_2026-09-16_anchor_incident/`. **YOUR THREE ITEMS: (1) copy the Fed statement text to
the inbox (~2 min, line ~174); (2) drag `cross_market/data/archives/fomc_2026-09-16_drill_raw.zip` (1.3 MB) to a
cloud drive or USB - there is NO git remote, so a commit is not a backup; (3) Q3 tax needs nothing, $0.00, see line
~130.** Two defects found during the audit are logged in AGENTS.md. Earlier header preserved below.)
  _(previous header: 2026-09-16 12:20 EDT (**DRILL DAY. T-1h 38m to the recorder.** Morning gates are DONE and both clean:
`fomc_rehearsal --online` 33 checks 0 FAIL 1 WARN, `fomc_live_rehearsal` 21 checks 0 FAIL 0 WARN. The cross-market
exporter had died again at 03:55 EDT (DEFECT-EXP-001, 3rd crash); you authorised the restart and it is cycling as
PID 4552. Collector fresh, all 3 CLOB tokens resolve in 129-233 ms, task armed for 13:58:58, on mains at 99%,
160 GB free, NTP offset +0.314 s, no sleep since the 09-13 boot. **13:30 verify DONE 13:30:44, all green; the task
fires at 13:58:00 sharp.** Remaining, from the minute-by-minute block at line ~123: 13:55 collector check (re-run the
one-liner; it read 0.3 min at 13:30), 13:56 drill card, 13:57:30 hands off everything, 14:00 read the rate
decision and run `event_json --bps <n>`, 14:06 survival curve + CLOB ingest, 14:08 event study. Earlier header
preserved below for the record.))_
  _(previous header: 2026-09-14 20:20 EDT (DRILL WEEK. Two human deadlines are live (the cross-market exporter restart is DONE, 20:39 EDT 09-14): **Q3 estimated tax TOMORROW Tue 09-15** (line ~110 below), and **laptop on AC, awake, you at the terminal by 13:30 EDT Wed 09-16** for the 14:00 FOMC print. The daily two-check block (line ~102) is still unticked for today. The Wed 09-16 minute-by-minute block was re-audited 09-14 19:55 EDT: its existing steps are correct and already cover logon, lid and sleep; the 13:55 collector check is RATIFIED by Antigravity in Section 85. Agent side: exchange closed with Section 85, Sections 64-85 all verified, ZERO directives owed either way, code freeze intact, all desks streaming (collector snapshot age ~7 s at 20:04Z). Nothing for you to relay to either agent before the drill. Earlier header preserved below for the record.))_
  _(previous header: 2026-09-10 16:10 EDT (RUN 3 DONE, all no-lead, Item 18 Phase 1 closed; laptop may be shut down after the commit; Round 126 next. Earlier: Round 126 assigned: Phase 2 pre-registration after run 3, lock Fri 09-11; five definitions for Antigravity in HANDOFF_PROMPT.md. Round 125 CLOSED, all rulings ratified: hardening deployed + collector restarted 14:26 EDT; gap #2 registered; run 3 re-bound to --since 2026-09-09T19:27:39Z, gate ETA 19:31:09Z = ~15:31 EDT Thu 09-10, ping ~15:35; both-stream gate live in the CLI, the exporter loop (pid 64692) and the Obsidian card; Phase 2 pre-registration due before 09-15).)_

---

## 📅 YOUR CALENDAR — every action, in date order (times are EDT)

If you read nothing else, read this block. Each line is one thing, when to do it, and how long it takes.

### Tonight / this week (now = early Mon 09-07, ~01:00 EDT)
- [x] ~~**Send the Round 121 handoff to Antigravity.**~~ Sent; Antigravity replied. Round 122 handoff sent too and
      ANSWERED: R122-1.A ratified, R122-1.B adopts the DISJOINT window for run 2, R122-1.C leaves the old pages as is.
- [x] ~~**Start the Windows Time service.**~~ DONE 2026-09-07 01:13 EDT (you approved the UAC prompts). It was
      *running but never synced* (Source: Local CMOS Clock) and something automated was stopping/starting it
      every ~17 min. Set to Automatic, started, and force-synced: now Source `time.windows.com`, last sync
      01:12:54. Minor watch: if the churner stops it again the clock still holds; re-run the resync only if a
      pre-flight ever shows a large offset.
- [x] ~~**Desk 4 packages**~~ - you said yes (2026-09-07), but nothing to install: both `uvicorn` and
      `hyperliquid-python-sdk` (0.24.0) are ALREADY in Desk 4's venv (the other agent installed them). The four
      formerly-skipped modules now run and pass (23 tests); the full Desk 4 suite is 180 passed, 0 skipped.
- [ ] **One decision left:** name a deploy window for the collector hardening (see 09-08 below; recommended
      Tue/Wed evening).
- [x] ~~**Run 2 of 3 (Mon 09-07 ~22:22 EDT)**~~ DONE 2026-09-07 23:28-23:31 EDT. Gate READY (25.1 h continuous,
      299 tagged stamps, largest gap 5.1 min, 0 breaks). The four pre-registered commands ran exactly as written
      (`--since 2026-09-07T02:22:00Z`, no `--until`), all four ingested: **every verdict is `no-lead`** (Tier 2
      fed-rates corr -0.07 @ +10 min; Tier 2 crypto -0.10 @ -35; Tier 2b identical to Tier 2). Run 1's Tier 2b
      crypto `polymarket-leads` did NOT replicate on the clean window. Regime page: 9 history rows, each
      tier/scope at runs: 2, consensus still `insufficient-history` until run 3. Measured span ran to
      03:27:28Z (25.1 h, executed 66 min after the gate hour). Run 2 COMMITTED 2026-09-08 (f72f1cb), and its
      25.1 h span STANDS per ruling R124-1.B (>= 24 h bar met; no re-run).
- [x] ~~**Collector incident 09-08/09**~~ RESOLVED 2026-09-09 14:26 EDT (Round 125, you authorised "deploy the
      hardening" via Antigravity's R125-1.B). The collector had been dead-alive since 09-08 12:01 EDT (26.4 h,
      `FOREIGN KEY constraint failed` every 10 s: `USELESS` and `para:TREAD` listed, not in `assets`). Hardening
      `70bd232` merged (`d3df1cb`, 8/8 tests), collector stopped and relaunched (supervisor 16844, collector 74972),
      assets 442 -> 444, first new snapshot 18:26:39Z. Gap #2 registered and compiled
      (`wiki/events/data_gap_2026-09-08_hl_asset_snapshots_2.md`, 26.42 h). The readiness gate now checks the price
      stream too (R125-1.C), so this exact failure can no longer be declared READY.
- [x] ~~**Run 3 of 3 (Tue 09-08 ~23:27 EDT)**~~ **VOID** per R125-1.A (executed late at 14:02 EDT 09-09; all four
      `no-lead`, but 26 h of the 38.5 h window had no BTC prices). Artifacts discarded, never ingested. Re-bound below.
- [x] ~~**Keep the laptop awake and collecting through ~15:30 EDT Thu 09-10**~~ **RUN 3 DONE 2026-09-10 15:58-16:05
      EDT**: gate READY on both bars (24.4 h, 291 stamps, 0 breaks; 8,391 price points, 0 holes); four verdicts all
      **no-lead** (fed-rates corr +0.08 @ +13 min; crypto -0.07 @ +7; Tier 2b identical); ingested; regime page:
      T2 fed-rates, T2 crypto, T2b fed-rates = no-lead 3/3; T2b crypto = `mixed` (run 1's hole-corrupted reading is
      still in the history; Antigravity to rule). ITEM 18 PHASE 1 CLOSED. **You may shut the laptop down after this
      commit**; wake it Friday morning, run `resume_all.bat`, tell me. Original re-bind block kept for the record:
      `--since 2026-09-09T19:27:39Z`. Why not the restart instant itself (18:26:39Z, R125-1.A's literal words): the
      run seeks prices from `since` minus `max_lag + 1` = 61 min, so a window bound at the first new snapshot pads
      61 min back into the hole, and the hardened gate (R125-1.C, 0 price holes > 60 min inside the sought window)
      would refuse it forever - verified live at 14:32 EDT ("1 hole 61 min: 17:25:39Z -> 18:26:39Z"). Binding 61 min
      after the first new snapshot makes the sought window start exactly where prices resume. Antigravity to ratify.
      RATIFIED by Antigravity (R125-2.A, 16:00 EDT) and re-verified live at 16:30 (price stream ready, 0 holes,
      window start aligned to the first new snapshot). The gate's own ETA is **2026-09-10T19:31:09Z = ~15:31 EDT
      Thu 09-10** (the first stamp inside the window landed at 19:31:09Z and the 24 h span clock runs from it).
      UNBROKEN collection until then (both daemons: the gate refuses on either stream). The run is mine
      (**ping me ~15:35 EDT**, or paste the block below):
      1. Gate (must say READY - both bars):
         `python -m cross_market.lead_lag --check-data --family macro --subfamily-from tags --since 2026-09-09T19:27:39Z`
      2. The four runs (`_run3.json`, `--since 2026-09-09T19:27:39Z`):
         `python -m cross_market.lead_lag --coin BTC --family macro --subfamily fed-rates --since 2026-09-09T19:27:39Z --json > cross_market/experiments/lead_lag_tier2_fed-rates_verdict_run3.json`
         `python -m cross_market.lead_lag --coin BTC --family macro --subfamily crypto --latency-minutes 5 --since 2026-09-09T19:27:39Z --json > cross_market/experiments/lead_lag_tier2_crypto_verdict_run3.json`
         `python -m cross_market.lead_lag --coin BTC --family macro --subfamily fed-rates --subfamily-from tags --since 2026-09-09T19:27:39Z --json > cross_market/experiments/lead_lag_tier2b_fed-rates_verdict_run3.json`
         `python -m cross_market.lead_lag --coin BTC --family macro --subfamily crypto --subfamily-from tags --latency-minutes 5 --since 2026-09-09T19:27:39Z --json > cross_market/experiments/lead_lag_tier2b_crypto_verdict_run3.json`
      3. Ingest each with its tier (`--tier 2` / `--tier 2b`), e.g.
         `python -m knowledge.ingest.lead_lag --result cross_market/experiments/lead_lag_tier2_fed-rates_verdict_run3.json --tier 2`
      Run 3 completes the 3-run `regime_consensus_3` on every tier/scope (only Tier 2b crypto is still open).
- [x] ~~**Now -> Fri 09-11: Round 126**~~ DONE Thu 09-10 evening, a day early: Item 18 Phase 2 is pre-registered
      (`cross_market/experiments/lead_lag_phase2_fomc.meta.json`, compiled to the vault), the engine
      (`python -m cross_market.event_study`) and the vault adapter (`knowledge.ingest.event_study`) are built and
      tested, and the whole thing is committed. Nothing for you Friday. **The laptop can be off tonight and Friday.**
- [x] ~~**Wed 09-16, ~14:06 EDT, one extra step after the recorder stops**~~ DONE 14:46, ingested. (added to the drill list below): the Phase 2
      run is mine - say "event study" once the survival curve and CLOB ingest are done, or paste:
      `python -m cross_market.event_study --event fomc_2026-09-16 --json > cross_market/experiments/event_study_fomc_2026-09-16.json`
      then `python -m knowledge.ingest.event_study --result cross_market/experiments/event_study_fomc_2026-09-16.json`.
      It refuses before 14:05 EDT by design; a HOLD that moves neither venue is `uninformative-shock` and is simply logged.

### Mon 09-08 or Tue 09-09 — recommended deploy window for the collector hardening (~5 min, my hands)
- [x] ~~Say "deploy the hardening"~~ DEPLOYED Wed 09-09 14:26 EDT (Round 125, R125-1.B). Soak: 7 days before the
      09-16 print; rollback window 09-10 to 09-15 (`git revert d3df1cb` + restart). Never change the collector
      inside 48 h of the print.
- [ ] **Watch for 24 h**: `collector_service.jsonl` now carries `silent_failure_watchdog` events from the hardened
      supervisor; one `coverage_report` with `coverage_pct` near 100 by Thu morning is the all-clear.
- [x] ~~Exporter loop onto the two-stream gate~~ DONE 16:06 EDT (R125-2.B): `cross_market.interfaces.obsidian_exporter`
      restarted as pid 64692. Its Obsidian card (Cross_Market_Titans.md) and `--status` now show the price stream
      too, and its automatic lead-lag run stays gated while the continuous stamp series still spans the 09-08 hole
      - expected; the runs that matter are the hand-bound ones above. One-line check any time:
      `python -m cross_market.interfaces.obsidian_exporter --status` (both streams named in the verdict).
      Note for run 3's gate: on a live window the WATCHER must also be fresh (newest stamp <= 15 min), so a sleeping
      laptop now fails the gate on either daemon.
- [x] ~~Keep the laptop awake through ~23:30 on 09-08~~ superseded: run 3 re-bound, closes ~15:27 EDT Thu 09-10 (above).

### Any day 09-07 to 09-14 — scheduler probe (~3 min, logged in)
- [x] `powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1`
      DONE 2026-09-07 01:05 EDT — **PROBE OK**, last result 0, 60/60 stamps into scratch, task self-removed.
      The scheduler → tracked batch → recorder chain fires correctly on this machine. Re-run only if the
      machine or the drill files change before the 16th.

### Every day until 09-16 — two 10-second checks
- [x] ~~**RESTART THE CROSS-MARKET EXPORTER BEFORE YOUR NEXT REHEARSAL (found 2026-09-14 19:43 EDT).**~~ **DONE 2026-09-14 20:39 EDT** (PID 64920, single instance, first cycle logged 20:41:07; the `exporter stream` check is back under its 5-minute limit). Still re-run the rehearsal Wednesday morning as the backstop. It died at 06:28 EDT today
      (a one-off race: a Polymarket drop file was pruned while the exporter was listing the folder). Nothing has
      restarted it. `fomc_rehearsal --online` has an `exporter stream` check with a 5-minute limit, so **that check
      FAILS today and will FAIL on Wednesday morning** until you run this once (it checks first and never double-launches):
      `start_cross_market_exporter.bat`
      Then re-run `python -m knowledge.drills.fomc_rehearsal --online` and confirm `exporter stream` reads PASS.
      Rough re-crash risk before the drill: about one in five (one crash in ~8 days of logs, so a very rough estimate).
      Your Wednesday-morning rehearsal is the backstop: if `exporter stream` FAILs again, run the .bat again.

- [x] ~~`python -m knowledge.drills.fomc_rehearsal --online`~~ **DONE 2026-09-15 12:31 EDT** (33 checks: 0 FAIL, 1 WARN; exporter stream PASSED at 0.0 min; clock offset +0.199s within limit).
- [x] ~~The collector one-liner under ROUND 119 in `COMMANDS.txt`~~ **DONE 2026-09-15 11:54 EDT** (0.1 min since last snapshot).

### Sun 09-13 or Mon 09-14 — live dress rehearsal (~2 min)
- [x] ~~`python -m knowledge.drills.fomc_live_rehearsal`  (60 s of real books into scratch; nothing real written).
      Expect: 180/180 stamps, one curve, two deferrals for a hold. Send me any FAIL line.~~ Ran 09-15 12:29 EDT (scratch
      `20260915T162924Z`, never ticked) and again 09-16 12:14 EDT: 21 checks 0 FAIL 0 WARN, 180/180, two deferrals.

### Tue 09-15 — Q3 estimated tax (deadline; not a trading task)
- [x] ~~`python -m Tax_Reserve_Agent.main calendar` for the amount, then pay it. Penalty accrues from this date.~~
      **NOTHING OWED. $0.00. Checked 2026-09-16 14:56 EDT by Claude Code.** Q1, Q2 and Q3 all CLOSED at $0.00;
      2026 realised gains are $0.00; escrow holds $0.00; PAST DUE / PAYABLE NOW = **$0.00**. There is no payment
      and no penalty. This item shouted "DEADLINE TOMORROW, penalty accrues" for a week over a bill that does not
      exist. **Caveat worth one minute of your time:** the agent taxes *realised* gains only. If you closed a
      position anywhere it does not track, the $0.00 is wrong and the deadline was real - you would know, not it.
      Next deadline Q4, 2027-01-15, currently IN_PROGRESS at $0.00.

### Wed 09-16 — FOMC drill day, minute by minute
- [x] ~~**Morning (any time before 12:00):** `fomc_rehearsal --online`, then `fomc_live_rehearsal`. Both clean, or call me.~~
      DONE by Claude Code 12:06-12:16 EDT. First `--online` pass: **1 FAIL** (exporter dead since 03:55, 490 min stale).
      You authorised the restart; exporter process started 12:12:31 (launcher ran ~12:11:57), PID 4552, lock taken, verified cycling at 12:13:27.
      Re-run: **33 checks, 0 FAIL, 1 WARN** (the accepted Interactive logon-type WARN). `fomc_live_rehearsal`:
      **21 checks, 0 FAIL, 0 WARN** - 60 polls, 180/180 stamps, 0 failures, 0 rate-limits, largest per-token gap
      1.002 s against a 3 s bar; real vault, real books dir and repo-root event.json all verified untouched.
- [x] ~~**13:30** - laptop ON, LOGGED IN, lid open, sleep disabled, VPN in whatever state it will stay in for the hour.~~
      **VERIFIED 13:30:44 EDT by Claude Code, all read-only, all green:** exporter RUNNING pid 4552; collector 0.3 min;
      AC at 99%; console session `ixis1` Active since 09-13 14:46; no recorder running; task Ready; AC idle-sleep = never.
      One correction to Section 84's record: **DC idle-sleep is 600 s (10 min), NOT never** - keep the cord in.
      Task fires at **13:58:00** (COM engine object, schtasks and the XML all agree; only the CIM API says 13:58:58 and
      that is the API the rehearsal reads - see AGENTS.md S91 ruling). **Hands off everything from 13:57:30 to 14:05:30.**
      Exporter: **already restarted 12:12 EDT** (see above), so this is now a VERIFY, not a fix. Run
      `start_cross_market_exporter.bat` anyway - it is guarded (exit 3 only) and will say `already running - kept`.
      If it instead says STOPPED, it crashed again: relaunch and carry on, it is not on the measurement path
      (`latency_sniper`, `event_study`, `ingest.clob`, `ingest.event_study` contain zero references to it).
      DEFECT-EXP-001 is now DAILY, not weekly - 3 crashes in the log (09-14 06:28, 09-14 21:20, 09-16 03:55) and the
      09-14 21:20 one died 41 min after your 20:39 restart. Prune is keyed to the filename stamp + 192 h, so today's
      crash windows are computable: drops stamped 09-08T17:50:51Z / 17:55:54Z / **18:00:58Z** age out at 13:50:51 /
      13:55:54 / **14:00:58 EDT** - the last one is 58 s after the print, inside the recording window. ~1% per event
      and harmless to the data, but if the vault cards freeze mid-drill, that is why. Do NOT patch it today.
- [x] ~~**13:55**~~ DONE 13:30:44 (0.3 min, GREEN) _(RATIFIED 09-14 by Antigravity R128 / Section 85)_
      collector liveness, 10 seconds, read-only. The morning rehearsal allows the collector 15 minutes of silence, but
      the measurement itself is ruled INSUFFICIENT on any feed gap over 5 seconds, so a collector that dies after the
      morning check would pass the rehearsal and still void the drill. Nothing between the morning and 13:58 catches it:
      `python -c "import sqlite3,time;c=sqlite3.connect('file:HyperLiquid/HL_Monarch/data/hyperliquid_data.db?mode=ro',uri=True);print(round((time.time()*1000-c.execute('SELECT MAX(timestamp) FROM asset_snapshots').fetchone()[0])/60000,1),'min since last snapshot')"`
      Under ~0.5 min: fine, carry on. Over ~1 min: the collector is stalled - call me before 13:58 rather than after.

- [x] ~~**13:56**~~ card printed at 14:10 (post-print form). `python -m knowledge.query --drill-card fomc-2026-09-16`  (read-only; countdown + the paste-ready commands).
- [x] ~~**13:58** - the scheduled task fires by itself and records for 420 s (until 14:05). Touch nothing.~~ FIRED 13:58:00.80, exit 0 at 14:05:02.48. 419 polls, 1257 stamps, 0 failures, 0 rate-limits.
- [x] ~~**14:00** - the statement prints. READ the rate decision yourself, then:~~ HIKE +25 bps to 3.75-4.00%. event.json written 14:06 as 0 (wrong), corrected 14:10 with --force, then re-anchored to 18:00:00Z - see the anchor incident in AGENTS.md.
      `python -m knowledge.drills.event_json --bps <n>`   (0 = hold, 25 = quarter-point hike, -25 = cut).
      Wrong number? `--force` overwrites. Nothing automated may decide this.
- [x] ~~**14:06 (after the recorder stops)** - the survival curve, then `knowledge.ingest.clob`.~~ DONE (twice - the first curve was anchored late and measured nothing). Final: baseline 87,221 notional at T-0.062 s, first change +0.939 s, half +1.939 s, 90% gone +5.942 s.
      Your p = 0.90 "no change" forecast scores itself once the event and the books are in the vault.
- [x] ~~**14:08** - the Phase 2 event study (Round 126).~~ DONE. Verdict **uninformative-shock**, informative false, lead_s null: Polymarket displaced (0.875 -> 0.975) but BTC moved 6.47 bps against a 17.43 bps bar. Panel: insufficient, 0 of 3 informative. Original line kept: paste the two commands from the
      "Wed 09-16, ~14:06" line above. It writes one Reaction Profile page per Fed market and the Phase 2 panel.
- [x] ~~**Afterwards** - tell me it ran.~~ Reported, audited, committed (067fdf7).

- [ ] **14:05-14:30 - save the statement text (1 min).** Copy the Fed press release (federalreserve.gov, the 14:00
      statement) into `obsidian_vault/raw/inbox/fomc_statement_2026-09-16.md`. The inbox is lint-exempt. It is the input
      for the statement-tone descriptor, which is NOT in Friday's registration (ruled 09-10): scored exploratory for
      09-16 under a rule locked before 10-28.

### If 09-16 is missed
- Next FOMC: 2026-10-27/28. Everything stays armed; the registration would need re-dating and fresh token ids.

### No date — whenever you are ready
- [ ] **Answer the 4 questions at the bottom of `DEV\ARB_LAUNCH_PLAN.md` (~10 min to read; written 09-14):** the
      crypto arbitrage audit found none of the three projects ready for money. Plan proposes: HL basis harvester
      goes to live in 7 phases (transport + fill handling are the missing pieces; ~8-10 rounds of work, 6-8 weeks
      calendar because of testnet and pilot windows); Funding_Arbitrage_Agent retired (fakes fills even in live
      mode, Binance leg unusable from NJ); Base DEX agent parked behind one 24 h spread measurement. Phase 7
      (mainnet pilot, $200-500/leg) is the first step that costs real money and needs your explicit go-ahead.
      Phases 1-2 are new files only and could start before the drill if you say so.
- [ ] **Decide whether to merge the backtester slippage fix (~10 min to read, after Wed 09-16; found 09-13):** the
      shared backtester never charged slippage (the two fills were shifted the same way and cancelled out), since
      2026-08-18. Antigravity ruled it DEFECT-ENG-001 and ordered a fix branch; it is built and tested on
      `quant_trading_lab` branch `bugfix/engine-slippage-signs` (worktree `qtl_slipfix`), NOT merged. Read
      `qtl_slipfix\backtesters\DEFECT_ENG_001_SLIPPAGE_AUDIT.md`: every futures stack loses $2-$20 a contract per
      trade (no profit factor crosses 1.0; the Core 3 portfolio baseline goes 8,636 -> 8,112 net), crypto moves by
      cents. If the numbers are acceptable, say "merge the slippage fix" and I merge it into lab master; nothing
      that runs before the drill uses the backtester, so waiting until after 09-16 costs nothing.
- [ ] **After Wed 09-16, two more go-aheads (1 min each; ruled by Antigravity Section 57 on 09-13):** (a) "fix the
      collector" - it has been silently dropping ~1 % of Hyperliquid trades and every liquidation event in those
      batches since 09-11 whenever its 7-minute database clean-up holds the lock too long (registered as an OPEN data
      gap); the fix is designed and waits only for the drill freeze to lift, then a collector restart. (b) "start the
      t0030 paper runner" - Campaign 5 is parked and t0030 is the champion; its forward paper-trading runner
      (STACK_10) is deferred until after the drill so no new always-on process joins the machine this week.
- [ ] **After Wed 09-16 — fix DEFECT-EXP-001 (exporter drop-prune race, ~2 min, you/Claude):**
      The cross-market exporter crashes with `FileNotFoundError` whenever `polymarket_fetcher.prune_stamped_drops` deletes
      drops older than 192h while `load_questions` is sorting the directory with `p.stat().st_mtime` (`obsidian_exporter.py:77`).
      Fix: add `_safe_mtime(p)` returning -1.0 on `OSError` to the sort key at line 77. Audit confirmed `lead_lag.py:140` and
      `titan_correlator.py:195` do not call `.stat()` in their sorts and are safe. Queued behind FOMC event study and DEFECT-COL-001.
      **Addendum 09-16 12:30 (Claude Code, from the "why does it keep crashing" read):** the 2-line `_safe_mtime` patch stops
      the death but not the disease. Measured: the drop dir is **5.4 GB in 3,857 files** (1,928 sports up to 4.9 MB each,
      1,927 macro ~250 KB) and `load_questions` reads and JSON-parses ALL of it EVERY cycle to keep one row per market -
      that is why the loop runs at ~54 s against `--interval 15` (40 s of parsing + 15 s sleep; 60-70 s cold after a
      restart) and why the stat pass is wide enough to lose the race ~0.4% of the time per prune (~288 prunes/day =
      ~1 crash/day; a restart does not reset the odds - 41 min (pid 64920) and ~15.5 h (pid 51256, your 09-15 12:28 restart
      before the 12:31 daily check) were both fair draws). Retention filled on
      09-14 06:26 EDT, so the bug was latent from Round 52 and went live at the first-ever deletion. Three fixes, in
      order of value: (a) `_safe_mtime` as above (stops the crash); (b) sort by the filename stamp, which `prune`'s own
      docstring already says is the honest ordering, and read only the newest drop per family, which is what the loop
      actually needs - takes the cycle from ~54 s to ~15 s and shrinks the race window to nothing; (c) the loop at
      `obsidian_exporter.py:672` catches only KeyboardInterrupt and has no supervisor (the collector has
      `run_collector_service.py`; the exporter has only a PID lock) - fold it into the post-drill guarded restart tool.
- [ ] **After Wed 09-16 drill — migrate MoonDev TradingView MCP into `DEV` (~5 min, you/Claude):**
      The TradingView MCP project (`tradingview_mcp`) was built in an isolated sandbox at
      `C:\Users\ixis1\Desktop\tradingview_mcp` to strictly protect the pre-drill freeze and keep active daemons
      untouched. Once the Wednesday 14:00 EDT FOMC print and Phase 2 event study conclude:
      (1) Move or clone `C:\Users\ixis1\Desktop\tradingview_mcp` into `C:\Users\ixis1\Desktop\DEV\tradingview_mcp\`
      (or alongside `MoonDev_Quant_Strats\`).
      (2) Ensure its virtual environment (`venv/`), `.env`, and Chrome profile cache (`.tradingview_mcp_chrome/`)
      are gitignored under DEV root `.gitignore`.
      (3) Update Claude Desktop / Claude Code MCP config `cwd` to the new DEV path.
- [ ] **Before any git remote (~5 min, you; found 09-10 02:20 EDT, re-verified 09-12):** TWO tracked files carry a
      credential: `BOTS/Phemex/Phem_key.py` (a 36-char key AND a 91-char secret, in the 09-03 root commit; nothing
      imports it). Tell me whether it is live. If live: rotate it at Phemex first, then I blank the file (like
      dontshare.py, or delete it - nothing imports it) and add `*_key.py` to .gitignore (blocks NEW key files; NOT
      `key_file.py`: an ignore does not untrack a tracked file, and untracking it breaks the five importers on a clone). `BOTS/HYPERLIQUID/key_file.py`
      is a 40-hex wallet ADDRESS (public, five bot scripts import it) - nothing to rotate; say if you would rather not
      publish the address. `BOTS/Aster/aster_key.py` is empty. History is NOT rewritten (both files are in the root
      commit, so a rewrite would change all 171 hashes; the vault's L5 and this file cite them). No push happens until
      you say so explicitly - a push publishes the whole history. Also needs `gh` installed and `gh auth login`.
- [ ] **Second tracked credential, found 2026-09-12 during the Polymarket launch-readiness audit (~5 min, you):**
      `Polymarket/Polymarket_Moondev/poly_whale_monitor.py:38` and `poly_traders_tracker.py:40` each hard-code a
      Moon Dev API key as the `os.getenv("MOONDEV_API_KEY", ...)` FALLBACK, so the key ships in the source even
      though `.env` itself is correctly gitignored (`.gitignore:10 *.env`). It has been tracked since the root-era
      commit `743496b`, so history is not rewritten here either. Tell me whether that Moon Dev subscription is
      still active. If yes: rotate it at Moon Dev first, then I replace both fallbacks with `""` and make the
      modules fail loudly when the env var is unset. If the subscription is dead, say so and I strip the fallback
      anyway. This blocks a git remote for the same reason Phem_key.py does.
- [ ] **Phase 2 event 2 is the September CPI: Wed 2026-10-14 08:30 EDT** (BLS schedule, verified 09-10; the next two
      are 11-10 and 12-10). Polymarket lists `Core CPI MoM / YoY - <month>` ladders a few weeks ahead under tags
      inflation/cpi/economy (not in the watcher's set); September's are not listed yet. The recorder, its scheduled
      task and the token ids are registered AFTER 09-16 and before 10-12. That Wednesday: laptop on and logged in by
      08:26.
- [x] ~~**APPROVED by Antigravity 02:40 EDT - Fri 09-11 08:28:00 EDT sharp (~8 min, you): August CPI scratch probe.**~~
      MISSED (noted 12:55 EDT): the laptop was asleep 01:43-12:21 EDT (gap registered in commit 869e092), no probe
      directory exists. Its own rule applies: missed 08:28 means skip, never run late. Exploratory only, no panel impact.
      Laptop awake and logged in by 08:25. In a terminal at the DEV root, at 08:28:00 (T-120 s; BLS prints 08:30:00),
      paste ONE line:
      `C:\Users\ixis1\anaconda\python.exe -m cross_market.latency_sniper --record-loop --tokens 62389524085487534523899712332044572176886590958623969587529644299844470210078,64368830477432477582522534288767253727710406730994687443511307805252003060742,94845965611974215936878491977753293595100306803782909168044786416574901031933 --interval 1 --duration 420 --books cross_market\data\clob_books\cpi_2026-09-11_probe`
      The three tokens are the YES sides of `Core CPI MoM - August 2026` rungs 0.2% (priced 0.645 tonight), 0.3%
      (0.29) and 0.1% (0.055) - the rungs carrying the probability mass, so the ones that reprice. Same recorder,
      same python and same shape as the FOMC drill batch; 3 read-only GETs per second; the books dir is created and is
      git-ignored; the HL leg needs nothing (the collector's trades table runs regardless). Exploratory only: not a
      panel entry, no code, no scheduled task, no daemon. It ends by itself at 08:35. If you miss 08:28, skip it -
      do not start it late.
- [x] ~~**Name the aim of the next project**~~ DONE 2026-09-12 23:00 EDT: **"find a second strategy family for
      the autoresearch loop."** The reading intake is built around that sentence (see the next item).
- [ ] **Drop links for the second strategy family search (no deadline, ~1 min per link, no money).** Open
      `obsidian_vault/raw/inbox/READING.md` and add one line per source under `## Links`: the URL, then
      ` — ` and a short note. YouTube videos, articles, arXiv papers, GitHub repos and PDFs are all read
      automatically. A page behind a login can be saved as its own `.md` file in that folder instead.
      **Then tell Claude Code: "fetch and review the reading inbox."** It downloads each new link once,
      reads it, and gives it a verdict: *candidate*, *needs-harness-change* (a real idea the test harness
      cannot run yet, usually because it needs data beyond price bars), *reject*, or *not-a-strategy*.
      The shortlist is the vault page `wiki/concepts/strategy_family_search.md`.
      **What makes a source useful:** a mechanism that is NOT a channel/trend breakout (that is family 1,
      the champion), works on hourly or slower crypto bars, and holds trades long enough to earn more than
      ~40 basis points per trade before fees. Short-timeframe scalping ideas will be rejected on cost alone.
      **If you skip this:** nothing breaks; the search page just stays empty.
      **Also (~1 min): paste `HANDOFF_PROMPT.md` into Antigravity.** It has to approve the one new module
      that downloads from the internet, and it is asked which three strategy families to look for first -
      worth reading its answer before you spend an evening collecting links.
- [ ] **Strategy autoresearch loop - ALL PHASES RUN. THE ANSWER IS NO, AND THAT IS THE RIGHT ANSWER
      (updated 2026-09-11 16:20 EDT).** The loop ran its full 40-trial budget in about two hours and found one
      strategy good enough to keep. Then the final test - three months of data it was never allowed to see -
      **failed it**. On data it could see, the strategy made $1.28 for every $1.00 lost. On the unseen months,
      $0.75 and $0.97. So it does not go to paper trading and nothing goes live.
      **Why that is a success, not a waste.** The whole point of the fences was to stop a losing strategy from
      looking like a winner. The loop produced a candidate that passed all twelve quality checks, and the one
      test it could not reach still caught it. The YouTube versions have no such test and would have reported
      the good number as a discovery. You now know this strategy family does not work, which is worth more than
      a backtest claiming it does.
      **Cost:** about two hours of usage, no money. **Gained:** 40 documented experiments, and several findings
      that make the next campaign better - chief among them that the parameter the optimiser kept choosing was
      actively harmful, while the value that worked was one it never picked.
      Nothing is committed to the lab's main branch; your other agent's work is untouched. Left for you:
      (a) **Send the cross-check to Antigravity.** It has never replied to any of this - three requests now
          outstanding. The prompt is in `HANDOFF_PROMPT.md`. There is also a genuine bug in one of my quality
          gates needing its ruling: it divides by a number that can approach zero.
      (b) **Decide whether to run a campaign 3** on a different strategy family. The harness is built, tested
          and now proven; a new campaign costs about two hours and needs only a new candidate file.
      (c) The 5-minute screen is DEFERRED until Antigravity replies - see the next item.
- [ ] **Campaign 3 is BUILT and ready to run - one question is out with Antigravity first
      (2026-09-11 18:57 EDT).** You said proceed, so the whole engine was rebuilt to Antigravity's ruled
      specification: 8 parameters, all implemented, 55 tests passing, the full lab suite green at 243.
      It took 20 minutes against my 50-minute estimate.
      **What changed, in plain terms.** The old engine picked different settings for each time window,
      and campaign 2 proved that was chasing noise - the setting it kept choosing was the one that lost
      money. The new engine picks ONE set of settings for the whole campaign, judged on how consistently
      they work across every window rather than how well they score on any single one. There is also now
      a cheap pre-test that refuses to start a campaign at all unless the strategy earns more per trade
      than it pays in fees, which would have saved us the 5-minute detour entirely.
      **It works.** The pre-test passes at 42 and 36 basis points against a 15 bar. A trial run scores
      1.38 and passes all twelve quality checks in 23 seconds, better than campaign 2's best.
      **Why I have not started it.** One number in Antigravity's formula behaves oddly on real data: the
      variance term is about twice the size of the return term, so the engine is effectively choosing
      the most *consistent* settings rather than the most *profitable* ones. That may be deliberate, but
      it is not what the formula looks like it does, and it is Antigravity's pre-registered number - so
      changing it myself is exactly the thing these guardrails exist to stop. The question is in
      `HANDOFF_PROMPT.md`.
      **Your options:** (a) send that prompt, get the number settled, then run; (b) tell me to run
      campaign 3 as-is and treat the variance question as a finding for afterwards. A 40-trial campaign
      is about 40 minutes of compute. No money either way.
- [x] ~~**ONE DECISION: do I apply Antigravity's rulings to the scoring engine? (2026-09-11 17:20 EDT)**
      Antigravity finally replied (commit `4c8c2ef`, 18 rulings). I tested its claims instead of just doing what it
      said, and the results were mixed - so this needs your call rather than mine, because the rulings change the
      scoring engine, which is meant to be fixed and un-editable once a campaign starts.
      **Where it was right:** its main proposal is a new rule that no campaign may start until the strategy is shown
      to earn more per trade than it pays in fees. I checked whether that rule would also have blocked the hourly
      campaign that actually worked. It would not - hourly earns 32 and 21 (BTC/ETH) against a bar of 15, while
      5-minute earns under 1. So the rule cleanly separates the good case from the dead one. Adopt.
      **Where it was wrong:** it flagged one issue as CRITICAL and said it "directly shaped" our failed result. I
      tested it. It changes nothing - the alternative it proposed gives a byte-identical outcome. It also quoted a
      correlation figure of "above 0.85" that measures 0.818.
      **Where it was right but its fix is buggy:** it correctly identified a real bug in one of my quality checks,
      and its replacement formula swaps one divide-by-zero problem for another (it produces a score of 5,000 in the
      degenerate case). I know how to fix that properly.
      **Your call:** say "apply the rulings" and I will implement the sound ones with my corrections, which resets
      the harness for a campaign 3. Say "leave it" and everything stays exactly as it is. Roughly 30 minutes either
      way, no money involved.
- [x] ~~**The 5-minute gross-edge screen**~~ DONE 2026-09-11 17:10 EDT, and **5-minute is dead by measurement**.
      Eight runs, four strategy families across two assets, 359,000 bars. Every one failed. The best earned 0.71
      basis points per trade before fees against a 10 basis point cost - fourteen times short - and five of eight
      lost money even before fees. These are in-sample numbers, which flatter everything, so nothing here can be
      rescued. For contrast the same strategy on hourly bars earns 32 and 21 basis points. The timeframe was the
      entire problem. Took ~20 minutes, not the 5 I first quoted.
- [x] ~~**The 5-minute gross-edge screen - WAITING ON ANTIGRAVITY (parked 2026-09-11 16:55 EDT).**~~
      **What it is:** one cheap test that answers "is 5-minute data worth a campaign at all?" without
      running one. It measures how much each candidate signal earns per trade BEFORE fees, and compares
      that against the 10 basis points of fees and slippage the desk actually pays. If nothing clears the
      bar even before costs, 5-minute is settled dead and we never spend two hours proving it.
      **WHEN TO RUN IT:** after Antigravity answers the cross-check, and only if its reply does NOT
      already rule 5-minute out (points 11 and 12 in the prompt ask it directly about maker pricing and
      re-scoping). If Antigravity says drop the family, skip the screen - it would be answering a closed
      question. If it says the timeframe is worth revisiting, run the screen FIRST, before any campaign.
      **Cost:** it is slower than I estimated. I started it and killed it after 12 minutes with no output;
      5-minute data is 385,000 bars per asset and one of the four signal families is expensive per bar.
      Budget 20-30 minutes and expect it to need a faster implementation, not the 5 I originally quoted.
      **Where it is:** the script is parked at
      `qtl_holdout/research/autoresearch/gross_edge_screen.py`, uncommitted. Just say "run the 5-minute
      screen" and I will optimise it first so it finishes in a sensible time.
- [x] ~~**Strategy autoresearch loop - PHASES 0, 1, 2 DONE. ONE DECISION NEEDED BEFORE ANY OVERNIGHT RUN
      (updated 2026-09-11 13:50 EDT).** Phase 2 ran five supervised trials and found something that stops Phase 3:
      **the 5-minute timeframe cannot pay its own trading costs.** At 5m the strategy makes ~7,000 trades and pays
      $281,916 in fees and slippage against a gross edge of roughly zero - fees are 15x the edge. At 1 HOUR the same
      strategy makes 552 trades, the gross edge turns positive, and fees are only 1.4x it. No amount of overnight
      searching fixes a cost problem that big; the loop would fail for five nights for a reason unrelated to the
      ideas it tries. **Your call (a 2-line change I have NOT made, because it changes what you accepted):**
      switch campaign 1 to the 1-hour data (already downloaded), which also means dropping the "100 trades minimum"
      gate since 1h produces about a tenth the trades. The alternative is to keep 5m but assume limit orders
      instead of market orders, which changes the backtest engine's cost model and needs Antigravity's sign-off.
      Also still owed: **Antigravity has not replied on any of this** (Phase 1's 9-point cross-check is in
      `HANDOFF_PROMPT.md`), and the blueprint says that cross-check comes before any overnight run.
      Trials so far are in `../qtl_autoresearch` (a separate copy of the lab on branch
      `autoresearch/c1_donchian_crypto_5m`); read `research/autoresearch/ledger.tsv` there.
- [x] ~~**Strategy autoresearch loop - Phases 0 AND 1 DONE, Phase 2 needs you (added 2026-09-11 ~01:15 EDT, updated
      13:30 EDT).**~~ Superseded by the line above; kept for the file layout it describes. The plan is `AUTORESEARCH_BLUEPRINT.md` at the DEV root (read s.0, s.2 and the Phase 1
      "Executed" block; 10 min). Built and verified so far: 44 months of BTC + ETH 5m and 1h from Binance's free
      archive (100 % coverage, 0 holes), and the full loop harness - one editable candidate file, walk-forward
      out-of-sample scoring with 7 gates, a locked holdout the loop cannot reach, a 40-trial nightly cap, an
      append-only ledger. 63 new tests, lab suite 243 green. Proven end to end on real data: the naive baseline
      strategy was correctly DISCARDED (loses in all 8 folds) and also FAILED the holdout, and all five fences
      refused live attempts to peek at data, hard-code a price level, edit the engine, skip the hypothesis and
      leave a stray file. Nothing is committed. Left for you:
      (a) **Send the Phase 1 cross-check to Antigravity** (the prompt is in `HANDOFF_PROMPT.md`, and s.8 of the
          blueprint now carries 9 questions - 4 new ones about design choices I made and want challenged).
      (b) **Accept or change the gate bars and the 5 % keep delta** in blueprint s.2.3. These decide what counts
          as an improvement worth keeping; they are my numbers, not yours, until you say so.
      (c) Then say "go Phase 2" (ratify the campaign + 5 supervised trials with you watching, ~20 min).
      (d) BEFORE any overnight `/loop` run (Phase 3, still not now): check whether usage overage billing is ON for
          the Claude account - an overnight loop stays inside the subscription only if it is off or you accept the
          cost. At 3 minutes per trial, a 40-trial night is about 2 hours of continuous use.
      No money is needed for Phases 0-2 (the Binance archive is free). TradingView Desktop / MCP is NOT required;
      it is a later, optional paid-plan and terms-of-use decision for the parity step only.
      ⚠ **Committing caveat:** `quant_trading_lab/config/portfolio_config.yaml` now contains BOTH my STACK_9 block
      and the other agent's uncommitted work (a retail_3k tier, two new correlation groups). Staging that one file
      stages their changes too. Every other file of mine is exclusively mine.

---

## 🔴 DATED — these have real deadlines

### 2026-09-15 (Tue) — Q3 estimated tax payment
- Run `python -m Tax_Reserve_Agent.main calendar` for the amount and the escrow release.
- The quarters are not quarters: Q3 covers Jun 1 – Aug 31 (3 months), due Sep 15.
- Registered in the vault as `wiki/events/tax_estimated_2026_q3.md`.
- **If missed:** an underpayment penalty accrues from the deadline, not from April.

### 2026-09-16 (Wed) 13:58 EDT — FOMC drill. THE BIG ONE.
- **Morning of the 16th, first:** `python -m knowledge.drills.fomc_rehearsal --online` (33 checks incl. a
  live fetch of each token and the four daemons' streams) and `python -m knowledge.drills.fomc_live_rehearsal`
  (60 s, scratch only). At T-2: `python -m knowledge.query --drill-card fomc-2026-09-16`.
- **At 14:00, after you read the statement:** `python -m knowledge.drills.event_json --bps <number>`
  (0 for a hold, 25 for a quarter-point hike, -25 for a cut). It writes `./event.json` correctly from that one
  number and refuses to overwrite a wrong one unless you add `--force`. Then the survival curve, per the card.
  It prints the countdown, the rules with their FULL token ids, your standing forecast and
  the exact post-print commands ready to paste, in under 60 lines. It writes nothing, so it
  is safe to run inside the window as often as you like.
- **Laptop ON and LOGGED IN at 13:58 EDT.** The task `Monarch_FOMC_Drill` fires
  at T-2 min and records 420 seconds of order-book depth on three Fed markets.
  It cannot run on a sleeping or logged-out machine.
- **Power:** the battery flags were cleared on your word (Round 121), so the drill starts and keeps recording
  on battery. Plugged in is still better; it is no longer required.
- **At 14:00 the statement prints. A HUMAN must read the actual rate decision**
  and write `event.json`:
  `{"kind":"fed_rate","payload":{"change_bps":<int from the statement>},`
  `"source":"federalreserve.gov statement","confidence":0.995,"observed_at":"<ISO>"}`
  Nothing automated is permitted to decide what the Fed said (confidence ≥ 0.99
  only from the statement itself).
- Then: survival curve → `knowledge.ingest.clob` → the Reaction Profile pages.
- **You have a forecast riding on this**: recorded 2026-09-06T00:37Z in
  `journal/2026-09-06.md` — *no change in rates, p = 0.90*. It scores itself
  against the event payload once the drill data lands.
- **If missed:** the next FOMC is Oct 27-28. Ten weeks of pipeline work sits idle
  until then, and the forecast never scores.

---

## 🟠 BLOCKING — nothing is blocking right now

- [x] ~~**Send the Round 121/122/123 handoffs to Antigravity.**~~ All sent and answered.
- [x] ~~**Run the scheduler probe.**~~ PROBE OK 2026-09-07 01:05 EDT (60/60 stamps; scheduler → batch → recorder verified).
- [x] ~~**Start the Windows Time service.**~~ DONE 2026-09-07 01:13 EDT; synced to time.windows.com, startup Automatic.

The only open item is a DECISION, not a blocker: name the deploy window for the collector hardening
(Tue 09-08 or Wed 09-09 evening). Everything else is in the calendar at the top.

---

## 🟡 RECOMMENDED BEFORE 2026-09-16

- [ ] **Run the live dress rehearsal yourself on Sep 13 or 14, and again the morning of
      the 16th**: `python -m knowledge.drills.fomc_live_rehearsal` (60 s of real order
      books into a scratch folder, then the whole post-print path into a scratch copy of
      the vault; nothing real is written). It ran clean on Sep 6 (Round 116). If any line
      says FAIL, send me the output. It also tells you, in advance, that a hold produces
      one curve and two deferrals.
- [x] ~~**Decide on Desk 4's missing packages.**~~ RESOLVED 2026-09-07: you said yes, and it turned out
      nothing needed installing. Desk 4 runs in its OWN venv (`quant_trading_lab/venv`), not the shared
      anaconda env, and that venv already has `uvicorn` (0.52.3), `fastapi` (0.141.1), and
      `hyperliquid-python-sdk` (0.24.0) with all dependencies - the other agent installed them. The four
      formerly-skipped modules (`test_webhook_server`, `test_hyperliquid_adapter`, `test_multivenue_execution`,
      `test_run_paper_trading`) now run and pass (23 tests); the full suite is 180 passed, 0 skipped. I
      installed nothing. Note: run the Desk 4 suite with `venv\Scripts\python.exe -m pytest tests`, not base python.

---

## 🔵 STANDING OPERATIONAL RULES

- **Keep the laptop awake** whenever a 24 h series is accumulating. A gap over
  60 minutes breaks the run and restarts the clock at zero.
- **Shut down cleanly** — normal Windows shutdown, never the power button.
  `hyperliquid_data.db` is 4.9 GB with an open write-ahead log.
- **After any shutdown or reboot, resume with ONE command:** `resume_all.bat` (DEV root).
  Round 123: it now recovers the collector, the watcher, the cross-market exporter, AND the five
  telemetry exporters, each gated on its OWN liveness, so it never double-starts, never forgets the
  collector, and no longer misses dead telemetry behind a live watcher. Prints a full health check.
  The daemons do NOT auto-start on login, so nothing collects until you run this (or ask me to).
  Dashboards only: `python -m knowledge.drills.telemetry_health` (exit 1 if any down; `--ensure` recovers them).
- **Never kill the daemons by hand.** DATA pipeline (unchanged): watcher 17688, cross-market
  exporter 62760, supervisor 24504, collector 60756. TELEMETRY layer: the five per-desk Obsidian
  sync exporters were found DOWN 2026-09-07 02:00 EDT (dashboards stale up to ~2 days: Polymarket
  from 09-04, Sports from 09-05, HyperLiquid/Bot Control/Terminal from 09-06). Relaunched detached
  02:10 EDT, one per desk (HyperLiquid, Polymarket, Sports, Tax, QuantLab+worker); HyperLiquid and
  Polymarket dashboards confirmed refreshing live; the rest write on change. The C2 bot is correctly
  DOWN - no token, no admin allowlist.
- **~~Known gap in `resume_all.bat`~~ FIXED (Round 123).** It no longer uses the watcher as a proxy; each
  component (collector, watcher, cross-market exporter, and the five telemetry exporters) is recovered on
  its own liveness. A watcher-up / telemetry-down state is now caught. Telemetry alone:
  `python -m knowledge.drills.telemetry_health --ensure`.
- **Quick collector health check** (any time): the one-liner under ROUND 119 in COMMANDS.txt
  prints minutes since the last price snapshot; over ~1 means look at `data\collector.log`.
- **Never seed the live tax ledger.** `seed-bankroll` is paper-only.
- **`DEV/HALT.flag`** is the kill switch: create it and every execution engine
  refuses with exit 3. Delete it to resume.

---

## ✅ DONE (kept briefly, then deleted)

- 2026-09-06 23:15 — **Your five Round 121 decisions, executed** ("proceed"): battery flags cleared on
  the drill task (only those two fields changed); the four stale one-off tasks deleted; the four
  engineering items built (stream health in the pre-flight, the event.json writer, the data-gap page
  and lint rule, the basis-window audit - nothing was measured from stale prices); the collector
  hardening staged on branch `feat/collector-hardening` (deploys only at a restart you authorise); the
  lead-lag artifacts moved beside their registrations.

- 2026-09-06 22:25 — **Tier 2b 24 h gate CLOSED** (286 stamps, 24.0 h, largest gap 5.1 min, 0 breaks)
  and, on your "lets do what we can", **the Tier 2 and Tier 2b runs were executed as registered**.
  Tier 2 crypto: no-lead; Tier 2 fed-rates: no-lead; Tier 2b crypto: polymarket-leads; Tier 2b fed-rates: no-lead. The crypto subfamily
  disagrees between tiers and the registration says that disagreement is the finding, not a verdict
  to pick. Four verdict pages and the regime page carry the numbers. Nothing trades on this.

- 2026-09-06 21:04 — **Collector restarted on your word** (Round 119). It had written no price
  snapshot since 11:46 EDT: a coin newly listed on the exchange (`para:CIFR`) had no row in the
  collector's asset table and one bad row failed every 10-second batch for nine hours. Your VPN
  was not involved. The restart re-synced the assets and snapshots resumed within a minute; the
  spread gate from Ruling R104-1 came live with it. The stop script turned out never to have
  killed anything (it now does, and says so).

- 2026-09-06 — **The FOMC drill was rehearsed live, end to end** (Round 116, self-directed).
  60 s of real order books for the three registered markets, 180 of 180 stamps, no gaps;
  a clearly-labelled synthetic event; the survival curve; the Reaction Profile pages -
  all into a scratch folder and a scratch copy of the vault. The real vault, the real
  books folder and ./event.json were untouched, and the pages the drill produces lint clean.

- 2026-09-06 — **Whale-sweeper cascade replay re-run: still INSUFFICIENT** (Round 115). Over the rows
  the engine counts (complete 60-minute forward series) the top coin ZEC is ZEC 20.20% against a 20%
  ceiling. Round 114 had read the sample as ready by counting rows the registration excludes; the
  page now counts the same rows the engine does and says which coin blocks. Item 14 stays gated.
- 2026-09-06 — **Desk 4 builds its risk sentinel from any directory** (Round 115). 73 root-run test
  failures gone; the 2 left are in another agent's uncommitted test file.

- 2026-09-06 — **The drill's batch file is under version control and the task points at it**
  (Round 114). `cross_market/scripts/fomc_drill_2026-09-16.bat`; a fresh clone now has the drill.
  Trigger, battery flags, logon and instance policy verified unchanged by the re-point.
- 2026-09-06 — **Passive fade reopening question answered: INSUFFICIENT** (Round 114). Over the
  registered population (trade_sweep) the top coin is ZEC 26.8% against a 20% ceiling and the
  data span 5.49 days against 7 required, so no verdict is issued; the fade stays retired
  and the page keeps counting. Round 113 had pooled two event sources and called it ready;
  that is corrected on the registration itself.

- 2026-09-06 — **FOMC drill pre-flight built and run** (Round 113). 22 read-only checks
  across the Event page, rules registration, drill card, the batch file the task runs,
  and the scheduled task. Everything agrees: tokens three ways, 13:58:00 local = T-2,
  420 s = the window, python path present, 124.8 GB free, on mains. Two warnings are
  the two open decisions above (battery flags; interactive logon means logged in).
- 2026-09-06 — **fastapi installed for Desk 4** after a clean dry run (no upgrades to
  shared packages). Desk 4 now collects with zero errors: 151 passed, 10 skipped, each
  skip naming the package it waits on. See the Desk 4 decision above for the rest.

- 2026-09-06 — **`regime_filtered_v1` formally PARKED** (Round 112, Ruling R112-OOB.1, Option 2).
  It had sat at N=0 of 50 for five days with no paper trader running. Parked by a dated
  amendment in its own registration file - the bar, the N=12 control and the record are
  untouched. Its page now says so, the experiments register reads `0/50 (0%) · parked`, and
  lint L10 will warn if any future registration sits at zero for 3 days. Antigravity's draft
  rationale cited the Round 104 cascade replay as a FAIL on this strategy; it was INSUFFICIENT,
  side-split, and about a different mechanism, so the amendment records that it is NOT the
  reason. A retuned trial needs a fresh pre-registration. Nothing was started.

- 2026-09-06 — **Desk 1 spread sampling gated on the entry bar** (Ruling R104-1).
  Only coins clearing the 25% gross bar with spot backing get a sampling slot, so
  future basis windows can carry a measured spread and `BASIS_MIN_NET_APR` becomes
  judgeable. **Costs zero extra REST weight** — the 24-coin per-pass cap is
  unchanged, so this reallocates budget rather than enlarging it. Takes effect on
  the collector's next restart (see above).

- 2026-09-06 — **All four R104 rulings implemented** (Round 105). Lint L8 catches
  dangling wikilinks and found **86 real broken links** on its first run — 85 CRM
  pages pointing at exporter notes that were never written, and a desk pointing at a
  page the FOMC drill has not produced yet. All fixed at their cause. The cascade
  replay artifact now stamps itself, and re-running any adapter over unchanged data
  changes zero files.

- 2026-09-05 22:44 — **Exporter restarted** (56412 → 62760), verified by waiting
  for the pid lock rather than trusting the launch. The Round 101 desk links now
  reach the dashboards. Closes the item deferred since Round 101.
- 2026-09-06 — **Whale-sweeper bar ratified and the replay run.** The bar was
  verified by antigravity/architect before any replay, and the replay's verdict
  is **INSUFFICIENT**: one sample gate fails (PONS supplies 22.5% of events against
  a 20% ceiling), so no verdict is issued. Item 14 stays gated off. It is now a
  wiki page compiled from the engine's own JSON, not from transcribed numbers.

- 2026-09-05 21:40 — **Item 18 maiden run executed.** Tier 1 verdict:
  *no measurable lead-lag* (peak |corr| 0.070 vs the 0.20 bar). All six protocol
  checks passed, exit 0. Now a permanent wiki page.
- 2026-09-05 22:20 — **Watcher restarted with tags live** (new PID 17688).
  Series continuity held: 4.1 min gap against a 60 min threshold.
