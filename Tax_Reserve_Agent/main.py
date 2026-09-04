"""
Main CLI entrypoint for Tax Reserve Agent.
"""
import sys
import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .database.db import DB_PATH, init_db
from .config import load_config
from .engine.lot_engine import process_batch
from .engine.tax_calculator import calculate_tax_summary
from .engine.lot_engine import rebuild_lots, resolve_method
from .engine.loss_harvester import LossHarvester
from .interfaces.tax_calendar import build_calendar
from .interfaces.cli import render_hud, render_strategy_table, run_health_check
from .interfaces.obsidian_export import export_summary_to_obsidian
from .ingestors.polymarket import (PolymarketIngestor, PolymarketChainIngestor,
                                   PolygonRPCClient, CTF_CONTRACT_ADDRESS,
                                   REORG_SAFETY_BLOCKS)
from .ingestors.spot import SpotIngestor
from .ingestors.options import OptionsIngestor
from .ingestors.csv_watcher import CSVWatcher
from .ingestors.market_resolution import MarketResolutionSync
from .interfaces.monarch_hook import MonarchBankrollHook

def seed_demo_trades():
    """Seeds sample multi-asset transactions to demonstrate real-time escrow math."""
    demo_txs = [
        # 1. Polymarket Trades
        PolymarketIngestor.create_manual_trade("FED_RATE_CUT_SEPT_YES", "BUY", 2000, 0.40, "2026-02-10 14:00:00", fee=0.0),
        PolymarketIngestor.create_redemption_trade("FED_RATE_CUT_SEPT_YES", 2000, "2026-03-01 18:00:00", fee=0.0), # Gain: 2000 * (1.00 - 0.40) = +$1,200
        
        PolymarketIngestor.create_manual_trade("ETH_ETF_APPROVAL_YES", "BUY", 1000, 0.70, "2026-02-15 10:00:00", fee=0.0),
        PolymarketIngestor.create_manual_trade("ETH_ETF_APPROVAL_YES", "SELL", 1000, 0.95, "2026-02-28 12:00:00", fee=0.0), # Gain: 1000 * 0.25 = +$250

        # 2. Crypto Spot Trades
        SpotIngestor.create_trade("SOL/USDC", "BUY", 10.0, 150.0, "2026-01-10 09:00:00", fee=1.5),
        SpotIngestor.create_trade("SOL/USDC", "SELL", 10.0, 210.0, "2026-02-20 15:30:00", fee=1.5), # Gain: 10 * 60 - 3 = +$597

        # 3. Options (Deribit/TradFi)
        OptionsIngestor.create_long_option_buy("BTC-90K-CALL", 1.0, 500.0, "2026-01-05 11:00:00", fee=5.0),
        OptionsIngestor.create_option_expiration("BTC-90K-CALL", 1.0, "2026-01-30 08:00:00"), # Expired: Loss = -$505 (offsets gains)
    ]
    process_batch(demo_txs)
    print("[SUCCESS] Seeded multi-asset demo trades into SQLite ledger.")

def _ledger_counts() -> dict:
    """Row counts in the live ledger, or zeros if it does not exist yet."""
    counts = {"transactions": 0, "tax_lots": 0, "realized_pnl": 0}
    if not DB_PATH.exists():
        return counts
    conn = sqlite3.connect(DB_PATH)
    try:
        for table in counts:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return counts


