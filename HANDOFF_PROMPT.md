# Out-of-band → Antigravity: the N=50 experiment has never run

**Raised**: 2026-09-06 04:55 EDT, from an operator status request, **not** from a round.
**Head**: `d207dcd`. **Branch**: `master`. Tree pristine. No daemon touched.

> **Round 112's directives are received and NOT lost** — collision-free filed-query slugs,
> the `registers_register` catalogue hub, and the drill-card verification test. They are
> queued and unstarted. This document is a finding raised ahead of them because it concerns a
> pre-registration that has been silently dead for five days, and because acting on it is an
> operator decision rather than a round deliverable.

---

## The finding

`regime_filtered_v1` was registered **2026-09-01T04:40:14Z** with a bar fixed before any data:

| | |
|---|---|
| `min_closed_trades` | **50** |
| PASS | win rate ≥ 54.0% **and** profit factor ≥ 1.25 |
| RETUNE | win rate 48.0–54.0% |
| FAIL | win rate < 48.0% |

Measured just now from `HyperLiquid/HL_Monarch/data/paper_trading_state.json`:

```
closed_trades      0
wins / losses      0 / 0
realized_pnl       0.0
open positions     0
open orders        0
file last written  2026-09-01T05:59:39Z   (122.9 hours ago)
```

**0 of 50. 0%.** The state file was last written **80 minutes after the experiment was
registered** and has not been touched since.

Cross-checked against running processes: the four live daemons are the watcher (`17688`), exporter
(`62760`), supervisor (`46740`) and collector (`38548`). **There is no paper-trading process, and
there has not been one for five days.**

So the experiment is not progressing slowly. It never started.

---

## What is *not* wrong

Worth stating plainly, because the failure is narrow:

- The registration is intact and well-formed, with its acceptance bar fixed before data.
- The **archived N=12 control** is intact and was never overwritten: 12 closed trades, 3 wins /
  9 losses (25% win rate), −$536.74 realized. That standing instruction has been honoured.
- The amendment history is intact, including the one dated amendment at
  `closed_trades_at_amendment: 0`.
- The `known_defect_not_fixed` block is still recorded (targets sized off a 15-minute ATR while
  positions force-close at 600 s; measured median time to a 1.0×ATR target is 1,224 s).

Nothing has drifted. There is simply no flight.

---

## The part I want ruled on

The registration commits to **"No mid-flight parameter changes before N=50."** That commitment is
currently being honoured *trivially* — there is no mid-flight. A pre-registration that cannot
accumulate evidence is indistinguishable, from the outside, from one that is being carefully
respected, and the vault renders both the same way.

**That is the structural problem worth a ruling, not just this one experiment:** we have a
pre-registration whose N is 0 and whose page says nothing about it. There is no lint rule, no
register column and no digest line that would have surfaced this. I found it only because the
operator asked a direct question.

### Three options, and I have taken none of them

1. **Start the paper trader** and let it accumulate toward 50. Note the scale: the control took a
   full run to produce 12 closed trades, so 50 is a stretch of *runtime*, not a day — and the FOMC
   drill work occupies the calendar to 2026-09-16.
2. **Formally park it** with a dated note on the Experiment page recording that it was registered,
   never run, and why. The bar stays fixed; the page stops implying an experiment in progress.
3. **Retire the regime filter** as not worth the runtime, and say so before the FOMC work absorbs
   the schedule.

Starting a paper trader is a live-execution decision, so I have not started anything.

### And one thing I would build regardless of which you choose

**A lint check for a stalled pre-registration.** An Experiment page with a `min_closed_trades`-style
bar, a registered instant older than N days, and zero recorded progress should say so on its own
page. Concretely: `dev.progress {closed_trades, of, measured_at}` on the registration page, and a
warning when it has not moved since the last measurement.

This is the same failure shape as Rounds 108–111 — **silence**. L9 returned zero findings while
broken; the digest compiler dropped two-thirds of its input; two register writers overwrote each
other. None errored. A pre-registration sitting at N=0 for five days is the same thing one layer up:
nothing is wrong, nothing is red, and nothing is happening.

---

## Please rule on

1. **Which of the three options** for `regime_filtered_v1`.
2. **Whether progress tracking belongs on Experiment pages** (`dev.progress`) and whether a stalled
   registration should be a lint **warning** or merely a register column.
3. **Whether the same check should cover the other live registration** — `passive_fade_rebenchmark`
   also carries sample gates. I have not audited its progress and did not want to widen a status
   answer into a survey without asking.
4. **Whether any of this should precede Round 112's three deliverables**, or run after them. My
   default, absent a ruling, is to do Round 112 as directed and leave this as an operator decision
   on `HOMEWORK.md`.

---

## Current system state (unchanged, for completeness)

- **Tests, all green offline**: knowledge 233, HL + cross-market + Sports + Polymarket 1,774,
  Tax 546, Desk 4 151 (+6 skipped) = **2,704 passing**. Desk 4 leaves 4 modules uncollectable for a
  missing `fastapi` — pre-existing.
- `knowledge.lint`: **491 pages + constitution · 0 errors · 0 warnings · CLEAN**.
- Daemons all healthy, verified read-only: watcher stamping every ~5 min with tags live, collector
  writing `asset_snapshots` 0.2 min ago. C2 bot correctly down (no token, no admin allowlist).
- Tier 2b series: **30.3 h unbroken**, largest gap 12.2 min against a 60 min threshold. Sleep is
  confirmed off; gate closes ~22:20 EDT tonight.
- `Monarch_FOMC_Drill` still carries `DisallowStartIfOnBatteries: True` — on the operator's list.
