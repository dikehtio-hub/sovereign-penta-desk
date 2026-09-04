# HyperLiquid — Agent Handoff

## Status
Two sibling projects, both Python, no git repo yet.

- **HL_Monarch/** — active build. Native (free, keyless) Hyperliquid + HIP3 TradFi market
  intelligence suite: REST + WS clients, SQLite WAL store, liquidation cluster engine,
  whale discovery, funding-arb matrix, paper trader, Rich terminal dashboard.
  CLI: `python main.py {dashboard|collector|sync|scan|inspect|liqs|whales|arb|paper|test-alert|maintain|obsidian|backtest|squeeze|summary}`.
  285 unit tests, all passing: `python -m unittest discover -s HL_Monarch/tests -t HL_Monarch -v`.
  Obsidian export: `python main.py obsidian --once` (share a vault with Polymarket via
  `OBSIDIAN_VAULT_PATH` — see COMMANDS_CHEAT_SHEET.txt).
- **HL_MoonDev/** — reference/benchmark only. MoonDev paid-API SDK stub plus older
  standalone liquidation backtests. HL_Monarch exists to replace this — see
  `API_MAPPING_COMPARISON.md`.

## What changed
2026-08-31 (round 14). Maker/taker fee model + pre-registered 50-trade hurdle.

**Fee model.** `MAKER_FEE_PCT = 1.0bps`, `TAKER_FEE_PCT = 3.5bps`, routed by fill type:
a resting limit (entry, take-profit) earns maker; anything crossing the book to get out
(stop-loss, time-stop) pays taker.

  The accounting is built so `cash_balance - initial == realized_pnl` exactly once flat.
  Every fill deducts its fee from cash and accumulates `fees_paid`; the entry fee is
  recorded on the position and attributed to the trade at close, so `realized_pnl` is the
  true net without double-counting. There is a test pinning that invariant, because it is
  the thing that makes the account trustworthy.

  **Consequence worth knowing: 1:1 geometry is no longer break-even at 50%.** A win exits
  maker and a loss exits taker, so on a $5k fade a win nets +$6.30 while a loss costs
  -$6.95. Break-even is ~52.5%. That is precisely why the agreed PASS bar is 54%, not 50%.

**Pre-registered 50-trade hurdle** (agreed before any trade closed, applied by rule):
PASS >= 54.0% win rate AND >= 1.25 profit factor, net of fees; RETUNE 48.0-53.9%; FAIL
< 48.0%. `hurdle_verdict()` returns PENDING below 50 closed trades. The matrix does not
cover "win rate >= 54% but profit factor < 1.25" - that reports **INCONCLUSIVE** rather
than being silently promoted or demoted, same convention as the retired squeeze bar.
Thresholds live in settings and `tests/test_round14_fees_and_hurdle.py` asserts each one,
so a later edit that relaxes a bar to flatter a result fails loudly.

**`main.py paper`** now shows Net PnL, gross, **Fees Paid**, and a hurdle progress line
(closed/50, win rate vs 54%, profit factor vs 1.25, W/L), colour-coded by verdict.

**Bug fixed during the round**: a `.replace()` without a count wrote the *summary* fields
into `to_dict()`, so `gross_profit`/`gross_loss` were never persisted and profit factor
came back `n/a` after a reload. Only raw totals are stored now; the ratios are recomputed
on load, since a stored copy could only go stale against the counters it derives from.

**Tests**: 350 -> 379. `pytest tests/ -q` -> **379 passed**. Offline: 375 passed, 4 skipped.
pyflakes clean. Two round-13 tests asserted the pre-fee contract and were updated: win/loss
are symmetric GROSS but not net, and cash reconciles from the starting balance rather than
from post-entry.

## What changed (round 13)
2026-08-31 (round 13). Exit engine built, fade re-geometried, post-pivot cut list executed.

**Re-geometried to 1:1.** Offset 0.50%, stop 0.65%, take-profit 0.65% *from the limit*.
The previous design targeted the pre-cascade mark exactly, pairing a ~0.5% reward with a
1.5% stop - about 1:3, needing a >75% win rate merely to break even. Both legs now sit the
same distance out, so it breaks even at 50%. At a 0.50% offset the 0.65% target lands just
beyond the pre-cascade mark, which is the intended snapback. Added
`FADE_POSITION_MAX_HOLD_SECONDS = 600.0`.

**Position exit engine** - `check_open_positions(current_mids)`, called from the collector's
allMids handler via `on_mids()`. Until now `stop_loss` and `take_profit` were merely STORED
on a filled position and nothing acted on them: fades sat open indefinitely and the reported
PnL measured entries only. Resolution order is stop -> take-profit -> time-stop, with
**stop first on an ambiguous tick**: a tick that straddles both levels cannot tell us which
traded first, and a paper account that resolves its own ambiguity favourably is worthless.
Exits at a level fill AT the level (a gap through it does not book a worse price); the
time-stop exits at the prevailing mid. Verified live: TAKE_PROFIT, TIME_STOP and STOP_LOSS
all firing, realised PnL accumulating, trade_history recording both legs.

**Cut list executed.** Deleted `cross_market_scanner.py`, `titan_pipeline.py`,
`squeeze_validator.py`, `test_round6_validation.py`, `test_round11_acceptance_bar.py`, and
removed the `titans` / `validate` subcommands plus the hub's Cross-Market Titans section.
Note: there was no `tests/test_titan_pipeline.py` - those tests were spread across four
other modules, so ~542 lines were excised class-by-class instead. `squeeze` is retained as
read-only informational, with a test asserting execution/ does not import it.

**BUG FOUND AND FIXED DURING VERIFICATION - concurrent collectors.** A live run produced an
account holding positions with the OLD geometry alongside orders with the new. Cause: the
PID lockfile guarded only the service *supervisor*; `python main.py collector` run directly
bypassed it, so a round-12-era collector was still alive and writing the same
`paper_trading_state.json`. Two writers silently clobbered each other - and the paper
account is now the thing being measured. `start_collector()` now takes its own lock
(`COLLECTOR_LOCK_PATH`) and refuses to start a second instance. Verified: the second
instance logs "Another collector is already running (PID ...)" and exits; a clean
single-instance run produced 4 orders all at exactly 0.650%/0.650%.

**Tests**: 430 -> 350 (net: +36 new exit-engine tests, -116 pruned with the cut modules).
`pytest tests/ -q` -> **350 passed**. Offline: 346 passed, 4 skipped, 0 failed.
pyflakes clean.

## What changed (round 12)
2026-08-31 (round 12). **Predictive squeeze classifier retired; pivoted to reactive fading.**

Pre-registered verdict, applied without revision: 118 flagged / 808 control across 25 coins,
lift **0.351** vs a 1.25x floor, p=0.9963 -> **FAIL**. The classifier was not merely
uninformative but anti-predictive, so it is out of the execution path entirely.

**Reactive fade architecture.** `LiquidationFadeStrategy.on_liquidation_sweep()` is called
from the collector's WebSocket trade handler the moment a verified sweep prints - no squeeze
score is consulted anywhere (there is a test asserting the module contains no reference to
one). Triggers unchanged: exotic $1k/1.0%, major $25k/0.4%.
  * Rests a limit 0.5% deeper into the wick; fills at the limit, never the mark.
  * **Take-profit is the PRE-CASCADE mark**, not a fixed percentage - the thesis is
    reversion to where price sat before the sweep, so that is the target.
  * Stop-loss 1.5% beyond the limit. TTL 180s.
  Verified live: `FADE BUY ETH limit $2,469.3910 TP $2,481.8000 SL $2,432.3501` against a
  $59,892 forced sell at a pre-cascade mark of $2,481.80 - every number checks out.

**Rotation now ranks by 24h volume, not squeeze score.** Gating the feed on an
anti-predictive classifier was actively selecting the markets *least* likely to liquidate.
Liquidations happen where there is flow. Hysteresis and the 35-slot cap are unchanged.

**Paper account now persists** (`data/paper_trading_state.json`, atomic write). This was
load-bearing, not cosmetic: `main.py paper` constructed a fresh PaperTrader on every
invocation, so it always reported a flat account no matter what the strategy did - the
collector and the CLI are different processes. Added explicit `realized_pnl` /
`closed_trades` / `expired_orders` tracking, and the dashboard now reads the same file.

**`main.py paper`** shows equity, realised vs unrealised PnL, return %, open positions, and
resting fade limits with a live **TTL countdown** (colour-coded as expiry approaches).

**Squeeze engine retained as informational only** - `main.py squeeze` still works; a test
asserts the execution layer does not import it.

**Tests**: 404 -> 430. `pytest tests/ -q` -> 430 passed. pyflakes clean.

## What changed (round 11)
2026-08-31 (round 11). Acceptance bar pre-registered in code; validator can now compute it.

**The bar Antigravity set required a statistic the validator did not produce.**
`is_significant` was purely `N >= 30` - there was no p-value anywhere, so `PASS` (lift >= 1.75
AND p < 0.05) was not computable. Added `fisher_exact_greater()` (one-sided, hypergeometric
via `math.comb`, dependency-free) and `classify_verdict()` applying the matrix by rule.
Verified against `scipy.stats.fisher_exact(alternative='greater')` - exact match to 6dp
across five cases. Fisher rather than a z-test because the counts are small and sparse,
where the normal approximation overstates significance.

  Thresholds live in `config/settings.py` (`VALIDATOR_ALPHA/PASS_LIFT/RETUNE_LIFT`) and
  `tests/test_round11_acceptance_bar.py` asserts each one, so a later edit that relaxes a
  threshold to flatter a disappointing result fails loudly instead of passing quietly.

  One gap in the matrix, resolved explicitly rather than silently: **lift >= 1.75 with
  p >= 0.05** is reported as `INCONCLUSIVE`, not promoted to PASS nor demoted to RETUNE.

**PRELIMINARY VALIDATION READING - NOT THE VERDICT.** The window is still accumulating
(coverage ~13%), and the agreement is to evaluate at completion. But the validator now has
real data and the early signal is strongly negative:

    2h horizon: 118 flagged / 694 control windows (both above the N>=30 floor)
                hit 2.54% vs baseline 9.94%  ->  lift 0.256, p=0.9993  ->  FAIL
    22 coins walked, 2,414 points evaluated.

  Lift 0.26 is not noise around 1.0 - flagged windows are *less* likely to be followed by a
  matching liquidation than unflagged ones. That is the classic symptom of an inverted
  direction convention, so it was tested directly: flipping the A/B mapping gives lift 0.511
  - better, still far below 1.0, still FAIL. **The convention is not the explanation.** The
  flag appears anti-predictive rather than merely uninformative.

**Tests**: 379 -> 404. `pytest tests/ -q` -> 404 passed. pyflakes clean.
Service running, PID 46888, uninterrupted.

## What changed (round 10)
2026-08-31 (Antigravity round 10 - final polish). Replay methodology settled: time-aligned
marks confirmed as the standard, 40 genuine exotic sweeps across 18,321 trades. The
predetermined $1,000 / 1.0% bar stands; the plan is 24-48h of continuous runtime, not
threshold tuning.

**Per-coin alert cooldown.** `ALERT_COOLDOWN_SECONDS = 60.0`, enforced by
`WebhookAlerter.should_send(category, coin)` and gated inside every alert entry point
rather than left to callers to remember. A 12-fill cascade now emits **one** webhook
instead of twelve.

  Two design choices worth noting:
  * Keyed by `(category, coin)`, not coin alone, so a margin-call warning is never
    swallowed by an unrelated whale-trade alert on the same market. Margin alerts key
    per-address as well - two accounts in danger on one market are two separate events.
  * `should_send()` *consumes* the slot under a lock. Alerts dispatch from a thread pool,
    so a non-atomic check-then-set would let two webhooks escape for the same event; there
    is a test that races 8 threads and asserts exactly one passes.
  `suppressed_count` is tracked for observability, and the coin key is normalised so
  `SKR`/`skr`/` SKR ` are one market.

**Tests**: 358 -> 379 (`tests/test_round10_alert_cooldown.py`, 21 new).
`python -m pytest tests/ -q` -> **379 passed**. Offline (DNS + sockets blocked):
**375 passed, 4 skipped, 0 failed**. pyflakes clean.

**Service**: restarted onto current code and running (coverage 11.87% and climbing from
4.15% earlier today). This is the 48h accumulation window for the precedence validation run.

## What changed (round 9)
2026-08-31 (Antigravity round 9). Two refinements, plus a methodology discrepancy to resolve.

**REPLAY COUNT DISAGREEMENT - please read before relying on the 177 figure.**
Antigravity reported reproducing the exotic replay as `2 -> 177`. My time-aligned method
gives `2 -> 33` on a now-larger corpus (13,637 exotic trades, up from 10,443). I traced the
gap: comparing each historical trade against a **single non-time-aligned mark** (the coin's
latest snapshot) yields **204** - essentially the 177, modulo DB growth between runs.

  That method inflates the count. A coin whose price drifted 5% over the recording window
  shows *every* old trade as "5% slippage vs mark", manufacturing sweeps that never
  happened. The defensible figure is the time-aligned one: each trade scored against the
  mark in force when it printed.
  * time-aligned, nearest preceding snapshot: **33**
  * single latest mark per coin (no alignment): **204**
  * mean mark per coin: **419**
  The direction of the fix is confirmed either way, and the agreed conclusion (accumulate
  runtime, do not lower the bar) is unaffected. But **33 is still below the validator's
  30-per-group significance floor in practice**, whereas 177 would suggest we are already
  powered. That distinction decides whether the next `validate` run means anything.

**Task 1 - fade order TTL.** `FADE_ORDER_TTL_SECONDS = 180.0`, enforced by
`PaperTrader.expire_stale_orders()` and called at the top of `check_open_orders()` so
expiry runs *before* fills - an order that has outlived its thesis cannot fill on the same
tick that retires it. Closes the risk flagged last round: a fade resting from a cascade
hours ago would otherwise fill on unrelated price action and book a trade the strategy
never intended, silently flattering the paper PnL.

**Task 2 - exotic threshold tuning.**
  * `SQUEEZE_MIN_NOTIONAL_OI` $250k -> **$100k**, admitting the $100k-$200k OI band - the
    thinnest books, where forced exits move price hardest.
  * `whale_tracker` now takes a per-market discovery floor: **$25k core / $7.5k exotic**
    (`discovery_floor_for()`). The flat floor meant the counterparties to exotic cascades -
    the accounts most worth having on the whale list - were never discovered.
  * `alerter` gained an exotic tier: `qualifies_as_exotic_sweep()` at **>= $2,500 with
    >= 1.5% slippage**, wired into the collector ahead of the notional tier. Size alone is
    the wrong test on a market whose median fill is under $100.

**Tests**: 328 -> 358 (`tests/test_round9_ttl_and_tiers.py`, 30 new).
`python -m pytest tests/ -q` -> **358 passed**. Offline (DNS + sockets blocked):
**354 passed, 4 skipped, 0 failed**. pyflakes clean.

## What changed (round 8)
2026-08-31 (Antigravity round 8). Exotic liquidation detection fixed - the bug that made
every previous round's squeeze work unmeasurable.

**Task 1 - two-tier sweep detection** in `analytics/liquidation_engine.py`. Confirmed
Antigravity's finding independently, and the numbers are worse than reported: across
**10,443 exotic fills the median notional was $69**, p90 was $495, and only **2 cleared the
$25k bar**. SKR logged 3,046 trades and zero liquidation events. The thresholds were
calibrated on BTC/ETH and locked exotics out entirely.

  Now two tiers: `$1,000 + >=1.0%` slippage (exotic - thin books move hard without size)
  OR `$25,000 + >=0.4%` (major), plus the unchanged protocol-backstop address check and
  `$50,000` whale-order fallback. **Replaying all 10,443 real historical exotic trades
  through both detectors: old 2 events, new 20 - a 10x improvement, 18 newly captured.**

**Task 2 - rotation hysteresis.** `_plan_rotation()` holds a coin subscribed for at least
`SQUEEZE_ROTATION_COOLDOWN_SECONDS` (1200s) after it drops out of the candidate set. A
squeeze stops scoring as crowded exactly when it begins unwinding - which is when its
liquidations print - so dropping the feed on that transition was cutting the recording off
mid-cascade. Freed slots are reused within the same cycle; held coins still consume capacity.

**Task 3 - capacity and interval.** `SQUEEZE_ROTATION_MAX_COINS` 20 -> 35,
`SQUEEZE_ROTATION_INTERVAL` 60s -> 180s. The score is computed from a 24h window and cannot
move meaningfully in a minute, so the faster loop only produced sub/unsub churn.

**Task 4 - fade engine reaches exotics.** The strategy's flat `$50k` trigger had the same
defect as Task 1: it could only ever fire on BTC/ETH, so every exotic liquidation the
rotation now records would have been ignored. Trigger and position size now scale with the
market (`FADE_EXOTIC_OI_CEILING` decides which scale applies, falling back to notional when
the event carries no OI). Added real limit-order support to `PaperTrader`
(`place_limit_order`, `check_open_orders`, `cancel_orders`): fades now rest *deeper* into
the cascade rather than crossing the spread into it, and fill at the limit price rather
than being handed price improvement they never asked for. `on_liquidation_batch()` is the
live ingestion entry point, wired into the dashboard with per-market OI attached.

**Tests**: 286 -> 328 (`tests/test_round8_exotic_liquidations.py`, 42 new).
`python -m pytest tests/ -q` -> **328 passed**. Verified genuinely offline with DNS and
sockets blocked to the API hosts: **324 passed, 4 skipped, 0 failed**.

  Two pre-existing tests changed contract rather than breaking: `test_execution`'s fade test
  asserted an immediate market fill, which limit-order fades no longer produce - it now
  asserts the order rests and then fills on overshoot, with the market path kept in a
  separate test. And `tests/test_rest_api.py` (live integration tests from round 1, asserting
  against the real API response shape) now skips when the host is unreachable instead of
  failing, which is what makes the "100% offline" claim true without deleting the coverage.

## What changed (round 7)
2026-08-31 (Antigravity round 7). Three tasks. Task 1 closes the loop that has blocked the
precedence question for two rounds.

**Task 1 - dynamic exotic squeeze WS subscriptions.** `_squeeze_rotation_loop()` in
`collectors/market_collector.py` recomputes squeeze candidates every 60s and rotates up to
20 exotics onto the live trade feed, dropping those that fall below the threshold. The core
watchlist is filtered out of the candidate set and never rotated, so the dashboard keeps its
feeds. Costs zero REST budget - WebSocket subscriptions are free.

  `api/ws_client.py` gained `subscribe(channel, params)`, `unsubscribe()`,
  `unsubscribe_trades()`, and introspection (`active_subscriptions`,
  `subscribed_trade_coins`). The important detail is that unsubscribe removes the entry from
  `_subscriptions`: without that a rotated-out coin would silently reappear on the next
  reconnect and the subscription set would only ever grow. There is a test for exactly that.

  **Verified live**: rotation logged `+19 -0` then `+0 -2`, and within five minutes 16
  exotic coins were streaming trades that previously had no feed at all - SKR (307 trades),
  XMR, 0G, APEX, xyz:CXMT, xyz:KIOXIA and others. Those are precisely the coins the squeeze
  engine flags and that `liquidation_events` never covered, which is why
  `main.py validate` had 0 flagged windows to measure. The loop is now closed; the validator
  needs runtime, not more code.

**Task 2 - PID lockfile + logarithmic coverage.**
`run_collector_service.py` now claims `data/collector_service.pid` and refuses to
double-start, replacing command-line string matching that was wrong in both directions (a
stale wmic parse reported a phantom process; a looser PowerShell match treated any command
merely *naming* the script - a linter or test run - as a running service). A stale lockfile
naming a dead pid is taken over rather than treated as a conflict, so a machine that lost
power needs no manual cleanup. `--status` reports lock state plus coverage as JSON, and the
launcher now consumes that instead of guessing. `MAX_BACKOFF_SECONDS` 300 -> 600, so a
chronically failing collector no longer settles at exactly one retry per healthy-window.

  `coverage_threshold_for()` is now logarithmic:
  `75 - 25 * log(hours/24)/log(168/24)`, clamped at both anchors and guarded against
  `hours <= 0`. Every doubling of the window now moves the bar by the same 8.91pp, where
  linear interpolation moved 24h->48h by only 4.2pp and over-rewarded the last doublings.

**Task 3 - production DB isolation.** `tests/test_obsidian_exporter.py` now binds a temp
database (it previously read snapshots, whales, liquidations and the titan table from the
live DB, so its assertions depended on what the collector happened to have written, and the
export itself touched production state). `tests/test_whale_tracker.py` was isolated in
round 6. A structural test asserts both reset the singleton in setUp *and* tearDown so the
binding cannot leak between tests.

**Tests**: 254 -> 285 (`tests/test_round7_rotation.py`, 31 new, all offline). Six earlier
tests asserting the superseded linear-interpolation contract were updated to the logarithmic
one. Polymarket 173 still green. pyflakes clean; verified across three consecutive runs.

## What changed (round 6)
2026-08-31 (Antigravity round 6). Three tasks.

**Task 1 - `analytics/squeeze_validator.py` + `python main.py validate`.**
Walks history, reconstructs the squeeze state at each point using **only data up to that
point**, then looks forward 1h/2h/4h for liquidations in the predicted direction
(LONG CASCADE -> forced sells / side 'A'; SHORT SQUEEZE -> forced buys / side 'B').

  Two things it does beyond the brief, because without them the number is not
  interpretable:
  * **A control group.** Every run also scores *unflagged* windows on the same coins over
    the same period, and reports `lift = hit_rate / baseline_rate`. An 80% hit rate means
    nothing if BTC liquidates in 80% of all windows anyway.
  * **A significance floor** (`VALIDATOR_MIN_OBSERVATIONS = 30`), so a 2-window "100% hit
    rate" reports as UNDERPOWERED rather than as a finding.
  A regression test plants a synthetic signal and confirms the harness detects it, so a
  null result on real data can be trusted as a real null rather than a broken harness.
  Lookahead is explicitly tested against: writing a violent future regime must not change
  the verdict at t.

  **Result on current data: 0 flagged windows out of 426 evaluated.** The baseline computed
  fine (7.3% / 10.4% / 14.4% of windows see a liquidation at 1h / 2h / 4h), but the squeeze
  engine never fires on the coins that have liquidation data. That is a structural mismatch,
  not a bug: liquidations are recorded almost entirely in majors (BTC 300, ETH 143 of 456
  events), whose funding is stable and never scores as crowded, while the squeeze engine
  deliberately targets exotic perps with no spot leg. **The question cannot be answered
  until the collector has run continuously long enough to record liquidations on the
  exotics.**

**Task 2 - interpolated coverage + backoff tuning.** `coverage_threshold_for()` now
interpolates linearly from 24h/75% to 168h/50% and is flat outside that range, replacing
the stepped tiers - those had a cliff where asking for one extra hour of history (72h -> 73h)
made the bar *easier*. `HEALTHY_RUNTIME_SECONDS` raised 120 -> 300 in the supervisor: a
collector dying every ~3 minutes previously reset its backoff on every cycle and so never
escalated.

**Task 3 - `launch_service_background.bat`.** One-click detached launch via `pythonw.exe`
(no console window), plus `status`, `stop`, and `log` subcommands. Process detection and
termination go through PowerShell rather than `wmic` + `for /f`: wmic is deprecated on
Windows 11, and the `for /f` parse reported a **phantom running process when none existed**,
which would have blocked every subsequent start. Verified end to end: start -> confirmed PID
-> status -> log -> stop -> NOT RUNNING.

**Tests**: 224 -> 254 (`tests/test_round6_validation.py`, 30 new, all offline). Six earlier
tests asserting the superseded stepped-tier contract were updated to the interpolated one.
Polymarket 173 still green. pyflakes clean.

## What changed (round 5)
2026-08-31 (Antigravity round 5 refinements). Four tasks; one spec issue corrected.

**Task 1 - squeeze exhaustion trigger.** `is_exhausting(percentile, mean_funding,
persistence)` in `squeeze_engine.py`, replacing the earlier loose heuristic. Fires only
when a crowd was committed (`persistence > 0.75`) AND its funding then broke out of its own
range: below the 35th percentile from a positive regime (longs exiting), or above the 65th
from a negative one (shorts covering). `is_regime_aligned` is untouched and still drives
the watchlist, so "still loading" and "actively unwinding" are now separate, mutually
exclusive states rather than two readings of the same number.

**Task 2 - relaxed gating + logarithmic conviction.** `qualifies_as_titan()` accepts an
actor on the Hyperliquid side via **either** account value >= $1k **or** volume >= $5k, with
Polymarket volume >= $1k as a hard floor. That fixes the round-4 over-strictness: requiring
both venues live *simultaneously* rejected people who rotate between them, which is the
actual cross-venue pattern.

  **The specified conviction formula is not on a 0-100 scale, so I normalised it.**
  As written, `log10(1+hl)*40 + log10(1+pm)*35 + min(25, max(0,pnl)/100)` passes 100 from
  the first term alone once hl > ~$316: a $1k/$1k actor scores **225**, a large one **515**.
  Clamping would put every real actor at exactly 100 and rank nothing. The log terms are now
  divided by a reference decade span (`TITAN_HL_REFERENCE_VALUE` $10M,
  `TITAN_PM_REFERENCE_VOLUME` $1M) before weighting, which keeps the intended 40/35/25 split
  and the logarithmic shape while actually landing in 0-100 and discriminating across
  realistic sizes (1k/1k -> 34.7, 50k/20k -> 71.9, 500k/100k -> 86.7). The literal formula
  is preserved as `conviction_score_raw()` for traceability, and a test asserts it exceeds
  100 so the reason for normalising stays documented.

**Task 3 - dynamic coverage thresholds.** `coverage_threshold_for(hours)`: 75% up to 24h,
60% up to 72h, 50% up to 168h, and no further relaxation beyond a week. A flat percentage
was not a flat amount of evidence - 70% of a day is 17 observed hours, 70% of a week is 118.
The label now names the bar that was actually missed. Same data can now legitimately pass a
24h window (83% coverage) and fail a 72h one (28%).

**Task 4 - persistent collector service.** `run_collector_service.py` +
`run_monarch_collector_service.bat`. Supervises the collector as a long-lived child:
exponential backoff on crash (2s -> 300s cap), backoff reset after a run survives 120s so
one bad night does not permanently slow recovery, optional restart budget, graceful
SIGINT/SIGTERM shutdown, and single-line JSON logs to
`data/collector_service.jsonl`. It reports **measured snapshot coverage** every 15 minutes
rather than process uptime, because a collector that is up but not persisting looks
identical from the outside - coverage below 95% logs at WARNING.
`--coverage-only` prints current coverage and exits.

**Tests**: 180 -> 224 (`tests/test_round5_refinements.py`, 44 new, all offline - the
supervisor is tested against a fake child process, so no real collector is spawned).
Two round-4 tests asserting the old flat 70% label were updated to the dynamic contract.
Polymarket 173 still green. pyflakes clean.

## What changed (round 4)
2026-08-31 (Antigravity round 4). Three tasks, plus one correction to my own earlier claim.

**CORRECTION — cross-venue overlap is real; my earlier "0%" was wrong in scope.**
I had measured only the 17 *discovered whales* and concluded no overlap existed. Re-measured
against a random 120-address sample of `hyperliquidusers.txt`: **31.7% have a Polymarket
profile** (Antigravity's 18.5% was directionally right; my 0% was not). But profile
existence is close to meaningless — a profile is created on wallet connect. Only **6.7%
have ANY Polymarket volume** and **3.3% have more than $1k**. That distinction drove the
Task 2 design.

**Task 1 - `analytics/squeeze_engine.py` + `python main.py squeeze`.**
Scores positioning stress 0-100 for the ~86% of perps with no spot leg, where funding is
directional risk rather than harvestable basis. Components: funding percentile against the
asset's *own* 24h history (40%), sign persistence (25%), OI expansion (20%), absolute
funding cost saturating at 200% APR (15%). Classifies `🔥 SHORT SQUEEZE WATCH` (crowded
shorts, breaks up) vs `💧 LONG CASCADE WATCH` (crowded longs, breaks down). Rendered as a
"Squeeze & Exhaustion Matrix" in `HyperLiquid_Monarch.md`.

  Design fix found during testing: folding the percentile to a bare distance-from-50 scored
  *unusually low* funding identically to *unusually high*, which mean opposite things.
  `xyz:CRWD` scored 85 while its funding sat at its 24h low. Extremity now counts only when
  it points the same way as the sustained regime (`is_regime_aligned`); a rate that has
  retreated toward neutral is tagged `is_exhausting` instead of scoring as loaded.

**Task 2 - `analytics/titan_pipeline.py` + `cross_market_titans` table + `main.py titans`.**
Bidirectional discovery: `hl_to_pm` asks Gamma whether an HL address has a Polymarket
profile; `pm_to_hl` asks `clearinghouseState` whether a Polymarket trader holds perp
collateral, trying every known alias (wallet / proxy / EOA). Confirmed matches persist to
`cross_market_titans`, which `Monarch_Hub.md` now reads in preference to recomputing the
live join. All network lookups are injected, so the pipeline is fully testable offline.

  **The gate is symmetric, and that matters.** Gating only on Polymarket volume produced 4
  "titans" from a 120-address scan — all of which turned out to have **no live Hyperliquid
  account**. A one-sided actor is not a cross-market actor. With activity required on both
  venues the honest answer on current data is **0 confirmed titans**. The pipeline is
  verified working (it finds matches when both sides are active, tested synthetically and
  by relaxing the gate).

**Task 3 - backtester coverage safety gate.** Below `MIN_COVERAGE_FOR_APR_PCT = 70.0`,
`realised_apr` is set to `None` and `realised_apr_label` reads
`"Insufficient History (<70%)"`. Suppressed rather than caveated, because a printed number
gets read and a caveat does not — at 1.7% coverage the old field extrapolated to +3313%.
`funding_pnl_pct` is still reported: the measured return is real, only the extrapolation is
withheld.

**Tests**: 132 -> 180 (`tests/test_squeeze_and_titans.py`, 48 new, all offline).
Polymarket 173 still green. pyflakes clean.

## What changed (round 3)
2026-08-31 (Antigravity round 3). APR mechanics confirmed correct upstream; three tasks.

**Task 1 - Polymarket EOA/proxy identity resolution.**
`pnl_scanner.resolve_polymarket_profile()` + `resolve_pending_identities()`, new
`proxy_wallet` / `eoa_address` / `identity_resolved_at` columns (migration follows the
existing ALTER pattern). `cross_market_scanner` now matches on an **alias index** built
from stored wallet + proxy + EOA, and can optionally push an HL address through Gamma
(`resolve_gamma_proxy`) to match by proxy.

  **Empirically established, contra the task wording**: Gamma `/public-profile` returns
  **only `proxyWallet`** - there is no `eoa_address` field to capture. The endpoint maps
  **EOA -> proxy** one-way (verified: `0x0cb0...` -> `0x6f35...`); there is no reverse
  proxy -> EOA lookup. So `eoa_address` is *inferred*: if a queried address resolves to a
  different proxy, the queried address was the EOA. Resolved 63/69 traders; 5 were stored
  under an EOA distinct from their proxy, growing the alias index 69 -> 74 keys.
  Overlap is still **0**, but now for a verified reason rather than an assumed one: all 17
  HL whales were pushed through Gamma and every one 404s - they have no Polymarket account
  at all. The join is no longer the suspect.

**Task 2 - 7-day amortised net APR + spot backing.**
`net_apr_after_spread(item, holding_period_days=7.0, hedge_legs=None)`. Cost model:
`spread% x legs x (365/holding_days)`, where a hedged basis trade pays 2 legs (perp + spot)
and a directional one pays 1. The old 1-day assumption over-penalised every row by ~7x.
Added `expected_pnl_pct()` (period return, not annualised) and `funding_payments_over()`.
`is_spot_backed` / `spot_symbol` / `trade_type` come from the live spot universe via new
`rest_client.get_spot_meta()`, checking wrapped tickers too.

  **Key finding**: Hyperliquid lists BTC/ETH/SOL on spot only as **UBTC/UETH/USOL**, and
  **373 of 436 perps (86%) have no spot leg at all**. Only **22 of 143** liquid
  opportunities are genuine basis arb; the rest are directional bets that earn funding.
  The recommendation text no longer advises "Long Spot" for markets where no spot exists -
  it says `DIRECTIONAL - no spot hedge`.

**Task 3 - historical funding backtester.** New `analytics/funding_backtester.py` +
`python main.py backtest [--coin X] [--hours N] [--min-coverage N] [--spot-backed]`.
Funding is integrated by **time**, not averaged over samples: snapshot density swings from
~8s (collector running) to hours (stopped), so sample-averaging would let a dense burst
outvote a long quiet stretch (validated: 1.09% correct vs 8.59% naive). Intervals beyond
`max_gap_hours` are treated as unobserved and excluded rather than extrapolating a rate
across a collector outage; `coverage_pct` reports how much of the window was really seen.

  **Data-quality finding**: the retained 72h of history is only ~1.7% observed - the
  collector has run in short bursts, not continuously, so per-coin series are 860 samples
  clustered into ~1.2h with a 17h hole. The ranking correctly returns nothing at the
  default 25% coverage floor and says why. Verified working on a fresh continuous window
  (49.6% coverage) after a 3-minute collector run.

  That run also demonstrated the Task 2 point concretely: `para:ANSEM` earned +648%
  realised funding APR while its unhedged price leg moved -0.12%, for a **net loss**.
  Funding yield without a hedge is noise against the directional move.

**Tests**: 95 -> 132 (`tests/test_backtester_and_identity.py`). Polymarket 173 still green.

## What changed (Antigravity round 2)
2026-08-30 (Antigravity audit follow-ups). Audit confirmed all 4 exporter bugs and the
A->LONG / B->SHORT liquidation semantics as correct; these are the three assigned tasks.

**Task A - content-hash dirty checking.** `write_note_if_changed()` in
`analytics/obsidian_links.py`, wired into all 6 note-write sites across both suites.
The non-obvious part: every note carries a per-sync timestamp (`last_synced`,
"Last Updated"), so hashing raw content would mark every note dirty on every pass and
save nothing. Volatile lines are normalised out before the SHA-256, so only substantive
change triggers a write. Measured on a settled 55-note shared vault: **0 of 55 rewritten**
on repeat syncs (previously all 55, every 15s under `--watch`). Skipped notes keep their
mtime, which is what actually stops Obsidian re-indexing. Corrupt/unreadable notes are
rewritten rather than skipped.

**Task B - Cross-Market Titan scanner.** New `analytics/cross_market_scanner.py` joins
`whale_wallets` (hyperliquid_data.db) and `sharp_traders` (polymarket_whales.db) on
lowercased address, ranked by a conviction score (HL open position notional + PM 7d
realized PnL). Both DBs opened **read-only**; a missing/locked/schema-shifted DB degrades
to an empty result, never an exception, because this feeds an exporter that must not fail
a sync. Renders as a "Cross-Market Titans" section in `Monarch_Hub.md`.

  **Empirical result: zero overlap today.** 17 HL whales vs 69 PM sharps -> 0 matches;
  also 0 against the full 5,014-address `hyperliquidusers.txt`. The likely structural
  reason is that Polymarket routes activity through per-user **proxy wallet contracts**,
  so the address it records is usually not the EOA that person uses on Hyperliquid. The
  join is correct and tested (synthetic overlap, case-insensitive), but it may
  structurally under-match real humans. The empty-state note in the hub explains this
  rather than looking broken, and `diagnose()` reports corpus sizes so "no overlap" can be
  told apart from "empty database". **Open question for Antigravity: is EOA-level joining
  the right key at all, or should this match on Polymarket's proxy-factory owner instead?**

**Task C - funding arb tradeability gates.** OI floor ($250k), 24h volume floor ($100k),
and an opt-in live top-of-book spread check (`--check-spreads`, 25bps max, capped at 8
l2Book calls per direction to bound rate-limit spend). Rejected opportunities are returned
in a new `rejected` key with a reason string, surfaced via `main.py arb --show-rejected`.
This finally uses `analyze_orderbook_depth()`, which existed but was dead code.

  **This materially changed the output**: 95 of 239 "opportunities" are filtered.
  The previously top-ranked `para:ANSEM` (+743% APR) fails the OI floor; `para:COHR`
  (+308% APR) has **$1,545** of 24h volume; and `SKR` (-2739% APR) - the headline row in
  last sprint's Obsidian export - has a **125bps spread** and is untradeable.
  `net_apr_after_spread()` reports yield net of round-trip spread cost.

**Tests**: 64 -> 95 (`tests/test_cross_market_and_arb.py`). Polymarket 173 still green.
Shared vault re-verified: 55 notes, 72 wikilinks, 0 broken.

## What changed (Obsidian linking sprint)
2026-08-30 (later) - Obsidian cross-suite linking pass, on top of Antigravity's exporters.

**The core structural finding**: Obsidian resolves `[[wikilinks]]` only within a single
vault root. HL_Monarch and Polymarket_Monarch each defaulted to their own
`obsidian_vault/`, so "inter-linking between both suites" was impossible as built - any
cross-link would have rendered as an unresolved stub. Both exporters already honoured
`OBSIDIAN_VAULT_PATH`, so the mechanism existed; what was missing was a layout that
survives sharing, plus the links themselves.

- **New `HL_Monarch/analytics/obsidian_links.py`** - one definition of the shared vault
  layout, imported by both suites (Polymarket imports it defensively and degrades to
  standalone if HyperLiquid is absent). Suites namespace their entity notes
  (`Whales/` vs `Wallets/`) so they never collide in one vault.
- **Conditional cross-links**: every cross-suite link is emitted only when the counterpart
  note actually exists in the same vault. Shared vault -> links appear both ways;
  separate vaults -> links are silently omitted. A standalone export never renders a
  dead link. Verified by a link validator over every generated note.
- **New `Monarch_Hub.md`** - vault index written by whichever exporter runs, listing only
  the suites actually present, with entity-note counts and setup instructions when only
  one suite is exporting.
- **HL whale notes** (`Whales/0x....md`) - HL previously produced a single dead-end note
  with zero wikilinks while Polymarket had 35 linked trader pages. Whales are now linkable
  entities with frontmatter, portfolio metrics, an explorer link, and the same
  research-note preservation Polymarket uses (verified: hand-written notes survive
  regeneration while metrics refresh).

**Bugs found in the exporter and fixed** (all three were visible in the committed
`HyperLiquid_Monarch.md`):
- Liquidated size always rendered `$0.00` - it read `l.get("sz_usd")`, a column that has
  never existed on `liquidation_events` (the column is `notional`).
- Position side always rendered `SHORT LIQ` - it compared against `"LONG"`/`"SHORT"`, but
  the table stores the fill aggressor as `'B'`/`'A'`. Now maps A -> LONG LIQ, B -> SHORT LIQ,
  matching how `LiquidationFadeStrategy` reads the same field, with UNKNOWN for anything else.
- Funding arb table only ever showed short-harvest rows - it concatenated
  `short + long` then sliced to 10, and the short list alone is far longer. Now interleaves
  both directions.
- Whale notes claimed "Hyperliquid System Liquidator" for 8 of 17 accounts, none of which
  are. `whale_tracker.is_liquidator` means "position reports no liquidationPx"
  (well-collateralised), not "backstop liquidator". The note now uses the authoritative
  `HL_SYSTEM_LIQUIDATOR_ADDRESSES` set for that title and reports the heuristic honestly as
  margin status.
- `run_obsidian_sync_loop` had no per-iteration error handling, so one DB lock or network
  blip killed the daemon permanently. Now logs and retries on the next tick.

**Tests**: 45 -> 64 (`tests/test_obsidian_linking.py`, all offline). Includes a wikilink
validator asserting zero unresolved links in both standalone and shared vaults.
Polymarket's 173 tests still pass after its `obsidian_sync.py` change.

## What changed (earlier, same day)
2026-08-30 — audit + hardening pass. Nothing renamed; all CLI commands and dashboard
hotkeys behave as before.

- **Rate limiting was 2x over the real ceiling.** Hyperliquid meters `/info` by request
  *weight* (1200/min per IP), not request count: `metaAndAssetCtxs` costs 20, `l2Book`/
  `allMids`/`clearinghouseState` cost 2. The old limiter counted requests, and the 3s poll
  over 6 DEXes spent 2400 weight/min. Limiter is now weight-aware, process-wide (shared
  bucket — the budget is per-IP), and `REST_POLL_INTERVAL` is 8.0s (~900 weight/min, leaving
  headroom for wallet/whale scans, which the collector previously starved).
- **DB grew without bound.** 79MB from ~1 day; `liquidation_clusters` alone accrued
  3.6M rows/day. Added retention windows (`SNAPSHOT_RETENTION_HOURS=72`,
  `CLUSTER_RETENTION_HOURS=24`, `TRADE_RETENTION_HOURS=168`), `wal_autocheckpoint`, a
  `run_maintenance()` prune+`wal_checkpoint(TRUNCATE)` pass on a 5-min loop in the collector,
  and a `python main.py maintain [--vacuum]` command. Prune always keeps the newest row per
  coin, so a collector outage can't blank the dashboard.
- **New `latest_snapshots` table** (one row per coin, upserted inside `insert_snapshots`).
  Deriving "latest per coin" from history was a full covering-index scan — the dashboard did
  that once per frame. Now 1.05ms vs 28.7ms (27x) and, more importantly, constant as history
  grows. `backfill_latest_snapshots()` migrates old DBs; already run on the live DB.
  Note: a first attempt at this (bounding the subquery to a 15-min window) did *not* work —
  the index leads with `coin`, so a time filter can't seek and it was slightly slower.
- **WS reconnect was a hot loop.** A clean server close broke the inner loop and reconnected
  with zero delay. Now exponential backoff + jitter on every path (reset on healthy connect),
  `self.ws` cleared on disconnect, app-level `{"method":"ping"}` heartbeat every 30s (HL reaps
  idle sockets ~60s; only the protocol-level ping existed before), and `_resubscribe_all`
  snapshots the subscription set under the lock (concurrent `subscribe_*` could raise
  "set changed size during iteration" — the collector subscribes 48 coins while connecting).
- **Collector no longer blocks the event loop.** WS trade handlers buffered into memory and
  flushed every `DB_FLUSH_INTERVAL` (2s, a setting that existed but was never used) via a
  single-thread executor; REST polling moved off the loop too. Buffers are capped and drop
  oldest-first. Whale portfolio scans and webhook alerts now use bounded `ThreadPoolExecutor`s
  instead of spawning one thread per event.
- **Dashboard scan caching.** Holding tab 6 (Whales) issued ~15 REST calls *per rendered
  frame*; now TTL-cached (30s whales, 5s arb) and serves stale data rather than blanking on error.
- Bug fixes: `main.py liqs` built a panel and never printed it (command produced no output);
  dashboard's dynamic cluster fallback read `openInterest` where the SQLite column is
  `open_interest`, so it always used the 1000.0 placeholder and reported bogus notionals;
  `format_currency` mangled negatives (PnL/equity); cluster panel crashed on null `estimated_px`.
- Cleanup: unused imports, duplicate `import time`, dead `hasattr(self, "whale_tracker")`,
  dropped the deprecated `websockets.WebSocketClientProtocol` annotation (removed in newer
  websockets majors).
- New tests: `tests/test_maintenance.py` (retention, WAL checkpoint, current-state table,
  weighted limiter), `tests/test_ws_resilience.py` (dispatch isolation, resubscribe under
  concurrency, reconnect backoff — all offline/faked, no network).

## Next / open questions
- **The 48h validation window is now running.** Leave `launch_service_background.bat`
  alone; check progress with `launch_service_background.bat status`. When coverage has been
  high for a sustained stretch, run `python main.py validate` - and report the SAMPLE SIZE
  before the lift, because the lift is uninterpretable until the denominator is credible.
- Restarting the service to pick up code changes costs a small coverage gap each time.
  Worth batching config changes rather than restarting per edit during the window.
- **Settle the replay methodology before reading the next validate run.** If Antigravity's
  177 came from a non-time-aligned mark, the exotic sample is ~33, not ~177, and the
  precedence test is still underpowered. Agreeing which number is real is now the gating
  question - the acceptance bar we set is meaningless against an inflated denominator.
- Lowering SQUEEZE_MIN_NOTIONAL_OI to $100k widens the rotation candidate pool. Worth
  re-checking that 35 slots still cover the qualifying set, or the cap starts silently
  truncating the very markets this round admitted.
- The exotic alert tier fires at $2.5k/1.5%. On a busy day that could be noisy; there is no
  rate limit or dedupe on alerts beyond the bounded thread pool.
- **20 exotic liquidation events is still thin for the validator**, which needs 30+
  observations per group before it reports anything as significant. The detection fix
  removes the blocker, but the precedence question still needs sustained runtime - this is
  now purely a matter of leaving the service running, not of more code.
- Genuine high-slippage exotic sweeps are rare (20 of 10,443 fills = 0.19%). That is correct
  behaviour rather than a shortfall, but it means the exotic sample will grow slowly. If it
  is still underpowered after a few days, the honest options are a longer horizon or a
  lower slippage bar - and lowering the bar should be a deliberate, measured decision, not a
  quiet tweak to make the number appear.
- The fade strategy now places resting limits that may never fill. `open_orders` is not
  aged out anywhere, so a stale limit from a cascade hours ago can still fill on unrelated
  price action. An order TTL is probably wanted before anyone reads the paper PnL seriously.
- **The precedence question is now genuinely answerable - it just needs hours.** Leave the
  service running, then `python main.py validate`. Exotic liquidations should start
  appearing in `liquidation_events` for the first time. Agree the acceptance bar (what lift
  counts as "this works") before looking at the number.
- Rotation currently reacts to squeeze score only. A coin that squeezes, liquidates, and
  then falls below threshold gets unsubscribed - possibly before its liquidation cascade
  finishes. A cooldown (keep a coin subscribed for N minutes after it drops out) would stop
  the feed cutting out mid-event.
- `SQUEEZE_ROTATION_MAX_COINS = 20` is arbitrary. WS subscriptions are free but not
  unlimited; Hyperliquid's per-connection subscription cap should be checked before raising it.
- **The precedence question is now blocked purely on data, and the tooling is ready.**
  Leave `launch_service_background.bat` running for a few days, then re-run
  `python main.py validate`. If exotics start recording liquidations, this finally answers
  whether the squeeze flags carry information - and if lift stays ~1.0, the engine should be
  reconsidered rather than tuned.
- Liquidation coverage is itself the narrower bottleneck: only 5-6 coins have any events at
  all, because `liquidation_events` is populated from the WS trade feed for the core
  watchlist only. Subscribing the exotic perps the squeeze engine actually flags would close
  the loop faster than simply running longer.
- The validator walks every coin serially with one query per point; at 1h steps over 72h
  that is fine, but a finer step or a wider universe will want batching.
- **Run the collector service before trusting any downstream number.**
  `HyperLiquid\run_monarch_collector_service.bat` (or `python run_collector_service.py`).
  Coverage at the time of writing is ~0.3% of 24h; the backtester and the squeeze engine's
  percentiles both need this near 99% to mean anything.
- The squeeze engine still has no coverage gate of its own - only `SQUEEZE_MIN_SAMPLES=20`.
  Once the service has run a while, it should adopt the backtester's dynamic-threshold
  approach so thin windows cannot produce confident-looking percentiles.
- Conviction reference values ($10M HL / $1M PM) are estimates of "top of corpus", not
  measured. Once the titan table has real rows they should be set from actual percentiles.
- Squeeze weights (40/25/20/15) and the exhaustion bands (35/65) remain unfitted judgement
  calls, validatable against realised forward volatility once continuous history exists.
- **The squeeze engine shares the backtester's data dependency.** Percentiles and OI deltas
  are computed from `asset_snapshots`; with the collector running in bursts the 24h window
  is thinly observed. Scores are directionally useful but will sharpen a lot once the
  collector runs continuously. `SQUEEZE_MIN_SAMPLES = 20` is the only guard right now -
  a coverage gate like the backtester's would be more honest.
- **Titan discovery is rate-limited by design** (one Gamma call per address, one
  clearinghouseState per alias). A full sweep of all 5,014 known addresses would take
  ~20 minutes at the current cadence. Worth running once as a batch job to establish the
  true bilateral-activity rate, rather than sampling 120 at a time.
- Squeeze scoring weights (40/25/20/15) are a judgement call, not fitted to anything. Once
  there is continuous history, they could be validated against realised forward volatility.
- **The backtester needs a continuously-running collector.** At 1.7% coverage the 72h
  history cannot support a real backtest. Run `python main.py collector` as a persistent
  service (or scheduled task) before trusting any ranking; retention already keeps 72h.
- **Cross-market overlap is still zero, and may stay that way.** Identity resolution is now
  correct on both sides, so the remaining explanation is simply that these populations do
  not intersect. Worth testing against a much larger HL corpus (the 5,014-address
  `hyperliquidusers.txt`) rather than only the 17 discovered whales.
- `net_apr_after_spread` still ignores slippage beyond top-of-book, funding-rate drift
  during the hold, and the spot leg's own borrow/carry cost. It is a floor, not a forecast.
- `--check-spreads` remains opt-in, so exported/dashboard rows show `spread_bps = None`
  and therefore an uncosted net APR.
- **Cross-market join key is unproven.** Zero real overlap so far (see Task B above).
  If Polymarket proxy wallets are the blocker, the join needs the proxy->owner mapping,
  not the raw address. Until then the Titans table will stay empty in production.
- Spread checks are opt-in and capped, so the Obsidian export and dashboard currently
  show OI/volume-filtered rows with `spread_bps = None`. Wiring `check_spreads=True` into
  the exporter would cost ~32 weight per sync - affordable at the 8s poll cadence, but it
  was left off by default rather than silently spending budget.
- `net_apr_after_spread()` assumes a 1-day hold to annualise the one-off spread cost.
  That is deliberately conservative; a holding-period parameter would be more honest.
- **Ordering caveat**: cross-links converge only after both exporters have run once into a
  shared vault. The first suite to run cannot see a counterpart that does not exist yet, so
  its dashboard omits the link until its next sync. Harmless in `--watch` mode; worth
  knowing for one-shot runs.
- Nothing automatically links an address that appears in BOTH suites - the hub explains the
  idea but matching is manual. A join on `whale_wallets.address` vs Polymarket's trader
  table would surface genuine cross-market actors automatically.
- The vault layout is duplicated knowledge: Polymarket reaches into HyperLiquid's
  `analytics/obsidian_links.py` via a sys.path insert. Fine while both live under `DEV/`,
  but a small shared package would be cleaner if they ever move apart.
- `orderbook_snapshots` is still never populated — `analyze_orderbook_depth()` and
  `insert_orderbook_snapshot()` both exist but nothing calls them. An `l2Book` poll loop
  (weight 2/call, cheap) on the core watchlist would fill it.
- `detect_liquidation_trade` writes *any* fill ≥ $50k into `liquidation_events` with source
  `trade_flow`, so that table mixes real liquidations with plain whale orders. Consider
  splitting, or filtering on `source` in the UI.
- Paper trader has no stop-loss/take-profit execution: `stop_loss`/`take_profit` are stored on
  the position but nothing ever checks them against mark price, so fade trades never exit.
- Cluster model assumes OI is spread evenly across leverage tiers (`tier_weight = 1/len(tiers)`).
  Fine as a heatmap heuristic, not a real distribution.
- Still no git init, no venv/lockfile (`requirements.txt` is 2 lines: rich, websockets).
- `DatabaseManager` is a singleton keyed to the first path used; it now warns instead of
  silently redirecting writes, but tests still poke `_instance = None` to reset it.

---

## Session Log — 2026-09-01 (Round 15, Claude Code)

### Status
Round 15 "institutional alpha upgrade" implemented in full. 442 HL tests + 194 Polymarket
tests pass offline. Collector service restarted on the new code (supervisor PID rotates;
check `python run_collector_service.py --status`).

### What changed
- **`analytics/indicators.py` (new)** — EMA/RSI/ATR over resampled `asset_snapshots`.
  These are point samples, not OHLC: ATR is a close-to-close proxy and understates a real
  ATR. Usable as a regime filter, not as an exchange-grade indicator. Everything is a
  PERCENT (1.93 == 1.93%).
- **Regime gate** in `liquidation_fade_strategy.py` — `regime_permits()`:
  BUY needs `price >= EMA` OR `RSI <= 32`; SELL needs `price <= EMA` OR `RSI >= 68`.
  Unknown regime BLOCKS (`REGIME_BLOCK_WHEN_UNKNOWN=True`) — permitting on unknown would
  silently restore the unfiltered baseline. Gate runs LAST so rejections are attributable;
  counted in `blocked_by_regime`.
- **ATR-scaled geometry** — `geometry_for()`: offset `max(0.40%, 0.50xATR)`,
  TP/SL `max(0.30%, 1.0xATR)`, still 1:1. Both floors matter: at 1m buckets ATR is ~0.025%
  so the floor always wins (hence 15m buckets), and a pure 1.0xATR target on BTC is ~0.15%
  against which the 4.5bp round trip is ~31% of gross.
- **Dual rotation pool** in `market_collector.py` — 20 volume-ranked majors + 15 exotics
  (`OI < $5M` AND `vol > $100k`), unused exotic slots spill back to majors. Fixes the tier
  collapse: volume-only ranking selected exclusively >$5M OI books, so all 12 baseline fills
  were the $10k major tier and the exotic tier built in rounds 9-12 never fired once.
- **`_refresh_regimes()`** runs on the rotation cadence on the DB executor, never on the WS
  path. All 35 watched markets currently return `sufficient: True`.
- **`execution/strategies/basis_strategy.py` (new)** + `main.py basis` — long spot/short perp.
  Deliberately a THIN layer over the pre-existing `analytics/funding_arbitrage.py`, which
  already had the spot mapping, liquidity gates, spread check and amortised net-APR maths.
- **`Polymarket_Monarch/dutched_arb.py` (new)** — negative-risk dutching scanner. No `main.py`
  exists in that project, so it is a standalone script with its own argparse, matching
  `pnl_scanner.py`.
- **Paper account reset to $100k.** Baseline archived to
  `data/experiments/baseline_unfiltered_N12_2026-09-01.json` (+ `.meta.json`); the new run is
  pre-registered in `data/experiments/regime_filtered_v1.meta.json`.
- Pre-Round-15 test fixtures now pass `regime_enabled=False` explicitly — they assert exit
  and fee mechanics and predate the gate. 57 tests failed until this was made explicit.

### Measurements worth keeping
- Filter admits **53% of direction-slots** right now (BUY 28/35, SELL 9/35 — the tape is
  broadly above its EMA). Expect roughly **half the trade rate** of the baseline, which did
  12 closes in ~24h. **N=50 is plausibly 5-8 days away, not 48h.**
- No dutch book exists on Polymarket: tightest of 200 scanned events was **1.0100**
  (-1.00% edge). The directive's `< 0.96` threshold is 5 points beyond the tightest book
  and would never fire. Only 8 of 200 events were even priceable.
- Live `basis` scan: **1** constructible trade (MON, gross 56.9%, net 56.5% on a measured
  0.4bp spread). `para:AVGO` rejected — spread unmeasurable.

### Next / open questions
- **The N=50 pre-registration was abandoned at N=12.** The archived control is the only
  unfiltered baseline; do not overwrite it. A PASS on `regime_filtered_v1` identifies the
  BUNDLE (filter + geometry + dual pool), not which of the four changes earned it —
  attribution needs an ablation.
- Long-standing items from earlier sessions below still stand (orderbook_snapshots unused,
  no git init, DatabaseManager singleton, liquidation_events mixing sources).

### Round 15 polish (same session, after Antigravity cross-check)
- **True-range ATR** replaces the close-to-close proxy (`resample_ohlc` +
  `atr_pct_true_range`). Antigravity proposed a flat 1.25x multiplier; rejected on
  measurement — 1.25 understated the real ratio in **35/35** markets, and the measured
  ratio spans **1.39 (xyz:CRWD) to 1.98 (INJ), median 1.59**, so no constant fits. With
  ~67 samples per 15m bucket the extremes are directly observable, so it is computed per
  market. Fee burden falls from ~15% of gross to ~8-11% on volatile names.
- **`cost_measured` flag** on funding rows + `FundingArbitrageEngine.is_costed()`.
  Antigravity asked to reject uncosted rows inside `funding_arbitrage.py`; that would have
  broken the `arb` command, which legitimately displays gross APR for uncosted rows.
  `net_apr_after_spread` keeps its documented "never fabricate a cost" fallback; the
  refusal stays in `basis_strategy`, now driven by an explicit flag rather than a None check.
- **10-minute exotic warmup NOT implemented — it solves a non-problem.** The REST sync
  already stores snapshots for *all* markets, not just WS-subscribed ones: **437 of 438
  coins already have >=50 15m buckets**, so a newly rotated exotic arrives with a full
  regime. It is also arithmetically impossible as specified — 10 minutes yields 0 complete
  15m buckets, and EMA-50 needs 50 buckets = 12.5 hours.

### !! BLOCKING FINDING — the current run cannot answer its own question !!
Targets are sized off a **15-minute** ATR bar; positions are force-closed after
**FADE_POSITION_MAX_HOLD_SECONDS = 600s**. Measured on live data:
- Median time to reach a 1.0xATR target: **1,224s** — more than double the hold window.
- Target reached inside 600s in **<50% of cases in 35/35 markets** (median 16.5%,
  BTC 3.4%, xyz:SP500 ~0%).

So most positions exit **TIME_STOP at the mid**, not at TP or SL. The 1:1 geometry is
largely decorative and the run measures a near coin-flip minus fees. This retrodicts the
archived control exactly: 25% win rate / PF 0.123 is what a fee-laden time-stop coin flip
looks like — which means the baseline may never have tested the fade thesis either.

NOT changed unilaterally (max hold is a frozen strategy parameter). Suggested fix:
`FADE_POSITION_MAX_HOLD_SECONDS` 600 -> ~1800, or halve `FADE_ATR_TARGET_MULT`. Either
needs a fresh registration. Recorded in `data/experiments/regime_filtered_v1.meta.json`
under `known_defect_not_fixed`.

Tests: 450 HL + 194 Polymarket passing.

### Round 15 final — geometry realigned, and the fade thesis measured
Authorised and applied: `FADE_ATR_TARGET_MULT = 0.50`, new `FADE_ATR_STOP_MULT = 0.50`
(separate multipliers, still 1:1), `FADE_POSITION_MAX_HOLD_SECONDS = 1800.0`,
`FADE_ATR_OFFSET_FLOOR_PCT` 0.40 -> 0.30. `geometry_for()` now returns
(offset, target, stop). The holding-window tripwire test fired on the change and was
inverted to assert the mismatch stays resolved.

**`analytics/wick_benchmark.py` + `main.py excursion` (new).** MFE/MAE excursion
benchmark with a matched RANDOM-ENTRY CONTROL — without it the raw ratio is
uninterpretable, since a trending tape moves it on its own.

### !!! THE FADE THESIS IS MEASURED AS WRONG-SIDED !!!
`trade_sweep` (the signal the strategy actually trades), n=466, 98% coverage:

  horizon   MFE      MAE      ratio   control   edge
      5m   0.711%   1.310%   0.543    1.185   -0.642
     15m   1.175%   2.299%   0.511    1.068   -0.557
     30m   1.530%   2.982%   0.513    1.092   -0.579

VERDICT: **NO_ALPHA**. After a liquidation sweep price moves roughly **2x further
AGAINST the fade than for it**. This is continuation, not mean reversion — the fade is
systematically on the wrong side. `trade_flow` (n=9,368, the contaminated >=$50k-fill
set) scores 0.981 vs a 0.978 control: pure noise, edge +0.003, exactly as expected.

The limit offset does NOT rescue it. Measuring from the actual fill rather than the mark:
  offset 0.00% -> ratio 0.392 (94.7% filled)
  offset 0.40% -> ratio 0.436 (90.8% filled)
  offset 1.00% -> ratio 0.555 (78.6% filled)
Deeper offsets improve the ratio monotonically but never approach 1.0, and cost fill rate.

**Corollary worth testing: the INVERSE trade.** Swapping the legs gives ~1.95 at 30m,
above the 1.50 alpha bar. Do NOT just flip the sign and deploy — a momentum entry is a
taker chasing a move, so fees and slippage differ, and the control at ~1.09 means some of
that is tape drift. It needs its own pre-registered run.

This also explains BOTH paper runs: a wrong-sided entry with a fee drag produces exactly
the archived control's 25% win rate and PF 0.123. The Round 15 filter, the geometry and
the dual pool were all real improvements to the *execution* of a signal that does not work.

Tests: 475 HL + 194 Polymarket passing.

---

## Session Log — 2026-09-01 (Round 16: fade retired, two engines built)

### Status
The reactive liquidation fade is RETIRED. Two replacement engines built.
505 HL + 222 Polymarket tests pass. Service restarted on the new code.

### 1. Fade retirement
`FADE_STRATEGY_ENABLED = False` in settings; the collector still DETECTS and stores
sweeps (they are the excursion benchmark's input) but no longer trades them.
Module and its ~100 tests KEPT, not deleted — deleting would have destroyed the
record of what was measured, and its paper/fee/exit machinery is shared with the
harvester. Docstring marked RETIRED with the evidence.

Significance re-derived independently rather than taken on trust: paired MFE−MAE per
event gives **t = −10.52** (n=466), MAE exceeded MFE in **72.7%** of events, and
**0 of 20,000** bootstrap resamples produced a non-negative mean.

### 2. ENGINE 1 — Polymarket sharp consensus (`consensus_scanner.py`)
Roster from `sharp_traders`, activity via `data-api/activity`, clusters ≥2 DISTINCT
wallets on the same market/outcome/side inside a sliding 3h window, paper copy book.

**Two guards were added after the live run, and both are load-bearing:**
- **Market-making suppression.** The first run fired "consensus" on BUY Up AND BUY
  Down of the SAME 5-minute BTC market — same two wallets, 50 and 53 trades in six
  minutes. Copying both legs buys both outcomes at the ask. Suppressed by a
  contradiction test (same wallets, opposing outcomes) and a churn test
  (>8 trades/wallet in window). **All 4 live clusters were suppressed; zero genuine
  consensus remained.**
- **`MIN_CLOSED_POSITIONS = 10`.** The specified bar (win ≥60%, PnL ≥$5k) selects 12
  wallets, and the top one has a 100% win rate on ONE closed position. Roster is
  ranked by PnL, not win rate. Only **7** wallets clear the bar — the directive asked
  for 20, and 20 do not exist without readmitting lucky one-trade wallets.

Paper copies fill at the CURRENT ask and record `slippage_pct` vs the sharp's price —
we always fill after them, never with them.

### 3. ENGINE 2 — basis harvester (`execution/basis_harvester.py`)
1:1 long spot / short perp cash-and-carry. `main.py basis --harvest` shows the book;
`_basis_accrual_loop` in the collector accrues hourly on the DB executor.
Bars: measured spread required, net APR ≥20%, hold ≥7d, max 5 concurrent.
Accrues the **CURRENT** hourly rate, never the entry rate; a missing rate accrues
**nothing** rather than repeating a stale one.
Bug caught by the flat-state invariant test: entry fee hit cash but not
`realized_pnl`, breaking `cash − starting == realized_pnl` at close. Fixed.

### Next / open questions
- **Neither engine is yet a business.** Basis has ONE qualifying market (MON);
  consensus currently has ZERO signals after market-making suppression. Both need a
  measured opportunity RATE over time before they justify capital.
- The sharp roster may be structurally contaminated: a 100% win rate on 5-minute
  binaries is what spread capture looks like, so "sharp" may be selecting market
  makers rather than forecasters. Worth measuring directly.
- The inverse fade (momentum) scores ~1.95 and remains untested.

### CORRECTION (same session) — the retirement evidence is thinner than first stated
Asked how long the data covered, and the answer materially qualifies the earlier claim.

  trade_sweep (the retirement evidence): 476 events over **15.2 HOURS**, not days
      2026-08-31 13:34 UTC -> 2026-09-01 04:49 UTC, 13 coins, 12 distinct hours
      top 3 hours hold 46% of all events
      **CASHCAT (199) + PONS (197) = 83% of every event, from TWO microcaps**
  trade_flow: 9,647 events over 49.5 hours

The earlier **t = -10.52 and 0/20,000 bootstrap were OVERSTATED** — both assumed 466
independent observations. They are not: 30-minute forward windows on events minutes
apart on the same coin overlap almost completely.

Redone with a CLUSTER bootstrap (resampling the 12 coins rather than the 466 events):

  P(ratio >= 1.0) = 0.024        <- not p < 1e-15
  10 of 12 coins have ratio < 1.0, median per-coin ratio 0.536
  EXCLUDING CASHCAT+PONS: n=70, ratio 0.849 (8 of 10 remaining coins < 1.0)

CONCLUSION HOLDS, WEAKER. The fade is still wrong-sided — the direction is consistent
across almost every coin — but the headline 0.513 is substantially a two-microcap
artifact; the broader-market effect is 0.849, much closer to neutral. Retirement stays
justified (nothing here suggests positive expectancy) but the "mathematically negative
expectancy, p<1e-15" framing is not supported. A proper verdict wants multi-day data
across more coins, and the collector still stores sweeps so that can accumulate.

### Round 16 final — auditing standard, macro filter, tactical basis cap

**Auditing standard is now enforced in code**, not convention. Every
`main.py excursion` run prints an `[audit]` line: coins measured, asset-concentration
HHI, top-coin share, and a CLUSTER-bootstrapped p-value (resampling coins, not
events — event-level bootstraps are invalid when forward windows overlap).
`reopening_gate()` blocks reconsidering the fade on a narrow sample.

Current live audit (n=492, 15 coins): **HHI 0.360, top coin 43%**, and
cluster P(ratio>=1.0) = **0.083 @5m, 0.077 @15m, 0.026 @30m**.
Worth stating plainly: **only the 30m horizon clears p<0.05.** The retirement rests
on one horizon of a concentrated sample. Direction is consistent; strength is not
what the original "p<1e-15" implied.

**Pre-registered re-benchmark** in `data/experiments/passive_fade_rebenchmark.meta.json`:
7-day window, N>=500 events, >=20 coins, max 20% per coin, re-open only if
P(ratio>=1.25) > 0.90. Asymmetric by design — retiring cost p=0.024, returning costs
more. Sweeps accumulate passively with execution disabled.

**Polymarket macro duration filter** (`min_market_duration_hours = 24.0`). Two real
bugs found getting it right, both worth remembering:
1. `endDate - startDate` is WRONG for micro-markets. Gamma reports `startDate` as when
   the market OBJECT was created (~24h early) for a 15-minute binary, giving a phantom
   ~23.9h lifetime that clustered just under the threshold BY ACCIDENT. The real window
   is `endDate - eventStartTime` -> 0.25h. First implementation silently passed every
   market it was built to catch.
2. Gamma `/markets` returns only OPEN markets by default, so a 5-minute binary from an
   hour ago is invisible. Needs a second pass with `closed=true`; coverage went 24/94
   -> 92/94 condition_ids.
Live effect: **339 of 525 trades (65%) dropped as sub-24h micro-markets.** Behavioural
guards (contradiction + churn) are KEPT — duration is a blunt proxy, those are direct
evidence, and they fail differently.
Also noted: these micro-markets carry `makerRebatesFeeShareBps: 10000` — they pay maker
rebates, which is precisely why MM bots farm them.

**Basis harvester capped at 2 concurrent** (was 5), matching a realistic 1-2 name
opportunity set.

Tests: 520 HL + 229 Polymarket = 749.

---

## Session Log — 2026-09-01 (Round 17: pruning + execution safeguards audit)

Cross-checked 4 removals and 2 safeguards. 3 confirmed, 3 corrected on measurement.
548 HL + 237 Polymarket = 785 tests. Service restarted.

### FADE RETIREMENT — confirmed, but the premise was FALSE until fixed
"Disabling removes 100% of directional drawdown" was **not true**. `on_mids` was
ungated: `check_open_orders` still FILLED resting limits, so the retired strategy
could open real positions from pre-retirement orders. Two live BTC/ETH limits were
resting when found. Added `wind_down()` + `on_mids(allow_fills=False)`: resting
orders are CANCELLED, while open positions are still managed to their exits (a
retired strategy must wind down, not freeze with exposure). Practical risk was
bounded by the 180s TTL, but the code path allowed it.

### REBATE FARMERS — threshold correct, RATIONALE wrong
Duration distribution is **not bimodal**: farmers at <=0.25h, next band 4-6h, so any
cut between 0.5h and 4h excludes every farmer and nothing else. 6h adopted (24h was
over-excluding). **But what 6h admits is 38 esports markets (LoL/Valorant/CS), NOT
the CPI/Fed/election markets given as justification — those all sit >7d.** Esports
consensus should be judged on its own evidence, not assumed macro-like.
Could not confirm the "~3.8% micro-specific penalty": measured spreads are 2.8%
(<30min) vs 3.4% (macro) on small n. Crossing costs a few percent everywhere; the
case against copying MMs rests on their edge BEING the rebate, not on spread.

### LONG-HARVEST — confirmed, already enforced
`build_position` rejects `funding_apr <= 0`; harvester repeats the check. Only
short-harvest is constructible. `arb` still displays negative rows, correctly
labelled DIRECTIONAL.

### 5-SLOT LOCK -> DYNAMIC EXIT — decay confirmed, EXIT THRESHOLD REJECTED
Decay is real and FASTER than claimed: a >=25% APR reading has median 28.3% at +6h,
15.8% at +12h, **8.4% at +24h**; 63.6% fall below 12% within 24h (not 48h).
BUT a 12% exit floor is value-destroying. Realised yield net of the 0.0900%
round trip:
      6h hold  -> **-0.0612%**, only 16% profitable
     12h hold  ->  +0.0070%, 56% profitable
     24h hold  ->  +0.0465%, 69% profitable
     48h hold  ->  +0.1185%, 78% profitable
At a sustained 12% APR the daily yield is 0.0329%, so a round trip needs **2.74 days**
to pay for itself. A 12% floor churns nearly every position within a day and pays
three days of yield for the privilege. Churn only helps if there is somewhere better,
and the qualifying set is 1-2 names.
Implemented `should_exit`/`sweep_exits` with `BASIS_EXIT_APR_FLOOR = 0.0` — hold
through DECAY, exit on REVERSAL. Threshold is configurable if you disagree.

### PRECISION GUARD — hazard real, but INDEPENDENT ROUNDING IS THE WRONG FIX
Confirmed live: MON perp szDecimals=0 vs spot=2; **2 of 3 spot-backed candidates
have a mismatch** (para:AVGO 2v4, xyz:HOOD 3v4). Sizing was an unrounded float.
Independent per-leg flooring prevents the REJECTED leg but reintroduces naked delta
(1000 perp vs 1000.56 spot). `execution/sizing.py` floors BOTH legs to the COARSER
precision so residual is zero by construction, and refuses rather than returning a
zero size. Also made szDecimals lookup dex-aware — alt-dex universes key on the
prefixed name (`para:TOTAL2`), the main one on the bare name.

### FRONT-RUN GUARD — did not exist, now does
`slippage_pct` was recorded but never acted on. Added `MAX_ENTRY_APPRECIATION_PCT
= 15.0`: refused, not sized down. Sharps at 0.35 with the ask at 0.65 (+86%) is now
rejected; +11% still copies.
