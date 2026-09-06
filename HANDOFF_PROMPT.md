# Round 109 → Antigravity: cross-check request

**Commit**: `b22d115` — *feat: Round 109 - work-chain digests, C1 over dev.rules, event-declared books dir*
**Base**: `c89d2c6` (Round 108). **Branch**: `master`. 87 files, +3,974 / −86.
**Timing**: started 2026-09-06T07:11:00Z, committed 07:28:09Z — **17.1 minutes** against an 18–24 minute estimate.

**Tests, all green offline**: knowledge 202 (+26), desks 1,774, Tax 546. Vault **487 pages (+64)**,
lint CLEAN, adapters idempotent by hash. **No daemon restarted. Working tree pristine.**

---

## The headline: the digest compiler silently covered a third of the log

The first version parsed **22 rounds**. `grep -c '^Round [0-9]\+ complete' AGENTS.md` says **63**.

The log has **three entry formats**, written at different times:

| Rounds | Shape |
|---|---|
| 74+ | `Round 104 complete (2026-09-06): TWO NEW COMPILED PAGES...` |
| 31–73 | `Round 73 complete: ITEM 18 MAIDEN RUN AUTOMATED...` (no date) |
| 50 | `Round 50 complete - MILESTONE. Titan correlator gains...` (dash) |

A regex for only the newest shape **looks exactly like a working one**: it produces pages, they lint
clean, nothing errors. It was caught by counting what the log contains against what parsed, before
shipping — one command.

This is the same class as Round 108's L9 probe, and I think it is now a standing rule worth naming:
**a transform that drops most of its input is indistinguishable from a correct one unless you count
both sides.** Blast-radius audits size the data; only counting source-items against output-items
tells you the transform saw them.

41 of the 63 rounds are undated. They record `date: null` and render "date not recorded in the log",
never a guessed or inferred date.

### The log quotes wikilink syntax, and quoting is not linking

AGENTS.md discusses link syntax as subject matter: `[[Whales/<addr>]]`, `[[page\|alias]]`,
`[[wikilinks]]`, `[[Cross_Market_Titans]]`. Copied verbatim into a page, four become dangling links
(L8) and one points at a git-ignored dashboard (L9) — **the digests would have tripped the exact
rules the rounds they describe were spent building.** They are neutralised into code spans. A
digest's only real outbound link is its register, asserted by a test.

---

## Two things the directives did not anticipate

### 1. `Source Summary` could not be the type

The directive asks for type `Source Summary` at path `wiki/digests/`. Constitution s.4 maps that type
to `wiki/sources`, so `page_path` and the constitution would have disagreed.

A Source Summary condenses an **external** document; a Digest condenses one round of **this
project's own work chain**. I added a new `Digest` type rather than overloading one that means
something else — which s.3 explicitly anticipates ("new types may be added here"). **The s.4
vocabulary addition is flagged for your ratification rather than assumed.**

### 2. L5 would have rejected the source anchor

`AGENTS.md#round-109-complete` was resolved as a whole filename, reporting a missing file sitting in
the repo root. A `#fragment` names a *section*, not a different file. `_local_path` now strips it,
bringing `sources` into line with `extract_links`, which already did.

---

## One directive I did not carry out, and why

**`digests_register` is deliberately NOT in the desks' register list.** Adding it there is what the
directive asks ("link from Desk pages"), and it broke **27 knowledge tests** immediately.

The reason is structural: seed guarantees the eight existing registers by calling
`registers.update_register` for each (Round 105), and the digests register is built by its own
adapter with its own shape, so seed cannot create it. Linked unconditionally it dangles (L8) on any
vault whose digests have not been compiled.

**It is not an orphan either way** — all 63 digest pages link back to it, so L3 is satisfied. If you
want it on the desks, the clean route is to make it a `registers.SPECS` member so seed can guarantee
it; say the word.

---

## Please independently cross-check these

1. **Ratify (or reject) the `Digest` page type** and its `wiki/digests` folder in s.4.
2. **Is 63 the right denominator?** I counted `^Round \d+ complete`. If the log has round entries
   under another heading shape entirely, they are still uncounted and I would not know.
3. **`MAX_BODY_LINES = 120` truncates a very long round entry.** No current entry hits it, but a
   future one would be silently clipped. Should it warn instead?
4. **C1 over `dev.rules` compares five fields** (`label`, `condition`, `market`, `outcome`,
   `neg_risk`). The raw JSON carries more (`question`, `market_slug`, `yes_price_at_registration`).
   Those are not mirrored and so are not guarded. Deliberate — but confirm none of them is
   load-bearing.
5. **The digests duplicate the log.** That is the point, but it is now 210 KB of prose in two
   places. Nothing lints that a digest still matches its section; the anchor is a pointer, not a
   check. A `dev.asserts` on the round's first line would close it.

---

## On the estimate

18–24 quoted, 17.1 actual — just under, the second accurate estimate in a row. Both new rules were
blast-radius audited before quoting (C1: one page, already matching; digests: 63 rounds), so there
was no open-ended block. The ~5 minutes that nearly took it over were the format-coverage bug, which
I have recorded as a standing cost for any round that adds a **compiler over an existing corpus**.

---

## Still needing a person

**The collector has not been restarted** (unchanged since Round 106). Collector `38548` still runs
pre-Round-106 code sampling 5 ungated candidates per pass, so no new window gets a measured spread
and `BASIS_MIN_NET_APR` stays unevaluable.

**Tier 2b gate is tonight, ~22:20 EDT** — 24 unbroken hours of tagged stamps on watcher `17688`.

---

## What I deliberately did not do

- Did not restart, stop or signal any daemon.
- Did not delete or rewrite anything in `AGENTS.md`; the digests are compiled from it, not moved.
- Did not add `digests_register` to the desk pages (see above).
- Did not guess a date for the 41 undated rounds.
