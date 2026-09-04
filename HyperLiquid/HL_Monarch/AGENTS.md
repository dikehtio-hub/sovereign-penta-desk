## What changed (2026-09-03, Claude Code - Round 18)

738 tests pass (was 669). Ecosystem: 738 HL + 375 Tax Agent + 237 Polymarket = 1,350.

- **`domain_verified` is COMPUTED, not asserted.** The SDK parity check passed, so
  the flag is now True - but it re-derives `GOLDEN_VECTOR`'s signature on every
  call rather than being a hard-coded constant. A constant `True` would keep
  claiming verification after someone edited the encoding, which is the exact
  situation the flag exists to catch. Change the domain, types, msgpack order or
  nonce packing and it goes False.
- **Basis pairs are gated as ONE decision.** `pair_gate()` prices the whole pair
  (`sz * (spot_px + perp_px)`), and both legs take the same clamped size. The old
  per-leg gating could clamp leg 1 and not leg 2, which turns a delta-neutral
  pair into a naked directional position wearing a hedge's name. If the gate moves
  between calls and re-sizes leg 1, LEG 2 IS NOT PLACED - holding one known leg
  beats adding a second at the wrong size.
- **Dead man's switch** (`scheduleCancel` + `arm_dead_man_switch`). The protection
  is the DEADLINE, not the call: a process that hangs cannot send a cancel, which
  is exactly when its resting orders are most dangerous. A failed submit does NOT
  record the switch as armed - believing you have protection you do not have is
  worse than knowing you have none. Not behind the tax gate: cancelling is
  risk-REDUCING, and an account out of capital must still be able to protect
  itself.
- **`api/asset_resolver.py`** - coin name to index, with three defences: unknown
  raises, stale raises, and a malformed universe is rejected all-or-nothing. The
  resolver OUTRANKS the static map and a stale answer blocks the order rather than
  falling back - a resolver saying "stale" is information, and a silent fallback
  would discard it and place the order anyway.

### Still open after Round 18

- **No resting-order lifecycle beyond the dead man's switch.** Nothing reprices or
  reconciles an individual order; the switch is a blunt all-or-nothing backstop.
- **No position reconciliation.** `reduce_only` is passed through but never
  checked against actual position state.
- **Nothing refreshes the resolver.** It is offline by construction, so a caller
  must fetch `meta` and call `load_universe()`. Without that it goes stale after
  an hour and blocks orders - which is the safe direction, but it means the
  refresh loop is a required piece of live wiring that does not exist yet.

## What changed (2026-09-03, Claude Code - Round 17)

669 tests pass (was 608). Ecosystem: 669 HL + 375 Tax Agent + 237 Polymarket = 1,281.

- **`require_tax_gate` decorator + `RiskBreachException`.** The decorator calls
  `check_order()` ITSELF rather than trusting the caller to remember - a gate you
  have to invoke is one that eventually is not invoked, and that failure is
  silent because the order simply goes through. `RiskBreachException` is its own
  type so a broad `except Exception` written to keep a trading loop alive cannot
  swallow it.
- **`execution/wallet_manager.py`** - EIP-712 agent-wallet signing, offline, no
  network code of any kind (there is a test asserting the module contains no
  URL, socket or HTTP reference). Key is read from `HL_AGENT_PRIVATE_KEY`, never
  logged, never in `__repr__`, never in an exception, never in a receipt.
- **`execution/order_executor.py`** - gate, sign, submit, receipt, in that order.
  Dry run by default, and live submission needs BOTH `dry_run=False` AND an
  injected `submit_fn`, so neither a stray default nor a stray injection is
  enough alone.

### THE SIGNING CONSTANTS ARE UNVERIFIED

`EIP712_DOMAIN` and `AGENT_TYPES` are written from the published shape of
Hyperliquid's agent scheme and have NEVER been checked against a signature the
live API accepted. A wrong domain yields a rejected signature (harmless); a wrong
ACTION encoding yields a valid signature over the wrong order (not harmless).
`describe()["domain_verified"]` is hard-coded False, and
`verify_against_known_vector()` exists to be run against a real captured request
before any of this is trusted. Component 3 is a scaffold, not a working client.

### Deliberate design choices

- **Testnet is the default.** The signature domain differs, so a misconfiguration
  is rejected by the exchange rather than executed on the live account.
- **Prices and sizes are decimal STRINGS, and floats are refused rather than
  coerced.** Binary rounding changes the action hash, which signs a subtly
  different order than the one intended.
- **An unmapped coin raises.** Defaulting an unknown symbol to asset index 0
  would sign a real order on whatever market holds that index - the worst failure
  available here.
