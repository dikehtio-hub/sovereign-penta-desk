#!/usr/bin/env python3
"""
Pre-Registered Intraday Funding Rate Profile Diagnostic.

Evaluates whether HyperLiquid hourly perp funding exhibits a systematic
diurnal difference between European/US daytime (07Z-16Z) and Asian/evening (17Z-06Z).

Pre-Registered Metrics & Thresholds (Dual-Cohort):
1. Cohort A (Core Liquid: BTC, ETH, SOL):
   - Delta APR = (mean_funding_day - mean_funding_eve) * 8760
   - Flag trigger: |Delta APR| > 5.0 % on any core asset.

2. Cohort B (Harvester Universe: evening APR >= 10%, spot volume >= $100k):
   - RelDev = (mean_funding_day - mean_funding_eve) / mean_funding_eve
   - Flag trigger: Pooled median RelDev outside [-0.25, +0.33] (i.e. < 0.75x or > 1.33x)
     on >= 10 qualifying coins.

Designated pilot run: Night 2026-09-20/2026-09-21 continuous segment.
Status: Pilot (N=1), screening flag only. Full certification requires 3 consecutive nights.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data" / "hyperliquid_data.db"
CORE_COINS = ("BTC", "ETH", "SOL")


def parse_iso_to_epoch_ms(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def format_epoch_ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 != 0 else (s[mid - 1] + s[mid]) / 2.0


def evaluate_windows(
    db_path: Path,
    eve_start_ms: int,
    eve_end_ms: int,
    day_start_ms: int,
    day_end_ms: int,
    min_volume_usd: float = 100_000.0,
    min_eve_apr: float = 0.10,
) -> None:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    print(f"Connecting to: {uri}")
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row

    # Query mean funding, volume, and OI for both windows
    query = """
    SELECT 
        coin,
        AVG(CASE WHEN timestamp >= ? AND timestamp < ? THEN funding_rate ELSE NULL END) as eve_funding,
        AVG(CASE WHEN timestamp >= ? AND timestamp < ? THEN day_ntl_vlm ELSE NULL END) as eve_volume,
        AVG(CASE WHEN timestamp >= ? AND timestamp < ? THEN notional_oi ELSE NULL END) as eve_oi,
        AVG(CASE WHEN timestamp >= ? AND timestamp < ? THEN funding_rate ELSE NULL END) as day_funding,
        AVG(CASE WHEN timestamp >= ? AND timestamp < ? THEN day_ntl_vlm ELSE NULL END) as day_volume,
        AVG(CASE WHEN timestamp >= ? AND timestamp < ? THEN notional_oi ELSE NULL END) as day_oi,
        COUNT(CASE WHEN timestamp >= ? AND timestamp < ? THEN 1 ELSE NULL END) as eve_samples,
        COUNT(CASE WHEN timestamp >= ? AND timestamp < ? THEN 1 ELSE NULL END) as day_samples
    FROM asset_snapshots
    GROUP BY coin
    HAVING (eve_samples > 0 OR day_samples > 0)
    """

    params = (
        eve_start_ms, eve_end_ms,
        eve_start_ms, eve_end_ms,
        eve_start_ms, eve_end_ms,
        day_start_ms, day_end_ms,
        day_start_ms, day_end_ms,
        day_start_ms, day_end_ms,
        eve_start_ms, eve_end_ms,
        day_start_ms, day_end_ms,
    )

    rows = conn.execute(query, params).fetchall()
    conn.close()

    print("\n" + "=" * 80)
    print("INTRADAY FUNDING RATE PROFILE EVALUATION (07Z-16Z vs 17Z-06Z)")
    print("=" * 80)
    print(f"Evening Window : {format_epoch_ms_to_iso(eve_start_ms)} -> {format_epoch_ms_to_iso(eve_end_ms)}")
    print(f"Daytime Window : {format_epoch_ms_to_iso(day_start_ms)} -> {format_epoch_ms_to_iso(day_end_ms)}")
    print(f"Total Assets Evaluated: {len(rows)}")

    cohort_a_results = []
    cohort_b_results = []

    for r in rows:
        coin = r["coin"]
        eve_f = r["eve_funding"]
        day_f = r["day_funding"]
        eve_vol = r["eve_volume"] or 0.0
        eve_oi = r["eve_oi"] or 0.0

        if eve_f is None or day_f is None:
            continue

        eve_apr = eve_f * 8760.0
        day_apr = day_f * 8760.0
        delta_apr = day_apr - eve_apr

        # Cohort A: Core Liquid Assets
        if coin in CORE_COINS:
            cohort_a_results.append({
                "coin": coin,
                "eve_apr": eve_apr,
                "day_apr": day_apr,
                "delta_apr": delta_apr,
                "eve_samples": r["eve_samples"],
                "day_samples": r["day_samples"],
            })

        # Cohort B: Harvester Qualifying Universe
        # Filter: baseline evening APR >= min_eve_apr (10%), volume >= min_volume_usd ($100k)
        if eve_apr >= min_eve_apr and eve_vol >= min_volume_usd:
            reldev = (day_f - eve_f) / eve_f if eve_f > 0 else 0.0
            cohort_b_results.append({
                "coin": coin,
                "eve_apr": eve_apr,
                "day_apr": day_apr,
                "delta_apr": delta_apr,
                "reldev": reldev,
                "volume": eve_vol,
                "oi": eve_oi,
            })

    # --- Print Cohort A ---
    print("\n--- COHORT A: Core Liquid Assets (BTC, ETH, SOL) ---")
    print(f"{'Coin':<8} {'Eve APR':<12} {'Day APR':<12} {'Delta APR':<12} {'Threshold':<12} {'Status'}")
    print("-" * 65)
    cohort_a_flags = 0
    for res in cohort_a_results:
        flagged = abs(res["delta_apr"]) > 0.05  # > 5.0% APR
        if flagged:
            cohort_a_flags += 1
        status_str = "SURPRISE_FLAG" if flagged else "NORMAL"
        print(f"{res['coin']:<8} {res['eve_apr']*100:>8.2f}% {res['day_apr']*100:>8.2f}% {res['delta_apr']*100:>+8.2f}% {'|Δ| > 5.0%':<12} {status_str}")

    # --- Print Cohort B ---
    print(f"\n--- COHORT B: Harvester Qualifying Universe (Eve APR >= {min_eve_apr*100:.0f}%, Vol >= ${min_volume_usd:,.0f}) ---")
    print(f"Qualified Coins Count: {len(cohort_b_results)}")

    if cohort_b_results:
        reldevs = [c["reldev"] for c in cohort_b_results]
        med_reldev = median(reldevs)
        cohort_b_flag = (len(cohort_b_results) >= 10) and (med_reldev < -0.25 or med_reldev > 0.33)

        print(f"Pooled Median RelDev: {med_reldev*100:+.2f}%  (Nominal acceptance band: [-25.0%, +33.0%])")
        print(f"{'Coin':<10} {'Eve APR':<12} {'Day APR':<12} {'RelDev':<12} {'Volume 24h':<14} {'OI Notional'}")
        print("-" * 75)
        for res in sorted(cohort_b_results, key=lambda x: x["oi"], reverse=True)[:15]:
            print(f"{res['coin']:<10} {res['eve_apr']*100:>8.2f}% {res['day_apr']*100:>8.2f}% {res['reldev']*100:>+8.2f}% ${res['volume']:>12,.0f} ${res['oi']:>12,.0f}")
        if len(cohort_b_results) > 15:
            print(f"... and {len(cohort_b_results) - 15} more coins.")
    else:
        med_reldev = 0.0
        cohort_b_flag = False
        print("No qualifying coins met both volume and APR thresholds in the evening window.")

    # --- Final Conclusion ---
    print("\n" + "=" * 80)
    print("PRE-REGISTERED RULING & VERDICT")
    print("=" * 80)
    if cohort_a_flags > 0 or cohort_b_flag:
        print("RESULT: [SURPRISE FLAG TRIGGERED]")
        print("Evidence indicates meaningful diurnal funding rate divergence between daytime and evening.")
        print("Action: Entry APR calculation should adopt a 24-hour rolling TWAP (TWAP_24h) rather than instantaneous spot APR.")
    else:
        print("RESULT: [NORMAL VARIANCE / FAIR SAMPLE]")
        print("Evening funding sample aligns within nominal limits of daytime funding.")
        print("Action: Evening-only sampling is fair; no structural distortion detected on this pilot night.")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Intraday Perp Funding Profile (07Z-16Z vs 17Z-06Z)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to hyperliquid_data.db")
    parser.add_argument("--eve-start", default="2026-09-20T17:00:00Z", help="Start ISO timestamp of evening window")
    parser.add_argument("--eve-end", default="2026-09-21T06:00:00Z", help="End ISO timestamp of evening window")
    parser.add_argument("--day-start", default="2026-09-21T07:00:00Z", help="Start ISO timestamp of daytime window")
    parser.add_argument("--day-end", default="2026-09-21T16:00:00Z", help="End ISO timestamp of daytime window")
    parser.add_argument("--min-volume", type=float, default=100_000.0, help="Minimum 24h notional volume in USD")
    parser.add_argument("--min-eve-apr", type=float, default=0.10, help="Minimum evening APR hurdle (e.g. 0.10 = 10 percent)")

    args = parser.parse_args()

    eve_start_ms = parse_iso_to_epoch_ms(args.eve_start)
    eve_end_ms = parse_iso_to_epoch_ms(args.eve_end)
    day_start_ms = parse_iso_to_epoch_ms(args.day_start)
    day_end_ms = parse_iso_to_epoch_ms(args.day_end)

    evaluate_windows(
        args.db,
        eve_start_ms,
        eve_end_ms,
        day_start_ms,
        day_end_ms,
        min_volume_usd=args.min_volume,
        min_eve_apr=args.min_eve_apr,
    )


if __name__ == "__main__":
    main()
