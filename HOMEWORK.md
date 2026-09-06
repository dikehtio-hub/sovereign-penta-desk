# HOMEWORK — things only the operator can do

Everything in this file needs a human. Anything an agent can do is not here; that
lives in `LLM_WIKI_BACKLOG.md` (knowledge layer) and the Top 20 registry in
`MASTER_COMMAND_LIST.txt` (trading desks).

Last updated: 2026-09-05 22:30 EDT (Round 103).

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

- [ ] **Send the latest handoff prompt to Antigravity.** Two things are blocked:
      (a) the whale-sweeper acceptance bar is registered but *unverified*, and the
      replay must not run until it is ratified; (b) three checklist corrections
      need a ruling — chiefly whether Items 10, 12 and 13 count as complete when
      the registry says they do not.
- [ ] **Decide when the exporter (PID 56412) restarts.** Deferred in Round 101.
      Until it restarts: the Round 101 desk links and shell-twin lines never appear
      on the dashboards, and the verdict artifact the new ingest expects is never
      written. Recommendation: tonight after Entry C, verified rather than trusted.

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

---

## 🔵 STANDING OPERATIONAL RULES

- **Keep the laptop awake** whenever a 24 h series is accumulating. A gap over
  60 minutes breaks the run and restarts the clock at zero.
- **Shut down cleanly** — normal Windows shutdown, never the power button.
  `hyperliquid_data.db` is 4.9 GB with an open write-ahead log.
- **Never kill the daemons by hand.** Current: watcher 17688 (restarted 22:20
  tonight, tags live), exporter 56412, supervisor 46740, collector 38548.
- **Never seed the live tax ledger.** `seed-bankroll` is paper-only.
- **`DEV/HALT.flag`** is the kill switch: create it and every execution engine
  refuses with exit 3. Delete it to resume.

---

## ✅ DONE (kept briefly, then deleted)

- 2026-09-05 21:40 — **Item 18 maiden run executed.** Tier 1 verdict:
  *no measurable lead-lag* (peak |corr| 0.070 vs the 0.20 bar). All six protocol
  checks passed, exit 0. Now a permanent wiki page.
- 2026-09-05 22:20 — **Watcher restarted with tags live** (new PID 17688).
  Series continuity held: 4.1 min gap against a 60 min threshold.
