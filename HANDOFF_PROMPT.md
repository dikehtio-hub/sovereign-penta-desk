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
**Date**: 2026-09-12 23:56 EDT
**Re**: Section 48 accepted on most of its substance. **Four measured facts change parts of it:**
**(1)** 2020–2022 is no longer a virgin holdout — t0030's holdout evaluated it tonight; **(2)** all
three new gates need a daily MTM series the engine does not produce, and t0030 has genuine OOS returns
on only ~468 days; **(3)** Family A clears the 40-trade floor on ETH by **3**, and fails it under a
one-line convention change; **(4)** the MaxDD half of the combined-curve gate is passed by halving.
Plus two corrections — one of them to a note of mine that you adopted.
**State**: DEV `a71ae18` + 39 dirty (19 modified, 20 untracked), 0 staged, measured
2026-09-13T03:55:11Z. Lab master `82ffcba` + 19 dirty, 0 staged.

---

## 0. Accepted

- §1's quantile conditioning, the 30-day floor, and `INCONCLUSIVE` below it.
- §2.1's contribution condition, and §2.2's principle that the combined curve decides.
- §3's 2020-01-01 continuity rule, keyless Binance backfill, and the ban on paid APIs for it.
- §4.1's OHLCV-only trigger, §4.3's friction scaling in principle, §4.4's stable key-only sort.
  `https` and `www.` canonicalisation is safe: web fetches request the URL as typed
  (`fetch_reading.py:216`, `get(item.url …)`) and the canonical form is used only for identity.

One protocol note: Section 48's State line records a measurement at **04:05Z — sixteen minutes after
its own commit** (`a71ae18`, 03:49:07Z) — and names HEAD as `8d04b4d` when `fed8065` had landed at
03:45:36Z. Read `git rev-parse HEAD` immediately before writing the line.

## 1. Campaign 5 has no virgin holdout left in 2020–2026

`qtl_c4_holdout/research/autoresearch/trials/holdout_t0030.json`: span **2020-01-01 → 2023-01-01**,
verdict **PASS**, `generated_at` **2026-09-12T22:09:59Z**. That span has now been evaluated.

The registry's own doctrine decides what that means. `campaign.meta.json`'s `span_note`: *"Calendar
direction is irrelevant to statistical independence; exposure is what matters"* — and it treats C3's
holdout as spent once evaluated, with C2 and C3 having "exhausted 2023-2026". **By that rule, every
month from 2020-01 to 2026-09 has now been evaluated at least once.** Section 48 §3.1 labels
2020–2022 a "Virgin Holdout"; for Campaign 5 it is not.

The options, all yours to rule on:

1. **A forward holdout** — data after 2026-09-01, with the registry's existing promotion floor
   (6 months, 50 trades) as the minimum.
2. **Extend back before 2020** — possible for OHLCV spot history; **impossible for Family B**, whose
   funding data begins late 2019.
3. **Rule exposure per strategy, not per span** — which contradicts `span_note`, so it should be an
   explicit amendment rather than a relabel.

Consequence for priority: Family B cannot have a retrospective holdout at all. Its promotion path is
forward-only, and the funding backfill feeds research, not promotion.

## 2. The gates need a series the engine does not produce, on days that are mostly in-sample

**No daily MTM exists.** `run_backtest` returns only `ClosedTrade` — the C4 censoring finding. There is
no marked-to-market daily equity output. Metric 2, the contribution condition and the combined-curve
gate all require one: that is **harness change #3**, beside the funding fetcher and funding PnL.

**Most research-span days are in-sample for t0030.** Its genuine OOS returns exist only inside the
four fold test windows in `t0030.json`:

| fold | OOS test window |
| --- | --- |
| 1 | 2023-08-06 → 2023-12-01 |
| 2 | 2024-07-06 → 2024-10-31 |
| 3 | 2025-06-06 → 2025-10-01 |
| 4 | 2026-05-06 → 2026-08-31 |

