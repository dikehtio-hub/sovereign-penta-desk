"""raw/index.md: the manifest of every federated raw stream, in the OKF index format.

    python -m knowledge.raw_manifest [--vault DIR] [--dev-root DIR] [--dry-run]

The raw layer is not copied into the vault (R95-A); this file is how an agent
finds it. One section per desk, one line per stream, path RELATIVE TO raw/ so
Obsidian and lint (L2 resolves entry paths against the index's own folder) can
both follow it. Streams that do not exist on this machine are listed under a
final "Not present" section so the reader knows they are expected, and lint
does not try to resolve them (no link).
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from . import DEV_ROOT, EXIT_HALT, EXIT_OK, VAULT, halted
from .pages import assert_owned


@dataclass(frozen=True)
class Stream:
    desk: str
    title: str
    path: str          # relative to the DEV root
    description: str
    owner: str         # actor that writes it


STREAMS: tuple[Stream, ...] = (
    Stream("Desk 1: HyperLiquid Monarch", "Hyperliquid snapshot warehouse", "HyperLiquid/HL_Monarch/data/hyperliquid_data.db",
           "SQLite, 13 tables (asset_snapshots, orderbook_snapshots, trades, liquidation_events, liquidation_clusters, cascade_excursions, basis_realised_windows, whale_wallets, cross_market_titans, measurement_watermarks). Open read-only: file:...?mode=ro", "process:HL_Monarch.collector"),
    Stream("Desk 1: HyperLiquid Monarch", "Collector service log", "HyperLiquid/HL_Monarch/data/collector_service.jsonl",
           "JSONL coverage reports (uptime, coverage_pct, samples) from the supervised collector", "process:HL_Monarch.run_collector_service"),
    Stream("Desk 1: HyperLiquid Monarch", "HL experiments", "HyperLiquid/HL_Monarch/data/experiments/",
           "pre-registered basis experiments: the N=12 unfiltered baseline (never overwritten) and *.meta.json registrations", "human:operator"),
    Stream("Desk 1: HyperLiquid Monarch", "Paper trading state", "HyperLiquid/HL_Monarch/data/paper_trading_state.json",
           "paper account state written by the paper trader", "process:HL_Monarch.paper_trader"),
    Stream("Desk 2: Sports Desk", "Sports market database", "Sports_Desk/data/sports_market.db",
           "SQLite: fair_odds_measurements, edge_opportunities, placed_bets, settled_results, brier_snapshots, processed_*_files", "process:Sports_Desk.odds_watcher"),
    Stream("Desk 2: Sports Desk", "Polymarket drops", "Sports_Desk/data/polymarket_drops/",
           "stamped polymarket_macro_*.json and polymarket_sports_*.json (one record per question: token_id, condition_id, yes_price, yes_bid, fetched_at, tags after Round 76) plus the canonical polymarket_macro.json / polymarket_sports.json; the Item 18 series; lint C2 reads the newest", "process:cross_market.ingestors.polymarket_fetcher"),
    Stream("Desk 2: Sports Desk", "Odds and results drops", "Sports_Desk/data/odds_drops/",
           "CSV odds drops (processed/ once imported) and results_drops/ for settlements", "human:operator"),
    Stream("Desk 3: Cross-Market Desk", "CLOB book stamps", "cross_market/data/clob_books/",
           "one JSON per token per stamp: market, asset_id, hash, bids, asks, neg_risk, fee_rate, observed_at; drill folders below it (fomc_2026-09-16/) from --record-loop", "process:cross_market.latency_sniper"),
    Stream("Desk 3: Cross-Market Desk", "Pre-registrations", "cross_market/experiments/",
           "lead_lag_tier2.meta.json, lead_lag_tier2b.meta.json, fomc_2026-09-16.rules.json (+ sniper_rules.sample.json placeholder); never edited inside a window; ingested by knowledge.ingest.experiments", "human:operator"),
    Stream("Desk 3: Cross-Market Desk", "Paper receipts", "cross_market/data/paper_receipts/",
           "PAPER receipts (paper:1) from execution_log --paper, latency_sniper --paper, amm_rewards --paper; the journal's Executions source (R95-F)", "process:cross_market.execution_log"),
    Stream("Desk 3: Cross-Market Desk", "Titan identity cache", "cross_market/titan_identities_cache.json",
           "Hyperliquid EOA -> Polymarket proxy wallet + pseudonym, resolved by titan_correlator --resolve; the crm/titans seed", "process:cross_market.titan_correlator"),
    Stream("Desk 3: Cross-Market Desk", "Exporter and protocol logs", "cross_market/data/cross_market_exporter.log",
           "the Cross-Market Arb exporter loop log (lead-lag gate telemetry every ~15 s); maiden_protocol_*.log and fomc_drill_*.log sit beside it", "process:cross_market.interfaces.obsidian_exporter"),
    Stream("Desk 3: Cross-Market Desk", "Polymarket whale database", "Polymarket/Polymarket_Monarch/data/polymarket_whales.db",
           "SQLite: sharp_traders, tracked_wallets, whale_trades; the crm/sharps seed", "process:Polymarket_Monarch.whale_collector"),
    Stream("Desk 4: Quant Trading Lab", "Continuous futures and crypto OHLCV", "quant_trading_lab/data/continuous/",
           "stitched continuous contracts (NQ ES GC CL) and BTC/ETH perps at 1m-1d; gitignored, re-fetchable", "process:quant_trading_lab.scripts.fetch_historical_continuous"),
    Stream("Desk 4: Quant Trading Lab", "Runtime state", "quant_trading_lab/state/runtime_state.json",
           "Risk Sentinel state (daily and cumulative P&L, halts, consecutive losses) and virtual ticket sequence", "process:quant_trading_lab.engine.state_manager"),
    Stream("Desk 5: Tax Reserve Agent", "Tax ledger", "Tax_Reserve_Agent/data/tax_ledger.db",
           "SQLite: transactions, tax_lots, realized_pnl, agent_meta; the escrow and safe-bankroll source of truth", "process:Tax_Reserve_Agent.main"),
    Stream("Desk 5: Tax Reserve Agent", "Receipt imports", "Tax_Reserve_Agent/data/imports/",
           "CSV receipts the watcher ingests (samples/ committed, live files ignored)", "human:operator"),
    Stream("Human-authored", "Statements", "obsidian_vault/raw/statements/",
           "pasted statement text (FOMC, BLS) ingested into Event and Source Summary pages", "human:operator"),
    Stream("Human-authored", "Memos", "obsidian_vault/raw/memos/",
           "operator voice-memo transcripts and notes", "human:operator"),
    Stream("Human-authored", "Post-mortems", "obsidian_vault/raw/postmortems/",
           "dated post-mortem write-ups, one per incident", "human:operator"),
)


def build_manifest(dev_root: Path, vault: Path) -> str:
    raw_dir = (vault / "raw").resolve()
    present: dict[str, list[str]] = {}
    absent: list[str] = []
    for s in STREAMS:
        target = (dev_root / s.path).resolve()
        if target.exists():
            rel = Path(os.path.relpath(target, raw_dir)).as_posix()
            if s.path.endswith("/") and not rel.endswith("/"):
                rel += "/"
            present.setdefault(s.desk, []).append(f"* [{s.title}]({rel}) - {s.description} (writer: `{s.owner}`)")
        else:
            absent.append(f"> not present: {s.title} (`{s.path}`) - {s.description}")
    lines: list[str] = []
    for desk in sorted(present):
        lines.append(f"# {desk}")
        lines += present[desk]
        lines.append("")
    if absent:
        lines.append("# Not present on this machine")
        lines += absent
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def write_manifest(dev_root: Path, vault: Path) -> Path:
    target = vault / "raw" / "index.md"
    assert_owned(target, vault)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_manifest(dev_root, vault))
    return target


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.raw_manifest", description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if halted(args.dev_root):
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - manifest refuses (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    text = build_manifest(args.dev_root, args.vault)
    if args.dry_run:
        print(text, file=out)
        return EXIT_OK
    target = write_manifest(args.dev_root, args.vault)
    n = sum(1 for l in text.splitlines() if l.startswith("* ["))
    print(f"raw manifest: {n} stream(s) present -> {target}", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
