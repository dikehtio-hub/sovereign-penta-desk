"""
👑 Polymarket Monarch - Obsidian Vault Synchronizer
Export live sharp trader leaderboards, whale fills, macro sentiment, and
individual trader profile notes directly into an Obsidian Vault.

Usage:
  python obsidian_sync.py --once                    # One-shot export to ./obsidian_vault
  python obsidian_sync.py --vault "C:/path/to/vault"  # Export to custom Obsidian Vault
  python obsidian_sync.py --watch --interval 15     # Continuous live synchronization
"""

import argparse
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "polymarket_whales.db"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# Cross-suite Obsidian linking lives in HL_Monarch so both exporters share one
# definition of the vault layout. Imported defensively: Polymarket must keep
# working on its own if the HyperLiquid project is absent.
_HL_ANALYTICS = BASE_DIR.parent.parent / "HyperLiquid" / "HL_Monarch"
if _HL_ANALYTICS.is_dir() and str(_HL_ANALYTICS) not in sys.path:
    sys.path.insert(0, str(_HL_ANALYTICS))
try:
    from analytics.obsidian_links import (
        HL_DASHBOARD_NOTE,
        QL_DASHBOARD_NOTE,
        HUB_NOTE,
        counterpart_link,
        note_exists,
        wikilink,
        write_hub_note,
        write_note_if_changed,
    )
    CROSS_SUITE_LINKING = True
except Exception:
    CROSS_SUITE_LINKING = False
    HL_DASHBOARD_NOTE = "HyperLiquid_Monarch"
    QL_DASHBOARD_NOTE = "Quant_Trading_Lab"
    HUB_NOTE = "Monarch_Hub"

    def counterpart_link(vault_path, note_name, label):
        return None

    def note_exists(vault_path, note_name):
        return (Path(vault_path) / f"{note_name}.md").exists()

    def wikilink(target, label=None):
        return f"[[{target}|{label}]]" if label else f"[[{target}]]"

    def write_hub_note(vault_path, synced_at):
        return None

    def write_note_if_changed(file_path, content):
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path, True

DEV_ROOT = Path("C:/Users/ixis1/Desktop/DEV")
DEFAULT_VAULT_DIR = (DEV_ROOT / "obsidian_vault") if (DEV_ROOT / "obsidian_vault").exists() else (BASE_DIR / "obsidian_vault")

USER_NOTES_HEADER = "## 📝 My Research & Notes"

# Per-run write accounting, so a sync can report how much disk churn it avoided.
WRITE_STATS = {"wallets_skipped": 0}
DEFAULT_USER_NOTES_TEMPLATE = """
*Add your custom notes, trading thesis, tags, or strategy analysis for this wallet below:*
- **Style**: 
- **Tags**: #polymarket #sharp-trader
- **Thesis**: 
"""


