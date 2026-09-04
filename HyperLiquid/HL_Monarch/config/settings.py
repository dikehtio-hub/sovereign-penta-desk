"""
HL_Monarch Settings and Watchlist Definitions.
Covers Main Dex crypto assets and HIP3 TradFi DEX assets (Stocks, Commodities, Indices, FX).
"""
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "hyperliquid_data.db"

# API Endpoints (100% Free, Native, Direct to Hyperliquid)
REST_API_URL = "https://api.hyperliquid.xyz/info"
EXCHANGE_API_URL = "https://api.hyperliquid.xyz/exchange"
TESTNET_REST_API_URL = "https://api.hyperliquid-testnet.xyz/info"
TESTNET_EXCHANGE_API_URL = "https://api.hyperliquid-testnet.xyz/exchange"
WS_API_URL = "wss://api.hyperliquid.xyz/ws"

# Rate Limiting.
# Hyperliquid meters the /info endpoint by *request weight*, not request count:
# the per-IP budget is 1200 weight/minute. Most info requests cost weight 20;
# the cheap ones (l2Book, allMids, clearinghouseState, orderStatus) cost weight 2.
# Budgeting by raw request count under-counts heavy calls by 10x, so the limiter
# is weight-aware and we spend against the real ceiling with a safety margin.
MAX_REQUEST_WEIGHT_PER_MINUTE = 1200
RATE_LIMIT_SAFETY_FACTOR = 0.8          # only ever spend 80% of the published budget
DEFAULT_REQUEST_WEIGHT = 20

# Per-endpoint weights (anything not listed falls back to DEFAULT_REQUEST_WEIGHT).
REQUEST_WEIGHTS = {
    "l2Book": 2,
    "allMids": 2,
    "clearinghouseState": 2,
    "orderStatus": 2,
    "openOrders": 2,
    "spotClearinghouseState": 2,
    "exchangeStatus": 2,
    "order": 1,
    "userRole": 60,
}

# Retained for backwards compatibility with callers that still think in req/min.
MAX_REQUESTS_PER_MINUTE = 120
REQUEST_TIMEOUT_SECONDS = 10.0

# Supported DEXes
DEX_MAIN = "main"        # Main Hyperliquid Crypto Perpetuals (230+ coins)
DEX_XYZ = "xyz"          # Primary HIP3 TradFi DEX (117 assets: TSLA, NVDA, GOLD, XYZ100, etc.)
DEX_KM = "km"            # Markets by Kinetiq
DEX_FLX = "flx"          # Felix Exchange
DEX_CASH = "cash"        # Dreamcash
DEX_PARA = "para"        # Paragon

ACTIVE_DEXES = [DEX_MAIN, DEX_XYZ, DEX_KM, DEX_FLX, DEX_CASH, DEX_PARA]

# Asset Watchlists (HIP-3 TradFi Categories)
WATCHLIST_STOCKS = [
    "xyz:TSLA", "xyz:NVDA", "xyz:AAPL", "xyz:META", "xyz:MSFT",
    "xyz:GOOGL", "xyz:AMZN", "xyz:AMD", "xyz:INTC", "xyz:PLTR",
    "xyz:COIN", "xyz:HOOD", "xyz:MSTR", "xyz:ORCL", "xyz:MU",
    "xyz:NFLX", "xyz:RIVN", "xyz:BABA"
]

WATCHLIST_COMMODITIES = [
    "xyz:GOLD", "xyz:SILVER", "xyz:COPPER", "xyz:CL", "xyz:NATGAS", "xyz:URANIUM"
]

WATCHLIST_INDICES = [
    "xyz:XYZ100", "xyz:SP500"
]

WATCHLIST_FX = [
    "xyz:EUR", "xyz:JPY", "xyz:GBP", "xyz:DXY"
]

WATCHLIST_CRYPTO_BENCHMARKS = [
    "BTC", "ETH", "SOL", "HYPE", "SUI", "DOGE"
]

ALL_CORE_WATCHLIST = (
    WATCHLIST_STOCKS +
    WATCHLIST_COMMODITIES +
    WATCHLIST_INDICES +
    WATCHLIST_FX +
    WATCHLIST_CRYPTO_BENCHMARKS
)

