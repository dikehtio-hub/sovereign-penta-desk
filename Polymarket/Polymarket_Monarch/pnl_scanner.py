"""
================================================================================
Polymarket Monarch: 100% Free & Native 7-Day PnL & Sharp Trader Scanner
================================================================================
Scans active prediction market wallets discovered by whale_collector or public feeds,
queries Polymarket's free public Data API to compute 7-day realized and unrealized PnL,
and surfaces sharp traders ($300+ 7-day PnL).

Stores sharp traders in SQLite (data/polymarket_whales.db) for the live dashboard.
Zero API keys or paid proxies required.
================================================================================
"""

import os
import sys
import time
import json
import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

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
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich import box

console = Console()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "polymarket_whales.db"

DATA_API_BASE = "https://data-api.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
HEADERS = {
    "User-Agent": "Polymarket-Monarch-PnL-Scanner/1.0",
    "Accept": "application/json"
}

# The headline PnL figure blends two different periods and must never be
# presented as a clean 7-day number:
#   * realized  -> positions that RESOLVED in the last 7 days (truly 7d)
#   * unrealized-> mark-to-market on positions still OPEN, which the API reports
#                  without a timestamp, so it is lifetime-to-date on live
#                  exposure and cannot be windowed
# A wallet holding a year-old open bet therefore carries that whole position's
# drift inside its "7D" row. Hence "Est. PnL" everywhere, plus this note.
PNL_BASIS_NOTE = (
    "Ranked by 7D Realized (profit actually banked this week). "
    "Est. PnL = 7D Realized + Open Unrealized, and open positions carry no "
    "timestamp, so that second half is lifetime-to-date, not 7d. "
    "ROI% = 7D Realized / 7D Volume. Win% shows — when nothing resolved "
    "in the window (no settled positions to score, which is not a 0% record)."
)

# Ceiling on /activity paging per wallet. A wallet that reaches it has more
# fills than we fetched, so its volume_7d is a PARTIAL sum -- see
# `volume_is_partial`, which suppresses ROI for those rows rather than
# reporting a ratio with a truncated denominator.
ACTIVITY_MAX_RECORDS = 500

# Cloudflare fronts the public Data API and starts returning 429 when requests
# arrive back-to-back. Every outbound call goes through _rate_limited_get(),
# which guarantees at least this gap between any two requests process-wide.
REQUEST_INTERVAL_SECONDS = 0.2
MAX_RETRIES = 3
_last_request_at = 0.0


def _rate_limited_get(url: str, params: Optional[Dict] = None, timeout: int = 10) -> Optional[requests.Response]:
    """
    GET the public Data API with a hard 200ms floor between requests, plus
    backoff on Cloudflare 429/5xx throttling.

    Returns the Response on success, or None if every attempt failed.
    """
    global _last_request_at

    for attempt in range(MAX_RETRIES):
        elapsed = time.time() - _last_request_at
        if elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)

        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            _last_request_at = time.time()
        except Exception:
            _last_request_at = time.time()
            time.sleep(REQUEST_INTERVAL_SECONDS * (2 ** attempt))
            continue

        if resp.status_code == 200:
            return resp

        if resp.status_code == 429 or resp.status_code >= 500:
            # Honour Retry-After when Cloudflare sends it, else exponential backoff.
            retry_after = resp.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else REQUEST_INTERVAL_SECONDS * (2 ** (attempt + 1))
            except (TypeError, ValueError):
                wait = REQUEST_INTERVAL_SECONDS * (2 ** (attempt + 1))
            time.sleep(min(wait, 10.0))
            continue

        # 4xx that is not a throttle (bad wallet, etc.) - no point retrying.
        return None

    return None


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Get SQLite database connection.

    DB_PATH is resolved at call time rather than baked into the default, so the
    target database can be redirected (tests, alternate data dirs).
    """
    conn = sqlite3.connect(db_path if db_path is not None else DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_pnl_tables(db_path: Path = DB_PATH):
    """Ensure sharp_traders and tracked_wallets tables exist."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
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

    # Migration: split the single pnl_7d figure into its realized / unrealized
    # components. Existing databases are upgraded in place.
    existing = {row[1] for row in cur.execute("PRAGMA table_info(sharp_traders)")}
    for column, ddl in [
        ("realized_pnl_7d", "REAL DEFAULT 0.0"),
        ("unrealized_pnl", "REAL DEFAULT 0.0"),
        ("open_positions", "INTEGER DEFAULT 0"),
        # Needed to tell "no positions resolved this week" apart from "resolved
        # several and lost every one" -- both leave win_rate at 0.0.
        # NULL default, not 0: existing rows genuinely do not know their count,
        # and claiming 0 would render them as an em dash they never earned.
        ("closed_positions_7d", "INTEGER DEFAULT NULL"),
        # 1 when /activity paging hit its cap, so volume_7d is a partial sum
        # and ROI must not be reported for the row.
        ("volume_is_partial", "INTEGER DEFAULT 0"),
        # Identity resolution. Polymarket trades through per-user *proxy wallet*
        # contracts, so `wallet` here may be either the proxy or the signing EOA
        # depending on how the address was discovered. Recording both lets the
        # cross-market scanner match a Hyperliquid EOA against either form.
        # NULL means "not resolved yet", distinct from "resolved to nothing".
        ("proxy_wallet", "TEXT DEFAULT NULL"),
        ("eoa_address", "TEXT DEFAULT NULL"),
        ("identity_resolved_at", "TIMESTAMP DEFAULT NULL"),
    ]:
        if column not in existing:
            cur.execute(f"ALTER TABLE sharp_traders ADD COLUMN {column} {ddl}")
            if column == "volume_is_partial":
                # Backfill: a row whose trade count sits at the paging cap was
                # truncated when it was written, so its volume_7d (and any ROI
                # derived from it) is partial. Without this, pre-existing rows
                # default to 0 and report ROI figures in the thousands of %.
                cur.execute(
                    "UPDATE sharp_traders SET volume_is_partial = 1 WHERE trades_7d >= ?",
                    (ACTIVITY_MAX_RECORDS,),
                )

    conn.commit()
    merge_duplicate_wallet_casings(conn)
    conn.close()


