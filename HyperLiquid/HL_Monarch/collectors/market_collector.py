"""
Continuous Real-Time Data Ingestion Collector for HL_Monarch.
Coordinates REST market state polling and WebSocket real-time trade/liquidation streams.
Persists all data to SQLite WAL database.
"""
import asyncio
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional, Sequence, Set, Tuple
from config.settings import (
    ACTIVE_DEXES, REST_POLL_INTERVAL, ALL_CORE_WATCHLIST, COLLECTOR_LOCK_PATH,
    ORDERBOOK_SAMPLE_INTERVAL, ORDERBOOK_SAMPLE_MAX_COINS, ORDERBOOK_SAMPLE_CANDIDATES,
    SPOT_UNIVERSE_REFRESH_SECONDS, ARB_MAX_SPREAD_BPS,
    DB_FLUSH_INTERVAL, DB_MAINTENANCE_INTERVAL,
    ROTATION_INTERVAL, ROTATION_MAX_COINS,
    ROTATION_COOLDOWN_SECONDS, ROTATION_MIN_DAY_VOLUME,
    ROTATION_MAJOR_SLOTS, ROTATION_EXOTIC_SLOTS,
    ROTATION_EXOTIC_MAX_OI, ROTATION_EXOTIC_MIN_VOLUME,
    FADE_STRATEGY_ENABLED,
    BASIS_ACCRUAL_INTERVAL, BASIS_MIN_NET_APR, BASIS_MIN_FUNDING_APR,
    BASIS_NOTIONAL_USD, BASIS_MAX_CONCURRENT,
    REGIME_ENABLED, REGIME_BUCKET_MINUTES, REGIME_LOOKBACK_MINUTES,
    REGIME_EMA_PERIOD, REGIME_RSI_PERIOD, REGIME_ATR_PERIOD,
    PAPER_SAVE_INTERVAL,
)
from api.rest_client import HyperliquidRestClient
from api.ws_client import HyperliquidWsClient
from storage.repository import MarketRepository
from analytics.liquidation_engine import LiquidationEngine
from analytics.whale_tracker import WhaleTracker
from analytics.alerter import WebhookAlerter
from collectors.orderbook_sampler import (sample_orderbooks, select_sample_coins,
                                          top_funding_candidates)
from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("HL_Collector")

# Hard ceiling on the in-memory write buffer. A burst that outruns the flush task
# is dropped oldest-first rather than growing until the process runs out of memory.
MAX_BUFFERED_TRADES = 20_000
MAX_BUFFERED_LIQ_EVENTS = 5_000


def _probe_process(pid: int) -> Optional[Tuple[bool, Optional[str]]]:
    """
    (exists, command line) for `pid` via psutil; None when psutil is unavailable.
    A process that exists but cannot be inspected reports a None command line.
    """
    try:
        import psutil
    except ImportError:
        return None
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False, None
    except psutil.AccessDenied:
        return True, None
    try:
        return True, " ".join(proc.cmdline())
    except (psutil.AccessDenied, psutil.ZombieProcess):
        return True, None
    except psutil.NoSuchProcess:
        return False, None


def read_service_pid(lock_path: Optional[Path] = None) -> Optional[int]:
    """The PID in `data/collector.pid`, or None when absent or unreadable."""
    path = Path(lock_path) if lock_path is not None else COLLECTOR_LOCK_PATH
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def service_collector_alive(lock_path: Optional[Path] = None,
                            probe: Optional[Callable[[int], Optional[Tuple[bool, Optional[str]]]]] = None
                            ) -> bool:
    """
    True when `data/collector.pid` names a LIVE COLLECTOR process other than this one.

    Used by the dashboard's embedded collector to decide whether to run the
    maintenance loop. Two pruners with two ideas of the retention window is
    exactly what happened in Round 34: the dashboard, launched fifteen hours
    before the retention constant changed, kept deleting at 72h every five
    minutes while the restarted service collector held 192h.

    ROUND 35 - PID REUSE. After a reboot the number in a stale lock file can
    belong to anything, so a live PID counts only if its command line says
    "collector". A process that exists but cannot be inspected is honoured as
    the service rather than risk a second pruner; an absent psutil is treated
    the same way.
    """
    pid = read_service_pid(lock_path)
    if pid is None or pid == os.getpid():
        return False
    result = (probe or _probe_process)(pid)
    if result is None:
        return True
    exists, cmdline = result
    if not exists:
        return False
    if cmdline is None:
        return True
    return "collector" in cmdline.lower()