def main():
    parser = argparse.ArgumentParser(description="Multi-Asset Tax Reserve & Safe Bankroll Agent")
    parser.add_argument("command", nargs="?", default="hud",
                        choices=["hud", "sync", "chain-sync", "resolve-markets", "import", "watch",
                                 "bankroll", "harvest", "calendar", "rebuild", "strategies",
                                 "health", "seed", "export", "init"],
                        help=("hud (default) | sync (REST data API) | chain-sync (Gnosis CTF logs + CLOB subgraph) "
                              "| import (one sweep of the CSV drop folder) | watch (poll the drop folder) "
                              "| resolve-markets (settle open lots in markets that have resolved) "
                              "| bankroll (bot-facing sizing check) | harvest (tax-loss scan) "
                              "| calendar (quarterly estimated tax schedule) "
                              "| rebuild (re-match every lot) | strategies (capital and attribution) "
                              "| health (exit 1 if review needed) "
                              "| seed | export | init"))
    parser.add_argument("--year", type=int, default=2026, help="Tax year to calculate (default: 2026)")
    parser.add_argument("--cash", type=float, default=None, help="Override current liquid balance")
    parser.add_argument("--from-block", type=int, default=None, help="chain-sync: first Polygon block to scan")
    parser.add_argument("--to-block", type=int, default=None, help="chain-sync: last Polygon block to scan")
    parser.add_argument("--interval", type=float, default=None, help="watch: seconds between drop-folder polls")
    parser.add_argument("--check", type=float, default=None, help="bankroll: order notional to test in USD")
    parser.add_argument("--apply", action="store_true",
                        help="resolve-markets: commit the plan (default is a dry run)")
    parser.add_argument("--force", action="store_true",
                        help="init: archive the existing ledger and start an empty one")
    parser.add_argument("--trust-gamma", action="store_true",
                        help="resolve-markets: accept Gamma's resolution without on-chain payout verification")
    parser.add_argument("--losers-only", action="store_true",
                        help="resolve-markets: write off worthless legs only, leaving winners open")
    parser.add_argument("--as-of", type=str, default=None,
                        help="resolve-markets: settlement date for markets Gamma gives no resolution date for; "
                             "harvest: holding-period cutoff")
    parser.add_argument("--method", type=str, default=None, choices=["FIFO", "HIFO"],
                        help="rebuild: accounting method to re-match under (default: config.yaml)")
    parser.add_argument("--marks", type=Path, default=None,
                        help="harvest: path to a marks CSV (default: data/marks.csv)")
    parser.add_argument("--live-marks", action="store_true",
                        help="harvest: price open Polymarket positions off the live CLOB midpoint")

    args = parser.parse_args()
    init_db()

    config = load_config()
    if args.cash is not None:
        config.setdefault("portfolio", {})["default_cash_balance_usdc"] = args.cash

    if args.command == "init":
        # PLAIN `init` IS NOT A RESET. It runs CREATE TABLE IF NOT EXISTS and
        # deletes nothing - the old message said "Database initialized", which
        # reads exactly like a wipe to anyone trying to clear demo data before
        # going live. Saying what actually happened is the whole fix.
        counts = _ledger_counts()
        if not args.force:
            if any(counts.values()):
                print(f"[OK] Schema is present. The ledger already holds "
                      f"{counts['transactions']} transaction(s), {counts['tax_lots']} lot(s) "
                      f"and {counts['realized_pnl']} realised row(s) - NOTHING WAS DELETED.")
                print("     To archive it and start empty, re-run with --force.")
            else:
                print("[OK] Schema is present. The ledger is empty.")
            return

        if not any(counts.values()):
            print("[OK] Ledger is already empty; nothing to archive.")
            return

        # Archive rather than delete. Clearing a tax ledger on a flag is not
        # something to do irreversibly, and the demo rows this exists to remove
        # are indistinguishable from real ones once they are gone.
        archive = DB_PATH.with_name(f"{DB_PATH.stem}.{datetime.now():%Y%m%d_%H%M%S}.bak")
        try:
            shutil.copy2(DB_PATH, archive)
        except OSError as e:
            print(f"[ABORT] Could not archive the existing ledger ({e}). Nothing was changed.")
            sys.exit(1)

        conn = sqlite3.connect(DB_PATH)
        try:
            with conn:
                conn.execute("DELETE FROM realized_pnl")
                conn.execute("DELETE FROM tax_lots")
                conn.execute("DELETE FROM transactions")
        finally:
            conn.close()

        print(f"[SUCCESS] Archived {counts['transactions']} transaction(s), "
              f"{counts['tax_lots']} lot(s) and {counts['realized_pnl']} realised row(s) to")
        print(f"          {archive.name}")
        print("          The live ledger is now EMPTY. Run `main health` to confirm the")
        print("          first reading is against an empty book.")
        return

    if args.command == "seed":
        seed_demo_trades()

    elif args.command == "sync":
        wallets = config.get("wallets", {}).get("polygon_wallets", [])
        print(f"Syncing on-chain trades for {len(wallets)} configured wallets...")
        poly = PolymarketIngestor(wallets)
        for w in wallets:
            trades = poly.fetch_trades_for_wallet(w)
            if trades:
                process_batch(trades)
                print(f"Synced {len(trades)} trades from {w[:8]}...")

    elif args.command == "chain-sync":
        chain_cfg = config.get("chain", {}) or {}
        wallets = config.get("wallets", {}).get("polygon_wallets", []) or []
        if not wallets:
            print("[WARN] No polygon_wallets configured in config.yaml - nothing to sync.")
        else:
            # Only pass overrides that are actually set - a blank config value must
            # fall through to the module default, not blank out the endpoint.
            kwargs = {"wallets": wallets,
                      "basis_allocation": chain_cfg.get("split_basis_allocation") or None,
                      "confirmations": int(chain_cfg.get("confirmations", REORG_SAFETY_BLOCKS)),
                      "polymarket_fee_rate": float(chain_cfg.get("polymarket_fee_rate", 0.0) or 0.0)}
            for key, cfg_key in (("rpc_url", "polygon_rpc_url"),
                                 ("subgraph_url", "orderbook_subgraph_url"),
                                 ("ctf_address", "ctf_contract")):
                if chain_cfg.get(cfg_key):
                    kwargs[key] = chain_cfg[cfg_key]
            endpoints = chain_cfg.get("polygon_rpc_endpoints") or []
            if endpoints:
                kwargs["rpc"] = PolygonRPCClient(endpoints=list(endpoints))
            ingestor = PolymarketChainIngestor(**kwargs)
            txs = ingestor.sync_all(
                from_block=args.from_block if args.from_block is not None else int(chain_cfg.get("start_block", 0)),
                to_block=args.to_block,
                include_clob=bool(chain_cfg.get("include_clob_fills", True)),
            )
            if txs:
                process_batch(txs)
                print(f"[SUCCESS] Committed {len(txs)} on-chain transactions to the ledger.")
            else:
                print("[INFO] No new on-chain activity found.")

    elif args.command in ("import", "watch"):
        imports_cfg = config.get("imports", {}) or {}
        drop_folder = Path(imports_cfg.get("drop_folder") or "data/imports")
        if not drop_folder.is_absolute():
            drop_folder = Path(__file__).parent / drop_folder
        watcher = CSVWatcher(imports_dir=drop_folder,
                             archive=bool(imports_cfg.get("archive_after_import", True)))
        if args.command == "import":
            # One-shot: no concurrent writer to race, so take files immediately.
            watcher.scan_once(require_stable=False)
        else:
            interval = args.interval if args.interval is not None else float(imports_cfg.get("poll_interval_seconds", 5))
            watcher.watch(interval_s=interval)

    elif args.command == "resolve-markets":
        chain_cfg = config.get("chain", {}) or {}
        rpc = None
        if not args.trust_gamma:
            rpc = PolygonRPCClient(rpc_url=chain_cfg.get("polygon_rpc_url"),
                                   endpoints=chain_cfg.get("polygon_rpc_endpoints") or None)
        syncer = MarketResolutionSync(
            rpc=rpc,
            ctf_address=chain_cfg.get("ctf_contract") or CTF_CONTRACT_ADDRESS,
            trust_gamma=args.trust_gamma,
            losers_only=args.losers_only,
        )
        plan = syncer.plan(as_of=args.as_of)
        print(plan.render())
        if not plan.settlements:
            print("\n[INFO] Nothing to settle.")
        elif args.apply:
            settled = syncer.apply(plan)
            print(f"\n[SUCCESS] Settled {settled} lot(s). Re-run `hud` to see the updated escrow.")
        else:
            print("\n[DRY RUN] Nothing was written. Re-run with --apply to commit this plan.")
        if args.trust_gamma and plan.settlements:
            print("[WARN] --trust-gamma: settlements were taken from Gamma without on-chain "
                  "payout verification. A market that closed but has not settled (or is disputed) "
                  "will book a loss that has not happened.")
        return

    elif args.command == "harvest":
        price_source = None
        if args.live_marks:
            from .engine.loss_harvester import PolymarketMarkSource
            price_source = PolymarketMarkSource()
        harvester = LossHarvester(config=config, marks_path=args.marks, price_source=price_source)
        print(harvester.analyze(tax_year=args.year, as_of=args.as_of).render())
        return

    elif args.command == "calendar":
        print(build_calendar(tax_year=args.year, config=config).render())
        return

    elif args.command == "rebuild":
        method = resolve_method(args.method)
        print(f"Re-matching every lot under {method}...")
        stats = rebuild_lots(method=method)
        print(f"[SUCCESS] Replayed {stats['transactions']} transactions: "
              f"{stats['realized_rows_before']} -> {stats['realized_rows_after']} realised rows.")
        summary = calculate_tax_summary(tax_year=args.year, config=config)
        print(render_hud(summary))
        return

    elif args.command == "health":
        bot_cfg = config.get("bot_integration", {}) or {}
        hook = MonarchBankrollHook(
            tax_year=args.year, config=config,
            max_position_pct=float(bot_cfg.get("max_position_pct", 0.05)),
            category_window=int(bot_cfg.get("category_window", 40)),
        )
        summary = calculate_tax_summary(tax_year=args.year, config=config)
        code, report = run_health_check(summary, hook.category_stats())
        print(report)
        sys.exit(code)

    elif args.command == "strategies":
        bot_cfg = config.get("bot_integration", {}) or {}
        hook = MonarchBankrollHook(
            tax_year=args.year, config=config,
            max_position_pct=float(bot_cfg.get("max_position_pct", 0.05)),
        )
        safe = hook.get_safe_bankroll(args.cash)
        budgets = {name: hook.strategy_budget(name, safe)
                   for name in hook.strategy_allocations}
        print(render_strategy_table(hook.strategy_stats(), budgets, safe))
        return

    elif args.command == "bankroll":
        bot_cfg = config.get("bot_integration", {}) or {}
        hook = MonarchBankrollHook(
            tax_year=args.year, config=config,
            max_position_pct=float(bot_cfg.get("max_position_pct", 0.05)),
            min_order_usd=float(bot_cfg.get("min_order_usd", 1.0)),
            allow_empirical_upsize=bool(bot_cfg.get("allow_empirical_upsize", False)),
            category_window=int(bot_cfg.get("category_window", 40)),
            min_category_trades=int(bot_cfg.get("min_category_trades", 5)),
            payoff_basis=str(bot_cfg.get("payoff_basis", "conservative")),
        )
        print(hook.status_line(args.cash))
        print(hook.strategy_report(args.cash))
        print(hook.category_report())
        print(f"[EDGE] After-tax break-even gross edge: "
              f"{hook.breakeven_gross_edge() * 100:.2f}% (below this is an after-tax loss)")
        if args.check is not None:
            print(hook.check_order(args.check, live_cash=args.cash))
        return

    # Always generate summary and show HUD
    summary = calculate_tax_summary(tax_year=args.year, config=config)
    print(render_hud(summary))

    if args.command == "export" or config.get("output", {}).get("export_to_obsidian"):
        out_file = export_summary_to_obsidian(summary)
        if out_file:
            print(f"\n[EXPORT] Saved report to Obsidian: {out_file}")

if __name__ == "__main__":
    main()
