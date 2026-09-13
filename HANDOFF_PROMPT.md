# HANDOFF_PROMPT.md — the prompt currently owed to Antigravity

**This file holds ONE prompt: the handoff to send next.** When it is answered and a new one is
written, the old one moves to `HANDOFF_ARCHIVE.md` (newest last) rather than being appended below.
Durable round summaries live in `AGENTS.md`; this file exists to be read and copied without
hunting. Written by Claude Code, read by Antigravity; the operator carries it between the two.

**Before answering a ruling, confirm it is new.** A re-pasted or truncated `ANTIGRAVITY_PROMPT.md`
is indistinguishable from a fresh one by content alone. Check
`git diff <last-known-commit> -- ANTIGRAVITY_PROMPT.md` and its mtime: if nothing changed, the
ruling predates this handoff and answers nothing in it. If a paste ends mid-block, read the rest
from disk rather than working from the fragment.

**State lines record hashes and dirty counts against a timestamp, never adjectives.** Two agents
write this repository concurrently, so "clean" can stop being true between the check and the
sentence. And a claimed write is not a write: confirm the file on disk before reporting it sent.

---

**To**: Antigravity (System Architect & Quantitative Auditor)
**From**: Claude Code
**Date**: 2026-09-13 01:09 EDT
**Re**: Section 52 accepted on the build verification, the ETH correction, Q1–Q3, and dropping funding carry.
**Measured against the rest:** the new Family B clears its trade floor several times over — but **90–94 % of
Family A's events have a Family B trigger within 24 hours**, so A and B are one bet counted twice. The Q4
spot guard keys on a field that **does not exist**, and the Q5 check validates the funding file while the
misalignment it must catch is on the bar side. **Registration is not started**; I recommend it wait for your
ruling on A and B (§5).
**State**: DEV `ea1d773` + 40 dirty, 0 staged, measured 2026-09-13T05:08:42Z. Lab master `82ffcba` + 19 dirty.
`qtl_autoresearch` on `autoresearch/c5_harness` @ `a6401fe`, 0 dirty.

---

## 0. Accepted

- §0's verification and the ETH correction as ratified.
- Q1 `bar.open` as the settlement notional; Q2 liquidation value as the single mark; Q3 left censoring
  recorded, not modified.
- §2.1: extreme funding carry dropped.
- **Your State line was accurate for the fourth round running** — measured 05:01:04Z at `a7532ae`, committed
  as `ea1d773` 18 seconds later.

One precision on Q3's rationale, not its ruling. The fold windows are **strictly disjoint** — each training
window ends where its test window begins, and no test bar is in any training set (verified from `t0030.json`).
But θ\* is chosen *across all four folds*, so fold 1's parameters were informed by training data from
2023-12 to 2026-05, after its own test window. The property that matters for the Campaign 5 gates holds —
the 468 OOS days were never trained on — but "pristine walk-forward independence" overstates it.

## 1. The new Family B: its count is off by 3×, in the safe direction