class MarketCollector:
    def __init__(self, maintenance: bool = True, yield_to_service: bool = False):
        # Whether THIS collector may prune, measure and sample order books at all.
        self.maintenance = bool(maintenance)
        # Round 35: re-checked EVERY cycle rather than once at start-up, so an
        # embedded collector (the dashboard's) hands maintenance over the moment a
        # service collector appears, and takes it back if the service dies.
        self.yield_to_service = bool(yield_to_service)
        self._yield_logged = False
        self.rest_client = HyperliquidRestClient()
        self.ws_client = HyperliquidWsClient()
        self.repo = MarketRepository()
        self.liq_engine = LiquidationEngine()
        self.whale_tracker = WhaleTracker()
        self.alerter = WebhookAlerter()
        # Round 38: the live spot token universe, for deciding which funding
        # candidates the sampler may treat as spot-backed. Fetched lazily on the
        # sampling thread and refreshed on SPOT_UNIVERSE_REFRESH_SECONDS.
        self._spot_universe: Optional[Set[str]] = None
        self._spot_volumes_map: Optional[Dict[str, float]] = None
        self._spot_universe_at: float = 0.0
        self._spot_universe_warned = False
        self._arb_engine = None
        self.running = False
        self._current_marks: Dict[str, float] = {}

        # WS handlers run on the event loop thread. Buffer writes there and flush
        # them from a worker thread so a busy trade feed never blocks recv().
        self._trade_buffer: List[Dict[str, Any]] = []
        self._liq_buffer: List[Dict[str, Any]] = []
        self._dropped_rows = 0
        self._db_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hl-db")
        # Round 34: maintenance gets its OWN thread. It now measures completed
        # basis windows and cascade excursions before pruning (~2 min per pass
        # across 440 coins), and the hl-db thread is also the snapshot poller and
        # the trade-buffer flusher. Queued behind a two-minute pass, the poller
        # would create the very gaps the measurements are made from and the
        # buffers (20k trades) would overflow. SQLite connections are per thread.
        self._maint_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hl-maint")
        # Round 35: order book sampling is REST-bound and must not sit behind a
        # measurement pass or in front of a buffer flush.
        self._io_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hl-l2")

        # Coins subscribed dynamically by volume rotation, tracked separately so
        # the core watchlist is never rotated out from under the dashboard.
        self._rotated_coins: Set[str] = set()
        # When each rotated coin was subscribed, for the hysteresis cooldown.
        self._rotation_sub_time: Dict[str, float] = {}
        # Notional OI per coin, so the fade strategy can tell an exotic cascade
        # from a major one without a second query.
        self._notional_oi: Dict[str, float] = {}
        self._last_rotation_split = (0, 0)
        # Regime snapshots keyed by coin, refreshed on the rotation cadence.
        # Computing them per sweep would put a multi-hundred-row DB read on the
        # WebSocket path during exactly the bursts where latency matters.
        self._regimes: Dict[str, Dict[str, Any]] = {}

        # Reactive paper execution. The account persists to disk so `main.py paper`
        # - a separate process - can read what the strategy actually did.
        self.paper_trader = PaperTrader.load()
        self.fade_strategy = LiquidationFadeStrategy(self.paper_trader)
        self._paper_dirty = False

    def _setup_ws_handlers(self):
        """Configure WebSocket callbacks for trades and liquidations."""
        def handle_trades(trades_data: Any):
            if not trades_data:
                return
            trades_list = trades_data if isinstance(trades_data, list) else [trades_data]

            for t in trades_list:
                coin = t.get("coin", "")
                px = float(t.get("px") or 0.0)
                sz = float(t.get("sz") or 0.0)
                side = t.get("side", "")
                ntl = px * sz
                trade_time = t.get("time", int(time.time() * 1000))

                mark = self._current_marks.get(coin, px)
                liq_info = self.liq_engine.detect_liquidation_trade(t, mark)

                # Auto-discover new whales from trade fills
                new_whales = self.whale_tracker.on_trade_fill(t)
                if new_whales:
                    logger.info(
                        f"🐋 Discovered {len(new_whales)} new whale wallet(s): "
                        f"{', '.join(w[:8] for w in new_whales)} from {coin} fill (${ntl:,.2f})"
                    )

                is_liq = bool(liq_info)
                self._buffer_trade({
                    "tid": t.get("tid"),
                    "coin": coin,
                    "side": side,
                    "px": px,
                    "sz": sz,
                    "notional": ntl,
                    "time": trade_time,
                    "hash": t.get("hash"),
                    "is_liquidation": is_liq
                })

                if liq_info:
                    self._buffer_liq_event(liq_info)
                    # React immediately, off the live fill, using the mark that was
                    # in force BEFORE this sweep printed - that is both the
                    # reversion target and the reference the fade rests beneath.
                    try:
                        if mark and mark > 0:
                            # Retired 2026-09-01 - see FADE_STRATEGY_ENABLED. The
                            # sweep is still detected and stored (it is the input
                            # to the excursion benchmark); only the trade is gone.
                            placed = None
                            if FADE_STRATEGY_ENABLED:
                                placed = self.fade_strategy.on_liquidation_sweep(
                                    liq_info, mark,
                                    notional_oi=self._notional_oi.get(coin),
                                    regime=self._regimes.get(coin),
                                )
                            if placed:
                                self._paper_dirty = True
                                logger.info(
                                    f"💼 FADE {placed['side']} {coin} "
                                    f"limit ${placed['limit_price']:,.4f} "
                                    f"TP ${placed['take_profit']:,.4f} "
                                    f"SL ${placed['stop_loss']:,.4f}"
                                )
                    except Exception as e:
                        logger.error(f"Fade placement failed for {coin}: {e}")
                    logger.info(
                        f"🚨 LIQUIDATION/WHALE [{coin}]: {side} ${ntl:,.2f} @ ${px:,.2f} ({liq_info['source']})"
                    )
                    if self.alerter.enabled:
                        slippage = (abs(px - mark) / mark * 100.0) if mark else 0.0
                        # Exotic tier first: a $2.5k fill printing far from mark is a
                        # forced exit that the $25k notional tier would never surface.
                        if self.alerter.qualifies_as_exotic_sweep(ntl, slippage) and ntl < 25000.0:
                            self.alerter.alert_exotic_sweep(coin, side, px, ntl, slippage, mark)
                        elif ntl >= 25000.0:
                            self.alerter.alert_whale_trade(coin, side, px, ntl, is_liq=True)
                elif ntl >= 100000.0 and self.alerter.enabled:
                    self.alerter.alert_whale_trade(coin, side, px, ntl, is_liq=False)

        def handle_mids(mids_data: Any):
            if isinstance(mids_data, dict):
                mids = mids_data.get("mids", mids_data)
                if not isinstance(mids, dict):
                    return
                for k, v in mids.items():
                    try:
                        self._current_marks[k] = float(v)
                    except (ValueError, TypeError):
                        pass
                # Settle resting fades on the freshest marks available. This also
                # expires anything past its TTL, so a stale order cannot fill on
                # price action unrelated to the cascade that placed it.
                try:
                    if self.paper_trader.open_orders or self.paper_trader.positions:
                        out = self.fade_strategy.on_mids(
                            self._current_marks, allow_fills=FADE_STRATEGY_ENABLED
                        )
                        if out["filled"] or out["closed"] or out.get("cancelled"):
                            self._paper_dirty = True
                        if out.get("cancelled"):
                            logger.info(
                                f"🛑 Fade retired: cancelled {out['cancelled']} "
                                f"resting order(s) rather than letting them fill"
                            )
                        for f in out["filled"]:
                            logger.info(
                                f"💼 FADE FILLED {f['side']} {f['coin']} @ ${f['limit_price']:,.4f}"
                            )
                        for c in out["closed"]:
                            pnl_note = ""
                            entry = c.get("entry_price") or 0.0
                            if entry:
                                move = (c["price"] - entry) / entry * 100.0
                                pnl_note = f" ({move:+.2f}% vs entry)"
                            logger.info(
                                f"💼 FADE CLOSED {c['coin']} {c['exit_reason']} "
                                f"@ ${c['price']:,.4f}{pnl_note} | "
                                f"realized ${self.paper_trader.realized_pnl:+,.2f}"
                            )
                except Exception as e:
                    logger.error(f"Fade settlement failed: {e}")

        self.ws_client.register_handler("trades", handle_trades)
        self.ws_client.register_handler("allMids", handle_mids)

    def _buffer_trade(self, row: Dict[str, Any]):
        if len(self._trade_buffer) >= MAX_BUFFERED_TRADES:
            self._trade_buffer.pop(0)
            self._dropped_rows += 1
        self._trade_buffer.append(row)

    def _buffer_liq_event(self, row: Dict[str, Any]):
        if len(self._liq_buffer) >= MAX_BUFFERED_LIQ_EVENTS:
            self._liq_buffer.pop(0)
            self._dropped_rows += 1
        self._liq_buffer.append(row)

    def _flush_buffers_sync(self, trades: List[Dict[str, Any]], liqs: List[Dict[str, Any]]):
        """Blocking DB write, always executed on the DB worker thread."""
        try:
            if trades:
                self.repo.insert_trades(trades)
            if liqs:
                self.repo.insert_liquidation_events(liqs)
        except Exception as e:
            logger.error(f"Failed to flush {len(trades)} trades / {len(liqs)} liq events: {e}")

    async def _flush_loop(self):
        """Drain the write buffers into SQLite on a fixed cadence."""
        loop = asyncio.get_running_loop()
        while self.running:
            await asyncio.sleep(DB_FLUSH_INTERVAL)
            trades, self._trade_buffer = self._trade_buffer, []
            liqs, self._liq_buffer = self._liq_buffer, []
            if not trades and not liqs:
                continue
            if self._dropped_rows:
                logger.warning(f"Write buffer overflow: dropped {self._dropped_rows} rows")
                self._dropped_rows = 0
            await loop.run_in_executor(self._db_executor, self._flush_buffers_sync, trades, liqs)

    def _owns_maintenance(self) -> bool:
        """
        Does THIS process prune, measure and sample right now?

        Exactly one process may. The service collector always does; the
        dashboard's embedded collector does only while no service collector is
        alive, and asks again every cycle.
        """
        if not self.maintenance:
            return False
        if self.yield_to_service and service_collector_alive():
            if not self._yield_logged:
                logger.info("Maintenance yielded: a service collector owns retention, "
                            "measurement persistence and order book sampling")
                self._yield_logged = True
            return False
        if self._yield_logged:
            logger.warning("Service collector gone: this embedded collector takes over maintenance")
            self._yield_logged = False
        return True

    def _spot_universe_cached(self) -> Set[str]:
        """
        The live spot token universe via the arbitrage engine's own lookup, so
        the sampler and the harvester's scan agree on what "spot-backed" means.

        A failed lookup yields an EMPTY set, which `top_funding_candidates`
        treats as "no spot backing can be claimed": zero candidates this pass,
        retried next pass. It is never a licence to fall back to the prefix
        rule that put four unhedgeable coins in the Round 37 sample. A stale
        copy outlives a failed refresh - a listing that existed six hours ago
        still exists.
        """
        now = time.time()
        cached = self._spot_universe
        if cached and now - self._spot_universe_at < SPOT_UNIVERSE_REFRESH_SECONDS:
            return cached
        universe: Set[str] = set()
        try:
            from analytics.funding_arbitrage import FundingArbitrageEngine
            if self._arb_engine is None:
                self._arb_engine = FundingArbitrageEngine(client=self.rest_client)
            universe = set(self._arb_engine.get_spot_universe(refresh=True) or ())
            volumes = dict(self._arb_engine.get_spot_volumes() or {})      # cached by the engine, no request
        except Exception as e:                              # noqa: BLE001 - never fail the pass
            logger.warning(f"Spot universe lookup failed: {e}")
        if universe:
            self._spot_universe, self._spot_universe_at = universe, now
            self._spot_volumes_map = volumes
            self._spot_universe_warned = False
            return universe
        if cached:
            return cached
        if not self._spot_universe_warned:
            logger.warning("Spot universe unavailable: no funding candidates are sampled until it loads")
            self._spot_universe_warned = True
        return set()

    def _sample_coins(self, snapshots: Sequence[Dict[str, Any]] = (),
                      spreads: Optional[Dict[str, float]] = None) -> List[str]:
        """
        Which coins this pass samples, capped:

            held positions > top funding candidates > rotated > core

        Held positions (Round 36) must never lose their spread series to a rank
        change; the top positive-funding candidates (Round 37) get a spread on
        record BEFORE their entry instant, so a persisted window is measured at
        the moment it opens rather than only after the position is held. Round
        38: a candidate must be spot-backed per the live universe and clear the
        OI and volume floors the harvester's scan applies. Round 39: a candidate
        with a spread on record (`spreads`) ranks on its net APR.
        """
        harvester = getattr(self, "basis_harvester", None)
        held = list(getattr(harvester, "positions", {}).keys()) if harvester is not None else []
        candidates: List[str] = []
        if snapshots:
            candidates = top_funding_candidates(snapshots, n=ORDERBOOK_SAMPLE_CANDIDATES,
                                                spot_universe=self._spot_universe_cached(),
                                                spreads=spreads,
                                                spot_volumes=getattr(self, "_spot_volumes_map", None))
        return select_sample_coins(ALL_CORE_WATCHLIST, self._rotated_coins,
                                   cap=ORDERBOOK_SAMPLE_MAX_COINS, extra=held, candidates=candidates)

    def _sample_pass(self) -> Dict[str, Any]:
        """Blocking: read current state, choose coins, sample. Runs on the hl-l2 thread."""
        try:
            snapshots = self.repo.get_latest_snapshots()
        except Exception as e:                              # noqa: BLE001 - sample without candidates
            logger.warning(f"Could not read latest snapshots for candidate selection: {e}")
            snapshots = []
        spreads: Dict[str, float] = {}
        try:
            spreads = self.repo.get_latest_orderbook_spreads()
        except Exception as e:                              # noqa: BLE001 - rank on gross instead
            logger.warning(f"Could not read latest spreads for candidate ranking: {e}")
        coins = self._sample_coins(snapshots, spreads)
        return sample_orderbooks(self.rest_client, self.repo, coins)

    async def _orderbook_sample_loop(self):
        """Round 35: sample top-of-book spreads for a bounded coin set (Ruling 5.C)."""
        loop = asyncio.get_running_loop()
        while self.running:
            await asyncio.sleep(ORDERBOOK_SAMPLE_INTERVAL)
            if not self.running:
                return
            if not self._owns_maintenance():
                continue
            try:
                stats = await loop.run_in_executor(self._io_executor, self._sample_pass)
                logger.info(
                    "Order book sample: %d/%d coins written, median spread %s bps%s",
                    stats["written"], stats["requested"],
                    ("%.1f" % stats["median_spread_bps"]) if stats["median_spread_bps"] is not None else "n/a",
                    (", failed: %s" % ", ".join(sorted(stats["failed"]))) if stats["failed"] else "")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Order book sampling failed: {e}")

    async def _maintenance_loop(self):
        """Periodically prune expired rows and checkpoint the WAL."""
        loop = asyncio.get_running_loop()
        while self.running:
            await asyncio.sleep(DB_MAINTENANCE_INTERVAL)
            if not self.running:
                return
            if not self._owns_maintenance():
                continue
            try:
                stats = await loop.run_in_executor(self._maint_executor, self.repo.run_maintenance)
                persisted = stats.get("persisted") or {}
                logger.info(
                    "DB maintenance: pruned %d rows, WAL %d pages checkpointed, DB %.1f MB; "
                    "persisted %d windows / %d events%s",
                    stats["total_deleted"],
                    max(0, stats["checkpointed_pages"]),
                    stats["db_bytes"] / 1_048_576.0,
                    persisted.get("windows_written", 0),
                    persisted.get("events_written", 0),
                    (" - PERSISTENCE FAILED, measured tables NOT pruned: %s" % persisted["error"])
                    if persisted.get("error") else "",
                )
            except Exception as e:
                logger.error(f"DB maintenance failed: {e}")

    def _refresh_regimes(self, coins: List[str]) -> int:
        """
        Recompute EMA/RSI/ATR for the subscribed set.

        Blocking: one snapshot-history query per coin. Runs on the DB executor at
        the rotation cadence, never on the WebSocket path - a sweep must not wait
        on a few dozen history reads to place its fade.
        """
        from analytics.indicators import compute_regime
        ok = 0
        for coin in coins:
            try:
                r = compute_regime(
                    coin, repo=self.repo,
                    ema_period=REGIME_EMA_PERIOD,
                    rsi_period=REGIME_RSI_PERIOD,
                    atr_period=REGIME_ATR_PERIOD,
                    bucket_minutes=REGIME_BUCKET_MINUTES,
                    lookback_minutes=REGIME_LOOKBACK_MINUTES,
                )
                self._regimes[coin] = r
                ok += int(bool(r.get("sufficient")))
            except Exception as e:
                logger.debug(f"Regime computation failed for {coin}: {e}")
        return ok

    async def _basis_accrual_loop(self):
        """
        The delta-neutral engine that replaced the retired fade.

        Once per funding period: credit open positions using the CURRENT hourly
        rate, then look for new cash-and-carries. Both halves are blocking (DB
        reads plus L2 book fetches for the spread check), so both run on the DB
        executor - a funding accrual must never stall the WebSocket path.
        """
        from execution.basis_harvester import BasisHarvester
        from execution.strategies.basis_strategy import scan_basis_opportunities
        from analytics.funding_arbitrage import FundingArbitrageEngine
        from config.dynamic_config import get_dynamic_config
        from strategies.funding_harvester import FundingHarvester

        harvester = BasisHarvester()
        harvester.load()
        self.basis_harvester = harvester
        # EVERY OPEN NOW GOES THROUGH THE hl_basis_harvest BUCKET. Until Round 29
        # this loop called `harvester.open_position(opp)` directly, and the
        # harvester gates only on its own paper cash - so two positions at the
        # configured notional committed $40,000 without one reference to the
        # bankroll. Built once, outside the cycle, because constructing it opens
        # the tax ledger.
        gated = FundingHarvester(harvester=harvester)
        self.basis_gate = gated
        if gated.gate.hook is None:
            # The gate fails closed by design, so this is the difference between
            # "no opportunities today" and "the strategy is switched off". Said
            # once, loudly, rather than discovered from an empty position list.
            logger.error(
                "Basis harvester is GATED OFF: the bankroll could not be read (%s). "
                "No position will open until the tax ledger is available.",
                gated.gate.hook_error or "no hook")
        loop = asyncio.get_running_loop()

        while self.running:
            try:
                await asyncio.sleep(BASIS_ACCRUAL_INTERVAL)

                def _cycle():
                    # Accrue on live rates. A coin with no current snapshot accrues
                    # nothing rather than repeating a stale rate.
                    rates = {}
                    for snap in self.repo.get_latest_snapshots():
                        coin = snap.get("coin")
                        if coin in harvester.positions:
                            rates[coin] = float(snap.get("funding_rate") or 0.0)
                    credited = harvester.accrue(rates, hours=BASIS_ACCRUAL_INTERVAL / 3600.0)

                    funding_aprs = {coin: rate * 8760.0 * 100.0 for coin, rate in rates.items()}
                    closed = harvester.sweep_exits(funding_aprs)
                    # Round 43 (Ruling 43-3): ONE volume map per cycle. The engine
                    # built here feeds the illiquid sweep, the scan (scanner=) and
                    # the sampler's cache, so all three agree on what "liquid"
                    # means this hour. A failed lookup leaves None: the sweep
                    # fails closed and the scan claims no spot backing.
                    engine = FundingArbitrageEngine(client=self.rest_client)
                    volumes = engine.get_spot_volumes()
                    if volumes:
                        self._spot_volumes_map = dict(volumes)
                        self._spot_universe = engine.get_spot_universe()
                        self._spot_universe_at = time.time()
                    # Round 42 (Ruling 42-2): a hedge that could not be filled is
                    # not a hedge.
                    closed += harvester.sweep_illiquid_exits(volumes)

                    opened = []
                    cfg = get_dynamic_config()
                    effective_max = cfg.max_concurrent_positions if cfg.max_concurrent_positions else BASIS_MAX_CONCURRENT
                    if not (cfg.emergency_killswitch or cfg.pause_new_entries) and len(harvester.positions) < effective_max:
                        scan = scan_basis_opportunities(
                            scanner=engine,
                            min_funding_apr=cfg.basis_min_funding_apr if cfg.basis_min_funding_apr is not None else BASIS_MIN_FUNDING_APR,
                            min_net_apr=cfg.basis_min_net_apr if cfg.basis_min_net_apr is not None else BASIS_MIN_NET_APR,
                            notional_usd=cfg.basis_notional_usd if cfg.basis_notional_usd is not None else BASIS_NOTIONAL_USD,
                            # Round 38: the spread ceiling reaches every costed
                            # row, not only the head the scanner probes.
                            max_spread_bps=cfg.max_spread_bps if cfg.max_spread_bps is not None else ARB_MAX_SPREAD_BPS,
                            check_spreads=True,
                        )
                        for opp in scan["accepted"]:
                            verdict = gated.evaluate(opp)
                            if not verdict.tradeable:
                                logger.info("Basis %s declined: %s",
                                            verdict.coin, " | ".join(verdict.reasons))
                                continue
                            pos = harvester.open_position(
                                opp,
                                notional_per_leg=verdict.gate.approved_notional_per_leg)
                            if pos:
                                opened.append(pos)
                            else:
                                logger.info("Basis %s not opened: %s", opp.get("coin"),
                                            getattr(harvester, "last_refusal", None) or "harvester gate")
                    harvester.save()
                    return credited, opened, closed

                credited, opened, closed = await loop.run_in_executor(self._db_executor, _cycle)

                if closed:
                    for c in closed:
                        logger.info(f"🚪 Basis position closed: {c['coin']} "
                                    f"reason={c.get('exit_reason')} net_pnl=${c.get('net_pnl', 0.0):+,.2f}")

                if credited:
                    total = sum(credited.values())
                    logger.info(f"💰 Basis funding accrued: ${total:+,.4f} across "
                                f"{len(credited)} position(s)")
                for pos in opened:
                    logger.info(f"⚖️  Basis position opened: {pos['coin']} "
                                f"(long {pos['spot_symbol']} spot / short perp) "
                                f"@ {pos['entry_funding_apr']:.1f}% APR")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Basis accrual cycle failed: {e}")

    async def _paper_save_loop(self):
        """
        Flush the paper account to disk when it has changed.

        Written here rather than on every fill: a cascade produces many events in
        a burst, and rewriting the file per event would put synchronous disk IO on
        the WebSocket path.
        """
        loop = asyncio.get_running_loop()
        while self.running:
            await asyncio.sleep(PAPER_SAVE_INTERVAL)
            if not self._paper_dirty:
                continue
            self._paper_dirty = False
            try:
                await loop.run_in_executor(self._db_executor, self.paper_trader.save)
            except Exception as e:
                logger.error(f"Paper state save failed: {e}")

    async def _sync_universe_metadata(self):
        """Fetch and cache universe specifications for all supported DEXes."""
        assets_records = []
        for dex in ACTIVE_DEXES:
            try:
                res = self.rest_client.get_meta_and_asset_ctxs(dex=dex)
                if not res or len(res) < 2:
                    continue
                universe = res[0].get("universe", [])
                for u in universe:
                    coin_name = u["name"]
                    # If DEX is not main and name doesn't have prefix, add prefix
                    if dex != "main" and not coin_name.startswith(f"{dex}:"):
                        coin_name = f"{dex}:{coin_name}"

                    assets_records.append({
                        "coin": coin_name,
                        "dex": dex,
                        "sz_decimals": u.get("szDecimals", 4),
                        "max_leverage": u.get("maxLeverage", 20),
                        "only_isolated": u.get("onlyIsolated", False)
                    })
            except Exception as e:
                logger.warning(f"Error fetching metadata for DEX {dex}: {e}")

        self.repo.upsert_assets(assets_records)
        logger.info(f"Synced {len(assets_records)} assets across DEXes: {ACTIVE_DEXES}")

    def _poll_contexts_once(self) -> Dict[str, Any]:
        """
        One full REST sweep across every active DEX.

        Blocking by design: the rate limiter sleeps, so this runs in the DB/IO
        executor rather than stalling the WebSocket recv loop.
        """
        now_ts = int(time.time() * 1000)
        snapshots: List[Dict[str, Any]] = []
        all_clusters: List[Dict[str, Any]] = []

        for dex in ACTIVE_DEXES:
            try:
                res = self.rest_client.get_meta_and_asset_ctxs(dex=dex)
                if not res or len(res) < 2:
                    continue
                universe = res[0].get("universe", [])
                ctxs = res[1]

                for u, c in zip(universe, ctxs):
                    coin = u["name"]
                    if dex != "main" and not coin.startswith(f"{dex}:"):
                        coin = f"{dex}:{coin}"

                    mark_px = float(c.get("markPx") or c.get("midPx") or c.get("oraclePx") or 0.0)
                    if mark_px <= 0:
                        continue

                    self._current_marks[coin] = mark_px
                    oi = float(c.get("openInterest") or 0.0)
                    notional_oi = oi * mark_px
                    funding = float(c.get("funding") or 0.0)
                    day_vlm = float(c.get("dayNtlVlm") or 0.0)

                    snapshots.append({
                        "timestamp": now_ts,
                        "coin": coin,
                        "dex": dex,
                        "mark_px": mark_px,
                        "mid_px": float(c.get("midPx") or mark_px),
                        "oracle_px": float(c.get("oraclePx") or mark_px),
                        "open_interest": oi,
                        "notional_oi": notional_oi,
                        "funding_rate": funding,
                        "premium": float(c.get("premium") or 0.0),
                        "day_ntl_vlm": day_vlm
                    })

                    # Calculate liquidation clusters for major TradFi and Crypto watchlist coins
                    if coin in ALL_CORE_WATCHLIST and oi > 0:
                        max_lev = u.get("maxLeverage", 20)
                        clusters = self.liq_engine.calculate_liquidation_clusters(
                            coin, mark_px, oi, max_lev
                        )
                        all_clusters.extend(clusters)

            except Exception as e:
                logger.error(f"Error polling DEX {dex}: {e}")

        if snapshots:
            self.repo.insert_snapshots(snapshots)
        if all_clusters:
            self.repo.insert_liquidation_clusters(all_clusters)

        return {"snapshots": len(snapshots), "clusters": len(all_clusters)}

    async def _poll_market_contexts_loop(self):
        """Periodically poll REST contexts for all DEXes and calculate liquidation clusters."""
        loop = asyncio.get_running_loop()
        while self.running:
            try:
                stats = await loop.run_in_executor(self._db_executor, self._poll_contexts_once)
                if stats["snapshots"]:
                    logger.info(
                        f"Persisted {stats['snapshots']} market snapshots "
                        f"and {stats['clusters']} liquidation clusters."
                    )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in market context polling loop: {e}")

            await asyncio.sleep(REST_POLL_INTERVAL)

    async def _subscribe_tradfi_streams(self):
        """Subscribe WS streams for top TradFi assets."""
        await self.ws_client.subscribe_all_mids()
        for coin in ALL_CORE_WATCHLIST:
            await self.ws_client.subscribe_trades(coin)
        logger.info(f"Subscribed to trade feeds for {len(ALL_CORE_WATCHLIST)} core watchlist assets")

    def _compute_rotation_candidates(self, limit: int = ROTATION_MAX_COINS) -> List[str]:
        """
        Coins worth streaming, split between liquid majors and thin-book exotics.

        Volume-only ranking had a defect that took a full observation window to
        surface: it selected exclusively >$5M OI books, so the exotic tier built
        across rounds 9-12 never fired once - every single fill was the $10k major
        tier, and the exotic thesis was never actually tested.

        Slots are therefore split. Majors are ranked by 24h volume (liquidations
        happen where there is flow); exotics are the thin books - OI under the
        ceiling but with real turnover - ranked by volume within that band.
        Unused exotic slots spill back to majors rather than idling.

        Blocking (a DB read), so it is always called on the DB executor.
        """
        try:
            snaps = self.repo.get_latest_snapshots()
        except Exception as e:
            logger.debug(f"Rotation candidate scan failed: {e}")
            return []

        # Cache OI while we have the rows, so the fade strategy can classify a
        # market without a second query on the hot path.
        for s in snaps:
            self._notional_oi[s.get("coin", "")] = float(s.get("notional_oi") or 0.0)

        def vol(s):
            return float(s.get("day_ntl_vlm") or 0.0)

        def oi(s):
            return float(s.get("notional_oi") or 0.0)

        tradeable = [s for s in snaps if vol(s) >= ROTATION_MIN_DAY_VOLUME]

        exotics = sorted(
            (s for s in tradeable
             if oi(s) < ROTATION_EXOTIC_MAX_OI and vol(s) >= ROTATION_EXOTIC_MIN_VOLUME),
            key=vol, reverse=True,
        )
        majors = sorted(
            (s for s in tradeable if oi(s) >= ROTATION_EXOTIC_MAX_OI),
            key=vol, reverse=True,
        )

        picked_exotics = [s["coin"] for s in exotics[:ROTATION_EXOTIC_SLOTS]]
        # Spill: an empty exotic band should not cost us major coverage.
        major_slots = ROTATION_MAJOR_SLOTS + (ROTATION_EXOTIC_SLOTS - len(picked_exotics))
        picked_majors = [s["coin"] for s in majors[:major_slots]]

        self._last_rotation_split = (len(picked_majors), len(picked_exotics))
        return (picked_majors + picked_exotics)[:limit]

    async def _rotation_loop(self):
        """
        Keep trade subscriptions pointed at whatever is currently squeezing.

        The precedence validator could not answer whether squeeze flags precede
        liquidations, because `liquidation_events` only ever filled for the core
        watchlist the trade feed subscribes to - while the squeeze engine
        deliberately targets exotics that were never subscribed. Rotating the
        exotic candidates onto the live feed closes that loop, and costs nothing
        in REST budget: WebSocket subscriptions are free.

        The core watchlist is never touched, so the dashboard keeps its feeds.
        """
        loop = asyncio.get_running_loop()
        core = set(ALL_CORE_WATCHLIST)

        while self.running:
            await asyncio.sleep(ROTATION_INTERVAL)
            if not self.running:
                return
            try:
                candidates = await loop.run_in_executor(
                    self._db_executor, self._compute_rotation_candidates, ROTATION_MAX_COINS
                )
                # Never rotate a core-watchlist coin: it is already subscribed
                # permanently, and unsubscribing it later would break the dashboard.
                wanted = {c for c in candidates if c not in core}
                to_add, to_drop, held = self._plan_rotation(wanted)

                for coin in to_drop:
                    await self.ws_client.unsubscribe_trades(coin)
                    self._rotation_sub_time.pop(coin, None)
                now = time.monotonic()
                for coin in to_add:
                    await self.ws_client.subscribe("trades", {"coin": coin})
                    self._rotation_sub_time[coin] = now

                self._rotated_coins = (self._rotated_coins | to_add) - to_drop

                # Refresh regimes for everything currently subscribed, so the
                # fade gate has a view for each market it might act on.
                if REGIME_ENABLED:
                    watched = sorted(core | self._rotated_coins)
                    ready = await loop.run_in_executor(
                        self._db_executor, self._refresh_regimes, watched
                    )
                    logger.info(
                        f"📐 Regime refresh: {ready}/{len(watched)} markets have usable "
                        f"EMA/RSI/ATR"
                    )

                if to_add or to_drop:
                    maj, exo = self._last_rotation_split
                    logger.info(
                        f"🌀 Rotation [{maj} majors / {exo} exotics]: +{len(to_add)} -{len(to_drop)} "
                        f"(tracking {len(self._rotated_coins)} active markets"
                        + (f", {len(held)} held by cooldown" if held else "")
                        + (f": {', '.join(sorted(self._rotated_coins)[:5])}" if self._rotated_coins else "")
                        + ")"
                    )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Rotation failed: {e}")

    def _plan_rotation(self, wanted: Set[str], now: float = None):
        """
        Decide what to subscribe, unsubscribe, and hold this cycle.

        Hysteresis: a coin that falls out of the candidate set is NOT dropped
        until it has been subscribed for at least ROTATION_COOLDOWN_SECONDS.
        Volume rank is noisy minute to minute, and a market that briefly slips out
        of the top N is often mid-cascade - dropping the feed there would cut the
        recording off exactly when it matters.

        Returns (to_add, to_drop, held_by_cooldown).
        """
        now = time.monotonic() if now is None else now
        capacity = max(0, ROTATION_MAX_COINS - len(self._rotated_coins))

        stale = self._rotated_coins - wanted
        to_drop = {
            c for c in stale
            if (now - self._rotation_sub_time.get(c, 0.0)) >= ROTATION_COOLDOWN_SECONDS
        }
        held = stale - to_drop

        # Freed slots become available to new candidates in the same cycle.
        capacity += len(to_drop)
        new = sorted(wanted - self._rotated_coins)
        to_add = set(new[:capacity])

        return to_add, to_drop, held

    async def run(self):
        """Run the complete asynchronous ingestion system."""
        self.running = True
        self._setup_ws_handlers()

        logger.info("Initializing asset universes...")
        await self._sync_universe_metadata()

        tasks = [
            asyncio.create_task(self.ws_client.start()),
            asyncio.create_task(self._poll_market_contexts_loop()),
            asyncio.create_task(self._subscribe_tradfi_streams()),
            asyncio.create_task(self._flush_loop()),
            asyncio.create_task(self._rotation_loop()),
            asyncio.create_task(self._paper_save_loop()),
            asyncio.create_task(self._basis_accrual_loop()),
        ]
        if self.maintenance:
            tasks.append(asyncio.create_task(self._maintenance_loop()))
            tasks.append(asyncio.create_task(self._orderbook_sample_loop()))
            if self.yield_to_service:
                logger.info("Embedded collector: maintenance and order book sampling yield to a "
                            "live service collector, re-checked every cycle")
        else:
            logger.info("Maintenance loop DISABLED for this collector: another process owns "
                        "retention and measurement persistence")

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Collector received stop signal.")
        finally:
            self.running = False
            for t in tasks:
                t.cancel()
            await self.ws_client.stop()
            # Do not lose whatever is still buffered on the way out.
            trades, self._trade_buffer = self._trade_buffer, []
            liqs, self._liq_buffer = self._liq_buffer, []
            if trades or liqs:
                self._flush_buffers_sync(trades, liqs)
            try:
                self.paper_trader.save()
            except Exception as e:
                logger.error(f"Final paper state save failed: {e}")
            self.whale_tracker.shutdown()
            self._db_executor.shutdown(wait=False)
            self._maint_executor.shutdown(wait=False)
            self._io_executor.shutdown(wait=False)