# Polling and Refresh Intervals (seconds)
# A full context sweep costs len(ACTIVE_DEXES) * 20 weight (= 120 for 6 DEXes).
# At the old 3s interval that is 2400 weight/min - double the real 1200 ceiling,
# which starved every other REST caller and invited sustained 429s. 8s keeps the
# collector at ~900 weight/min and leaves headroom for wallet/whale scans.
REST_POLL_INTERVAL = 8.0       # Ticker and context polling interval
ORDERBOOK_POLL_INTERVAL = 5.0  # Order book snapshot interval (dashboard live view; not the sampler)

# --- Round 35: TOP-OF-BOOK SPREAD SAMPLING (Ruling 5.C) ------------------------
# orderbook_snapshots was empty and nothing wrote it, so no persisted basis window
# carried a measured execution cost. The sampler writes one l2Book snapshot per
# coin per interval for a BOUNDED set of coins, and only from the collector that
# owns maintenance (two samplers would double the spend).
#
# THE BUDGET IS THE CONSTRAINT. Context polling already costs len(ACTIVE_DEXES)
# x 20 weight every REST_POLL_INTERVAL = 900 weight/min against a 960/min ceiling
# (1200 x 0.8 safety). l2Book costs 2. 24 coins every 120s is 24 weight/min -
# inside the remaining headroom, with room left for wallet and whale scans. Do
# not raise the cap or shorten the interval without redoing that arithmetic.
ORDERBOOK_SAMPLE_INTERVAL = 120.0   # seconds between sampling passes
ORDERBOOK_SAMPLE_MAX_COINS = 24     # held positions > funding candidates > rotated > core watchlist
ORDERBOOK_SAMPLE_CANDIDATES = 5     # top positive-funding spot-backed perps sampled ahead of their entry (Round 37/38)
# Round 38: candidate eligibility is decided by spot_symbol_for() against the
# live spot token universe, never by the coin's dex prefix. The universe changes
# rarely (new listings), so the sampler refreshes its copy on this cadence.
SPOT_UNIVERSE_REFRESH_SECONDS = 6 * 3600.0

# --- Round 38: the stalled-service threshold scales with the poll cadence -------
# A service that is ALIVE BUT NOT WRITING shows STALLED on the dashboard once the
# newest snapshot is older than this. Four missed cycles is a stall, not jitter:
# the effective cycle is REST_POLL_INTERVAL plus ~2s of request overhead (8s
# configured, ~10s observed), and 45s is the floor so a faster poll cannot turn
# ordinary jitter into a red badge. Derived here rather than hard-coded in the
# UI so raising the poll interval does not make every frame a false alarm.
STALLED_FLOOR_SECONDS = 45.0


def stalled_after_seconds(poll_interval: float = REST_POLL_INTERVAL,
                          floor: float = STALLED_FLOOR_SECONDS) -> float:
    return max(float(floor), (float(poll_interval) + 2.0) * 4.0)


STALLED_AFTER_SECONDS = stalled_after_seconds()
DB_FLUSH_INTERVAL = 2.0        # Database batch insert flush interval

# Database maintenance / retention.
# asset_snapshots and liquidation_clusters are written every poll for every asset,
# so without retention the DB grows without bound (~12M rows/day at 436 assets).
DB_MAINTENANCE_INTERVAL = 300.0     # seconds between prune + WAL checkpoint passes

