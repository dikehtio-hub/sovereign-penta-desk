"""
👑 Tax Reserve Agent - Obsidian Vault Synchronizer & Ingestion Watcher
Continuously monitors data/imports/ for live execution receipts and exports
real-time tax escrow reserves, safe deployable bankrolls, and strategy bucket
exposure directly into your Obsidian Command Center.

Usage:
  python obsidian_sync.py --once
  python obsidian_sync.py --watch --interval 15 --vault "C:/path/to/vault"
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .config import load_config
from .database.db import init_db
from .engine.tax_calculator import calculate_tax_summary
from .interfaces.obsidian_export import export_summary_to_obsidian
from .ingestors.csv_watcher import CSVWatcher


def sync_cycle(watcher: CSVWatcher, vault_path: str = "") -> dict:
    """Runs one scan of the drop folder and updates the Obsidian tax card."""
    results = watcher.scan_once(require_stable=True)
    ingested_rows = sum(r.get("rows", 0) for r in results if r.get("status") == "ok")

    config = load_config()
    summary = calculate_tax_summary(tax_year=datetime.now().year, config=config)
    out_file = export_summary_to_obsidian(summary, vault_path_override=vault_path)

    return {
        "ingested_rows": ingested_rows,
        "escrow": summary.get("tax_escrow_reserve", 0.0),
        "safe_bankroll": summary.get("safe_deployable_bankroll", 0.0),
        "escrow_pct": summary.get("reserve_ratio_pct", 0.0),
        "out_file": out_file,
    }


def main():
    parser = argparse.ArgumentParser(description="Tax Reserve Agent Obsidian Synchronizer & Watcher")
    parser.add_argument("--watch", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--once", action="store_true", help="Run a single export cycle and exit")
    parser.add_argument("--interval", type=float, default=15.0, help="Poll interval in seconds (default: 15)")
    parser.add_argument("--vault", type=str, default="", help="Path to Obsidian Vault directory")
    args = parser.parse_args()

    init_db()
    config = load_config()
    vault = args.vault or config.get("output", {}).get("obsidian_vault_path", "")

    drop_folder = Path("Tax_Reserve_Agent/data/imports").resolve()
    watcher = CSVWatcher(imports_dir=drop_folder, archive=True)

    print("======================================================================")
    print("👑 Tax & Bankroll Reserve Agent - Obsidian Synchronizer")
    print(f"   Drop folder: {drop_folder}")
    print(f"   Vault path:  {vault or '[from config.yaml]'}")
    print("======================================================================")

    if not args.watch:
        status = sync_cycle(watcher, vault_path=vault)
        print(f"[OK] Single sync cycle completed at {datetime.now():%H:%M:%S}")
        print(f"     Escrow: ${status['escrow']:,.2f} ({status['escrow_pct']:.1f}%) | "
              f"Safe Bankroll: ${status['safe_bankroll']:,.2f}")
        return

    print(f"[SYNC] Monitoring imports and updating Obsidian every {args.interval:g}s. Ctrl-C to stop.\n")
    try:
        while True:
            status = sync_cycle(watcher, vault_path=vault)
            now = datetime.now().strftime("%H:%M:%S")
            msg = (f"[{now}] Safe Bankroll: ${status['safe_bankroll']:,.2f} | "
                   f"Escrow: ${status['escrow']:,.2f} ({status['escrow_pct']:.1f}%)")
            if status["ingested_rows"] > 0:
                msg += f" | Ingested: {status['ingested_rows']} fills"
            print(msg)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[STOP] Tax Reserve synchronizer gracefully terminated.")


if __name__ == "__main__":
    main()
