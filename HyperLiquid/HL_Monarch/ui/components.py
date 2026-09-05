"""
Rich UI Components for HL_Monarch Terminal Dashboard.
Sleek, compact, high-density terminal formatters with responsive widths.
"""
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from analytics.market_intelligence import MarketIntelligence

def format_currency(val: float, decimals: int = 2) -> str:
    """Compact USD formatting. Handles negatives, which PnL and equity can be."""
    try:
        val = float(val)
    except (TypeError, ValueError):
        return "$0.00"
    sign = "-" if val < 0 else ""
    mag = abs(val)
    if mag >= 1_000_000_000:
        return f"{sign}${mag / 1_000_000_000:.2f}B"
    elif mag >= 1_000_000:
        return f"{sign}${mag / 1_000_000:.1f}M"
    elif mag >= 1_000:
        return f"{sign}${mag / 1_000:.0f}K"
    else:
        return f"{sign}${mag:.{decimals}f}"

def format_coin_name(coin: str) -> str:
    """Strip verbose dex prefix for compact UI readability."""
    if coin.startswith("xyz:"):
        return coin[4:]
    return coin

# Round 38: derived from REST_POLL_INTERVAL in settings (floor 45s), not fixed here.
from config.settings import STALLED_AFTER_SECONDS  # noqa: E402 - re-exported for the dashboard and tests


