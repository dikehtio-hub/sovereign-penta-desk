"""
================================================================================
Moon Dev Polymarket Whale Monitor
================================================================================
Polls the Moon Dev Quantitative API (/api/poly/whales) for live $1,000+ USD fills
and displays real-time smart-money position shifts across Polymarket.
================================================================================
"""

import os
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Load environment variables
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

API_KEY = os.getenv("MOONDEV_API_KEY", "")
API_URL = os.getenv("MOONDEV_API_URL", "https://api.moondev.com")


def _require_api_key() -> str:
    """Return the Moon Dev API key, or fail loudly with an actionable message.

    Called at request time rather than import time so the module stays
    importable without credentials. Never fall back to a literal key here:
    this file is tracked, and a hardcoded fallback is a published credential.
    """
    if not API_KEY:
        raise RuntimeError(
            "MOONDEV_API_KEY is not set. Add it to "
            "Polymarket/Polymarket_Moondev/.env (gitignored) as\n"
            "    MOONDEV_API_KEY=your_key_here\n"
            "or export it in the environment before running this module."
        )
    return API_KEY

console = Console()


def fetch_whales(min_usd: float = 1000.0, limit: int = 100) -> dict:
    """
    Fetch recent whale trades from Moon Dev API.
    """
    endpoint = f"{API_URL.rstrip('/')}/api/poly/whales"
    headers = {
        "x-api-key": _require_api_key(),
        "User-Agent": "Polymarket-Moondev-WhaleMonitor/1.0",
        "Accept": "application/json"
    }
    params = {
        "min_usd": min_usd,
        "limit": limit
    }

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Whale API Request Error:[/bold red] {e}")
        return {}


def format_usd(val: float) -> str:
    """Format USD currency amount."""
    if val is None:
        return "$0.00"
    return f"${val:,.2f}"


def format_wallet_short(wallet: str) -> str:
    """Shorten wallet address for display."""
    if not wallet or len(wallet) < 10:
        return wallet or "Unknown"
    return f"{wallet[:6]}...{wallet[-4:]}"


def print_banner(min_usd: float, interval: float):
    """Print welcome monitor banner."""
    txt = Text()
    txt.append("🐋 MOON DEV POLYMARKET REAL-TIME WHALE MONITOR\n", style="bold cyan")
    txt.append("Tracking Live Smart-Money Position Shifts >= ", style="bold white")
    txt.append(f"${min_usd:,.0f} USD  ", style="bold green")
    txt.append("|  Poll Interval: ", style="bold white")
    txt.append(f"{interval}s  ", style="bold yellow")
    txt.append("|  Endpoint: ", style="bold white")
    txt.append(f"{API_URL}/api/poly/whales", style="dim")
    console.print(Panel(txt, border_style="cyan", padding=(1, 2)))


def print_whale_trade(trade: dict):
    """Print an individual whale trade in styled terminal card."""
    ts = trade.get("ts")
    if ts:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S UTC")
    else:
        dt = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    market_title = trade.get("market_title", "Unknown Market")
    outcome = trade.get("outcome", "Unknown")
    side = (trade.get("side") or "BUY").upper()
    price = trade.get("price", 0.0)
    size = trade.get("size", 0.0)
    usd = trade.get("usd_amount", 0.0)
    wallet = trade.get("wallet", "")
    pseudonym = trade.get("pseudonym") or "Anonymous"
    tx_hash = trade.get("tx_hash", "")
    slug = trade.get("market_slug", "")

    # Side styling
    if side == "BUY":
        side_style = "bold white on green"
        side_icon = "🟢 BUY "
    else:
        side_style = "bold white on red"
        side_icon = "🔴 SELL"

    # Tiered USD styling
    if usd >= 50_000:
        usd_badge_text = f" 🚨 MEGA WHALE: {format_usd(usd)} "
        usd_badge_style = "bold bright_white on dark_magenta"
    elif usd >= 10_000:
        usd_badge_text = f" ⚡ MAJOR WHALE: {format_usd(usd)} "
        usd_badge_style = "bold bright_yellow on dark_blue"
    else:
        usd_badge_text = f" 🐋 {format_usd(usd)} "
        usd_badge_style = "bold bright_green"

    short_w = format_wallet_short(wallet)
    poly_url = f"https://polymarket.com/market/{slug}" if slug else "https://polymarket.com"
    wallet_url = f"https://polymarket.com/profile/{wallet}" if wallet else ""

    card = Text()
    card.append(f"[{dt}] ", style="dim")
    card.append(f"{side_icon} ", style=side_style)
    card.append(f"  {outcome}  ", style="bold yellow")
    card.append(f"@ ${price:.3f}  ", style="bold white")
    card.append(f"(Size: {size:,.0f} shares)  ", style="dim")
    card.append("-> ")
    card.append(usd_badge_text, style=usd_badge_style)
    card.append("\n")
    card.append("   Market: ", style="bold cyan")
    card.append(f"{market_title}\n", style="bold white")
    card.append("   Trader: ", style="dim")
    card.append(f"{pseudonym} ({short_w})", style="bold cyan")
    if tx_hash:
        card.append("  |  Tx: ", style="dim")
        card.append(f"{tx_hash[:10]}...{tx_hash[-6:]}", style="dim")
    if wallet_url:
        card.append(f"\n   Profile: {wallet_url}", style="underline dim blue")

    console.print(Panel(card, border_style="green" if side == "BUY" else "red", padding=(0, 1)))


def main():
    parser = argparse.ArgumentParser(description="Moon Dev Polymarket Live Whale Monitor")
    parser.add_argument("--min-usd", type=float, default=1000.0, help="Minimum USD fill threshold (default: 1000.0)")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Polling interval in seconds (default: 5.0)")
    parser.add_argument("--limit", type=int, default=50, help="Number of trades to retrieve per poll (default: 50)")
    parser.add_argument("--once", action="store_true", help="Fetch and display recent whales once then exit")

    args = parser.parse_args()

    console.clear()
    print_banner(args.min_usd, args.poll_interval)

    seen_trade_keys = set()
    first_run = True

    try:
        while True:
            data = fetch_whales(min_usd=args.min_usd, limit=args.limit)
            trades = data.get("trades", [])

            # Sort chronological so oldest prints first
            trades_sorted = sorted(trades, key=lambda x: x.get("ts", 0))

            new_trades = []
            for t in trades_sorted:
                key = t.get("tx_hash") or f"{t.get('ts')}_{t.get('wallet')}_{t.get('size')}_{t.get('price')}"
                if key not in seen_trade_keys:
                    seen_trade_keys.add(key)
                    new_trades.append(t)

            if first_run:
                console.print(f"[bold green]Connected! Loaded {len(trades_sorted)} recent whale transactions.[/bold green]")
                console.print("[dim]Displaying most recent 5 trades as initial baseline:[/dim]\n")
                for t in trades_sorted[-5:]:
                    print_whale_trade(t)
                first_run = False
            else:
                if new_trades:
                    console.print(f"\n[bold yellow]⚡ {len(new_trades)} NEW WHALE POSITION SHIFT(S) DETECTED:[/bold yellow]")
                    for t in new_trades:
                        print_whale_trade(t)

            # Prevent memory leak on seen keys
            if len(seen_trade_keys) > 10_000:
                seen_trade_keys = set(list(seen_trade_keys)[-5000:])

            if args.once:
                break

            time.sleep(args.poll_interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Whale monitor stopped by user.[/yellow]")


if __name__ == "__main__":
    main()
