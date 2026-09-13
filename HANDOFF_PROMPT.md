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
**Date**: 2026-09-13 13:19 EDT
**Re**: **DEFECT-ENG-001 is fixed and measured** on `quant_trading_lab` branch `bugfix/engine-slippage-signs`
(`9c87974`), with the same correction carried to `autoresearch/c5_harness` (`a3c0464`), where t0030 was re-scored
(§1). **The operator chose Path B** — park autoresearch, incubate t0030 — with one amendment: the paper runner starts
**after** the 09-16 drill (§2). Three corrections to Section 56 as written, one of them to the order it gave (§3). One
new defect, outside the lab: **the Hyperliquid collector has been silently discarding trade batches since 09-11** (§4).
**State**: DEV `d0d046c` + 41 dirty, 0 staged, measured 2026-09-13T17:19:56Z. Lab master `82ffcba` + 19 dirty. `qtl_autoresearch` on `autoresearch/c5_harness` @ **`a3c0464`**, 0 dirty. **New worktree `qtl_slipfix` on `bugfix/engine-slippage-signs` @ `9c87974`, 0 dirty** (off master `82ffcba`, not merged). `qtl_c4_holdout` `628d6fe`, 0 dirty.

---

## 0. Accepted

- §1: Families 1 and 2 closed at Gate Zero; no filter hunting.
- §2: `DEFECT-ENG-001`, the fix formula, the branch name, the audit before any merge.
- §3: the two paths, as put to the operator.
- §4: all five confirmations.
- **Your State line was accurate for the eighth round running** — measured 07:31:06Z at `6579c35`, committed as
  `d0d046c` at 07:33:20Z; all four repositories matched.

## 1. DEFECT-ENG-001 — fixed, measured, not merged

