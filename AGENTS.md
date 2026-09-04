# DEV — Sovereign Quad-Desk Trading Ecosystem

Handoff log between Claude Code and Antigravity. Terse by design; git history has
the detail.

## Status

Round 31 complete: Targets D (exit hysteresis) and E (leverage policy) applied,
and **Item 14 built as a GATED, NON-TRADING module** - see findings. 38 new tests.

Round 29 before it: Item 8, the funding harvester's BUCKET GATE and after-tax
economics (`HL_Monarch/strategies/funding_harvester.py`). The delta-neutral
engine already existed and was left alone; what was missing was the layer
between it and the bankroll. 24 new tests.

Round 27 before it: Item 6, cross-market arbitrage (`cross_market/hybrid_arb.py`,
`matcher.py`, `hud.py`, `--cross-market` on Monarch_Shark). 52 new tests.

Round 26m before it. **The repository now has version history** — it had none
through ~12 rounds of work. Two commits: the baseline (`743496b`, 526 files) and
the reconcile alias (`5e188a5`).

Suites, all offline:

| suite | count |
|---|---|
| master + bridges + cross-market (11 modules) | 738 OK |
| HL_Monarch (pytest) | 966 passed |
| Sports_Desk master + bridges (9 modules) | 680 OK |
| Tax_Reserve_Agent (4 modules) | 524 OK |

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

## Round 31 findings

- **Item 14 is the retired liquidation fade.** Same signal (liquidation
  clusters), same thesis (wick rebound), same mechanism (pre-positioned limits).
  It was measured and killed in Round 16: **MFE/MAE 0.513 vs a random-entry
  control of 1.092**, n=466, t=-10.52, MAE > MFE in 72.7% of events, 0/20,000
  bootstrap resamples non-negative. Below the control means *worse than random*.
  `config/settings.py` records: "no filter or geometry fixes a sign error" and
  "do not re-enable without a new pre-registered excursion result".
- **Forced liquidations are momentum drivers, not mean-reverting wicks.** The
  spec's "tight post-fill trailing stops" is the worst possible configuration
  against that - it converts adverse excursion from paper into realised loss,
  and is exactly what rounds 9-15 kept retrying.
- **A live pre-registration already exists**: `data/experiments/
  passive_fade_rebenchmark.meta.json`, status PASSIVE, reopening bar
  `P(ratio >= 1.25) > 0.90` under a **cluster** bootstrap, >=500 events, >=20
  coins, top coin <=20%. Building Item 14 as specified would have violated the
  project's own protocol.
- **The retirement is weaker than the headline**, and the registration says so:
  0.513 was substantially a two-microcap artifact (83% of events, HHI 0.360);
  broad-market effect was 0.849. Only the 30m horizon clears p<0.05. So: probably
  no edge, *not proven* across the broad market, under active re-measurement.
- **What I built instead**: `strategies/whale_sweeper.py` with cluster geometry,
  zone maths, the `hl_whale_sweep` bucket, and `EvidenceGate` holding execution
  shut until the pre-registered bar clears. Two independent locks; both must
  open. The path is wired and tested, not stubbed.

## Round 29 findings

- **Item 8 was ~90% already built.** `execution/basis_harvester.py` (delta-neutral,
  accrues at the CURRENT rate not the entry quote), `analytics/funding_arbitrage.py`
  (scan + spread amortisation), `BASIS_MIN_NET_APR = 20.0` already the *net* bar,
  and `hl_basis_harvest` already the bucket name in `risk_manager.py`.
- **The real gap: the harvester never asked the bankroll.** It imported
  `STRATEGY_BASIS_HARVEST` only to tag receipts and gated on its own paper cash;
  `market_collector.py` opened positions with no bucket check at all. Same defect
  as Monarch_Shark running 1.7x over its sports bucket. Now wired, and the live
  call site goes through it.
- **The quoted APR is double the return on capital.** Every APR in the system is
  per-*leg*; `capital_required()` is `notional x 2`. A position reporting 56%
  realised earns 28% on money committed. A gate asking for one leg's notional
  would authorise half what the position spends.
- **The honest restatement**: 20% quoted -> 10% on capital -> 6.8% after tax ->
  vs 3.7% for a T-bill after ITS tax (state-exempt, 31 USC 3124(a)). A three-point
  edge, not fifteen.
- The gate **fails closed**: an unreadable ledger rejects rather than waving
  through, and logs loudly so "gated off" is never mistaken for "no opportunities".

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
