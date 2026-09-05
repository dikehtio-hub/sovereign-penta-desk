"""
Interactive Real-Time Terminal Dashboard for HL_Monarch.
Responsive layout, compact density, Windows UTF-8 safe, interactive category hotkeys (1-8, Tab, Q).
"""
import sys
import time
import signal
import threading
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from config.settings import (
    ALL_CORE_WATCHLIST, WATCHLIST_STOCKS, WATCHLIST_COMMODITIES,
    WATCHLIST_INDICES, WATCHLIST_FX, WATCHLIST_CRYPTO_BENCHMARKS,
    DASHBOARD_SCAN_TTL_SECONDS
)
from storage.repository import MarketRepository
from analytics.market_intelligence import MarketIntelligence
from analytics.liquidation_engine import LiquidationEngine
from analytics.position_scanner import PositionScanner
from analytics.funding_arbitrage import FundingArbitrageEngine
from analytics.alerter import WebhookAlerter
from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy
from collectors.market_collector import MarketCollector, read_service_pid, service_collector_alive
from ui.components import (append_dashboard_event, ingestion_badge, newest_snapshot_age_seconds,
                           novel_dex_badge, read_collector_status)
from ui.components import (
    build_header_panel, build_tradfi_table, build_liquidations_panel,
    build_clusters_panel, build_top_wallets_panel, build_funding_arb_panel,
    build_paper_trading_panel
)

console = Console()

CYCLE_ASSETS = [
    "xyz:GOLD", "xyz:XYZ100", "xyz:NVDA", "xyz:TSLA", "xyz:SP500",
    "xyz:SILVER", "xyz:CL", "BTC", "ETH", "SOL", "HYPE"
]

