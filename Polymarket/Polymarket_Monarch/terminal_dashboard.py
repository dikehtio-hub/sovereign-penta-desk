"""
================================================================================
Polymarket Monarch: Live Rich CLI Terminal Intelligence Dashboard
================================================================================
Displays a real-time, colorized, 3-panel terminal dashboard showing:
  1) Top 10 Most Profitable Polymarket Wallets (7-Day PnL)
  2) Real-Time Whale Trade Stream (Market, Side, USD Notional, Wallet)
  3) Macro Sentiment Breakdown (BTC Up/Down, Fed Interest Rates, Geopolitics)

Zero paid API dependence — 100% self-hosted via Polymarket Public WebSocket,
Data API, and Gamma API.
================================================================================
"""

import os
import sys
import time
import json
import sqlite3
import threading
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests

# --------------------------------------------------------------------------
# Windows console safety.
#
# A stock cmd.exe runs cp1252, which cannot encode the emoji and block-drawing
# characters this dashboard uses; writing them raises UnicodeEncodeError and
# kills the render loop mid-frame. Two defences, in order:
#   1. Reconfigure the streams to UTF-8 (works on Win10+ / Windows Terminal).
#   2. If that fails, fall back to pure-ASCII glyphs via safe_glyph().
# --------------------------------------------------------------------------
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
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box

# Shared with the scanner so both surfaces format PnL, ROI and win rate
# identically -- and so the "no data" dash rule lives in exactly one place.
# pnl_scanner does not import this module, so there is no cycle.
from pnl_scanner import compute_roi, format_roi, format_win_rate
from tax_gate import TaxGate

# One gate for the whole dashboard. Built once at import rather than per frame:
# the hook caches its SQLite snapshot for 60s, and rebuilding it every refresh
# would throw that cache away on every tick.
TAX_GATE = TaxGate()


def _console_supports_unicode() -> bool:
    """Probe whether the attached console can actually encode our glyph set."""
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "👑🐋🏆📊🪙🏛🌐🥇█░".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


UNICODE_OK = _console_supports_unicode()

# name -> (preferred glyph, ASCII fallback)
_GLYPHS = {
    "crown": ("👑", "[M]"),
    "whale": ("🐋", "*"),
    "trophy": ("🏆", "#"),
    "chart": ("📊", "~"),
    "coin": ("🪙", "$"),
    "bank": ("🏛", "%"),
    "globe": ("🌐", "@"),
    "gold": ("🥇", "1."),
    "silver": ("🥈", "2."),
    "bronze": ("🥉", "3."),
    "dash": ("—", "-"),
    "bar_full": ("█", "#"),
    "bar_empty": ("░", "-"),
}


def safe_glyph(name: str) -> str:
    """Return a glyph the current console can definitely render."""
    preferred, fallback = _GLYPHS.get(name, ("", ""))
    return preferred if UNICODE_OK else fallback


# Rich needs to know the target encoding too, so it does not emit box-drawing
# characters the console cannot take.
console = Console(
    legacy_windows=False if UNICODE_OK else None,
    safe_box=not UNICODE_OK,
)

# Rich's `safe_box` only downgrades ROUNDED -> SQUARE, and SQUARE still uses
# U+2500/U+2502, which cp1252 cannot encode. On a non-UTF-8 console we must drop
# all the way to pure-ASCII borders. Resolved per render, not baked in at import,
# so the fallback is exercisable and stays consistent with safe_glyph().
def panel_box():
    """Border style for panels, safe for the current console encoding."""
    return box.ROUNDED if UNICODE_OK else box.ASCII


def table_box():
    """Border style for tables, safe for the current console encoding."""
    return box.SIMPLE_HEAD if UNICODE_OK else box.ASCII

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "polymarket_whales.db"

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"

# Shared in-memory state for live stream
shared_recent_whales: List[Dict[str, Any]] = []
shared_macro_sentiment: Dict[str, Any] = {}
shared_lock = threading.Lock()
running = True


