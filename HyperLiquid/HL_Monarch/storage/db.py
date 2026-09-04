"""
SQLite Database Connection and Schema Management for HL_Monarch.
Uses Write-Ahead Logging (WAL) for high-concurrency real-time reads & writes.
"""
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Tuple
from config.settings import DB_PATH, WAL_AUTOCHECKPOINT_PAGES

logger = logging.getLogger("Storage")

SCHEMA_SQL = """
-- Asset metadata
CREATE TABLE IF NOT EXISTS assets (
    coin TEXT PRIMARY KEY,
    dex TEXT NOT NULL,
    sz_decimals INTEGER NOT NULL,
    max_leverage INTEGER,
    only_isolated BOOLEAN DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Real-time asset snapshots (price, open interest, funding rate, volume)
CREATE TABLE IF NOT EXISTS asset_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    coin TEXT NOT NULL,
    dex TEXT NOT NULL,
    mark_px REAL NOT NULL,
    mid_px REAL,
    oracle_px REAL,
    open_interest REAL NOT NULL,
    notional_oi REAL NOT NULL,
    funding_rate REAL,
    premium REAL,
    day_ntl_vlm REAL,
    FOREIGN KEY(coin) REFERENCES assets(coin)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_coin_time ON asset_snapshots(coin, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_dex_time ON asset_snapshots(dex, timestamp DESC);

-- Materialised "current state", one row per coin.
-- Deriving the latest row per coin from asset_snapshots costs a full scan of the
-- (coin, timestamp) index: the index leads with coin, so a time filter cannot seek
-- and SQLite has no loose index scan. The dashboard asks for this once per frame,
-- so it is kept as a table whose size is bounded by the universe (~436 rows) rather
-- than by history.
CREATE TABLE IF NOT EXISTS latest_snapshots (
    coin TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    dex TEXT NOT NULL,
    mark_px REAL NOT NULL,
    mid_px REAL,
    oracle_px REAL,
    open_interest REAL NOT NULL,
    notional_oi REAL NOT NULL,
    funding_rate REAL,
    premium REAL,
    day_ntl_vlm REAL
);

CREATE INDEX IF NOT EXISTS idx_latest_oi ON latest_snapshots(notional_oi DESC);

-- Real-time trade stream and detected liquidations
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tid INTEGER UNIQUE,
    coin TEXT NOT NULL,
    side TEXT NOT NULL,          -- 'B' (Buy/Long) or 'A' (Ask/Short)
    px REAL NOT NULL,
    sz REAL NOT NULL,
    notional REAL NOT NULL,
    time INTEGER NOT NULL,       -- Unix milliseconds
    hash TEXT,
    is_liquidation BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_trades_coin_time ON trades(coin, time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_is_liq ON trades(is_liquidation, time DESC);

-- Explicit Liquidation & Large Fill Events
CREATE TABLE IF NOT EXISTS liquidation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,
    side TEXT NOT NULL,
    px REAL NOT NULL,
    sz REAL NOT NULL,
    notional REAL NOT NULL,
    time INTEGER NOT NULL,
    source TEXT NOT NULL,        -- 'trade_sweep', 'liquidation_fill', 'block_event'
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_liq_events_coin_time ON liquidation_events(coin, time DESC);

-- Order Book Snapshots & Depth Analysis
CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    coin TEXT NOT NULL,
    best_bid REAL NOT NULL,
    best_ask REAL NOT NULL,
    spread REAL NOT NULL,
    spread_bps REAL NOT NULL,
    bid_depth_1pct REAL NOT NULL,
    ask_depth_1pct REAL NOT NULL,
    bid_depth_total REAL NOT NULL,
    ask_depth_total REAL NOT NULL,
    imbalance_ratio REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ob_coin_time ON orderbook_snapshots(coin, timestamp DESC);

-- Estimated Liquidation Clusters
CREATE TABLE IF NOT EXISTS liquidation_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    coin TEXT NOT NULL,
    side TEXT NOT NULL,          -- 'LONG_LIQ' (below mark) or 'SHORT_LIQ' (above mark)
    leverage INTEGER NOT NULL,
    estimated_px REAL NOT NULL,
    distance_pct REAL NOT NULL,
    estimated_notional REAL NOT NULL,
    risk_level TEXT NOT NULL     -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
);

CREATE INDEX IF NOT EXISTS idx_clusters_coin_time ON liquidation_clusters(coin, timestamp DESC);

-- Self-Growing Whale Discovery Table
CREATE TABLE IF NOT EXISTS whale_wallets (
    address TEXT PRIMARY KEY,
    discovered_at INTEGER NOT NULL,
    first_coin TEXT NOT NULL,
    first_notional REAL NOT NULL,
    total_position_value REAL DEFAULT 0,
    account_value REAL DEFAULT 0,
    is_liquidator BOOLEAN DEFAULT 0,
    last_scanned_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_whale_wallets_discovered ON whale_wallets(discovered_at DESC);

-- Confirmed cross-venue actors: one row per address active on BOTH Hyperliquid
-- perps and Polymarket prediction markets. Keyed by the Hyperliquid address,
-- since that is the identity the rest of this database is organised around.
CREATE TABLE IF NOT EXISTS cross_market_titans (
    hl_address TEXT PRIMARY KEY,
    pm_proxy_wallet TEXT,
    pm_pseudonym TEXT,
    hl_account_value REAL DEFAULT 0,
    hl_position_value REAL DEFAULT 0,
    pm_weighted_volume REAL DEFAULT 0,
    pm_realized_pnl_7d REAL DEFAULT 0,
    conviction_score REAL DEFAULT 0,
    discovery_direction TEXT,       -- 'hl_to_pm' or 'pm_to_hl'
    confirmed_at INTEGER NOT NULL,
    last_verified_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_titans_conviction ON cross_market_titans(conviction_score DESC);
"""

