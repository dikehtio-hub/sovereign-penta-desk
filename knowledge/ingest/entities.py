"""CRM seeds: titans, sharps, whales, sportsbooks -> crm/ pages (Round 99, B8).

    python -m knowledge.ingest.entities [--limit-whales 100] [--limit-titans 100] [--at ISO]

Sources, every one read-only (SQLite via `file:...?mode=ro`):
  cross_market/titan_identities_cache.json          EOA -> {proxy_wallet, pseudonym}   (1,685 pairs, not 8)
  HyperLiquid/HL_Monarch/data/hyperliquid_data.db   whale_wallets (8,866 rows; top N by account_value)
  Polymarket/Polymarket_Monarch/data/polymarket_whales.db  sharp_traders (79) + tracked_wallets (97)
  Sports_Desk/data/sports_market.db                 edge_opportunities (96) + fair_odds_measurements (32)

WHAT A CRM PAGE IS. A compiled judgement about a counterparty, not a metrics
mirror: the exporter-owned `Whales/` and `Wallets/` notes keep the live numbers.
A CRM page keeps identity (addresses, pseudonym, how the identity was resolved),
a **Judgement** section a human writes, and dated **evidence** rows the adapter
appends (one per distinct scan time), so behaviour accumulates instead of being
overwritten every 15 s.

A TITAN is a name seen trading on BOTH venues. The identity cache maps every
whale EOA that Gamma could resolve to a Polymarket proxy (1,685 of them), so
the cache alone proves an account exists, not that it trades: a titan needs
the proxy (or the EOA) to appear in the Polymarket trader tables
(sharp_traders.wallet / proxy_wallet / eoa_address, tracked_wallets.wallet),
or a sharp trader's resolved EOA to appear in whale_wallets. Zero titans is a
legitimate result and matches the dashboard's "0 institutional actors".

THE INVARIANT (Round 99). Re-ingest never overwrites the Judgement section,
`verified`, `stale_after`, or a status a human promoted past `draft`; evidence
rows append (deduplicated by scan time, newest 50 kept). The CRM register is
rebuilt after every run.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc, page_path,
                     write_index, write_page)
from ..registers import update_register
from . import add_common_args, at_from, guard, item_link, rel_to, page_changed

TITAN_CACHE = Path("cross_market") / "titan_identities_cache.json"
HL_DB = Path("HyperLiquid") / "HL_Monarch" / "data" / "hyperliquid_data.db"
PM_DB = Path("Polymarket") / "Polymarket_Monarch" / "data" / "polymarket_whales.db"
SPORTS_DB = Path("Sports_Desk") / "data" / "sports_market.db"
REGISTER_FILE = "crm_register"
JUDGEMENT_HEADING = "## Judgement"
JUDGEMENT_PLACEHOLDER = "_(none yet: write the compiled judgement here; re-ingest keeps this section and only appends evidence)_"
EVIDENCE_KEEP = 50


# ---------------------------------------------------------------- read-only sources

def ro(db: Path) -> sqlite3.Connection | None:
    if not db.is_file():
        return None
    try:
        return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    except sqlite3.Error:
        return []


def _ts(v: Any) -> str | None:
    """Epoch milliseconds (HL) or an ISO/`YYYY-MM-DD HH:MM:SS` string -> ISO Z."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return iso(datetime.fromtimestamp(float(v) / 1000.0, tz=timezone.utc))
    s = str(v).strip().replace(" ", "T")
    return s if s.endswith("Z") or "+" in s else s + "Z"


def short(addr: str) -> str:
    return f"{addr[:6]}…{addr[-4:]}" if len(addr) > 12 else addr


def load_titan_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k).lower(): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


WHALE_COLS = ("address, discovered_at, first_coin, first_notional, total_position_value, account_value, "
              "is_liquidator, last_scanned_at")