# --- Round 33: RETENTION MUST OUTLAST THE HOLDING PERIOD IT EVALUATES --------
# These were 72 / 24 / 168, and the 72 was the binding defect of the whole
# analytics stack. BASIS_MIN_HOLD_DAYS is 7 (168h) and the price series needed to
# score a 7-day hold was deleted after 3. The strategy's holding period was 2.3x
# the data retained to evaluate it, so `net_apr_after_spread` - which amortises
# execution cost over 7 days, and is what turns a 3bp spread into ~6% annualised
# instead of ~44% - rested on a window no data in the repo could test.
#
# The same 72 blocked the fade re-benchmark: passive_fade_rebenchmark.meta.json
# requires a 7-day window and excursions are measured against asset_snapshots, so
# events older than 3 days had no price series to measure against. The reopening
# gate was unreachable by construction, not merely not-yet-reached.
#
# RAISING THIS DOES NOT CREATE HISTORY. Pruned rows are gone; the change only
# stops future deletion. Snapshots currently span 69.1h, so a 168h window first
# becomes available ~4.1 days from the moment this ships - not today.
#
# AND IT IS NOT SUFFICIENT FOR THE 30-DAY STANDARD. 720 hours of observation
# cannot be held in a 192-hour window at any disk size; that needs measurements
# persisted incrementally as raw rows age out. Round 34 built it:
# `storage/incremental_persistence.py`, run by the repository BEFORE every prune.
#
# A RUNNING COLLECTOR DOES NOT SEE THIS FILE CHANGE. Settings are read at import.
# The collector launched 2026-09-03 14:45 kept pruning at 72h until it was
# restarted on 2026-09-04 after this was found (oldest snapshot was exactly 72.0h
# old, 15 hours after the constant below said 192). Restart the collector after
# any change here, or the change is a comment.
#
# Cost: snapshots are ~12M rows/day and dominate the file. 69h -> 192h is ~2.8x
# on a 3.9 GB database, so roughly +7 GB against 60 GB free.
SNAPSHOT_RETENTION_HOURS = 192      # 8 days: one clear day beyond a 7-day hold
CLUSTER_RETENTION_HOURS = 24        # liquidation_clusters history kept
TRADE_RETENTION_HOURS = 192         # trades + liquidation_events, matched to above
WAL_AUTOCHECKPOINT_PAGES = 2000     # ~8MB WAL before an automatic checkpoint

# --- Round 34: INCREMENTAL MEASUREMENT PERSISTENCE (option b) -----------------
# The pruner reduces raw rows to measurements BEFORE deleting them, so the
# walk-forward's history is unbounded while the raw tables stay at 192h.
# See storage/incremental_persistence.py for the rules.
MEASUREMENT_HOLD_HOURS = (24.0, 168.0)      # holds materialised: the validated 24h, and the 7-day the money is committed for
MEASUREMENT_ENTRY_STRIDE_HOURS = 3.0        # candidate entries every 3h on an epoch-aligned grid (Round 32 script used 3h)
MEASUREMENT_MAX_GAP_HOURS = 2.0             # longer intervals count as unobserved, never extrapolated across
MEASUREMENT_MIN_COVERAGE = 0.60             # below this a window's realised APR is NULL, not a number
# One instant per hold per pass: a 7-day scan is ~0.25s per coin, so one instant
# is ~2 min across 440 coins. Steady state needs one per 3h; one per 5 min catches
# up 36x faster than data arrives without keeping the maintenance thread busy.
MEASUREMENT_MAX_GRID_POINTS_PER_PASS = 1
MEASUREMENT_MAX_EVENTS_PER_PASS = 2000      # collector pass budget for cascade events
EXCURSION_PERSIST_HORIZONS_MINUTES = (5.0, 15.0, 30.0, 60.0)
EXCURSION_PERSIST_SOURCES = ("trade_sweep", "trade_flow")
# trade_flow is ANY fill >= $50k and ran 107k events per 72h - mostly plain whale
# orders. Persisting all of it would be ~13M rows/year for a source the fade
# does not trade. The floor keeps the tail that the whale sweeper cares about.
EXCURSION_PERSIST_MIN_NOTIONAL = {"trade_sweep": 0.0, "trade_flow": 250_000.0}
EXCURSION_CONTROL_MULTIPLE = 1              # matched random entries persisted per event
# Regime tag read off the reference coin over the trailing window. Thresholds are
# ENGINEERING ESTIMATES; the underlying numbers are stored on every row so they
# can be re-bucketed later without raw data.
REGIME_REFERENCE_COIN = "BTC"
REGIME_LOOKBACK_HOURS = 24.0
REGIME_MIN_HOURLY_BUCKETS = 12
REGIME_VOL_BUCKETS = (1.5, 3.5)             # daily realised vol %: LOW < 1.5 <= MID < 3.5 <= HIGH
REGIME_FUNDING_BUCKETS = (0.0, 20.0)        # APR %: NEG < 0 <= FLAT < 20 <= HOT (neutral BTC funding is ~10.95%)
# Ruling D: 30 days across >= 2 regimes before an edge is called enduring.
RULING_D_REQUIRED_HOURS = 720.0
RULING_D_MIN_REGIMES = 2
RULING_D_MIN_HOURS_PER_REGIME = 48.0        # a regime seen for less than two days is a blip, not a regime

# UI refresh caching: how long the dashboard reuses an expensive REST-backed scan
# before re-issuing it. Without this, holding the Whale tab issued ~15 REST calls
# per rendered frame.
DASHBOARD_SCAN_TTL_SECONDS = 30.0