def get_db_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_dashboard_db():
    """
    Ensure tables exist AND are migrated.

    whale_collector.init_database() creates sharp_traders in its original shape,
    without realized_pnl_7d / unrealized_pnl. The leaderboard now orders by
    realized_pnl_7d, so on a database the dashboard created by itself that query
    would raise and the panel would silently render empty. Running the scanner's
    migration here keeps the schema whole whichever tool touches the DB first.
    """
    from whale_collector import init_database
    from pnl_scanner import init_pnl_tables
    init_database(DB_PATH)
    init_pnl_tables(DB_PATH)


def format_wallet_short(wallet: str) -> str:
    """Shorten wallet address."""
    if not wallet or len(wallet) < 10:
        return wallet or "Unknown"
    return f"{wallet[:6]}...{wallet[-4:]}"


def format_usd(val: float) -> str:
    """Format USD currency."""
    if val is None:
        return "$0.00"
    return f"${val:,.2f}"


def fetch_top_sharp_traders(limit: int = 10) -> List[sqlite3.Row]:
    """Fetch top profitable traders from SQLite."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM sharp_traders
            ORDER BY realized_pnl_7d DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def fetch_db_stats() -> Dict[str, int]:
    """Fetch database counters."""
    stats = {"whales": 0, "wallets": 0, "sharp": 0}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM whale_trades")
        stats["whales"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tracked_wallets")
        stats["wallets"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sharp_traders WHERE is_sharp = 1")
        stats["sharp"] = cur.fetchone()[0]
        conn.close()
    except Exception:
        pass
    return stats


def fetch_recent_whale_trades_from_db(limit: int = 15) -> List[sqlite3.Row]:
    """Fetch recent whale fills from SQLite."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM whale_trades
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


# Macro categories, each resolved against the Gamma API by tag.
#
# IMPORTANT: Gamma's /events endpoint filters on `tag_slug`, NOT `tag`. Passing
# `tag=crypto` is silently ignored and returns the same unfiltered global feed
# for every category (verified against the live API). Each category lists
# fallback slugs because some tags -- `economics` in particular -- carry very
# few active events at any given time.
MACRO_CATEGORIES = [
    ("crypto",    "coin",  "Crypto",    ["crypto", "bitcoin"]),
    ("politics",  "globe", "Politics",  ["politics", "geopolitics"]),
    ("economics", "bank",  "Economics", ["economics", "economy", "fed-rates", "inflation"]),
]

GAMMA_HEADERS = {"User-Agent": "Polymarket-Monarch-Dashboard/1.0", "Accept": "application/json"}


