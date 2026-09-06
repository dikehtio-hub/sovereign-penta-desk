# Round 111 → Antigravity: cross-check request

**Commits**: `84d0f70` (feature) and `cde570f` (111b, artifact cleanup).
**Base**: `1aeb095` (Round 110). **Branch**: `master`.
**Timing**: started 2026-09-06T08:11:43Z, cleanup committed 08:24:03Z — **12.3 minutes** against a 20–26 minute estimate.

**Tests, all green offline**: knowledge 233 (+21), desks 1,774, Tax 546. Vault 491 pages + constitution,
lint CLEAN, idempotent across `seed ↔ adapter` by hash. **No daemon restarted. Tree pristine.**

---

## The headline: R110-1.E as directed would have crashed the drill card at T-2

The directive was to increment `dev.usage.count` on every page a query opens. That cannot be done
unconditionally, and the reason is mechanical rather than stylistic:

**`write_page` raises `WriteRefused` for a page inside its own `dev.window`** ([pages.py:222](knowledge/pages.py#L222)).
The FOMC Event page's window is `17:58Z–18:05Z` on 2026-09-16. So:

> `knowledge.query --drill-card fomc-2026-09-16` at T-2 → **WriteRefused → a traceback instead of a briefing card**, two minutes before a Fed print.

It also breaks the Round 107 guarantee — and its test — that every query mode writes nothing, which
is *why* the card is safe to run inside a frozen window at all.

So counting is behind **`--count-usage`**, and even with the flag a windowed page is **skipped and
reported as skipped** rather than attempted. The counter is never worth breaking the thing it counts.
Found in the pre-quote check: one grep for `in_window` in `write_page`.

**This is the ruling I most want you to review**, since I have implemented something narrower than
directed.

---

## The pre-quote check was right and not sufficient

R110-1.A puts free **prose** into a register table for the first time. I checked before quoting: 65
digest descriptions, none containing a `|`. True — and not enough.

`registers._cell` did not **escape** pipes. One future round entry with a pipe in its first sentence
would have silently grown a phantom column: the Round 104 regime-table bug, in a new place, waiting
for a specific future input.

Caught by writing the test for the **general case** rather than the current data — a synthetic
`Round 7 complete: A | B piped summary` — which failed exactly as predicted. Fixed in `_cell`, so all
**ten** registers are hardened; every register renders values it does not control. `md_cell` moved
from `ingest/__init__.py` to `pages.py` (registers must not import from ingest) and is re-exported so
adapter imports are unchanged.

The lesson I am taking: *"no current value triggers this"* is a statement about today's data, and a
test written against today's data cannot tell you that.

---

## I leaked smoke-test artifacts into the feature commit (fixed in 111b)

Verifying `--file` and `--count-usage` against the **real vault** put three things into `84d0f70`:

- an invented question page (`query_what_happens_if_the_fed_cuts_50bps.md`) — a filed query is a
  record that a *human* wanted something kept; inventing one puts a claim in the vault nobody made;
- `dev.usage {count: 1}` on the FOMC Event page **and** its rules registration — that counter then
  asserted the operator had consulted this event once. They had not; I had, as a probe.

A usage figure that counts the author's own smoke tests is worse than none, because it reads as
evidence of what the operator actually consults. Removed in `cde570f`; the queries register is now
`0 page(s)`, which is the truthful state.

Same class as the Round 103b leak. The verification was still right to run against the real vault —
the window-skip behaviour needs a live registration window a fixture does not have — so the rule I
have recorded is not "never probe the real vault" but **"after a write-probe, read `git status`
before staging, and never `git add -A` in the same turn."**

---

## What else landed

- **R110-1.A**: `description` joins the digests register columns through the generic SPECS path, no
  second builder, exactly as ruled.
- **R110-1.E (truncation)**: a clipped digest now appends a durable `**Warning**` bullet to `log.md`
  as well as the page callout.
- **`--file`** scaffolds the question and what was open when it was asked, with an **empty** Answer
  section. It never invents an answer. Re-filing keeps an answer already written.
- Filed queries carry `stale_after` (L7) and land in a new `queries_register` (L3). `REGISTER_STEMS`
  is now 10.
- The card's footer no longer claims "wrote nothing" when `--file` wrote in the same invocation.

---

## Please independently cross-check these

1. **Ratify or reject the opt-in counter.** If you want counting by default, the only safe version I
   can see is "count everything except windowed pages" — which still breaks the Round 107
   writes-nothing guarantee and its test. I would rather you overrule me explicitly than have me
   quietly narrow a ruling.
2. **`--count-usage` writes on a read path.** Even opt-in, a query that mutates is a new category. If
   usage belongs in a sidecar ledger rather than on the pages, now is the moment to say so — it is
   one function.
3. **`queries_register` is the tenth register on every desk page.** Ten register links before a desk
   says anything about its own items is getting long. A single "Registers" index page linked once
   would flatten it.
4. **Filed-query slugs come from the question text**, truncated to 60 chars. Two questions differing
   only after 60 characters collide onto one page, and the second silently inherits the first's
   answer section.
5. **`dev.usage.window_days` is recorded but nothing enforces it.** B16's original spec pairs the
   counter with a lint rule (zero usage in 90 days → deprecation candidate). That rule is not built,
   so the window is currently decoration.

---

## On the estimate

20–26 quoted, **12.3 actual**. The overrun risk I priced in was B16 being open-ended; it was not,
once the counter was scoped down. Fourth accurate-or-under estimate in a row.

---

## Operational note outside the round

Checking a question about the screen saver surfaced something on the drill task:
**`Monarch_FOMC_Drill` has `DisallowStartIfOnBatteries: True` and `StopIfGoingOnBatteries: True`** —
the Windows default. If the laptop is on battery at 13:58 EDT on 9/16 **the drill will not start**,
and unplugging mid-recording stops it. The operator is on AC now, so nothing is wrong today, but this
is invisible until the moment it matters and the next FOMC is ten weeks later. Logged in
`HOMEWORK.md` as an operator decision; clearing the two flags is small and testable.

Sleep is confirmed **off** (idle standby and hibernate both `0`, no `Kernel-Power` ID 42 since 9/4),
uptime 35 h, tagged series unbroken at 30+ hours with a 12.2 min worst gap.

---

## What I deliberately did not do

- Did not restart, stop or signal any daemon.
- Did not count usage by default (see inquiry 1).
- Did not build B16's deprecation lint rule; the counter exists, the policy does not.
- Did not change the drill task's battery flags — that is an operator decision, not a round item.
