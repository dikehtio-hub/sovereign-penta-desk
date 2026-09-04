# DEV — Sovereign Quad-Desk Trading Ecosystem

Handoff log between Claude Code and Antigravity. Terse by design; git history has
the detail.

## Status

Round 27 complete: Item 6, cross-market arbitrage (`cross_market/hybrid_arb.py`,
`matcher.py`, `hud.py`, `--cross-market` on Monarch_Shark). 52 new tests.

Round 26m before it. **The repository now has version history** — it had none
through ~12 rounds of work. Two commits: the baseline (`743496b`, 526 files) and
the reconcile alias (`5e188a5`).

Suites, all offline:

| suite | count |
|---|---|
| master + bridges + cross-market (11 modules) | 736 OK |
| Sports_Desk master + bridges (9 modules) | 680 OK |
| Tax_Reserve_Agent (4 modules) | 524 OK |
| HL_Monarch | 904 passed |

Tax config is **New Jersey resident** (Union, 07083): composite 32.37% =
24% federal + 6.37% NJ + 2% buffer, `casual_standard_deduction`.

## What changed

- **`.gitignore` written before the first commit, not after.** `Keys/` holds a
  *screenshot of a HyperLiquid API key*; two live `.env` files; `*.db` carries a
  real tax position. A committed secret survives deletion — it stays in every
  clone — so these never entered history.
- **`quant_trading_lab/` is excluded and that is deliberate.** It has its own
  git repo. Staged from the parent it becomes a bare gitlink: it *looks*
  version-controlled while tracking nothing. It versions itself; the outer repo
  stays out of its way.
- **Three secret-scan hits were checked, not assumed.** The `connection_id` and
  `r`/`s` values in `HyperLiquid/HL_Monarch/execution/wallet_manager.py` are
  EIP-712 test vectors sitting beside `"private_key": "0x" + "11" * 32`. The
  base64 hits in `MoonDev_Quant_Strats/.../chart_benchmark_*.html` are chart
  image data. All false positives.
- **`--reconcile` added as an alias of `--check-sync`** on `monarch_shark`, with
  a test — an argparse alias regresses silently.

## Round 27 findings

- **Both deltas in the Round 27 spec were overstated.** `delta_state = 1.0` on
  the sportsbook leg reads as full relief; it is full relief *at the bare state
  rate*, an effective delta of 6.37/32.37 = **0.197**. And `delta = 1.0` on the
  Polymarket leg assumes capital gains exist to absorb the loss.
- **The structural reason**: each leg's loss is deductible only against a class
  of income the other leg does not produce. When the sportsbook leg loses the
  winner is a capital gain (nothing for NJ 54A:5-1(g) to net against); when the
  Polymarket leg loses the winner is ordinary income (IRC 1211(b) caps the
  offset at $3,000). Both reliefs are therefore *capacity*-dependent and default
  to zero.
- **Hurdles**: 8.83% with ample capacity, **16.75% with none**, 23.93% if the
  Polymarket leg is read as wagering. Real cross-book arbs pay 1-3%, so the
  engine's usual answer is REJECTED.
- Pinned against two closed forms: the known single-venue delta=0 hurdle
  (23.9317%, matches to 1e-6) and the trivially-zero fully-relieved case.

## Next / open questions

- **Is a Polymarket event contract capital or wagering?** Unsettled - the IRS has
  not ruled on retail-held CFTC-regulated binaries. IRC 1234A supports capital;
  a wagering characterisation collapses the leg into the same trap as the
  sportsbook and costs ~7 points of hurdle. `--prediction-as-wagering` prices it.
  This is the largest open legal question in the build.
- `matcher.TEAMS` is deliberately partial. An absent team produces NO MATCH,
  which is safe. Add teams on demand rather than loosening the matcher.

- **The drop path is `data/imports`, not `data/drop`.** Round 26m specified
  `Tax_Reserve_Agent/data/drop/`; that directory does not exist and nothing reads
  it. `config.yaml -> imports.drop_folder` and `csv_watcher.DEFAULT_IMPORTS_DIR`
  both resolve to `data/imports`. An export to `data/drop` would look like it
  worked and import nothing. A test now pins `TAX_DROP_DIR ==
  DEFAULT_IMPORTS_DIR` so they cannot drift.
- **No remote is configured.** Nothing is pushed anywhere. Before adding one,
  re-check `.gitignore` — the secrets argument only holds while the history is
  local.
- **The multi-state problem is not modelled.** A travelling contract worker
  resident in NJ owes roughly `max(NJ, work-state)` per dollar after the
  other-jurisdiction credit — higher in NY, lower in PA — and betting while
  physically in another state can source winnings there. The single 6.37% is the
  right approximation for a NJ resident; it is not a return.
- `professional_schedule_c` is permanently barred under *Groetzinger* while the
  x-ray contract work continues. Do not re-open it.
