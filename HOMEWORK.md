# HOMEWORK — things only the operator can do

Everything in this file needs a human. Anything an agent can do is not here; that
lives in `LLM_WIKI_BACKLOG.md` (knowledge layer) and the Top 20 registry in
`MASTER_COMMAND_LIST.txt` (trading desks).

Last updated: 2026-09-05 23:55 EDT (Round 104).

---

## 🔴 DATED — these have real deadlines

### 2026-09-15 (Tue) — Q3 estimated tax payment
- Run `python -m Tax_Reserve_Agent.main calendar` for the amount and the escrow release.
- The quarters are not quarters: Q3 covers Jun 1 – Aug 31 (3 months), due Sep 15.
- Registered in the vault as `wiki/events/tax_estimated_2026_q3.md`.
- **If missed:** an underpayment penalty accrues from the deadline, not from April.

### 2026-09-16 (Wed) 13:58 EDT — FOMC drill. THE BIG ONE.
- **Laptop ON and LOGGED IN at 13:58 EDT.** The task `Monarch_FOMC_Drill` fires
  at T-2 min and records 420 seconds of order-book depth on three Fed markets.
  It cannot run on a sleeping or logged-out machine.
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

### 2026-09-06 (Sun) ~22:20 EDT — Tier 2b gate (soft)
- Needs 24 unbroken hours of *tagged* stamps, which began at the 22:20 watcher
  restart tonight. Just leave the laptop on and awake.
- **If missed:** nothing breaks; the clock restarts from the next boot.

---

## 🟠 BLOCKING — work is stopped until you do these

- [ ] **Send the Round 104 handoff prompt to Antigravity.** Three rulings are
      requested and one of them decides whether a live hurdle means anything:
      see the net-hurdle item directly below.
- [ ] **Rule on the net funding hurdle, which currently cannot be enforced.**
      `BASIS_MIN_NET_APR = 20.0` is the bar that is supposed to govern the basis
      book after paying spread on both legs. It can be evaluated on **197 of
      10,635 recorded windows (1.9%)** — every other row has `fee_basis` set to
      `'unmeasured'`, because spreads were not recorded when the window closed.
      So the stricter of the two hurdles is, on this data, decorative. Either the
      window writer starts recording both legs' spreads, or the bar should stop
      being described as governing anything. This is a decision, not a bug fix.
- [ ] **Rule on stamping the cascade replay artifact.** Its `--json` output carries
      no run timestamp, so two runs over a table that grows continuously cannot be
      ordered from their contents. Round 103 already recorded two figures from it
      that had silently moved. The fix is the `_artifact` envelope Ruling R102-2 put
      on the lead-lag exporter. **Not done here on purpose** — `cascade_replay.py`
      is Antigravity's module and shipped this round.

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
- **Never kill the daemons by hand.** Current: watcher 17688 (tags live, stamping
  every ~5 min), exporter 62760 (restarted 2026-09-06T02:44Z), supervisor 46740,
  collector 38548. Both were verified healthy read-only at 03:41Z.
- **Never seed the live tax ledger.** `seed-bankroll` is paper-only.
- **`DEV/HALT.flag`** is the kill switch: create it and every execution engine
  refuses with exit 3. Delete it to resume.

---

## ✅ DONE (kept briefly, then deleted)

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