- **An oversized order is CLAMPED to the gate's number, not rejected.** The order
  still happens, correctly sized.
- **A transport failure reports UNKNOWN, not rejected**, and names the cloid to
  reconcile on. The order may be resting; reporting a rejection invites a retry
  that duplicates it.
- **Partial fills book EXACTLY what filled.** Basis legs are two independent
  orders and are never smoothed into a symmetric hedge that did not happen -
  `residual_sz` is the real unhedged exposure. Filled legs are NOT auto-unwound:
  unwinding is itself a market order into whatever just moved.

## What changed (2026-09-03, Claude Code - Round 16)

608 tests pass (was 561). Ecosystem: 608 HL + 375 Tax Agent + 237 Polymarket = 1,220.

- **`execution/risk_manager.py`** - `RiskManager` gates every order on TWO limits
  that constrain different things and must both hold: account MARGIN utilisation
  (surviving volatility - perps liquidate on margin, not notional) and SAFE
  BANKROLL / strategy bucket from the Tax Reserve Agent (not spending money
  already owed in tax). The smaller wins; `binding_limit` says which.
- **Degrades but never silently.** With the tax agent missing or broken it falls
  back to the paper balance and says `TAX GATE UNAVAILABLE` in `reason` on EVERY
  decision, not just in a log. `require_tax_gate=True` turns that into a refusal -
  what a live order router should set.
- **Receipts on every fill**, entries and exits alike, because the ledger runs its
  own FIFO matching and netting them here would duplicate that logic elsewhere.
  Exit reason (TAKE_PROFIT / STOP_LOSS / TIME_STOP) rides in the notes.
- **Receipts are OFF by default.** They write real CSVs into the tax ledger's drop
  folder; 561 existing tests and every backtest share `PaperTrader`, and they must
  not file fabricated fills into a book Q1 reads as truth.

### Two deviations from the brief, both deliberate

1. **The brief hooked only `paper_trader.py`. `BasisHarvester` never goes through
   it** - it keeps its own cash and positions. Hooking only the paper trader would
   have instrumented `hl_liquidation_fade`, which is RETIRED
   (`FADE_STRATEGY_ENABLED = False`, killed in Round 16 on MFE/MAE 0.513 vs 1.092),
   and missed the delta-neutral book that is actually live. Both are instrumented.
2. **`csv_watcher` could not classify a hyperliquid receipt** - it knew only
   polymarket/options/spot, so HL fills landed in `failed/` and never reached the
   ledger. Caught by the end-to-end test, not by inspection. Perps now book under
   `asset_class = "crypto_perp"`, which also keeps them out of the Polymarket
   category sizer.

### Funding is NOT booked as a capital gain

Basis funding accrual is periodic ORDINARY income; the ledger models capital gains
only. Pushing it through the FIFO engine would misclassify it - invisible on the
HUD and wrong on a filing. It is memoed into the receipt notes so the number is
not lost, and needs separate treatment before any real filing.

# HL Monarch - Agent Handoff

## Status


## Session Log — Round 24 (Claude Code, 2026-09-03)

Audit of Antigravity's Rounds 19–23. 1,619 -> 1,671 tests, all four desks green.

### Bugs found and fixed (all four were silent; none had test coverage)

1. **Spot orders were being placed on the wrong market.** `asset_id()` derived a
   spot id as `perp_index + 10000`. A spot asset id is `10000 + the pair's index
   in spotMeta.universe`, an unrelated numbering space. BTC is perp 0 and PURR is
   spot pair 0, so `BTC-SPOT` resolved to PURR/USDC. `open_basis_pair` would buy
   PURR while shorting BTC perp — unhedged short + unwanted altcoin, reported as
   a successful pair. `AssetResolver` now carries a separate spot map
   (`load_spot_universe` / `resolve_spot` / `refresh_spot_universe`) and RAISES
   until a real spotMeta is loaded. Supervisor refreshes both universes.

2. **Order submissions were blind-retried.** `post_action` -> `_post` retried
   5xx and transport exceptions. The nonce is fixed inside the signed payload, so
   a retry after a timeout either double-places or comes back as a duplicate-nonce
   REJECTION for an order that is actually resting — defeating the executor's own
   "UNKNOWN, not rejected" discipline one layer down. Writes now retry only on
   429 (refused at the rate limiter, never reaches the engine).

3. **Reconciler booked `requested_sz` as the fill size.** A receipt is a tax
   record; a partial fill put inventory in the ledger the account does not hold.
   Now uses `origSz - sz`. Also: a partial fill followed by a cancel booked zero.