def _parse_json_field(val, default):
    """Gamma returns `outcomes` / `outcomePrices` as JSON-encoded strings."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else default
        except Exception:
            return default
    return default


def _market_24h_volume(market: Dict[str, Any]) -> float:
    """
    24h volume for a single market.

    Deliberately does NOT fall back to lifetime `volumeNum`: markets that have
    already resolved report volume24hr=None but carry huge lifetime volume, so a
    fallback would rank settled 100%/0% markets above live ones.
    """
    try:
        return float(market.get("volume24hr") or 0.0)
    except (TypeError, ValueError):
        return 0.0


# Floor on the contested-ness weight. A hugely traded extreme leg should still
# be able to win on volume alone; this weights it down, it does not delete it.
CONTESTED_WEIGHT_FLOOR = 0.1


def contested_score(volume_24h: float, prob: float) -> float:
    """
    Volume discounted by distance from a coin flip.

    Full weight at 50%, falling linearly to CONTESTED_WEIGHT_FLOOR at 0% or 100%.
    Used to rank the legs of a multi-strike ladder, where cheap far-out strikes
    rack up share volume without being what the market is actually debating.
    """
    weight = max(CONTESTED_WEIGHT_FLOOR, 1.0 - abs(prob - 50.0) / 50.0)
    return volume_24h * weight


def extract_event_probability(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Reduce a Gamma event to a single headline probability row.

    Multi-market events (e.g. "What price will Bitcoin hit in August?" carries 47
    strike markets) mix live and already-settled legs. Selection keeps every
    tradeable leg and then ranks them:

      * skip settled legs -- `closed is True`, or `volume24hr` absent (the API
        stops reporting 24h volume once a market resolves)
      * skip legs pinned at exactly 100.0% / 0.0%, which are decided in all but
        name and carry no sentiment
      * rank what remains and take the top one

    RANKING. For a two-outcome event, raw `volume24hr` is the right ranking: the
    most-traded leg IS the market's view, even at 99% ("the Fed will hold, 99%"
    is real conviction, not noise).

    For a multi-strike ladder (>2 markets) raw volume misleads. Deep-out-of-the
    money strikes ("BTC to $1M") accumulate large SHARE counts precisely because
    they are cheap lottery tickets, so they can out-volume the strike the market
    is actually arguing about. There, volume is weighted by how contested the
    price is, which surfaces the live strike boundary instead of the lotto ticket:

        score = volume24hr * max(0.1, 1 - |prob - 50| / 50)

    The 0.1 floor keeps a hugely-traded extreme leg in contention rather than
    zeroing it out -- weighting, not filtering.
    """
    markets = [m for m in (event.get("markets") or []) if isinstance(m, dict)]
    if not markets:
        return None

    try:
        event_volume = float(event.get("volume24hr") or 0.0)
    except (TypeError, ValueError):
        event_volume = 0.0

    candidates = []
    for market in markets:
        # Settled legs: explicitly closed/deactivated, or no 24h volume reported.
        if market.get("closed") is True or market.get("active") is False:
            continue
        if market.get("volume24hr") is None:
            continue

        outcomes = _parse_json_field(market.get("outcomes"), [])
        prices = _parse_json_field(market.get("outcomePrices"), [])
        if not prices:
            continue

        prob = None
        if outcomes and len(outcomes) == len(prices):
            for outcome, price in zip(outcomes, prices):
                if str(outcome).strip().lower() in ("yes", "up"):
                    try:
                        prob = float(price) * 100.0
                    except (TypeError, ValueError):
                        prob = None
                    break
        if prob is None:
            try:
                prob = float(prices[0]) * 100.0
            except (TypeError, ValueError):
                continue

        prob = round(prob, 1)
        # Pinned at a certainty -- decided in all but settlement.
        if prob == 100.0 or prob == 0.0:
            continue

        candidates.append({
            "title": (market.get("question") or event.get("title") or "Unknown market"),
            "prob": prob,
            "volume": event_volume,
            "market_volume_24h": _market_24h_volume(market),
        })

    if not candidates:
        return None

    # Multi-strike ladders need the contested-ness weighting; a plain two-sided
    # event does not (and must not be re-weighted away from its own headline).
    is_multi_strike = len(markets) > 2
    for candidate in candidates:
        candidate["score"] = (
            contested_score(candidate["market_volume_24h"], candidate["prob"])
            if is_multi_strike else candidate["market_volume_24h"]
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0]


def fetch_top_markets_by_tag(tag_slug: str, limit: int = 4, timeout: int = 8) -> List[Dict[str, Any]]:
    """
    Fetch the highest 24h-volume active events carrying `tag_slug` from Gamma.
    Returns [] on any failure so the dashboard degrades instead of crashing.
    """
    params = {
        "tag_slug": tag_slug,
        "active": "true",
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false",
        "limit": limit,
    }
    try:
        resp = requests.get(f"{GAMMA_API_BASE}/events", headers=GAMMA_HEADERS, params=params, timeout=timeout)
        if resp.status_code != 200:
            return []
        events = resp.json()
    except Exception:
        return []

    if isinstance(events, dict):
        events = events.get("data", [])
    if not isinstance(events, list):
        return []
    return [e for e in events if isinstance(e, dict)]


