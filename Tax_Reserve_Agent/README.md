# 🛡️ Tax Reserve & Safe Bankroll Agent

A local-first, zero-token-cost trading accountant and real-time tax escrow calculator covering:
- **Polymarket / Prediction Markets** (CLOB order fills, CTF splits/merges, $1.00 payout redemptions)
- **Crypto Spot** (Buys, sells, DEX swaps, fee deductions)
- **Options** (Calls, puts, worthless expirations to $0 as capital losses, assignments)

---

## 🚀 Quick Start Commands

Run all commands from `c:\Users\ixis1\Desktop\DEV`:

```bash
# 1. View your Real-Time Tax Escrow & Safe Bankroll HUD
python -m Tax_Reserve_Agent.main hud

# 2. Sync On-Chain Trades from Configured Wallets
python -m Tax_Reserve_Agent.main sync

# 3. Sync straight from the settlement layer (Gnosis CTF logs + CLOB subgraph)
python -m Tax_Reserve_Agent.main chain-sync --from-block 50000000

# 4. Ingest whatever CSVs are sitting in data/imports/
python -m Tax_Reserve_Agent.main import

# 5. Keep watching that folder (polls every 5s, Ctrl-C to stop)
python -m Tax_Reserve_Agent.main watch

# 6. Ask the bot-facing gate whether a $500 order is affordable
python -m Tax_Reserve_Agent.main bankroll --check 500

# 7. Settle open lots in markets that have resolved (dry run by default)
python -m Tax_Reserve_Agent.main resolve-markets
python -m Tax_Reserve_Agent.main resolve-markets --apply

# 8. Tax-loss harvesting scan (needs marks - see below)
python -m Tax_Reserve_Agent.main harvest

# 9. Quarterly estimated tax schedule
python -m Tax_Reserve_Agent.main calendar

# 10. Re-match every lot (required after changing accounting.method)
python -m Tax_Reserve_Agent.main rebuild --method HIFO

# 11. Export Daily Markdown Card to Obsidian Vault
python -m Tax_Reserve_Agent.main export

# 12. Run Unit Test Suite
python -m unittest Tax_Reserve_Agent.tests.test_agent Tax_Reserve_Agent.tests.test_new_features
```

---

## Accounting Method (FIFO / HIFO)

`config.yaml -> accounting.method` chooses which open lot a sale consumes.

* **FIFO** (default) - oldest lot first. The IRS fallback when no specific
  identification was made.
* **HIFO** - highest cost basis first. Minimises the gain on each sale, and so the
  escrow. It is not free: spending the expensive basis first leaves the **cheap,
  old** lots open, so it tends to convert future long-term gains into short-term
  ones and defer tax rather than remove it. It also requires that you can identify
  the lots sold - this ledger is that record.

**Changing the method does not rewrite history.** Lots already consumed stay
consumed, so flipping the config mid-year leaves a ledger that is half one method
and half the other. The method the lots were built under is recorded in
`agent_meta`; the HUD prints a warning when it no longer matches the config; and
`main rebuild` replays the whole history from the `transactions` table (the
immutable source of truth) under one consistent policy.

---

## Concurrency

`get_connection()` opens every connection in **WAL** mode with a 5s
`busy_timeout`, so the CSV watcher, a Monarch scanner reading through the
bankroll hook, and a `chain-sync` write can run at once without
`database is locked`. `synchronous` is deliberately left at **FULL** - `NORMAL` is
the usual WAL companion and is faster, but it can lose the most recent commits on
a power cut, which is a bad trade for a ledger written a few times a day.

---

## Tax-Loss Harvesting (`harvest`)

Ranks open underwater lots by the tax they would actually save.

**Marks are the hard part.** The ledger knows what everything cost and nothing
about what it is worth. Nothing here invents a price: an unmarked position is
listed as UNMARKED and excluded from every total. Supply marks via
`data/marks.csv` (`symbol,price` - see `marks.csv.example`) or `--live-marks`,
which prices open Polymarket positions off the CLOB midpoint.

**A harvest is not worth `loss * rate`.** A capital loss is only worth the tax on
the gain it can offset, so the real netting order is applied: short-term losses
against short-term gains, long-term against long-term, then the crossover, then up
to $3,000 against ordinary income, and the remainder carries forward - valued at
**zero**, because it is worth nothing this April. Modelling it any other way
overstates the benefit of harvesting into a flat year by an order of magnitude.

