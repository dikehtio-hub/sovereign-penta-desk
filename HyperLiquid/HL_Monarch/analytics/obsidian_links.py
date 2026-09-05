"""
Cross-suite Obsidian linking helpers shared by HL_Monarch and Polymarket_Monarch.

Obsidian resolves [[wikilinks]] only *within a single vault root*. Two suites that
each write into their own `obsidian_vault/` folder therefore cannot link to each
other at all - a link from one would render as an unresolved stub. Seamless
inter-linking requires both exporters to write into one shared vault, with each
suite namespaced into its own subfolder so note names never collide.

Layout inside a shared vault:

    <vault>/Monarch_Hub.md              <- index, links to both suites
    <vault>/HyperLiquid_Monarch.md      <- HL dashboard
    <vault>/Whales/0x....md             <- HL whale accounts
    <vault>/Polymarket_Monarch.md       <- Polymarket dashboard
    <vault>/Wallets/0x....md            <- Polymarket sharp traders

Both suites keep working unchanged when pointed at separate vaults: every
cross-suite link is emitted only when the counterpart note actually exists in the
same vault, so a standalone export never renders a dead link.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Optional, Tuple

# Note names each suite owns at the vault root.
HL_DASHBOARD_NOTE = "HyperLiquid_Monarch"
PM_DASHBOARD_NOTE = "Polymarket_Monarch"
QL_DASHBOARD_NOTE = "Quant_Trading_Lab"
TITANS_DASHBOARD_NOTE = "Cross_Market_Titans"
HUB_NOTE = "Monarch_Hub"
BOT_CONTROL_NOTE = "Bot_Control"
BOT_CONFIG_NOTE = "Bot_Config"
TRADING_TERMINAL_NOTE = "Trading_Terminal"
# Round 33: the fourth and fifth desks. Sports_Desk and the cross-market arb
# exporter write these at the vault root; the hub lists them when present.
SPORTS_DESK_NOTE = "Sports_Desk"
CROSS_MARKET_ARB_NOTE = "Cross_Market_Arb"

# Per-suite subfolders for entity notes.
HL_WHALES_DIR = "Whales"
PM_WALLETS_DIR = "Wallets"

# Round 34: the penta-desk canvas and the tax desk's dated notes it centres on.
PENTA_CANVAS_DIR = "Canvases"
PENTA_CANVAS_NOTE = "Sovereign_Penta_Cockpit"
TAX_NOTES_DIR = "Trading_Taxes"

USER_NOTES_HEADER = "## 📝 My Research & Notes"


def note_exists(vault_path: Path, note_name: str) -> bool:
    """True when `<vault>/<note_name>.md` is present in this vault."""
    return (Path(vault_path) / f"{note_name}.md").exists()


def make_progress_bar(val: float, max_val: float, length: int = 10, fill_char: str = "█", empty_char: str = "░") -> str:
    """Create a visual text progress bar for Markdown tables."""
    if max_val <= 0:
        return f"`{empty_char * length}` 0%"
    pct = max(0.0, min(100.0, (val / max_val) * 100.0))
    filled = int(round((pct / 100.0) * length))
    filled = max(0, min(length, filled))
    empty = length - filled
    return f"`{fill_char * filled}{empty_char * empty}` **{pct:.1f}%** ({int(val)}/{int(max_val)})"


# --- Content-hash dirty checking -------------------------------------------
#
# Every note carries a per-sync timestamp (`last_synced`, "Last Updated", ...).
# Hashing raw content would therefore mark every note dirty on every pass and
# save nothing, so the volatile lines are normalised out before hashing. A note
# is rewritten only when its *substance* changed; otherwise the file - and its
# mtime - is left untouched, which is what stops Obsidian re-indexing in a loop
# under `--watch`.

_VOLATILE_LINE_PATTERNS = (
    re.compile(r"^last_synced:.*$", re.MULTILINE),
    re.compile(r"^\s*>\s*-\s*\*\*Last (?:Updated|Synchronized|Refreshed)\*\*:.*$", re.MULTILINE),
)

# Round 69 (Ruling 68-1): elapsed-time FRAGMENTS inside otherwise substantive lines. Whole
# lines cannot be dropped here - the same line carries the collector's PID, a position's
# accrued funding, an engine's badge - so each pattern replaces only the clock-derived
# number and leaves the state beside it in the hash:
#   "`12s ago`" / "(243475s ago)"  - how long since the DB / Polymarket engine last wrote;
#   "`89.2h`"                       - a position's Duration (hours held);
#   the Realised APR cell           - accrued / notional / hours held: it ticks with the clock
#                                     even when nothing accrued (the Funding Accrued cell beside
#                                     it, which does change on an accrual, stays hashed; so does
#                                     the Entry APR).
_VOLATILE_FRAGMENT_PATTERNS = (
    (re.compile(r"\b\d+s ago\b"), "<VOLATILE_TIME>"),
    (re.compile(r"`\d+(?:\.\d+)?h`"), "`<VOLATILE_TIME>`"),
    (re.compile(r"(\| `[+-]?\d+(?:\.\d+)?%` \| )`[+-]?\d+(?:\.\d+)?%`( \| \*\*`[+-]?\$)"),
     r"\1`<VOLATILE_APR>`\2"),
)


def normalize_for_hash(content: str) -> str:
    """Strip per-sync timestamps and clock-derived fragments so only substantive changes register."""
    out = content
    for pattern in _VOLATILE_LINE_PATTERNS:
        out = pattern.sub("", out)
    for pattern, replacement in _VOLATILE_FRAGMENT_PATTERNS:
        out = pattern.sub(replacement, out)
    # Collapse trailing whitespace so cosmetic line-ending drift is not a change.
    return "\n".join(line.rstrip() for line in out.splitlines()).strip()


def content_hash(content: str) -> str:
    """SHA-256 of a note's substantive content."""
    return hashlib.sha256(normalize_for_hash(content).encode("utf-8")).hexdigest()


