# Polymarket Monarch — Agent Handoff

## Status

Three-tool suite, all working against live Polymarket public APIs (no keys, no paid proxies).
169 pytest tests pass, all offline.

| File | Role | Verify with |
|---|---|---|
| `whale_collector.py` | RTDS WebSocket -> SQLite whale fills | `python whale_collector.py --replay` |
| `pnl_scanner.py` | 7d realized+unrealized PnL per wallet | `python pnl_scanner.py --wallet 0x...` |
| `terminal_dashboard.py` | 3-panel live TUI | `python terminal_dashboard.py --dry-run` |

Run tests: `python -m pytest tests/ -q`

## API facts verified against the live endpoints (2026-08-29)

These were checked by hitting the real APIs, not assumed. Re-check before changing them.

- **Gamma `/events` filters on `tag_slug`, NOT `tag`.** `tag=crypto` is silently
  ignored — it returns the identical unfiltered global feed for every category.
  Confirmed by diffing responses for crypto/politics/economics.
- **`economics` is a thin tag** (often 1 active event). `MACRO_CATEGORIES` in
  `terminal_dashboard.py` carries a fallback slug chain (`economics` -> `economy`
  -> `fed-rates` -> `inflation`) to top the panel up.
- **Multi-market Gamma events mix live and settled legs.** Settled legs report
  `closed: true`, price `1`/`0`, and `volume24hr: null` while keeping a huge
  lifetime `volumeNum`. Never rank sub-markets by `volumeNum` — it surfaces
  resolved markets as a meaningless "100%".
- **Wallet address casing differs by endpoint.** REST `/trades` returns
  lowercase addresses; the RTDS socket returns EIP-55 checksummed ones. They are
  the same address (mixed case is only a checksum), so everything is normalised
  to lowercase on write — otherwise one trader occupies two DB rows and is
  counted twice on the leaderboard.
- **`/positions` rows have no timestamp**, so unrealized PnL cannot be windowed
  to 7 days. It is lifetime-to-date on live exposure; `pnl_7d` = 7d realized +
  current unrealized. Documented in `compute_pnl_metrics()`.
- **`/activity` includes non-trade rows** (`REDEEM`, `SPLIT`, `MERGE`, `REWARD`).
  Only `type == "TRADE"` counts toward volume and trade count.
- **REST `/trades` payloads are shape-identical to RTDS `payload`**, which is why
  the replay fixture can mix both sources. `/trades` also supports
  `filterType=CASH&filterAmount=N` for pulling whale fills directly.
- **Gamma `/markets` silently caps at 100 rows** regardless of `limit`. Asking
  for 500 quietly returns 100 -- paginate with `offset`. `order=volume24hr` and
  `ascending=false` both work there.
- **The RTDS socket answers a ping with an EMPTY text frame, not `"PONG"`.** It
  accepts `"PING"`, `"ping"` and `{"action":"ping"}` alike and stays open for all
  three. The receive loop's `if not msg or msg == "PONG"` guard covers both.

## What changed (2026-09-02, Claude Code) — tax-aware sizing

- **New `tax_gate.py`** — the single coupling point to `DEV/Tax_Reserve_Agent`,
  which tracks FIFO cost basis and knows how much of the wallet balance is
  already owed in tax. Handles the `sys.path` bootstrap and the import guard so
  no scanner has to. `TaxGate.clamp_shares(shares, cost_per_share)` returns a
  `GatedSize`; `add_tax_arguments(parser)` adds `--no-tax-gate`, `--cash` and
  `--max-position-pct`.
- **`dutched_arb.py`** — `--shares` is now clamped through the gate BEFORE
  `price_with_depth()` walks the book. Depth pricing a size the bankroll cannot
  fund yields an executable share count and a profit figure for a trade that was
  never placeable, which is the most misleading output the scanner could produce.
  A complete negative-risk set costs the summed ask, so the notional is
  `shares * ask_sum`, not `shares * 1.00`. New pure `gate_shares()` holds the
  logic; `render()` prints the status line and any clamp.
- **`terminal_dashboard.py`** — header carries the escrow / safe-bankroll line.
  `TAX_GATE` is built once at import, not per frame: the hook caches its SQLite
  snapshot for 60s and rebuilding it every tick would discard that. Header layout
  `size` 4 -> 5.

