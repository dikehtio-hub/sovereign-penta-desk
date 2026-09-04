"""
👑 HL_Monarch - Obsidian Interactive Command Cockpit & Exporter
Exports Hyperliquid & HIP-3 TradFi market intelligence, funding rate arbitrage,
whale accounts, liquidation alerts, live bot telemetry, risk controllers, and trading terminal.

Usage:
  python main.py obsidian --once                   # One-shot export to ./obsidian_vault
  python main.py obsidian --vault "C:/path/vault"  # Export to custom Obsidian Vault
  python main.py obsidian --watch --interval 15    # Continuous synchronization daemon
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

MONARCH_DIR = Path(__file__).resolve().parent.parent
if str(MONARCH_DIR) not in sys.path:
    sys.path.insert(0, str(MONARCH_DIR))

from storage.repository import MarketRepository
from config.settings import (
    HL_SYSTEM_LIQUIDATOR_ADDRESSES,
    ARB_MIN_NOTIONAL_OI,
    ARB_MIN_DAY_VOLUME,
    DATA_DIR,
    PAPER_STATE_PATH,
    BASIS_PAPER_STATE_PATH,
)
from config.dynamic_config import DynamicConfigManager, get_dynamic_config
from analytics.funding_arbitrage import FundingArbitrageEngine
from analytics.obsidian_links import (
    HL_DASHBOARD_NOTE,
    PM_DASHBOARD_NOTE,
    QL_DASHBOARD_NOTE,
    HUB_NOTE,
    BOT_CONTROL_NOTE,
    BOT_CONFIG_NOTE,
    TRADING_TERMINAL_NOTE,
    HL_WHALES_DIR,
    USER_NOTES_HEADER,
    counterpart_link,
    note_exists,
    preserve_user_notes,
    wikilink,
    write_hub_note,
    SPORTS_DESK_NOTE,
    CROSS_MARKET_ARB_NOTE,
    write_note_if_changed,
    make_progress_bar,
)

DEV_ROOT = Path("C:/Users/ixis1/Desktop/DEV")
DEFAULT_VAULT_DIR = (DEV_ROOT / "obsidian_vault") if (DEV_ROOT / "obsidian_vault").exists() else (MONARCH_DIR / "obsidian_vault")
LAUNCHERS_DIR = MONARCH_DIR / "scripts" / "launchers"

DEFAULT_WHALE_NOTES_TEMPLATE = """
*Add your custom notes, trading thesis, tags, or strategy analysis for this account below:*
- **Style**:
- **Tags**: #hyperliquid #whale
- **Thesis**:
"""

DEFAULT_CONTROL_NOTES_TEMPLATE = """
*Log operational notes, maintenance schedules, and incident post-mortems below:*
- **Operator Notes**: 
"""


def get_vault_path(custom_path: Optional[str] = None) -> Path:
    """Resolve target Obsidian vault path."""
    if custom_path:
        p = Path(custom_path).expanduser().resolve()
    elif os.environ.get("OBSIDIAN_VAULT_PATH"):
        p = Path(os.environ["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()
    else:
        p = DEFAULT_VAULT_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def format_usd(val: float) -> str:
    """Compact USD formatting. Keeps the sign - PnL and equity can be negative."""
    try:
        val = float(val)
    except (TypeError, ValueError):
        return "$0.00"
    sign = "-" if val < 0 else ""
    mag = abs(val)
    if mag >= 1_000_000_000:
        return f"{sign}${mag / 1_000_000_000:.2f}B"
    if mag >= 1_000_000:
        return f"{sign}${mag / 1_000_000:.2f}M"
    if mag >= 1_000:
        return f"{sign}${mag / 1_000:.1f}K"
    return f"{sign}${mag:,.2f}"


def format_apr(apr: float) -> str:
    sign = "+" if apr > 0 else ""
    return f"`{sign}{apr:.2f}%`"


def short_address(addr: str) -> str:
    return f"{addr[:6]}...{addr[-4:]}" if len(addr) > 12 else addr


def liquidation_side_label(side: str) -> str:
    s = (side or "").strip().upper()
    if s in ("A", "SELL", "ASK", "SHORT"):
        return "🟢 **LONG LIQ**"
    if s in ("B", "BUY", "BID", "LONG"):
        return "🔴 **SHORT LIQ**"
    return "⚪ **UNKNOWN**"


def interleave_opportunities(
    short_harvest: List[Dict[str, Any]],
    long_harvest: List[Dict[str, Any]],
    limit: int,
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for i in range(max(len(short_harvest), len(long_harvest))):
        if i < len(short_harvest):
            merged.append(short_harvest[i])
        if i < len(long_harvest):
            merged.append(long_harvest[i])
        if len(merged) >= limit:
            break
    return merged[:limit]


# --- Service Telemetry Helper ----------------------------------------------

def get_service_telemetry() -> Dict[str, Any]:
    """Inspect background daemons via PID lockfiles and database timestamps."""
    collector_pid_file = DATA_DIR / "collector.pid"
    service_pid_file = DATA_DIR / "collector_service.pid"
    db_file = DATA_DIR / "hyperliquid_data.db"
    poly_db_file = MONARCH_DIR.parent.parent / "Polymarket" / "Polymarket_Monarch" / "data" / "polymarket_whales.db"

    collector_running = False
    collector_pid = "—"
    if collector_pid_file.exists():
        try:
            pid_str = collector_pid_file.read_text().strip()
            collector_pid = pid_str
            collector_running = True
        except Exception:
            pass
    elif service_pid_file.exists():
        try:
            pid_str = service_pid_file.read_text().strip()
            collector_pid = pid_str
            collector_running = True
        except Exception:
            pass

    db_mtime_ago = "—"
    if db_file.exists():
        try:
            diff_s = time.time() - db_file.stat().st_mtime
            db_mtime_ago = f"{int(diff_s)}s ago" if diff_s >= 0 else "0s ago"
        except Exception:
            pass

    poly_mtime_ago = "—"
    poly_active = False
    if poly_db_file.exists():
        try:
            diff_s = time.time() - poly_db_file.stat().st_mtime
            poly_mtime_ago = f"{int(diff_s)}s ago" if diff_s >= 0 else "0s ago"
            poly_active = diff_s < 300
        except Exception:
            pass

    return {
        "collector_running": collector_running,
        "collector_pid": collector_pid,
        "db_freshness": db_mtime_ago,
        "poly_freshness": poly_mtime_ago,
        "poly_active": poly_active,
    }


# --- Note Generators -------------------------------------------------------

def generate_bot_control_note(vault_path: Path, synced_at: str) -> Tuple[Path, bool]:
    """Generate the Bot_Control.md interactive activation deck note."""
    file_path = vault_path / f"{BOT_CONTROL_NOTE}.md"
    telemetry = get_service_telemetry()
    cfg = get_dynamic_config(vault_path=vault_path)

    collector_badge = "🟢 **ONLINE (PID: " + telemetry["collector_pid"] + ")**" if telemetry["collector_running"] else "⚪ **OFFLINE (IDLE)**"
    poly_badge = "🟢 **SYNCED (" + telemetry["poly_freshness"] + ")**" if telemetry["poly_active"] else "⚪ **IDLE (" + telemetry["poly_freshness"] + ")**"
    kill_badge = "🚨 **ENGAGED (HALTED)**" if cfg.emergency_killswitch else "🟢 **ARMED (NORMAL)**"
    pause_badge = "⏸️ **PAUSED**" if cfg.pause_new_entries else "🟢 **ACCEPTING ENTRIES**"

    pm_link_row = f"- [[{PM_DASHBOARD_NOTE}|🌐 Polymarket Intelligence]]\n" if note_exists(vault_path, PM_DASHBOARD_NOTE) else ""
    ql_link_row = f"- [[{QL_DASHBOARD_NOTE}|⚡ Quant Trading Lab]]\n" if note_exists(vault_path, QL_DASHBOARD_NOTE) else ""
    user_notes = preserve_user_notes(file_path, DEFAULT_CONTROL_NOTES_TEMPLATE)
    launchers_uri = LAUNCHERS_DIR.as_uri()

    content = f"""---
