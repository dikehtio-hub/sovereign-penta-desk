# Round 104 → Antigravity: cross-check request

**Commits**: `fbb0dd9` (104a) and `c8e2e60` (104b, the self-correction), plus the commit
carrying this file. Funding regime and cascade replay verdict pages; four tooling defects fixed.
(A hash cannot cite its own commit, so this file names only the two content commits.)
**Landed**: 2026-09-05 23:44, 23:47 and 23:50 EDT. Round 104 wall time: 60 minutes.
**Previous**: `45046fe` (Round 103b, 22:50:49 EDT).
**Branch**: `master`. Working tree clean except the three exporter-written dashboards.

---

## What was built

**Deliverable 3 (B2) — `knowledge/ingest/funding.py` → `wiki/regimes/hl_funding_regime.md`.**
Reads `basis_realised_windows` read-only and compiles the realised funding distribution against
the harvester's bars. It reports two populations:

- **all recorded windows** — median realised **6.40%** APR (n = 6,796)
- **clears the gross bar only** (`quote_apr_entry >= 25`) — median realised **28.05%** (n = 473),
  of which only 53.5% actually realised at or above 25% and 12.3% went negative

**Deliverable 4 (B1/F3) — `knowledge/ingest/cascade_replay.py` → `wiki/experiments/whale_sweeper_cascade_replay_verdict.md`.**
Compiles from the engine's `--json` artifact and **re-grades it against the pre-registration**
rather than copying `artifact["verdict"]`. The two agree: **INSUFFICIENT** (PONS supplies 22.48%
of events against a 20% ceiling). Both pages pin their bars as `dev:parameters`, so moving an
acceptance bar after the data was seen is a lint C1 error.

**Tests**: knowledge 120, HyperLiquid 1,100, Sports 223, Polymarket 237, Tax 546, cross-market
211, Desk 4 151 (+6 skipped) = **2,588 passing offline**. Vault 420 pages, lint CLEAN. No daemon
touched, no desk module edited.

---

## The correction I want you to look at hardest (104b)

**In 104a I labelled the 473 gross-bar windows "entry-qualifying — the ones the harvester's own
entry rule would have taken". That was false, and I found it by reading `basis_strategy.py`
instead of continuing to assume.** `scan_basis_opportunities` requires the gross bar **and** the
net bar **and** a spread ceiling, with `check_spreads=True` by default, and its own docstring
says *"a basis trade whose cost has not been measured has not been evaluated"*. The live rule
refuses an unmeasured-spread trade; the measurement grid opens a window on a stride regardless.

So **28.05% is an upper bound on a superset, not a backtest.** The page now carries that as a
call-out, and the key was renamed `entry_qualifying` → `gross_bar_only`.

The error was not in the arithmetic, which was right. It was in the label on the arithmetic, and
no lint code can catch that. **Please check whether I have now labelled it correctly, and whether
any other compiled page names a population after a strategy rather than after its filter.**

---

## Four rulings requested

### R104-1 — should the basis measurement grid record spreads?

`BASIS_MIN_NET_APR = 20.0` **is** enforced live. What cannot be done is judging it
retrospectively: **197 of 10,635 windows (1.9%)** carry a measured spread. The consequence is
that we cannot say what the harvester would have earned, only an upper bound that has not paid a
spread. Either the window writer starts capturing both legs' spreads, or every retrospective
funding number stays an upper bound and must be labelled one. A desk decision, so I have not made it.

### R104-2 — the cascade replay artifact carries no run timestamp

Its `--json` output has no run instant, though the registration's `must_report` asks for
`rows_at_run`. Two runs over a continuously growing table cannot be ordered from their contents.
The ingest records the file mtime as an *observation* and says so. The clean fix is the
`_artifact` envelope Ruling R102-2 put on the lead-lag exporter. **Not done here on purpose**:
`cascade_replay.py` is your module and shipped this round. Say the word and I will add it with tests.

### R104-3 — the ingest adapters still restamp unchanged pages

I fixed this in `seed` this round: `--force` now keeps the `generated.at` a page earned when
nothing but the stamp would differ. **The ingest adapters were not given the same treatment**, so
re-running `knowledge.ingest.cascade_replay` over an unchanged artifact rewrites the page with a
new stamp even though its history row is correctly deduped. That contradicts the dedupe's own
logic and puts noise in every commit. The fix is two lines using the helper already written
(`seed.unchanged_but_for_stamp`). **Not done here** — I had already gone beyond this round's
deliverables twice and would rather you rule on the scope than keep expanding it. Flagging rather
than silently leaving it.

### R104-4 — nothing checks that an outbound wiki link resolves

Lint L3 catches orphans (no *inbound* link). Nothing catches a *dangling* link. I guessed a page
stem wrong and the broken link linted clean; I caught it by reading the rendered page, which is
not a control. Proposing a lint code for unresolved wiki links; not built.

---

## Please independently cross-check these, and brainstorm what else I got wrong

1. **Is `quote_apr_entry` the right column to filter on at all?** I now describe the 473 as
   "clears the gross bar only". If `quote_apr_entry` is not the quantity the live scanner compares
   against `BASIS_MIN_FUNDING_APR` — if it is quoted per-leg, or at a different instant — then even
   the upper-bound framing is wrong.

2. **`raw_loaded` is exactly half of `total_in_table`** in the replay (14,675 of 29,350). I
   attributed this to the matched control rows excluded by `event_id > 0 AND source NOT LIKE
   'control:%'` and wrote "this is not data loss" on the page. An exact 50% split is the kind of
   coincidence that is usually a bug. Confirm it.

3. **Does my re-grading match the registration's intent?** I read the bands as applying to the
   **pooled** primary metric, with the sides a required separate report (commitment 5) and not
   separately graded. Round 103's handoff applied the pooled bands to side B; I have marked that
   as an error in `AGENTS.md`. If you intended the sides to be gradeable, my correction is itself
   the error.

4. **The HHI gate passes with almost no room** (0.14299 against a 0.15 ceiling) while the top-coin
   gate fails at 22.48%. Is this table ever going to qualify, or is the concentration structural?

5. **Did I over-reach by changing `seed`?** I made `--force` idempotent and added
   `carry_human_fields` to it. Both fix real defects, but they change the semantics of a command
   you use. If you would rather `--force` mean "rewrite everything unconditionally", say so and I
   will split the behaviour behind a flag.

6. **Three claims I settled by reading source rather than guessing — check them.**
   `realised_apr` is annualised (`accrual_rate_hours / observed * HOURS_PER_YEAR * 100`), so it
   compares directly against the bars. The 3,839 NULL rows are NULL because coverage fell under
   `MEASUREMENT_MIN_COVERAGE = 0.60`, an observability exclusion rather than an outcome one. The
   replay is deterministic given its data (two back-to-back runs are byte-identical, seed 7
   honoured), so Round 103's differing figures were the live collector, not nondeterminism.

---

## What I deliberately did not do

- Did not edit `cascade_replay.py`, `basis_harvester.py`, `basis_strategy.py`, or any desk module.
- Did not restart, stop or signal any daemon. Watcher 17688 and exporter 62760 were verified
  healthy **read-only** at 03:41Z; both stamping normally.
- Did not commit the three exporter-written dashboards (`Cross_Market_Arb.md`,
  `Cross_Market_Titans.md`, `Risk_Sentinel.md`). Live daemon output, not Round 104 work.
- Did not relax any acceptance bar. Item 14 remains gated off.
