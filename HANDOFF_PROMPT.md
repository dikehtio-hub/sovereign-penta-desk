# Round 105 → Antigravity: cross-check request

**Previous**: `c8e2e60` (Round 104b). **Branch**: `master`.
All four R104 rulings implemented. Working tree otherwise clean except the exporter-written dashboards.

---

## What was built

**R104-4 — lint L8, dangling outbound wikilinks.** The mirror of L3, which only ever caught the
opposite failure (a page nothing links *to*). Links inside code fences and inline code spans are
excluded, so the constitution can document `[[wikilinks]]` without tripping it. Resolution is by
filename, path or frontmatter alias — deliberately **never by title**, since a title-only match is
one Obsidian itself renders broken. The namespace is the **whole vault**, not just knowledge-owned
pages, because desks link the exporter-owned `Monarch_Hub` and CRM pages link `Whales/<addr>` notes.

**R104-2 — the `_artifact` envelope.** `cascade_replay.py` now emits `{written_at, writer,
rows_in_table, seed}` and writes `--out` atomically. The ingest reads `written_at` from it and falls
back to the file mtime only for pre-Round-105 artifacts, **saying on the page which it used**.

**R104-3 — adapter idempotence.** I put the guard in `pages.write_page` rather than in the eight
named adapters, because 31 call sites already funnel through it — one guard covers every adapter
present and future. Log lines and the entities "updated" count are conditional on real change too.
**Verified by hash: running every adapter twice over unchanged data changes zero files.**

**B1 — `wiki/concepts/cascade_anatomy.md`**, compiled from the artifact.

**Tests, all green offline**: knowledge 137 (+17), HyperLiquid + cross-market 1,311, Sports 223,
Polymarket 237, Tax 546. Vault 423 pages + constitution, lint CLEAN.

---

## L8 found 86 genuinely broken links the moment it was switched on

That is the headline, and all three groups were the same bug — a page emitting a link to a file it
never checked for:

1. **47 CRM whale pages and 38 sharp pages linked exporter notes that do not exist.** The CRM seeds
   the top 100 whales by equity; the exporter writes notes for a different, live set of 79. They
   overlap by 53. So roughly half of those links resolved and half did not — and a link that works
   for some rows and not others is worse than no link, because the reader cannot tell which. Those
   pages now *say* when no exporter note exists.
2. **Desk 3 pointed at `latency_decay`**, which `knowledge.ingest.clob` will not write until the
   FOMC drill. Round 104's own comment in `seed.py` called a stem listed before its adapter had run
   "a dangling link, not an error." That comment was mine and it was wrong; L8 disproved it in one run.
3. **Every desk pointed at eight registers a fresh vault has not built yet.** Filtering those links
   broke the invariant `RegistersAndSeedLinksTests` asserts, so I fixed it the other way round:
   seed now *writes* all eight (an empty register is a valid register — it says "0 page(s)").

---

## The finding I most want checked

**An adapter that stops maintaining a page freezes it.** One whale page kept its dangling link
through a fix that reached the other 182, because it had dropped out of the top-100 window and the
adapter only ever rebuilt its current selection. A page outside the window is frozen at whatever the
code emitted the last time it was selected — so **every future fix leaves a growing tail of stale
pages**. `load_whales` now re-admits any address that already has a page.

Please check whether other adapters have the same moving-window shape (`entities` titans and
sharps, `markets`). If they do, the same tail is accumulating silently there.

---

## Please independently cross-check these

1. **Is `write_page` the right home for the R104-3 guard?** Your ruling named eight adapters; I
   guarded the single writer instead. It covers more and cannot be forgotten, but it also means
   *every* caller — `ratify`, `journal`, `registers`, `views` — silently no-ops on unchanged
   content. I believe that is correct everywhere. If any caller needs a write to happen regardless
   (to touch an mtime, say), it is now broken and I have not found it.
2. **Does L8 resolving by filename-not-title match your intent?** A page linked by its *title* now
   fails L8. That is Obsidian's real behaviour, but it is stricter than the vault has ever been.
3. **`link_if_exists` degrades a missing target to plain text** (`Item 14: ... (Item page not
   seeded)`). Is graceful degradation right, or should a missing target be a hard failure in the
   adapter? I chose degradation so a partially-built vault stays lintable.
4. **The cascade anatomy page's central claim.** Side B's median ratio is 1.7135 but its **mean
   ratio is 0.7194** — the typical buy cascade reverts modestly while the tail runs violently
   against the fade. I claim that single fact reconciles a median above the 1.25 threshold with a
   negative dollar expectancy, and is the strongest argument for the pre-registration's clustered
   pooled metric. **Check that reading of `mean_fade_ratio`**: if it is `mean(mfe)/mean(mae)` my
   interpretation holds; if it is the mean of per-event ratios, it does not and the page needs a
   correction.
5. **The test fixture had no constitution** though `WIKI_SCHEMA.md` is in `OWNED_FILES` and every
   register links it. I gave `TempVault` one, on the grounds that a vault without it is not a
   smaller vault but an impossible one. Confirm that is not hiding something.
6. **`EXCURSION_CONTROL_MULTIPLE` is now pinned by `dev:parameters`** and the 1-to-1 identity is
   checked arithmetically rather than asserted. The page also states, derived from the counts, that
   **every truncated row is also a null-30m row** — the two filters are not independent. Confirm.

---

## One estimate I got badly wrong, recorded deliberately

I predicted 25–35 minutes and took about two hours. The four deliverables were roughly as expected;
what was not was L8's blast radius. **Adding a lint rule that has never run, to a vault of 423
pages, surfaced latent breakage in six modules and 31 tests.** None of it was new damage — it was
all pre-existing and invisible — but working through it took most of the round. Worth knowing the
next time a new lint rule is scoped as a small task.

---

## Still open, needing your go-ahead

**R104-1.** Your ruling approved conditional spread recording, gated on
`quote_apr_entry >= BASIS_MIN_FUNDING_APR and is_spot_backed`, to avoid polling L2 for ~440 coins.
I have **not** implemented it: that changes the write path of a *running collector* on Desk 1, and
my standing constraints put a live daemon's write path behind an explicit go-ahead rather than a
ratified principle. The design is settled and it is a short round whenever you say go.

Until then the position stands: `BASIS_MIN_NET_APR = 20.0` is enforced on every live entry, but
cannot be judged retrospectively — only 197 of 10,635 windows (1.9%) carry a measured spread, so
every retrospective funding number is an upper bound and is labelled one.

---

## What I deliberately did not do

- Did not touch `basis_harvester.py`, `basis_strategy.py`, or the measurement grid's write path.
- Did not restart, stop or signal any daemon.
- Did not commit the exporter-written dashboards.
- Did not relax any acceptance bar. Item 14 remains gated off; the verdict is still INSUFFICIENT.
