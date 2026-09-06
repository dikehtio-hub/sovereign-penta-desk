# HOMEWORK — things only the operator can do

Everything in this file needs a human. Anything an agent can do is not here; that
lives in `LLM_WIKI_BACKLOG.md` (knowledge layer) and the Top 20 registry in
`MASTER_COMMAND_LIST.txt` (trading desks).

Last updated: 2026-09-06 14:50 EDT (Round 113; drill pre-flight exists, fastapi installed).

---

## 🔴 DATED — these have real deadlines

### 2026-09-15 (Tue) — Q3 estimated tax payment
- Run `python -m Tax_Reserve_Agent.main calendar` for the amount and the escrow release.
- The quarters are not quarters: Q3 covers Jun 1 – Aug 31 (3 months), due Sep 15.
- Registered in the vault as `wiki/events/tax_estimated_2026_q3.md`.
- **If missed:** an underpayment penalty accrues from the deadline, not from April.

### 2026-09-16 (Wed) 13:58 EDT — FOMC drill. THE BIG ONE.
- **Run this first:** `python -m knowledge.query --drill-card fomc-2026-09-16`.
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

- [ ] **Send the Round 113 handoff prompt to Antigravity.**
- [ ] **Clear the FOMC drill's battery flags, or commit to staying on AC.** The condition
      itself is described under the 2026-09-16 entry above. This line is the DECISION:
      leave the flags and rely on remembering the charger, or have me clear them. Clearing
      is small and testable. Either is fine; drifting into the 16th without choosing is not.
      `python -m knowledge.drills.fomc_rehearsal` now reports this as a WARN every time you run it,
      and will report PASS the moment the flags are cleared.
- [ ] **Decide when the collector restarts** so the new spread gate takes effect.
      Ruling R104-1 is implemented but collector `38548` is still running the old
      code, which samples only 5 candidates per pass. Until it restarts, no new
      window gets a measured spread and the net hurdle stays unevaluable. Per the
      ruling's own daemon policy I did **not** restart it — the change takes effect
      on the next maintenance restart, whenever you choose that. Nothing breaks if
      you wait; the backlog of unmeasured windows simply keeps growing.

---

## 🟡 RECOMMENDED BEFORE 2026-09-16

- [ ] **Authorise the LIVE dress rehearsal of the FOMC drill (Sep 13-14).** The
      offline pre-flight now exists and passes on the real setup (Round 113:
      `python -m knowledge.drills.fomc_rehearsal`, 0 FAIL, 2 WARN). What it cannot
      do is record real order books: the Round 94 dry run recorded 9 stamps over 3
      seconds; the real thing is ~1,260 stamps over 420 seconds across three tokens,
      and stamps → survival curve → Reaction Profile page has only ever run against a
      fixture. A live 60-second recording into a scratch books dir, then the curve and
      ingest over it, is the step that needs your go-ahead (network, and it exercises
      the same code the 16th will). Round 102/103 found two components that looked
      fine and were not; the pre-flight found a third in its own regex on first run.
- [ ] **Decide on Desk 4's missing packages.** fastapi is installed (Round 113, after a
      clean dry run). The webhook path is STILL untested: `main.py` imports the
      Hyperliquid adapter at module level, so `test_webhook_server`,
      `test_hyperliquid_adapter` and `test_multivenue_execution` all skip until
      `pip install hyperliquid-python-sdk` (dry run: also eth-utils 5.3.1 and msgpack
      1.2.2 - new crypto-adjacent packages into the same environment the live desks run
      in), and `test_run_paper_trading` skips until `pip install uvicorn` (0.52.4, no
      other deps). I did not install either without your word. Say yes to one or both
      and I will dry-run again, install, and run the four modules for the first time in
      a long while - they may fail for real reasons, which is the point.

---

## 🔵 STANDING OPERATIONAL RULES

- **Keep the laptop awake** whenever a 24 h series is accumulating. A gap over
  60 minutes breaks the run and restarts the clock at zero.
- **Shut down cleanly** — normal Windows shutdown, never the power button.
  `hyperliquid_data.db` is 4.9 GB with an open write-ahead log.
- **Never kill the daemons by hand.** All four verified healthy read-only at
  2026-09-06 04:05 EDT: watcher 17688 (tags live, stamp 0.3 min old), exporter 62760
  (restarted 2026-09-06T02:44Z), supervisor 46740, collector 38548 (30.5 h uptime,
  writing `asset_snapshots` 0.2 min ago). The C2 bot is correctly DOWN - it has no
  token and no admin allowlist, so it would fail closed anyway.
- **Never seed the live tax ledger.** `seed-bankroll` is paper-only.
- **`DEV/HALT.flag`** is the kill switch: create it and every execution engine
  refuses with exit 3. Delete it to resume.

---

## ✅ DONE (kept briefly, then deleted)

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