title: Monarch Bot Control & Activation Deck
tags:
  - monarch
  - bot-control
  - operations
  - launchers
last_synced: "{synced_at}"
---

# 🎮 Monarch Bot Control & Activation Deck

> [!INFO] **Live Service Telemetry & Operational State**
> - **HyperLiquid Ingestion Collector**: {collector_badge} • SQLite DB Updated: `{telemetry['db_freshness']}`
> - **Polymarket Engine**: {poly_badge}
> - **Active Risk Preset**: `{cfg.active_preset.upper()}` • Capital Per Leg: `${cfg.basis_notional_usd:,.0f}`
> - **Execution State**: {pause_badge} • Kill-Switch: {kill_badge}
> - **Last Synchronized**: `{synced_at}`

---

## 🚀 1-Click Windows Launchers Deck

> [!TIP] **Execution Instructions**
> Click any launcher link below to execute the corresponding standalone Windows batch script in `scripts/launchers/`.

| Service / Action | Description | Primary Launcher | Stop / Reset |
| :--- | :--- | :---: | :---: |
| ⚡ **Master Tri-Market Sync** | Start ALL 3 sync exporters (HL + Polymarket + Quant Lab) | [🚀 Start All Sync]({launchers_uri}/start_all_ecosystem_sync.bat) | [🛑 Stop All Sync]({launchers_uri}/stop_all_ecosystem_sync.bat) |
| 🏛 **HyperLiquid Collector** | 436 Market perp ingestion daemon & orderbook watcher | [▶ Start Collector]({launchers_uri}/start_collector.bat) | [⏹ Stop Collector]({launchers_uri}/stop_collector.bat) |
| 🔄 **Obsidian Sync Watcher** | Real-time vault background synchronizer (15s loop) | [▶ Start Sync]({launchers_uri}/start_obsidian_sync.bat) | [⏹ Stop Sync]({launchers_uri}/stop_obsidian_sync.bat) |
| 🌐 **Polymarket Daemon** | Sharp trader PnL scanner & whale trade collector | [▶ Start Polymarket]({launchers_uri}/start_poly_monarch.bat) | [⏹ Stop Polymarket]({launchers_uri}/stop_poly_monarch.bat) |
| 📊 **Rich Terminal Dashboard** | Fullscreen institutional TUI terminal | [🖥️ Launch Dashboard]({launchers_uri}/open_dashboard.bat) | — |
| 📈 **Delta-Neutral Basis Scan** | Scan live spot-hedged funding harvest opportunities | [⚡ Run Basis Scan]({launchers_uri}/run_basis_scan.bat) | — |
| 🎯 **Polymarket PnL Scanner** | Scan 7-day realized/unrealized sharp trader rankings | [⚡ Run PnL Scan]({launchers_uri}/run_pnl_scan.bat) | — |

