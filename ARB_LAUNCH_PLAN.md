# ARB_LAUNCH_PLAN.md - crypto arbitrage projects: what goes live, what gets parked, and in what order

Written 2026-09-14 by Claude Code after a read-only audit of the three crypto arbitrage
projects. This is a plan, not a status log: nothing below has been built yet. The
operator decides which track to start and when; Antigravity should cross-check the
triage and the Phase 0 bars before any code is written.

Rule that gates everything: **nothing touches the HL collector or the live tier until
after the 2026-09-16 FOMC drill.** Phases 0-2 of Track A are new-file work and can
start before that; Phase 3 onward waits.

---

## 1. Triage (audit of 2026-09-14)

| Project | Verdict | Evidence |
|---|---|---|
| **HL basis harvester** - `HyperLiquid/HL_Monarch/execution/basis_harvester.py`, `strategies/funding_harvester.py`, `analytics/funding_arbitrage.py` | **Build to live (Track A).** | Real HL feed; signing verified against the official SDK golden vector; bankroll + tax gate (`hl_basis_harvest` bucket); `Supervisor` dead-man's switch; `ReconciliationEngine`; `preflight.py` harness with testnet + dry-run defaults. Missing: a transport (`OrderExecutor.submit_fn` is `None`, and the module has "no HTTP client, no URL and no socket" by design) and fill/imbalance handling. Paper book: 5 closed positions, +$432 on $100k, $322 of it from one trade (para:ANSEM). 173 tests green. |
| **Funding_Arbitrage_Agent** - `AGENTS/Funding_Arbitrage_Agent/` (copy of `~/.agents/arbitrage_agent`) | **Retire.** | Weaker duplicate of the harvester. `execution_manager.py::_place_single_live_leg` is a placeholder that sleeps 0.5 s and marks the leg `FILLED` - **fills are faked even in `--mode live`**; `get_account_balance` returns the $10k paper balance in live mode; `close_arbitrage_position` live branch just flips a flag. Cross-exchange leg depends on Binance perps, which a New Jersey resident cannot access (Binance.US has no perps). 95% equity at 3x with a -5% stop on a trade that is not supposed to move with price. Nothing worth porting. |
| **Base DEX arb** - `AGENTS/Arbitrage Agent/` | **Park behind one measurement (Track B).** | Prices and fills are random (`data_stream.py` `random.choice([0.003, ..., 0.014])`; `execution.py` 90% random fill). Contract `L2AtomicArbitrageExecutor.sol` written, never deployed. Live mode correctly refuses (`LIVE_PENDING`). Real Uniswap/Aerodrome gaps are taken by MEV searchers inside the block; a 24 h measurement decides whether this lives. |

Operator can override any row. If Funding_Arbitrage_Agent is retired, do the housekeeping in section 4.

---

## 2. Track A - HL basis harvester to mainnet

Effort estimates are engineering rounds at the measured 12-18 min pace; calendar time
is dominated by the testnet and pilot observation windows (6-8 weeks start to first
real tier if nothing goes wrong).

### Phase 0 - Evidence bar (now; no code, no money)
- Pre-register, as a `data/experiments/*.meta.json` like the other campaigns, the bar
  the paper book must clear before any mainnet order. Proposed (Antigravity to check):
  - >= 20 closed positions
  - median realised **net** APR >= 20% (net = after `TAKER_FEE_PCT` both legs in and out)
  - top position's share of total PnL < 50%
  - >= 10 distinct coins
- Keep the paper harvester running through the drill. It runs inside the collector
  (`collectors/market_collector.py:595`, `BasisHarvester()` with no executor) and
  accrues from the live funding curve.
- After 09-16: fix the collector "database is locked" batch drops (frozen item). A live
  harvester on a collector that silently loses trade batches is not acceptable.

### Phase 1 - Transport layer (~1 round; can start now)
- New `api/exchange_client.py`:
  - `post_exchange(payload) -> dict` = `POST {base}/exchange`. This is the `submit_fn`
    `OrderExecutor` already accepts.
  - Info client: `openOrders`, `orderStatus`, `userFills`, `userFunding`,
    `clearinghouseState`, `spotClearinghouseState`, `meta`, `spotMeta`.
  - Base URL switches on the same `testnet` flag `WalletManager` uses, so the URL and
    the signing domain can never disagree.
- No strategy logic in this file. Tests use recorded JSON fixtures; the suite stays offline.

### Phase 2 - Dry-run wiring (~1 round; can start now)
- Construct the real chain in the collector:
  `BasisHarvester(executor=OrderExecutor(wallet, risk_manager, submit_fn=None))`.
  With `submit_fn=None` the executor gates, signs and logs but sends nothing - the exact
  payloads the harvester would emit, from real opportunities, for days, at zero risk.
- Verify sizes against real `szDecimals` from `spotMeta`/`meta` for the coins the
  harvester actually picks. The paper book favours `xyz:`/`para:` builder-deployed
  tokens with odd precision and thin books; the sizing helper must be proven on them.
- `basis_harvester.py` open path already refuses on `exec_result["aborted"]` (line ~237).
  The close path (`close_basis_pair`, line ~447) ignores the executor's result - make it
  refuse the same way.

