"""
================================================================================
Polymarket Monarch: 100% Free & Native Real-Time Whale Trade Collector
================================================================================
Connects directly to Polymarket's public real-time WebSocket
(wss://ws-live-data.polymarket.com) and stores whale fills plus every discovered
wallet in a local SQLite DB (data/polymarket_whales.db).

A fill counts as a whale when EITHER it clears the absolute threshold
(size * price >= $1,000 USD by default) OR it is at least $250 AND at least 1%
of that market's own 24h volume -- the relative rule catches fills that are
small in dollars but large relative to a thin book. See is_whale_trade().

Market volume is joined onto each RTDS frame by GammaVolumeCache, which keeps a
background-refreshed conditionId -> volume24hr map (RTDS frames carry no volume
of their own). Measured on 150s of live traffic: the relative rule roughly
DOUBLED whale detections (14 absolute + 14 relative-only out of 6,212 frames).

Zero API keys or third-party paid proxies required.
================================================================================
"""

import os
import sys
import time
import json
import sqlite3
import asyncio
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import threading
import requests
import websockets

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    # Flip the console itself to code page 65001 (the API equivalent of
    # `chcp 65001`). Reconfiguring Python's streams alone is not enough when the
    # attached console is still cp1252 -- that is what mangles Polymarket market
    # titles carrying accented characters ("Atletico", "Vitoria", ...).
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        # Child processes (the .bat launches these modules) inherit UTF-8 too.
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "polymarket_whales.db"

FIXTURES_DIR = DATA_DIR / "fixtures"
SAMPLE_TRADES_PATH = FIXTURES_DIR / "sample_trades.json"
# Replay writes to its own DB so offline testing never pollutes live collected data.
REPLAY_DB_PATH = DATA_DIR / "replay_whales.db"

WS_URL = "wss://ws-live-data.polymarket.com"
REST_TRADES_URL = "https://data-api.polymarket.com/trades"

# Cloudflare sits in front of the RTDS socket and drops connections it considers
# idle. websockets' own protocol-level ping is not always enough, so we also send
# an application-level "PING" frame. The server acknowledges with an empty text
# frame (verified live -- it does NOT send a literal "PONG"); the receive loop
# discards both forms.
PING_INTERVAL_SECONDS = 20

# Market-relative whale rule: a fill also counts as a whale when it is at least
# this fraction of the market's own 24h volume, however small in dollar terms.
# 1% of a day's flow is a real footprint in a thin book.
RELATIVE_WHALE_FRACTION = 0.01

# ...but never below this in absolute dollars. Without a floor, a dead market
# doing $50/day makes any 50-cent fill a "whale" -- 1% of nearly nothing is
# nearly nothing, and the alert stream fills with dust.
RELATIVE_WHALE_MIN_USD = 250.0

# Field names a caller may use to attach Gamma 24h volume to a trade payload.
# Raw RTDS frames carry none of these -- the join has to be done upstream.
MARKET_VOLUME_KEYS = ("market_volume_24h", "volume24hr", "marketVolume24hr", "volume_24h")

# --- Gamma market-volume cache -------------------------------------------
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
GAMMA_MARKETS_URL = f"{GAMMA_API_BASE}/markets"
# Gamma silently caps /markets at 100 rows per request regardless of `limit`,
# so reaching VOLUME_CACHE_MARKET_LIMIT means paginating with `offset`.
GAMMA_PAGE_SIZE = 100
VOLUME_CACHE_MARKET_LIMIT = 500
VOLUME_CACHE_REFRESH_SECONDS = 60