---

## 🎛️ Dynamic Risk Presets & Safety Actions

| Action | Impact | Launcher Script |
| :--- | :--- | :---: |
| 🛡️ **Apply Conservative Preset** | $5k Notional, 1 Slot, 35% Gross / 25% Net APR Floor | [🛡️ Apply Conservative]({launchers_uri}/apply_preset_conservative.bat) |
| ⚖️ **Apply Balanced Preset** | $10k Notional, 2 Slots, 25% Gross / 20% Net APR Floor | [⚖️ Apply Balanced]({launchers_uri}/apply_preset_balanced.bat) |
| ⚔️ **Apply Aggressive Preset** | $25k Notional, 4 Slots, 18% Gross / 14% Net APR Floor | [⚔️ Apply Aggressive]({launchers_uri}/apply_preset_aggressive.bat) |
| 🚨 **EMERGENCY KILL-SWITCH** | Instantly halts new entries and cancels resting orders | [🚨 TRIGGER EMERGENCY STOP]({launchers_uri}/emergency_killswitch.bat) |
| ⏸️ **Pause New Entries** | Keeps existing positions active but prevents new opens | [⏸️ Pause Entries]({launchers_uri}/pause_new_entries.bat) |
| 🟢 **Resume Entries** | Clears pause & killswitch, restoring execution | [▶ Resume Entries]({launchers_uri}/resume_entries.bat) |

---

## 🔗 Cockpit Navigation

- [[Monarch_Hub|👑 Monarch Intelligence Hub]]
- [[Bot_Config|⚙️ Bot Configuration & Risk Controller]]
- [[Trading_Terminal|📈 Live Trading Terminal & 50-Trade Hurdle]]
- [[HyperLiquid_Monarch|🏛 HyperLiquid Market Dashboard]]
{pm_link_row}{ql_link_row}---