def fetch_macro_sentiment_data(per_category: int = 2) -> Dict[str, Any]:
    """
    Build the Macro Sentiment panel data by pulling the top 24h-volume markets
    for each macro tag (crypto / politics / economics) straight from Gamma.
    """
    results: Dict[str, Any] = {
        "last_updated": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        "categories": [],
    }

    # Deduped across categories, not just within one: events carry several tags
    # (the Fed decision is both `politics` and `economics`), and showing the same
    # market twice wastes a scarce panel row.
    seen_titles = set()

    for key, glyph, label, slugs in MACRO_CATEGORIES:
        rows: List[Dict[str, Any]] = []
        used_slug = slugs[0]

        # Walk the fallback chain until the category is full. A thin tag
        # (`economics` often has a single active event) tops up from the next
        # slug rather than leaving the row half empty.
        for slug in slugs:
            if len(rows) >= per_category:
                break
            events = fetch_top_markets_by_tag(slug, limit=per_category + 3)
            if events and not rows:
                used_slug = slug
            for event in events:
                row = extract_event_probability(event)
                if not row or row["title"] in seen_titles:
                    continue
                seen_titles.add(row["title"])
                rows.append(row)
                if len(rows) >= per_category:
                    break

        # Highest 24h volume first, then trim to the requested depth.
        rows.sort(key=lambda r: r.get("volume", 0.0), reverse=True)
        rows = rows[:per_category]

        results[key] = rows
        results["categories"].append({
            "key": key,
            "glyph": glyph,
            "label": label,
            "tag_slug": used_slug,
            "rows": rows,
        })

    return results


def macro_poller_thread():
    """Background thread to periodically refresh macro sentiment metrics."""
    global shared_macro_sentiment, running
    while running:
        data = fetch_macro_sentiment_data()
        with shared_lock:
            shared_macro_sentiment = data
        time.sleep(30)


def whale_collector_background_thread(min_usd: float = 1000.0):
    """
    Background worker that continuously ingests public trades via WebSocket/REST.
    """
    global shared_recent_whales, running
    from whale_collector import save_trade, REST_TRADES_URL

    headers = {"User-Agent": "Polymarket-Monarch-Dashboard-Worker/1.0", "Accept": "application/json"}
    while running:
        try:
            resp = requests.get(f"{REST_TRADES_URL}?limit=40", headers=headers, timeout=8)
            if resp.status_code == 200:
                trades = resp.json()
                for t in sorted(trades, key=lambda x: x.get("timestamp", 0)):
                    is_whale = save_trade(t, min_usd=min_usd)
                    if is_whale:
                        with shared_lock:
                            shared_recent_whales.insert(0, t)
                            if len(shared_recent_whales) > 30:
                                shared_recent_whales.pop()
        except Exception:
            pass
        time.sleep(3)


def make_header_panel(stats: Dict[str, int]) -> Panel:
    """Create top status header banner."""
    dt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    txt = Text()
    txt.append(f"{safe_glyph('crown')} POLYMARKET MONARCH ", style="bold bright_yellow")
    txt.append("• 100% NATIVE & FREE PREDICTION INTELLIGENCE • ", style="bold cyan")
    txt.append(f"[{dt}]\n", style="dim")
    
    txt.append("Database Stats: ", style="bold white")
    txt.append(f"{stats['whales']} Whale Fills Stored  ", style="bold green")
    txt.append("• ", style="dim")
    txt.append(f"{stats['wallets']} Tracked Wallets  ", style="bold magenta")
    txt.append("• ", style="dim")
    txt.append(f"{stats['sharp']} Sharp Traders ($300+ 7D PnL)  ", style="bold yellow")
    txt.append("• ", style="dim")
    txt.append("Zero Third-Party API Dependence", style="bold blue")

    # Risk capital, not wallet balance. Gains already realised this year carry a
    # tax liability that the balance does not show, and sizing off the balance
    # spends money that is already owed.
    txt.append("\n")
    if TAX_GATE.available:
        txt.append(TAX_GATE.status_line(), style="bold bright_green")
    else:
        txt.append(TAX_GATE.status_line(), style="bold yellow")

    return Panel(txt, border_style="cyan", box=panel_box(), padding=(0, 1))


