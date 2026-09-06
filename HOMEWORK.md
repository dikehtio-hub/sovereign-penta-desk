# HOMEWORK — things only the operator can do

Everything in this file needs a human. Anything an agent can do is not here; that
lives in `LLM_WIKI_BACKLOG.md` (knowledge layer) and the Top 20 registry in
`MASTER_COMMAND_LIST.txt` (trading desks).

Last updated: 2026-09-06 04:55 EDT (N=50 experiment stall added).

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

- [ ] **Send the Round 111 handoff prompt to Antigravity.**
- [ ] **Clear the FOMC drill's battery flags, or commit to staying on AC.** The condition
      itself is described under the 2026-09-16 entry above. This line is the DECISION:
      leave the flags and rely on remembering the charger, or have me clear them. Clearing
      is small and testable. Either is fine; drifting into the 16th without choosing is not.
- [ ] **The N=50 experiment has recorded ZERO trades and has not run for 5 days.**
      `regime_filtered_v1` was registered 2026-09-01T04:40Z with a pre-committed bar of
      `min_closed_trades: 50` (PASS: win rate >= 54% AND profit factor >= 1.25). Measured
      2026-09-06 04:50 EDT:

      | | |
      |---|---|
      | closed trades | **0 of 50** |
      | wins / losses | 0 / 0 |
      | `paper_trading_state.json` last written | **2026-09-01T05:59Z (122.9 h ago)** |
      | paper-trading process running | **none** |

      The state file was last touched 80 minutes after registration. The four live daemons are
      the watcher, exporter, supervisor and collector - **nothing is generating trades**. The
      registration, its acceptance bar, the archived N=12 control and the amendment history are
      all intact; there is simply no flight.
      The registration commits to "no mid-flight parameter changes before N=50", which is being
      honoured trivially. For scale: the control took a full run to produce 12 closed trades, so
      50 is a stretch of runtime, not a day.
      **This needs a human because starting a paper trader is a live-execution decision.** I have
      not started anything. Three options: start it and let it accumulate, formally park the
      experiment with a dated note, or decide the regime filter is not worth the runtime before
      the FOMC work absorbs the calendar. Say which and I will implement it.

- [ ] **Decide when the collector restarts** so the new spread gate takes effect.
      Ruling R104-1 is implemented but collector `38548` is still running the old
      code, which samples only 5 candidates per pass. Until it restarts, no new
      window gets a measured spread and the net hurdle stays unevaluable. Per the
      ruling's own daemon policy I did **not** restart it — the change takes effect
      on the next maintenance restart, whenever you choose that. Nothing breaks if
      you wait; the backlog of unmeasured windows simply keeps growing.

---

## 🟡 RECOMMENDED BEFORE 2026-09-16

- [ ] **Authorise a full dress rehearsal of the FOMC drill.** The Round 94 dry run
      recorded 9 stamps over 3 seconds. The real thing is ~1,260 stamps over 420
      seconds across three tokens, and the path from stamps → survival curve →
      Reaction Profile page has only ever run against a test fixture.
      Round 102/103 alone found two components that looked fine and were not
      (a `--json` flag documented for four rounds that never worked; a restart
      script that reports failure on success). Ten days out is the right time to
      find the third one.
- [ ] **`pip install fastapi` for Desk 4.** Four test modules in `quant_trading_lab`
      cannot even be collected without it (`test_webhook_server`,
      `test_hyperliquid_adapter`, `test_multivenue_execution`,
      `test_run_paper_trading`). The other 151 pass. This is pre-existing and has
      nothing to do with recent rounds, but it means Desk 4's webhook path has been
      untested for some time.

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
