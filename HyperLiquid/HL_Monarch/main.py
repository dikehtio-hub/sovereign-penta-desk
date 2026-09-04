import sys
from pathlib import Path

# Self-anchor HL_Monarch root to sys.path regardless of execution CWD
MONARCH_DIR = Path(__file__).resolve().parent
if str(MONARCH_DIR) not in sys.path:
    sys.path.insert(0, str(MONARCH_DIR))

import argparse

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def main():
    parser = argparse.ArgumentParser(
        description="HL_Monarch: Hyperliquid & HIP3 TradFi Market Intelligence Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available Commands")

    # Command: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Launch the Live Rich Terminal Dashboard")
    dash_parser.add_argument("--coin", default="xyz:GOLD", help="Focus asset for Liquidation Clusters (default: xyz:GOLD)")
    dash_parser.add_argument("--inline", action="store_true", help="Run dashboard in inline mode without clearing screen")
    dash_parser.add_argument("--once", action="store_true", help="Print a single clean snapshot and exit immediately")

    # Command: collector
    subparsers.add_parser("collector", help="Run the continuous background data ingestion collector")

    # Command: sync
    subparsers.add_parser("sync", help="Perform a one-shot market sync into SQLite")

    # Command: scan (Wallet position scanner)
    scan_parser = subparsers.add_parser("scan", help="Scan active trader wallets for positions closest to liquidation")
    scan_parser.add_argument("--top", type=int, default=20, help="Number of top addresses to scan (default: 20)")
    scan_parser.add_argument("--min-usd", type=float, default=25000.0, help="Minimum position size in USD (default: 25000)")
    scan_parser.add_argument("--danger", type=float, default=None, help="Filter positions with distance to liquidation <= X percent (e.g. --danger 5.0)")

    # Command: inspect (Deep dive inspect single wallet)
    inspect_parser = subparsers.add_parser("inspect", help="Deep-dive inspect an individual trader/whale wallet on-chain")
    inspect_parser.add_argument("address", help="Trader Ethereum address (0x...)")

    # Command: liqs (Query stored liquidations)
    liqs_parser = subparsers.add_parser("liqs", help="Query stored historical liquidation events from SQLite")
    liqs_parser.add_argument("--coin", default=None, help="Filter by coin (e.g. xyz:GOLD, BTC)")
    liqs_parser.add_argument("--limit", type=int, default=25, help="Number of records (default: 25)")

    # Command: whales (View auto-discovered whale wallets)
    whales_parser = subparsers.add_parser("whales", help="List auto-discovered whale wallets and their portfolio metrics")
    whales_parser.add_argument("--limit", type=int, default=20, help="Number of records (default: 20)")

    # Command: arb (Funding rate arbitrage opportunity matrix)
    arb_parser = subparsers.add_parser("arb", help="Scan for extreme funding rate arbitrage yield opportunities")
    arb_parser.add_argument("--min-apr", type=float, default=10.0, help="Minimum annual funding APR threshold (default: 10.0)")
    arb_parser.add_argument("--check-spreads", action="store_true", help="Fetch live order books for top candidates and reject wide spreads")
    arb_parser.add_argument("--min-oi", type=float, default=None, help="Override the open-interest floor in USD (default: 250000)")
    arb_parser.add_argument("--show-rejected", action="store_true", help="Also list opportunities filtered out for illiquidity")

    # Command: paper (Simulated paper trading overview)
    subparsers.add_parser("paper", help="View simulated paper trading balance, open positions, and PnL")

    # Command: test-alert (Send test webhook alert)
    subparsers.add_parser("test-alert", help="Send a test notification to configured Discord/Telegram webhooks")

    # Command: backtest (Replay historical funding harvest)
    bt_parser = subparsers.add_parser("backtest", help="Backtest funding harvest returns over retained snapshot history")
    bt_parser.add_argument("--coin", default=None, help="Backtest a single coin (default: rank all)")
    bt_parser.add_argument("--hours", type=float, default=72.0, help="History window in hours (default: 72)")
    bt_parser.add_argument("--top", type=int, default=15, help="How many coins to rank (default: 15)")
    bt_parser.add_argument("--min-coverage", type=float, default=25.0, help="Minimum observed-time coverage %% to trust a result (default: 25)")
    bt_parser.add_argument("--spot-backed", action="store_true", help="Assume the price leg is hedged (true basis arb)")

    # Command: squeeze (Squeeze & funding exhaustion radar)
    sq_parser = subparsers.add_parser("squeeze", help="Rank perps by squeeze / cascade risk from funding and OI positioning")
    sq_parser.add_argument("--hours", type=float, default=24.0, help="Lookback window in hours (default: 24)")
    sq_parser.add_argument("--top", type=int, default=15, help="How many assets to show (default: 15)")
    sq_parser.add_argument("--all-markets", action="store_true", help="Include spot-backed perps too (default: exotic/no-spot only)")

    # Command: basis (Delta-neutral long spot + short perp funding harvest)
    basis_parser = subparsers.add_parser("basis", help="Scan delta-neutral basis trades: long spot + short perp funding harvest")
    basis_parser.add_argument("--min-apr", type=float, default=None, help="Gross funding APR floor %% (default: 25)")
    basis_parser.add_argument("--min-net-apr", type=float, default=None, help="Net APR floor %% after both legs' spread (default: 15)")
    basis_parser.add_argument("--notional", type=float, default=None, help="USD notional per leg (default: 10,000)")
    basis_parser.add_argument("--days", type=float, default=None, help="Holding period in days used to amortise cost (default: 7)")
    basis_parser.add_argument("--harvest", action="store_true", help="Show the paper harvester book instead of a fresh scan")
    basis_parser.add_argument("--no-spreads", action="store_true", help="Skip live L2 spread checks (net APR then equals gross - the net bar becomes a no-op)")
    basis_parser.add_argument("--unmapped-spot", action="store_true", help="List liquid spot tokens no perp resolves to (a wrapper missing from SPOT_SYMBOL_ALIASES, or nothing to harvest)")

    # Command: excursion (MFE/MAE benchmark on the liquidation entry signal)
    exc_parser = subparsers.add_parser("excursion", help="MFE/MAE excursion benchmark: does the liquidation entry signal have edge?")
    exc_parser.add_argument("--source", default="trade_sweep", help="Event source: trade_sweep (the strategy's), trade_flow, or 'all' (default: trade_sweep)")
    exc_parser.add_argument("--horizons", default="5,15,30", help="Forward windows in minutes (default: 5,15,30)")
    exc_parser.add_argument("--min-notional", type=float, default=0.0, help="Ignore events below this USD notional")
    exc_parser.add_argument("--threshold", type=float, default=1.50, help="MFE/MAE bar for ALPHA_CONFIRMED (default: 1.50)")
    exc_parser.add_argument("--control-multiple", type=int, default=3, help="Random control entries drawn per real event (default: 3)")

    # Command: maintain (Prune retention windows + checkpoint WAL)
    maintain_parser = subparsers.add_parser("maintain", help="Prune expired rows, checkpoint the WAL, and report DB size")
    maintain_parser.add_argument("--vacuum", action="store_true", help="Also VACUUM to return freed pages to the OS")

    # Command: persist (Round 34 - incremental measurement persistence, option b)
    persist_parser = subparsers.add_parser(
        "persist",
        help="Materialise completed basis windows and cascade excursions into the never-pruned "
             "summary tables (the pruner runs one bounded pass of this before every delete)")
    persist_parser.add_argument("--backfill", action="store_true",
                                help="Loop passes until every watermark is caught up (default: one bounded pass)")
    persist_parser.add_argument("--status", action="store_true",
                                help="Report watermarks, spans, regimes and the Ruling D precondition; write nothing")
    persist_parser.add_argument("--hold", type=float, default=None,
                                help="Print the entry-conditioned walk-forward for this hold (hours) from the persisted windows")
    persist_parser.add_argument("--excursions", action="store_true",
                                help="Print MFE/MAE per horizon from the persisted rows, against the persisted control")
    persist_parser.add_argument("--source", default="trade_sweep",
                                help="Excursion source for --excursions (default: trade_sweep)")
    persist_parser.add_argument("--max-passes", type=int, default=500, help="Backfill pass cap (default: 500)")

    # Command: summary
    summary_parser = subparsers.add_parser("summary", help="Print an instant TradFi snapshot table to console")
    summary_parser.add_argument("--dex", default="xyz", help="Target DEX (default: xyz)")

    # Command: obsidian
    obs_parser = subparsers.add_parser("obsidian", help="Export live HyperLiquid intelligence into an Obsidian Vault")
    obs_parser.add_argument("--vault", default=None, help="Target Obsidian Vault path")
    obs_parser.add_argument("--once", action="store_true", help="Perform single export and exit")
    obs_parser.add_argument("--watch", action="store_true", help="Continuous background sync watcher daemon")
    obs_parser.add_argument("--interval", type=int, default=15, help="Sync interval in seconds (default: 15)")

    # Command: test-order  (Round 19 live pre-flight harness)
    to_parser = subparsers.add_parser(
        "test-order",
        help="Construct, gate and display ONE order without sending it (pre-flight)")
    to_parser.add_argument("--coin", default="BTC", help="Coin to price (default: BTC)")
    to_parser.add_argument("--sz", default="0.001",
                           help="Size as a decimal STRING (default: 0.001)")
    to_parser.add_argument("--px", default=None,
                           help="Limit price as a decimal STRING (required)")
    to_parser.add_argument("--sell", action="store_true", help="Sell instead of buy")
    # Both safety defaults are ON, and each has to be turned off by name. There is
    # deliberately no single flag that does both.
    to_parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                           default=True, help="Do not submit (DEFAULT)")
    to_parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                           help="Actually submit the order")
    to_parser.add_argument("--testnet", dest="testnet", action="store_true",
                           default=True, help="Sign for testnet (DEFAULT)")
    to_parser.add_argument("--mainnet", dest="testnet", action="store_false",
                           help="Sign for MAINNET - real money")
    to_parser.add_argument("--confirm", default=None,
                           help='Required for a live mainnet order: "SEND IT LIVE"')

    args = parser.parse_args()

    if args.command == "dashboard" or args.command is None:
        from ui.terminal_dashboard import TerminalDashboard
        focus = getattr(args, "coin", "xyz:GOLD") or "xyz:GOLD"
        dashboard = TerminalDashboard(focus_asset=focus)
        if getattr(args, "once", False):
            dashboard.print_snapshot()
        else:
            dashboard.start(fullscreen=not getattr(args, "inline", False))

    elif args.command == "collector":
        from collectors.market_collector import start_collector
        print("Starting HL_Monarch Market Ingestion Collector (Ctrl+C to stop)...")
        start_collector()

    elif args.command == "sync":
        import asyncio
        from collectors.market_collector import MarketCollector
        collector = MarketCollector()
        print("Synchronizing Hyperliquid universes and contexts...")
        asyncio.run(collector._sync_universe_metadata())
        print("Sync complete.")

    elif args.command == "whales":
        from storage.repository import MarketRepository
        from ui.components import format_currency
        from rich.console import Console
        from rich.table import Table
        from rich import box
        from datetime import datetime

        console = Console()
        repo = MarketRepository()
        whales = repo.get_whale_wallets(limit=args.limit)

        table = Table(
            title="🐋 Auto-Discovered Whale Wallets",
            box=box.ROUNDED,
            header_style="bold cyan",
            title_style="bold magenta"
        )
        table.add_column("Address", style="dim cyan", width=16)
        table.add_column("Discovered At", style="dim", width=10)
        table.add_column("Trigger Asset", style="bold white", width=12)
        table.add_column("Trigger Fill", justify="right", style="yellow", width=12)
        table.add_column("Account Value", justify="right", style="bold green", width=14)
        table.add_column("Open Positions", justify="right", style="bold yellow", width=14)
        table.add_column("Role", justify="center", width=10)

        if not whales:
            table.add_row("No whales recorded yet", "--", "--", "$0.00", "$0.00", "$0.00", "--")
        else:
            for w in whales:
                addr = w.get("address", "")
                short_addr = f"{addr[:6]}...{addr[-4:]}"
                disc_ts = w.get("discovered_at", 0)
                disc_str = datetime.fromtimestamp(disc_ts / 1000.0).strftime("%H:%M:%S") if disc_ts else "--"
                coin = w.get("first_coin", "")
                fill_val = float(w.get("first_notional", 0))
                acc_val = float(w.get("account_value", 0))
                pos_val = float(w.get("total_position_value", 0))
                is_liq = bool(w.get("is_liquidator", 0))

                table.add_row(
                    short_addr,
                    disc_str,
                    coin,
                    format_currency(fill_val),
                    format_currency(acc_val) if acc_val > 0 else "Scanning...",
                    format_currency(pos_val) if pos_val > 0 else "--",
                    "👑 Liquidator" if is_liq else "Trader"
                )
        console.print(table)

    elif args.command == "inspect":
        from analytics.position_scanner import PositionScanner
        from ui.components import format_currency, format_coin_name
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from rich import box

        console = Console()
        scanner = PositionScanner()
        addr = args.address
        print(f"Fetching full on-chain clearinghouse portfolio for {addr}...")
        wallet_info = scanner.inspect_wallet(addr)
        if not wallet_info:
            console.print("[bold red]Failed to retrieve wallet information. Please verify address.[/bold red]")
        else:
            role = "👑 Hyperliquid System Liquidator" if wallet_info["is_liquidator"] else "Active Trader"
            summary_text = (
                f"[bold cyan]Address:[/bold cyan] {wallet_info['address']}\n"
                f"[bold green]Account Equity:[/bold green] {format_currency(wallet_info['account_value'])}  │  "
                f"[bold yellow]Total Open Positions:[/bold yellow] {format_currency(wallet_info['total_position_value'])}  │  "
                f"[bold magenta]Margin Used:[/bold magenta] {format_currency(wallet_info['margin_used'])}  │  "
                f"[bold blue]Role:[/bold blue] {role}"
            )
            console.print(Panel(summary_text, title="🐋 Whale Account Profile", box=box.ROUNDED, style="bright_cyan"))

            table = Table(
                title=f"📊 Open Position Breakdown ({len(wallet_info['positions'])} Active)",
                box=box.SIMPLE_HEAVY,
                header_style="bold magenta"
            )
            table.add_column("Asset", style="bold white", width=10)
            table.add_column("Side", width=7)
            table.add_column("Size", justify="right", width=12)
            table.add_column("Position Value", justify="right", style="bold green", width=15)
            table.add_column("Entry Price", justify="right", style="yellow", width=12)
            table.add_column("Liq Price", justify="right", style="red", width=12)
            table.add_column("Liq Dist %", justify="right", width=10)
            table.add_column("Unrealized PnL", justify="right", style="bold", width=15)
            table.add_column("Lev", justify="right", width=6)

            if not wallet_info["positions"]:
                table.add_row("--", "--", "0.0", "$0.00", "$0.00", "$0.00", "--", "$0.00", "--")
            else:
                for p in wallet_info["positions"]:
                    is_long = p["is_long"]
                    side_text = Text("LONG" if is_long else "SHORT", style="green" if is_long else "red")
                    pnl = p["unrealized_pnl"]
                    pnl_style = "bright_green" if pnl >= 0 else "bright_red"
                    dist = p["distance_pct"]
                    dist_style = "bold red" if dist <= 5.0 else ("yellow" if dist <= 15.0 else "green")

                    table.add_row(
                        format_coin_name(p["coin"]),
                        side_text,
                        f"{abs(p['size']):,.4f}",
                        format_currency(p["position_value"]),
                        f"${p['entry_price']:,.2f}",
                        f"${p['liquidation_price']:,.2f}" if p['liquidation_price'] > 0 else "None",
                        Text(f"{dist:.1f}%" if dist < 900 else "--", style=dist_style),
                        Text(f"${pnl:+,.2f}", style=pnl_style),
                        f"{p['leverage']:.0f}x"
                    )
            console.print(table)

    elif args.command == "scan":
        from analytics.position_scanner import PositionScanner
        from ui.components import build_top_wallets_panel
        from rich.console import Console
        console = Console()
        scanner = PositionScanner()
        target_addrs = scanner.addresses[:args.top]
        danger_text = f" (Distance <= {args.danger}%)" if args.danger is not None else ""
        print(f"Scanning top {len(target_addrs)} wallets from data/hyperliquidusers.txt for positions >= ${args.min_usd:,.2f}{danger_text}...")
        positions = scanner.scan_batch(target_addrs, min_value_usd=args.min_usd, max_danger_dist_pct=args.danger)
        panel = build_top_wallets_panel(positions)
        console.print(panel)

    elif args.command == "liqs":
        from storage.repository import MarketRepository
        from ui.components import build_liquidations_panel
        from rich.console import Console
        console = Console()
        repo = MarketRepository()
        liqs = repo.get_recent_liquidations(limit=args.limit)
        if args.coin:
            liqs = [l for l in liqs if l.get("coin") == args.coin]
        trades = repo.get_recent_trades(coin=args.coin, limit=args.limit)
        panel = build_liquidations_panel(liqs, trades)
        console.print(panel)

    elif args.command == "arb":
        from analytics.funding_arbitrage import FundingArbitrageEngine
        from ui.components import build_funding_arb_panel
        from rich.console import Console
        console = Console()
        engine = FundingArbitrageEngine()
        from config.settings import ARB_MIN_NOTIONAL_OI
        min_oi = args.min_oi if args.min_oi is not None else ARB_MIN_NOTIONAL_OI
        extra = " (with live spread checks)" if args.check_spreads else ""
        print(f"Scanning 436 perpetual markets across all DEXes for funding yields >= {args.min_apr}% APR{extra}...")
        arb_data = engine.scan_funding_opportunities(
            min_apr_pct=args.min_apr,
            min_notional_oi=min_oi,
            check_spreads=args.check_spreads,
        )
        panel = build_funding_arb_panel(arb_data)
        console.print(panel)

        if args.show_rejected and arb_data.get("rejected"):
            from rich.table import Table
            from rich import box
            rej = Table(title="⚠️  Filtered Out (illiquid / untradeable)", box=box.SIMPLE, header_style="bold yellow")
            rej.add_column("Asset", style="bold white", width=18)
            rej.add_column("Funding APR", justify="right", width=13)
            rej.add_column("Why rejected", style="dim")
            for item in arb_data["rejected"][:15]:
                rej.add_row(item["coin"], f"{item['funding_apr']:+.1f}%", item.get("reject_reason") or "--")
            console.print(rej)

    elif args.command == "paper":
        from execution.paper_trader import PaperTrader
        from storage.repository import MarketRepository
        from ui.components import build_paper_trading_panel
        from rich.console import Console
        console = Console()
        from config.settings import FADE_ORDER_TTL_SECONDS
        # Load the account the collector has been writing to. Constructing a fresh
        # PaperTrader here would always report a flat account no matter what the
        # strategy actually did - the two run in different processes.
        trader = PaperTrader.load()
        repo = MarketRepository()
        snapshots = repo.get_latest_snapshots()
        prices = {s["coin"]: float(s.get("mark_px", 0)) for s in snapshots}
        summary = trader.get_account_summary(prices)
        panel = build_paper_trading_panel(
            summary, trader.positions, trader.trade_history,
            open_orders=trader.open_orders, ttl_seconds=FADE_ORDER_TTL_SECONDS,
        )
        console.print(panel)
        if not trader.positions and not trader.open_orders and not trader.trade_history:
            console.print(
                "[dim]No paper activity yet. The reactive fade engine runs inside the "
                "collector - start it with launch_service_background.bat and it will "
                "place fades as liquidation sweeps print.[/dim]"
            )

    elif args.command == "test-alert":
        from analytics.alerter import WebhookAlerter
        from rich.console import Console
        console = Console()
        alerter = WebhookAlerter()
        if not alerter.enabled:
            console.print("[bold yellow]⚠️ No DISCORD_WEBHOOK_URL or TELEGRAM_BOT_TOKEN set in environment.[/bold yellow]")
            console.print("To configure, set environment variable:\n  $env:DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...'")
        else:
            console.print("[bold green]Sending test alert to configured webhooks...[/bold green]")
            alerter.alert_whale_trade("xyz:GOLD", "BUY", 4468.50, 250000.0, is_liq=False)
            console.print("[bold green]✓ Test alert dispatched![/bold green]")

    elif args.command == "backtest":
        from analytics.funding_backtester import (
            backtest_funding_harvest, rank_funding_backtests, summarise_coverage,
        )
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
        console = Console()

        if args.coin:
            r = backtest_funding_harvest(args.coin, hours=args.hours, is_spot_backed=args.spot_backed)
            if not r["samples"]:
                console.print(f"[bold red]No snapshot history for {args.coin} in the last {args.hours}h.[/bold red]")
            else:
                # Suppressed below the coverage gate, so render the label instead.
                apr_text = (
                    f"{r['realised_apr']:+.1f}%" if r["realised_apr"] is not None
                    else f"[yellow]{r['realised_apr_label']}[/yellow]"
                )
                body = (
                    f"[bold cyan]Coin:[/bold cyan] {r['coin']}   "
                    f"[bold]Side:[/bold] {r['side'] or '--'}   "
                    f"[bold]Hedged:[/bold] {'yes' if r['is_spot_backed'] else 'no'}\n"
                    f"[bold green]Funding PnL:[/bold green] {r['funding_pnl_pct']:+.4f}%   "
                    f"[bold yellow]Price PnL:[/bold yellow] {r['price_pnl_pct']:+.2f}%   "
                    f"[bold magenta]Net:[/bold magenta] {r['net_pnl_pct']:+.2f}%\n"
                    f"[bold]Realised APR:[/bold] {apr_text}\n"
                    f"[dim]Observed {r['observed_hours']:.2f}h of {r['requested_hours']:.0f}h "
                    f"({r['coverage_pct']:.1f}% coverage, {r['gap_hours']:.2f}h of gaps, "
                    f"{r['samples']} samples)[/dim]"
                )
                console.print(Panel(body, title=f"📉 Funding Harvest Backtest — {args.coin}", box=box.ROUNDED, style="cyan"))
                if r["coverage_pct"] < args.min_coverage:
                    console.print(
                        f"[bold yellow]⚠️  Only {r['coverage_pct']:.1f}% of the window was observed. "
                        f"Run the collector continuously for a trustworthy backtest.[/bold yellow]"
                    )
        else:
            results = rank_funding_backtests(
                hours=args.hours, top_n=args.top,
                min_coverage_pct=args.min_coverage, is_spot_backed=args.spot_backed,
            )
            table = Table(
                title=f"📉 Realised Funding Harvest — last {args.hours:.0f}h",
                box=box.ROUNDED, header_style="bold cyan",
            )
            table.add_column("Coin", style="bold white", width=16)
            table.add_column("Side", width=6)
            table.add_column("Funding PnL", justify="right", style="bold green", width=12)
            table.add_column("Price PnL", justify="right", width=11)
            table.add_column("Net PnL", justify="right", style="bold", width=11)
            table.add_column("Coverage", justify="right", style="dim", width=9)
            table.add_column("Realised APR", justify="right", style="yellow", width=13)

            if not results:
                table.add_row("--", "--", "--", "--", "--", "--", "--")
                console.print(table)
                console.print(
                    "[bold yellow]No coin met the coverage threshold.[/bold yellow] The retained history is "
                    "too sparse to backtest — this needs the collector running continuously, not in bursts.\n"
                    "Lower the bar with [bold]--min-coverage 1[/bold] to inspect what data exists."
                )
            else:
                for r in results:
                    table.add_row(
                        r["coin"], r["side"] or "--",
                        f"{r['funding_pnl_pct']:+.4f}%",
                        f"{r['price_pnl_pct']:+.2f}%",
                        f"{r['net_pnl_pct']:+.2f}%",
                        f"{r['coverage_pct']:.1f}%",
                        f"{r['realised_apr']:+.1f}%" if r["realised_apr"] is not None
                        else f"[dim]{r['realised_apr_label']}[/dim]",
                    )
                console.print(table)
                cov = summarise_coverage(results)
                console.print(
                    f"[dim]{cov['coins']} coins · mean coverage {cov['mean_coverage_pct']:.1f}% · "
                    f"longest observed window {cov['observed_hours']:.1f}h[/dim]"
                )

    elif args.command == "basis":
        from execution.strategies.basis_strategy import scan_basis_opportunities, format_report
        from config.settings import (
            BASIS_MIN_FUNDING_APR, BASIS_MIN_NET_APR,
            BASIS_NOTIONAL_USD, BASIS_HOLDING_DAYS,
        )
        kwargs = {
            "min_funding_apr": args.min_apr if args.min_apr is not None else BASIS_MIN_FUNDING_APR,
            "min_net_apr": args.min_net_apr if args.min_net_apr is not None else BASIS_MIN_NET_APR,
            "notional_usd": args.notional if args.notional is not None else BASIS_NOTIONAL_USD,
            "holding_days": args.days if args.days is not None else BASIS_HOLDING_DAYS,
            "check_spreads": not args.no_spreads,
        }
        if args.unmapped_spot:
            from analytics.funding_arbitrage import FundingArbitrageEngine, effective_spot_min_volume
            engine = FundingArbitrageEngine()
            rows = engine.get_unmapped_liquid_spot()
            floor = effective_spot_min_volume()
            print()
            print(f"LIQUID SPOT TOKENS NO PERP RESOLVES TO  (24h pair volume >= ${floor:,.0f})")
            if engine.get_spot_volumes() is None:
                print("  spot volume lookup failed - nothing can be said")
            elif not rows:
                print("  none: every liquid spot token is reachable from some perp")
            else:
                print(f"  {'TOKEN':<10}{'24H VOLUME':>16}")
                for r in rows:
                    print(f"  {r['token']:<10}{r['day_volume']:>16,.0f}")
            print("  A row is either a wrapper missing from SPOT_SYMBOL_ALIASES (verify its fullName on the")
            print("  live token list before adding it) or an asset with no perp - nothing to harvest.")
            print()
            return
        if args.harvest:
            from execution.basis_harvester import BasisHarvester, format_report as harvest_report
            from analytics.funding_arbitrage import FundingArbitrageEngine
            h = BasisHarvester()
            h.load()
            # One request, so dead spot legs are tagged [ILLIQUID SPOT]; a failed
            # lookup prints the book untagged rather than claiming anything.
            volumes = None
            try:
                volumes = FundingArbitrageEngine().get_spot_volumes()
            except Exception:
                volumes = None
            print(harvest_report(h, spot_volumes=volumes))
            return
        print("Scanning for delta-neutral basis trades (long spot + short perp)...")
        print(format_report(scan_basis_opportunities(**kwargs)))

    elif args.command == "excursion":
        from analytics.wick_benchmark import benchmark, format_report
        horizons = tuple(float(x) for x in args.horizons.split(",") if x.strip())
        sources = ["trade_sweep", "trade_flow"] if args.source == "all" else [args.source]
        print(f"Walking historical liquidation events over {args.horizons}m forward windows...")
        results = [benchmark(source=s, horizons=horizons, min_notional=args.min_notional,
                             control_multiple=args.control_multiple) for s in sources]
        print(format_report(results, alpha_threshold=args.threshold))

    elif args.command == "squeeze":
        from analytics.squeeze_engine import scan_squeeze_candidates, summarise_squeeze
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text
        from rich import box
        console = Console()
        scope = "all markets" if args.all_markets else "exotic perps (no spot leg)"
        print(f"Scanning {scope} for squeeze / cascade positioning over the last {args.hours:.0f}h...")
        rows = scan_squeeze_candidates(
            hours=args.hours, top_n=args.top, exotic_only=not args.all_markets
        )
        summary = summarise_squeeze(rows)

        table = Table(
            title=f"🌀 Squeeze & Exhaustion Matrix — {summary['short_squeeze']} squeeze / {summary['long_cascade']} cascade",
            box=box.ROUNDED, header_style="bold cyan",
        )
        table.add_column("Asset", style="bold white", width=16)
        table.add_column("Score", justify="right", style="bold", width=6)
        table.add_column("Intensity", width=12)
        table.add_column("Classification", width=24)
        table.add_column("Fund %ile", justify="right", width=10)
        table.add_column("OI Change", justify="right", width=11)
        table.add_column("Funding APR", justify="right", style="yellow", width=13)

        if not rows:
            table.add_row("--", "--", "--", "Not enough history — run the collector", "--", "--", "--")
        else:
            for r in rows:
                filled = max(0, min(10, int(r["squeeze_score"] / 10)))
                bar = Text("█" * filled + "░" * (10 - filled),
                           style="bright_red" if r["squeeze_score"] >= 80 else "yellow")
                cls = r["classification"]
                style = "bright_green" if "SQUEEZE" in cls else ("bright_red" if "CASCADE" in cls else "dim")
                table.add_row(
                    r["coin"], f"{r['squeeze_score']:.1f}", bar,
                    Text(cls, style=style),
                    f"{r['funding_percentile']:.0f}th",
                    f"{r['oi_expansion_pct']:+.1f}%",
                    f"{r['current_funding_apr']:+.1f}%",
                )
        console.print(table)
        console.print("[dim]Positioning stress, not a trade signal: it scores how stretched a crowd is, not when it breaks.[/dim]")

    elif args.command == "maintain":
        from storage.repository import MarketRepository
        from ui.components import format_currency
        from rich.console import Console
        console = Console()
        repo = MarketRepository()
        before = repo.db.page_size_bytes()
        console.print(f"[cyan]Database before:[/cyan] {before / 1_048_576.0:,.1f} MB")
        stats = repo.run_maintenance(vacuum=args.vacuum)
        for table, count in stats["deleted"].items():
            console.print(f"  pruned [bold]{count:,}[/bold] rows from {table}")
        console.print(
            f"[green]WAL checkpoint:[/green] {max(0, stats['checkpointed_pages']):,} pages"
            f"{' (reader busy, partial)' if stats['wal_busy'] else ''}"
        )
        console.print(f"[bold green]Database after:[/bold green] {stats['db_bytes'] / 1_048_576.0:,.1f} MB")

    elif args.command == "persist":
        from storage.repository import MarketRepository
        from storage.incremental_persistence import (
            backfill, entry_conditioned_summary, excursion_summary, format_entry_conditioned,
            format_excursions, format_status, persist_completed_measurements, persistence_status)
        repo = MarketRepository()
        conn = repo.db.connection
        if not args.status:
            if args.backfill:
                def progress(r):
                    print("  pass: %d windows, %d events, %d controls in %.1fs%s" % (
                        r["windows_written"], r["events_written"], r["controls_written"],
                        r["elapsed_s"], "" if r["pending"] else " - caught up"), flush=True)
                print("Backfilling measurements from the retained window...", flush=True)
                result = backfill(conn, progress=progress, max_passes=args.max_passes,
                                  max_grid_points=8, max_events=5000)
                print("%d pass(es): %d windows, %d events, %d controls, %.1fs%s" % (
                    result["passes"], result["windows_written"], result["events_written"],
                    result["controls_written"], result["elapsed_s"],
                    "" if result["caught_up"] else " - NOT caught up (pass cap hit)"))
            else:
                r = persist_completed_measurements(conn)
                print("one pass: %d windows, %d events, %d controls in %.1fs%s" % (
                    r["windows_written"], r["events_written"], r["controls_written"],
                    r["elapsed_s"], " (more pending)" if r["pending"] else ""))
        print(format_status(persistence_status(conn)))
        if args.hold:
            print(format_entry_conditioned(entry_conditioned_summary(conn, args.hold)))
        if args.excursions:
            print(format_excursions(excursion_summary(conn, args.source)))

    elif args.command == "summary":
        from api.rest_client import HyperliquidRestClient
        from ui.components import build_tradfi_table
        from rich.console import Console
        
        console = Console()
        client = HyperliquidRestClient()
        print(f"Fetching live snapshot for DEX '{args.dex}'...")
        res = client.get_meta_and_asset_ctxs(dex=args.dex)
        if res and len(res) >= 2:
            universe = res[0].get("universe", [])
            ctxs = res[1]
            snapshots = []
            for u, c in zip(universe, ctxs):
                coin = f"{args.dex}:{u['name']}" if args.dex != "main" and not u['name'].startswith(f"{args.dex}:") else u['name']
                mark = float(c.get("markPx") or c.get("oraclePx") or 0.0)
                oi = float(c.get("openInterest") or 0.0)
                snapshots.append({
                    "coin": coin,
                    "mark_px": mark,
                    "notional_oi": oi * mark,
                    "day_ntl_vlm": float(c.get("dayNtlVlm") or 0.0),
                    "funding_rate": float(c.get("funding") or 0.0)
                })
            snapshots.sort(key=lambda x: x["notional_oi"], reverse=True)
            table = build_tradfi_table(snapshots[:25], title=f"Top 25 Assets in DEX '{args.dex}'")
            console.print(table)
        else:
            print("Failed to retrieve market data.")

    elif args.command == "test-order":
        from execution.preflight import (LIVE_CONFIRMATION_PHRASE, build_preflight,
                                         confirm_live, render_preflight)
        if not args.px:
            print("[ERROR] --px is required. A pre-flight order needs an explicit "
                  "limit price; there is no sensible default for one.")
            return
        if not confirm_live(network_is_mainnet=not args.testnet, dry_run=args.dry_run,
                            typed=args.confirm):
            print(f'[BLOCKED] A live MAINNET order needs '
                  f'--confirm "{LIVE_CONFIRMATION_PHRASE}". Nothing was signed.')
            return
        report = build_preflight(coin=args.coin, sz=str(args.sz), px=str(args.px),
                                 is_buy=not args.sell, testnet=args.testnet,
                                 dry_run=args.dry_run)
        print(render_preflight(report))

    elif args.command == "obsidian":
        from analytics.obsidian_exporter import export_hyperliquid_to_obsidian, run_obsidian_sync_loop
        if getattr(args, "watch", False):
            run_obsidian_sync_loop(args.vault, interval=args.interval)
        else:
            out_file = export_hyperliquid_to_obsidian(args.vault)
            print(f"✓ Exported HyperLiquid intelligence note to Obsidian: {out_file}")

if __name__ == "__main__":
    main()