def merge_duplicate_wallet_casings(conn: sqlite3.Connection) -> int:
    """
    Collapse rows that are the same wallet under different address casing.

    The REST feed hands back lowercase addresses and the RTDS socket hands back
    EIP-55 checksummed ones, so before normalisation was added the same trader
    could occupy two rows and appear twice on the leaderboard. Returns the number
    of duplicate rows removed.
    """
    cur = conn.cursor()
    removed = 0

    # sharp_traders: keep the most recently scanned row per lowercase address.
    groups: Dict[str, List[sqlite3.Row]] = {}
    for row in cur.execute("SELECT rowid, wallet, last_scanned FROM sharp_traders").fetchall():
        groups.setdefault((row["wallet"] or "").lower(), []).append(row)
    for lower, rows in groups.items():
        if len(rows) > 1:
            keep = max(rows, key=lambda r: (r["last_scanned"] or ""))
            for r in rows:
                if r["rowid"] != keep["rowid"]:
                    cur.execute("DELETE FROM sharp_traders WHERE rowid = ?", (r["rowid"],))
                    removed += 1
            cur.execute("UPDATE sharp_traders SET wallet = ? WHERE rowid = ?", (lower, keep["rowid"]))
        elif rows[0]["wallet"] != lower:
            cur.execute("UPDATE sharp_traders SET wallet = ? WHERE rowid = ?", (lower, rows[0]["rowid"]))

    # tracked_wallets: the counters are additive, so fold them together.
    groups = {}
    for row in cur.execute(
        "SELECT rowid, wallet, pseudonym, first_seen, last_seen, trade_count, total_volume_usd "
        "FROM tracked_wallets"
    ).fetchall():
        groups.setdefault((row["wallet"] or "").lower(), []).append(row)
    for lower, rows in groups.items():
        if len(rows) > 1:
            keep = rows[0]
            total_trades = sum(r["trade_count"] or 0 for r in rows)
            total_volume = sum(r["total_volume_usd"] or 0.0 for r in rows)
            first_seen = min((r["first_seen"] for r in rows if r["first_seen"]), default=None)
            last_seen = max((r["last_seen"] for r in rows if r["last_seen"]), default=None)
            pseudonym = next(
                (r["pseudonym"] for r in rows if r["pseudonym"] and r["pseudonym"] != "Anonymous"),
                keep["pseudonym"],
            )
            for r in rows[1:]:
                cur.execute("DELETE FROM tracked_wallets WHERE rowid = ?", (r["rowid"],))
                removed += 1
            cur.execute(
                "UPDATE tracked_wallets SET wallet = ?, pseudonym = ?, first_seen = ?, "
                "last_seen = ?, trade_count = ?, total_volume_usd = ? WHERE rowid = ?",
                (lower, pseudonym, first_seen, last_seen, total_trades, total_volume, keep["rowid"]),
            )
        elif rows[0]["wallet"] != lower:
            cur.execute("UPDATE tracked_wallets SET wallet = ? WHERE rowid = ?", (lower, rows[0]["rowid"]))

    conn.commit()
    return removed


def resolve_polymarket_profile(address: str, timeout: int = 10) -> Optional[Dict]:
    """
    Resolve a Polymarket public profile for `address`.

    The Gamma `/public-profile` endpoint returns a `proxyWallet` field and maps
    **EOA -> proxy wallet**: querying a signing EOA returns the proxy contract it
    trades through, while querying a proxy returns that same proxy back. There is
    no reverse (proxy -> EOA) lookup and no `eoa_address` field in the response,
    so `eoa_address` is only populated when we can infer it: if the queried
    address resolves to a *different* proxy, the queried address was the EOA.

    Returns None when the address has no Polymarket profile (the endpoint 404s),
    which is itself informative - it means this address has never traded there.
    """
    addr = normalize_wallet(address)
    if not addr:
        return None

    resp = _rate_limited_get(f"{GAMMA_API_BASE}/public-profile", {"address": addr}, timeout=timeout)
    if resp is None:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    proxy = normalize_wallet(data.get("proxyWallet") or "")
    if not proxy:
        return None

    # A distinct proxy means the address we asked about is the signing EOA.
    eoa = addr if proxy != addr else None

    return {
        "queried": addr,
        "proxy_wallet": proxy,
        "eoa_address": eoa,
        "pseudonym": data.get("pseudonym"),
        "created_at": data.get("createdAt"),
        "weighted_volume": data.get("weightedVolume"),
    }