Wash sales are not modelled; the report says so explicitly.

---

## Quarterly Estimated Tax (`calendar`)

**The quarters are not quarters**, which is the detail that produces
underpayment penalties on a year that was paid in full:

| Period | Covers | Due |
|---|---|---|
| Q1 | Jan 1 - Mar 31 (3 months) | Apr 15 |
| Q2 | Apr 1 - May 31 (**2 months**) | Jun 15 |
| Q3 | Jun 1 - Aug 31 (3 months) | Sep 15 |
| Q4 | Sep 1 - Dec 31 (**4 months**) | Jan 15 **of the next year** |

A gain booked on June 1 is due in September; the same gain on May 31 is due in
June. Gains are attributed to the period they were realised in (the annualised
income installment method), which is the right treatment for lumpy trading income.
The report splits the escrow into what is already past its deadline (release and
pay) and what is still reserved for a later one.

Weekend deadlines roll to Monday. **Federal holidays are not modelled** - notably
Emancipation Day, which pushes the April date in some years. Safe-harbour rules
(90% of this year, 100/110% of last) are not modelled either.

---

## On-Chain CTF Sync (`chain-sync`)

Reads Polymarket's real settlement layer rather than the convenience REST API:
`PositionSplit`, `PositionsMerge` and `PayoutRedemption` logs from the Gnosis
Conditional Tokens contract on Polygon, plus CLOB fills from the orderbook
subgraph. Event topic hashes are derived from their canonical signatures with a
bundled pure-Python Keccak-256 (`ingestors/keccak.py`), so there is no `web3`
dependency and no hard-coded constant to go stale.

**Cost-basis conventions** (accounting choices, not facts - change them in
`config.yaml -> chain.split_basis_allocation` if your CPA prefers otherwise):

| Event | Booked as | Basis |
|---|---|---|
| `PositionSplit` | one opening lot per outcome leg | the $1 set price split **equally** across legs ($0.50/$0.50 binary) |
| `PositionsMerge` | one closing sell per leg | same allocation, so split-then-merge nets exactly $0 |
| `PayoutRedemption` | closing sell on the paying leg | `shares = payout / ratio`, with the ratio read from `payoutNumerators` on chain |

A losing outcome emits no event at all - the shares simply become worthless - so
its loss is booked by `resolve-markets` (below) rather than by the log sync.

**Reorg horizon.** A sync never reads closer to the chain head than
`chain.confirmations` blocks (default 64). The horizon is the **more
conservative** of that floor and the node's `finalized` tag - not the tag alone,
because public Polygon RPCs disagree wildly about what it means (measured at one
chain head: publicnode `head-4`, drpc `head-3`, 1rpc `head-500`). A 3-4 block lag
is not finality, and trusting it would void the guard. An explicit `--to-block`
above the horizon is capped, not honoured.

**RPC endpoints are a list, not a URL.** `chain.polygon_rpc_endpoints` is tried
in order with automatic failover, because the previous single default
(`polygon-rpc.com`) started returning 401 and took the whole sync down. Note that
`polygon.llamarpc.com` no longer resolves. Pin a private node with
`PolygonRPCClient(..., allow_fallback=False)`.

**CLOB fills come from the Polymarket Data API**, not a subgraph - the public
Goldsky endpoint 404s. Rows carry `slug`, `outcome` and `conditionId`, so fills
resolve to the same canonical symbols as the on-chain path without a Gamma
lookup. Three caveats:

* The endpoint reports **no fees**, so Polymarket cost basis is gross of them.
* `user=` matches your **proxy** wallet (a Gnosis Safe), not the EOA you sign
  with. `chain-sync` warns when a wallet returns on-chain CTF rows but zero CLOB
  fills, which is the signature of that mistake - otherwise cost basis gets built
  from redemptions with no purchases behind them.
* Offset paging races a live feed: a trade landing mid-walk pushes older rows to a
  higher offset and the next page re-serves them (15 repeats measured in a
  2,000-trade walk). Rows are keyed on `transactionHash|asset|side` and
  de-duplicated across pages. This matters more here than in a typical indexer: a reorged log that
has already been through the FIFO engine has minted tax lots and `realized_pnl`
rows that nothing will ever retract.

---

## Market Resolution Sync (`resolve-markets`)

Finds prediction-market lots still open in the ledger, checks whether their
market actually resolved, and books the settlement - losers at $0.00, winners at
their payout. Dry run by default; `--apply` commits.