def start_collector():
    """
    Run one collector, refusing to start if another already holds the lock.

    The PID lockfile previously guarded only the service *supervisor*, so
    `python main.py collector` run directly bypassed it entirely. Two collectors
    then wrote the same paper_trading_state.json and clobbered each other - which
    is how a position carrying the old fade geometry ended up in an account
    created after the re-geometry. The paper account is now the thing being
    measured, so a silent second writer corrupts the measurement.
    """
    try:
        from run_collector_service import acquire_pid_lock, release_pid_lock, running_supervisor_pid
        from config.settings import COLLECTOR_LOCK_PATH
    except Exception:
        # Lock unavailable: run anyway rather than refusing to collect at all.
        collector = MarketCollector()
        asyncio.run(collector.run())
        return

    if not acquire_pid_lock(COLLECTOR_LOCK_PATH):
        holder = running_supervisor_pid(COLLECTOR_LOCK_PATH)
        logger.error(
            "Another collector is already running (PID %s). Refusing to start a second "
            "one - concurrent writers corrupt the paper account and contend on SQLite.",
            holder,
        )
        return

    try:
        collector = MarketCollector()
        asyncio.run(collector.run())
    finally:
        release_pid_lock(COLLECTOR_LOCK_PATH)


if __name__ == "__main__":
    start_collector()