### Phase 3 - Fill handling and leg imbalance (~2 rounds; after 09-16)
The part that turns a "riskless" trade into a directional bet if done wrong.
- Both legs as limit orders at a tight tolerance with a fill deadline. Track both via
  `ReconciliationEngine.reconcile_once(user_address)` (already queries
  `openOrders`/`orderStatus`).
- **Imbalance rule:** one leg filled and the other not at the deadline -> cancel the
  resting leg, flatten the filled leg at market, alert. Never book a pair the exchange
  did not fill (the executor docstring already commits to this).
- **Exchange is the source of truth.** Rebuild the harvester's position list from
  `clearinghouseState` + `spotClearinghouseState` on startup and cross-check every
  cycle. Divergence from the JSON state = halt and alert.
- Funding accrual from `userFunding` (payments actually received), not the modelled
  `hourly_rate x elapsed`. Paper keeps the model; live reports what was paid.

### Phase 4 - Margin and wallet plumbing (~2 rounds)
The harvester's own header lists these as unmodelled; they are where live cash-and-carry
blows up.
- HL keeps spot and perp balances separately. Entering a pair means a `usdClassTransfer`
  of margin to the perp side first - an explicit, gated, logged step.
- Margin monitor on the short perp leg: price up -> short loses -> margin ratio worsens
  even though spot gains. Rule: threshold crossed -> top up from spot USDC; cannot ->
  close the pair. Liquidation of one leg is the real tail risk.
- Basis-drift exit: if spot-perp basis moves against the position by more than funding
  earned so far plus a buffer, exit. `EXIT_FUNDING_SPREAD` hysteresis (Round 31) covers
  funding compression; this covers the price case.

### Phase 5 - Protection and observability (~1 round)
- Arm the `Supervisor` dead-man's switch (`scheduleCancel`) in the live loop. It exists;
  it is not wired into the harvester's run loop.
- Kill-switch file (`data/HALT`) checked every cycle.
- Alerts through the existing Discord/Telegram env vars on: imbalance event, margin
  top-up, reconciliation divergence, supervisor arm failure.
- `receipts_enabled=True` so fills flow to `Tax_Reserve_Agent/data/imports/` like every
  other live path.

### Phase 6 - Testnet campaign (1-2 weeks calendar; ~1 round of fixes)
- First order by hand through `execution/preflight.py` (testnet + dry-run are its
  defaults; switch them off one at a time).
- Full loop on testnet 1-2 weeks. Testnet funding rates are meaningless, so lower the
  APR bar for testnet only. Under test is mechanics: fills, imbalance handling,
  transfers, reconciliation, and the dead-man's switch firing when the process is killed
  on purpose.

### Phase 7 - Mainnet pilot  !!! MONEY GATE !!!
- **First step that costs real money beyond the subscription**: exchange fees, slippage,
  capital at risk. Requires explicit operator acknowledgment; Claude Code will not
  execute it unprompted.
- Size $200-500 per leg, well under the smallest `dynamic_config` tier ($5k). Mainnet +
  live requires the pre-flight confirmation phrase, by design.
- Run 2-4 weeks. Compare realised funding vs quoted, actual fees vs `TAKER_FEE_PCT`,
  fill quality, after-tax return vs the 3.7% T-bill benchmark (Round 29: 20% quoted ->
  10% on capital -> 6.8% after tax).
- Step up to the $5k, $10k, $25k tiers only on measured results, one tier at a time.

---

## 3. Track B - Base DEX arb: measurement before any build (~1 round; no money)

- Build nothing in the agent yet. Standalone script: call the real Uniswap v3 Quoter and
  Aerodrome Router (addresses in `config.DEX_ADDRESSES`) via a free Base RPC, for the 10
  pairs, every block for 24 h; log `gross_spread - 0.60% fees - gas`.
- **Decision rule, fixed before the run:** if net-positive spreads at tradeable size
  appear fewer than N times/day (Antigravity to propose N), the project is parked and
  `COMMANDS.txt` says so. Expected outcome: fails the bar (searchers backrun within the
  block).
- Only if it passes: the README's list - deploy the contract on Base, `web3.py` signing,
  `MAX_SLIPPAGE_PCT` enforced as min-amount-out - and it still competes on latency
  against bots with private-mempool access.

---

## 4. Retirement housekeeping (~1/2 round)

- `COMMANDS.txt` section 2 (Funding Arbitrage Agent): mark superseded by the HL
  harvester; correct the "real exchange-connection code" line (fills are faked even in
  live mode).
- `Dexter/registry.yaml`: set `funding-arbitrage-agent` to disabled with the reason.
- Leave the folder in place; deletion is a separate decision.

---

## 5. Open questions for the operator

1. Agree with the triage? (Retire Funding_Arbitrage_Agent; park DEX arb behind Track B.)
2. Phase 0 bar numbers - accept the proposed ones or have Antigravity tune them?
3. Start Phases 1-2 (new files only, zero risk) before the 09-16 drill, or hold everything?
4. Track B measurement: worth one round, or park the DEX agent outright?