def write_note_if_changed(file_path: Path, content: str) -> Tuple[Path, bool]:
    """
    Write `content` to `file_path` only when its substance differs from what is
    already on disk.

    Returns (path, written). `written` is False when the note was left alone,
    which callers can total up to report how much churn was avoided.
    """
    path = Path(file_path)
    payload = content if content.endswith("\n") else content + "\n"

    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
            if content_hash(existing) == content_hash(payload):
                return path, False
        except Exception:
            # Unreadable/corrupt note: fall through and rewrite it.
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path, True


def wikilink(target: str, label: Optional[str] = None) -> str:
    """Build an Obsidian wikilink, with an optional display label."""
    return f"[[{target}|{label}]]" if label else f"[[{target}]]"


def counterpart_link(vault_path: Path, note_name: str, label: str) -> Optional[str]:
    """
    Link to another suite's dashboard, but only if it shares this vault.

    Returns None when the counterpart is absent, so callers can omit the row
    entirely rather than emitting a link Obsidian cannot resolve.
    """
    if note_exists(vault_path, note_name):
        return wikilink(note_name, label)
    return None


def preserve_user_notes(file_path: Path, default_template: str) -> str:
    """
    Carry a reader's hand-written research forward across regeneration with multi-encoding fallback.

    Everything after the research header belongs to the user, so an exporter that
    rewrites the note must splice that tail back in verbatim.
    """
    path = Path(file_path)
    if not path.exists():
        return default_template

    content = None
    for enc in ("utf-8", "utf-8-sig", "utf-16", "cp1252"):
        try:
            content = path.read_text(encoding=enc)
            break
        except Exception:
            continue

    if content is not None and USER_NOTES_HEADER in content:
        return content.split(USER_NOTES_HEADER, 1)[1]

    return default_template


def _fmt_usd(val: float) -> str:
    sign = "-" if val < 0 else ""
    mag = abs(float(val))
    if mag >= 1_000_000_000:
        return f"{sign}${mag / 1_000_000_000:.2f}B"
    if mag >= 1_000_000:
        return f"{sign}${mag / 1_000_000:.2f}M"
    if mag >= 1_000:
        return f"{sign}${mag / 1_000:.1f}K"
    return f"{sign}${mag:,.2f}"