def init_database(db_path: Path = DB_PATH):
    """Initialize SQLite database tables for whale trades and tracked wallets."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS whale_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_hash TEXT UNIQUE,
            timestamp INTEGER,
            wallet TEXT,
            pseudonym TEXT,
            market_title TEXT,
            market_slug TEXT,
            outcome TEXT,
            side TEXT,
            price REAL,
            size REAL,
            usd_notional REAL,
            condition_id TEXT,
            asset TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_whale_trades_ts ON whale_trades(timestamp DESC)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_whale_trades_wallet ON whale_trades(wallet)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_whale_trades_usd ON whale_trades(usd_notional DESC)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tracked_wallets (
            wallet TEXT PRIMARY KEY,
            pseudonym TEXT,
            first_seen INTEGER,
            last_seen INTEGER,
            trade_count INTEGER DEFAULT 1,
            total_volume_usd REAL DEFAULT 0.0,
            last_scanned TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sharp_traders (
            wallet TEXT PRIMARY KEY,
            pseudonym TEXT,
            pnl_7d REAL,
            volume_7d REAL,
            trades_7d INTEGER,
            win_rate REAL,
            is_sharp BOOLEAN DEFAULT 1,
            polymarket_link TEXT,
            last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def normalize_wallet(wallet: str) -> str:
    """
    Canonicalise a wallet address to lowercase.

    Ethereum addresses are case-insensitive -- mixed case is only an EIP-55
    checksum. The REST /trades feed returns them lowercased while the RTDS
    socket returns them checksummed, so without this the SAME trader lands in
    the DB twice under two primary keys and is double-counted on the leaderboard.
    """
    return (wallet or "").strip().lower()


class GammaVolumeCache:
    """
    conditionId -> 24h volume, refreshed in the background from Gamma.

    RTDS trade frames carry no volume field, so the market-relative whale rule
    has nothing to work with until that figure is joined on. This cache does the
    join: it periodically snapshots the busiest active markets from Gamma and
    hands back a volume for any conditionId it has seen.

    COVERAGE NOTE: markets are pulled in descending 24h volume, so the cache
    holds the top `limit` markets and not the long thin tail. That is the right
    trade-off here -- with a $250 floor the relative rule can only ever fire on
    markets doing <= $25k/day (below that, $250 is already >= 1%), and 500
    markets currently reaches down to roughly $8k/day, comfortably covering the
    band where the rule does anything. Markets thinner than that fall back to
    the absolute threshold, which is the safe direction to fail.

    Thread-safe: refreshes build a new dict and swap it in under a lock, so
    readers never observe a half-populated map.
    """

    def __init__(
        self,
        limit: int = VOLUME_CACHE_MARKET_LIMIT,
        refresh_seconds: float = VOLUME_CACHE_REFRESH_SECONDS,
        page_size: int = GAMMA_PAGE_SIZE,
        timeout: int = 15,
    ):
        self.limit = limit
        self.refresh_seconds = refresh_seconds
        self.page_size = page_size
        self.timeout = timeout
        self._volumes: dict = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_refresh_at: Optional[float] = None
        self.last_error: Optional[str] = None

    # -- reads --------------------------------------------------------------
    def __len__(self) -> int:
        with self._lock:
            return len(self._volumes)

    def get(self, condition_id: Optional[str]) -> Optional[float]:
        """24h volume for a conditionId, or None when it is not cached."""
        if not condition_id:
            return None
        with self._lock:
            return self._volumes.get(str(condition_id).lower())

    def volume_for_trade(self, trade: dict) -> Optional[float]:
        """
        Resolve a trade's market volume: whatever the payload already carries
        wins, otherwise look the conditionId up in the cache.
        """
        inline = extract_market_volume_24h(trade)
        if inline is not None:
            return inline
        return self.get(trade.get("conditionId") or trade.get("condition_id"))

    # -- refresh ------------------------------------------------------------
    def fetch_market_volumes(self) -> dict:
        """
        Page through Gamma's active markets, busiest first, and build a fresh
        conditionId -> volume24hr map. Returns {} on total failure so a bad
        refresh never wipes the cache.
        """
        headers = {"User-Agent": "Polymarket-Monarch-VolumeCache/1.0", "Accept": "application/json"}
        volumes: dict = {}
        offset = 0

        while len(volumes) < self.limit:
            params = {
                "active": "true",
                "closed": "false",
                "limit": self.page_size,
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            }
            try:
                resp = requests.get(GAMMA_MARKETS_URL, headers=headers, params=params, timeout=self.timeout)
                if resp.status_code != 200:
                    self.last_error = f"HTTP {resp.status_code}"
                    break
                page = resp.json()
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
                break

            if isinstance(page, dict):
                page = page.get("data", [])
            if not isinstance(page, list) or not page:
                break

            for market in page:
                if not isinstance(market, dict):
                    continue
                condition_id = market.get("conditionId")
                raw_volume = market.get("volume24hr")
                if not condition_id or raw_volume is None:
                    continue
                try:
                    volume = float(raw_volume)
                except (TypeError, ValueError):
                    continue
                if volume > 0:
                    volumes[str(condition_id).lower()] = volume

            if len(page) < self.page_size:
                break  # last page
            offset += self.page_size

        return volumes

    def refresh(self) -> int:
        """Pull a fresh snapshot. Returns the number of markets now cached."""
        volumes = self.fetch_market_volumes()
        if volumes:
            with self._lock:
                self._volumes = volumes
            self.last_refresh_at = time.time()
            self.last_error = None
        return len(self)

    # -- background thread --------------------------------------------------
    def _loop(self):
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
            self._stop.wait(self.refresh_seconds)

    def start(self, refresh_now: bool = True):
        """Start refreshing in a daemon thread. Idempotent."""
        if refresh_now:
            self.refresh()
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="gamma-volume-cache")
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()


def extract_market_volume_24h(trade: dict) -> Optional[float]:
    """
    Pull the market's 24h volume off a trade payload, if the feed carried one.

    Raw RTDS frames do NOT include this -- it has to be joined on from Gamma by
    an enriching caller (see MARKET_VOLUME_KEYS for the accepted field names).
    Returns None when no usable figure is present, which disables the
    market-relative rule for that trade rather than guessing.
    """
    for key in MARKET_VOLUME_KEYS:
        if key in trade and trade[key] is not None:
            try:
                vol = float(trade[key])
            except (TypeError, ValueError):
                continue
            if vol > 0:
                return vol
    return None


def is_whale_trade(
    usd_notional: float,
    min_usd: float = 1000.0,
    market_volume_24h: Optional[float] = None,
    relative_fraction: float = RELATIVE_WHALE_FRACTION,
    relative_min_usd: float = RELATIVE_WHALE_MIN_USD,
) -> bool:
    """
    Decide whether a fill counts as a whale.

    Two independent triggers, OR'd together:

      1. ABSOLUTE  -- usd_notional >= min_usd (default $1,000).
      2. RELATIVE  -- usd_notional >= relative_min_usd ($250 floor)
                      AND usd_notional >= relative_fraction * market_volume_24h.

    The relative rule exists because $1,000 means very different things in
    different books: a $300 fill in a market doing $5k/day is 6% of the entire
    day's flow and moves the price, while the same $300 in the $2.3M Fed market
    is noise. Rule 2 catches the significant small fills a flat threshold misses.

    The $250 floor is what stops rule 2 collapsing into nonsense at the bottom
    of the book: in a dead market doing $50/day, 1% is 50 cents, and without a
    floor every dust trade would raise a whale alert.

    Being an OR, rule 2 can only ever ADD whales -- it never removes one that
    rule 1 already caught. Falls back to rule 1 alone when no volume is known.
    """
    if usd_notional >= min_usd:
        return True
    if market_volume_24h and market_volume_24h > 0 and relative_fraction > 0:
        return (
            usd_notional >= relative_min_usd
            and usd_notional >= relative_fraction * market_volume_24h
        )
    return False


def save_trade(
    trade: dict,
    min_usd: float = 1000.0,
    db_path: Path = DB_PATH,
    market_volume_24h: Optional[float] = None,
    relative_fraction: float = RELATIVE_WHALE_FRACTION,
    relative_min_usd: float = RELATIVE_WHALE_MIN_USD,
    volume_cache: Optional["GammaVolumeCache"] = None,
) -> bool:
    """
    Process trade, update tracked_wallets, and store it if it qualifies as a
    whale under either the absolute or the market-relative rule.

    `market_volume_24h` overrides whatever the payload carries, so a caller that
    already has Gamma volume cached can pass it in directly.

    Returns True if saved as a NEW whale trade (False if already stored).
    """
    tx_hash = trade.get("transactionHash") or trade.get("tx_hash") or ""
    wallet = normalize_wallet(trade.get("proxyWallet") or trade.get("wallet") or "")
    pseudonym = trade.get("pseudonym") or trade.get("name") or "Anonymous"
    market_title = trade.get("title") or trade.get("market_title") or "Unknown Market"
    market_slug = trade.get("slug") or trade.get("market_slug") or trade.get("eventSlug") or ""
    outcome = trade.get("outcome") or "Yes"
    side = (trade.get("side") or "BUY").upper()
    condition_id = trade.get("conditionId") or ""
    asset = trade.get("asset") or ""

    try:
        price = float(trade.get("price", 0.0))
        size = float(trade.get("size", 0.0))
    except (ValueError, TypeError):
        price = 0.0
        size = 0.0

    usd_notional = float(trade.get("usd_amount") or (price * size))

    ts = trade.get("timestamp") or trade.get("ts")
    if not ts:
        ts = int(time.time())
    else:
        ts = int(ts)

    # If missing tx_hash, generate a deterministic key
    if not tx_hash:
        tx_hash = f"synth_{ts}_{wallet}_{size:.2f}_{price:.4f}"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Track wallet regardless of fill size (useful for PnL scanner pool)
    if wallet:
        cur.execute("""
            INSERT INTO tracked_wallets (wallet, pseudonym, first_seen, last_seen, trade_count, total_volume_usd)
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                pseudonym = CASE WHEN excluded.pseudonym != 'Anonymous' THEN excluded.pseudonym ELSE tracked_wallets.pseudonym END,
                last_seen = excluded.last_seen,
                trade_count = tracked_wallets.trade_count + 1,
                total_volume_usd = tracked_wallets.total_volume_usd + excluded.total_volume_usd
        """, (wallet, pseudonym, ts, ts, usd_notional))

    # Absolute threshold OR market-relative significance (see is_whale_trade).
    # Volume resolution order: explicit argument > payload field > Gamma cache.
    if market_volume_24h is None:
        if volume_cache is not None:
            market_volume_24h = volume_cache.volume_for_trade(trade)
        else:
            market_volume_24h = extract_market_volume_24h(trade)

    is_whale = False
    if is_whale_trade(usd_notional, min_usd, market_volume_24h,
                      relative_fraction, relative_min_usd):
        try:
            cur.execute("""
                INSERT OR IGNORE INTO whale_trades 
                (tx_hash, timestamp, wallet, pseudonym, market_title, market_slug, outcome, side, price, size, usd_notional, condition_id, asset)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx_hash, ts, wallet, pseudonym, market_title, market_slug, outcome, side, price, size, usd_notional, condition_id, asset))
            
            if cur.rowcount > 0:
                is_whale = True
        except Exception as e:
            console.print(f"[dim red]DB insert error: {e}[/dim red]")

    conn.commit()
    conn.close()
    return is_whale