This is the only component that *infers* an event rather than reporting one, and
a false write-off invents a capital loss that lowers the escrow - so the failure
mode points straight at under-reserving. Hence:

* **Gamma finds candidates; the chain decides.** `closed: true` means trading
  stopped, not that payouts were reported - a market can close days before UMA
  resolves it, or close disputed. `payoutDenominator > 0` on the
  ConditionalTokens contract is the authoritative signal. `--trust-gamma` relaxes
  this and warns.
* **A condition settles all its legs together.** Splitting $100 and holding both
  legs is a wash: +$50 winner, -$50 loser. Writing off only the loser would
  invent a $50 loss. (`--losers-only` forces the narrow behaviour if you want it.)
* **The settlement is dated to the resolution, never to today**, because the date
  picks the tax year. A market Gamma gives no resolution date for is skipped
  unless you supply `--as-of`.
* **Symbols with no condition id on record are reported, not guessed at.**

---

## CSV Drop Folder (`import` / `watch`)

Drop a broker export into `data/imports/` and it lands in the ledger. Files are
classified (by `source` column, then filename, then headers, then side values),
parsed, committed, and moved to `processed/` or `failed/`.

* A file whose source cannot be determined is **rejected, not guessed** - filing
  options under crypto spot is invisible in the HUD and permanent.
* A file is only read once its size and mtime are unchanged across two polls, so
  a half-copied 40MB export is never parsed as a complete trade history.
* Re-dropping the same export is a no-op: rows carry a deterministic id (the
  export's own, or a content hash) and the ledger deduplicates on it.

See `data/imports/README.txt` and `data/imports/samples/` for the column shapes.

---

## ⚙️ Configuration (`Tax_Reserve_Agent/config.yaml`)

Edit `config.yaml` to customize:
* **Tax Rates:** Set your short-term (e.g. 24%), state (e.g. 5%), and safety buffer rates.
* **Wallets:** Add your Polygon / EVM / Solana wallet addresses for automated sync.
* **Portfolio Cash:** Specify your liquid portfolio balance to get your exact **Safe-to-Deploy** number.
* **Obsidian Sync:** Exports automatic markdown cards into your Obsidian Vault under `Trading_Taxes/`.

---

## 🤖 Programmatic Bot Integration (0 Tokens)

If you run trading bots, you can check your safe deployable capital before sizing a bet:

```python
from Tax_Reserve_Agent.interfaces.sdk import get_safe_bankroll, get_tax_escrow_reserve

# True risk capital (excluding money owed to taxes)
safe_capital = get_safe_bankroll()
print(f"Safe to deploy on next trade: ${safe_capital:,.2f}")

# Escrow to keep in USDC/cash
tax_escrow = get_tax_escrow_reserve()
print(f"Tax escrow to keep safe: ${tax_escrow:,.2f}")
```

### Polymarket Monarch hook

`interfaces/monarch_hook.py` is the sized, gated version of the above - it
answers "can I place this order, and for how much?" rather than just reporting a
number:

```python
import sys
sys.path.insert(0, r"c:/Users/ixis1/Desktop/DEV")   # Monarch lives in a sibling folder
from Tax_Reserve_Agent.interfaces.monarch_hook import MonarchBankrollHook

hook = MonarchBankrollHook(max_position_pct=0.05)
print(hook.status_line())
# [TAX] safe $9,460.30 | escrow $539.70 (5.4% of $10,000.00) | max order $473.01

decision = hook.check_order(desired_notional=2000.0, live_cash=12_000.0)
if decision.approved:
    place_order(size=decision.approved_notional)     # already clamped to every limit
else:
    print(f"Skipping: {decision.reason}")
```

Behaviour worth knowing before wiring it in:

* **Fail-closed.** An unreadable ledger rejects orders; it never falls open into
  unlimited sizing. `decision.stale` flags that case.
* **Never raises into the trading loop.** Errors come back as a rejected
  decision, not an exception.
* **`live_cash` beats config.** The static `default_cash_balance_usdc` is stale
  the moment anything trades - pass the bot's own balance.
* **`already_deployed`** subtracts capital committed since the last refresh, so a
  burst of orders inside one cache window cannot each claim the same dollars.

It also runs standalone, exiting non-zero on rejection so a `.bat` can gate on it:

```bash
python -m Tax_Reserve_Agent.interfaces.monarch_hook --check 500 --cash 12000 --json
```