def get_vault_path(custom_path: Optional[str] = None) -> Path:
    """Resolve the target Obsidian Vault path."""
    if custom_path:
        p = Path(custom_path).expanduser().resolve()
    elif os.environ.get("OBSIDIAN_VAULT_PATH"):
        p = Path(os.environ["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()
    else:
        p = DEFAULT_VAULT_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


def format_money(val: float) -> str:
    """Format money with sign and thousands/millions abbreviations."""
    sign = "+" if val > 0 else ("-" if val < 0 else "")
    mag = abs(val)
    if mag >= 1_000_000:
        return f"{sign}${mag / 1_000_000:.2f}M"
    if mag >= 1_000:
        return f"{sign}${mag / 1_000:.1f}K"
    return f"{sign}${mag:,.2f}"


def format_volume(val: float) -> str:
    mag = abs(val)
    if mag >= 1_000_000:
        return f"${mag / 1_000_000:.2f}M"
    if mag >= 1_000:
        return f"${mag / 1_000:.1f}K"
    return f"${mag:,.0f}"


def format_roi_str(pnl: float, vol: float, is_partial: bool) -> str:
    if is_partial or vol <= 0:
        return "—"
    roi = (pnl / vol) * 100.0
    sign = "+" if roi > 0 else ""
    return f"{sign}{roi:.1f}%"


def format_win_rate_str(win_rate: float, closed_count: Optional[int]) -> str:
    if closed_count is None or closed_count <= 0:
        return "—"
    return f"{float(win_rate):.0f}%"


def fetch_sharp_traders(db_path: Optional[Path] = None, limit: int = 50) -> List[Dict]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM sharp_traders
            WHERE realized_pnl_7d >= 300
            ORDER BY realized_pnl_7d DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def fetch_recent_whale_trades(db_path: Optional[Path] = None, limit: int = 25) -> List[Dict]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM whale_trades
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def fetch_macro_sentiment() -> List[Dict]:
    """Fetch top volume macro markets across Crypto, Politics, Economics."""
    categories = [
        ("crypto", "🪙 Crypto", "crypto"),
        ("politics", "🌐 Politics", "politics"),
        ("economics", "🏛 Economics", "economics"),
    ]
    results = []
    headers = {"User-Agent": "Polymarket-Monarch-Obsidian/1.0", "Accept": "application/json"}
    for key, label, tag_slug in categories:
        try:
            resp = requests.get(
                f"{GAMMA_API_BASE}/events",
                params={
                    "limit": 3,
                    "active": "true",
                    "closed": "false",
                    "order": "volume24hr",
                    "ascending": "false",
                    "tag_slug": tag_slug
                },
                headers=headers,
                timeout=5
            )
            if resp.status_code == 200:
                events = resp.json()
                for ev in events:
                    markets = ev.get("markets", [])
                    if not markets:
                        continue
                    m = markets[0]
                    # Parse probabilities
                    try:
                        import json
                        prices_raw = m.get("outcomePrices", "[]")
                        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                        prob = float(prices[0]) * 100.0 if prices else 50.0
                    except Exception:
                        prob = 50.0
                    results.append({
                        "category": label,
                        "title": ev.get("title") or m.get("question", "Unknown Market"),
                        "volume_24h": float(ev.get("volume24hr") or 0.0),
                        "prob": prob,
                    })
        except Exception:
            pass
    return results


def make_prob_bar(prob: float, length: int = 10) -> str:
    """Create a visual text probability bar for Markdown."""
    filled = int(round(prob / 100.0 * length))
    filled = max(0, min(length, filled))
    empty = length - filled
    return f"`{'█' * filled}{'░' * empty}` **{prob:.1f}%**"


def preserve_user_notes(file_path: Path) -> str:
    """Extract and preserve user-written notes from an existing markdown note."""
    if not file_path.exists():
        return DEFAULT_USER_NOTES_TEMPLATE
    try:
        content = file_path.read_text(encoding="utf-8")
        if USER_NOTES_HEADER in content:
            parts = content.split(USER_NOTES_HEADER, 1)
            return parts[1]
    except Exception:
        pass
    return DEFAULT_USER_NOTES_TEMPLATE


def generate_wallet_note(trader: Dict, vault_path: Path) -> Path:
    """Generate an individual researcher profile page for a single sharp trader."""
    wallets_dir = vault_path / "Wallets"
    wallets_dir.mkdir(parents=True, exist_ok=True)

    wallet = trader["wallet"].lower()
    pseudonym = trader.get("pseudonym") or "Anonymous"
    short_w = f"{wallet[:6]}...{wallet[-4:]}"
    display_title = f"{pseudonym} ({short_w})" if pseudonym != "Anonymous" else short_w
    file_path = wallets_dir / f"{wallet}.md"

    realized = trader.get("realized_pnl_7d", 0.0)
    unrealized = trader.get("unrealized_pnl", 0.0)
    pnl_7d = trader.get("pnl_7d", realized + unrealized)
    volume_7d = trader.get("volume_7d", 0.0)
    trades_7d = trader.get("trades_7d", 0)
    win_rate = trader.get("win_rate", 0.0)
    closed_pos = trader.get("closed_positions_7d", 0)
    is_partial = bool(trader.get("volume_is_partial", 0))
    roi = format_roi_str(realized, volume_7d, is_partial)
    win_str = format_win_rate_str(win_rate, closed_pos)
    poly_link = trader.get("polymarket_link") or f"https://polymarket.com/profile/{wallet}"
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    user_notes = preserve_user_notes(file_path)

    md = f"""---
title: {display_title}
wallet: "{wallet}"
pseudonym: "{pseudonym}"
realized_7d: {realized}
unrealized: {unrealized}
est_pnl_7d: {pnl_7d}
volume_7d: {volume_7d}
trades_7d: {trades_7d}
win_rate: {win_rate}
roi_7d: "{roi}"
last_synced: "{now_utc}"
tags:
  - polymarket
  - sharp-trader
---

# 👑 Sharp Trader: {display_title}

> [!INFO] **Trader Overview**
> - **Wallet Address**: `{wallet}`
> - **Pseudonym**: **{pseudonym}**
> - **Polymarket Profile**: [View on Polymarket]({poly_link})
> - **Last Updated**: `{now_utc}`

---

## 📊 7-Day Performance Metrics

| Metric | Value | Context |
| :--- | :--- | :--- |
| **7D Realized PnL** | **`{format_money(realized)}`** | Banked profit from resolved markets |
| **Open Unrealized PnL** | `{format_money(unrealized)}` | Mark-to-market live exposure |
| **Est. Total PnL** | **`{format_money(pnl_7d)}`** | Realized + Open Unrealized |
| **7D Traded Volume** | `{format_volume(volume_7d)}` | Capital turned over in 7 days |
| **7D Realized ROI** | **`{roi}`** | Return on traded volume |
| **Win Rate** | `{win_str}` | Settled winning positions |
| **Trade Count** | `{trades_7d}` fills | Total 7-day activity |

---

{USER_NOTES_HEADER}
{user_notes.strip()}
"""
    _, was_written = write_note_if_changed(file_path, md.strip() + "\n")
    if not was_written:
        WRITE_STATS["wallets_skipped"] += 1
    return file_path


def generate_master_dashboard_note(
    traders: List[Dict],
    whales: List[Dict],
    macro: List[Dict],
    vault_path: Path,
) -> Path:
    """Generate the central Polymarket_Monarch.md dashboard in Obsidian."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    master_file = vault_path / "Polymarket_Monarch.md"

    # Cross-suite navigation. The HyperLiquid & Quant Lab links are emitted only when
    # those dashboards share this vault, so a standalone export never renders a link
    # Obsidian cannot resolve.
    hl_link = counterpart_link(vault_path, HL_DASHBOARD_NOTE, "👑 HyperLiquid Monarch")
    ql_link = counterpart_link(vault_path, QL_DASHBOARD_NOTE, "⚡ Quant Trading Lab")
    sports_link = counterpart_link(vault_path, "Sports_Desk", "🏈 Sports Desk")
    xarb_link = counterpart_link(vault_path, "Cross_Market_Arb", "⚖️ Cross-Market Arb")
    nav_parts = [wikilink(HUB_NOTE, "👑 Monarch Intelligence Hub")]
    if hl_link:
        nav_parts.append(hl_link)
    if ql_link:
        nav_parts.append(ql_link)
    if sports_link:
        nav_parts.append(sports_link)
    if xarb_link:
        nav_parts.append(xarb_link)
    nav_line = "> **Vault Navigation**: " + " • ".join(nav_parts)

    # 1. Leaderboard Table
    leaderboard_rows = []
    for rank, t in enumerate(traders[:20], 1):
        wallet = t["wallet"].lower()
        pseudonym = t.get("pseudonym") or "Anonymous"
        short_w = f"{wallet[:6]}...{wallet[-4:]}"
        trader_label = pseudonym if pseudonym != "Anonymous" else short_w
        # Obsidian link to individual note page
        link = f"[[Wallets/{wallet}|{trader_label}]]"
        
        realized = t.get("realized_pnl_7d", 0.0)
        unrealized = t.get("unrealized_pnl", 0.0)
        pnl = t.get("pnl_7d", realized + unrealized)
        vol = t.get("volume_7d", 0.0)
        trades = t.get("trades_7d", 0)
        win_rate = t.get("win_rate", 0.0)
        closed_pos = t.get("closed_positions_7d", 0)
        is_partial = bool(t.get("volume_is_partial", 0))
        roi = format_roi_str(realized, vol, is_partial)
        win_str = format_win_rate_str(win_rate, closed_pos)

        badge = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"#{rank}"))
        leaderboard_rows.append(
            f"| {badge} | {link} | `{format_money(realized)}` | `{format_money(unrealized)}` | `{format_money(pnl)}` | `{format_volume(vol)}` | `{roi}` | `{win_str}` | `{trades}` |"
        )
    leaderboard_table = "\n".join(leaderboard_rows) if leaderboard_rows else "| — | *No sharp traders found yet. Run pnl_scanner.py.* | — | — | — | — | — | — | — |"

    # 2. Whale Trades Table
    whale_rows = []
    for w in whales[:15]:
        ts = w.get("timestamp")
        dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S") if ts else "—"
        side = (w.get("side") or "BUY").upper()
        side_badge = f"🟢 **BUY**" if side == "BUY" else f"🔴 **SELL**"
        size = float(w.get("size_usd") or 0.0)
        size_str = f"`${size:,.0f}`"
        title = (w.get("title") or "Unknown Market")[:45]
        outcome = w.get("outcome") or "—"
        trader_addr = (w.get("trader_address") or "").lower()
        trader_name = w.get("trader_name") or (f"{trader_addr[:6]}...{trader_addr[-4:]}" if trader_addr else "Anon")
        trader_link = f"[[Wallets/{trader_addr}|{trader_name}]]" if trader_addr else trader_name
        whale_rows.append(f"| {dt_str} | {side_badge} | {size_str} | {title} | `{outcome}` | {trader_link} |")
    whale_table = "\n".join(whale_rows) if whale_rows else "| — | — | — | *No whale trades recorded yet. Run whale_collector.py.* | — | — |"

    # 3. Macro Sentiment Table
    macro_rows = []
    for m in macro:
        cat = m["category"]
        title = m["title"]
        vol = format_volume(m["volume_24h"])
        bar = make_prob_bar(m["prob"])
        macro_rows.append(f"| {cat} | {title} | `{vol}` | {bar} |")
    macro_table = "\n".join(macro_rows) if macro_rows else "| — | *Macro data updating...* | — | — |"

    content = f"""---
title: Polymarket Monarch Live Intelligence
tags:
  - polymarket
  - prediction-markets
  - alpha
  - dashboard
last_synced: "{now_utc}"
---

# 👑 Polymarket Monarch • Real-Time Intelligence

{nav_line}
> **Desk**: [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]] · Shell twin: `python Polymarket/Polymarket_Monarch/obsidian_sync.py --once`

> [!TIP] **System Status: LIVE**
> - **Last Synchronized**: `{now_utc}`
> - **Active Sharp Traders ($300+ 7D Realized)**: `{len(traders)}`
> - **Public Polymarket Data Engine**: 100% Free / Native Public APIs (No Paid Keys)

---

## 🏆 Top Sharp Traders (7-Day Realized PnL)
*Click any trader's name to open their dedicated research notes page.*

| Rank | Trader / Wallet | 7D Realized | Open Unreal. | Est. Total PnL | 7D Volume | ROI% | Win% | Trades |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
{leaderboard_table}

---

## 🐋 Live Whale Fill Stream ($1,000+ USD)

| Time (UTC) | Side | Size | Market | Outcome | Trader |
| :---: | :---: | :---: | :--- | :---: | :--- |
{whale_table}

---

## 📊 Macro Market Sentiment & 24h Volume

| Category | Top Volume Market | 24h Vol | Yes Odds / Probability |
| :--- | :--- | :---: | :--- |
{macro_table}

---
*Generated automatically by Polymarket Monarch Obsidian Sync.*
"""
    write_note_if_changed(master_file, content.strip() + "\n")
    return master_file


def sync_to_obsidian(vault_path_str: Optional[str] = None, db_path: Optional[Path] = None) -> Tuple[Path, int]:
    """Perform a full synchronization cycle to the Obsidian Vault."""
    vault_path = get_vault_path(vault_path_str)
    
    # 1. Fetch data
    traders = fetch_sharp_traders(db_path=db_path)
    whales = fetch_recent_whale_trades(db_path=db_path)
    macro = fetch_macro_sentiment()

    # 2. Write individual wallet notes (unchanged ones are left untouched)
    WRITE_STATS["wallets_skipped"] = 0
    wallet_count = 0
    for t in traders:
        generate_wallet_note(t, vault_path)
        wallet_count += 1

    # 3. Write master dashboard note
    master_file = generate_master_dashboard_note(traders, whales, macro, vault_path)

    # 4. Refresh the vault index so it reflects whichever suites live here.
    if CROSS_SUITE_LINKING:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        write_hub_note(vault_path, now_utc)

    return master_file, wallet_count


def main():
    parser = argparse.ArgumentParser(description="Polymarket Monarch Obsidian Vault Synchronizer")
    parser.add_argument("--vault", type=str, default=None, help="Target Obsidian Vault path (defaults to ./obsidian_vault)")
    parser.add_argument("--once", action="store_true", help="Perform a single sync and exit")
    parser.add_argument("--watch", action="store_true", help="Run continuously in background sync mode")
    parser.add_argument("--interval", type=int, default=15, help="Sync interval in seconds when in --watch mode (default: 15)")
    args = parser.parse_args()

    vault_path = get_vault_path(args.vault)
    print(f"👑 Polymarket Monarch Obsidian Synchronizer")
    print(f"📁 Target Obsidian Vault: {vault_path}")

    if args.watch:
        print(f"🔄 Watching SQLite and syncing every {args.interval}s. Press Ctrl+C to stop.\n")
        try:
            while True:
                master_file, count = sync_to_obsidian(args.vault)
                dt = datetime.now().strftime("%H:%M:%S")
                print(f"[{dt}] ✓ Synced master dashboard & {count} trader notes -> {master_file.name}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped Obsidian sync watcher.")
    else:
        master_file, count = sync_to_obsidian(args.vault)
        print(f"✓ Successfully exported master dashboard and {count} trader notes!")
        print(f"📄 Master Note: {master_file}")
        print(f"📂 Wallets Folder: {vault_path / 'Wallets'}")


if __name__ == "__main__":
    main()