# Funding Arbitrage Tradeability Gates.
# The most extreme funding APRs sit on illiquid or near-dead markets where the
# spread eats the yield and size cannot be filled, so headline APR is filtered
# against real liquidity before an opportunity is called tradeable.
ARB_MIN_NOTIONAL_OI = 250_000.0    # USD open interest floor
ARB_MIN_DAY_VOLUME = 100_000.0     # USD 24h turnover floor - OI without volume cannot be exited
ARB_MAX_SPREAD_BPS = 25.0          # reject wider than 25bps top-of-book
ARB_SPREAD_CHECK_LIMIT = 8         # max live l2Book checks per direction (weight 2 each)
# Round 39: a spot TOKEN is not a spot MARKET. Measured 2026-09-04: TSLA and AVGO
# spot pairs turned over $0 in 24h, CRCL under $2k, and COIN/NVDA have a token
# entry but no pair at all - while their HIP-3 perps trade tens of millions. A
# basis trade hedged on such a leg has no hedge. Only tokens whose best spot pair
# clears this 24h notional floor count as spot-backed anywhere in the system
# Round 40 (Ruling 40-3) raised the floor from $10k to $50k: a $10k leg into a
# $10k/day pair is the whole day's turnover. 32 of 499 tokens clear $50k on
# 2026-09-04 (46 at $10k, 25 at $100k) - the liquid wrappers stay, the shells go.
SPOT_MIN_DAY_VOLUME = 50_000.0     # USD 24h notional floor for the SPOT leg's pair (>= 5x a $10k leg)
# Round 41 (Ruling 41-3): the floor scales with the leg. effective_spot_min_volume()
# in analytics/funding_arbitrage.py returns max(SPOT_MIN_DAY_VOLUME, notional x this),
# so a $25k leg needs a $125k/day pair. The constant above is the floor of the floor.
SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE = 5.0
# Round 41 (Ruling 41-1): tokenised equities (NVDAX, TSLAX, EQNVDA...) are liquid spot
# tokens that price a stock which trades five days a week. A basis hedge on one
# carries the weekend gap and the market-hours liquidity cliff the perp does not.
# Quarantined: spot_symbol_for ignores SYNTHETIC_EQUITY_ALIASES while this is False.
ALLOW_SYNTHETIC_EQUITY_BASIS = False
# Round 41 (Ruling 41-4): liquid spot tokens that can never be a basis leg because
# they are the quote/settlement asset, not something a perp prices. Excluded from
# the unmapped-spot telemetry so it reports missing aliases, not stablecoins.
SPOT_NON_BASIS_TOKENS = ("USDC", "USDT0", "USDE", "USDH", "USDHL", "FEUSD", "USR")

# Funding harvest modelling.
# Hyperliquid settles perp funding hourly (verified against the API: the `funding`
# field on metaAndAssetCtxs is a 1-hour rate, so APR = rate * 24 * 365 * 100).
ARB_FUNDING_INTERVAL_HOURS = 1.0
# Horizon used to amortise the one-off entry/exit spread cost. A week is a
# realistic funding-harvest hold; a 1-day assumption over-penalises every row.
ARB_DEFAULT_HOLDING_DAYS = 7.0

# Squeeze & Funding Exhaustion Engine.
# Aimed at the ~86% of perps with no spot leg, where funding yield is a directional
# bet rather than a hedgeable basis trade.
SQUEEZE_LOOKBACK_HOURS = 24.0     # window for funding percentile / OI expansion
SQUEEZE_MIN_SAMPLES = 20          # below this the percentile is meaningless
# $100k, not $250k: high-volatility exotics in the $100k-$200k OI band are exactly
# the thin books where a forced exit moves price hardest, and were being excluded
# from rotation before they could ever be observed.
SQUEEZE_MIN_NOTIONAL_OI = 100_000.0   # ignore markets too small to squeeze
SQUEEZE_WATCH_THRESHOLD = 60.0    # score at or above which an asset earns a WATCH label
# Dynamic WS subscription rotation. WebSocket subscriptions cost no REST budget,
# so the trade feed can follow whatever is currently squeezing. This is what makes
# liquidation_events fill for exotics - previously it only ever covered the core
# watchlist, which is why the precedence validator had nothing to measure.
# 180s, not 60s: the squeeze score is computed from a 24h window and cannot move
# meaningfully in a minute, so a faster loop only produced sub/unsub churn.
SQUEEZE_ROTATION_INTERVAL = 180.0     # retained: squeeze engine is informational only
SQUEEZE_ROTATION_MAX_COINS = 35
# A coin stays subscribed at least this long after being added, even once its
# score drops. A squeeze stops looking crowded exactly when it begins unwinding,
# which is when its liquidations print - dropping the feed then would discard the
# data the precedence validator is measuring.
SQUEEZE_ROTATION_COOLDOWN_SECONDS = 1200.0   # 20 minutes
# Active-unwind trigger. The crowd must first have been committed, then the rate
# must break decisively out of its own range - drifting to the median is not an unwind.
SQUEEZE_EXHAUSTION_PERSISTENCE = 0.75
SQUEEZE_EXHAUSTION_LOW_PCT = 35.0     # positive regime collapsing below this = longs exiting
SQUEEZE_EXHAUSTION_HIGH_PCT = 65.0    # negative regime rising above this = shorts covering