# The traders panel shares its row with the whale stream, so it only ever gets
# about half the console. The realized/unrealized breakdown needs ~66 columns of
# table, hence roughly double that in console width before it can be shown.
TRADERS_PANEL_WIDE_MIN_CONSOLE = 136


def _row_get(row, key: str, default=0.0):
    """Read a column from a sqlite3.Row, tolerating pre-migration databases."""
    try:
        val = row[key]
    except (IndexError, KeyError):
        return default
    return default if val is None else val


def _abbrev_usd(mag: float) -> str:
    if mag >= 1_000_000:
        return f"${mag / 1_000_000:.1f}M"
    if mag >= 1_000:
        return f"${mag / 1_000:.1f}K"
    return f"${mag:,.0f}"


def _money(val: float) -> str:
    """Signed, abbreviated PnL with a colour that matches its sign."""
    style = "bold bright_green" if val > 0 else ("bold red" if val < 0 else "dim")
    sign = "-" if val < 0 else ("+" if val > 0 else "")
    return f"[{style}]{sign}{_abbrev_usd(abs(val))}[/{style}]"


def make_traders_panel() -> Panel:
    """
    Panel 1: Top 10 Most Profitable Polymarket Wallets.

    Ranked by 7D REALIZED profit -- money actually banked this week. Ranking on
    the blended realized+unrealized figure let dormant wallets with no trades
    this week sit at the top on the strength of an old open position.

    Open unrealized stays visible beside it, because "+$25k realized" reads very
    differently next to a -$38k open book. On a wide console the blended
    "Est. PnL" total and 7d volume are shown too.
    """
    traders = fetch_top_sharp_traders(limit=10)
    # This panel occupies only HALF the console (it sits beside the whale
    # stream), so the console has to be roughly twice as wide as the columns
    # need. Below that, Rich squeezes every column into an ellipsis.
    wide = console.width >= TRADERS_PANEL_WIDE_MIN_CONSOLE

    table = Table(
        box=table_box(),
        header_style="bold bright_white on dark_green",
        expand=True,
        show_edge=False,
        pad_edge=False
    )

    table.add_column("Rank", justify="center", style="bold yellow", width=4, no_wrap=True)
    table.add_column("Wallet / Trader", justify="left", style="bold cyan", width=14,
                     no_wrap=True, overflow="ellipsis")
    # 7D Realized is the ranking key, so it stays visible at every width; Open
    # Unrealized rides alongside it because a big realized number next to a
    # deeply negative open book means something very different.
    table.add_column("7D Real.", justify="right", style="bold green", width=8, no_wrap=True)
    table.add_column("Open Unr.", justify="right", width=8, no_wrap=True)
    if wide:
        # This panel gets only half the console, so ROI% displaces the two least
        # load-bearing columns rather than being squeezed in beside them:
        # Est. PnL is just the sum of the two columns already shown, and raw
        # volume matters less than the return earned on it.
        table.add_column("ROI%", justify="right", style="bold yellow", width=7, no_wrap=True)
    table.add_column("Trades", justify="center", style="bold magenta", width=5, no_wrap=True)
    table.add_column("Win%", justify="center", style="bold cyan", width=5, no_wrap=True)

    for rank, r in enumerate(traders, 1):
        wallet = r["wallet"]
        short_w = format_wallet_short(wallet)
        pseudonym = r["pseudonym"]
        label = pseudonym if pseudonym and pseudonym != "Anonymous" else short_w
        pnl = r["pnl_7d"]
        realized = _row_get(r, "realized_pnl_7d")
        unrealized = _row_get(r, "unrealized_pnl")
        volume = r["volume_7d"]
        trades = r["trades_7d"]
        win_rate = r["win_rate"]
        closed_positions = _row_get(r, "closed_positions_7d", None)
        volume_partial = bool(_row_get(r, "volume_is_partial", 0))
        roi = None if volume_partial else compute_roi(realized, volume)

        if rank == 1:
            rank_str = safe_glyph("gold")
        elif rank == 2:
            rank_str = safe_glyph("silver")
        elif rank == 3:
            rank_str = safe_glyph("bronze")
        else:
            rank_str = f"#{rank}"

        dash = safe_glyph("dash")
        cells = [rank_str, label, _money(realized), _money(unrealized)]
        if wide:
            cells.append(format_roi(roi, dash=dash))
        cells += [str(trades), format_win_rate(win_rate, closed_positions, dash=dash)]
        table.add_row(*cells)

    title = f"{safe_glyph('trophy')} Top 10 Wallets by 7D Realized PnL (open unrealized shown for context)"
    if not traders:
        msg = Text("No sharp traders stored in SQLite yet.\nRun 'python pnl_scanner.py' to populate leaderboard!", style="dim yellow")
        return Panel(msg, title=title, border_style="green", box=panel_box())

    return Panel(table, title=title, border_style="green", box=panel_box())