**Fix** (`bugfix/engine-slippage-signs` @ `9c87974`, worktree `qtl_slipfix`, off master `82ffcba`): `entry + d·slip`,
`exit − d·slip`, in the **three** copies master carries — `backtesters/engine.py`, `test_portfolio_concurrent.py`'s
`_close_trade`, and `test_stack6_smt.py`'s own loop. Section 56 named one. Every pinned number that included PnL was
regenerated on the corrected engine: the Core 3 portfolio baseline, six golden-master constants, and two breakeven-trail
bounds that now compute the exact friction from the spec instead of a `> −20` guess. Lab suite **158 passed, 0 failed**
(the tracked tests; the untracked ones in master's working tree are not in a worktree), plus the same pre-existing
collection error.

**Audit** — `backtesters/DEFECT_ENG_001_SLIPPAGE_AUDIT.md` on that branch. All 18 `validate_real_edge.py` runs, same
data, same random seeds, before → after:

| | |
| --- | --- |
| trade counts | identical in all 18 (slippage moves no stop, target or size) |
| total net across the 18 | −$243 → −$2,354 (**−$2,110**) |
| profit factor crossing 1.0 | none |
| net PnL changing sign | one — Stack 0 on 1m, +$153 → −$7 on 14 trades, already LOW-CONFIDENCE |
| per-trade cost | MNQ $2 a contract; Stack 4 on 1m pays most, −$732 on 91 trades |
| Core 3 portfolio baseline (frozen fixtures) | 150 trades unchanged; net **$8,636.18 → $8,112.06 (−6.1 %)**; max DD $1,678 → $1,815; `hwm_halted` still False |
| t0030 (c5 branch) | BTC −$1.59, ETH −$5.42; **the delta is the slippage to the cent**; θ*, fold trade counts, S = 2.09, all gates unchanged |

**t0030's re-baseline** (`a3c0464`): `trials/t0030.json` is **not** rewritten — its sha256 is pinned in `ledger.tsv`
and it is the record of what the loop scored. The corrected score is `trials/t0030_defect_eng_001_rescore.json`; the
harness regression test pins that file and a new test asserts the record differs from it by exactly the slippage.
`gate_zero.measure` now counts the two slippage fills as friction, so Gate Zero's gross stays the pure price return —
re-run, every Family 1 gross figure is unchanged, only friction moved (+$314 BTC, +$446 ETH). c5 suite **312 passed, 0 failed (was 310)**.

Not re-run, left as records: `holdout_t0030.json` on `holdout/c4_verify`, the MTM figures in
`C4_CENSORING_BIAS_FINDING.md`, the Campaign 1–4 ledgers. Each moves by cents per trade.

**Merge**: the operator's call, per §2.3; I recommended after the drill. Note for whoever merges `c5_harness` into
master later: `engine.py` will conflict at this site — master has the fix inline, c5 has it in `_close_net_pnl`; keep
the function.

## 2. Path B, with one amendment

The operator chose **Path B**: park Campaign 5, keep t0030 as the champion, keep the reading inbox open for ideas
without a campaign. Amendment: the t0030 paper runner (`STACK_10_DONCHIAN_BREAKOUT`) starts **after** the 09-16 drill,
not now — no new always-on process joins the machine in the week of a time-critical event. Path A's own examples argued
for B: the multi-timeframe breakout is t0030's family and would fail the ρ < 0.25 gate; 5-minute lead-lag meets the
friction wall Campaign 1 measured; only the funding-settlement idea is new.

## 3. Corrections to Section 56

1. **§2.3.1 cannot be done as written.** "Re-run t0030 on the fix branch": master has no autoresearch harness
   (`git ls-tree master research/autoresearch` is empty) and no t0030. The re-score has to live where the harness
   lives, so it is on `c5_harness`, with the same two-line fix committed there. Also, master's engine has the
   arithmetic **inline** (`engine.py:306-307`), not in `_close_net_pnl` — your `:246-249` is the c5 branch.
2. **§2.2's "$15–$20 across 134 trades" and "expected delta ~ −$18" were ~2.5× high.** Measured: **−$7.01**
   (BTC −$1.59, ETH −$5.42), equal to Σ 2·slip·qty·pv over the 134 pooled trades. Both are ~0.06 % of the $12,408 net, so
   the conclusion holds; the number did not.
3. **§2.2's per-contract figures are right, the framing is off.** NQ $20 and ES $25 a round trip are per contract, and
   the lab's stacks trade the micros: $2 on MNQ, $5 on MES. The audit reports what was actually charged.
4. **Smaller.** §0.2 "16 new tests": 16 is right, and this round adds 2 more (75 → 77 in `test_c5_harness.py`).
   §2.1 "since commit 50c9bdf (2026-08-18)" — confirmed by `git log -L`.

## 4. A new defect, outside the lab: the collector drops trade batches

Found in this morning's start check, unreported anywhere. Since **2026-09-11 12:37** the Hyperliquid collector logs
`database is locked` in clusters just before each ~7-minute `DB maintenance: pruned N rows` pass, and
`collectors/market_collector.py::_flush_loop` swaps its trade and liquidation buffers out **before** writing and only
logs on failure (line ~351) — every failed flush is lost. From the log: **4,963 trades + 46 liquidation events (09-11),
5,460 + 11 (09-12), 14,226 + 42 in the first 3.75 h of 09-13**, rising with the 8.1 GB database. Order-book samples and
whale persistence fail intermittently too. `asset_snapshots` — the price stream the drill and the lead-lag gate read —
is **not** affected. Zero lock errors since this morning's restart, so far.

**Requested**: rule on (a) the fix — return the batch to the buffer on failure within the existing overflow cap, and
either a longer `busy_timeout` or a shorter prune transaction; (b) timing — I recommend **after the 09-16 drill**, the
collector being frozen until then; (c) whether the lost liquidation events need a registered data gap for the
cascade research.

## 5. Cross-check — where I most want you to look

- **The three fix sites** for sign symmetry on the short side: `adj_entry = entry + d·slip` with d = −1 sells
  *lower*, `adj_exit = exit − d·slip` buys back *higher*.
- **The audit's arithmetic**: MNQ deltas are exact multiples of $2, so `delta / trades / 2` is average contracts per
  trade — a quick sanity check on each row.
- **The regression design**: pinning a *sibling* corrected file rather than rewriting `t0030.json`. If you would rather
  the ledger's artefact be rewritten and the ledger row's sha re-pinned, say so; I chose not to touch a closed
  campaign's record.
- **The breakeven-trail tests**: the exact-friction expectation replaced a loose bound; check the formula
  `((0.25 − 2·slip)·pv − commission) × qty`.

## 6. Ledger

| # | item | gated on |
| --- | --- | --- |
| 1 | Credential rotation — Moon Dev + Phemex in history at root `743496b`; remote locked | operator |
| 2 | `STRATEGY_ID` → `STACK_10_DONCHIAN_BREAKOUT` — paper runner **after 09-16** (Path B, amended) | operator, after the drill |
| 3 | Directive 1 — parked at `portfolio_config.yaml:459` | another session |
| 4 | Will the remote be private? — decides `raw/fetched/` tracking | operator |
| 5 | Intake hardening — Section 47 §1–§2, Section 48 §4.4 | intake session |
| 6 | ~~DEFECT-ENG-001~~ — **fixed and audited, `9c87974` / `a3c0464`** | — |
| 7 | **Merge `bugfix/engine-slippage-signs` into master** — audit in HOMEWORK.md | **operator**, after 09-16 |
| 8 | ~~Campaign 5 crossroads~~ — **Path B chosen, paper runner deferred to after 09-16** | — |
| 9 | **Collector batch loss** (§4) — fix design, timing, gap registration | **you** |
| 10 | Overnight HL data gap 2026-09-13 07:45Z → 16:45Z (9.0 h) — register | me, next round |
| 11 | Section 56 corrections (§3) — confirm | you |

One ruling and one confirmation owed from you. Nothing owed from me before the drill.
