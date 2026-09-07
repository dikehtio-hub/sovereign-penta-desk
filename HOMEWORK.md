# HOMEWORK — things only the operator can do

Everything in this file needs a human. Anything an agent can do is not here; that
lives in `LLM_WIKI_BACKLOG.md` (knowledge layer) and the Top 20 registry in
`MASTER_COMMAND_LIST.txt` (trading desks).

Last updated: 2026-09-07 00:50 EDT (Round 122: lead-lag pages carry their measured span; disjoint replication windows possible; no new operator actions).

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
- [ ] **Two yes/no decisions I am waiting on:** (a) install `uvicorn` and `hyperliquid-python-sdk` for Desk 4;
      (b) name a deploy window for the collector hardening (see 09-08 below for my recommendation).
- [ ] **Keep the laptop awake and collecting from now through ~22:22 EDT tonight (Mon 09-07)** - run 2 of 3.
      Antigravity's R122-1.B fixes run 2 as the DISJOINT window starting 2026-09-07T02:22:00Z, which reaches 24 h
      at ~22:22 tonight. Its start (01:21Z) is after the collector came back (01:05Z), so its prices are clean.
      **This needs UNBROKEN collection until then**: if the machine sleeps or shuts down, that fixed window gets a
      gap, the readiness gate fails, and run 2 slides to a new start after you resume. The run itself is mine
      (ping me ~22:20 and I execute it, or paste the block below). Exact, pre-registered:
      1. Gate (must say `ready: true`):
         `python -m cross_market.lead_lag --check-data --family macro --subfamily-from tags --since 2026-09-07T02:22:00Z`
      2. The four runs:
         `python -m cross_market.lead_lag --coin BTC --family macro --subfamily fed-rates --since 2026-09-07T02:22:00Z --json > cross_market/experiments/lead_lag_tier2_fed-rates_verdict_run2.json`
         `python -m cross_market.lead_lag --coin BTC --family macro --subfamily crypto --latency-minutes 5 --since 2026-09-07T02:22:00Z --json > cross_market/experiments/lead_lag_tier2_crypto_verdict_run2.json`
         `python -m cross_market.lead_lag --coin BTC --family macro --subfamily fed-rates --subfamily-from tags --since 2026-09-07T02:22:00Z --json > cross_market/experiments/lead_lag_tier2b_fed-rates_verdict_run2.json`
         `python -m cross_market.lead_lag --coin BTC --family macro --subfamily crypto --subfamily-from tags --latency-minutes 5 --since 2026-09-07T02:22:00Z --json > cross_market/experiments/lead_lag_tier2b_crypto_verdict_run2.json`
      3. Ingest each with its tier: `--tier 2` for the two tier2 files, `--tier 2b` for the two tier2b files, e.g.
         `python -m knowledge.ingest.lead_lag --result cross_market/experiments/lead_lag_tier2_fed-rates_verdict_run2.json --tier 2`
      Run 3 then binds `--since <run 2's shift_last_utc>` and closes ~22:22 EDT Tue 09-08.

### Mon 09-08 or Tue 09-09 — recommended deploy window for the collector hardening (~5 min, my hands)
- [ ] Say "deploy the hardening" on one of these two evenings. That gives the watchdog a full week of soak
      before the FOMC drill and leaves 09-10 to 09-15 for a rollback if it misbehaves. Do NOT deploy on
      09-14 or later: never change the collector inside 48 h of the print.
- [ ] **Keep the laptop awake through 22:20 on 09-08** as well - run 3 of 3 closes then.

### Any day 09-07 to 09-14 — scheduler probe (~3 min, logged in)
- [x] `powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1`
      DONE 2026-09-07 01:05 EDT — **PROBE OK**, last result 0, 60/60 stamps into scratch, task self-removed.
      The scheduler → tracked batch → recorder chain fires correctly on this machine. Re-run only if the
      machine or the drill files change before the 16th.

### Every day until 09-16 — two 10-second checks
- [ ] `python -m knowledge.drills.fomc_rehearsal --online`   (33 checks; 0 FAIL is the answer; forward any FAIL line to me)
- [ ] The collector one-liner under ROUND 119 in `COMMANDS.txt` (minutes since the last snapshot; over ~1 means look).

### Sat 09-13 or Sun 09-14 — live dress rehearsal (~2 min)
- [ ] `python -m knowledge.drills.fomc_live_rehearsal`  (60 s of real books into scratch; nothing real written).
      Expect: 180/180 stamps, one curve, two deferrals for a hold. Send me any FAIL line.

### Mon 09-15 — Q3 estimated tax (deadline; not a trading task)
- [ ] `python -m Tax_Reserve_Agent.main calendar` for the amount, then pay it. Penalty accrues from this date.