def make_whales_panel() -> Panel:
    """Panel 2: Real-Time Whale Trade Stream."""
    trades = fetch_recent_whale_trades_from_db(limit=8)

    table = Table(
        box=table_box(),
        header_style="bold bright_white on dark_blue",
        expand=True,
        show_edge=False,
        pad_edge=False
    )

    table.add_column("Time", justify="center", style="dim", width=9)
    table.add_column("Side", justify="center", width=7)
    table.add_column("Market / Outcome", justify="left", style="bold white", width=34)
    table.add_column("Price", justify="right", style="bold yellow", width=7)
    table.add_column("Notional (USD)", justify="right", width=15)
    table.add_column("Trader", justify="left", style="bold cyan", width=14)

    for r in trades:
        ts = r["timestamp"]
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%H:%M:%S") if ts else "N/A"
        side = (r["side"] or "BUY").upper()
        market = (r["market_title"] or "Unknown")[:22]
        outcome = r["outcome"] or ""
        price = r["price"] or 0.0
        usd = r["usd_notional"] or 0.0
        pseudonym = r["pseudonym"] or format_wallet_short(r["wallet"])

        if side == "BUY":
            side_str = "[bold white on green] BUY [/bold white on green]"
        else:
            side_str = "[bold white on red] SELL[/bold white on red]"

        if usd >= 50_000:
            usd_str = f"[bold bright_white on dark_magenta] ${usd:,.2f} [/bold bright_white on dark_magenta]"
        elif usd >= 10_000:
            usd_str = f"[bold bright_yellow on dark_blue] ${usd:,.2f} [/bold bright_yellow on dark_blue]"
        else:
            usd_str = f"[bold bright_green]${usd:,.2f}[/bold bright_green]"

        market_full = f"{market} ({outcome})" if outcome else market

        table.add_row(
            dt,
            side_str,
            market_full,
            f"${price:.2f}",
            usd_str,
            pseudonym[:13]
        )

    if not trades:
        msg = Text("Listening to real-time whale fills (>= $1,000 USD)...\nCollecting live stream from Polymarket RTDS...", style="dim cyan")
        return Panel(msg, title=f"{safe_glyph('whale')} Real-Time Whale Trade Stream ($1k+ USD)", border_style="blue", box=panel_box())

    return Panel(table, title=f"{safe_glyph('whale')} Real-Time Whale Trade Stream ($1k+ USD)", border_style="blue", box=panel_box())