4. **Reconciler leaked and re-polled forever.** `unknownOid` matched no branch, so
   the order stayed RESTING and was re-queried every cycle indefinitely (rate-limit
   drain + phantom entries in `open_orders()`). Nothing was ever evicted either.
   Added terminal UNKNOWN status and `prune()`; resting/partial never pruned.

### Verified correct
- Supervisor 30s TTL renewed every 10s; deadline stops sliding when it stalls.
- `arm()` never touches a RiskManager; `arm_dead_man_switch` is not tax-gated.
- `reduce_only` bypass approves unconditionally, but `execute_order`'s own numeric
  validation still blocks junk before signing — defence in depth holds.
- Inner-vs-outer `order.status` parsing is right (outer is "order" = found).
- Funding income creates no tax lots and no realized_pnl (§1211 isolation holds).
- RiskSentinel `point_value * price * qty` and the integer contract floor.

### Open for Antigravity
- **§1256 is tagged but not implemented** (see Tax_Reserve_Agent/VERSION). Futures
  book 100% short-term (35%) where 60/40 gives 26% — over-reserving. Separately,
  year-end mark-to-market is not modelled at all, which UNDER-reserves. Electing
  60/40 lowers the reserve, so it needs the operator + a CPA, not an agent.
- `RiskSentinel.validate_order` mutates `order.quantity` before later checks can
  reject. Conservative (smaller), but a rejected order carries the clamp home.
- `reduce_only=True` approves any notional with no position check.

## Session Log — Round 25 (Claude Code, 2026-09-03)

Antigravity's live-API audit of my Round 24 work found two real bugs in my own
code. Both confirmed and fixed. 1,671 -> 1,700 tests, all four desks green.

1. **My spot resolver indexed almost nothing on live data.** I parsed the pair
   NAME for a "/". Live mainnet returns 326 pairs of which only PURR/USDC is
   `isCanonical`; the rest are named `@1`..`@142` and identify their market via
   `tokens: [base_idx, quote_idx]` into the sibling `tokens` array. Now builds a
   token map and registers each pair under its raw name (`@142`), its resolved
   pair (`UBTC/USDC`), and its base (`UBTC`). Added `UNIT_BRIDGED_ALIASES`
   (UBTC->BTC, UETH->ETH, USOL->SOL) so `BTC-SPOT` finds Unit Bitcoin — explicit
   and closed, because a general "strip the U" rule maps UNI to NI. A bridged
   alias never overrides a real listing. Failed SAFE (refused every spot order)
   rather than wrong, but it was broken.

2. **My `PARTIAL` status was self-contradictory.** A cancelled-with-partial-fill
   order was marked PARTIAL, which put it back in `resting_orders`, so a DEAD
   order was re-polled every cycle (~360 times/hr) until prune() caught it. And
   PARTIAL was simultaneously in TERMINAL_STATUSES, contradicting prune()'s own
   docstring and risking eviction of a genuinely resting partial. Now: cancelled
   is CANCELED (with `filled_sz > 0` carrying the partial), and PARTIAL is not
   terminal. Test asserts exactly 1 `get_order_status` call across two cycles.

3. **§1256 60/40 applied** (operator-authorised; I held it back in Round 24
   because it lowers the reserve). Futures carved out of the term buckets and
   escrowed at 0.6*lt + 0.4*st = **26.0%**, freeing $900 per $10k of futures
   gains. Guards tested: no double-taxation, a 1256 loss releases nothing, a
   futures loss does not offset a crypto gain.

### Corrections to the brief
- The blend is **26.0%, not 27.2%**. 27.2% assumes `lt_rate` carries
  `safety_buffer_pct`; it does not (only `st_rate` does). I did not change that
  asymmetry — it would silently re-rate every long-term gain. Your call.

### Still open
- **§1256 year-end mark-to-market is not modelled** and UNDER-reserves. Open CME
  contracts on Dec 31 are deemed sold at fair value with no closing trade. Needs
  a year-end position snapshot the ledger does not take.

## Sign-off — 2026-09-03

Quad-desk sealed at 1,700 offline tests, 0 failures (HL 904 | Tax 388 |
Polymarket 237 | quant_trading_lab 171). No known open defects.

Carried forward as operator decisions, not bugs — see Tax_Reserve_Agent/VERSION
"SIGN-OFF" block for detail:
  1. safety_buffer_pct on lt_rate? (26.0% vs 27.2% §1256 blend)
  2. §1256 year-end mark-to-market — under-reserves if CME held across Dec 31
  3. Reconcile any pre-Round-24 live spot fills — they may be on the wrong market

Standing caveat for whoever picks this up: nothing here has been reconciled
against a live fill. Rounds 24 and 25 each found silent bugs in code that was
already "complete" and fully green, and both times by running something rather
than reading it.