def format_wallet_short(wallet: str) -> str:
    """Shorten wallet address for display."""
    if not wallet or len(wallet) < 10:
        return wallet or "Unknown"
    return f"{wallet[:6]}...{wallet[-4:]}"


def print_whale_alert(
    trade: dict,
    market_volume_24h: Optional[float] = None,
    min_usd: float = 1000.0,
):
    """
    Print formatted rich whale alert card to console.

    When the fill qualified only on the market-relative rule, the card says so
    and shows the share of the day's volume -- otherwise a $300 "whale" looks
    like a bug rather than a deliberate signal.
    """
    ts = trade.get("timestamp") or trade.get("ts") or time.time()
    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%H:%M:%S UTC")

    market_title = trade.get("title") or trade.get("market_title") or "Unknown Market"
    outcome = trade.get("outcome") or "Yes"
    side = (trade.get("side") or "BUY").upper()
    price = float(trade.get("price", 0.0))
    size = float(trade.get("size", 0.0))
    usd = float(trade.get("usd_amount") or (price * size))
    wallet = trade.get("proxyWallet") or trade.get("wallet") or ""
    pseudonym = trade.get("pseudonym") or trade.get("name") or "Anonymous"
    tx_hash = trade.get("transactionHash") or trade.get("tx_hash") or ""
    slug = trade.get("slug") or trade.get("market_slug") or ""

    if side == "BUY":
        side_style = "bold white on green"
        side_icon = "🟢 BUY "
    else:
        side_style = "bold white on red"
        side_icon = "🔴 SELL"

    # Did this clear the dollar bar, or only the market-relative one?
    relative_only = usd < min_usd and bool(market_volume_24h)
    volume_share = (usd / market_volume_24h * 100.0) if market_volume_24h else None

    if usd >= 50_000:
        badge_text = f" 🚨 MEGA WHALE: ${usd:,.2f} "
        badge_style = "bold bright_white on dark_magenta"
    elif usd >= 10_000:
        badge_text = f" ⚡ MAJOR WHALE: ${usd:,.2f} "
        badge_style = "bold bright_yellow on dark_blue"
    elif relative_only:
        badge_text = f" 🎯 THIN-MARKET WHALE: ${usd:,.2f} ({volume_share:.1f}% of 24h vol) "
        badge_style = "bold bright_white on dark_cyan"
    else:
        badge_text = f" 🐋 ${usd:,.2f} "
        badge_style = "bold bright_green"

    short_w = format_wallet_short(wallet)
    poly_url = f"https://polymarket.com/profile/{wallet}" if wallet else ""

    card = Text()
    card.append(f"[{dt}] ", style="dim")
    card.append(f"{side_icon} ", style=side_style)
    card.append(f"  {outcome}  ", style="bold yellow")
    card.append(f"@ ${price:.3f}  ", style="bold white")
    card.append(f"(Size: {size:,.0f} shares)  ", style="dim")
    card.append("-> ")
    card.append(badge_text, style=badge_style)
    card.append("\n")
    card.append("   Market: ", style="bold cyan")
    card.append(f"{market_title}\n", style="bold white")
    card.append("   Trader: ", style="dim")
    card.append(f"{pseudonym} ({short_w})", style="bold cyan")
    if tx_hash:
        card.append("  |  Tx: ", style="dim")
        card.append(f"{tx_hash[:10]}...{tx_hash[-6:]}", style="dim")
    if poly_url:
        card.append(f"\n   Profile: {poly_url}", style="underline dim blue")

    console.print(Panel(card, border_style="green" if side == "BUY" else "red", padding=(0, 1)))