**The gate fails OPEN and labels itself UNGATED.** The agent-side hook
(`MonarchBankrollHook`) fails CLOSED — it rejects orders when it cannot read the
ledger. Monarch places no orders, so refusing to scan because an accounting DB is
missing would be absurd. If anything here ever sends a real order, call
`MonarchBankrollHook.check_order()` directly and honour its rejection instead of
going through this shim.

All 237 pytest tests still pass.

## What changed (2026-09-02, Claude Code - Round 10)

- **`consensus_scanner.py`** now filters copies on after-tax break-even and
  Wilson-shrinks the sharps' win rate first (they were selected for having won, so
  the raw rate made the filter too permissive). Copies derive a category and are
  size-gated through `tax_gate`, tagged `strategy="consensus_copy"`.
- **`dutched_arb.py`** `--min-edge` no longer fails open: an unreachable agent
  falls back to 0.0308 rather than disabling the filter.
- **`tax_gate.py`** carries `FALLBACK_AFTER_TAX_EDGE` and a `strategy` passthrough.

FROZEN for Q1 live deployment alongside the agent. 237 tests still pass.

## What changed (this session)

- **whale_collector**: 20s application-level `PING` keepalive (`ws_keepalive`)
  running as a cancelled-on-exit task alongside the receive loop — Cloudflare
  reaps sockets that look idle. Added `--replay` / `--replay-file` /
  `--replay-delay` / `--db`, and `data/fixtures/sample_trades.json` (22 real
  recorded frames: 16 whales incl. a $324k mega, 6 sub-threshold). Replay
  defaults to `data/replay_whales.db` so offline runs never pollute live data.
- **pnl_scanner**: all HTTP goes through `_rate_limited_get()` — hard 200ms floor
  between requests, `Retry-After`-aware 429/5xx backoff, no retry on plain 4xx.
  PnL engine split into a pure, testable `compute_pnl_metrics()`; realized and
  unrealized are now tracked separately (new DB columns, migrated in place).
  Fixed a volume bug (`max(v, v + usdc*0.5)` was dead code that always took the
  second branch and triple-counted across all three endpoints). `/activity` now
  pages to 500 records.
- **terminal_dashboard**: macro panel is now tag-driven off Gamma
  (`fetch_top_markets_by_tag`), deduped across categories, and prefers genuinely
  contested markets (2–98%) over pinned ones. UTF-8 safety via `safe_glyph()` +
  `panel_box()`/`table_box()` — on a cp1252 console it degrades to ASCII glyphs
  AND ASCII borders (Rich's own `safe_box` only reaches SQUARE, which still uses
  U+2500/U+2502 and would still crash).

## Gotchas worth remembering

- Module-level constants baked into function defaults (`def f(p = DB_PATH)`) are
  frozen at import and can't be redirected. Two bugs of exactly this shape were
  caught by tests here; both now resolve at call time. Watch for it.
- The leaderboard adapts to `console.width >= 120` — wallet + profile URL columns
  only appear on wide terminals, otherwise Rich squeezes every column to nothing.

## Round 2 (post-cross-check)

- **Market selection rewritten.** `extract_event_probability()` now ranks
  strictly by `volume24hr DESC` and skips a leg only when it is settled
  (`closed is True`, `active is False`, or `volume24hr is None`) or pinned at
  exactly 100.0%/0.0%. The old `2 <= prob <= 98` band was discarding heavily
  traded 99%/1% markets — real conviction — in favour of thin coin-flip noise.
- **PnL relabelled to "Est. PnL" everywhere**, with `PNL_BASIS_NOTE` rendered as
  a table caption. The headline mixes 7d realized with lifetime-to-date open
  unrealized, and the old "7D Net PnL" label misrepresented that. Both halves get
  their own columns on a wide console.
- **Market-relative whale rule.** `is_whale_trade()` flags a fill when it clears
  the absolute bar OR reaches `RELATIVE_WHALE_FRACTION` (1%) of the market's 24h
  volume. Being an OR it only ever adds whales. NOTE: raw RTDS frames carry no
  volume field, so the relative branch stays inert until a caller attaches one
  (`MARKET_VOLUME_KEYS`, or the `market_volume_24h=` argument). Wiring a Gamma
  volume cache into the stream is the obvious follow-up.