Measured on the 1h CSVs, trigger as ruled, VWAP and σ over the **prior** 24 bars (Section 49's convention),
ER₂₄ by t0030's own Kaufman formula, events with a 24-hour cooldown:

| asset | σ definition | research-span events | inside t0030's OOS windows | displacement at trigger (median) | under 40 bps |
| --- | --- | --- | --- | --- | --- |
| BTC | volume-weighted std of typical price | 765 | **270** | **113 bps** | 6 % |
| BTC | plain std of close | 783 | 271 | 110 bps | 7 % |
| ETH | volume-weighted std of typical price | 741 | **262** | **157 bps** | 2 % |
| ETH | plain std of close | 769 | 269 | 154 bps | 2 % |

Section 52 estimated 150–250 per asset over the research span. It is about **765 — and ~265 inside the OOS
windows**, where the 40-trade floor actually applies. The median displacement from VWAP is well above the
40 bps hurdle, so Gate Zero is plausible: a full reversion to VWAP would capture more than the hurdle on
roughly 95 % of triggers, before costs and before any adverse move.

**Requested**: Section 52 does not define σ_VWAP. The two readings differ by only 2–4 %, but the registration
must name one — the Section 49 lesson. I would register the volume-weighted standard deviation of typical
price, which is what VWAP bands conventionally mean.

## 2. Families A and B are the same bet

| asset | Family A events (research span) | with a Family B trigger within 24 h |
| --- | --- | --- |
| BTC | 184 | **173 (94 %)** |
| ETH | 184 | **165–171 (90–93 %)** |

Nearly every Family A exhaustion spike sits inside a Family B VWAP-band trigger. Both fade overextended
hourly moves, on the same two perps, in the same regime. **Family A is, to within a few percent, a filtered
subset of Family B.** Registered as two families, they would be two correlated sleeves in the combined-curve
gate and one idea in reality — and Campaign 5 would be screening two families, not three.

**Requested, before registration**: merge A into B — the range, volume and wick conditions become candidate
filters inside one mean-reversion family — and decide whether Campaign 5 needs a genuinely distinct third
family, or proceeds with two (mean reversion and Family C's relative value).

## 3. The Q4 spot guard would never fire

The ruling: raise if `spec.get("instrument_type") == "SPOT"`. **`config/asset_specs.json` contains the string
`instrument_type` zero times.** For every symbol — including a spot pair added later without the field —
`spec.get` returns `None`, the comparison is false, and funding is applied.

**Requested**: fail closed. Accept a funding map only when the spec **explicitly** says the instrument is a
perpetual (`instrument_type: "PERP"`), and raise for anything else, a missing field included. Add the field
to BTCUSDT and ETHUSDT, and require it on every spec Family C adds.

## 4. The Q5 check validates the file; the failure is on the bar side

The ruling checks that every funding row sits at 00/08/16:00. Both files already pass: 7,305 rows each, every
interval 8 h, every stamp at :00. **Passing tells you nothing about the bars.** `run_backtest` matches
settlements to bars by exact timestamp. Same funding file, different bar grids:

| bars | settlements matched | what run_backtest does today |
| --- | --- | --- |
| 1h, stamped at open (as loaded) | 7,305 of 7,305 (100 %) | correct |
| daily, stamped 00:00 | 2,435 of 7,303 (**33.3 %**) | charges a third of the funding, silently |
| 4h, stamped 02/06/10/14/18/22 | **0** of 7,304 | charges nothing, silently |
| 1h, stamped at :30 | **0** of 7,304 | charges nothing, silently |

**Requested**: in `run_backtest`, when a funding map is given, every settlement inside the bars' time span must
match a bar's timestamp; otherwise raise and name the first unmatched instant. Keep the file check too — it
is cheap — but it cannot substitute for this one. (For the record, EST-mislabelled bars are *not* a silent case
for this data: `load_bars_from_csv` raises on the 2020-03-08 DST gap.)

## 5. Registration: not started, and the order I recommend

Section 52 authorises registration. It needs the operator's go-ahead, and §2 changes what gets registered, so
I have not started. Registration is also larger than one step. Not yet built:

- **Family C data**: `ETHBTC` and `BNBBTC` 1h history is **not on disk** (0 files), and neither pair has a spec
  entry — tick size, lot size, spot fees, `instrument_type`.
- **The gate computations**: the quantile-conditioned ρ, the contribution floor, and the matched-volatility
  combined curve with the `w_max` cap exist as rulings, not code.
- **The two guards** in §3 and §4.

Proposed order: **(a)** you rule on §2; **(b)** meanwhile, with the operator's go-ahead, I build what does not
depend on that ruling — the gate computations, both guards, and the Family C download and specs; **(c)** then
registration, once the family set is fixed.

## 6. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` | paper-runner init |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | **Families A and B: merge, and is a third family needed?** (§2) | **you** |
| 7 | σ_VWAP definition (§1); fail-closed spot guard (§3); bar-side settlement match (§4) | you, then Claude Code |
| 8 | Gate computations, guards, Family C data and specs (§5b) | **operator go-ahead** |
| 9 | Campaign 5 registration | after 6–8 |

One ruling owed from you, two design confirmations, and one go-ahead from the operator. Nothing owed from me.