# Cross-Market Titan pipeline.
# Measured over a 120-address sample of hyperliquidusers.txt: 31.7% of Hyperliquid
# addresses have a Polymarket profile, but only 6.7% have ANY volume and 3.3% have
# more than $1k. A profile is created on wallet connection, so existence alone is
# not a signal - both directions gate on demonstrated activity.
TITAN_MIN_PM_VOLUME = 1_000.0        # Polymarket weighted volume to count as active
TITAN_MIN_HL_ACCOUNT_VALUE = 1_000.0 # Hyperliquid account equity to count as active
TITAN_MIN_HL_VOLUME = 5_000.0        # ...OR this much Hyperliquid throughput
# Reference sizes that normalise the logarithmic conviction terms onto 0-100.
# Roughly the largest values seen in each corpus, so a top-decile actor lands near
# the weight ceiling rather than saturating it.
TITAN_HL_REFERENCE_VALUE = 10_000_000.0
TITAN_PM_REFERENCE_VOLUME = 1_000_000.0
TITAN_SCAN_LIMIT = 50                # addresses probed per direction per pass
TITAN_REVERIFY_HOURS = 24.0          # re-confirm a titan at most once a day

# Squeeze precedence validation.
# A hit rate from a handful of windows is noise, not a finding; below this count the
# validator reports UNDERPOWERED rather than a number.
VALIDATOR_MIN_OBSERVATIONS = 30
# Pre-registered acceptance bar, agreed 2026-08-31 BEFORE any validation data
# existed. Written down so the verdict is applied by rule rather than judged once
# the number is visible.
VALIDATOR_ALPHA = 0.05          # PASS also requires p < this
VALIDATOR_PASS_LIFT = 1.75      # >= this AND significant -> deploy
VALIDATOR_RETUNE_LIFT = 1.25    # >= this -> retune weights; below -> retire classifier

# Liquidation sweep detection thresholds.
# Two tiers: a single notional floor cannot serve both BTC (median fill in the
# thousands) and the exotics the squeeze engine targets (median fill $69, p90
# $495). The exotic tier trades size for slippage - thin books mean a forced exit
# moves price hard without needing size.
EXOTIC_SWEEP_MIN_NOTIONAL = 1_000.0     # small fill...
EXOTIC_SWEEP_MIN_SLIPPAGE_PCT = 1.0     # ...but must print far from mark
MAJOR_SWEEP_MIN_NOTIONAL = 25_000.0     # large fill...
MAJOR_SWEEP_MIN_SLIPPAGE_PCT = 0.4      # ...needs less slippage to qualify
WHALE_ORDER_MIN_NOTIONAL = 50_000.0     # size alone, regardless of slippage