- **Wallet de-duplication.** Addresses normalise to lowercase on write, and
  `merge_duplicate_wallet_casings()` folds pre-existing duplicates on startup
  (summing `tracked_wallets` counters, keeping the newest `sharp_traders` row).
  This was found live: "Ultimate-Underpass" held two leaderboard slots.

### Width thresholds (they differ, on purpose)

| Surface | Breakdown shown at | Why |
|---|---|---|
| `pnl_scanner` leaderboard | `console.width >= 120` | full-width table |
| `pnl_scanner` profile URL | `console.width >= 150` | +38 cols on top |
| dashboard traders panel | `console.width >= 136` | panel gets only HALF the console |

## Round 3 (post-cross-check 2)

- **`GammaVolumeCache` (whale_collector).** Background thread, 60s refresh,
  `conditionId -> volume24hr`, snapshot-swapped under a lock. **Gamma silently
  caps `/markets` at 100 rows whatever `limit` says**, so it paginates with
  `offset`, ordered `volume24hr DESC`. ~590 markets in ~0.5s.
- **$250 floor on relative whales.** `is_whale_trade` now needs
  `usd >= 250 AND usd >= 1% * volume24h`. Without it, 1% of a dead $50/day
  market made every dust fill a whale.
- **Multi-strike weighting (dashboard).** `contested_score(vol, prob) =
  vol * max(0.1, 1 - |prob-50|/50)`, applied only to events with >2 markets.
  Two-outcome events still rank on raw volume so a genuine 99% headline is not
  dragged toward a thin 50% sibling.
- **Leaderboard ranks on `realized_pnl_7d`**, in both tools, and `is_sharp` now
  keys off realized too. Open unrealized stays visible for context.

### Measured on live traffic (150s, 6,212 frames)

| metric | value |
|---|---|
| absolute whales ($1k+) | 14 |
| relative-only whales (new) | 14 |
| cache hit rate | 9.8% |

The relative rule roughly **doubled** detections. Examples it caught: $985 =
5.0% of a $19.7k/day ceasefire market; $352 = 3.0% of an $11.9k/day market.

**The 9.8% hit rate is not a coverage bug -- do not "fix" it by raising the
limit.** The misses are dominated by ephemeral 5-minute crypto markets
("Bitcoin Up or Down - 10:50PM-10:55PM ET") that mint a fresh conditionId every
5 minutes and report `volume24hr` of ~$250 or `null`. They are structurally
uncacheable, and at that volume the relative rule would fire on nearly every
$250+ scalp. Falling back to the absolute threshold there is the correct
outcome.

### The filter changed too, not just the sort

The task asked only to re-sort by realized. Sorting alone left the flaw half
fixed, because the WHERE clause still filtered on the blended figure: 7 real 7d
winners were being hidden entirely, including one at **+$24,995 realized** that
was excluded because its open book was marked down -$38k. Both the ORDER BY and
the WHERE now use `realized_pnl_7d`.

## Round 4 (final polish)

- **Win rate shows an em dash, not 0%,** when nothing resolved in the 7d window.
  Required a new persisted column: `closed_positions_7d` was computed but never
  stored, so the display could not tell "nothing settled yet" from "settled
  several and lost them all". Defaults to NULL (not 0) so pre-existing rows do
  not claim a dash they never earned.
- **ROI% = 7D Realized / 7D Volume**, shown at `console.width >= 136`, plus
  `--sort [realized|roi|volume]` (default realized). ROI is derived, not stored;
  the sort uses a SQL CASE expression looked up from `SORT_MODES` (never
  interpolated from user input).

### ROI exposed a real data bug -- read this before touching volume_7d

The first live render showed **+2,576,423%** for the top wallet: `volume_7d` was
$5 against $132.7K realized, with `trades_7d` at exactly 500 -- the
`ACTIVITY_MAX_RECORDS` paging cap. The 500 most recent rows were tiny scalps;
the fills that produced the profit were truncated away. So:

- `compute_pnl_metrics(..., activity_truncated=True)` sets `volume_is_partial`
  and returns `roi_7d = None`.
- `format_roi(None)` renders the dash; `--sort roi` puts partial rows last.
- The migration **backfills** `volume_is_partial = 1 WHERE trades_7d >=
  ACTIVITY_MAX_RECORDS`, since rows written earlier default to 0.

**`volume_7d` is a partial sum for any wallet at the cap.** Anything new built
on it (Sharpe, per-market ROI, capital efficiency) inherits that and must check
`volume_is_partial` first.

