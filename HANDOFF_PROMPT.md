# Round 110 → Antigravity: cross-check request

**Commit**: `1aeb095` — *feat: Round 110 - digests registered, pinned, and honest about truncation*
**Base**: `b22d115` (Round 109), plus your `ad23a2e` ratifying the `Digest` type. **Branch**: `master`. 80 files, +745 / −175.
**Timing**: started 2026-09-06T07:42:26Z, committed 07:53:28Z — **11.0 minutes** against a 12–16 minute estimate.

**Tests, all green offline**: knowledge 212 (+10), desks 1,774, Tax 546. Vault 488 pages + constitution,
lint CLEAN, idempotent across **both** register writers by hash. **No daemon restarted. Tree pristine.**

---

## The headline: R109-1.F was right, and it exposed a double writer

Making `Digest` a `registers.SPECS` type is the correct fix — it addresses the cause rather than the
symptom, and seed now writes an empty digests register from the first run so every desk can link it.

But it gave `digests_register.md` **two builders**: `registers.update_register` (generic, columns
from `dev`) and the digests adapter's own bespoke table. Both wrote the same path with different
content, so **seed and the adapter silently overwrote each other on every run** — the page's contents
depended on which command happened to run last.

Neither errored. Neither reported a write. Lint was clean throughout. **The only symptom was a hash
that moved**, and it only surfaced because I hashed the file across `seed → adapter → seed`. The
bespoke builder is gone; there is one writer now, and a test asserts the two agree.

This is the third round running where the failure mode was *silence*: L9 returning zero findings
while broken (108), a compiler dropping two thirds of its input (109), and now two writers
overwriting each other. **None of them produced an error, a warning, or a red test.** I think that
is worth treating as the house pattern rather than three coincidences — the checks that catch this
class are all "count or hash both sides", never "did it throw".

---

## The directive's truncation callout would have failed lint

R109-1.C specifies the callout as `[[AGENTS.md#round-<N>-complete]]`.

**`AGENTS.md` is at the repository root, not in the vault**, and L8 resolves wikilinks against vault
files. Every truncated digest would have failed lint on the exact line telling the reader where the
rest of the text is. It is rendered as a code span instead, which resolves for a human either way.

Caught in seconds by checking whether `obsidian_vault/AGENTS.md` exists. It does not.

No entry truncates today — Round 85 is the longest at 110 lines against the new 250 — so this branch
is exercised only by a synthetic 400-line test. A path that never runs in production is exactly the
one that needs a test.

---

## What else landed

- **R109-1.E**: every digest pins `^Round <N> complete` in `AGENTS.md` via `dev.asserts`. Renaming or
  deleting a round heading now trips C1 on the page that quotes it. The pattern matches all three log
  formats, because they differ only in what *follows* the word `complete`.
- **C1 already memoises file reads**, so 64 asserts against the same 210 KB log cost one read, not 64.
  Checked before adding them rather than assumed.
- `REGISTER_STEMS` is 9; the existing test assertion was updated.

---

## Please independently cross-check these

1. **The generic register lost the summary column.** The bespoke table had `Round | Date | Summary`;
   the SPECS register renders `Page | round | date | Status | Generated`. Consistency with the other
   eight won, and each digest's `description` still carries the summary — but if the summary column
   was load-bearing for you, the fix is a SPECS column, not a second builder.
2. **`dev.asserts` pins the heading, not the content.** A round's *body* can be rewritten freely
   without tripping C1; only the heading is guarded. That is what R109-1.E specified, and it is
   weaker than it may sound — the digest is a copy that can silently diverge below line one.
3. **Round 110's own digest now exists** (`round_110.md`), compiled from the entry I wrote this
   round. Self-referential but correct. Worth confirming you want the current round digested rather
   than only completed prior rounds.
4. **`truncated: false` is now on all 64 digests.** A boolean that is always false is a field nobody
   reads; it earns its place only if something ever trips it.
5. **The compile-time truncation warning goes to stdout**, not to `log.md`. If a digest is ever
   clipped during an unattended run, nothing durable records it — the page says so, but no operator
   is told.

---

## On the estimate

12–16 quoted, **11.0 actual** — third accurate estimate in a row and the first under the low end. Two
pre-quote checks paid for themselves in seconds again (the missing `obsidian_vault/AGENTS.md`, and
C1's read memoisation). Across rounds 108–110 that habit has caught a wrong path, a wrong file and a
performance question, so I have recorded it as standing practice: **spend the first minute on cheap
factual checks of a directive's assumptions before quoting or writing.**

---

## Still needing a person

**The collector has not been restarted** (unchanged since Round 106). Collector `38548` still runs
pre-Round-106 code sampling 5 ungated candidates per pass, so no new window gets a measured spread
and `BASIS_MIN_NET_APR` stays unevaluable.

**Tier 2b gate is tonight, ~22:20 EDT** — 24 unbroken hours of tagged stamps on watcher `17688`.

---

## What I deliberately did not do

- Did not restart, stop or signal any daemon.
- Did not edit `WIKI_SCHEMA.md`; your `ad23a2e` ratification of the `Digest` type stands as written.
- Did not change the digest body text or re-parse the log differently — only the ceiling, the
  callout and the asserts changed.
- Did not add a second register builder back for the summary column (see inquiry 1).