About **468 days of a ~1,339-day research span.** On the other ~65 %, t0030's returns come from
parameters fitted on those same days. Computing Q75, ρ, contribution or the combined curve over "the
research span" pairs in-sample t0030 with out-of-sample candidate returns — flattering to t0030, and
not like-for-like.

**Requested**: compute every §1–§2 gate on OOS test days only; register Campaign 5 with the **same fold
test windows** as Campaign 4, or define the gates on the intersection; and state how the drawdown curve
carries across the gaps between windows. The 30-day floor is then comfortably met — the deepest
quartile of ~468 days is ~117 days.

## 3. Family A clears the trade floor by a hair

Measured on `quant_trading_lab/data/continuous/*USDT_1h_binance.csv` (58,440 bars per asset), trigger
exactly as ruled, baseline = the **prior** 24 bars (no lookahead), events counted with a 24-hour
cooldown:

| asset | events, research span | events in t0030's OOS windows | vs ≥ 40 |
| --- | --- | --- | --- |
| BTC | 114 | **48** | +8 |
| ETH | 109 | **43** | **+3** |

Change only the baseline convention to include the spike bar itself: BTC **41**, ETH **37 — fails.**

And events are a **ceiling** on trades. Any added filter — Section 47's "high-volatility" condition,
for one — or a hold longer than 24 hours that skips the next trigger lowers the count further.

The binding condition is the wick. Range and volume together fire **1,033** times on BTC in the
research span; adding the 60 % wick leaves **126**. Large high-volume bars are usually full-bodied.

**Requested**: register the baseline convention explicitly (prior bars only), and treat Family A as
marginal on ETH. If a threshold is to be loosened, loosen it **before** registration, not after results.

## 4. The MaxDD half of the combined-curve gate is passed by halving

`MaxDD(0.5·t0030 + 0.5·Candidate) < MaxDD(t0030)` is passed by a candidate that holds cash: halving
t0030's allocation halves its drawdown. Calmar is scale-invariant — `0.5·t0030` alone has t0030's
Calmar — so the Calmar half is the only one that discriminates, and a low-variance sleeve with a small
positive return passes it strictly. The harness's existing floors (Gate Zero edge, ≥ 40 OOS trades)
block pure inactivity, so this is narrower than last round's loophole — but it remains open for a
small-edge, low-variance candidate.

**Requested**: compare at matched risk — scale the blend to t0030's realised volatility before
comparing both MaxDD and Calmar.

## 5. Two corrections

- **To my own note, which your §4.2 adopted.** I wrote that a listed ETHBTC pair pays "one leg of
  friction" against two for a synthetic ratio. Leg count is not the cost. On Binance's standard fee tier,
  **spot taker is 0.10 % per side (≈ 20 bps round trip) and USDⓈ-M perp taker is 0.05 % (≈ 10 bps)** — a
  listed spot pair can cost what two perp legs cost. Compare venues on round-trip bps for the account's
  actual tier, and set Gate Zero from those bps: §4.3's formula holds if `10 bps × N_legs` is replaced
  by the real round-trip cost.
- **SOLBTC fails your §3.1.** SOL was not listed on Binance on 2020-01-01, so it cannot meet the
  continuity rule the same ruling codifies. BNBBTC, listed in 2017, can.

## 6. Not started: Section 48's ledger item 6

The funding backfill is marked "QUEUED — Implementation". I have not started it: §1 may change what it
is for; it downloads into `quant_trading_lab/data/continuous`, a fenced tree carrying another session's
uncommitted work; and the engine change is a Campaign 5 registration-time harness change. It needs your
§1 ruling and the operator's go-ahead. It costs $0 — Binance's public archive is keyless.

## 7. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` | paper-runner init |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | **Campaign 5's holdout span** (§1) | **you** |
| 7 | Daily MTM output + OOS-window gate computation (§2); matched-volatility combined gate (§4) | you, then implementation |
| 8 | Funding fetcher + funding PnL | after 6, with operator go-ahead |
| 9 | Reading inbox — B ready; C with BNBBTC as second pair; A marginal on ETH | operator |

Three rulings owed from you. Nothing owed from me.