# Liquidation-fade paper strategy sizing.
# The old flat $50k trigger meant the strategy could only ever fire on BTC/ETH,
# so every exotic liquidation the squeeze rotation now records was ignored.
FADE_MIN_NOTIONAL_MAJOR = 50_000.0    # trigger on a deep-book market
FADE_MIN_NOTIONAL_EXOTIC = 1_000.0    # trigger on a thin-book market
FADE_EXOTIC_OI_CEILING = 5_000_000.0  # notional OI below which a market counts as exotic
FADE_LIMIT_OFFSET_PCT = 0.5           # rest the fade this far deeper into the cascade
# A fade is a bet on THIS cascade reverting. Without a TTL a resting order from
# hours ago eventually fills on unrelated price action and books a trade the
# strategy never intended, quietly flattering the paper PnL.
FADE_ORDER_TTL_SECONDS = 180.0        # cancel unfilled fade limits after 3 minutes
# Re-geometried 2026-08-31. The previous 0.5% offset with a 1.5% stop was ~1:3
# reward:risk, needing a >75% win rate merely to break even. Both legs are now
# 0.65% from the limit: 1:1, which breaks even at 50%.
FADE_STOP_LOSS_PCT = 0.65             # stop this far beyond the limit price
FADE_TAKE_PROFIT_PCT = 0.65           # snapback target, same distance -> 1:1
# A fade is a bet on a fast snapback. A position still open after ten minutes has
# had its thesis disproved by time, whatever the price is doing.
FADE_POSITION_MAX_HOLD_SECONDS = 1800.0

# Hyperliquid fee schedule. A resting limit earns the maker rate; anything that
# crosses the book to get out pays taker. This matters at these targets: a 0.65%
# move against a maker-in / taker-out round trip loses 4.5bps to fees, which is
# ~7% of the gross edge. Reading PnL without it would be optimistic by an unknown
# amount, which is exactly the kind of number that survives longer than it should.
MAKER_FEE_PCT = 0.00010   # 1.0 bps - resting limit (entry, take-profit)
TAKER_FEE_PCT = 0.00035   # 3.5 bps - crossing out (stop-loss, time-stop)

# Pre-registered 50-trade hurdle, agreed 2026-08-31 BEFORE any closed trades
# existed. Net of fees. Recorded here so the verdict is applied by rule, exactly
# as the retired squeeze classifier's bar was.
#   PASS   : win rate >= 54.0% AND profit factor >= 1.25
#   RETUNE : 48.0% <= win rate < 54.0%
#   FAIL   : win rate < 48.0%
HURDLE_MIN_TRADES = 50
HURDLE_PASS_WIN_RATE = 54.0
HURDLE_PASS_PROFIT_FACTOR = 1.25
HURDLE_RETUNE_WIN_RATE = 48.0

# --- Round 15: trend / ATR confluence filter --------------------------------
# The unfiltered baseline lost GROSS (-$482.77 over 12 closes, 25% win rate):
# blind fading on liquid majors was catching trend waterfalls, not dislocations.
# The filter refuses fades that lean against a strong prevailing trend unless the
# market is already stretched to an extreme.
#
# ALL THRESHOLDS BELOW ARE PERCENTS, not fractions. atr_pct is a percent too
# (1.93 == 1.93%). Mixing the two is how an offset ends up 100x wrong.
# --- RETIRED 2026-09-01: the reactive liquidation fade -----------------------
# The MFE/MAE excursion benchmark measured the entry signal at 0.513 against a
# random-entry control of 1.092 (n=466, 98% coverage, 30m horizon). Paired
# MFE-MAE per event: t=-10.52, MAE exceeded MFE in 72.7% of events, and 0 of
# 20,000 bootstrap resamples produced a non-negative mean.
#
# Forced liquidations are MOMENTUM drivers, not mean-reverting wicks: price moves
# ~2x further against the fade than for it. No filter or geometry fixes a sign
# error, which is why rounds 9-15 of execution refinement never moved the result.
#
# The module and its tests are KEPT, not deleted - they are the record of what
# was measured and why, and the paper engine, fee model and exit engine they
# exercise are shared with the basis harvester. This flag is what stops it
# trading. Do not re-enable without a new pre-registered excursion result.
FADE_STRATEGY_ENABLED = False

REGIME_ENABLED = True
REGIME_BUCKET_MINUTES = 15.0      # "15m ATR" - also the EMA/RSI bar
REGIME_LOOKBACK_MINUTES = 1440.0  # 24h: enough bars for EMA-50 at 15m
REGIME_EMA_PERIOD = 50
REGIME_RSI_PERIOD = 14
REGIME_ATR_PERIOD = 14
REGIME_RSI_OVERSOLD = 32.0        # buy a downtrend only when this stretched
REGIME_RSI_OVERBOUGHT = 68.0      # sell an uptrend only when this stretched
# With indicators unavailable (thin/gappy series) the filter BLOCKS rather than
# permits: "unknown regime" is not the same as "regime is fine", and defaulting
# to permit would quietly restore the unfiltered baseline we just rejected.
REGIME_BLOCK_WHEN_UNKNOWN = True

