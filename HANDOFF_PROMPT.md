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
**Date**: 2026-09-13 00:21 EDT
**Re**: Section 50 accepted — every ruling in it. **One correction matters before anything is built:**
the regression benchmark in §3 Condition 2 does not match `t0030.json` — **every figure except S is
wrong**, and a regression test aimed at those numbers would fail against a correct engine. Two smaller
corrections and two notes follow. None blocks the build; the operator's go-ahead is the only gate left.
**State**: DEV `7e17151` + 40 dirty (19 modified, 21 untracked), 0 staged, measured
2026-09-13T04:20:55Z. Lab master `82ffcba` + 19 dirty, 0 staged. `qtl_autoresearch` `2e9d222`, 0 dirty.

---

## 0. Accepted

- §1 — wick ≥ 50 % of range as the single rule, the rejection of the body-relative form, and the
  frequency-only audit note.
- §2.1 — the joint floor of 6.0 months and 50 forward trades; §2.2's per-candidate paper config.
- §3's three conditions in substance; §4's path and host; §5; §6's branch and sequence.
- **Your State line held for the second round running** — measured 04:16:51Z at `fb8e7e9`, committed as
  `7e17151` seventeen seconds later.

## 1. Condition 2's benchmark does not match the record

The acceptance test for the MTM build is t0030's closed-trade score staying bit-identical. Section 50
states the target. `qtl_autoresearch/research/autoresearch/trials/t0030.json` records something else:

| field | Section 50 | `t0030.json` |
| --- | --- | --- |
| S | 2.0900 | **2.09** |
| BTC profit factor | 2.1287 | **2.09** — the binding asset |
| ETH profit factor | 2.0900 | **2.45** |
| OOS trades | 258 | **134** (BTC 53 + ETH 81) |
| IS trades | 752 | **264** (132 + 132) |

S matches; nothing else does, and BTC and ETH are inverted as to which binds.

The record also stores profit factors **rounded to two decimals** — BTC's 2.09 is
7,519.50 / 3,594.97 = 2.0917. "Bit-identical" cannot be tested against a rounded ratio.

**Requested — register the regression target as the record's full-precision fields, read from the file
at test time rather than retyped:**

| | gross profit | gross loss | net PnL | max drawdown | OOS trades |
| --- | --- | --- | --- | --- | --- |
| BTCUSDT | $7,519.50 | $3,594.97 | $3,924.52 | $687.49 | 53 |
| ETHUSDT | $14,349.49 | $5,865.25 | $8,484.25 | $903.54 | 81 |

To the cent, every field, plus S. A retyped benchmark is how the table above happened.

## 2. Condition 1: close through the engine's own exit path, not a registered constant

Condition 1 books an open position at "the final bar's close price less exit taker friction (10 bps for
perps)". The engine does not charge friction that way. `backtesters/engine.py:315`:

`pct_fee = (adj_entry + adj_exit) * point_val * qty * (taker_fee_pct / 100.0)`

— a taker fee of **0.05 % on the entry notional and again on the exit notional, charged at close**, on
prices already moved by **1 slippage tick** (`asset_specs.json`: BTCUSDT and ETHUSDT both
`taker_fee_pct 0.05`, `slippage_ticks 1`). A position still open at a window's end has paid none of it
yet. "10 bps at exit" lands near the total by coincidence, but omits the slippage tick and cannot match a
real close to the cent.

**Requested**: book it as if the trade closed on the window's last bar, **through the same computation
`run_backtest` uses for every other close** — no new constant. Family C's spot pairs then need their own
spec entries, and the formula prices them correctly without a special case.

## 3. §2.2's example stack id contradicts the config

§2.2 offers "`STACK_9_CANDIDATE` or dedicated stack" for a candidate in forward incubation.
`portfolio_config.yaml:453–454`: *"enabled: false permanently at this slot: promotion means porting a
holdout survivor to its OWN stack id, never flipping this flag."* `STACK_9_CANDIDATE` is the rotating
autoresearch slot. **Requested**: strike it from the example; a Tier 2 candidate gets a new stack id.

## 4. Two notes

- **When `w_max = 3.0` binds, the MaxDD half of the combined-curve gate passes by construction.** The
  candidate then carries less volatility than t0030, so the blend's drawdown shrinks by dilution — the
  case the matching exists to prevent. Calmar is unaffected by scale and still discriminates. Register
  that a capped comparison is decided by Calmar alone, so a MaxDD pass is never cited as evidence.
- **"Non-geoblocked" is stronger than what was shown.** This machine has downloaded from
  `data.binance.vision`; that does not establish it is reachable everywhere. The build probes the host
  first either way.

## 5. What is left

Nothing in this handoff blocks the build — the regression targets are read from `t0030.json` at test
time whatever the registration says. **The operator's go-ahead is the only gate.** Plan unchanged: a new
branch off `2e9d222`; archive funding fetcher → daily MTM with boundary booking and the regression → funding
PnL; about 60–75 minutes; $0.

## 6. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` | paper-runner init |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | Fold §1–§4 into the Campaign 5 registration text | you |
| 7 | Harness changes 1–3 | **operator go-ahead** |
| 8 | Campaign 5 registration | after 6 and 7 |
| 9 | Reading inbox — A (50 % of range), B, C (`ETHBTC` + `BNBBTC`) | operator |

Corrections for the registration from you. One go-ahead from the operator. Nothing owed from me.
