# Round 106 → Antigravity: cross-check request

**Commit**: `8fd7462` — *feat: Round 106 - adapter lifecycle invariant, Desk 1 spread gate, git provenance in L5*
**Base**: `bc9b889` (Round 105). **Branch**: `master`. 110 files, +742 / −321.
**Timing**: started 2026-09-06T05:43:56Z, committed 05:56:54Z — **13 minutes** against a 60–80 minute estimate.

**Tests, all green offline**: knowledge 145 (+8), HyperLiquid + cross-market 1,314 (+3), Sports 223,
Polymarket 237, Tax 546. Vault 423 pages + constitution, lint CLEAN, adapters idempotent by hash.
**No daemon restarted.**

---

## Two directives I did not implement literally, and why

Both were right in intent. Both named the wrong target, and in one case the literal reading would
have destroyed data. Please check my reasoning on each — if I have misread either, the fix is small
but the current code is wrong.

### 1. R104-1 names `incremental_persistence.py`; the gate went in `orderbook_sampler.py`

`storage/incremental_persistence.py` is the **retrospective measurement grid**. It walks a grid of
*past* entry instants and reads spreads through `spread_bps_at`, which is a pure reader of
`orderbook_snapshots`. Polling L2 now cannot tell you the spread at a window that opened three days
ago, so no amount of sampling in that module would ever measure a historical window.

The gate therefore went into `collectors/orderbook_sampler.py`, the live caller. **The gate condition
you specified was exactly right** — `ORDERBOOK_SAMPLE_MIN_APR = BASIS_MIN_FUNDING_APR`, on the
**gross** APR (the gross bar comes first, as in the harvester), while ranking still uses the net
figure where a spread is known.

**The part worth knowing: this costs zero extra REST weight.** `ORDERBOOK_SAMPLE_MAX_COINS = 24` caps
the *total* coins per pass, carries explicit budget arithmetic in its comment, and is unchanged;
`select_sample_coins` enforces it with the priority held > candidates > rotated > core. Raising
candidate slots 5 → 12 **reallocates** budget away from the rotated/core watchlist toward coins the
harvester could actually enter. Your guardrail "zero unconditional polling across 440 coins" is
satisfied structurally rather than by promise.

### 2. The markets re-admission sketch would have written degraded duplicates

`wanted |= {existing Market tokens}` is destructive as written. With no drop record, `compile_market`
falls back to the placeholder question `"Polymarket token abc123…"`, family `"unknown"`, **and a
token-derived slug instead of the market slug**. So an aged-out market would get a second, degraded
page at a *new path* while the good page was orphaned — the note in your ruling that
"`compile_market` already handles `record is None` gracefully" is true of the null-handling but not
of the identity.

Identity is now recovered from the page's own `dev` block. Verified before shipping: 97 tokens, 0 new
pages.

---

## A regression I introduced and caught inside the same round

Removing the `skipped` guard so market pages could be refreshed meant `first_seen` was overwritten
with the newest drop's `fetched_at` **on every run**. That field was accidentally correct before only
because the page was written once and then skipped forever. It is now explicitly the *earliest*
sighting, with a test.

Caught by reading the diff of the first live run — 97 pages showing a changed `first_seen` is not a
plausible refresh. Worth noting as a pattern: **making a frozen thing refreshable exposes every field
that was silently depending on never being rewritten.** If you see other adapters with write-once
fields, they carry the same latent bug.

---

## The provenance audit came back empty, and that is the result

Lint L5 now resolves `git:<sha>` sources and `dev.citations` entries with `git cat-file -e`. I ran the
audit **read-only before building** — the lesson recorded after L8's 86-link surprise — and it found
**5 cited hashes across the vault, all 5 resolving.** Blast radius zero.

The check **skips rather than passes** outside a git repository: reporting "valid" where `git cat-file`
cannot answer would be a lie, and reporting "missing" would be a false alarm.

---

## Please independently cross-check these

1. **Is the sampler the right home for the R104-1 gate?** If `incremental_persistence.py` has a live
   path I did not find — something that runs at window-open rather than over a historical grid — then
   my reading is wrong and the gate is in the wrong place.
2. **Is 12 candidate slots the right number?** The gate itself bounds the set (few coins quote ≥25%
   gross with spot backing above the liquidity floors), so 12 is a safety ceiling, not a target. But it
   does take up to 12 slots from the rotated/core watchlist. If core coverage matters more than
   pre-entry spread coverage, the number should come down.
3. **`report.unmaintained` names pages the adapter cannot rebuild** (a sharp pruned from
   `sharp_traders`) rather than deprecating them. I took Ruling 99-2 to mean a counterparty judgement
   is human, so the adapter reports and does not decide. Confirm — the alternative is auto-deprecation.
4. **Did I miss a moving window?** I fixed titans, sharps and markets. `journal`, `clob`, `calendar`
   and `theses` may have the same shape and I did not audit them.
5. **The `first_seen` class of bug.** Any adapter field that was write-once by accident is now at
   risk wherever R105-2 made pages refreshable. I checked markets; I did not sweep the others.

---

## On the estimate: I over-corrected

I quoted 60–80 minutes and took 13. That is the mirror image of last round's 25–35 quoted against two
hours, and the cause is instructive: **the audit-first discipline worked.** Running the new lint rule
read-only took two minutes and turned the open-ended part of the estimate into a known-small number
immediately; reading the target module first revealed the wrong-file problem before I built anything
on it. The lesson recorded is not "estimate higher" but "when part of an estimate is
unknown-until-measured, measure it first and re-quote rather than padding the whole number."

---

## Still needing a person

**The collector has not been restarted.** Ruling R104-1's daemon policy said not to, and I did not —
collector `38548` is still running the pre-Round-106 code that samples 5 candidates per pass. Until it
restarts, **no new window gets a measured spread and `BASIS_MIN_NET_APR` stays unevaluable.** Nothing
breaks if you wait; the backlog of unmeasured windows simply keeps growing. It is in `HOMEWORK.md` as
an operator decision.

---

## What I deliberately did not do

- Did not restart, stop or signal any daemon; watcher `17688`, exporter `62760`, supervisor `46740`,
  collector `38548` all untouched.
- Did not change `ORDERBOOK_SAMPLE_MAX_COINS`, `ORDERBOOK_SAMPLE_INTERVAL`, or the REST budget
  arithmetic they document.
- Did not change the `basis_realised_windows` schema.
- Did not commit the exporter-written dashboards.
- Did not auto-deprecate any counterparty page.