class TerminalDashboard:
    def __init__(self, focus_asset: str = "xyz:GOLD"):
        self.repo = MarketRepository()
        self.scanner = PositionScanner()
        self.arb_engine = FundingArbitrageEngine()
        # Same persisted account the collector's reactive fade engine writes to,
        # so the dashboard reflects real strategy activity rather than a blank
        # in-memory account of its own.
        self.paper_trader = PaperTrader.load()
        self.fade_strategy = LiquidationFadeStrategy(self.paper_trader)
        self.running = False
        # Round 36 (Ruling 3.A): None until start() decides; True = read-only
        # viewer over the service's database; False = standalone ingestion.
        self.service_mode: Optional[bool] = None
        self.service_pid: Optional[int] = None
        self._service_alive: bool = False
        self._service_badge: str = ""
        # Round 53: dead-service watchdog + alerts (Rulings 53-1/53-2).
        self.alerter = WebhookAlerter()
        self._watchdog_last_relaunch: float = 0.0
        self._service_dead_since: Optional[float] = None
        self._status_stale_alerted = False
        self._service_checked_at: float = 0.0
        self.focus_asset = focus_asset
        self.active_tab = "ALL"  # 'ALL', 'STOCKS', 'COMMODITIES', 'INDICES_FX', 'CRYPTO', 'WHALES', 'ARB', 'PAPER'
        self._focus_idx = 0
        if focus_asset in CYCLE_ASSETS:
            self._focus_idx = CYCLE_ASSETS.index(focus_asset)
        # generate_layout() runs on every rendered frame (~1/s). The whale and
        # funding scans behind tabs 6 and 7 are REST-backed, so without a TTL
        # holding one of those tabs issued ~15 requests per second and blocked
        # the render thread on the rate limiter.
        self._scan_cache: Dict[str, Any] = {}

    def _cached(self, key: str, producer, ttl: float = DASHBOARD_SCAN_TTL_SECONDS):
        """Memoize an expensive scan for `ttl` seconds, serving stale data on error."""
        now = time.monotonic()
        entry = self._scan_cache.get(key)
        if entry is not None and (now - entry[0]) < ttl:
            return entry[1]
        try:
            value = producer()
        except Exception:
            # Keep the panel populated rather than blanking it on a transient error.
            return entry[1] if entry is not None else None
        self._scan_cache[key] = (now, value)
        return value

    def cycle_focus_asset(self):
        """Cycle to the next focus asset for the liquidation heatmap."""
        self._focus_idx = (self._focus_idx + 1) % len(CYCLE_ASSETS)
        self.focus_asset = CYCLE_ASSETS[self._focus_idx]

    def set_tab(self, tab_name: str):
        """Set the active category tab."""
        self.active_tab = tab_name

    def _get_active_watchlist_coins(self) -> List[str]:
        """Return list of coins corresponding to active tab."""
        if self.active_tab == "STOCKS":
            return WATCHLIST_STOCKS
        elif self.active_tab == "COMMODITIES":
            return WATCHLIST_COMMODITIES
        elif self.active_tab == "INDICES_FX":
            return WATCHLIST_INDICES + WATCHLIST_FX
        elif self.active_tab == "CRYPTO":
            return WATCHLIST_CRYPTO_BENCHMARKS
        else:
            return ALL_CORE_WATCHLIST

    def _header_status(self, service_badge: str) -> str:
        """The service badge plus, when the collector's status file names a dex no
        settings set knows, the amber NOVEL DEX badge (Round 48, Ruling 48-2)."""
        from config.settings import COLLECTOR_STATUS_PATH
        status = read_collector_status(COLLECTOR_STATUS_PATH)
        drift = novel_dex_badge(status.get("unclassified_dexs"))
        try:
            self.status_stale_watch()
        except Exception:                                   # noqa: BLE001 - never break a frame
            pass
        return "  ".join(part for part in (service_badge, drift) if part)

    @staticmethod
    def relaunch_service(bat=None) -> bool:
        """Run the detached launcher without a window; True if the command was issued."""
        import subprocess
        from config.settings import START_COLLECTOR_BAT
        bat = Path(bat or START_COLLECTOR_BAT)
        if not bat.exists():
            return False
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(bat.parent), creationflags=flags,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:                                   # noqa: BLE001 - a failed relaunch is logged, not fatal
            return False

    def service_watchdog(self, alive: bool, now: Optional[float] = None, relaunch=None,
                         alerter=None, log=None, enabled: Optional[bool] = None,
                         cooldown: Optional[float] = None) -> Optional[str]:
        """
        Round 53 (Rulings 53-1/53-2). Only a dashboard that STARTED read-only
        acts: when its service dies it logs service_dead, alerts once per
        episode, and issues the detached relaunch at most once per cooldown;
        when the service is back it logs service_back. A standalone dashboard
        is the ingester itself and never relaunches anything. Returns the
        action taken, for the log and the tests.
        """
        from config.settings import (DASHBOARD_LOG_PATH, SERVICE_WATCHDOG_COOLDOWN_SECONDS,
                                     SERVICE_WATCHDOG_ENABLED)
        if not self.service_mode:
            return None
        now = time.monotonic() if now is None else now
        relaunch = relaunch or self.relaunch_service
        alerter = alerter or self.alerter
        log = log or (lambda event, **fields: append_dashboard_event(DASHBOARD_LOG_PATH, event, **fields))
        enabled = SERVICE_WATCHDOG_ENABLED if enabled is None else enabled
        cooldown = SERVICE_WATCHDOG_COOLDOWN_SECONDS if cooldown is None else cooldown
        if alive:
            if self._service_dead_since is not None:
                log("service_back", service_pid=self.service_pid,
                    dead_for_s=round(now - self._service_dead_since, 1))
                self._service_dead_since = None
                return "back"
            return None
        action = "dead"
        if self._service_dead_since is None:
            self._service_dead_since = now
            log("service_dead", service_pid=self.service_pid)
            try:
                alerter.alert_service_down(self.service_pid)
            except Exception:                               # noqa: BLE001 - alerting must not break the viewer
                pass
        if enabled and now - self._watchdog_last_relaunch >= cooldown:
            self._watchdog_last_relaunch = now
            issued = bool(relaunch())
            log("service_relaunch", issued=issued, service_pid=self.service_pid)
            action = "relaunched" if issued else "relaunch_failed"
        return action

    def status_stale_watch(self, status_path=None, now: Optional[float] = None, alerter=None,
                           log=None) -> bool:
        """
        Round 53 (Ruling 53-2): while the service is alive, a status file older
        than COLLECTOR_STATUS_MAX_AGE_SECONDS means the hourly cycle stopped
        writing. Alert once per stale episode; reset when it is fresh again.
        """
        from config.settings import (COLLECTOR_STATUS_MAX_AGE_SECONDS, COLLECTOR_STATUS_PATH,
                                     DASHBOARD_LOG_PATH)
        status = read_collector_status(status_path or COLLECTOR_STATUS_PATH, max_age_s=None)
        if not status or not self._service_alive:
            return False
        try:
            age = (now if now is not None else time.time()) - float(status.get("checked_at") or 0.0)
        except (TypeError, ValueError):
            return False
        stale = age > COLLECTOR_STATUS_MAX_AGE_SECONDS
        if stale and not self._status_stale_alerted:
            self._status_stale_alerted = True
            (log or (lambda event, **f: append_dashboard_event(DASHBOARD_LOG_PATH, event, **f)))(
                "status_stale", age_s=round(age, 1))
            try:
                (alerter or self.alerter).alert_status_stale(age, COLLECTOR_STATUS_MAX_AGE_SECONDS)
            except Exception:                               # noqa: BLE001
                pass
        elif not stale:
            self._status_stale_alerted = False
        return stale

    def _refresh_service_badge(self, force: bool = False, ttl: float = 5.0,
                               newest_snapshot_age_s: Optional[float] = None) -> str:
        """
        Re-check the service every few seconds so the header tells the truth:
        a read-only dashboard whose service has died is showing STALE data, and
        a standalone dashboard that a service has since joined is double-polling
        until it is restarted. The process probe is cached for `ttl`; the badge
        itself is rebuilt every frame because the snapshot age (Round 37's
        STALLED state) moves every frame and costs nothing.
        """
        now = time.monotonic()
        if force or now - self._service_checked_at >= ttl:
            self._service_checked_at = now
            self._service_alive = service_collector_alive()
            if self._service_alive:
                self.service_pid = read_service_pid()
            self.service_watchdog(self._service_alive, now=now)
        _, self._service_badge = ingestion_badge(self._service_alive, self.service_pid, self.service_mode,
                                                 newest_snapshot_age_s=newest_snapshot_age_s)
        return self._service_badge

    def generate_layout(self) -> Layout:
        """Construct a sleek, responsive UI layout fitting any terminal window."""
        term_width = console.width or 100

        # Fetch latest data
        all_snapshots = self.repo.get_latest_snapshots()
        # Round 37: the service badge needs the newest snapshot age, so it is
        # built AFTER the fetch - a live process writing nothing is a stall.
        service_badge = self._refresh_service_badge(
            newest_snapshot_age_s=newest_snapshot_age_seconds(all_snapshots))
        active_coins = self._get_active_watchlist_coins()
        filtered_snapshots = [s for s in all_snapshots if s.get("coin") in active_coins]
        if not filtered_snapshots and all_snapshots and self.active_tab not in ("WHALES", "ARB", "PAPER"):
            filtered_snapshots = all_snapshots[:15]

        summary = MarketIntelligence.summarize_tradfi_metrics(all_snapshots)
        dex_oi = self.repo.get_total_oi_by_dex()
        recent_liqs = self.repo.get_recent_liquidations(limit=10)
        recent_trades = self.repo.get_recent_trades(limit=10)
        clusters = self.repo.get_latest_clusters(self.focus_asset)

        # Dynamic cluster calculation if not yet in DB
        if not clusters and all_snapshots:
            for s in all_snapshots:
                if s.get("coin") == self.focus_asset:
                    # Snapshot rows come from SQLite, whose column is open_interest;
                    # the camelCase API key never matched, so this always fell back
                    # to the 1000.0 placeholder and reported bogus cluster notionals.
                    clusters = LiquidationEngine.calculate_liquidation_clusters(
                        self.focus_asset,
                        float(s.get("mark_px") or 0.0),
                        float(s.get("open_interest") or 0.0)
                    )
                    break

        # Check for simulated strategy executions from recent large liquidations
        if recent_liqs and all_snapshots:
            marks_map = {s["coin"]: float(s.get("mark_px", 0)) for s in all_snapshots}
            # Settle resting fades against the latest marks. Placement happens in
            # the collector, off the live trade feed - the dashboard only marks
            # the book and never opens a position of its own.
            try:
                self.paper_trader.check_open_orders(marks_map)
            except Exception:
                pass

        # Root Layout
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=1)
        )

        # Split body: Left (Market Watch / Tabs) and Right (Intelligence / Feeds)
        if term_width >= 125:
            layout["body"].split_row(
                Layout(name="left", ratio=3),
                Layout(name="right", ratio=2)
            )
            layout["right"].split(
                Layout(name="clusters", ratio=1),
                Layout(name="liquidations", ratio=1)
            )
        else:
            # Full width clean vertical stack for standard terminals
            layout["body"].split(
                Layout(name="left", ratio=3),
                Layout(name="clusters", ratio=2),
                Layout(name="liquidations", ratio=2)
            )

        # Populate components
        layout["header"].update(
            build_header_panel(summary["total_oi"], summary["total_volume_24h"], dex_oi,
                               active_tab=self.active_tab, status=self._header_status(service_badge))
        )

        if self.active_tab == "WHALES":
            top_positions = self._cached(
                "whales",
                lambda: self.scanner.scan_batch(self.scanner.addresses[:15], min_value_usd=50000.0),
            ) or []
            layout["left"].update(build_top_wallets_panel(top_positions))
        elif self.active_tab == "ARB":
            arb_data = self._cached(
                "arb",
                lambda: self.arb_engine.scan_funding_opportunities(
                    min_apr_pct=8.0, snapshots=all_snapshots
                ),
                ttl=5.0,   # DB-backed and cheap, but still not worth redoing per frame
            ) or {}
            layout["left"].update(build_funding_arb_panel(arb_data))
        elif self.active_tab == "PAPER":
            prices_map = {s["coin"]: float(s.get("mark_px", 0)) for s in all_snapshots}
            self.paper_trader = PaperTrader.load()   # pick up collector activity
            acc_summary = self.paper_trader.get_account_summary(prices_map)
            layout["left"].update(build_paper_trading_panel(
                acc_summary, self.paper_trader.positions, self.paper_trader.trade_history,
                open_orders=self.paper_trader.open_orders,
            ))
        else:
            title = f"{self.active_tab.capitalize()} Watchlist" if self.active_tab != "ALL" else "HIP-3 TradFi Watchlist"
            layout["left"].update(build_tradfi_table(filtered_snapshots, title=title))

        layout["clusters"].update(
            build_clusters_panel(self.focus_asset, clusters)
        )
        layout["liquidations"].update(
            build_liquidations_panel(recent_liqs, recent_trades)
        )

        footer_text = Text(
            f"⚡ Press [1-8] Tabs │ [Tab/H] Focus: {self.focus_asset} │ [Q] Exit",
            style="dim italic yellow"
        )
        layout["footer"].update(footer_text)

        return layout

    def _start_keyboard_listener(self):
        """Non-blocking keyboard listener thread for Windows."""
        if sys.platform == "win32":
            import msvcrt
            def listen_keys():
                while self.running:
                    try:
                        if msvcrt.kbhit():
                            ch = msvcrt.getch()
                            # Handle special keys / arrows
                            if ch in (b'\x00', b'\xe0'):
                                msvcrt.getch()
                                continue
                            try:
                                key = ch.decode("utf-8", errors="ignore").lower()
                            except Exception:
                                continue

                            if key == '1':
                                self.set_tab("ALL")
                            elif key == '2':
                                self.set_tab("STOCKS")
                            elif key == '3':
                                self.set_tab("COMMODITIES")
                            elif key == '4':
                                self.set_tab("INDICES_FX")
                            elif key == '5':
                                self.set_tab("CRYPTO")
                            elif key == '6' or key == 'w':
                                self.set_tab("WHALES")
                            elif key == '7' or key == 'a':
                                self.set_tab("ARB")
                            elif key == '8' or key == 'p':
                                self.set_tab("PAPER")
                            elif key == '\t' or key == 'h':
                                self.cycle_focus_asset()
                            elif key == 'q' or key == '\x03':  # Ctrl+C or 'q'
                                self.running = False
                                break
                        time.sleep(0.05)
                    except Exception:
                        break
            t = threading.Thread(target=listen_keys, daemon=True)
            t.start()

    def start(self, refresh_rate: float = 1.0, fullscreen: bool = True):
        """Run terminal live dashboard with interactive hotkeys and background collector."""
        self.running = True

        # ROUND 36 (Ruling 3.A): ONE INGESTER. While a service collector is alive
        # this dashboard is a READ-ONLY VIEWER over the database it writes. The
        # embedded collector it used to start polled contexts alongside the
        # service - a second 900 weight/min on one IP and ~1.6x the snapshot
        # rows - and that contention was the likeliest source of the 429s behind
        # the continuity gaps. With no service alive it falls back to standalone
        # ingestion (Round 34/35: never pruning underneath a service; yielding
        # maintenance the moment one appears). The header re-checks every few
        # seconds so a service that dies under a read-only dashboard is shown.
        alive = service_collector_alive()
        self.service_pid = read_service_pid()
        self.service_mode = alive
        self._refresh_service_badge(force=True)
        # Round 49 (Ruling 49-1): a lifecycle log, because the viewer died twice
        # today with no trace and there was nothing to read afterwards.
        from config.settings import DASHBOARD_LOG_PATH
        append_dashboard_event(DASHBOARD_LOG_PATH, "dashboard_start",
                               mode="read_only" if alive else "standalone",
                               service_pid=self.service_pid, fullscreen=bool(fullscreen))
        if not alive:
            def run_bg_collector():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                collector = MarketCollector(maintenance=True, yield_to_service=True)
                try:
                    loop.run_until_complete(collector.run())
                except Exception:
                    pass

            collector_thread = threading.Thread(target=run_bg_collector, daemon=True)
            collector_thread.start()

        # Start keyboard hotkey listener
        self._start_keyboard_listener()

        # Handle graceful shutdown
        def handle_exit(signum, frame):
            self.running = False

        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

        self._run_live_loop(fullscreen=fullscreen, refresh_rate=refresh_rate)

    def _run_live_loop(self, fullscreen: bool = True, refresh_rate: float = 1.0) -> None:
        """
        The Live render loop, with its lifecycle written to the dashboard log
        (Round 49, Ruling 49-1): a frame that fails to render is logged (the
        first few, then counted), an exception that escapes the loop is logged
        as a crash WITH its traceback and re-raised, and a clean exit logs stop
        with the frame-error count.
        """
        import traceback
        from config.settings import DASHBOARD_LOG_PATH
        frame_errors = 0
        crashed = False
        try:
            with Live(self.generate_layout(), console=console, screen=fullscreen, refresh_per_second=4) as live:
                while self.running:
                    try:
                        live.update(self.generate_layout())
                        time.sleep(refresh_rate)
                    except KeyboardInterrupt:
                        break
                    except Exception as e:                  # noqa: BLE001 - one bad frame must not end the viewer
                        frame_errors += 1
                        if frame_errors <= 3:
                            append_dashboard_event(DASHBOARD_LOG_PATH, "dashboard_frame_error",
                                                   error=f"{type(e).__name__}: {e}",
                                                   traceback=traceback.format_exc(), count=frame_errors)
                        time.sleep(1.0)
        except BaseException as e:                          # noqa: BLE001 - log the cause, then let it propagate
            crashed = True
            append_dashboard_event(DASHBOARD_LOG_PATH, "dashboard_crash", error=f"{type(e).__name__}: {e}",
                                   traceback=traceback.format_exc(), frame_errors=frame_errors)
            raise
        finally:
            self.running = False
            if not crashed:
                append_dashboard_event(DASHBOARD_LOG_PATH, "dashboard_stop", frame_errors=frame_errors)
            console.print("\n[bold green]✓ Dashboard exited. Terminal ready for commands.[/bold green]\n")

    def print_snapshot(self):
        """Print a single clean snapshot to console without taking over the screen."""
        layout = self.generate_layout()
        console.print(layout)

if __name__ == "__main__":
    dashboard = TerminalDashboard()
    dashboard.start()