{USER_NOTES_HEADER}
{user_notes.strip()}
"""
    _, was_written = write_note_if_changed(file_path, content.rstrip() + "\n")
    return file_path, was_written


def generate_trading_terminal_note(vault_path: Path, synced_at: str) -> Tuple[Path, bool]:
    """Generate the Trading_Terminal.md note tracking account telemetry and the 50-trade hurdle."""
    file_path = vault_path / f"{TRADING_TERMINAL_NOTE}.md"

    # Read basis paper state if present
    basis_state_file = Path(BASIS_PAPER_STATE_PATH)
    basis_state: Dict[str, Any] = {}
    if basis_state_file.exists():
        try:
            basis_state = json.loads(basis_state_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Read general paper trader state if present
    paper_state_file = Path(PAPER_STATE_PATH)
    paper_state: Dict[str, Any] = {}
    if paper_state_file.exists():
        try:
            paper_state = json.loads(paper_state_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    cash = float(basis_state.get("cash", basis_state.get("starting_cash", 100_000.0)))
    starting = float(basis_state.get("starting_cash", 100_000.0))
    realized_pnl = float(basis_state.get("realized_pnl", 0.0))
    fees_paid = float(basis_state.get("fees_paid", 0.0))
    funding_collected = float(basis_state.get("funding_collected", 0.0))
    positions = basis_state.get("positions", {})
    closed_trades = basis_state.get("closed", [])
    open_orders = paper_state.get("open_orders", [])

    # Hurdle metrics
    closed_count = len(closed_trades)
    wins = sum(1 for t in closed_trades if float(t.get("realized_pnl", 0)) > 0)
    win_rate = (wins / closed_count * 100.0) if closed_count > 0 else 0.0

    gross_gains = sum(float(t.get("realized_pnl", 0)) for t in closed_trades if float(t.get("realized_pnl", 0)) > 0)
    gross_losses = abs(sum(float(t.get("realized_pnl", 0)) for t in closed_trades if float(t.get("realized_pnl", 0)) < 0))
    profit_factor = (gross_gains / gross_losses) if gross_losses > 0 else (99.9 if gross_gains > 0 else 0.0)

    # Hurdle Verdict
    if closed_count >= 50:
        if win_rate >= 54.0 and profit_factor >= 1.25:
            verdict_badge = "🟢 **PASS (EDGE VALIDATED - READY FOR LIVE DEPLOYMENT)**"
        elif win_rate >= 48.0:
            verdict_badge = "🟡 **RETUNE (MARGINAL EDGE - RETUNE PARAMETERS)**"
        else:
            verdict_badge = "🔴 **FAIL (NO EDGE - SYSTEM REJECTED)**"
    else:
        verdict_badge = f"🔵 **IN PROGRESS ({closed_count}/50 TRADES COMPLETED)**"

    hurdle_bar = make_progress_bar(closed_count, 50, length=15)
    win_bar = make_progress_bar(win_rate, 100, length=10)

    # Build Open Positions Table
    pos_rows = []
    deployed_capital = sum(float(p.get("capital") or (float(p.get("notional_per_leg", 0.0)) * 2)) for p in positions.values())
    total_equity = cash + deployed_capital
    for coin, pos in positions.items():
        ntl = format_usd(float(pos.get("notional_per_leg", 0.0)))
        spot_px = float(pos.get("spot_entry_px") or pos.get("entry_mark") or 0.0)
        perp_px = float(pos.get("perp_entry_px") or pos.get("entry_mark") or 0.0)
        spot_str = f"${spot_px:,.2f}" if spot_px >= 1.0 else f"${spot_px:.4f}"
        perp_str = f"${perp_px:,.2f}" if perp_px >= 1.0 else f"${perp_px:.4f}"
        entry_apr = format_apr(float(pos.get("entry_funding_apr", 0.0)))
        accrued = float(pos.get("funding_collected") or pos.get("funding_accrued") or 0.0)
        accrued_str = f"+${accrued:,.2f}" if accrued > 0 else f"${accrued:,.2f}"
        opened_at = pos.get("opened_at", 0)
        dur = f"{(time.time() - opened_at) / 3600:.1f}h" if opened_at else "—"
        pos_rows.append(f"| **`{coin}`** | {ntl} | `{spot_str}` | `{perp_str}` | {entry_apr} | **`{accrued_str}`** | `{dur}` |")
    pos_table = "\n".join(pos_rows) if pos_rows else "| — | — | — | — | — | *No active open delta-neutral basis positions.* | — |"

    # Build Resting Orders Table
    order_rows = []
    for o in open_orders:
        coin = o.get("coin", "")
        side = o.get("side", "")
        px = float(o.get("price", 0.0))
        sz = float(o.get("size", 0.0))
        ntl = format_usd(px * sz)
        placed_at = float(o.get("placed_at", time.time()))
        ttl = max(0, int(180 - (time.time() - placed_at)))
        order_rows.append(f"| **`{coin}`** | `{side}` | `${px:,.2f}` | `{sz:.4f}` | {ntl} | `{ttl}s remaining` |")
    order_table = "\n".join(order_rows) if order_rows else "| — | — | — | — | — | *No resting limit orders active.* |"

    # Build Closed Trades Table
    closed_rows = []
    for t in closed_trades[-10:]:
        coin = t.get("coin", "")
        pnl = format_usd(float(t.get("realized_pnl", 0.0)))
        pnl_badge = f"🟢 **{pnl}**" if float(t.get("realized_pnl", 0.0)) > 0 else f"🔴 **{pnl}**"
        dur = f"{float(t.get('hold_duration_hours', 0.0)):.1f}h"
        reason = t.get("exit_reason", "normal_close")
        closed_rows.append(f"| **`{coin}`** | {pnl_badge} | `{dur}` | `{reason}` |")
    closed_table = "\n".join(closed_rows) if closed_rows else "| — | — | *No closed trades logged yet.* | — |"

    pm_link_row = f"- [[{PM_DASHBOARD_NOTE}|🌐 Polymarket Intelligence]]\n" if note_exists(vault_path, PM_DASHBOARD_NOTE) else ""
    ql_link_row = f"- [[{QL_DASHBOARD_NOTE}|⚡ Quant Trading Lab]]\n" if note_exists(vault_path, QL_DASHBOARD_NOTE) else ""

    content = f"""---
title: Monarch Trading Terminal & 50-Trade Hurdle Tracker
tags:
  - monarch
  - trading-terminal
  - hurdle-tracker
  - execution-telemetry
last_synced: "{synced_at}"
---

# 📈 Monarch Trading Terminal & 50-Trade Hurdle Tracker

