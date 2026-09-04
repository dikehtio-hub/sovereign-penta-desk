# DEV — Sovereign Quad-Desk Trading Ecosystem

Handoff log between Claude Code and Antigravity. Terse by design; git history has
the detail.

## Status

Round 34 complete: INCREMENTAL PERSISTENCE & DATA INGESTION. The pruner now
reduces raw rows to `basis_realised_windows` and `cascade_excursions` BEFORE
deleting them (never pruned; Ruling D's 720h standard is now reachable);
Polymarket sports questions flow into `Sports_Desk/data/polymarket_drops/`
(`Cross_Market_Arb.md` shows 6 matched pairs, 0 clearing); the odds fetcher
polls and drops only on price change; `Canvases/Sovereign_Penta_Cockpit.canvas`
renders all six notes around the tax reserve. **The collector was restarted** -
it had been pruning at 72h for 15 hours after Round 33 said 192 (see findings).
58 new tests.

Round 33 complete: DATA GROUNDING. Retention raised to 192h; the bankroll gate
now FAILS CLOSED on an empty ledger (config placeholder removed, DEPOSIT rows
are the measured balance); Sports_Desk has a real `sports_market.db` for the
first time; Obsidian is a penta-desk cockpit (Sports_Desk.md, Cross_Market_Arb.md,
hub regenerated). 62 new tests.

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
| master + bridges + cross-market + exporters + ingestors (15 modules) | 788 OK |
| HL_Monarch (pytest) | 1012 passed |
| Tax_Reserve_Agent (5 modules) | 546 OK |

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

## Round 34 findings

- **The Round 33 retention fix was not in effect on the machine.** Settings are
  read at import; the collector had been launched 2026-09-03 14:45, nine hours
  before `SNAPSHOT_RETENTION_HOURS` was edited, and the oldest snapshot was
  exactly 72.0h old 15 hours later. Its supervisor (`run_collector_service.py`)
  had died, leaving a bare child with **78% hour-continuity** over the retained
  window (12 of the last 24 hours had no rows for ANY coin). Restarted under the
  supervisor 2026-09-04 04:45 UTC, and again 05:20 UTC after the collector patch
  below. Ruling C's ~2026-09-08 for 168h of raw rows still holds; the first
  PERSISTED 168h windows (entry must carry a quote, window must complete) land
  ~2026-09-11, and Ruling D's 720h no earlier than ~2026-10-04.
- **A SECOND pruner: the dashboard.** `main.py dashboard` embeds a full
  `MarketCollector`, maintenance loop included. The dashboard launched 2026-09-03
  14:46 kept 72h in memory and pruned every five minutes AFTER the service was
  restarted with 192h - caught because rows older than 72.5h stayed at zero and
  the boundary moved at 05:02:34 UTC, a time no service pass could produce.
  The embedded collector now skips maintenance whenever `data/collector.pid`
  names a live process (`service_collector_alive`); the dashboard was restarted.
  Restart BOTH after any settings change.
- **What the persisted tables say after the first backfill** (6,670 windows,
  11,941 events + matched controls, 418s): entry-conditioned 24h, quote >= 20%:
  n=358 on 103 coins, median realised 25.7% vs 6.8% unconditional, **+18.9pp,
  coin-bootstrap P(median >= 20%) = 0.897**; >= 25%: +22.3pp, P 0.972; >= 40%:
  +28.6pp, P 1.000 - the Round 32 result reproduced from the summary tables.
  Cascade excursions, trade_sweep, 7,694 events on 31 coins: MFE/MAE 0.49 (5m)
  to 0.83 (60m) against a persisted control of ~1.05, cluster P(>= 1) 0.000-0.032
  - the fade retirement on 15x the sample. Regimes seen: VOL_MID|FUND_FLAT 18h,
  UNKNOWN 15h (BTC reference gaps); 168h hold: 0 windows until ~2026-09-11.
- **The collector's one `hl-db` thread ran the snapshot poller, the buffer
  flusher AND maintenance.** A two-minute measurement pass queued behind it
  would have created the gaps the measurements are made from. Maintenance now
  has its own `hl-maint` thread; the per-pass budget is one grid instant per
  hold (~2 min across 440 coins for the 7-day scan, 0.25s per coin measured).
- **Fail closed on the measured tables.** If the persistence pass raises,
  `asset_snapshots` and `liquidation_events` are NOT pruned that cycle; the
  others prune as before. Tested by monkeypatching the pass to raise.
- **"No quote, no entry."** The first rule wrote 1,760 seven-day windows whose
  entry instant predated any row for the coin - entries nobody could have made.
  Deleted; a window is now recorded only if a funding quote was in force at the
  entry instant (one indexed lookup, asked first). Thin windows AFTER a real
  entry still record with a NULL rate, never a number.
- **`orderbook_snapshots` is empty and nothing writes it.** `net_apr_after_fees`
  is therefore NULL on every persisted window (`fee_basis = 'unmeasured'`); no
  default spread is substituted. The cost model that decides the 7-day hold has
  no measured spread anywhere in the repo.
- **Antigravity's Gamma URL does not filter.** `?tag=sports` returned a crypto IPO
  event and French politics; `tag_id=1` (the "Sports" tag per `/tags/slug/sports`)
  does. Fixture markets are team-vs-team, not yes/no, and are rewritten into two
  derived questions carrying `derived_from`. `takerBaseFee` has no documented
  unit and is NOT inferred into `fee_rate`.
- **Spread pairs never match, by convention conflict.** `odds_watcher` keys both
  spread legs under the home handicap (Round 33 fix); `matcher.hedge_leg_for`
  looks for the MIRRORED line on the opponent. The sample carries one spread
  question so the gap is visible: 7 questions loaded, 6 pairs matched. Needs a
  ruling on which convention wins before spreads can be hedged.
- A static odds source cannot fabricate line history: `--watch` fingerprints
  PRICES (not timestamps) and skips an unchanged poll. Brier scoring is fed by
  settled results (`results_watcher`), not by quotes - the poller does not
  touch it.
- The supervisor sends the collector's stdout to DEVNULL, so its maintenance
  log lines are invisible. `python main.py persist --status` and
  `measurement_watermarks.updated_at` are the evidence that passes run.

## Round 33 findings

- **Three of Antigravity's Round 33 rulings needed correction before building on
  them, all verified**: (1) Ruling B's cost-drag figures (3.13% / 21.90%) used
  `legs=1` for a two-leg spot-backed trade; correct values are **6.26% / 43.80%**
  - the conclusion (keep 7-day hold) is *strengthened*. (2) Ruling A's "unblocks
  7-day windows TODAY" is wrong: raising retention does not recreate pruned
  rows; snapshots spanned 69.1h, so a full 168h window first exists **~4.1 days
  after the change**. (3) Ruling D (720h across >=2 regimes) **cannot be met under
  Ruling A alone** - 192h retention can never hold 720h; incremental measurement
  persistence (option b) is required by D, not optional.
- **Target 2 path names were wrong** (`monarch_bankroll.py` does not exist; the
  hook is `interfaces/monarch_hook.py`). No `DEPOSIT` type existed in the ledger;
  one now does (`asset_class="cash"`, opens no lot, never summed into gains).
- **Precedence for liquid cash**: override (`--cash` / `--paper-bankroll`) >
  deposits (measured) > declared-in-config > **none = $0.00**. `config.yaml` now
  ships `default_cash_balance_usdc: null`. One HL test relied on the old
  placeholder and now declares its balance explicitly.
- **The odds watcher's own guard caught a defect in my sample**: I keyed the two
  spread legs under different lines (-3.5/+3.5), making two one-leg markets it
  correctly refused. Both legs now share one line key; 6/6 markets price.
- **`.gitignore` data rules were root-anchored** - `data/odds_drops/` never
  matched `Sports_Desk/data/odds_drops/`, and the first real drop showed up as
  untracked. All data rules now use `**/` prefixes; verified with `check-ignore`.
- The Sports exporter had a tz-aware `now` vs naive `placed_at` bug that silently
  disabled the >3-day un-exported warning; caught by the test that asked for the
  warning by name.

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

- **Ruling needed: spread line convention.** Store the selection's OWN handicap
  (away leg at +3.5) and group markets by |line|, or teach the matcher the
  home-keyed form. Until then no spread hedge can price.
- **Orderbook collection.** Nothing populates `orderbook_snapshots`; the cost
  drag on every basis decision rests on an assumed spread. Persisted windows
  will carry a measured `net_apr_after_fees` the moment it is written.
- `persist --status` daily. Ruling D precondition: 720h across >= 2 regime tags
  with >= 48h each; UNKNOWN never counts. First 168h persisted windows
  ~2026-09-11; first 24h walk-forward read `persist --hold 24` is available now.
- Polymarket live polling is the operator's call (network):
  `python -m cross_market.ingestors.polymarket_fetcher --live --watch`.

- **Incremental measurement persistence (option b)** is now *required* by Ruling
  D's 720h standard, not a follow-up. Design: persist per-event excursions and
  per-window realised funding as raw rows age out, so the analysis window is
  unbounded while storage stays flat.
- **7-day entry-conditioned re-run** once snapshots reach 168h (~2026-09-08).
  The 24h signal is validated (+17.7pp over control, coin-bootstrap 0.913-1.000);
  the 7-day hold the money is committed for is not.
- Run `python -m Tax_Reserve_Agent.main seed-bankroll --paper-bankroll <amt>`
  before any live desk starts, or every gate stays FAIL-CLOSED by design.

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