class DatabaseManager:
    """Thread-safe SQLite Database Manager with WAL mode."""
    _instance: Optional['DatabaseManager'] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[Path] = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._db_path = db_path or DB_PATH
                cls._instance._local = threading.local()
                cls._instance.init_db()
            elif db_path is not None and Path(db_path) != cls._instance._db_path:
                # Silently returning the singleton bound to a different file used to
                # send writes somewhere the caller never asked for.
                logger.warning(
                    "DatabaseManager already initialised at %s; ignoring requested path %s",
                    cls._instance._db_path, db_path
                )
            return cls._instance

    @property
    def connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(
                str(self._db_path),
                timeout=30.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode and performance optimizations
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA temp_store = MEMORY;")
            conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
            conn.execute("PRAGMA busy_timeout = 30000;")
            # Cap WAL growth. Long-lived readers (the dashboard polls once a second)
            # block auto-checkpoints, so without this the -wal file grows unbounded.
            conn.execute(f"PRAGMA wal_autocheckpoint = {int(WAL_AUTOCHECKPOINT_PAGES)};")
            self._local.conn = conn
        return self._local.conn

    def init_db(self):
        """Initialize SQLite database schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection as conn:
            conn.executescript(SCHEMA_SQL)

    def checkpoint(self, mode: str = "TRUNCATE") -> Tuple[int, int, int]:
        """
        Force a WAL checkpoint and reclaim the -wal file.

        Returns the raw (busy, wal_pages, checkpointed_pages) triple from SQLite;
        busy == 1 means a reader held the WAL open and it was not fully reclaimed.
        """
        if mode.upper() not in ("PASSIVE", "FULL", "RESTART", "TRUNCATE"):
            raise ValueError(f"Invalid checkpoint mode: {mode}")
        conn = self.connection
        try:
            row = conn.execute(f"PRAGMA wal_checkpoint({mode.upper()});").fetchone()
        except sqlite3.OperationalError as e:
            logger.warning(f"WAL checkpoint skipped: {e}")
            return (1, -1, -1)
        if not row:
            return (0, 0, 0)
        return (int(row[0]), int(row[1]), int(row[2]))

    def vacuum(self):
        """Reclaim free pages left behind by retention pruning."""
        conn = self.connection
        conn.isolation_level = None  # VACUUM cannot run inside a transaction
        try:
            conn.execute("VACUUM;")
        finally:
            conn.isolation_level = ""

    def page_size_bytes(self) -> int:
        """Current on-disk size of the main database file in bytes."""
        conn = self.connection
        pages = conn.execute("PRAGMA page_count;").fetchone()[0]
        size = conn.execute("PRAGMA page_size;").fetchone()[0]
        return int(pages) * int(size)

    def close(self):
        """Close current thread connection."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None