def backfill_recent_trades(min_usd: float = 1000.0, limit: int = 100, db_path: Path = DB_PATH) -> int:
    """
    Backfill recent trades from Polymarket's free public REST Data API.
    """
    console.print(f"[bold cyan]Backfilling last {limit} trades from Polymarket Public Data API...[/bold cyan]")
    headers = {"User-Agent": "Polymarket-Monarch-Collector/1.0", "Accept": "application/json"}
    params = {"limit": limit}

    try:
        resp = requests.get(REST_TRADES_URL, headers=headers, params=params, timeout=12)
        resp.raise_for_status()
        trades = resp.json()
        saved_count = 0
        whale_count = 0

        # Sort chronological
        trades_sorted = sorted(trades, key=lambda x: x.get("timestamp", 0))
        for t in trades_sorted:
            is_whale = save_trade(t, min_usd=min_usd, db_path=db_path)
            if is_whale:
                whale_count += 1
            saved_count += 1

        console.print(f"[green]✓ Ingested {saved_count} public trades ({whale_count} whales >= ${min_usd:,.0f} stored in DB).[/green]")
        return whale_count
    except Exception as e:
        console.print(f"[yellow]Backfill warning (REST): {e}[/yellow]")
        return 0


async def ws_keepalive(ws, interval: float = PING_INTERVAL_SECONDS):
    """
    Application-level keepalive.

    Cloudflare terminates RTDS sockets that look idle, which shows up as a silent
    ConnectionClosed a minute or two into a quiet market. Sending a "PING" frame
    every `interval` seconds keeps the edge from reaping the connection.

    Verified against the live socket: the server acknowledges with an EMPTY text
    frame, not a literal "PONG" (it accepts "PING", "ping" and {"action":"ping"}
    alike and keeps the connection open for all three). The receive loop's
    `if not msg or msg == "PONG"` guard already discards both forms.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await ws.send("PING")
        except Exception:
            # Socket is going down; let the receive loop own the reconnect.
            return


async def stream_websocket_trades(
    min_usd: float = 1000.0,
    max_trades: int = 0,
    db_path: Path = DB_PATH,
    volume_cache: Optional[GammaVolumeCache] = None,
):
    """
    Connect to Polymarket RTDS WebSocket, listen to live trades, and store whales.

    `volume_cache`, when supplied, joins Gamma 24h volume onto each frame by
    conditionId so the market-relative whale rule can fire.
    """
    reconnect_delay = 2
    trade_counter = 0

    while True:
        keepalive_task = None
        try:
            console.print(f"[bold cyan]Connecting to Polymarket RTDS WebSocket ({WS_URL})...[/bold cyan]")
            async with websockets.connect(WS_URL, open_timeout=10, ping_interval=20, ping_timeout=20) as ws:
                # Send trade activity subscription
                sub_payload = {
                    "action": "subscribe",
                    "subscriptions": [
                        {
                            "topic": "activity",
                            "type": "trades"
                        }
                    ]
                }
                await ws.send(json.dumps(sub_payload))
                console.print("[bold green]✓ Subscribed to real-time Polymarket trade activity stream![/bold green]")
                console.print(f"[dim]Keepalive: sending PING every {PING_INTERVAL_SECONDS}s to defeat Cloudflare idle timeouts.[/dim]")
                reconnect_delay = 2

                keepalive_task = asyncio.create_task(ws_keepalive(ws, PING_INTERVAL_SECONDS))

                while True:
                    msg = await ws.recv()
                    if not msg or msg == "PONG":
                        continue

                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError:
                        continue

                    payload = data.get("payload")
                    if not payload or not isinstance(payload, dict):
                        continue

                    market_volume = volume_cache.volume_for_trade(payload) if volume_cache else None
                    is_whale = save_trade(
                        payload, min_usd=min_usd, db_path=db_path,
                        market_volume_24h=market_volume,
                    )
                    if is_whale:
                        print_whale_alert(payload, market_volume_24h=market_volume, min_usd=min_usd)

                    trade_counter += 1
                    if max_trades > 0 and trade_counter >= max_trades:
                        console.print(f"[yellow]Reached max test trades ({max_trades}). Exiting stream.[/yellow]")
                        return

        except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError, OSError) as e:
            console.print(f"[yellow]WebSocket connection lost ({e}). Reconnecting in {reconnect_delay}s...[/yellow]")
            # While reconnecting, fetch missing fills via REST
            backfill_recent_trades(min_usd=min_usd, limit=20, db_path=db_path)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)
        except Exception as e:
            console.print(f"[bold red]Unexpected stream error:[/bold red] {e}")
            await asyncio.sleep(5)
        finally:
            if keepalive_task is not None:
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except (asyncio.CancelledError, Exception):
                    pass


def load_fixture_frames(fixture_path: Path = SAMPLE_TRADES_PATH) -> list:
    """
    Load recorded RTDS frames from a JSON fixture for offline replay.

    Accepts either the documented wrapper form ({"frames": [...]}) or a bare
    list, and tolerates entries that are raw trade payloads rather than full
    {topic, type, payload} envelopes.
    """
    fixture_path = Path(fixture_path)
    if not fixture_path.exists():
        raise FileNotFoundError(f"Replay fixture not found: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)

    if isinstance(doc, dict):
        frames = doc.get("frames", [])
    elif isinstance(doc, list):
        frames = doc
    else:
        frames = []

    payloads = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        payload = frame.get("payload")
        if isinstance(payload, dict):
            payloads.append(payload)
        elif "price" in frame and "size" in frame:
            payloads.append(frame)  # bare payload, no envelope
    return payloads


def replay_fixture(
    fixture_path: Path = SAMPLE_TRADES_PATH,
    min_usd: float = 1000.0,
    delay: float = 0.0,
    db_path: Path = REPLAY_DB_PATH,
    quiet: bool = False,
) -> dict:
    """
    Replay recorded whale frames through the exact same save/alert path the live
    socket uses. Fully offline: no network, no API keys, instant.

    Returns {"frames", "whales", "stored", "skipped"} where `whales` counts every
    fill in the fixture at or above the threshold and `stored` counts only those
    newly written to the DB. The two differ on a repeat replay, because tx_hash
    is unique -- reporting only `stored` would misleadingly read as "0 whales".
    """
    payloads = load_fixture_frames(fixture_path)
    init_database(db_path)

    whales = 0
    stored = 0
    for payload in payloads:
        try:
            notional = float(payload.get("price") or 0.0) * float(payload.get("size") or 0.0)
        except (TypeError, ValueError):
            notional = 0.0
        # Same predicate the live path uses, so replay counts match production.
        is_whale = is_whale_trade(notional, min_usd, extract_market_volume_24h(payload))

        if save_trade(payload, min_usd=min_usd, db_path=db_path):
            stored += 1
            if not quiet:
                print_whale_alert(payload)
        if is_whale:
            whales += 1
        if delay:
            time.sleep(delay)

    summary = {
        "frames": len(payloads),
        "whales": whales,
        "stored": stored,
        "skipped": len(payloads) - whales,
    }
    if not quiet:
        already = summary["whales"] - summary["stored"]
        console.print(Panel(
            Text.assemble(
                ("REPLAY COMPLETE\n", "bold green"),
                (f"Fixture: {Path(fixture_path).name}\n", "cyan"),
                (f"Frames replayed: {summary['frames']}\n", "white"),
                (f"Whale fills (>= ${min_usd:,.0f}): {summary['whales']}\n", "bold yellow"),
                (f"Newly stored: {summary['stored']}"
                 + (f"  ({already} already in DB)\n" if already else "\n"), "green"),
                (f"Below threshold: {summary['skipped']}\n", "dim"),
                (f"Written to: {Path(db_path).name}", "dim"),
            ),
            border_style="green",
            padding=(0, 1),
        ))
    return summary



def print_banner(min_usd: float, db_path: Path = DB_PATH):
    """Print welcome header banner."""
    txt = Text()
    txt.append("👑 POLYMARKET MONARCH - 100% FREE NATIVE WHALE COLLECTOR\n", style="bold green")
    txt.append("Real-Time Public WebSocket Stream  |  ", style="bold white")
    txt.append(f"Whale Filter: >= ${min_usd:,.0f} USD  |  ", style="bold yellow")
    txt.append(f"Storage: SQLite ({Path(db_path).name})\n", style="bold cyan")
    txt.append(
        f"...or >= {RELATIVE_WHALE_FRACTION:.0%} of a market's 24h volume "
        "(when volume data is attached)\n",
        style="bold yellow",
    )
    txt.append("No API Keys Required  |  Direct Polymarket RTDS Feed", style="dim")
    console.print(Panel(txt, border_style="green", padding=(1, 2)))


def main():
    parser = argparse.ArgumentParser(description="Polymarket Monarch Whale Collector")
    parser.add_argument("--min-usd", type=float, default=1000.0, help="Minimum USD whale threshold (default: 1000.0)")
    parser.add_argument("--test", action="store_true", help="Run in test mode for 5 trades and exit")
    parser.add_argument("--backfill-only", action="store_true", help="Only backfill recent trades from REST API and exit")
    parser.add_argument("--replay", action="store_true",
                        help="Offline mode: replay recorded whale frames from a fixture instead of connecting to the network")
    parser.add_argument("--replay-file", type=str, default=str(SAMPLE_TRADES_PATH),
                        help=f"Fixture to replay (default: {SAMPLE_TRADES_PATH.name})")
    parser.add_argument("--replay-delay", type=float, default=0.0,
                        help="Seconds to pause between replayed frames, to simulate live pacing (default: 0.0)")
    parser.add_argument("--db", type=str, default=None,
                        help="Override the SQLite DB path (replay defaults to replay_whales.db to keep live data clean)")
    parser.add_argument("--no-volume-cache", action="store_true",
                        help="Disable the Gamma 24h-volume cache, leaving only the absolute USD whale threshold")
    parser.add_argument("--volume-cache-limit", type=int, default=VOLUME_CACHE_MARKET_LIMIT,
                        help=f"How many markets to keep volume for, busiest first (default: {VOLUME_CACHE_MARKET_LIMIT})")

    args = parser.parse_args()

    console.clear()

    if args.replay:
        db_path = Path(args.db) if args.db else REPLAY_DB_PATH
        print_banner(args.min_usd, db_path)
        console.print(f"[bold magenta]OFFLINE REPLAY MODE - no network calls will be made.[/bold magenta]")
        try:
            replay_fixture(
                fixture_path=Path(args.replay_file),
                min_usd=args.min_usd,
                delay=args.replay_delay,
                db_path=db_path,
            )
        except FileNotFoundError as e:
            console.print(f"[bold red]{e}[/bold red]")
            sys.exit(1)
        return

    db_path = Path(args.db) if args.db else DB_PATH
    init_database(db_path)
    print_banner(args.min_usd, db_path)

    # Initial backfill to populate baseline
    backfill_recent_trades(min_usd=args.min_usd, limit=50, db_path=db_path)

    if args.backfill_only:
        console.print("[green]Backfill complete. Exiting.[/green]")
        return

    volume_cache = None
    if not args.no_volume_cache:
        console.print("[cyan]Priming Gamma 24h-volume cache (enables thin-market whale detection)...[/cyan]")
        volume_cache = GammaVolumeCache(limit=args.volume_cache_limit)
        loaded = volume_cache.start().__len__()
        if loaded:
            console.print(
                f"[green]✓ Volume cache primed: {loaded} markets, refreshing every "
                f"{VOLUME_CACHE_REFRESH_SECONDS}s.[/green]"
            )
        else:
            console.print(
                f"[yellow]Volume cache empty ({volume_cache.last_error or 'no data'}); "
                "falling back to the absolute threshold only.[/yellow]"
            )

    max_trades = 5 if args.test else 0
    try:
        asyncio.run(stream_websocket_trades(
            min_usd=args.min_usd, max_trades=max_trades, db_path=db_path,
            volume_cache=volume_cache,
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Whale collector stopped by user.[/yellow]")
    finally:
        if volume_cache is not None:
            volume_cache.stop()


if __name__ == "__main__":
    main()