# Dynamic, volatility-scaled geometry. Offset floors at 0.40% so a quiet major
# does not rest inside the noise; TP/SL floor because a pure 1.0x ATR target on
# BTC is ~0.15%, against which the 4.5bp round-trip fee is ~31% of gross - the
# strategy would be paying a third of its edge to the exchange.
FADE_ATR_OFFSET_MULT = 0.50
FADE_ATR_OFFSET_FLOOR_PCT = 0.30
FADE_ATR_TARGET_MULT = 0.50       # halved: a 1.0x target needed 1,224s median
FADE_ATR_STOP_MULT = 0.50         # equal to target -> still 1:1
FADE_ATR_TARGET_FLOOR_PCT = 0.30  # keeps fees <= ~15% of the gross target
FADE_USE_DYNAMIC_GEOMETRY = True

# --- Round 15: dual rotation pool -------------------------------------------
# Volume-only ranking selected exclusively >$5M OI books, so the exotic tier
# built in rounds 9-12 never fired once - every fill was the $10k major tier.
# Slots are now split so both regimes are actually observed.
ROTATION_MAJOR_SLOTS = 20
ROTATION_EXOTIC_SLOTS = 15
ROTATION_EXOTIC_MAX_OI = 5_000_000.0
ROTATION_EXOTIC_MIN_VOLUME = 100_000.0
# The paper account is written by the collector and read by `main.py paper` - two
# processes - so it has to live somewhere both can see.
PAPER_STATE_PATH = DATA_DIR / "paper_trading_state.json"
PAPER_SAVE_INTERVAL = 10.0            # seconds between paper-state flushes
# Single-instance guard for the collector itself. Distinct from the service
# supervisor's lockfile: `python main.py collector` bypassed that one entirely,
# so two collectors could write the paper account concurrently.
COLLECTOR_LOCK_PATH = DATA_DIR / "collector.pid"

# WebSocket rotation for REACTIVE execution.
# Ranked by 24h volume, not squeeze score: the predictive classifier was retired
# 2026-08-31 (lift 0.351 vs a 1.25x floor - anti-predictive), so gating the feed on
# it was choosing the markets least likely to liquidate. Liquidations happen where
# there is flow.
ROTATION_INTERVAL = 180.0             # seconds between rotations
ROTATION_MAX_COINS = 35               # cap on dynamically subscribed markets
ROTATION_COOLDOWN_SECONDS = 1200.0    # hysteresis: hold a coin 20min before dropping
ROTATION_MIN_DAY_VOLUME = 100_000.0   # ignore markets with no meaningful turnover

# Liquidation Cluster Settings
DEFAULT_LEVERAGE_TIERS = [5, 10, 20, 25, 30, 50]

# Whale discovery floors. A $25k fill is a whale on BTC and an impossibility on a
# thin exotic - the flat floor meant exotic counterparties were never discovered.
WHALE_DISCOVERY_MIN_NOTIONAL_CORE = 25_000.0
WHALE_DISCOVERY_MIN_NOTIONAL_EXOTIC = 7_500.0

# Alerting tiers. The exotic tier trades size for slippage, matching how
# liquidation detection distinguishes a thin-book sweep from ordinary flow.
ALERT_EXOTIC_MIN_NOTIONAL = 2_500.0
ALERT_EXOTIC_MIN_SLIPPAGE_PCT = 1.5
# One cascade prints many qualifying fills within seconds. Without a cooldown a
# single event becomes a dozen near-identical webhooks, which trains readers to
# ignore the channel - the opposite of what an alert is for.
ALERT_COOLDOWN_SECONDS = 60.0

# Known Hyperliquid System Backstop Liquidators & Market Maker Addresses
HL_SYSTEM_LIQUIDATOR_ADDRESSES = {
    '0xdfc24b077bc1425ad1dea75bcb6f8158e10df303',
    '0x31ca8395cf837de08b24da3f660e77761dfb974b',
    '0xb0a55f13d22f66e6d495ac98113841b2326e9540',
    '0x010461c14e146ac35fe42271bdc1134ee31c703a',
    '0x2ed5c4484ea3ff8d57d5f2fb152a40d9f2b68308',
    '0x5e177e5e39c0f4e421f5865a6d8beed8d921cb70'
}