> [!INFO] **Account Telemetry Snapshot**
> - **Total Account Equity**: **`{format_usd(total_equity)}`** (Starting: `{format_usd(starting)}`)
> - **Available Cash Balance**: **`{format_usd(cash)}`** • Deployed Collateral: **`{format_usd(deployed_capital)}`**
> - **Net Realized Yield / PnL**: **`+{format_usd(realized_pnl)}`**
> - **Accrued Funding Yield**: **`+{format_usd(funding_collected)}`**
> - **Total Execution Fees Paid**: `{format_usd(fees_paid)}` (Net of maker/taker accounting)
> - **Last Synchronized**: `{synced_at}`

---

## 🎯 Pre-Registered 50-Trade Hurdle Validation Deck

> [!IMPORTANT] **Rigorous Statistical Hurdle Bar**
> To prevent deploying curve-fitted strategies to live capital, the engine must satisfy our pre-registered acceptance criteria over **50 discrete closed trades**:
> - **Hurdle 1**: Win Rate **`>= 54.0%`** (Net of fees)
> - **Hurdle 2**: Profit Factor **`>= 1.25`**
> - **Current Verdict**: {verdict_badge}

| Hurdle Metric | Current Value | Required PASS Floor | Validation Progress |
| :--- | :---: | :---: | :--- |
| **Sample Size** | **`{closed_count} trades`** | `50 trades` | {hurdle_bar} |
| **Win Rate** | **`{win_rate:.1f}%`** | `>= 54.0%` | {win_bar} |
| **Profit Factor** | **`{profit_factor:.2f}`** | `>= 1.25` | `Gross: {format_usd(gross_gains)} / Loss: {format_usd(gross_losses)}` |

---

## 📊 Active Delta-Neutral Basis Positions

| Asset | Leg Size | Spot Entry | Perp Entry | Entry APR | Funding Accrued | Duration |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
{pos_table}

---

## ⏳ Resting Limit Order Book (TTL Countdown)

| Asset | Side | Limit Price | Units | Notional | Order Expiration |
| :--- | :---: | :---: | :---: | :---: | :---: |
{order_table}

---

## 📜 Recent Closed Trades History

| Asset | Net Realized PnL | Holding Period | Exit Classification |
| :--- | :---: | :---: | :--- |
{closed_table}

---

## 🔗 Cockpit Navigation

- [[Monarch_Hub|👑 Monarch Intelligence Hub]]
- [[Bot_Control|🎮 Bot Control & Activation Deck]]
- [[Bot_Config|⚙️ Bot Configuration & Risk Controller]]
- [[HyperLiquid_Monarch|🏛 HyperLiquid Market Dashboard]]
{pm_link_row}{ql_link_row}---
*Generated automatically by Monarch Execution Exporter.*
"""
    _, was_written = write_note_if_changed(file_path, content.rstrip() + "\n")
    return file_path, was_written


def generate_whale_note(whale: Dict[str, Any], vault_path: Path, synced_at: str) -> Tuple[Path, bool]:
    whales_dir = vault_path / HL_WHALES_DIR
    whales_dir.mkdir(parents=True, exist_ok=True)

    addr = str(whale.get("address", "")).lower()
    file_path = whales_dir / f"{addr}.md"

    equity = float(whale.get("account_value") or 0.0)
    pos_val = float(whale.get("total_position_value") or 0.0)
    first_coin = whale.get("first_coin") or "—"
    first_ntl = float(whale.get("first_notional") or 0.0)
    is_system_liquidator = addr in HL_SYSTEM_LIQUIDATOR_ADDRESSES
    no_liq_price = bool(whale.get("is_liquidator", 0))
    discovered_at = whale.get("discovered_at", 0)
    disc_str = (
        datetime.fromtimestamp(discovered_at / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if discovered_at else "—"
    )
    role = "👑 Hyperliquid System Liquidator" if is_system_liquidator else "Active Trader"
    margin_note = (
        "No liquidation price on open positions (well collateralised)"
        if no_liq_price else "Carries a liquidation price"
    )
    leverage = (pos_val / equity) if equity > 0 else 0.0

    user_notes = preserve_user_notes(file_path, DEFAULT_WHALE_NOTES_TEMPLATE)
    pm_link = counterpart_link(vault_path, PM_DASHBOARD_NOTE, "Polymarket Monarch")
    cross_row = (
        f"\n> [!NOTE] **Cross-Suite**\n"
        f"> If this address also trades prediction markets, link its {pm_link} trader note here.\n"
        if pm_link else ""
    )

    content = f"""---
title: Whale {short_address(addr)}
address: "{addr}"
account_value: {equity}
total_position_value: {pos_val}
first_coin: "{first_coin}"
is_system_liquidator: {str(is_system_liquidator).lower()}
no_liquidation_price: {str(no_liq_price).lower()}
discovered_at: "{disc_str}"
last_synced: "{synced_at}"
tags:
  - hyperliquid
  - whale