### Wed 09-16 — FOMC drill day, minute by minute
- [ ] **Morning (any time before 12:00):** `fomc_rehearsal --online`, then `fomc_live_rehearsal`. Both clean, or call me.
- [ ] **13:30** - laptop ON, LOGGED IN, lid open, sleep disabled, VPN in whatever state it will stay in for the hour.
- [ ] **13:56** - `python -m knowledge.query --drill-card fomc-2026-09-16`  (read-only; countdown + the paste-ready commands).
- [ ] **13:58** - the scheduled task fires by itself and records for 420 s (until 14:05). Touch nothing.
- [ ] **14:00** - the statement prints. READ the rate decision yourself, then:
      `python -m knowledge.drills.event_json --bps <n>`   (0 = hold, 25 = quarter-point hike, -25 = cut).
      Wrong number? `--force` overwrites. Nothing automated may decide this.
- [ ] **14:06 (after the recorder stops)** - the survival curve, then `knowledge.ingest.clob`, exactly as the card prints them.
      Your p = 0.90 "no change" forecast scores itself once the event and the books are in the vault.
- [ ] **Afterwards** - tell me it ran (or send the output of anything that did not).

### If 09-16 is missed
- Next FOMC: 2026-10-27/28. Everything stays armed; the registration would need re-dating and fresh token ids.

### No date — whenever you are ready
- [ ] **Name the aim of the next project** (the reading-intake layer: links, videos, articles). One sentence
      on what the notes are FOR is all I need to build the inbox and the fetch adapter.

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

## 🟠 BLOCKING — work is stopped until you do these

- [ ] **Send the Round 121 handoff prompt to Antigravity.** (Four rulings requested; the watchdog deviation is one.)
- [ ] **Run the scheduler probe** (any time before the 16th, logged in, on AC, ~3 minutes):
      `powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1`
      It registers a temporary task that fires in 2 minutes and runs the drill's batch for 20 s into
      a scratch folder, then removes itself. PROBE OK means Task Scheduler -> batch -> recorder works
      on this machine; PROBE FAILED with 'never ran' on battery is the battery-flag decision showing
      itself. Add `-WhatIf` first if you want to see what it would do without doing it.
- [x] ~~**Start the Windows Time service.**~~ DONE 2026-09-07 01:13 EDT. See the calendar entry above:
      it was running but had never synced to the internet (Local CMOS Clock); now synced to time.windows.com,
      startup Automatic. No longer a blocker.

---

## 🟡 RECOMMENDED BEFORE 2026-09-16

- [ ] **Run the live dress rehearsal yourself on Sep 13 or 14, and again the morning of
      the 16th**: `python -m knowledge.drills.fomc_live_rehearsal` (60 s of real order
      books into a scratch folder, then the whole post-print path into a scratch copy of
      the vault; nothing real is written). It ran clean on Sep 6 (Round 116). If any line
      says FAIL, send me the output. It also tells you, in advance, that a hold produces
      one curve and two deferrals.
- [ ] **Decide on Desk 4's missing packages.** fastapi is installed (Round 113, after a
      clean dry run). The webhook path is STILL untested: `main.py` imports the
      Hyperliquid adapter at module level, so `test_webhook_server`,
      `test_hyperliquid_adapter` and `test_multivenue_execution` all skip until
      `pip install hyperliquid-python-sdk` (dry run: also eth-utils 5.3.1 and msgpack
      1.2.2 - new crypto-adjacent packages into the same environment the live desks run
      in), and `test_run_paper_trading` skips until `pip install uvicorn` (0.52.4, no
      other deps). Antigravity approved both in Round 114 on condition the dry run shows no
      downgrades (it does not). I still have not installed either: the environment the live
      desks run in is yours. Say yes to one or both and I will install and run the four modules.

---

## 🔵 STANDING OPERATIONAL RULES

- **Keep the laptop awake** whenever a 24 h series is accumulating. A gap over
  60 minutes breaks the run and restarts the clock at zero.
- **Shut down cleanly** — normal Windows shutdown, never the power button.
  `hyperliquid_data.db` is 4.9 GB with an open write-ahead log.
- **After any shutdown or reboot, resume with ONE command:** `resume_all.bat` (DEV root).
  It brings back the price collector AND the watcher/exporters, each gated on its own status so it
  never double-starts and never forgets the collector, then prints a health check. The daemons do
  NOT auto-start on login, so nothing collects until you run this (or ask me to). Built Round 122b,
  tested live (all-kept when already up).
- **Never kill the daemons by hand.** As of 2026-09-06 21:07 EDT: watcher 17688, exporter
  62760 (restarted 2026-09-06T02:44Z), supervisor **24504** and collector **60756** (both
  restarted 21:04 EDT after the snapshot outage; the R104-1 spread gate is now live). The
  C2 bot is correctly DOWN - it has no token and no admin allowlist.
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