MAINTENANCE_MARGIN_FRACTIONS = {
    5: 0.10,
    10: 0.05,
    20: 0.025,
    25: 0.02,
    30: 0.0166,
    50: 0.01
}

# --- Round 15: delta-neutral basis trade ------------------------------------
# Long spot + short perp, harvesting positive funding with no net delta.
# Only the SHORT_HARVEST direction is constructible: the mirror trade (long perp
# + short spot) needs to borrow spot, and Hyperliquid spot has no borrow. A
# negative-funding row is therefore a directional idea, never a basis trade.
BASIS_MIN_FUNDING_APR = 25.0   # gross bar, per the Round 15 directive
BASIS_MIN_NET_APR = 20.0       # after spread on BOTH legs, amortised over the hold
BASIS_HOLDING_DAYS = 7.0       # matches the funding backtester's realised-APR window
BASIS_NOTIONAL_USD = 10_000.0  # per leg; the position is 1:1 by construction

# Paper harvester: the delta-neutral engine that replaced the retired fade.
BASIS_PAPER_STARTING_CASH = 100_000.0
BASIS_PAPER_STATE_PATH = str(DATA_DIR / "basis_paper_state.json")
BASIS_MAX_CONCURRENT = 2            # tactical: the realistic opportunity set is 1-2 names
BASIS_ACCRUAL_INTERVAL = 3600.0     # funding is quoted hourly, so accrue hourly
BASIS_MIN_HOLD_DAYS = 7.0           # do not open what we would not hold a week

# --- Dynamic yield exit -----------------------------------------------------
# MEASURED, not assumed. Realised yield after entering on a >=25% APR reading,
# net of the 0.0900% round-trip fee on both legs:
#     6h hold  -> -0.0612% net, only 16% of entries profitable
#    12h hold  -> +0.0070% net, 56% profitable
#    24h hold  -> +0.0465% net, 69% profitable
#    48h hold  -> +0.1185% net, 78% profitable
# Short holds LOSE money. The fee dominates: at a sustained 12% APR the daily
# yield is 0.0329%, so a round trip takes 2.74 DAYS just to pay for itself.
#
# A 12% exit floor was proposed. It was rejected on this data: 63.6% of >=25%
# readings fall under 12% within 24h, so a 12% floor churns almost every position
# inside a day and pays 0.09% for the privilege - three days of yield at the very
# rate it is exiting for being "too low". Churn only helps if there is somewhere
# better to redeploy, and the qualifying set is 1-2 names.
#
# So we exit when the position turns against us, not when it merely gets boring.
BASIS_EXIT_APR_FLOOR = 0.0          # exit when funding goes NEGATIVE (we start paying)

# --- Round 31 Target D: exit HYSTERESIS ---------------------------------------
# A position does not close on a dip below the 20% entry bar. Entry and exit are
# deliberately different thresholds, because a single bar makes the strategy
# thrash: a rate oscillating around 20% would open and close the same position
# repeatedly, paying the full round trip each time to re-acquire what it just sold.
#
# So there are exactly two exits: funding REVERSES (below), or the position has
# gone stale - held long enough to have paid for itself, at a rate no longer worth
# the capital. Without the stale leg a position at 2% APR is held forever, which
# is not a loss but is an unbounded opportunity cost the engine never notices.
BASIS_EXIT_STALE_DAYS = 7.0         # only after the hold has earned its round trip
BASIS_EXIT_STALE_APR = 10.0         # below this, the capital is better used elsewhere

# --- Round 31 Target E: leverage policy, locked --------------------------------
# 1.0x everywhere. The perp leg's liquidation cushion is (1/L - maintenance
# margin), so 1x dies on a ~98.8% move and 2x on ~48.8%. The exception list is
# limited to the three deepest books, where a 48.8% adverse move without an
# intervening chance to add margin is a genuinely remote event. It is NOT a
# view that leverage is free: it buys capital efficiency by moving the
# liquidation price closer, and a liquidated perp leg leaves the position
# DIRECTIONAL at the worst possible moment.
BASIS_DEFAULT_PERP_LEVERAGE = 1.0
BASIS_MAX_PERP_LEVERAGE = 1.0
BASIS_LEVERAGE_EXCEPTIONS = {"BTC": 2.0, "ETH": 2.0, "SOL": 2.0}
# A switch must pay for its own round trip, with margin, before it is worth doing.
BASIS_SWITCH_MIN_GAIN_APR = 25.0
