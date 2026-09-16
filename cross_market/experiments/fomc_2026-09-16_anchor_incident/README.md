# Anchor incident — FOMC drill 2026-09-16

The drill's first survival curve was anchored 624.558 s late and measured nothing.
It was re-anchored to the release instant and re-ingested. This directory holds the
original artifacts so the correction is auditable. **Nothing here is a result.**

## What happened

`latency_sniper.py:641` sets `anchor = event.observed_at` — the instant written into
`event.json`, not the registered `release_utc`. `knowledge.drills.event_json` defaults
`observed_at` to *now*, so the anchor is whenever the operator typed the command.

Timeline (EDT):

| Time | Event |
|---|---|
| 13:58:00.80 | recorder fired (scheduled task), 419 polls, 1257 stamps, 0 failures |
| 14:00:00 | statement: **+25 bps**, target range 3.75–4.00% |
| 14:05:02.48 | recorder exited clean, duration 421 s |
| 14:06:05 | operator wrote `event.json` with `--bps 0` (hold) — wrong number |
| 14:10:24 | operator corrected to `--bps 25 --force` — **correct number, but 10 min after the print** |
| 14:11 | curve run: anchor 18:10:24.558Z, `post_print_stamps: 0`, every summary field null/zero |
| 14:13 | originals archived here |
| 14:15 | re-anchored to 18:00:00Z, curve re-run, vault re-ingested |

The wrong number at 14:06 is not the cause. Even the correct `--bps 25` at 14:10:24
produced an empty curve, because the recording had already stopped at 14:05:01 —
all 419 stamps fell *before* the anchor.

## Cause

Claude Code instructed the operator to run `event_json` at 14:04 and to correct it at
14:10, without checking that `observed_at` is the curve anchor. The drill card lists
`write ./event.json` as step 1 but does not say the default timestamp becomes T0, and
nothing in the tool warns when the anchor lands outside the recording window.

Not caused by: the recorder (fired on time, clean exit), the books (1257 stamps intact,
0 failures, 0 rate-limited), the exporter (not on this path), or the operator.

## Why 18:00:00Z is the defensible anchor

Pre-registered before the print, in `lead_lag_phase2_fomc.meta.json`:

- `baseline_offset_s: -5` — "the forward-filled value at **17:59:55Z**"
- window `17:58:00Z .. 18:05:00Z`, `pre_s: 120`
- `fomc_2026-09-16.rules.json` → `release_utc: 2026-09-16T18:00:00+00:00`

The registration fixed T0 at the release instant in advance. Re-anchoring restores the
registered value; it does not select one. `anchor_minus_release_s` is now exactly `0.0`,
which is self-evidently the release instant rather than a typed-in time.

**Conservative Modification Precedent (Section 82):** post-disclosure modification is
admissible only if it makes passing strictly harder. This change was made *after* seeing
the flat result, so it is disclosed in full here. It is not a hurdle change — it corrects
a clerical timestamp to a pre-registered constant. The direction-of-difficulty test does
not apply cleanly; the disclosure requirement does, and is met by this file.

## Files

| File | sha256 (first 16) | What it is |
|---|---|---|
| `event_anchor_18-10-24Z.ORIGINAL.json` | `766f29d960b57cce` | the 14:10:24 event file, correct bps, late timestamp |
| `curve_anchor_18-10-24Z.ORIGINAL.json` | `3c77874bc930b76b` | the empty curve it produced |

The five vault pages written from the original curve (3 profiles, the event page,
`latency_decay.md`) were **overwritten** by the re-ingest. They are recoverable from git
if ever needed; they contained no valid measurement.

## Result after correction

Only `hike 25 bps` is live; the other two are neg-risk NO sides, deferred under Ruling R4.

```
baseline_notional   87,221.29   at T-0.062 s
pre_print_stamps          119
post_print_stamps         300
first_change_s          0.939
half_s                  1.939
tenth_s                 5.942
gone_s                  5.942
max_post_notional   78,225.09
notional_seconds   162,777.46
```

## Post-drill fixes queued

1. `event_json` should default `observed_at` to the event's registered `release_utc`
   when one exists, not to `now`.
2. `--survival-curve` should FAIL, not silently return zeros, when the anchor falls
   outside `[window_start, window_end]` — `post_print_stamps == 0` with a non-empty
   book set is a defect, not a result.
3. The drill card's step 1 should state that `observed_at` becomes T0.