def latest_tax_note(vault_path: Path) -> Optional[str]:
    """Vault-relative path of the newest `Trading_Taxes/Tax_Reserve_<date>.md`, or None."""
    folder = Path(vault_path) / TAX_NOTES_DIR
    if not folder.is_dir():
        return None
    names = sorted(p.name for p in folder.glob("Tax_Reserve_*.md"))
    return "%s/%s" % (TAX_NOTES_DIR, names[-1]) if names else None


def write_penta_canvas(vault_path: Path) -> Tuple[Path, bool]:
    """
    `Canvases/Sovereign_Penta_Cockpit.canvas`: the five desks around the tax
    reserve, capital gating drawn one way and reserve flows drawn back.

    A node is a FILE node when the desk's note exists in this vault - Obsidian
    renders the live note inside the canvas, so the cockpit shows the dashboards
    themselves rather than a drawing of them - and a text placeholder otherwise,
    so a partially exported vault still opens cleanly. The centre is the newest
    Tax_Reserve note, because every desk's sizing runs through that ledger. The
    content carries no timestamp, so the content-hashed write leaves the file
    alone unless a desk appeared or the tax note rolled to a new day.
    """
    vault_path = Path(vault_path)
    target = vault_path / PENTA_CANVAS_DIR / ("%s.canvas" % PENTA_CANVAS_NOTE)

    def node(nid, x, y, width, height, color, note, placeholder):
        base = {"id": nid, "x": x, "y": y, "width": width, "height": height, "color": color}
        if note and (vault_path / note).exists():
            base.update({"type": "file", "file": note})
        else:
            base.update({"type": "text", "text": placeholder})
        return base

    desks = [
        ("hl", -1300, -700, "5", "%s.md" % HL_DASHBOARD_NOTE,
         "## 🏛 HyperLiquid Desk\nPerp basis harvest · whale sweeps · liquidation waterfall\n\n"
         "*not exported into this vault yet*"),
        ("pm", 740, -700, "3", "%s.md" % PM_DASHBOARD_NOTE,
         "## 🌐 Polymarket Desk\nPrediction CLOB · sharp consensus · dutching\n\n"
         "*not exported into this vault yet*"),
        ("ql", -1300, 260, "6", "%s.md" % QL_DASHBOARD_NOTE,
         "## ⚡ Quant Trading Lab\nCME futures · killzones · risk sentinel\n\n"
         "*not exported into this vault yet*"),
        ("sports", 740, 260, "4", "%s.md" % SPORTS_DESK_NOTE,
         "## 🏈 Sports Desk\nFair value · CLV · after-tax hurdle\n\n*not exported into this vault yet*"),
        ("xarb", -280, 760, "2", "%s.md" % CROSS_MARKET_ARB_NOTE,
         "## ⚖️ Cross-Market Arb\nAsymmetric hedger · 16.75% / 23.93% hurdles\n\n"
         "*not exported into this vault yet*"),
    ]
    nodes = [
        node("hub", -210, -1160, 420, 220, "4", "%s.md" % HUB_NOTE,
             "# 👑 Monarch Hub\n\n*not exported into this vault yet*"),
        node("tax", -280, -220, 560, 400, "1", latest_tax_note(vault_path),
             "# 💰 Tax & Bankroll Reserve\n**Centre of the ecosystem**\n"
             "- safe bankroll → strategy buckets → per-order cap\n"
             "- FAIL-CLOSED on an empty ledger\n"
             "- lots · escrow · W-2G · §165(d) / §1234A\n\n*no Tax_Reserve note in this vault yet*"),
    ]
    for nid, x, y, color, note, placeholder in desks:
        nodes.append(node(nid, x, y, 560, 380, color, note, placeholder))

    # Sides chosen so the two arrows between the centre and each desk do not overlap.
    geometry = {"hl": ("left", "right", "bottom", "top"), "pm": ("right", "left", "bottom", "top"),
                "ql": ("left", "right", "top", "bottom"), "sports": ("right", "left", "top", "bottom"),
                "xarb": ("bottom", "top", "left", "left")}
    colours = {d[0]: d[3] for d in desks}
    edges = [{"id": "hub-tax", "fromNode": "hub", "toNode": "tax", "fromSide": "bottom",
              "toSide": "top", "color": "4", "label": "vault index"}]
    for nid, *_ in desks:
        gate_from, gate_to, flow_from, flow_to = geometry[nid]
        edges.append({"id": "gate-%s" % nid, "fromNode": "tax", "toNode": nid,
                      "fromSide": gate_from, "toSide": gate_to, "color": "1",
                      "label": "capital gate: safe bankroll → bucket → max order"})
        edges.append({"id": "flow-%s" % nid, "fromNode": nid, "toNode": "tax",
                      "fromSide": flow_from, "toSide": flow_to, "color": colours[nid],
                      "label": "receipts → lots · escrow · reserve"})
    edges.append({"id": "sports-xarb", "fromNode": "sports", "toNode": "xarb", "fromSide": "bottom",
                  "toSide": "right", "color": "4", "label": "book quotes · sports_market.db"})
    edges.append({"id": "pm-xarb", "fromNode": "pm", "toNode": "xarb", "fromSide": "bottom",
                  "toSide": "right", "color": "3", "label": "questions · polymarket_drops"})

    content = json.dumps({"nodes": nodes, "edges": edges}, indent=1, ensure_ascii=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    return write_note_if_changed(target, content + "\n")


def write_hub_note(vault_path: Path, synced_at: str) -> Path:
    """
    Write (or refresh) the master executive vault index that ties the entire ecosystem together.
    """
    vault_path = Path(vault_path)
    vault_path.mkdir(parents=True, exist_ok=True)
    hub_file = vault_path / f"{HUB_NOTE}.md"

    has_hl = note_exists(vault_path, HL_DASHBOARD_NOTE)
    has_pm = note_exists(vault_path, PM_DASHBOARD_NOTE)
    has_ql = note_exists(vault_path, QL_DASHBOARD_NOTE)
    has_titans = note_exists(vault_path, TITANS_DASHBOARD_NOTE)
    has_ctrl = note_exists(vault_path, BOT_CONTROL_NOTE)
    has_cfg = note_exists(vault_path, BOT_CONFIG_NOTE)
    has_term = note_exists(vault_path, TRADING_TERMINAL_NOTE)
    has_sports = note_exists(vault_path, SPORTS_DESK_NOTE)
    has_xarb = note_exists(vault_path, CROSS_MARKET_ARB_NOTE)

    rows = []
    if has_ctrl:
        rows.append(
            f"| {wikilink(BOT_CONTROL_NOTE, '🎮 Bot Control & Activation Deck')} "
            f"| Operations / Services | Background daemon telemetry, Windows 1-click launchers, Killswitch "
            f"| `Active Cockpit` |"
        )
    if has_cfg:
        rows.append(
            f"| {wikilink(BOT_CONFIG_NOTE, '⚙️ Bot Configuration & Risk Controller')} "
            f"| Risk & Sizing | Hot-reloadable YAML frontmatter, presets (Conservative/Balanced/Aggressive) "
            f"| `Live Config` |"
        )
    if has_term:
        rows.append(
            f"| {wikilink(TRADING_TERMINAL_NOTE, '📈 Trading Terminal & 50-Trade Hurdle')} "
            f"| Execution Telemetry | Paper account equity, active basis positions, resting limits, 50-trade hurdle "
            f"| `Telemetry` |"
        )
    if has_hl:
        whales = vault_path / HL_WHALES_DIR
        count = len(list(whales.glob("*.md"))) if whales.is_dir() else 0
        rows.append(
            f"| {wikilink(HL_DASHBOARD_NOTE, '👑 HyperLiquid Monarch')} "
            f"| Perp DEX / HIP-3 TradFi | Liquidations, funding arbitrage, whale portfolios, danger zone "
            f"| `{count}` whale notes |"
        )
    if has_pm:
        wallets = vault_path / PM_WALLETS_DIR
        count = len(list(wallets.glob("*.md"))) if wallets.is_dir() else 0
        rows.append(
            f"| {wikilink(PM_DASHBOARD_NOTE, '👑 Polymarket Monarch')} "
            f"| Prediction markets | Sharp-trader PnL, whale fills, macro sentiment, consensus radar "
            f"| `{count}` trader notes |"
        )
    if has_ql:
        rows.append(
            f"| {wikilink(QL_DASHBOARD_NOTE, '⚡ Quant Trading Lab')} "
            f"| CME Futures / Microstructure | /NQ, /ES, /GC, /CL, 9 Strategy Stacks, ICT Killzones, Risk Sentinel "
            f"| `Active Desk` |"
        )
    if has_titans:
        rows.append(
            f"| {wikilink(TITANS_DASHBOARD_NOTE, '👑 Cross-Market Titans')} "
            f"| Multi-Venue Intelligence | Whale entity resolution, logarithmic conviction score, macro co-positioning "
            f"| `Active Intelligence` |"
        )
    if has_sports:
        rows.append(
            f"| {wikilink(SPORTS_DESK_NOTE, '🏈 Sports Desk')} "
            f"| Sportsbooks / Fair Value | Shin-devigged edges, after-tax hurdle, execution CLV, tax-ledger bridge "
            f"| `Active Desk` |"
        )
    if has_xarb:
        rows.append(
            f"| {wikilink(CROSS_MARKET_ARB_NOTE, '⚖️ Cross-Market Arb')} "
            f"| Polymarket vs Sportsbook | Matched pairs priced through the asymmetric tax, both characterisations "
            f"| `Active Desk` |"
        )
    table = "\n".join(rows) if rows else "| — | — | *No suite dashboards exported into this vault yet.* | — |"
    both = has_hl and has_pm
    cross_note = (
        "> [!TIP] **Both suites share this vault**\n"
        "> Wikilinks resolve across suites, so a wallet seen on Hyperliquid and a trader\n"
        "> seen on Polymarket can be linked to each other by hand, and Obsidian's graph\n"
        "> view shows both intelligence networks as one connected graph."
        if both else
        "> [!WARNING] **Only one suite is exporting into this vault**\n"
        "> Cross-suite links stay hidden until both exporters target the same vault.\n"
        "> Point them at one root to unify them:\n"
        "> `$env:OBSIDIAN_VAULT_PATH = \"C:/Users/ixis1/Desktop/DEV/obsidian_vault\"`\n"
        "> then re-run `python main.py obsidian --once` (HyperLiquid) and\n"
        "> `python obsidian_sync.py --once` (Polymarket)."
    )

    launcher_rows = []
    if has_ctrl:
        launcher_rows.append(f"| 🎮 **Bot Operations** | Service management, daemon PIDs, 1-click execution | [[{BOT_CONTROL_NOTE}|Open Bot Control Deck]] |")
    if has_cfg:
        launcher_rows.append(f"| ⚙️ **Risk Configuration** | Capital allocation, funding rate floors, dynamic presets | [[{BOT_CONFIG_NOTE}|Open Risk Controller]] |")
    if has_term:
        launcher_rows.append(f"| 📈 **Trading Terminal** | Paper balance, active basis pairs, 50-trade hurdle validation | [[{TRADING_TERMINAL_NOTE}|Open Trading Terminal]] |")
    if has_hl:
        launcher_rows.append(f"| 🏛 **HyperLiquid Desk** | Spot-backed basis arb, liquidation waterfall, whale CRM | [[{HL_DASHBOARD_NOTE}|Open HL Dashboard]] |")
    if has_pm:
        launcher_rows.append(f"| 🌐 **Polymarket Desk** | Sharp trader PnL, multi-sharp consensus, macro sentiment | [[{PM_DASHBOARD_NOTE}|Open Polymarket Desk]] |")
    if has_ql:
        launcher_rows.append(f"| ⚡ **CME Futures Desk** | /NQ, /ES, /GC, /CL, 9 Strategy Stacks, Killzones | [[{QL_DASHBOARD_NOTE}|Open Quant Lab Desk]] |")
    if has_titans:
        launcher_rows.append(f"| 👑 **Cross-Market Titans** | Multi-venue entity resolution, macro co-positioning | [[{TITANS_DASHBOARD_NOTE}|Open Titans Desk]] |")
    if has_sports:
        launcher_rows.append(f"| 🏈 **Sports Desk** | +EV hotlist, realised P&L, execution CLV, un-exported bet alerts | [[{SPORTS_DESK_NOTE}|Open Sports Desk]] |")
    if has_xarb:
        launcher_rows.append(f"| ⚖️ **Cross-Market Arb** | Polymarket vs sportsbook pairs, 16.75% / 23.93% after-tax hurdles | [[{CROSS_MARKET_ARB_NOTE}|Open Cross-Market Arb]] |")

    launcher_rows.append(
        f"| 🗺️ **Penta-Desk Canvas** | Visual cockpit: capital gating and reserve flows across all five desks "
        f"| [[{PENTA_CANVAS_DIR}/{PENTA_CANVAS_NOTE}.canvas|Open Canvas]] |")

    launchers_table = "\n".join(launcher_rows) if launcher_rows else "| — | *No active dashboards.* | — |"

    content = f"""---
title: Monarch Intelligence Hub & Executive Command Center
tags:
  - monarch
  - hub
  - executive-cockpit
  - dashboard
last_synced: "{synced_at}"
---

# 👑 Monarch Intelligence Hub & Executive Command Center

> [!INFO] **Vault Index**
> - **Last Refreshed**: `{synced_at}`
> - **Suites In This Vault**: `{int(has_hl) + int(has_pm) + int(has_ql) + int(has_titans) + int(has_sports) + int(has_xarb)}` of {2 + (1 if has_ql else 0) + (1 if has_titans else 0) + (1 if has_sports else 0) + (1 if has_xarb else 0)}
> - **Vault Root**: `{vault_path}`

{cross_note}

---

## 🎛️ Command Desks & Intelligence Suites

| Command Desk / Suite | Domain | Covers | Status / Notes |
| :--- | :--- | :--- | :---: |
{table}

---

## ⚡ Quick Launcher Deck

| Quick Action | Target Module | Shortcut |
| :--- | :--- | :---: |
{launchers_table}

---

## 🔗 Connected Ecosystem Topology

Both suites track **wallet addresses** as primary entities, backed by local SQLite databases (`hyperliquid_data.db` and `polymarket_whales.db`).
- **HyperLiquid**: Discovers whales from live perp fills (>= $25k) and records on-chain portfolio equity and liquidation margin stress.
- **Polymarket**: Discovers sharp traders from prediction-market fills and tracks 7-day realized/unrealized PnL and consensus convergence.
- **Quant Trading Lab**: Tracks CME Futures microstructure (/NQ, /ES, /GC, /CL), 9 Strategy Stacks, and real-time ICT Killzone session clocks.
- **Cross-Market Titans**: An address appearing in both venues is an institutional actor operating across perps and prediction markets.
- **Sports Desk**: Devigs the sharp book, scores retail prices against it, gates every stake through the tax ledger's after-tax hurdle, and flags bets the ledger has not yet seen.
- **Cross-Market Arb**: Pairs a Polymarket YES with the opposite sportsbook side and prices the worst branch after tax - each leg's loss is deductible only against income the other leg does not produce.

---
*Generated automatically by Monarch Intelligence Exporters.*
"""
    write_note_if_changed(hub_file, content.strip() + "\n")
    # Round 34: the canvas is refreshed with the hub so whichever exporter runs
    # last leaves it reflecting the notes that actually exist.
    write_penta_canvas(vault_path)
    return hub_file