### Caveat that remains, and is NOT fixed

ROI's numerator and denominator do not share a cohort: realized PnL comes from
positions that CLOSED in the window, while volume counts fills that HAPPENED in
the window. A position opened three weeks ago and closed on Monday contributes
profit but no volume, which is why healthy wallets show 300-900% "ROI". It is
"realized profit per dollar traded this week", not a return on capital. Treat it
as a ranking signal, not an accounting figure.

### Column budgets (measured, not guessed)

Rich charges width + 3 per column (2 padding + 1 border), and silently squeezes
rather than overflowing. Scanner leaderboard: `>=120` wallet + 7d volume +
Est. PnL, `>=136` ROI%, `>=170` profile URL (raised from 150 -- ROI displaced
it). Below 120, Est. PnL is dropped because it is just the sum of the two
columns already on screen. The dashboard traders panel gets only HALF the
console, so at `>=136` ROI% replaces Est. PnL and 7D Volume rather than joining
them.

## Concurrent-edit note (2026-08-29)

RESOLVED: `console_compat.py` was deleted in the cross-check round. The inline
`safe_glyph()` / `panel_box()` / `table_box()` helpers in `terminal_dashboard.py`
are the single implementation. Kept below for context.

`console_compat.py` appeared in this folder mid-session, written by the other
tool, and **nothing imported it**. It solves the same UTF-8 problem as the
`safe_glyph()` / `panel_box()` / `table_box()` helpers now wired into
`terminal_dashboard.py` and covered by tests. Its one better idea -- calling
`SetConsoleOutputCP(65001)` via ctypes to flip the real Windows code page rather
than only Python's streams -- has been adopted into all three modules' headers.

Decide which one wins: either delete `console_compat.py`, or refactor the three
modules to import it and delete the inline helpers. Right now it is dead code.

## Next / open questions

- `sharp_traders` rows written before this session have `realized_pnl_7d = 0` /
  `unrealized_pnl = 0` (migration back-fills defaults, not history). They correct
  themselves on the next scan of that wallet.
- The dashboard's background whale worker still polls REST `/trades` every 3s
  instead of using the RTDS socket the collector already speaks. Sharing one
  WebSocket between them is the obvious next consolidation.
- Win rate is computed only from positions that *resolved* inside the window, so
  wallets holding everything open show 0% — correct but easy to misread.

## Independent verification pass (2026-08-29, Claude Code)

A second session re-ran everything against the live APIs rather than re-reading
the code. All four tasks verified working:

- `python -m pytest tests -q` -> **169 passed** in 8.9s, fully offline.
- `whale_collector.py --replay --replay-delay 0` -> 22 frames parsed, 16 whale
  fills, 6 correctly rejected below threshold, written to `replay_whales.db`.
  No network touched.
- `whale_collector.py --test` -> live RTDS connect, subscribe, keepalive armed
  at 20s, 5 trades consumed, clean exit 0.
- `terminal_dashboard.py --dry-run` -> all three macro tags returned live
  Gamma data (Crypto $901K BTC-80k, Politics $2.3M Fed, Economics $102K rate
  cuts). Re-run under `PYTHONIOENCODING=cp1252`: rendered identically, exit 0 --
  the ctypes code-page flip wins over the env var, so the ASCII path is a
  second line of defence rather than the active one.
- `calculate_wallet_7d_pnl()` against a live wallet -> realized $66,773.58 and
  unrealized -$25,494.12 reported separately, `volume_is_partial=True` with
  `roi_7d=None` withheld. 3 chained API calls took 2.52s, comfortably above the
  0.4s the 200ms floor implies.

Independently confirmed the handoff brief's `tag=crypto` is wrong: Gamma
silently ignores `tag` and returns the unfiltered global feed (`tag=crypto` and
`tag=politics` both return "Fed Decision in September?" as row 1). `tag_slug`
is the parameter that filters. The code already uses `tag_slug`; the brief does
not.

### Flagged, not changed

The whale rule now fires on `usd_notional >= $1,000` **OR** `>= 1% of market
24h volume` (floor $250). That is a deliberate improvement, but it means the
"$1,000+ whale" contract in the original spec no longer holds -- a $300 fill
can raise an alert, and the dashboard panel is still titled "($1k+ USD)".
Either retitle the panel or gate the relative rule behind an opt-in flag.