def make_macro_panel() -> Panel:
    """Panel 3: Macro Sentiment Breakdown."""
    with shared_lock:
        data = shared_macro_sentiment.copy()

    table = Table(
        box=table_box(),
        header_style="bold bright_white on dark_magenta",
        expand=True,
        show_edge=False,
        pad_edge=False
    )

    # Every column is no_wrap: a wrapped cell doubles the panel's row height and
    # pushes the Economics category out of view on an 80-column terminal.
    table.add_column("Macro Tag", justify="left", style="bold cyan", width=13, no_wrap=True)
    table.add_column("Top 24h Volume Market", justify="left", style="bold white", width=34,
                     no_wrap=True, overflow="ellipsis")
    table.add_column("24h Vol", justify="right", style="dim", width=8, no_wrap=True)
    table.add_column("Odds / Sentiment", justify="right", width=18, no_wrap=True)

    full = safe_glyph("bar_full")
    empty = safe_glyph("bar_empty")

    def volume_str(v: float) -> str:
        if v >= 1_000_000:
            return f"${v / 1_000_000:.1f}M"
        if v >= 1_000:
            return f"${v / 1_000:.0f}K"
        return f"${v:,.0f}"

    categories = data.get("categories") or []
    for cat in categories:
        rows = cat.get("rows") or []
        label = f"{safe_glyph(cat['glyph'])} {cat['label']}"
        if not rows:
            table.add_row(label, f"[dim]No active markets for tag '{cat['tag_slug']}'[/dim]", "-", "[dim]--[/dim]")
            continue
        for item in rows:
            p = item["prob"]
            prob_color = "bright_green" if p >= 55 else ("yellow" if p >= 45 else "red")
            bar_filled = max(0, min(10, int(p / 10)))
            bar = full * bar_filled + empty * (10 - bar_filled)
            table.add_row(
                label,
                item["title"],
                volume_str(item.get("volume", 0.0)),
                f"[{prob_color}]{bar} {p:.1f}%[/{prob_color}]"
            )
            label = ""  # only label the first row of each category

    if not categories:
        msg = Text("Fetching top 24h volume markets from Gamma API...", style="dim magenta")
        return Panel(msg, title=f"{safe_glyph('chart')} Macro Sentiment", border_style="magenta", box=panel_box())

    updated = data.get("last_updated", "Live")
    title = f"{safe_glyph('chart')} Macro Sentiment - Top 24h Volume by Tag (Updated: {updated})"
    return Panel(table, title=title, border_style="magenta", box=panel_box())


def build_dashboard_layout() -> Layout:
    """Assemble the 3-panel dashboard layout."""
    stats = fetch_db_stats()

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),   # 3 text lines + panel border
        Layout(name="body")
    )

    layout["body"].split_column(
        Layout(name="top_section", ratio=1),
        # Macro needs a fixed floor: 3 categories x 2 rows + header/border.
        # A pure ratio clips the Politics/Economics rows on shorter terminals.
        Layout(name="bottom_section", size=12)
    )

    layout["top_section"].split_row(
        Layout(name="traders", ratio=1),
        Layout(name="whales", ratio=1)
    )

    layout["header"].update(make_header_panel(stats))
    layout["top_section"]["traders"].update(make_traders_panel())
    layout["top_section"]["whales"].update(make_whales_panel())
    layout["bottom_section"].update(make_macro_panel())

    return layout


def main():
    global running, shared_macro_sentiment
    parser = argparse.ArgumentParser(description="Polymarket Monarch Live Terminal Dashboard")
    parser.add_argument("--refresh-rate", type=float, default=2.0, help="Dashboard refresh rate in seconds (default: 2.0)")
    parser.add_argument("--min-usd", type=float, default=1000.0, help="Whale fill threshold (default: 1000.0)")
    parser.add_argument("--dry-run", action="store_true", help="Render single dashboard frame and exit")

    args = parser.parse_args()

    console.clear()
    init_dashboard_db()

    # Initial macro fetch
    shared_macro_sentiment = fetch_macro_sentiment_data()

    if args.dry_run:
        layout = build_dashboard_layout()
        console.print(layout)
        return

    # Start background threads
    t_macro = threading.Thread(target=macro_poller_thread, daemon=True)
    t_macro.start()

    t_whale = threading.Thread(target=whale_collector_background_thread, args=(args.min_usd,), daemon=True)
    t_whale.start()

    try:
        refresh_fps = max(1, int(1.0 / max(0.1, args.refresh_rate)))
        with Live(build_dashboard_layout(), console=console, refresh_per_second=refresh_fps, screen=True) as live:
            while True:
                live.update(build_dashboard_layout())
                time.sleep(args.refresh_rate)
    except KeyboardInterrupt:
        running = False
        console.clear()
        console.print("[yellow]Polymarket Monarch Dashboard closed.[/yellow]")


if __name__ == "__main__":
    main()