def resolve_and_store_identity(wallet: str, db_path: Optional[Path] = None) -> Optional[Dict]:
    """Resolve a trader's proxy/EOA pair and persist it onto their sharp_traders row."""
    profile = resolve_polymarket_profile(wallet)
    if not profile:
        return None

    conn = get_db_connection(db_path)
    try:
        conn.execute(
            """
            UPDATE sharp_traders
               SET proxy_wallet = ?,
                   eoa_address = COALESCE(?, eoa_address),
                   identity_resolved_at = CURRENT_TIMESTAMP
             WHERE wallet = ?
            """,
            (profile["proxy_wallet"], profile["eoa_address"], normalize_wallet(wallet)),
        )
        conn.commit()
    finally:
        conn.close()
    return profile


def resolve_pending_identities(limit: int = 25, db_path: Optional[Path] = None) -> int:
    """
    Resolve identities for traders that have never been resolved.

    Bounded per call because every resolution is a network round trip through the
    shared 200ms rate limiter; the scan cycle calls this incrementally.
    """
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT wallet FROM sharp_traders
             WHERE identity_resolved_at IS NULL
             ORDER BY realized_pnl_7d DESC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
        wallets = [r[0] for r in rows]
    finally:
        conn.close()

    resolved = 0
    for w in wallets:
        if resolve_and_store_identity(w, db_path=db_path):
            resolved += 1
    return resolved


def normalize_wallet(wallet: str) -> str:
    """
    Canonicalise a wallet address to lowercase (see whale_collector for the full
    rationale: the REST feed and the RTDS socket disagree on address casing, and
    an un-normalised key stores the same trader twice).
    """
    return (wallet or "").strip().lower()