def newest_snapshot_age_seconds(snapshots, now: Optional[float] = None) -> Optional[float]:
    """
    Seconds since the newest row in `snapshots` (millisecond timestamps), or
    None when there are no rows to age - a fresh database is not a stall.
    """
    newest = 0.0
    for s in snapshots or ():
        try:
            ts = float(s.get("timestamp") or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
        newest = max(newest, ts)
    if newest <= 0:
        return None
    return max(0.0, (now if now is not None else time.time()) - newest / 1000.0)


COLLECTOR_STATUS_MAX_AGE_SECONDS = 7200.0   # Round 49 (Ruling 49-1): two hours, then the file is history


def append_dashboard_event(path, event: str, **fields) -> bool:
    """
    Append one JSON line {ts, event, pid, ...fields} to the dashboard log
    (Round 49, Ruling 49-1). Never raises: a logging failure must not take
    the viewer down with it. Returns whether the line was written.
    """
    import json
    import os
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": str(event), "pid": os.getpid()}
    record.update(fields)
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        return True
    except Exception:
        return False


def read_collector_status(path, max_age_s: Optional[float] = COLLECTOR_STATUS_MAX_AGE_SECONDS,
                          now: Optional[float] = None) -> Dict[str, Any]:
    """
    The collector's status file as a dict, or {} when absent, unreadable, or
    older than `max_age_s` (default two hours, Round 49) by its own checked_at
    stamp - a dead collector's last write must not keep claiming a badge. Pass
    max_age_s=None to read it regardless of age. Never raises.
    """
    import json
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    if max_age_s is not None:
        try:
            age = (now if now is not None else time.time()) - float(data.get("checked_at") or 0.0)
        except (TypeError, ValueError):
            return {}
        if age > max_age_s:
            return {}
    return data


def novel_dex_badge(unclassified_dexs) -> str:
    """
    Amber header badge naming dexes the settings do not know (Round 48, Ruling
    48-2), or "" when there are none. They are already refused by construction;
    the badge exists so a human classifies them.
    """
    names = sorted({str(n).strip().lower() for n in (unclassified_dexs or ()) if n and str(n).strip()})
    if not names:
        return ""
    return "[bold dark_orange]⚠ NOVEL DEX: %s · refused until classified[/bold dark_orange]" % ", ".join(names)


def watchdog_badge(abandoned: bool, relaunches: int = 0) -> str:
    """
    Round 55 (Directive 55-2): the read-only dashboard's watchdog reached its
    relaunch ceiling (Round 54) and stopped trying. Red, because the only way
    out is a human running the launcher; it clears itself on service_back.
    """
    if not abandoned:
        return ""
    return ("[bold red]⚠ WATCHDOG GAVE UP · %d relaunch(es) left the service dead · run start_collector.bat"
            "[/bold red]" % int(relaunches or 0))


def ingestion_badge(alive: bool, pid, started_read_only, newest_snapshot_age_s: Optional[float] = None):
    """
    (mode, badge markup) for the dashboard header - Round 36, Ruling 3.A.

    `started_read_only` is what the dashboard decided at start-up: None while
    deciding, True if it started as a viewer, False if it started ingesting.
    The states are deliberately distinct: a read-only dashboard whose service
    has DIED is showing stale tables with nothing ingesting, and that must not
    look calm; a standalone dashboard that a service has since joined is
    double-polling until restarted, and must say so.

    Round 37 (cross-check 3.1): a service that is ALIVE BUT NOT WRITING - a hung
    child, a dead socket - is the state a process probe cannot see. It shows as
    STALLED when the newest snapshot is older than STALLED_AFTER_SECONDS, and it
    outranks read-only, because a calm badge over stale tables is the failure.
    """
    if alive:
        if newest_snapshot_age_s is not None and newest_snapshot_age_s > STALLED_AFTER_SECONDS:
            return ("stalled", "[bold red]Service: STALLED (PID %s) · No snapshots written in %ds; "
                               "restart service[/bold red]" % (pid, int(newest_snapshot_age_s)))
        if started_read_only is False:
            return ("dual", "[bold yellow]Service: RUNNING (PID %s) · Standalone ingestion still running - "
                            "restart the dashboard for read-only[/bold yellow]" % pid)
        return "read_only", "[dim]Service: RUNNING (PID %s) · Read-Only Mode[/dim]" % pid
    if started_read_only is True:
        return ("orphaned", "[bold red]Service: STOPPED · No ingestion - tables are going stale; "
                            "run start_collector.bat[/bold red]")
    return "standalone", "[bold yellow]Service: STOPPED · Standalone Ingestion Active[/bold yellow]"


def build_header_panel(total_oi: float, total_vol: float, dex_oi: Dict[str, float], active_tab: str = "ALL",
                       status: str = None) -> Panel:
    """Build compact summary header card with interactive hotkey tabs."""
    now_str = datetime.now().strftime("%H:%M:%S")

    header_text = Text()
    header_text.append("👑 HL_MONARCH ", style="bold gold1")
    header_text.append("│ Hyperliquid & HIP3 TradFi Market Intelligence   ", style="bold cyan")
    header_text.append(f"⏱ {now_str}  │ ", style="dim")
    header_text.append(f"TradFi OI: {format_currency(total_oi)}  │ ", style="bold green")
    header_text.append(f"24h Vol: {format_currency(total_vol)}", style="bold yellow")
    if status:
        header_text.append("  │ ", style="dim")
        header_text.append(Text.from_markup(status))
    header_text.append("\n")
    
    # Navigation hotkeys tabs (8 total)
    tabs = [
        ("1", "ALL", "Core Watch"),
        ("2", "STOCKS", "Stocks (18)"),
        ("3", "COMMODITIES", "Commodities (6)"),
        ("4", "INDICES_FX", "Indices & FX (6)"),
        ("5", "CRYPTO", "Crypto (6)"),
        ("6", "WHALES", "Whale Radar"),
        ("7", "ARB", "Funding Arb"),
        ("8", "PAPER", "Paper Trader"),
    ]
    
    header_text.append("Tabs: ", style="dim")
    for key, tab_id, label in tabs:
        if active_tab == tab_id:
            header_text.append(f" [{key}: {label}] ", style="bold black on bright_yellow")
        else:
            header_text.append(f" [{key}: {label}] ", style="dim cyan")
    
    header_text.append(" │ [Tab/H]: Focus Asset │ [Q]: Exit", style="dim italic yellow")

    return Panel(header_text, box=box.ROUNDED, style="bright_blue", padding=(0, 1))

def build_tradfi_table(snapshots: List[Dict[str, Any]], title: str = "TradFi Watchlist") -> Table:
    """Build high-density structured table of TradFi assets."""
    table = Table(
        title=f"📊 {title}",
        box=box.SIMPLE,
        expand=True,
        header_style="bold magenta",
        title_style="bold bold",
        padding=(0, 1)
    )
    table.add_column("Asset", style="bold white", width=9)
    table.add_column("Price", justify="right", style="bright_yellow", width=10)
    table.add_column("OI ($)", justify="right", style="green", width=9)
    table.add_column("24h Vol", justify="right", style="cyan", width=9)
    table.add_column("1h Fund", justify="right", width=9)
    table.add_column("APR", justify="right", style="bold", width=8)

    for s in snapshots[:15]:
        coin = s.get("coin", "")
        mark_px = float(s.get("mark_px") or 0.0)
        ntl_oi = float(s.get("notional_oi") or 0.0)
        vol = float(s.get("day_ntl_vlm") or 0.0)
        funding = float(s.get("funding_rate") or 0.0)
        funding_apr = MarketIntelligence.calculate_annualized_funding_apr(funding)

        # Price formatting
        if mark_px >= 1000:
            px_str = f"${mark_px:,.1f}"
        elif mark_px >= 1:
            px_str = f"${mark_px:.2f}"
        else:
            px_str = f"${mark_px:.4f}"

        # Funding color
        if funding > 0.0001:
            fund_style = "bright_red"
            apr_style = "bright_red"
        elif funding < -0.0001:
            fund_style = "bright_green"
            apr_style = "bright_green"
        else:
            fund_style = "dim"
            apr_style = "white"

        funding_str = f"{funding * 100:+.3f}%"
        apr_str = f"{funding_apr:+.1f}%"

        table.add_row(
            format_coin_name(coin),
            px_str,
            format_currency(ntl_oi),
            format_currency(vol),
            Text(funding_str, style=fund_style),
            Text(apr_str, style=apr_style)
        )

    return table

def build_liquidations_panel(liquidations: List[Dict[str, Any]], recent_trades: Optional[List[Dict[str, Any]]] = None) -> Panel:
    """Build recent liquidations and whale feed."""
    table = Table(
        box=box.SIMPLE,
        expand=True,
        header_style="bold red",
        padding=(0, 1)
    )
    table.add_column("Time", style="dim", width=8)
    table.add_column("Coin", style="bold white", width=8)
    table.add_column("Side", width=5)
    table.add_column("Price", justify="right", style="yellow", width=9)
    table.add_column("Notional", justify="right", style="bold", width=9)
    table.add_column("Type", style="italic", width=12)

    feed_items = liquidations if liquidations else (recent_trades or [])

    if not feed_items:
        table.add_row("--:--", "SYNC", Text("LIVE", style="cyan"), "$0.00", "$0.00", "Connecting...")
    else:
        for item in feed_items[:8]:
            ts = item.get("time", 0)
            time_str = datetime.fromtimestamp(ts / 1000.0).strftime("%H:%M:%S") if ts else "--"
            coin = item.get("coin", "")
            side = item.get("side", "")
            px = float(item.get("px") or 0.0)
            ntl = float(item.get("notional") or 0.0)
            source = item.get("source", "trade_fill")
            note = item.get("note", "Whale" if ntl >= 25000 else "Live Fill")

            side_text = Text("BUY" if side == "B" else "SELL", style="green" if side == "B" else "red")
            ntl_text = Text(format_currency(ntl), style="bold yellow" if ntl >= 50000 else "white")

            table.add_row(
                time_str,
                format_coin_name(coin),
                side_text,
                f"${px:,.1f}" if px >= 1000 else (f"${px:.2f}" if px >= 1 else f"${px:.4f}"),
                ntl_text,
                (note or source)[:12]
            )

    return Panel(table, title="🔥 Live Liquidations & Whale Flow", box=box.ROUNDED, style="red", padding=(0, 1))

def build_clusters_panel(coin: str, clusters: List[Dict[str, Any]]) -> Panel:
    """Build liquidation price cluster panel with compact ASCII intensity bars."""
    table = Table(
        box=box.SIMPLE,
        expand=True,
        header_style="bold blue",
        padding=(0, 1)
    )
    table.add_column("Lev", style="bold", width=4)
    table.add_column("Side", width=5)
    table.add_column("Target", justify="right", style="yellow", width=9)
    table.add_column("Dist%", justify="right", width=6)
    table.add_column("Est.Vol", justify="right", style="cyan", width=8)
    table.add_column("Wall Intensity", justify="left")

    for c in clusters[:8]:
        side = c.get("side", "")
        is_long = side == "LONG_LIQ"
        side_text = Text("LONG" if is_long else "SHRT", style="green" if is_long else "red")
        
        lev = int(c.get("leverage") or 10)
        est_px = float(c.get("estimated_px") or 0.0)
        filled_blocks = min(8, max(2, int((40 / max(1, lev)) * 2)))
        bar_char = "█" * filled_blocks + "░" * (8 - filled_blocks)
        bar_style = "bright_red" if is_long else "bright_green"
        bar_text = Text(bar_char, style=bar_style)

        table.add_row(
            f"{lev}x",
            side_text,
            f"${est_px:,.1f}" if est_px >= 1000 else f"${est_px:.2f}",
            f"{float(c.get('distance_pct') or 0.0):.1f}%",
            format_currency(c.get("estimated_notional", 0)),
            bar_text
        )

    return Panel(table, title=f"🎯 Liquidation Heatmap ({format_coin_name(coin)})", box=box.ROUNDED, style="blue", padding=(0, 1))

def build_top_wallets_panel(positions: List[Dict[str, Any]]) -> Panel:
    """Build panel displaying top trader accounts closest to liquidation."""
    table = Table(
        box=box.SIMPLE,
        expand=True,
        header_style="bold magenta",
        padding=(0, 1)
    )
    table.add_column("Address", style="dim cyan", width=12)
    table.add_column("Asset", style="bold white", width=6)
    table.add_column("Side", width=5)
    table.add_column("Pos Value", justify="right", style="bold green", width=9)
    table.add_column("Entry", justify="right", style="yellow", width=8)
    table.add_column("Liq Price", justify="right", style="red", width=8)
    table.add_column("Lev", justify="right", width=4)

    if not positions:
        table.add_row("Scanning...", "--", "--", "$0.00", "$0.00", "$0.00", "--")
    else:
        for p in positions[:6]:
            addr = p.get("address", "")
            short_addr = f"{addr[:5]}..{addr[-3:]}" if len(addr) > 10 else addr
            if p.get("is_liquidator"):
                short_addr = f"👑{short_addr}"
            
            is_long = p.get("is_long", True)
            side_text = Text("LONG" if is_long else "SHRT", style="green" if is_long else "red")
            val = float(p.get("position_value") or 0.0)

            table.add_row(
                short_addr,
                format_coin_name(p.get("coin", "")),
                side_text,
                format_currency(val),
                f"${float(p.get('entry_price') or 0):,.1f}",
                f"${float(p.get('liquidation_price') or 0):,.1f}",
                f"{p.get('leverage', 1):.0f}x"
            )

    return Panel(table, title="🐋 Top Trader Positions", box=box.ROUNDED, style="magenta", padding=(0, 1))

def build_funding_arb_panel(arb_data: Dict[str, List[Dict[str, Any]]]) -> Panel:
    """Build high-yield funding rate arbitrage matrix table."""
    table = Table(
        box=box.SIMPLE,
        expand=True,
        header_style="bold cyan",
        padding=(0, 1)
    )
    table.add_column("Asset", style="bold white", width=10)
    table.add_column("Strategy", width=14)
    table.add_column("1h Rate", justify="right", width=9)
    table.add_column("Ann. APR", justify="right", style="bold yellow", width=11)
    table.add_column("Daily Yield", justify="right", style="green", width=11)
    table.add_column("Open Interest", justify="right", style="dim", width=11)
    table.add_column("Spread", justify="right", width=8)
    table.add_column("Action / Hedge", style="italic", width=22)

    shorts = arb_data.get("short_harvest", [])[:5]
    longs = arb_data.get("long_harvest", [])[:5]
    combined = shorts + longs
    rejected_count = len(arb_data.get("rejected", []))

    if not combined:
        table.add_row("--", "NO_ARB", "0.000%", "+0.0%", "+0.00%", "$0.00", "--", "No liquid opportunities")
    else:
        for item in combined:
            is_short = item.get("strategy") == "SHORT_HARVEST"
            strat_text = Text("SHORT YIELD" if is_short else "LONG YIELD", style="bright_red" if is_short else "bright_green")
            apr = item.get("funding_apr", 0)
            daily = item.get("daily_yield_pct", 0)

            # Spread is only populated when a live book check ran for this row.
            spread_bps = item.get("spread_bps")
            if spread_bps is None:
                spread_text = Text("--", style="dim")
            else:
                spread_text = Text(
                    f"{spread_bps:.1f}bp",
                    style="bright_green" if spread_bps <= 10 else ("yellow" if spread_bps <= 25 else "bright_red"),
                )

            table.add_row(
                format_coin_name(item.get("coin", "")),
                strat_text,
                f"{item.get('funding_1h', 0)*100:+.3f}%",
                f"{apr:+.1f}% APR",
                f"{daily:+.2f}% / day",
                format_currency(item.get("notional_oi", 0)),
                spread_text,
                item.get("recommendation", "")[:22]
            )

    title = "📈 Funding Rate Yield Arbitrage Matrix (Liquid Only)"
    if rejected_count:
        title += f" — {rejected_count} filtered for illiquidity"
    return Panel(table, title=title, box=box.ROUNDED, style="cyan", padding=(0, 1))

def build_resting_orders_table(open_orders: List[Dict[str, Any]],
                               ttl_seconds: float = 180.0) -> Table:
    """
    Resting fade limits with a live TTL countdown.

    The countdown is the point: a fade is a bet on *this* cascade reverting, so
    knowing how long an order has left before it self-cancels is what tells you
    whether the thesis is still alive.
    """

    table = Table(box=box.SIMPLE, expand=True, header_style="bold yellow", padding=(0, 1))
    table.add_column("Asset", style="bold white", width=12)
    table.add_column("Side", width=6)
    table.add_column("Size", justify="right", width=11)
    table.add_column("Limit", justify="right", style="yellow", width=11)
    table.add_column("Take Profit", justify="right", style="green", width=11)
    table.add_column("Stop Loss", justify="right", style="red", width=11)
    table.add_column("TTL", justify="right", width=8)

    if not open_orders:
        table.add_row("--", "--", "--", "--", "--", "--", "--")
        return table

    now_ms = int(time.time() * 1000)
    for o in open_orders[:10]:
        remaining = ttl_seconds - (now_ms - int(o.get("placed_at", now_ms))) / 1000.0
        remaining = max(0.0, remaining)
        ttl_style = "bright_red" if remaining < 30 else ("yellow" if remaining < 90 else "green")
        is_buy = o.get("side") == "BUY"
        table.add_row(
            format_coin_name(o.get("coin", "")),
            Text("BUY" if is_buy else "SELL", style="green" if is_buy else "red"),
            f"{float(o.get('size') or 0):,.3f}",
            f"${float(o.get('limit_price') or 0):,.4f}",
            f"${float(o.get('take_profit') or 0):,.4f}" if o.get("take_profit") else "--",
            f"${float(o.get('stop_loss') or 0):,.4f}" if o.get("stop_loss") else "--",
            Text(f"{remaining:>4.0f}s", style=ttl_style),
        )
    return table


def build_paper_trading_panel(
    account_summary: Dict[str, Any],
    positions: Dict[str, Dict[str, Any]],
    recent_fills: List[Dict[str, Any]],
    open_orders: Optional[List[Dict[str, Any]]] = None,
    ttl_seconds: float = 180.0,
) -> Panel:
    """Build live paper trading simulator status and PnL card."""
    realized = account_summary.get("realized_pnl", 0.0)
    unrealized = account_summary.get("total_unrealized_pnl", 0.0)
    ret_pct = account_summary.get("return_pct", 0.0)
    r_style = "bright_green" if realized >= 0 else "bright_red"
    fees = account_summary.get("fees_paid", 0.0)
    gross = account_summary.get("gross_pnl", realized)

    # Hurdle progress, applied by rule from the pre-registered matrix.
    hurdle = account_summary.get("hurdle") or {}
    verdict = hurdle.get("verdict", "PENDING")
    v_style = {
        "PASS": "bold bright_green", "RETUNE": "bold yellow",
        "FAIL": "bold bright_red", "INCONCLUSIVE": "bold yellow",
    }.get(verdict, "dim")
    pf = hurdle.get("profit_factor")
    pf_text = f"{pf:.2f}" if pf is not None else "n/a"

    summary_text = (
        f"[bold cyan]Equity:[/bold cyan] {format_currency(account_summary.get('equity', 0))}  │  "
        f"[bold {r_style}]Net PnL:[/bold {r_style}] ${realized:+,.2f}  │  "
        f"[dim]gross ${gross:+,.2f}[/dim]  │  "
        f"[bold magenta]Fees Paid:[/bold magenta] ${fees:,.2f}  │  "
        f"[bold yellow]Unrealized:[/bold yellow] ${unrealized:+,.2f}  │  "
        f"[bold white]Return:[/bold white] {ret_pct:+.3f}%\n"
        f"[dim]Cash {format_currency(account_summary.get('cash_balance', 0))}  │  "
        f"Open {len(positions)}  │  "
        f"Resting {account_summary.get('open_orders_count', 0)}  │  "
        f"Expired {account_summary.get('expired_orders', 0)}[/dim]\n"
        f"[bold]50-Trade Hurdle:[/bold] [{v_style}]{verdict}[/{v_style}]  "
        f"[dim]{hurdle.get('closed_trades', 0)}/{hurdle.get('trades_required', 50)} closed  │  "
        f"win rate {hurdle.get('win_rate_pct', 0.0):.1f}% (need 54.0%)  │  "
        f"profit factor {pf_text} (need 1.25)  │  "
        f"W{account_summary.get('wins', 0)}/L{account_summary.get('losses', 0)}[/dim]"
    )

    table = Table(
        box=box.SIMPLE,
        expand=True,
        header_style="bold green",
        padding=(0, 1)
    )
    table.add_column("Asset", style="bold white", width=9)
    table.add_column("Side", width=6)
    table.add_column("Size", justify="right", width=10)
    table.add_column("Entry Price", justify="right", style="yellow", width=10)
    table.add_column("Leverage", justify="right", width=6)
    table.add_column("Stop Loss", justify="right", style="red", width=10)
    table.add_column("Take Profit", justify="right", style="green", width=10)

    if not positions:
        table.add_row("--", "--", "0.0", "$0.00", "--", "$0.00", "$0.00")
    else:
        for coin, pos in positions.items():
            is_long = pos["size"] > 0
            side_text = Text("LONG" if is_long else "SHORT", style="green" if is_long else "red")
            sl = pos.get("stop_loss")
            tp = pos.get("take_profit")
            table.add_row(
                format_coin_name(coin),
                side_text,
                f"{abs(pos['size']):,.3f}",
                f"${pos['entry_price']:,.2f}",
                f"{pos['leverage']}x",
                f"${sl:,.2f}" if sl else "None",
                f"${tp:,.2f}" if tp else "None"
            )

    content = Table.grid(expand=True)
    content.add_row(Panel(summary_text, box=box.ROUNDED, style="green", padding=(0, 1)))
    content.add_row(Text("  Open Positions", style="bold green"))
    content.add_row(table)
    content.add_row(Text("  Resting Fade Limits (auto-cancel at TTL)", style="bold yellow"))
    content.add_row(build_resting_orders_table(open_orders or [], ttl_seconds))

    return Panel(content, title="💼 Reactive Liquidation Fade — Paper Account",
                 box=box.ROUNDED, style="green", padding=(0, 1))