def load_whales(db: Path, limit: int, keep: set[str] | None = None) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """The top-N rows for pages, and address -> account_value for EVERY whale (titan ranking is uncapped).

    `keep` re-admits addresses that ALREADY have a page. Round 105: the top-N is a moving window,
    so a whale that drops out of it was never rebuilt again - and a page the adapter stops
    maintaining freezes at whatever the code emitted the last time it was selected. That is how one
    page kept a dangling exporter-note link through a fix that reached the other 182. An adapter
    maintains every page it has created, or it does not own them.
    """
    conn = ro(db)
    if conn is None:
        return [], {}
    top = _rows(conn, f"SELECT {WHALE_COLS} FROM whale_wallets WHERE account_value IS NOT NULL "
                      "ORDER BY account_value DESC LIMIT ?", (int(limit),))
    if keep:
        have = {str(r["address"]).lower() for r in top}
        wanted = sorted(keep - have)
        if wanted:
            marks = ",".join("?" * len(wanted))
            top += _rows(conn, f"SELECT {WHALE_COLS} FROM whale_wallets WHERE lower(address) IN ({marks})",
                         tuple(wanted))
    every = {str(r["address"]).lower(): float(r["account_value"] or 0.0)
             for r in _rows(conn, "SELECT address, account_value FROM whale_wallets")}
    conn.close()
    return top, every