---

# 🐋 Hyperliquid Whale: {short_address(addr)}

> [!INFO] **Account Overview**
> - **Address**: `{addr}`
> - **Role**: **{role}**
> - **Explorer**: [View on Hyperliquid](https://app.hyperliquid.xyz/explorer/address/{addr})
> - **First Seen**: `{disc_str}`
> - **Last Updated**: `{synced_at}`
{cross_row}
---

## 📊 Portfolio Metrics

| Metric | Value | Context |
| :--- | :--- | :--- |
| **Account Equity** | **`{format_usd(equity)}`** | Total collateral held |
| **Open Position Size** | `{format_usd(pos_val)}` | Notional exposure across all perps |
| **Effective Leverage** | `{leverage:.2f}x` | Position size ÷ equity |
| **Discovery Trade** | `{format_usd(first_ntl)}` on `{first_coin}` | Fill that surfaced this account |
| **Margin Status** | `{margin_note}` | From last portfolio scan |

---

## 🔗 Related

- {wikilink(HL_DASHBOARD_NOTE, 'HyperLiquid Monarch Dashboard')}
- {wikilink(BOT_CONTROL_NOTE, 'Bot Control Deck')}
- Inspect live: `python main.py inspect {addr}`

---

{USER_NOTES_HEADER}{user_notes}"""

    _, written = write_note_if_changed(file_path, content.rstrip() + "\n")
    return file_path, written


def export_hyperliquid_to_obsidian(
    vault_path_str: Optional[str] = None,
    repo: Optional[MarketRepository] = None,
    write_whale_notes: bool = True,
) -> Path:
    """Generate all HyperLiquid notes, Bot Control, Config, and Terminal notes inside the vault."""
    vault_path = get_vault_path(vault_path_str)
    repo = repo or MarketRepository()
    arb_engine = FundingArbitrageEngine()
    cfg = get_dynamic_config(vault_path=vault_path)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    master_file = vault_path / f"{HL_DASHBOARD_NOTE}.md"

    # 1. Fetch Market Snapshots
    snapshots = repo.get_latest_snapshots()
    tradfi_snaps = [s for s in snapshots if str(s.get("coin", "")).startswith("xyz:")]
    tradfi_snaps.sort(key=lambda x: float(x.get("day_ntl_vlm") or 0.0), reverse=True)

    # 2. Fetch Funding Arbitrage Opportunities
    arb_results = arb_engine.scan_funding_opportunities(
        min_apr_pct=cfg.basis_min_funding_apr,
        snapshots=snapshots
    )
    short_harvest = arb_results.get("short_harvest", [])
    long_harvest = arb_results.get("long_harvest", [])
    arb_rejected = arb_results.get("rejected", [])
    arb_total = len(short_harvest) + len(long_harvest)
    arb_opps = interleave_opportunities(short_harvest, long_harvest, limit=10)

    # 3. Fetch Whale Wallets
    whales = repo.get_whale_wallets(limit=30)

    # 4. Fetch Recent Liquidations
    liqs = repo.get_recent_liquidations(limit=15)

    # 5. Generate Individual Whale Notes
    whale_notes: Dict[str, Path] = {}
    whales_written = 0
    if write_whale_notes:
        for w in whales:
            addr = str(w.get("address", "")).lower()
            if addr:
                note_path, was_written = generate_whale_note(w, vault_path, now_utc)
                whale_notes[addr] = note_path
                whales_written += int(was_written)

    # Build TradFi Table
    tradfi_rows = []
    for s in tradfi_snaps[:15]:
        coin = s.get("coin", "")
        mark_px = float(s.get("mark_px") or 0.0)
        px_str = f"`${mark_px:,.2f}`" if mark_px >= 1.0 else f"`${mark_px:.4f}`"
        oi = format_usd(float(s.get("notional_oi") or 0.0))
        vol = format_usd(float(s.get("day_ntl_vlm") or 0.0))
        fr = float(s.get("funding_rate") or 0.0)
        apr = fr * 24 * 365 * 100.0
        tradfi_rows.append(f"| **`{coin}`** | {px_str} | {oi} | {vol} | {format_apr(apr)} |")
    tradfi_table = "\n".join(tradfi_rows) if tradfi_rows else "| — | — | *No active TradFi market data.* | — | — |"

    # Build Funding Arb Table
    arb_rows = []
    for opp in arb_opps:
        coin = opp.get("coin", "")
        apr = float(opp.get("funding_apr") or 0.0)
        strat = opp.get("recommendation", "Long Perp / Short Spot" if apr < 0 else "Short Perp / Long Spot")
        strat_badge = "🟢 **Long Yield**" if apr < 0 else "🔴 **Short Yield**"
        oi = format_usd(float(opp.get("notional_oi") or 0.0))
        arb_rows.append(f"| **`{coin}`** | {format_apr(apr)} | {strat_badge} | {oi} | {strat} |")
    arb_table = "\n".join(arb_rows) if arb_rows else "| — | — | — | — | *No liquid funding arbitrage opportunities currently.* |"

    # Build Whales Table
    whale_rows = []
    for w in whales[:10]:
        addr = str(w.get("address", "")).lower()
        label = short_address(addr)
        cell = wikilink(f"{HL_WHALES_DIR}/{addr}", label) if addr in whale_notes else f"`{label}`"
        equity = format_usd(float(w.get("account_value") or 0.0))
        pos_val = format_usd(float(w.get("total_position_value") or 0.0))
        coin = w.get("first_coin") or "—"
        role = "👑" if addr in HL_SYSTEM_LIQUIDATOR_ADDRESSES else ""
        whale_rows.append(f"| {cell} {role} | **{equity}** | {pos_val} | `{coin}` |")
    whale_table = "\n".join(whale_rows) if whale_rows else "| — | — | — | *No whale wallets discovered yet.* |"

    # Build Liquidations Table
    liq_rows = []
    for l in liqs[:10]:
        t_ms = l.get("time", 0)
        dt_str = datetime.fromtimestamp(t_ms / 1000, tz=timezone.utc).strftime("%H:%M:%S") if t_ms else "—"
        coin = l.get("coin", "")
        side_badge = liquidation_side_label(l.get("side"))
        sz = format_usd(float(l.get("notional") or 0.0))
        px = float(l.get("px") or 0.0)
        px_str = f"`${px:,.2f}`" if px >= 1.0 else f"`${px:.4f}`"
        liq_rows.append(f"| {dt_str} | **`{coin}`** | {side_badge} | {sz} | {px_str} |")
    liq_table = "\n".join(liq_rows) if liq_rows else "| — | — | — | *No recent liquidations recorded.* | — |"

    # Squeeze Table
    squeeze_rows = []
    squeeze_summary = {"scanned": 0, "short_squeeze": 0, "long_cascade": 0}
    try:
        from analytics.squeeze_engine import scan_squeeze_candidates, summarise_squeeze
        squeeze = scan_squeeze_candidates(snapshots=snapshots, top_n=10)
        squeeze_summary = summarise_squeeze(squeeze)
        for sq in squeeze:
            bar_len = max(0, min(10, int(sq["squeeze_score"] / 10)))
            bar = "█" * bar_len + "░" * (10 - bar_len)
            squeeze_rows.append(
                f"| **`{sq['coin']}`** | `{sq['squeeze_score']:.1f}` {bar} | {sq['classification']} | "
                f"`{sq['funding_percentile']:.0f}th` | {sq['oi_expansion_pct']:+.1f}% | "
                f"{format_apr(sq['current_funding_apr'])} |"
            )
    except Exception as e:
        squeeze_rows = [f"| — | — | *Squeeze engine unavailable: {e}* | — | — | — |"]
    squeeze_table = "\n".join(squeeze_rows) if squeeze_rows else (
        "| — | — | *Not enough snapshot history yet.* | — | — | — |"
    )

    # Cross-suite navigation
    pm_link = counterpart_link(vault_path, PM_DASHBOARD_NOTE, "👑 Polymarket Monarch")
    ql_link = counterpart_link(vault_path, QL_DASHBOARD_NOTE, "⚡ Quant Trading Lab")
    hub_link = wikilink(HUB_NOTE, "👑 Monarch Intelligence Hub")
    ctrl_link = wikilink(BOT_CONTROL_NOTE, "🎮 Bot Control")
    cfg_link = wikilink(BOT_CONFIG_NOTE, "⚙️ Bot Config")
    term_link = wikilink(TRADING_TERMINAL_NOTE, "📈 Trading Terminal")

    sports_link = counterpart_link(vault_path, SPORTS_DESK_NOTE, "🏈 Sports Desk")
    xarb_link = counterpart_link(vault_path, CROSS_MARKET_ARB_NOTE, "⚖️ Cross-Market Arb")
    nav_parts = [hub_link, ctrl_link, cfg_link, term_link]
    if pm_link:
        nav_parts.append(pm_link)
    if ql_link:
        nav_parts.append(ql_link)
    if sports_link:
        nav_parts.append(sports_link)
    if xarb_link:
        nav_parts.append(xarb_link)
    nav_line = "> **Cockpit Navigation**: " + " • ".join(nav_parts)

    content = f"""---
title: HyperLiquid Monarch TradFi & Crypto Intelligence
tags:
  - hyperliquid
  - tradfi
  - hip3
  - perp-dex
  - dashboard
last_synced: "{now_utc}"
---

# 👑 HyperLiquid Monarch • Market Intelligence

{nav_line}

> [!INFO] **Perpetual DEX Terminal Status**
> - **Last Synchronized**: `{now_utc}`
> - **Active Risk Preset**: `{cfg.active_preset.upper()}` • Capital Allocation: `${cfg.basis_notional_usd:,.0f} / leg`
> - **HIP-3 TradFi Universe (xyz DEX)**: `{len(tradfi_snaps)}` Active Markets
> - **Discovered Whale Accounts**: `{len(whales)}` Tracked (`{len(whale_notes)}` linked notes)
> - **Funding Rate Arbitrage Opportunities**: `{arb_total}` liquid pairs (> {cfg.basis_min_funding_apr:.0f}% APR), `{len(arb_rejected)}` filtered as illiquid

---

## 🏛 HIP-3 TradFi Markets (Stocks, Commodities, Indices)

| Asset | Mark Price | Open Interest | 24h Volume | Funding APR |
| :--- | :---: | :---: | :---: | :---: |
{tradfi_table}

---

## 📈 Funding Rate Arbitrage Yield Opportunities
*Screened for tradeability: open interest >= {int(ARB_MIN_NOTIONAL_OI):,} USD and 24h volume >= {int(ARB_MIN_DAY_VOLUME):,} USD.*

| Asset | Funding APR | Direction | Open Interest | Strategy Recommendation |
| :--- | :---: | :---: | :---: | :--- |
{arb_table}

---

## 🐋 Discovered Whale Wallets & Portfolio Exposure
*Click any address to open its dedicated research note.*

| Address | Account Equity | Total Position Size | Primary Asset |
| :--- | :---: | :---: | :---: |
{whale_table}

---

## 🌀 Squeeze & Exhaustion Matrix
*Positioning stress on perps with **no spot leg**. `{squeeze_summary['short_squeeze']}` squeeze / `{squeeze_summary['long_cascade']}` cascade watches.*

| Asset | Squeeze Score | Classification | Funding %ile | OI Change | Funding APR |
| :--- | :--- | :---: | :---: | :---: | :---: |
{squeeze_table}

---

## 🔥 Recent Liquidation Events

| Time (UTC) | Coin | Position Side | Liquidated Notional | Execution Price |
| :---: | :--- | :---: | :---: | :---: |
{liq_table}

---
*Generated automatically by HL_Monarch Obsidian Exporter.*
"""
    _, master_written = write_note_if_changed(master_file, content.strip() + "\n")

    # 6. Generate Cockpit Companion Notes
    generate_bot_control_note(vault_path, now_utc)
    DynamicConfigManager(vault_path=vault_path)._write_config_note(cfg)
    generate_trading_terminal_note(vault_path, now_utc)

    # 7. Refresh Hub Note
    write_hub_note(vault_path, now_utc)

    export_hyperliquid_to_obsidian.last_write_stats = {
        "master_written": master_written,
        "whale_notes": len(whale_notes),
        "whales_written": whales_written,
        "whales_skipped": len(whale_notes) - whales_written,
    }
    return master_file


def run_obsidian_sync_loop(vault_path_str: Optional[str] = None, interval: int = 15):
    vault_path = get_vault_path(vault_path_str)
    repo = MarketRepository()
    interval = max(1, int(interval))
    print("👑 HL_Monarch Obsidian Interactive Command Cockpit Synchronizer")
    print(f"📁 Target Vault: {vault_path}")
    if note_exists(vault_path, PM_DASHBOARD_NOTE):
        print("🔗 Shared vault detected - cross-linking with Polymarket Monarch.")
    print(f"🔄 Syncing intelligence & cockpit notes every {interval}s (Press Ctrl+C to stop)...\n")
    try:
        while True:
            try:
                file_path = export_hyperliquid_to_obsidian(vault_path_str, repo=repo)
                stats = getattr(export_hyperliquid_to_obsidian, "last_write_stats", {})
                skipped = stats.get("whales_skipped", 0)
                churn = f" ({skipped} unchanged notes skipped)" if skipped else ""
                dt = datetime.now().strftime("%H:%M:%S")
                print(f"[{dt}] ✓ Synced Command Cockpit & Market Dashboard -> {file_path.name}{churn}")
            except Exception as e:
                dt = datetime.now().strftime("%H:%M:%S")
                print(f"[{dt}] ⚠ Sync failed, retrying next tick: {e}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped Obsidian sync watcher.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HL_Monarch Obsidian Exporter")
    parser.add_argument("--vault", type=str, default=None, help="Target Obsidian Vault path")
    parser.add_argument("--once", action="store_true", help="One-shot sync and exit")
    parser.add_argument("--watch", action="store_true", help="Continuous background sync loop")
    parser.add_argument("--interval", type=int, default=15, help="Interval in seconds for watch mode")
    args = parser.parse_args()

    if args.watch:
        run_obsidian_sync_loop(args.vault, interval=args.interval)
    else:
        out = export_hyperliquid_to_obsidian(args.vault)
        print(f"✓ Exported HyperLiquid intelligence & command notes to: {out}")
