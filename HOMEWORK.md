# HOMEWORK — things only the operator can do

Everything in this file needs a human. Anything an agent can do is not here; that
lives in `LLM_WIKI_BACKLOG.md` (knowledge layer) and the Top 20 registry in
`MASTER_COMMAND_LIST.txt` (trading desks).

Last updated: 2026-09-06 21:15 EDT (Round 119; collector restarted after a 9 h snapshot outage).

---

## 🔴 DATED — these have real deadlines

### 2026-09-15 (Tue) — Q3 estimated tax payment
- Run `python -m Tax_Reserve_Agent.main calendar` for the amount and the escrow release.
- The quarters are not quarters: Q3 covers Jun 1 – Aug 31 (3 months), due Sep 15.
- Registered in the vault as `wiki/events/tax_estimated_2026_q3.md`.
- **If missed:** an underpayment penalty accrues from the deadline, not from April.

### 2026-09-16 (Wed) 13:58 EDT — FOMC drill. THE BIG ONE.
- **Morning of the 16th, first:** `python -m knowledge.drills.fomc_rehearsal --online` (30 checks incl.
  a live fetch of each token) and `python -m knowledge.drills.fomc_live_rehearsal` (60 s, scratch only).
  Then at T-2: `python -m knowledge.query --drill-card fomc-2026-09-16`.
  It prints the countdown, the rules with their FULL token ids, your standing forecast and
  the exact post-print commands ready to paste, in under 60 lines. It writes nothing, so it
  is safe to run inside the window as often as you like.
- **Laptop ON and LOGGED IN at 13:58 EDT.** The task `Monarch_FOMC_Drill` fires
  at T-2 min and records 420 seconds of order-book depth on three Fed markets.
  It cannot run on a sleeping or logged-out machine.
- **AC POWER REQUIRED (Battery Warning):** `Monarch_FOMC_Drill` has `DisallowStartIfOnBatteries: True`
  and `StopIfGoingOnBatteries: True`. If the laptop is on battery at 13:58 EDT, the drill WILL NOT START,
  and unplugging mid-recording stops it. Keep AC plugged in, or clear these flags in Task Scheduler.
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

### 2026-09-06 (Sun) ~22:20 EDT — Tier 2b gate (soft) — TODAY
- Needs 24 unbroken hours of *tagged* stamps. The clock started at the 2026-09-05
  22:20 EDT watcher restart, so it closes ~22:20 tonight.
- **Verified 2026-09-06 04:00 EDT**: 30.3 h of unbroken tagged stamps, largest gap
  12.2 min against a 60 min break threshold. Sleep is off (idle standby and
  hibernate both 0); no `Kernel-Power` ID 42 since 2026-09-04. On track.
- Just leave the laptop on. Closing the lid is the one path not ruled out.
- **If missed:** nothing breaks; the clock restarts from the next boot.

---

## 🟠 BLOCKING — work is stopped until you do these

- [ ] **Send the Round 119 handoff prompt to Antigravity.** (Incident report inside; it needs rulings.)
- [ ] **Run the scheduler probe** (any time before the 16th, logged in, on AC, ~3 minutes):
      `powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1`
      It registers a temporary task that fires in 2 minutes and runs the drill's batch for 20 s into
      a scratch folder, then removes itself. PROBE OK means Task Scheduler -> batch -> recorder works
      on this machine; PROBE FAILED with 'never ran' on battery is the battery-flag decision showing
      itself. Add `-WhatIf` first if you want to see what it would do without doing it.
- [ ] **Start the Windows Time service.** The pre-flight found W32Time STOPPED. The clock is only
      +0.37 s off today, but nothing corrects it between now and the 16th, and a scheduler on a slow
      clock records the print as history. Two commands in an elevated PowerShell:
      `Start-Service W32Time; w32tm /resync` - then `python -m knowledge.drills.fomc_rehearsal` should
      show that WARN gone. I did not start it: starting a service is yours to do.
- [ ] **Clear the FOMC drill's battery flags, or commit to staying on AC.** The condition
      itself is described under the 2026-09-16 entry above. This line is the DECISION:
      leave the flags and rely on remembering the charger, or have me clear them. Clearing
      is small and testable. Either is fine; drifting into the 16th without choosing is not.
      `python -m knowledge.drills.fomc_rehearsal` (29 checks now) reports this as a WARN every time you
      run it, and will report PASS the moment the flags are cleared.

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
