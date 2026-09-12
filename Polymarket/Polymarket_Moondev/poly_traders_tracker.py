"""
================================================================================
Moon Dev Polymarket Profitable Traders Tracker
================================================================================
Fetches and displays top-performing, highly profitable prediction market traders
from the Moon Dev Quantitative API (/api/poly/profitable-traders).

Displays formatted terminal tables with 7-day PnL, volume, trade counts,
and direct 1-click Polymarket profile links.
================================================================================
"""

import os
import sys
import time
import argparse
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
from rich.table import Table
from rich.panel import Panel
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



def fetch_profitable_traders(min_pnl: float = 0.0, limit: int = 50) -> dict:
    """
    Fetch top profitable traders from Moon Dev API.
    """
    endpoint = f"{API_URL.rstrip('/')}/api/poly/profitable-traders"
    headers = {
        "x-api-key": _require_api_key(),
        "User-Agent": "Polymarket-Moondev-Tracker/1.0",
        "Accept": "application/json"
    }

    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]API Connection Error:[/bold red] {e}")
        return {}


def format_currency(val: float) -> str:
    """Format float as currency with commas."""
    if val is None:
        return "$0.00"
    if val >= 1_000_000:
        return f"${val:,.2f}"
    return f"${val:,.2f}"


def format_wallet_short(wallet: str) -> str:
    """Shorten wallet address for display."""
    if not wallet or len(wallet) < 10:
        return wallet or "Unknown"
    return f"{wallet[:6]}...{wallet[-4:]}"


def display_traders_table(data: dict, min_pnl: float = 0.0, limit: int = 25):
    """
    Render a clean, rich CLI table for top profitable traders.
    """
    traders = data.get("traders", [])
    stats = data.get("stats", {})
    updated_at = data.get("updated_at", "N/A")
    total_traders = data.get("total", len(traders))

    # Header Panel
    uptime_h = stats.get("uptime_minutes", 0) / 60.0
    wallets_checked = stats.get("wallets_checked", 0)
    
    header_text = Text()
    header_text.append("🌙 MOON DEV POLYMARKET ALPHA - TOP PROFITABLE TRADERS\n", style="bold cyan")
    header_text.append(f"Wallets Scanned: ", style="bold white")
    header_text.append(f"{wallets_checked:,}  ", style="bold yellow")
    header_text.append(f"|  Profitable Wallets Identified: ", style="bold white")
    header_text.append(f"{total_traders}  ", style="bold green")
    header_text.append(f"|  Engine Uptime: ", style="bold white")
    header_text.append(f"{uptime_h:.1f} hrs  ", style="bold magenta")
    header_text.append(f"|  Updated: ", style="bold white")
    header_text.append(f"{updated_at[:19]} UTC", style="dim")

    console.print(Panel(header_text, border_style="cyan", padding=(1, 2)))

    # Filter traders
    filtered = [t for t in traders if t.get("pnl_7d", 0) >= min_pnl]
    # Sort by 7d PnL descending
    filtered.sort(key=lambda x: x.get("pnl_7d", 0), reverse=True)
    if limit:
        filtered = filtered[:limit]

    if not filtered:
        console.print(f"[yellow]No traders found matching min PnL threshold of ${min_pnl:,.2f}[/yellow]")
        return

    table = Table(
        title="🏆 Top 7-Day Polymarket Smart Money Traders",
        title_style="bold green",
        header_style="bold bold bright_white on dark_blue",
        border_style="blue",
        show_lines=True
    )

    table.add_column("Rank", justify="center", style="bold yellow", width=6)
    table.add_column("Wallet Address", justify="left", style="bold cyan", width=18)
    table.add_column("7D Net PnL", justify="right", style="bold green", width=16)
    table.add_column("7D Volume", justify="right", style="bold white", width=16)
    table.add_column("7D Trades", justify="center", style="bold magenta", width=10)
    table.add_column("Redeems", justify="center", style="dim", width=9)
    table.add_column("Alpha Source", justify="center", style="bold blue", width=14)
    table.add_column("Direct Polymarket Profile Link", justify="left", style="underline cyan")

    for rank, trader in enumerate(filtered, 1):
        wallet = trader.get("wallet", "")
        short_wallet = format_wallet_short(wallet)
        pnl = trader.get("pnl_7d", 0.0)
        volume = trader.get("volume_7d", 0.0)
        trades = trader.get("trades_7d", 0)
        redeems = trader.get("redeems_7d", 0)
        source = trader.get("source", "poly_scan")
        poly_link = trader.get("polymarket_link") or f"https://polymarket.com/profile/{wallet}"

        pnl_style = "bold bright_green" if pnl > 0 else "bold red"
        pnl_text = f"+{format_currency(pnl)}" if pnl > 0 else format_currency(pnl)

        # Highlight top 3 ranks
        if rank == 1:
            rank_str = "🥇 1"
        elif rank == 2:
            rank_str = "🥈 2"
        elif rank == 3:
            rank_str = "🥉 3"
        else:
            rank_str = f"#{rank}"

        table.add_row(
            rank_str,
            short_wallet,
            f"[{pnl_style}]{pnl_text}[/{pnl_style}]",
            format_currency(volume),
            str(trades),
            str(redeems),
            f"[dim]{source}[/dim]",
            poly_link
        )

    console.print(table)
    console.print()


def main():
    parser = argparse.ArgumentParser(description="Moon Dev Polymarket Profitable Traders Tracker")
    parser.add_argument("--limit", type=int, default=25, help="Max number of traders to display (default: 25)")
    parser.add_argument("--min-pnl", type=float, default=0.0, help="Minimum 7-day PnL in USD (default: 0.0)")
    parser.add_argument("--loop", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--interval", type=int, default=60, help="Refresh interval in seconds when looping (default: 60)")

    args = parser.parse_args()

    console.clear()
    console.print("[bold cyan]Connecting to Moon Dev Quantitative Polymarket Intelligence API...[/bold cyan]")

    while True:
        data = fetch_profitable_traders(min_pnl=args.min_pnl, limit=args.limit)
        if data:
            console.clear()
            display_traders_table(data, min_pnl=args.min_pnl, limit=args.limit)
        else:
            console.print("[red]Failed to retrieve profitable traders data.[/red]")

        if not args.loop:
            break

        console.print(f"[dim]Next refresh in {args.interval} seconds... (Press Ctrl+C to stop)[/dim]")
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping tracker.[/yellow]")
            break


if __name__ == "__main__":
    main()
