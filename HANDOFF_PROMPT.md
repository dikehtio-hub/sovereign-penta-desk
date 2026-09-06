# Round 107 → Antigravity: cross-check request

**Commit**: `eb49ae2` — *feat: Round 107 - query cards, rank_at_seed frozen, volatile dashboards untracked*
**Base**: `8fd7462` (Round 106). **Branch**: `master`. 212 files, +1,075 / −755.
**Timing**: started 2026-09-06T06:27:41Z, committed 06:38:24Z — **10.7 minutes** against a 30–40 minute estimate.

**Tests, all green offline**: knowledge 156 (+11), HyperLiquid + cross-market 1,314, Sports 223,
Polymarket 237, Tax 546. Vault 423 pages + constitution, lint CLEAN, adapters idempotent by hash.
**No daemon restarted. `git status` is now pristine between rounds.**

---

## D3: the drill card, and what reading-under-pressure forces

`knowledge/query.py` answers both queries the constitution pre-baked in s.Query. The card is read at
T-2 with a clock running, and every choice follows from that one fact:

- **It never writes.** No log bullet, no index rebuild, no usage counter. Inside its own window the
  Event page and the rules registration are *frozen* — a query that mutated what it describes could
  not be run at the moment it is most needed. A test hashes the whole vault before and after all
  three modes and asserts nothing moved.
- **It computes the countdown, and the unit matches the decision.** My first render said
  `T-251h 29m`. Nobody converts that at 13:58 with a statement about to print. Days past 48h, hours
  and minutes inside two days, minutes near the window.
- **A missing Event page is an error, not an empty card** — it refuses with the list of known events
  and exits 3. An operator holding a blank sheet two minutes before a print has been actively misled.
- **HALT still refuses**, even though nothing is written: HALT means the pipeline behind the card has
  stopped, and answering normally would imply it had not.
- It surfaces the standing forecast from the journal's calibration ledger (p=0.90, `change_bps == 0`),
  because that forecast scores itself against the payload the operator is about to write — T-2 is the
  last moment it can be checked against what they actually believe.

Live output is 32 lines against the 60 budget.

---

## Two things the directives did not mention, which mattered

### 1. `rank_at_seed` had to be fixed in two places, not one

The directive says to preserve it in the frontmatter. **The body prints the same number from the live
rank.** Preserving only the metadata would have produced a page whose frontmatter said `1` and whose
text said `12` — worse than either number alone. It is now resolved once, before the body is built,
and both read from it. A new `rank_now` carries the live figure, and the body renders
`rank by equity at seed: 1 (now 12)` when they differ.

### 2. Untracking a dashboard needed an L8 check first

Lint L8 resolves wikilinks against files **on disk**. Untracking a dashboard that something links to
would make a fresh clone fail L8. Verified before running `git rm --cached`: the three files you
named have **zero** inbound wikilinks. `Monarch_Hub.md` is also exporter-written and has **five**, so
it stays tracked.

Your list was exactly right — but the *reason* is worth recording, because the next dashboard added
to that list has to pass the same test, and nothing enforces it automatically.

---

## Please independently cross-check these

1. **Is the drill card missing anything you would want at T-2?** I chose: countdown, frozen-window
   banner, the one human-only step, the registered rules with token ids, the standing forecast, and
   the three post-print commands. I deliberately left out market prices (s.6 — the dashboards carry
   the live number) and any depth/liquidity figure. If the operator needs a liquidity read at T-2,
   it is absent by choice and that choice may be wrong.
2. **`--regime BTC` matches on stem or title substring.** `--regime B` would match both regime pages.
   Should ambiguity be an error rather than a multi-page answer?
3. **The `rank_now` field is new.** It is not in the OKF vocabulary and I added it to `dev` without a
   ruling. If `dev.evidence` should carry it instead, say so — I put it in `dev` because it is a
   scalar the register can column on, not a dated observation.
4. **Untracking is not enforced going forward.** Nothing stops a future exporter-owned dashboard from
   being committed, and nothing checks that an ignored file has no inbound links. A lint rule could
   cover the second half; I did not build one.
5. **The card reads the rules table by parsing the rendered markdown body**, not the frontmatter.
   That is fragile if the rules page's table layout changes. The alternative is reading
   `dev.tokens`/`dev.rules`, which would be sturdier — I took the body because it carries the
   human-readable labels and thresholds together. Worth a second opinion.

---

## On the estimate: third consecutive over-quote

30–40 quoted, 10.7 actual. That is the third in a row (105 was 4× under, 106 was 5× over, 107 is 3×
over), and the pattern is now clear enough to change my default: **in this codebase a well-specified
round lands in 10–15 minutes almost regardless of deliverable count** — even one that adds a new
module from scratch. The two things that actually cost time are a new validation rule run over
existing data for the first time (Round 105: two hours), and unfamiliar desk code that must be read
before it can be changed. I have recorded 12–18 minutes as the new default, with an open-ended block
named separately only when a first-run validation rule is involved.

---

## Still needing a person

**The collector has not been restarted** (unchanged from Round 106). Collector `38548` is still
running pre-Round-106 code sampling 5 ungated candidates per pass, so no new window gets a measured
spread and `BASIS_MIN_NET_APR` stays unevaluable. `restart_basis_collector.bat` activates it whenever
you choose. Nothing breaks while you wait.

**The FOMC drill is 10 days out.** `python -m knowledge.query --drill-card fomc-2026-09-16` now works
and is safe to run at any time, including inside the window. It is in `HOMEWORK.md` as the first step
of the drill.

---

## What I deliberately did not do

- Did not restart, stop or signal any daemon; watcher `17688`, exporter `62760`, supervisor `46740`,
  collector `38548` all untouched.
- Did not untrack `Monarch_Hub.md` or any dashboard with inbound links.
- Did not add usage counters or query filing (backlog B16 proper) — the directive cited B16 but the
  spec implemented is the constitution's s.Query, which is a different item.
- Did not change any acceptance bar, gate, or the vault constitution.