def load_sharps(db: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    conn = ro(db)
    if conn is None:
        return [], {}
    sharps = _rows(conn, "SELECT * FROM sharp_traders")
    tracked = {str(r["wallet"]).lower(): r for r in _rows(conn, "SELECT * FROM tracked_wallets")}
    conn.close()
    return sharps, tracked


def load_books(db: Path) -> dict[str, dict[str, Any]]:
    """Per book: role and evidence rows aggregated per market type from edge_opportunities."""
    conn = ro(db)
    if conn is None:
        return {}
    books: dict[str, dict[str, Any]] = {}
    for r in _rows(conn, "SELECT sportsbook, COUNT(*) AS n, MIN(timestamp) AS first, MAX(timestamp) AS last "
                         "FROM fair_odds_measurements GROUP BY sportsbook"):
        books.setdefault(str(r["sportsbook"]).lower(), {"role": "sharp", "measurements": int(r["n"]), "rows": []})
    for r in _rows(conn, "SELECT sharp_book, COUNT(*) AS n FROM edge_opportunities GROUP BY sharp_book"):
        b = books.setdefault(str(r["sharp_book"]).lower(), {"role": "sharp", "measurements": 0, "rows": []})
        b["role"] = "sharp"
        b["priced_against"] = int(r["n"])
    for r in _rows(conn, "SELECT retail_book, sport, market_type, COUNT(*) AS edges, SUM(clears_hurdle) AS cleared, "
                         "AVG(gross_edge) AS mean_gross_edge, MAX(gross_edge) AS max_gross_edge, MIN(timestamp) AS first, "
                         "MAX(timestamp) AS last FROM edge_opportunities GROUP BY retail_book, sport, market_type"):
        b = books.setdefault(str(r["retail_book"]).lower(), {"role": "soft", "measurements": 0, "rows": []})
        b["role"] = "soft" if b.get("role") != "sharp" else "sharp"
        b["rows"].append({"sport": r["sport"], "market_type": r["market_type"], "edges": int(r["edges"] or 0),
                          "cleared": int(r["cleared"] or 0), "mean_gross_edge": round(float(r["mean_gross_edge"] or 0), 4),
                          "max_gross_edge": round(float(r["max_gross_edge"] or 0), 4), "first": _ts(r["first"]), "last": _ts(r["last"])})
    conn.close()
    return books


# ---------------------------------------------------------------- the invariant

def _judgement_of(existing: Page | None) -> str:
    if existing is None:
        return JUDGEMENT_PLACEHOLDER
    m = re.search(rf"^{re.escape(JUDGEMENT_HEADING)}\s*\n(.*?)(?=^## |\Z)", existing.body, re.S | re.M)
    text = m.group(1).strip() if m else ""
    return text or JUDGEMENT_PLACEHOLDER


def _merge_evidence(existing: Page | None, new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if existing is not None:
        rows = [dict(r) for r in (existing.meta.get("dev") or {}).get("evidence", []) if isinstance(r, dict)]
    seen = {str(r.get("at")) for r in rows}
    for r in new_rows:
        if str(r.get("at")) not in seen:
            rows.append(r)
            seen.add(str(r.get("at")))
    return rows[-EVIDENCE_KEEP:]


_carry_human_fields = carry_human_fields  # shared with the other adapters since Round 99


def _evidence_table(rows: list[dict[str, Any]], cols: list[str]) -> list[str]:
    if not rows:
        return ["_(no evidence rows yet)_", ""]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join("-" if r.get(c) is None else str(r.get(c)) for c in cols) + " |")
    out.append("")
    return out


def _assemble(vault: Path, type_: str, stem: str, title: str, description: str, tags: list[str], identity: list[str],
              evidence_rows: list[dict[str, Any]], evidence_cols: list[str], related: list[str], dev: dict[str, Any],
              sources: list[dict[str, Any]], at: datetime, by: str) -> tuple[Page, bool]:
    path = page_path(vault, type_, stem)
    existing = load_page(path)
    rows = _merge_evidence(existing, evidence_rows)
    dev = dict(dev)
    dev["evidence"] = rows
    body = [f"# {title}", "", "## Identity", "", *identity, "", JUDGEMENT_HEADING, "", _judgement_of(existing), "",
            "## Evidence (dated rows the adapter appends; never live state)", "", *_evidence_table(rows, evidence_cols),
            "## Related", "", *related, f"- [[{REGISTER_FILE}|CRM register]]", ""]
    meta = make_meta(type_, title, description, tags=tags, generated_by=by, at=at, status="draft", sources=sources, dev=dev)
    _carry_human_fields(existing, meta)
    return Page(path, meta, "\n".join(body)), existing is None


# ---------------------------------------------------------------- builders

def exporter_note_line(vault: Path, folder: str, key: str, label: str) -> str:
    """Link the exporter-owned note for this counterparty, but only if it actually exists.

    Round 105 (lint L8): these lines linked `Whales/<addr>` and `Wallets/<wallet>` unconditionally,
    and 85 of them pointed at nothing. The two sets never matched - the CRM seeds the top 100 by
    equity while the exporter writes notes for a different, live-changing set, and they overlapped
    by 53. A link that resolves for some rows and not others is worse than no link, because the
    reader cannot tell which. Where the note is absent the page now SAYS so, which is also the
    honest statement: this counterparty has no live exporter note.
    """
    if (vault / folder / f"{key}.md").is_file():
        return f"- live note (exporter-owned): [[{folder}/{key}|{label}]]"
    return f"- live note (exporter-owned): none written for `{key}` (the exporter tracks a different set)"


def build_whale(r: dict[str, Any], rank: int, cache: dict[str, dict[str, Any]], vault: Path, dev_root: Path, at: datetime, by: str) -> tuple[Page, bool]:
    addr = str(r["address"]).lower()
    equity = float(r.get("account_value") or 0.0)
    position = float(r.get("total_position_value") or 0.0)
    lev = round(position / equity, 2) if equity > 0 else None
    identity = [f"- address: `{addr}`", f"- discovered: `{_ts(r.get('discovered_at'))}` via `{r.get('first_coin')}` (${float(r.get('first_notional') or 0):,.0f})",
                f"- system liquidator: {bool(r.get('is_liquidator'))}", f"- rank by equity at seed: {rank}",
                exporter_note_line(vault, "Whales", addr, "whale note")]
    related = ["- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]"]
    dev: dict[str, Any] = {"desk": 1, "address": addr, "first_coin": r.get("first_coin"), "discovered_at": _ts(r.get("discovered_at")),
                           "is_liquidator": bool(r.get("is_liquidator")), "rank_at_seed": rank}
    if addr in cache:
        dev["titan"] = f"titan_{addr}"
        related.insert(0, f"- [[titan_{addr}|Titan {cache[addr].get('pseudonym') or short(addr)}]] (same name on Polymarket)")
    ev = [{"at": _ts(r.get("last_scanned_at")), "account_value": round(equity, 2), "position_value": round(position, 2), "leverage": lev}]
    return _assemble(vault, "Entity/Whale", f"whale_{addr}", f"Whale {short(addr)}",
                     f"Hyperliquid whale {short(addr)}: rank {rank} by account equity at seed; first seen on {r.get('first_coin')}.",
                     ["crm", "whale", "desk-1"], identity, ev, ["at", "account_value", "position_value", "leverage"], related, dev,
                     [{"id": "whale_wallets", "resource": rel_to(dev_root / HL_DB, dev_root), "title": "hyperliquid_data.db whale_wallets (mode=ro)",
                       "author": "process:HL_Monarch.collector"}], at, by)


def build_sharp(r: dict[str, Any], tracked: dict[str, dict[str, Any]], titans: set[str], vault: Path, dev_root: Path, at: datetime, by: str,
                titan_by_proxy: dict[str, str] | None = None) -> tuple[Page, bool]:
    titan_by_proxy = titan_by_proxy or {}
    wallet = str(r["wallet"]).lower()
    name = str(r.get("pseudonym") or short(wallet))
    eoa = str(r["eoa_address"]).lower() if r.get("eoa_address") else None
    proxy = str(r["proxy_wallet"]).lower() if r.get("proxy_wallet") else None
    titan_eoa = eoa if (eoa and eoa in titans) else titan_by_proxy.get(wallet) or (titan_by_proxy.get(proxy) if proxy else None)
    t = tracked.get(wallet, {})
    identity = [f"- wallet: `{wallet}`", f"- pseudonym: **{name}**", f"- profile: {r.get('polymarket_link') or '-'}",
                f"- proxy wallet: `{r.get('proxy_wallet') or '-'}` · EOA: `{eoa or 'unresolved'}`"
                + (f" (resolved `{_ts(r.get('identity_resolved_at'))}`)" if r.get("identity_resolved_at") else ""),
                f"- first seen: `{_ts(t.get('first_seen'))}`" if t else "- first seen: -",
                exporter_note_line(vault, "Wallets", wallet, "trader note")]
    related = ["- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]"]
    dev: dict[str, Any] = {"desk": 3, "wallet": wallet, "pseudonym": name, "proxy_wallet": r.get("proxy_wallet"), "eoa_address": eoa,
                           "identity_resolved_at": _ts(r.get("identity_resolved_at")), "first_seen": _ts(t.get("first_seen")) if t else None}
    if titan_eoa:
        dev["titan"] = f"titan_{titan_eoa}"
        related.insert(0, f"- [[titan_{titan_eoa}|Titan {name}]] (same name on Hyperliquid)")
    ev = [{"at": _ts(r.get("last_scanned")), "pnl_7d": r.get("pnl_7d"), "realized_pnl_7d": r.get("realized_pnl_7d"),
           "volume_7d": r.get("volume_7d"), "trades_7d": r.get("trades_7d"), "win_rate": r.get("win_rate"), "is_sharp": bool(r.get("is_sharp"))}]
    return _assemble(vault, "Entity/Sharp Trader", f"sharp_{wallet}", f"Sharp trader {name}",
                     f"Polymarket sharp trader {name} ({short(wallet)}); identity {'resolved to an EOA' if eoa else 'unresolved'}.",
                     ["crm", "sharp-trader", "desk-3"], identity, ev,
                     ["at", "pnl_7d", "realized_pnl_7d", "volume_7d", "trades_7d", "win_rate", "is_sharp"], related, dev,
                     [{"id": "sharp_traders", "resource": rel_to(dev_root / PM_DB, dev_root), "title": "polymarket_whales.db sharp_traders (mode=ro)",
                       "author": "process:Polymarket_Monarch.pnl_scanner"}], at, by)


def build_titan(eoa: str, entry: dict[str, Any], whale: dict[str, Any] | None, sharp: dict[str, Any] | None,
                vault: Path, dev_root: Path, at: datetime, by: str) -> tuple[Page, bool]:
    name = str(entry.get("pseudonym") or (sharp or {}).get("pseudonym") or short(eoa))
    proxy = str(entry.get("proxy_wallet") or (sharp or {}).get("proxy_wallet") or (sharp or {}).get("wallet") or "").lower()
    identity = [f"- Hyperliquid EOA: `{eoa}`" + (f" -> [[whale_{eoa}|whale page]]" if whale else " (not in the top-N whale pages)"),
                f"- Polymarket proxy: `{proxy or '-'}`" + (f" -> [[sharp_{str(sharp['wallet']).lower()}|sharp page]]" if sharp else ""),
                f"- pseudonym: **{name}**", f"- resolution: {entry.get('source', 'titan_identities_cache.json (Gamma EOA -> proxy)')}"]
    related = ["- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]", "- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]",
               item_link(vault, "Item_18_Cross_Market_Titan_Correlator_Macro_Crypto", "Item 18: Cross-Market Titan Correlator")]
    dev: dict[str, Any] = {"desk": 3, "item": 18, "eoa": eoa, "proxy_wallet": proxy or None, "pseudonym": name,
                           "in_whales": bool(entry.get("in_whales", whale is not None)), "in_polymarket": True,
                           "resolution": str(entry.get("source", "titan_identities_cache.json"))}
    ev: list[dict[str, Any]] = []
    if whale:
        ev.append({"at": _ts(whale.get("last_scanned_at")), "venue": "hyperliquid", "account_value": round(float(whale.get("account_value") or 0), 2),
                   "metric": "equity"})
    if sharp:
        ev.append({"at": _ts(sharp.get("last_scanned")), "venue": "polymarket", "account_value": sharp.get("realized_pnl_7d"), "metric": "realized_pnl_7d"})
    return _assemble(vault, "Entity/Titan", f"titan_{eoa}", f"Titan {name}",
                     f"Cross-venue identity {name}: Hyperliquid {short(eoa)} is Polymarket {short(proxy) if proxy else '-'}; "
                     f"seen trading on both venues.",
                     ["crm", "titan", "desk-3", "item-18"], identity, ev, ["at", "venue", "metric", "account_value"], related, dev,
                     [{"id": "titan-cache", "resource": rel_to(dev_root / TITAN_CACHE, dev_root), "title": "titan_identities_cache.json",
                       "author": "process:cross_market.titan_correlator"}], at, by)


def build_book(name: str, info: dict[str, Any], vault: Path, dev_root: Path, at: datetime, by: str) -> tuple[Page, bool]:
    role = info.get("role", "soft")
    identity = [f"- book: **{name}**", f"- role in the fair-value engine: **{role}**"
                + (" (the devigged reference every edge is priced against)" if role == "sharp" else " (a retail book whose stale lines are the edge)"),
                f"- fair-odds measurements as reference: {info.get('measurements', 0)}"
                + (f" · edges priced against it: {info.get('priced_against', 0)}" if info.get("priced_against") else "")]
    rows = [dict(r, at=r.get("last")) for r in info.get("rows", [])]
    dev: dict[str, Any] = {"desk": 2, "book": name, "role": role, "measurements": info.get("measurements", 0)}
    return _assemble(vault, "Entity/Sportsbook", f"book_{name}", f"Sportsbook {name}",
                     f"{name}: {role} book in the Sports Desk fair-value engine" + (f"; {sum(r['edges'] for r in rows)} edges recorded across "
                     f"{len(rows)} sport/market-type cell(s)." if rows else "."),
                     ["crm", "sportsbook", "desk-2", role], identity, rows,
                     ["at", "sport", "market_type", "edges", "cleared", "mean_gross_edge", "max_gross_edge", "first"],
                     ["- [[Desk_02_Sports_Desk|Desk 2: Sports Desk]]", item_link(vault, "Item_15_Closing_Line_Value_CLV_Tracker_Soft", "Item 15: CLV tracker & soft-book health")],
                     dev, [{"id": "sports_market", "resource": rel_to(dev_root / SPORTS_DB, dev_root), "title": "sports_market.db edge_opportunities (mode=ro)",
                            "author": "process:Sports_Desk.odds_watcher"}], at, by)


# ---------------------------------------------------------------- driver

@dataclass
class EntitiesReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def ingest_entities(vault: Path, dev_root: Path, *, at: datetime | None = None, by: str = GENERATED_BY,
                    limit_whales: int = 100, limit_titans: int = 100) -> EntitiesReport:
    at = at or now_utc()
    report = EntitiesReport()
    cache = load_titan_cache(dev_root / TITAN_CACHE)
    if not cache:
        report.missing_sources.append(TITAN_CACHE.as_posix())
    existing_whales = {p.stem[len("whale_"):].lower() for p in (vault / "crm" / "whales").glob("whale_*.md")}
    whales, whale_equity = load_whales(dev_root / HL_DB, limit_whales, keep=existing_whales)
    whale_addrs = set(whale_equity)
    if not whale_addrs and not (dev_root / HL_DB).is_file():
        report.missing_sources.append(HL_DB.as_posix())
    sharps, tracked = load_sharps(dev_root / PM_DB)
    if not sharps and not (dev_root / PM_DB).is_file():
        report.missing_sources.append(PM_DB.as_posix())
    books = load_books(dev_root / SPORTS_DB)
    if not books and not (dev_root / SPORTS_DB).is_file():
        report.missing_sources.append(SPORTS_DB.as_posix())

    whale_by_addr = {str(w["address"]).lower(): w for w in whales}
    sharp_by_eoa = {str(s["eoa_address"]).lower(): s for s in sharps if s.get("eoa_address")}
    sharp_by_wallet = {str(s["wallet"]).lower(): s for s in sharps}
    pm_wallets: set[str] = set(sharp_by_wallet) | set(tracked)
    pm_wallets |= {str(s["proxy_wallet"]).lower() for s in sharps if s.get("proxy_wallet")}
    pm_wallets |= set(sharp_by_eoa)

    # a titan needs presence on BOTH venues (see the module docstring)
    titan_map: dict[str, dict[str, Any]] = {}
    for eoa, entry in cache.items():
        proxy = str(entry.get("proxy_wallet") or "").lower()
        if eoa in sharp_by_eoa or (proxy and proxy in pm_wallets):
            titan_map[eoa] = dict(entry, proxy_wallet=proxy or None, in_whales=eoa in whale_addrs,
                                  source="titan_identities_cache.json (Gamma EOA -> proxy) + Polymarket trader tables")
    for eoa, s in sharp_by_eoa.items():
        if eoa in whale_addrs and eoa not in titan_map:
            titan_map[eoa] = {"proxy_wallet": str(s.get("proxy_wallet") or s.get("wallet")).lower(), "pseudonym": s.get("pseudonym"),
                              "in_whales": True, "source": "sharp_traders.eoa_address -> whale_wallets"}
    titan_eoas = sorted(titan_map, key=lambda e: (-whale_equity.get(e, 0.0), e))[:limit_titans]
    titans = set(titan_eoas)
    titan_by_proxy = {str(titan_map[e].get("proxy_wallet")): e for e in titan_eoas if titan_map[e].get("proxy_wallet")}

    def sharp_for(eoa: str) -> dict[str, Any] | None:
        proxy = titan_map[eoa].get("proxy_wallet")
        return sharp_by_eoa.get(eoa) or (sharp_by_wallet.get(proxy) if proxy else None) \
            or next((s for s in sharps if proxy and str(s.get("proxy_wallet") or "").lower() == proxy), None)

    def emit(page: Page, created: bool) -> None:
        # Ruling R104-3: "updated" must mean the page actually moved. write_page already declines to
        # rewrite identical content, so counting every call as an update reported 184 updates on a
        # run that changed nothing, and appended a log line saying so.
        changed = page_changed(page, vault)
        write_page(page, vault, now=at)
        if changed:
            (report.created if created else report.updated).append(page.path.relative_to(vault).as_posix())

    for eoa in titan_eoas:
        emit(*build_titan(eoa, titan_map[eoa], whale_by_addr.get(eoa), sharp_for(eoa), vault, dev_root, at, by))
    for rank, w in enumerate(whales, 1):
        emit(*build_whale(w, rank, {k: titan_map[k] for k in titans}, vault, dev_root, at, by))
    for s in sharps:
        emit(*build_sharp(s, tracked, titans, vault, dev_root, at, by, titan_by_proxy))
    for name in sorted(books):
        emit(*build_book(name, books[name], vault, dev_root, at, by))
    report.counts = {"titans": len(titan_eoas), "whales": len(whales), "sharps": len(sharps), "books": len(books)}

    if report.created or report.updated:
        write_page(update_register(vault, "Entity", at=at, by=by), vault, now=at)
        write_index(vault, load_pages(vault))
        append_log(vault, "Ingest", f"CRM entities: {report.counts['titans']} titan(s) (identities present on both venues, cap {limit_titans}), "
                   f"{report.counts['whales']} whale(s) (top by equity, cap {limit_whales}), {report.counts['sharps']} sharp(s), "
                   f"{report.counts['books']} book(s); {len(report.created)} created, {len(report.updated)} updated (judgement kept, evidence appended); "
                   f"[index](index.md) rebuilt.", when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.entities", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--limit-whales", type=int, default=100)
    ap.add_argument("--limit-titans", type=int, default=100)
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    report = ingest_entities(args.vault, args.dev_root, at=at_from(args), limit_whales=args.limit_whales, limit_titans=args.limit_titans)
    for m in report.missing_sources:
        print(f"[SKIP]  source not found: {m}", file=out)
    print(f"entities: {report.counts} · {len(report.created)} created, {len(report.updated)} updated", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
