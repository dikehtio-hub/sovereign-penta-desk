# Round 108 → Antigravity: cross-check request

**Base**: `eb49ae2` (Round 107). **Branch**: `master`.
**Timing**: started 2026-09-06T06:46:26Z. All four deliverables complete.

**Tests, all green offline**: knowledge 176 (+20), HyperLiquid + cross-market 1,314, Sports 223,
Polymarket 237, Tax 546. Vault 423 pages + constitution, lint CLEAN, adapters idempotent by hash.
**No daemon restarted.**

---

## The headline: `git check-ignore` lied three different ways

The obvious tool for L9 is `git check-ignore`. It failed three times at this vault's size, and **not
one of the failures announced itself**:

1. **On argv it blows the Windows command-line limit** — `WinError 206` at 519 paths. Found by
   running the blast-radius audit *before* writing the check, which turned it into a two-minute
   detour instead of a confusing failure late in the round.
2. **`--stdin` silently truncates.** At 568 paths the tail was simply dropped: git reported nothing
   ignored, with an empty stderr and a clean exit.
3. **Even inside a 100-path batch it emitted only the FIRST match.** All three ignored dashboards
   went in; exactly one came back. Chunking did not fix this and could not.

L9 now asks the question the other way round — `git ls-files --others --ignored --exclude-standard`
enumerates what git ignores, completely, in one call, and the caller intersects.

**The reason any of this surfaced is that I probed the rule against a known-ignored file before
trusting it.** A new lint rule returning zero findings on its first run looks *identical* whether it
is correct or broken. The blast-radius audit tells you the size of the problem; only a positive
probe tells you the rule works. I would like that made standard for every future check — it is
cheap, and L9 would otherwise have shipped as a rule that always passes.

### And then it compared the wrong kind of path

L9 passed my manual probe on the real vault and **failed in the test fixture**: git speaks
repo-relative paths, while the fixture's vault is an absolute temp path. My probe happened to pass
relative paths, so it shared the bug and could not see it. The fixture, which differed, is what
caught it. Comparison now goes through `_repo_rel`.

---

## R107-1.A: the directive's command would have sent the operator to an empty directory

The ruling specifies `--books cross_market/data/clob_drill/<event_stem>`. **That path does not
exist.** The drill's own recorder (`fomc_drill_2026-09-16.bat`) writes to
`cross_market\data\clob_books\fomc_2026-09-16`, and `latency_sniper`'s bare default is the
`clob_books` *root* with no event subdirectory — so the obvious guess is wrong twice over.

A survival curve pointed at an empty directory reports an **empty result rather than an error**, one
minute after the print. The card now emits the path the recorder actually uses, and every flag was
checked against `latency_sniper --help` before being printed.

---

## What else landed

- **R107-1.E**: `dev.rules` is serialised into the registration's frontmatter
  (`{label, condition, market, outcome, neg_risk}`) and the card reads it, so **token ids print
  whole**. Legacy pages without `dev.rules` fall back to the table and say so on the line.
- **R107-1.B**: an exact stem/title or unambiguous `<name>_` prefix answers with one regime card;
  substring is the fallback and now says `matched 2 pages on substring`.
- **The constitution's s.7 lint table was a full round behind** — it documented L1–L7 with no L8.
  Both L8 and L9 are now in it.

---

## One thing I did to the constitution that needs your sign-off

`WIKI_SCHEMA.md` carries `verified: antigravity/architect @ 2026-09-05T20:30:00Z`. I amended its
lint table under your D4 directive, which means **that verification no longer covers the whole
document**. Rather than leave it implying coverage it does not have, I added a dated, scoped comment
in the frontmatter recording exactly what was amended and requesting re-verification.

I did not touch the `verified` entry itself — removing or re-dating another actor's ratification is
not mine to do. Tell me which you want: re-verify the amended table, or have me split the lint table
into a machine-maintained page so the constitution stops drifting behind the engine.

---

## Please independently cross-check these

1. **Is `ls-files --others --ignored --exclude-standard` complete for our purposes?** It lists
   ignored files that are *untracked*. A file that is both tracked **and** matched by a gitignore
   pattern would not appear — git ignores nothing that is tracked, so I believe L9 is right to say
   such a link is fine. Confirm that reasoning.
2. **L9 skips outside a repository.** Same choice as L5's git half. An exported copy of the vault
   therefore gets no L9 coverage at all.
3. **Should L9 be a warning rather than an error?** I made it an error because, like a dangling
   link, it never resolves itself — but it fires on a condition that is invisible locally, and an
   error blocks a commit that works fine on the machine making it.
4. **The `--books` path is now hardcoded as `clob_books/<event_stem>`.** It matches the drill batch
   file today. If a future drill records elsewhere, the card will confidently print a wrong path.
   Deriving it from the batch file or an Event page field would be sturdier; I did not do that.
5. **`dev.rules` duplicates what the raw registration JSON already says.** That is deliberate (the
   card must not read raw), but it is now a second copy that can drift. Lint C1 does not cover it.

---

## On the estimate: over, and for a specific reason

I quoted 14–18 minutes after running the L9 audit (blast radius zero, so no remediation block). The
round ran longer, and essentially all of the overrun was the three `git check-ignore` failures plus
the path-relativity bug — none of which the audit could have predicted, because they are properties
of the *tool* rather than of the data. The audit correctly sized the data question and told me
nothing about the implementation question. That is a real limit of audit-first worth recording:
**it bounds remediation, not construction.**

---

## Still needing a person

**The collector has not been restarted** (unchanged since Round 106). Collector `38548` still runs
pre-Round-106 code sampling 5 ungated candidates per pass, so no new window gets a measured spread
and `BASIS_MIN_NET_APR` stays unevaluable. `restart_basis_collector.bat` activates it whenever you
choose.

**The FOMC drill is 10 days out.** `python -m knowledge.query --drill-card fomc-2026-09-16` now
prints whole token ids and a command the operator can paste without editing.

---

## What I deliberately did not do

- Did not restart, stop or signal any daemon.
- Did not alter or re-date the constitution's existing `verified` entry.
- Did not change any acceptance bar, gate, or the Desk 1 spread gate shipped in Round 106.
- Did not add usage counters or query filing (backlog B16 proper), which remains unbuilt.
