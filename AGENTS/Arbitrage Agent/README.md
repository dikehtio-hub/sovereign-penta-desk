# Base L2 DEX Arbitrage Agent

Scans a fixed list of token pairs on Base L2, compares a simulated Uniswap v3
price against a simulated Aerodrome price for each pair, and "trades" the
biggest spread that clears the fee + profit hurdle. Tracks PnL, a gas
reserve, a revert circuit breaker, and an off-ramp profit-harvest milestone.

**Today this only runs in paper (simulated) mode.** Price feeds are
synthetic and trade execution/fills are randomized — nothing touches the
real chain yet. See [Going Live](#going-live) for exactly what's missing.

## How it works (RBI loop)

Each scan cycle, `agent.py` runs 4 steps for every pair in
`config.TARGET_PRODUCTS`:

1. **Research** — `data_stream.py` generates a simulated Uniswap v3 price and
   Aerodrome price around a fixed benchmark mid-price for the pair.
2. **Backtest / pre-flight** — `strategies/dex_arb.py` computes the gross
   spread %, subtracts the round-trip DEX fee (`CUMULATIVE_FEE_PCT`), and
   checks it clears both `min_spread` (per-pair) and `MIN_PROFIT_USD`.
3. **Implement / execute** — the best viable opportunity (highest net profit)
   is sent to `execution.py`, which simulates an atomic swap: ~90% fill,
   ~10% simulated revert (zero capital loss, only gas spent).
4. **Risk / milestone guard** — `risk_manager.py` updates PnL and the gas
   reserve, trips a circuit breaker after `MAX_CONSECUTIVE_REVERTS`
   consecutive reverts (30s pause), and flags when the wallet balance
   crosses `OFFRAMP_TRIGGER_USDC` (a suggested profit-harvest point).

## Files

| File | Purpose |
|---|---|
| `agent.py` | Main loop / CLI entry point (`--mode`, `--interval`) |
| `config.py` | **All tunable values live here** — capital, fees, thresholds, pair list |
| `data_stream.py` | Simulated price feed (see limitation above) |
| `strategies/dex_arb.py` | Spread math and viability check |
| `execution.py` | Trade simulation (paper) / live-mode credential gate |
| `risk_manager.py` | PnL, gas floor, circuit breaker, off-ramp milestone |
| `backtest.py` | Standalone compounding-yield projector (not the live loop) |
| `contracts/L2AtomicArbitrageExecutor.sol` | Solidity contract for atomic on-chain execution — **written but not yet deployed or wired up to Python** |
| `test_agent.py` | Unit tests |
| `run_agent_test.py` | Quick 5-cycle smoke test of the live loop, paper mode |

## Setup

```bash
pip install -r requirements.txt
```

## Testing

```bash
python -m pytest test_agent.py -v      # unit tests
python run_agent_test.py               # 5-cycle end-to-end smoke test
python backtest.py                     # long-horizon compounding projection
```

## Altering values

Everything you'd want to tune lives in **`config.py`**, in one place:

- `CAPITAL_CONFIG["WORKING_USDC"]` / `TOTAL_BANKROLL_USD"]` — capital sizing.
  `backtest.py` derives its numbers from these too, so changing them here
  keeps the simulator and the live agent in sync.
- `CAPITAL_CONFIG["MIN_PROFIT_USD"]` / `["MIN_SPREAD_PCT"]` — profitability
  hurdle (a pair can also override `min_spread` individually in
  `TARGET_PRODUCTS`).
- `CAPITAL_CONFIG["CUMULATIVE_FEE_PCT"]` — assumed round-trip DEX fee.
- `CAPITAL_CONFIG["OFFRAMP_TRIGGER_USDC"]` — balance at which the agent
  suggests harvesting profit back off-chain.
- `CAPITAL_CONFIG["MAX_CONSECUTIVE_REVERTS"]` / `["MIN_GAS_RESERVE_ETH"]` —
  circuit breaker / gas floor.
- `TARGET_PRODUCTS` — the list of pairs scanned each cycle.

Run with `python agent.py --mode paper --interval 2.0` (interval is seconds
between scan cycles).

## Going Live

**Live execution is not implemented — do not expect `--mode live` to trade.**
Right now it will refuse to start unless `dontshare.py` exists (copy it from
`dontshare_template.py` and fill in your RPC URL + hot wallet key), and even
then it only prints a warning and returns a `LIVE_PENDING` stub — no
transaction is ever signed or broadcast, and `risk_manager.py` explicitly
does *not* record PnL for `LIVE_PENDING` results (it logs a warning instead)
so you can't be fooled into thinking a trade happened.

To actually go live you'd need to build, in roughly this order:

1. **Real quotes** — replace the synthetic prices in `data_stream.py` with
   on-chain calls to the Uniswap v3 Quoter and Aerodrome Quoter contracts
   (addresses already defined in `config.DEX_ADDRESSES`), likely via `web3.py`.
2. **Deploy the contract** — `contracts/L2AtomicArbitrageExecutor.sol` exists
   but has never been deployed; deploy it to Base and put its address in
   `dontshare.py` / `config.py`.
3. **Transaction building & signing** — in `execution.py`'s live branch,
   build the `executeAtomicArbitrage(...)` calldata, sign with
   `dontshare.HOT_WALLET_PRIVATE_KEY` via `eth_account`, and broadcast
   through `web3.py` against `dontshare.BASE_RPC_URL`.
4. **Slippage enforcement** — `CAPITAL_CONFIG["MAX_SLIPPAGE_PCT"]` is defined
   but currently unused anywhere; it needs to be applied when building swap
   calldata (min-amount-out) before this is safe with real capital.
5. **Wallet funding** — fund the hot wallet with `WORKING_USDC` in USDC and
   `GAS_RESERVE_ETH` in ETH on Base before running.

Given this involves a real private key and real money, treat that build as
its own reviewed piece of work rather than something to bolt on quickly.