def _as_list(payload) -> List[dict]:
    """Data API mostly returns bare lists, but tolerate a {'data': [...]} wrapper."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        inner = payload.get("data")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


def fetch_wallet_closed_positions(wallet: str, limit: int = 100) -> List[dict]:
    """
    Fetch closed (resolved) positions -> REALIZED PnL.

    Each row carries `realizedPnl`, `totalBought`, and a `timestamp` marking when
    the position closed, so these can be windowed to the last 7 days.
    """
    resp = _rate_limited_get(f"{DATA_API_BASE}/closed-positions", {"user": wallet, "limit": limit})
    if resp is None:
        return []
    try:
        return _as_list(resp.json())
    except Exception:
        return []


def fetch_wallet_open_positions(wallet: str, limit: int = 100) -> List[dict]:
    """
    Fetch open positions -> UNREALIZED PnL.

    Rows carry `cashPnl` (mark-to-market vs entry), `initialValue`, and
    `currentValue`. Note: open positions have no timestamp, so unrealized PnL is
    lifetime-to-date on live exposure and cannot be windowed to 7 days.
    """
    resp = _rate_limited_get(f"{DATA_API_BASE}/positions", {"user": wallet, "limit": limit})
    if resp is None:
        return []
    try:
        return _as_list(resp.json())
    except Exception:
        return []


def fetch_wallet_activity(wallet: str, limit: int = 100,
                          max_records: int = ACTIVITY_MAX_RECORDS) -> List[dict]:
    """
    Fetch recent activity -> trade count and true traded volume.

    Pages through the endpoint (offset-based) because an active whale can blow
    through `limit` records in well under 7 days, which would silently truncate
    the volume figure.
    """
    records: List[dict] = []
    offset = 0
    while len(records) < max_records:
        resp = _rate_limited_get(
            f"{DATA_API_BASE}/activity",
            {"user": wallet, "limit": limit, "offset": offset},
        )
        if resp is None:
            break
        try:
            page = _as_list(resp.json())
        except Exception:
            break
        if not page:
            break
        records.extend(page)
        if len(page) < limit:
            break  # last page
        offset += limit
    return records[:max_records]


# Shown instead of "0%" when a wallet resolved nothing in the window. An em dash
# is cp1252-encodable, so it survives a legacy Windows console.
NO_DATA_DASH = "—"


def compute_roi(realized_pnl_7d: float, volume_7d: float) -> float:
    """
    7d return on capital actually traded, as a percentage.

    Separates edge from bankroll: banking $5k on $10k of volume (50%) is a very
    different trader from banking $5k on $500k of volume (1%), yet both look
    identical ranked on realized PnL alone.
    """
    if volume_7d and volume_7d > 0:
        return round(realized_pnl_7d / volume_7d * 100.0, 1)
    return 0.0


def format_roi(roi, dash: str = NO_DATA_DASH) -> str:
    """
    Render ROI%, or a dash when it cannot be trusted.

    `None` means the wallet's /activity paging hit its cap, so volume_7d is a
    partial sum -- dividing by it produces figures like +2,576,423%. Very large
    genuine values are abbreviated so they cannot blow the column width open.
    """
    if roi is None:
        return dash
    try:
        roi = float(roi)
    except (TypeError, ValueError):
        return dash
    style = "bold bright_green" if roi > 0 else ("bold red" if roi < 0 else "dim")
    if abs(roi) >= 1000:
        text = f"{roi / 1000:+.0f}k%"
    else:
        text = f"{roi:+.1f}%"
    return f"[{style}]{text}[/{style}]"


def format_win_rate(win_rate, closed_positions, dash: str = NO_DATA_DASH) -> str:
    """
    Render win rate, or a dash when there is nothing to compute it from.

    A wallet holding only open positions resolves nothing, so winning_positions
    and closed_in_window are both 0 and the rate falls out as 0.0. Printing
    "0%" reads as "lost every trade" -- the opposite of "no trades settled yet".
    `None` means the row predates the closed_positions_7d column.
    """
    if closed_positions is None or closed_positions <= 0:
        return dash
    try:
        return f"{float(win_rate):.0f}%"
    except (TypeError, ValueError):
        return dash


def _to_float(val, default: float = 0.0) -> float:
    """Coerce an API field to float without exploding on None/''/garbage."""
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def compute_pnl_metrics(
    wallet: str,
    closed: List[dict],
    open_pos: List[dict],
    activity: List[dict],
    now: Optional[int] = None,
    activity_truncated: bool = False,
) -> Optional[Dict]:
    """
    Pure aggregation step of the PnL engine (no I/O, so it is unit-testable).

    Three independent sources, each used for what it is actually authoritative on:
      * /closed-positions -> REALIZED PnL, windowed to 7d via each row's timestamp
      * /positions        -> UNREALIZED PnL (mark-to-market on live exposure)
      * /activity         -> true traded volume + trade count, windowed to 7d

    `pnl_7d` is the headline number: 7d realized + current unrealized.
    """
    if not closed and not open_pos and not activity:
        return None

    now = int(now if now is not None else time.time())
    seven_days_ago = now - (7 * 24 * 3600)

    # --- 1. Realized PnL from resolved positions inside the 7d window --------
    realized_pnl_7d = 0.0
    winning_positions = 0
    closed_in_window = 0
    for pos in closed:
        pos_ts = pos.get("timestamp")
        # Rows without a timestamp are treated as recent (the API omits it on
        # some legacy rows); rows outside the window are skipped entirely.
        if pos_ts is not None and _to_float(pos_ts) < seven_days_ago:
            continue
        realized = _to_float(pos.get("realizedPnl"))
        realized_pnl_7d += realized
        closed_in_window += 1
        if realized > 0:
            winning_positions += 1

    # --- 2. Unrealized PnL on still-open positions ---------------------------
    # No timestamp is available on open positions, so this is lifetime-to-date
    # on live exposure rather than a strict 7d figure.
    unrealized_pnl = 0.0
    open_exposure = 0.0
    for pos in open_pos:
        cash_pnl = _to_float(pos.get("cashPnl"))
        cur_val = _to_float(pos.get("currentValue"))
        init_val = _to_float(pos.get("initialValue"))

        if cash_pnl:
            unrealized_pnl += cash_pnl
        elif cur_val or init_val:
            unrealized_pnl += (cur_val - init_val)

        open_exposure += cur_val if cur_val > 0 else init_val

    # --- 3. Real traded volume and trade count from activity ----------------
    volume_7d = 0.0
    trades_7d = 0
    for act in activity:
        if _to_float(act.get("timestamp")) < seven_days_ago:
            continue
        # Only actual fills count; REDEEM / SPLIT / MERGE / REWARD are not trades.
        if (act.get("type") or "TRADE").upper() != "TRADE":
            continue
        trades_7d += 1
        volume_7d += _to_float(act.get("usdcSize"))

    # If activity is unavailable, fall back to capital deployed into positions
    # that closed inside the window.
    if volume_7d == 0.0:
        volume_7d = sum(
            _to_float(p.get("totalBought"))
            for p in closed
            if p.get("timestamp") is None or _to_float(p.get("timestamp")) >= seven_days_ago
        )
    if trades_7d == 0 and closed_in_window > 0:
        trades_7d = closed_in_window

    win_rate = (winning_positions / closed_in_window * 100.0) if closed_in_window > 0 else 0.0
    pnl_7d = realized_pnl_7d + unrealized_pnl

    # Pseudonym: prefer the human-readable handle from activity rows.
    pseudonym = "Anonymous"
    for act in activity:
        cand = act.get("pseudonym")
        if cand and cand != "Anonymous":
            pseudonym = cand
            break
        cand = act.get("name")
        if cand and not str(cand).startswith("0x"):
            pseudonym = cand
            break

    return {
        "wallet": wallet,
        "pseudonym": pseudonym,
        "pnl_7d": round(pnl_7d, 2),
        "realized_pnl_7d": round(realized_pnl_7d, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "volume_7d": round(volume_7d, 2),
        "open_exposure": round(open_exposure, 2),
        "trades_7d": trades_7d,
        "open_positions": len(open_pos),
        "closed_positions_7d": closed_in_window,
        "win_rate": round(win_rate, 1),
        # When /activity was truncated, volume_7d is a partial sum and ROI would
        # be wildly overstated -- so it is withheld rather than guessed.
        "volume_is_partial": bool(activity_truncated),
        "roi_7d": None if activity_truncated else compute_roi(realized_pnl_7d, volume_7d),
        "polymarket_link": f"https://polymarket.com/profile/{wallet}"
    }


def calculate_wallet_7d_pnl(wallet: str) -> Optional[Dict]:
    """
    Fetch all three public Data API sources for a wallet and aggregate them into
    7-day realized + unrealized PnL, volume, trade count, and win rate.
    """
    wallet = normalize_wallet(wallet)
    closed = fetch_wallet_closed_positions(wallet, limit=100)
    open_pos = fetch_wallet_open_positions(wallet)
    activity = fetch_wallet_activity(wallet, limit=100, max_records=ACTIVITY_MAX_RECORDS)
    # Hitting the cap means there were more fills we did not fetch, so the
    # volume sum (and any ROI built on it) is incomplete.
    truncated = len(activity) >= ACTIVITY_MAX_RECORDS
    return compute_pnl_metrics(wallet, closed, open_pos, activity, activity_truncated=truncated)


def get_wallets_to_scan(limit: int = 30) -> List[str]:
    """
    Get prioritized list of wallets to scan from SQLite tracked_wallets and whale_trades.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Prioritize wallets that haven't been scanned recently, ordered by volume/activity
    cur.execute("""
        SELECT wallet FROM tracked_wallets
        ORDER BY last_scanned ASC NULLS FIRST, total_volume_usd DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    wallets = [r["wallet"] for r in rows if r["wallet"]]

    # Also grab distinct wallets from whale_trades if needed
    if len(wallets) < limit:
        remaining = limit - len(wallets)
        cur.execute("""
            SELECT DISTINCT wallet FROM whale_trades
            WHERE wallet NOT IN (SELECT wallet FROM sharp_traders)
            LIMIT ?
        """, (remaining,))
        extra = [r["wallet"] for r in cur.fetchall() if r["wallet"]]
        wallets.extend(extra)

    conn.close()
    return list(dict.fromkeys(wallets))  # deduplicate preserving order


def save_sharp_trader(metrics: Dict, min_sharp_pnl: float = 300.0, db_path: Optional[Path] = None):
    """Save or update trader in SQLite database."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    wallet = normalize_wallet(metrics["wallet"])
    # "Sharp" is judged on 7d REALIZED profit, not the blended figure: a wallet
    # sitting on an unrealized paper gain from a months-old open bet has not
    # demonstrated anything this week.
    is_sharp = 1 if metrics.get("realized_pnl_7d", 0.0) >= min_sharp_pnl else 0

    cur.execute("""
        INSERT INTO sharp_traders (wallet, pseudonym, pnl_7d, realized_pnl_7d, unrealized_pnl,
                                   volume_7d, trades_7d, open_positions, closed_positions_7d,
                                   volume_is_partial, win_rate, is_sharp, polymarket_link,
                                   last_scanned)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(wallet) DO UPDATE SET
            pseudonym = excluded.pseudonym,
            pnl_7d = excluded.pnl_7d,
            realized_pnl_7d = excluded.realized_pnl_7d,
            unrealized_pnl = excluded.unrealized_pnl,
            volume_7d = excluded.volume_7d,
            trades_7d = excluded.trades_7d,
            open_positions = excluded.open_positions,
            closed_positions_7d = excluded.closed_positions_7d,
            volume_is_partial = excluded.volume_is_partial,
            win_rate = excluded.win_rate,
            is_sharp = excluded.is_sharp,
            polymarket_link = excluded.polymarket_link,
            last_scanned = CURRENT_TIMESTAMP
    """, (
        wallet,
        metrics["pseudonym"],
        metrics["pnl_7d"],
        metrics.get("realized_pnl_7d", 0.0),
        metrics.get("unrealized_pnl", 0.0),
        metrics["volume_7d"],
        metrics["trades_7d"],
        metrics.get("open_positions", 0),
        metrics.get("closed_positions_7d", 0),
        1 if metrics.get("volume_is_partial") else 0,
        metrics["win_rate"],
        is_sharp,
        metrics["polymarket_link"]
    ))

    cur.execute("""
        UPDATE tracked_wallets SET last_scanned = CURRENT_TIMESTAMP WHERE wallet = ?
    """, (wallet,))

    conn.commit()
    conn.close()


def format_wallet_short(wallet: str) -> str:
    """Shorten wallet address for display."""
    if not wallet or len(wallet) < 10:
        return wallet or "Unknown"
    return f"{wallet[:6]}...{wallet[-4:]}"


def _row_get(row: sqlite3.Row, key: str, default=0.0):
    """Read a column from a sqlite3.Row, tolerating pre-migration databases."""
    try:
        val = row[key]
    except (IndexError, KeyError):
        return default
    return default if val is None else val


# ORDER BY expression per --sort mode. ROI is derived rather than stored, so it
# is computed inline; the CASE guards against divide-by-zero on idle wallets.
SORT_MODES = {
    "realized": "realized_pnl_7d DESC",
    # Rows with a truncated volume denominator sort last -- their ratio is
    # inflated by an incomplete divisor, not by genuine edge.
    "roi": ("COALESCE(volume_is_partial, 0) ASC, "
            "CASE WHEN volume_7d > 0 THEN realized_pnl_7d / volume_7d ELSE 0 END DESC"),
    "volume": "volume_7d DESC",
}


def display_sharp_traders_table(min_pnl: float = 300.0, limit: int = 20, sort_by: str = "realized"):
    """
    Display formatted Rich table of sharp traders from SQLite.

    `sort_by` is one of SORT_MODES. The qualifying filter stays on 7d realized
    whatever the sort -- re-sorting reorders the sharp traders, it does not
    change who counts as one.
    """
    order_by = SORT_MODES.get(sort_by, SORT_MODES["realized"])
    conn = get_db_connection()
    cur = conn.cursor()
    # order_by is looked up from SORT_MODES, never interpolated from user input.
    cur.execute(f"""
        SELECT * FROM sharp_traders
        WHERE realized_pnl_7d >= ?
        ORDER BY {order_by}
        LIMIT ?
    """, (min_pnl, limit))
    rows = cur.fetchall()
    conn.close()

    sort_label = {"realized": "7D Realized", "roi": "ROI%", "volume": "7D Volume"}.get(sort_by, "7D Realized")
    table = Table(
        title=f"👑 Polymarket Monarch - Sharp Money Leaderboard "
              f"(7D Realized >= ${min_pnl:,.0f}, sorted by {sort_label})",
        title_style="bold green",
        caption=PNL_BASIS_NOTE,
        caption_style="dim italic",
        header_style="bold bright_white on dark_green",
        border_style="green",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=False,
        pad_edge=False
    )

    wide = console.width >= 120
    show_roi = console.width >= 136
    show_profile = console.width >= 170

    table.add_column("Rank", justify="center", style="bold yellow", width=4, no_wrap=True)
    table.add_column("Trader", justify="left", style="bold cyan", width=14,
                     no_wrap=True, overflow="ellipsis")
    if wide:
        table.add_column("Wallet", justify="left", style="cyan", width=14, no_wrap=True)
    table.add_column("7D Realized", justify="right", style="bold green", width=12, no_wrap=True)
    table.add_column("Open Unreal.", justify="right", width=12, no_wrap=True)
    if wide:
        table.add_column("Est. PnL", justify="right", width=11, no_wrap=True)
        table.add_column("7D Volume", justify="right", style="bold white", width=10, no_wrap=True)
    table.add_column("Trades", justify="center", style="bold magenta", width=6, no_wrap=True)
    if show_roi:
        table.add_column("ROI%", justify="right", style="bold yellow", width=8, no_wrap=True)
    table.add_column("Win%", justify="center", style="bold cyan", width=5, no_wrap=True)
    if show_profile:
        table.add_column("Polymarket Profile", justify="left", style="underline cyan", width=34,
                         no_wrap=True, overflow="ellipsis")

    def _style_for(val: float) -> str:
        return "bold bright_green" if val > 0 else ("bold red" if val < 0 else "dim")

    def _abbrev(mag: float) -> str:
        if mag >= 1_000_000:
            return f"${mag / 1_000_000:.1f}M"
        if mag >= 1_000:
            return f"${mag / 1_000:.1f}K"
        return f"${mag:,.0f}"

    def money(val: float) -> str:
        """Signed, abbreviated PnL figure."""
        sign = "-" if val < 0 else ("+" if val > 0 else "")
        return f"[{_style_for(val)}]{sign}{_abbrev(abs(val))}[/{_style_for(val)}]"

    def volume_str(val: float) -> str:
        """Volume is never negative, so it carries no sign."""
        return _abbrev(abs(val))

    for rank, r in enumerate(rows, 1):
        wallet = r["wallet"]
        short_w = format_wallet_short(wallet)
        pseudonym = r["pseudonym"] or "Anonymous"
        # Prefer the human handle; fall back to the shortened address.
        trader = pseudonym if pseudonym != "Anonymous" else short_w
        pnl = r["pnl_7d"]
        realized = _row_get(r, "realized_pnl_7d")
        unrealized = _row_get(r, "unrealized_pnl")
        volume = r["volume_7d"]
        trades = r["trades_7d"]
        win_rate = r["win_rate"]
        closed_positions = _row_get(r, "closed_positions_7d", None)
        volume_partial = bool(_row_get(r, "volume_is_partial", 0))
        roi = None if volume_partial else compute_roi(realized, volume)
        link = r["polymarket_link"]

        if rank == 1:
            rank_str = "🥇"
        elif rank == 2:
            rank_str = "🥈"
        elif rank == 3:
            rank_str = "🥉"
        else:
            rank_str = f"#{rank}"

        cells = [rank_str, trader]
        if wide:
            cells.append(short_w)
        cells += [money(realized), money(unrealized)]
        if wide:
            cells += [money(pnl), volume_str(volume)]
        cells.append(str(trades))
        if show_roi:
            cells.append(format_roi(roi))
        cells.append(format_win_rate(win_rate, closed_positions))
        if show_profile:
            cells.append(link)
        table.add_row(*cells)

    if not rows:
        console.print(f"[yellow]No sharp traders found with 7D Realized PnL >= ${min_pnl:,.2f} yet. Run a scan to discover more active wallets![/yellow]")
    else:
        console.print(table)


def run_scan_cycle(min_pnl: float = 300.0, max_wallets: int = 30):
    """Run a single scan cycle over tracked wallets."""
    wallets = get_wallets_to_scan(limit=max_wallets)
    if not wallets:
        console.print("[yellow]No tracked wallets found to scan. Ingesting recent public trades first...[/yellow]")
        # Ingest recent trades to discover active wallets
        try:
            resp = _rate_limited_get(f"{DATA_API_BASE}/trades", {"limit": 50})
            if resp is not None:
                conn = get_db_connection()
                cur = conn.cursor()
                for t in resp.json():
                    w = normalize_wallet(t.get("proxyWallet"))
                    p = t.get("pseudonym") or t.get("name") or "Anonymous"
                    ts = t.get("timestamp") or int(time.time())
                    if w:
                        cur.execute("""
                            INSERT INTO tracked_wallets (wallet, pseudonym, first_seen, last_seen, trade_count, total_volume_usd)
                            VALUES (?, ?, ?, ?, 1, 0)
                            ON CONFLICT(wallet) DO NOTHING
                        """, (w, p, ts, ts))
                conn.commit()
                conn.close()
                wallets = get_wallets_to_scan(limit=max_wallets)
        except Exception as e:
            console.print(f"[red]Error seeding wallets: {e}[/red]")

    console.print(f"[bold cyan]Scanning 7D PnL for {len(wallets)} active wallets via Polymarket Free Data API...[/bold cyan]")
    sharp_found = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Analyzing wallets...", total=len(wallets))

        for w in wallets:
            metrics = calculate_wallet_7d_pnl(w)
            if metrics:
                save_sharp_trader(metrics, min_sharp_pnl=min_pnl)
                if metrics["pnl_7d"] >= min_pnl:
                    sharp_found += 1
            progress.advance(task)
            # Extra spacing between wallets on top of the per-request floor
            # enforced inside _rate_limited_get(), to stay well clear of
            # Cloudflare's 429 threshold on long scans.
            time.sleep(REQUEST_INTERVAL_SECONDS)

    console.print(f"[green]✓ Scan completed! Found/updated {sharp_found} sharp traders ($300+ 7D PnL).[/green]\n")


def scan_single_wallet(wallet: str, min_pnl: float = 300.0):
    """Scan and print detailed metrics for a single wallet."""
    console.print(f"[bold cyan]Analyzing wallet {wallet}...[/bold cyan]")
    metrics = calculate_wallet_7d_pnl(wallet)
    if not metrics:
        console.print("[red]Could not retrieve activity for this wallet.[/red]")
        return

    save_sharp_trader(metrics, min_sharp_pnl=min_pnl)

    pnl = metrics["pnl_7d"]
    pnl_style = "bold bright_green" if pnl > 0 else "bold red"
    
    realized = metrics.get("realized_pnl_7d", 0.0)
    unrealized = metrics.get("unrealized_pnl", 0.0)

    txt = Text()
    txt.append("🎯 WALLET PERFORMANCE AUDIT\n", style="bold cyan")
    txt.append(f"Wallet: {metrics['wallet']}\n", style="bold white")
    txt.append(f"Pseudonym: {metrics['pseudonym']}\n", style="bold yellow")
    txt.append(f"Est. PnL (7d realized + open unrealized): ", style="bold white")
    txt.append(f"${pnl:,.2f}\n", style=pnl_style)
    txt.append(f"  7d realized (positions resolved in window): ", style="dim")
    txt.append(f"${realized:,.2f}\n", style="bright_green" if realized > 0 else "red")
    txt.append(f"  Open unrealized (mark-to-market, lifetime-to-date): ", style="dim")
    txt.append(f"${unrealized:,.2f}\n", style="bright_green" if unrealized > 0 else "red")
    txt.append(f"7D Volume: ${metrics['volume_7d']:,.2f}\n", style="bold white")
    txt.append(f"Open Exposure: ${metrics.get('open_exposure', 0.0):,.2f} across {metrics.get('open_positions', 0)} open positions\n", style="bold white")
    txt.append(f"Trades Count: {metrics['trades_7d']}\n", style="bold white")
    closed_n = metrics.get("closed_positions_7d", 0)
    txt.append(
        f"Win Rate: {format_win_rate(metrics['win_rate'], closed_n)} "
        f"({closed_n} positions resolved in window)\n",
        style="bold white",
    )
    roi_val = metrics.get("roi_7d")
    roi_text = NO_DATA_DASH if roi_val is None else f"{roi_val:+.1f}%"
    roi_note = "  [volume truncated - ROI withheld]" if metrics.get("volume_is_partial") else ""
    txt.append(f"7D ROI (realized / volume): {roi_text}{roi_note}\n", style="bold white")
    txt.append(f"Sharp Trader Status: ", style="bold white")
    txt.append("SHARP ($300+ PnL)" if pnl >= min_pnl else "STANDARD", style="bold green" if pnl >= min_pnl else "dim")
    txt.append(f"\nPolymarket Link: {metrics['polymarket_link']}", style="underline cyan")

    console.print(Panel(txt, border_style="green" if pnl >= min_pnl else "blue", padding=(1, 2)))


def print_banner(min_pnl: float):
    """Print welcome header banner."""
    txt = Text()
    txt.append("👑 POLYMARKET MONARCH - 100% FREE PNL & SHARP TRADER SCANNER\n", style="bold green")
    txt.append("Native Public Data API Engine  |  ", style="bold white")
    txt.append(f"Sharp Money Threshold: >= ${min_pnl:,.0f} 7D REALIZED PnL  |  ", style="bold yellow")
    txt.append(f"Storage: SQLite ({DB_PATH.name})\n", style="bold cyan")
    txt.append("Zero Third-Party API Dependence  |  Direct Polymarket Data API", style="dim")
    console.print(Panel(txt, border_style="green", padding=(1, 2)))


def main():
    parser = argparse.ArgumentParser(description="Polymarket Monarch Free PnL Scanner")
    parser.add_argument("--min-pnl", type=float, default=300.0, help="Minimum 7-day REALIZED PnL to qualify as sharp (default: 300.0)")
    parser.add_argument("--sort", choices=sorted(SORT_MODES), default="realized",
                        help="Leaderboard ordering: realized (banked profit, default), "
                             "roi (profit per dollar traded), or volume (turnover)")
    parser.add_argument("--max-wallets", type=int, default=30, help="Max wallets to scan per batch (default: 30)")
    parser.add_argument("--loop", action="store_true", help="Run continuous scan loop")
    parser.add_argument("--interval", type=int, default=120, help="Interval in seconds between scan loops (default: 120)")
    parser.add_argument("--wallet", type=str, help="Scan a single specific wallet address")
    parser.add_argument("--show-only", action="store_true", help="Only display existing sharp traders table without scanning")
    parser.add_argument("--obsidian", action="store_true", help="Auto-sync scan results into Obsidian Vault")
    parser.add_argument("--vault", type=str, default=None, help="Custom Obsidian Vault path")

    args = parser.parse_args()

    console.clear()
    init_pnl_tables()
    print_banner(args.min_pnl)

    if args.wallet:
        scan_single_wallet(args.wallet, min_pnl=args.min_pnl)
        if args.obsidian:
            try:
                from obsidian_sync import sync_to_obsidian
                sync_to_obsidian(args.vault)
                console.print(f"[bold green]✓ Synced results to Obsidian Vault![/bold green]")
            except Exception as e:
                console.print(f"[red]Obsidian sync failed: {e}[/red]")
        return

    if args.show_only:
        display_sharp_traders_table(min_pnl=args.min_pnl, sort_by=args.sort)
        if args.obsidian:
            try:
                from obsidian_sync import sync_to_obsidian
                sync_to_obsidian(args.vault)
                console.print(f"[bold green]✓ Synced results to Obsidian Vault![/bold green]")
            except Exception as e:
                console.print(f"[red]Obsidian sync failed: {e}[/red]")
        return

    while True:
        run_scan_cycle(min_pnl=args.min_pnl, max_wallets=args.max_wallets)
        display_sharp_traders_table(min_pnl=args.min_pnl, sort_by=args.sort)

        if args.obsidian:
            try:
                from obsidian_sync import sync_to_obsidian
                master, count = sync_to_obsidian(args.vault)
                console.print(f"[bold green]✓ Synced {count} trader notes to Obsidian: {master.name}[/bold green]")
            except Exception as e:
                console.print(f"[red]Obsidian sync failed: {e}[/red]")

        if not args.loop:
            break

        console.print(f"[dim]Next scan cycle in {args.interval} seconds... (Press Ctrl+C to stop)[/dim]")
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]Scanner stopped by user.[/yellow]")
            break


if __name__ == "__main__":
    main()
