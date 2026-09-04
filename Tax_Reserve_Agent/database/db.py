"""
SQLite Database manager and schema initialization for Tax Reserve Agent.
"""
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "tax_ledger.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,                  -- 'polymarket', 'spot', 'options', 'manual'
    tx_hash TEXT,                          -- on-chain hash or exchange order id
    timestamp TEXT NOT NULL,               -- ISO-8601 string
    asset_class TEXT NOT NULL,             -- 'prediction_market', 'crypto_spot', 'option'
    symbol TEXT NOT NULL,                  -- 'TRUMP-YES', 'ETH/USDC', 'BTC-100k-CALL'
    side TEXT NOT NULL,                    -- 'BUY', 'SELL', 'SPLIT', 'MERGE', 'REDEEM', 'OPTION_EXPIRE', etc.
    quantity REAL NOT NULL,                -- Amount of shares/coins/contracts
    price REAL NOT NULL,                   -- Price per unit in USD/USDC
    fee REAL DEFAULT 0.0,                  -- Gas or trading fees in USD
    total_value REAL NOT NULL,             -- Total trade value in USD
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, tx_hash, symbol, side) ON CONFLICT IGNORE
);

CREATE TABLE IF NOT EXISTS tax_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER,
    asset_class TEXT NOT NULL,
    symbol TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    original_qty REAL NOT NULL,
    remaining_qty REAL NOT NULL,
    unit_cost_basis REAL NOT NULL,
    total_cost_basis REAL NOT NULL,
    is_closed INTEGER DEFAULT 0,
    FOREIGN KEY(transaction_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS realized_pnl (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    close_transaction_id INTEGER,
    open_lot_id INTEGER,
    asset_class TEXT NOT NULL,
    symbol TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT NOT NULL,
    quantity REAL NOT NULL,
    cost_basis REAL NOT NULL,
    proceeds REAL NOT NULL,
    net_gain_loss REAL NOT NULL,
    holding_period_days INTEGER NOT NULL,
    term TEXT NOT NULL,                     -- 'SHORT_TERM' or 'LONG_TERM'
    tax_year INTEGER NOT NULL,
    FOREIGN KEY(close_transaction_id) REFERENCES transactions(id),
    FOREIGN KEY(open_lot_id) REFERENCES tax_lots(id)
);

CREATE TABLE IF NOT EXISTS agent_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tx_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_lots_symbol ON tax_lots(symbol, is_closed);
CREATE INDEX IF NOT EXISTS idx_pnl_year ON realized_pnl(tax_year);
"""

BUSY_TIMEOUT_MS = 5000

# WAL is a persistent property of the database file, so it only has to take once.
# The flag stops every later connection from re-issuing the pragma and re-warning.
_WAL_CHECKED: set = set()


def _apply_pragmas(conn: sqlite3.Connection, db_path: Path) -> None:
    """
    Makes a connection safe to hold while other processes are also writing.

    The agent is no longer a single CLI: the CSV watcher polls in one process,
    a Monarch scanner reads the ledger through the bankroll hook in another, and
    `chain-sync` may be committing in a third. Under the default rollback journal
    a reader blocks a writer and the writer fails outright with
    "database is locked"; under WAL they proceed concurrently.

      * journal_mode=WAL  - readers never block the writer, writer never blocks
                            readers. Set once and stored in the file itself.
      * busy_timeout      - wait rather than fail when two writers do collide.

    NOT set: `synchronous=NORMAL`, the usual WAL companion. It is a real speed-up
    but it can lose the most recent commits on a power cut. This is a tax ledger
    that is written a few times a day, so the default (FULL) is kept and the
    performance is irrelevant. Do not "optimise" this without a reason.

    WAL is unavailable on some network filesystems, where SQLite silently keeps
    the old journal mode. That is a correctness-neutral fallback - it only costs
    concurrency - so it warns once and carries on rather than refusing to run.
    """
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")

    key = str(db_path)
    if key in _WAL_CHECKED:
        return
    _WAL_CHECKED.add(key)
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        mode = (mode[0] if mode else "").lower()
        if mode not in ("wal", "memory"):
            print(f"[WARN] SQLite kept journal_mode={mode!r} for {db_path} - WAL is "
                  f"unavailable here (network share?). Concurrent access may hit "
                  f"'database is locked'.")
    except sqlite3.Error as e:
        print(f"[WARN] Could not enable WAL on {db_path}: {e}")


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_path or DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    # The Python-level timeout and PRAGMA busy_timeout set the same waiter; both
    # are given so a connection is protected even if the pragma cannot be applied.
    conn = sqlite3.connect(target_path, timeout=BUSY_TIMEOUT_MS / 1000.0)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn, target_path)
    return conn


def set_meta(key: str, value: str, db_path: Optional[Path] = None) -> None:
    """Records a ledger-level fact (e.g. the accounting method its lots were built with)."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO agent_meta (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """, (key, str(value)))
    except sqlite3.Error as e:
        print(f"[WARN] Could not record meta {key!r}: {e}")
    finally:
        conn.close()


def get_meta(key: str, default: Optional[str] = None, db_path: Optional[Path] = None) -> Optional[str]:
    """Reads a ledger-level fact. Returns `default` on a ledger predating agent_meta."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT value FROM agent_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    except sqlite3.Error:
        return default
    finally:
        conn.close()

def init_db(db_path: Optional[Path] = None) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
