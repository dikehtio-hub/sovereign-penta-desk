"""
Item 14 Whale Cascade Sweeper Replay Engine (Backlog B15).

Executes the retrospective statistical replay over cascade_excursions
accumulated in HyperLiquid/HL_Monarch/data/hyperliquid_data.db against the
acceptance bar pre-registered in whale_sweeper_cascade_replay.meta.json.

Guarantees & Constraints:
- Strict read-only SQLite connection: file:...?mode=ro.
- Treatment vs Synthetic Control: separates real liquidation cascades (event_id > 0)
  from matched random-entry controls (event_id < 0).
- Forward truncation audit: filters samples_60m >= 1 and audits the truncation rate.
- Sample requirements: asserts min 500 events, min 20 coins, max single coin share <= 0.20,
  max HHI <= 0.15.
- Cluster bootstrap: resamples coins with replacement (10,000 draws, seed 7) to
  evaluate P(fade_ratio_30m >= 1.25).
- Multi-metric reporting: reports median(MFE)/median(MAE), mean(MFE)/mean(MAE),
  dollar-weighted expectancy, win share, and side A vs side B asymmetry.
"""

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sqlite3
import statistics
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Pre-registered constants from whale_sweeper_cascade_replay.meta.json
REOPEN_MIN_EVENTS = 500
REOPEN_MIN_COINS = 20
REOPEN_MAX_COIN_SHARE = 0.20
REOPEN_MAX_HHI = 0.15
REOPEN_MIN_SAMPLES_60M = 1
ACCEPTANCE_THRESHOLD = 1.25
DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 7
DEFAULT_HORIZONS = ("5m", "15m", "30m", "60m")

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "hyperliquid_data.db"


def concentration_hhi(counts: Sequence[int]) -> float:
    """
    Herfindahl-Hirschman Index of per-coin event shares, normalized 0..1.
    HHI = sum(s_i^2) where s_i = c_i / total.
    """
    total = sum(counts)
    if total <= 0:
        return 0.0
    return sum((c / total) ** 2 for c in counts)


def load_cascade_excursions(
    db_path: Path | str,
    min_samples_60m: int = REOPEN_MIN_SAMPLES_60M,
    include_controls: bool = False,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Loads cascade excursion rows from SQLite read-only.
    Filters out incomplete forward series (samples_60m < min_samples_60m)
    and unmeasurable 30m windows.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_file}")

    uri = f"file:{db_file.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row

    try:
        # 1. Total rows in table
        total_in_table = conn.execute("SELECT COUNT(*) FROM cascade_excursions").fetchone()[0]

        # 2. Query qualifying rows
        query = """
            SELECT event_id, coin, timestamp_utc, source, cascade_side,
                   fade_is_long, notional_usd, event_px, entry_px,
                   mfe_5m, mae_5m, mfe_15m, mae_15m, mfe_30m, mae_30m,
                   mfe_60m, mae_60m, samples_60m, regime_tag
            FROM cascade_excursions
            WHERE 1=1
        """
        params: List[Any] = []

        if not include_controls:
            query += " AND event_id > 0 AND source NOT LIKE 'control:%'"

        if source:
            query += " AND source = ?"
            params.append(source)

        cursor = conn.execute(query, params)
        raw_rows = [dict(r) for r in cursor.fetchall()]

        # Audit filtering counts
        truncated_count = sum(1 for r in raw_rows if r["samples_60m"] < min_samples_60m)
        null_30m_count = sum(
            1 for r in raw_rows
            if r["mfe_30m"] is None or r["mae_30m"] is None
        )

        qualifying_rows = [
            r for r in raw_rows
            if r["samples_60m"] >= min_samples_60m
            and r["mfe_30m"] is not None
            and r["mae_30m"] is not None
        ]

        truncation_rate = (truncated_count / len(raw_rows)) if raw_rows else 0.0

        return {
            "rows": qualifying_rows,
            "total_in_table": total_in_table,
            "raw_loaded": len(raw_rows),
            "truncated_count": truncated_count,
            "null_30m_count": null_30m_count,
            "truncation_rate": truncation_rate,
            "qualifying_count": len(qualifying_rows),
        }
    finally:
        conn.close()


def evaluate_sample_gates(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates the pre-registered sample requirements:
    - min_events >= 500
    - min_coins >= 20
    - max_single_coin_share <= 0.20
    - max_hhi <= 0.15
    - min_samples_60m_per_event >= 1
    """
    n = len(rows)
    if n == 0:
        return {
            "passed": False,
            "status": "NO_DATA",
            "failures": ["No qualifying rows"],
            "metrics": {
                "events": 0,
                "coins": 0,
                "top_coin_share": 0.0,
                "hhi": 0.0,
            },
        }

    coin_counts = Counter(r["coin"] for r in rows)
    coins = len(coin_counts)
    top_coin, top_count = coin_counts.most_common(1)[0]
    top_share = top_count / n
    hhi = concentration_hhi(list(coin_counts.values()))

    failures: List[str] = []
    if n < REOPEN_MIN_EVENTS:
        failures.append(f"events={n} < {REOPEN_MIN_EVENTS}")
    if coins < REOPEN_MIN_COINS:
        failures.append(f"coins={coins} < {REOPEN_MIN_COINS}")
    if top_share > REOPEN_MAX_COIN_SHARE:
        failures.append(f"top_coin_share={top_share:.3f} ({top_coin}) > {REOPEN_MAX_COIN_SHARE:.2f}")
    if hhi > REOPEN_MAX_HHI:
        failures.append(f"hhi={hhi:.3f} > {REOPEN_MAX_HHI:.2f}")

    passed = len(failures) == 0
    status = "SAMPLE_ADEQUATE" if passed else "SAMPLE_TOO_NARROW"

    return {
        "passed": passed,
        "status": status,
        "failures": failures,
        "metrics": {
            "events": n,
            "coins": coins,
            "top_coin": top_coin,
            "top_coin_share": top_share,
            "hhi": hhi,
        },
    }


def compute_horizon_stats(rows: List[Dict[str, Any]], horizon: str) -> Dict[str, Any]:
    """
    Computes excursion statistics for a specific horizon (e.g. '30m').
    """
    mfe_col = f"mfe_{horizon}"
    mae_col = f"mae_{horizon}"

    valid_pairs = [
        (float(r[mfe_col]), float(r[mae_col]), float(r["notional_usd"]))
        for r in rows
        if r.get(mfe_col) is not None and r.get(mae_col) is not None
    ]

    if not valid_pairs:
        return {
            "horizon": horizon,
            "n": 0,
            "median_mfe": None,
            "median_mae": None,
            "median_fade_ratio": None,
            "mean_mfe": None,
            "mean_mae": None,
            "mean_fade_ratio": None,
            "win_share": None,
            "median_net_move": None,
            "dollar_expectancy": None,
        }

    mfes = [p[0] for p in valid_pairs]
    maes = [p[1] for p in valid_pairs]
    notionals = [p[2] for p in valid_pairs]

    med_mfe = statistics.median(mfes)
    med_mae = statistics.median(maes)
    mean_mfe = statistics.mean(mfes)
    mean_mae = statistics.mean(maes)

    med_ratio = (med_mfe / med_mae) if med_mae > 0 else None
    mean_ratio = (mean_mfe / mean_mae) if mean_mae > 0 else None
    win_share = sum(1 for m, a in zip(mfes, maes) if m > a) / len(valid_pairs) * 100.0
    net_moves = [m - a for m, a in zip(mfes, maes)]
    med_net = statistics.median(net_moves)

    total_notional = sum(notionals)
    dollar_exp = (
        sum((m - a) * notional for m, a, notional in valid_pairs) / total_notional
        if total_notional > 0 else 0.0
    )

    return {
        "horizon": horizon,
        "n": len(valid_pairs),
        "median_mfe": med_mfe,
        "median_mae": med_mae,
        "median_fade_ratio": med_ratio,
        "mean_mfe": mean_mfe,
        "mean_mae": mean_mae,
        "mean_fade_ratio": mean_ratio,
        "win_share": win_share,
        "median_net_move": med_net,
        "dollar_expectancy": dollar_exp,
    }


def cluster_bootstrap(
    rows: List[Dict[str, Any]],
    threshold: float = ACCEPTANCE_THRESHOLD,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    horizon: str = "30m",
) -> Dict[str, Any]:
    """
    Cluster bootstrap resampling COINS with replacement.
    Evaluates P(median(MFE) / median(MAE) >= threshold).
    """
    by_coin: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_coin.setdefault(r["coin"], []).append(r)

    coins = list(by_coin.keys())
    if not coins:
        return {
            "p_ge_threshold": None,
            "hits": 0,
            "resamples": resamples,
            "seed": seed,
            "threshold": threshold,
        }

    rng = random.Random(seed)
    hits = 0
    mfe_col = f"mfe_{horizon}"
    mae_col = f"mae_{horizon}"

    for _ in range(resamples):
        picked_coins = [coins[rng.randrange(len(coins))] for _ in coins]
        resample_rows = [r for c in picked_coins for r in by_coin[c]]

        valid_pairs = [
            (float(r[mfe_col]), float(r[mae_col]))
            for r in resample_rows
            if r.get(mfe_col) is not None and r.get(mae_col) is not None
        ]

        if not valid_pairs:
            continue

        mfes = [p[0] for p in valid_pairs]
        maes = [p[1] for p in valid_pairs]
        med_mfe = statistics.median(mfes)
        med_mae = statistics.median(maes)

        if med_mae > 0:
            ratio = med_mfe / med_mae
            if ratio >= threshold:
                hits += 1

    p_value = hits / resamples
    return {
        "p_ge_threshold": p_value,
        "hits": hits,
        "resamples": resamples,
        "seed": seed,
        "threshold": threshold,
    }


def classify_verdict(
    sample_gates: Dict[str, Any],
    cluster_p: Optional[float],
    cluster_p_side_a: Optional[float] = None,
    cluster_p_side_b: Optional[float] = None,
) -> str:
    """
    Classifies the outcome against the pre-registered acceptance bar:
    - INSUFFICIENT: any sample requirement unmet
    - FAIL: P(ratio >= 1.25) < 0.50
    - RETUNE: 0.50 <= P(ratio >= 1.25) <= 0.90
    - PASS: P(ratio >= 1.25) > 0.90
    - PASS-ASYMMETRIC: Pooled passes (>0.90), but Side A or Side B fails (<0.50)
    """
    if not sample_gates.get("passed", False):
        return "INSUFFICIENT"

    if cluster_p is None:
        return "INSUFFICIENT"

    if cluster_p < 0.50:
        return "FAIL"
    elif cluster_p <= 0.90:
        return "RETUNE"
    else:
        # Pooled passes > 0.90; check for severe asymmetry
        if (cluster_p_side_a is not None and cluster_p_side_a < 0.50) or (
            cluster_p_side_b is not None and cluster_p_side_b < 0.50
        ):
            return "PASS-ASYMMETRIC"
        return "PASS"


def run_replay(
    db_path: Path | str = DEFAULT_DB_PATH,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    include_controls: bool = False,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the end-to-end replay analysis.
    """
    data_load = load_cascade_excursions(
        db_path=db_path,
        min_samples_60m=REOPEN_MIN_SAMPLES_60M,
        include_controls=include_controls,
        source=source,
    )
    rows = data_load["rows"]

    # 1. Sample Gates
    gates = evaluate_sample_gates(rows)

    # 2. Multi-horizon stats on pooled sample
    horizons_stats = {h: compute_horizon_stats(rows, h) for h in DEFAULT_HORIZONS}

    # 3. Subgroup breakdown (Side A vs Side B) for 30m
    rows_side_a = [r for r in rows if str(r.get("cascade_side", "")).upper() == "A"]
    rows_side_b = [r for r in rows if str(r.get("cascade_side", "")).upper() == "B"]

    stats_side_a = compute_horizon_stats(rows_side_a, "30m")
    stats_side_b = compute_horizon_stats(rows_side_b, "30m")

    # 4. Cluster bootstrap (Pooled)
    bootstrap_res = cluster_bootstrap(
        rows=rows,
        threshold=ACCEPTANCE_THRESHOLD,
        resamples=resamples,
        seed=seed,
        horizon="30m",
    )

    # 5. Cluster bootstrap (Side A & Side B)
    bootstrap_a = cluster_bootstrap(
        rows=rows_side_a,
        threshold=ACCEPTANCE_THRESHOLD,
        resamples=resamples,
        seed=seed,
        horizon="30m",
    )
    bootstrap_b = cluster_bootstrap(
        rows=rows_side_b,
        threshold=ACCEPTANCE_THRESHOLD,
        resamples=resamples,
        seed=seed,
        horizon="30m",
    )

    # 6. Verdict Classification
    verdict = classify_verdict(
        sample_gates=gates,
        cluster_p=bootstrap_res.get("p_ge_threshold"),
        cluster_p_side_a=bootstrap_a.get("p_ge_threshold"),
        cluster_p_side_b=bootstrap_b.get("p_ge_threshold"),
    )

    # 7. Regime breakdown
    regimes = sorted(list(set(r.get("regime_tag", "UNKNOWN") for r in rows)))
    regime_stats = {
        reg: compute_horizon_stats([r for r in rows if r.get("regime_tag") == reg], "30m")
        for reg in regimes
    }

    return {
        # Ruling R104-2 (Round 105). Without this the artifact could not be ordered against another
        # run: cascade_excursions is written by a live collector and grows continuously, so two
        # results with different numbers and no instants are indistinguishable from a bug. Round 103
        # recorded two figures from this engine that had silently moved for exactly that reason.
        # Same shape as the R102-2 envelope on the lead-lag exporter, deliberately.
        "_artifact": {
            "written_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "writer": "HyperLiquid.HL_Monarch.analytics.cascade_replay",
            "rows_in_table": data_load["total_in_table"],
            "seed": seed,
        },
        "experiment": "whale_sweeper_cascade_replay",
        "verdict": verdict,
        "primary_metric": {
            "name": "fade_ratio_30m",
            "definition": "median(mfe_30m) / median(mae_30m)",
            "value": horizons_stats["30m"]["median_fade_ratio"],
            "comparison_mean_ratio": horizons_stats["30m"]["mean_fade_ratio"],
            "cluster_p_ge_1_25": bootstrap_res.get("p_ge_threshold"),
            "acceptance_threshold": ACCEPTANCE_THRESHOLD,
        },
        "sample_gates": gates,
        "data_audit": {
            "total_in_table": data_load["total_in_table"],
            "raw_loaded": data_load["raw_loaded"],
            "truncated_count": data_load["truncated_count"],
            "truncation_rate": data_load["truncation_rate"],
            "null_30m_count": data_load["null_30m_count"],
            "qualifying_count": data_load["qualifying_count"],
        },
        "horizons": horizons_stats,
        "asymmetry": {
            "side_A_sell_fade_buys": {
                "n": stats_side_a["n"],
                "median_fade_ratio_30m": stats_side_a["median_fade_ratio"],
                "mean_fade_ratio_30m": stats_side_a["mean_fade_ratio"],
                "dollar_expectancy": stats_side_a["dollar_expectancy"],
                "cluster_p_ge_1_25": bootstrap_a.get("p_ge_threshold"),
            },
            "side_B_buy_fade_sells": {
                "n": stats_side_b["n"],
                "median_fade_ratio_30m": stats_side_b["median_fade_ratio"],
                "mean_fade_ratio_30m": stats_side_b["mean_fade_ratio"],
                "dollar_expectancy": stats_side_b["dollar_expectancy"],
                "cluster_p_ge_1_25": bootstrap_b.get("p_ge_threshold"),
            },
        },
        "regime_breakdown": regime_stats,
        "bootstrap_config": {
            "resamples": resamples,
            "seed": seed,
            "threshold": ACCEPTANCE_THRESHOLD,
        },
    }


def format_report(result: Dict[str, Any]) -> str:
    lines = [
        "=" * 78,
        "ITEM 14: WHALE CASCADE SWEEPER RETROSPECTIVE REPLAY (B15)",
        "=" * 78,
        f"VERDICT: {result['verdict']}",
        "",
        "1. PRE-REGISTERED PRIMARY METRIC (30-Minute Horizon)",
        "-" * 78,
        f"  fade_ratio_30m (median/median):  {result['primary_metric']['value']:.4f}"
        if result['primary_metric']['value'] else "  fade_ratio_30m: N/A",
        f"  comparison ratio (mean/mean):     {result['primary_metric']['comparison_mean_ratio']:.4f}"
        if result['primary_metric']['comparison_mean_ratio'] else "  comparison ratio: N/A",
        f"  Cluster Bootstrap P(ratio>=1.25): {result['primary_metric']['cluster_p_ge_1_25']:.4f}"
        if result['primary_metric']['cluster_p_ge_1_25'] is not None else "  Cluster Bootstrap P: N/A",
        f"  Target Threshold:                 >= {result['primary_metric']['acceptance_threshold']:.2f} (Confidence > 0.90)",
        "",
        "2. SAMPLE REQUIREMENTS & GATING AUDIT",
        "-" * 78,
        f"  Status:          {result['sample_gates']['status']}",
        f"  Qualifying Rows: {result['sample_gates']['metrics']['events']} (min {REOPEN_MIN_EVENTS})",
        f"  Coins Measured:  {result['sample_gates']['metrics']['coins']} (min {REOPEN_MIN_COINS})",
        f"  Top Coin Share:  {result['sample_gates']['metrics']['top_coin_share'] * 100:.1f}% ({result['sample_gates']['metrics']['top_coin']}) (max {REOPEN_MAX_COIN_SHARE * 100:.0f}%)",
        f"  HHI:             {result['sample_gates']['metrics']['hhi']:.4f} (max {REOPEN_MAX_HHI:.4f})",
    ]

    if result["sample_gates"]["failures"]:
        lines.append("  Gating Failures: " + "; ".join(result["sample_gates"]["failures"]))

    lines.extend([
        "",
        "3. DATA TRUNCATION AUDIT",
        "-" * 78,
        f"  Total In Table:   {result['data_audit']['total_in_table']:,}",
        f"  Raw Queried:      {result['data_audit']['raw_loaded']:,}",
        f"  Truncated (<60m): {result['data_audit']['truncated_count']:,} ({result['data_audit']['truncation_rate'] * 100:.2f}%)",
        f"  Null 30m Windows: {result['data_audit']['null_30m_count']:,}",
        "",
        "4. MULTI-HORIZON EXCURSION PROFILE",
        "-" * 78,
        f"{'Horizon':<8} {'Events':<8} {'Median MFE':<12} {'Median MAE':<12} {'Med Ratio':<12} {'Mean Ratio':<12} {'Win %':<8} {'Exp ($)':<8}",
        "-" * 78,
    ])

    for h, d in result["horizons"].items():
        if d["n"] > 0:
            lines.append(
                f"{h:<8} {d['n']:<8} {d['median_mfe']:<12.4f} {d['median_mae']:<12.4f} "
                f"{(d['median_fade_ratio'] or 0.0):<12.4f} {(d['mean_fade_ratio'] or 0.0):<12.4f} "
                f"{d['win_share']:<8.1f} {d['dollar_expectancy']:<8.4f}"
            )
        else:
            lines.append(f"{h:<8} 0")

    lines.extend([
        "",
        "5. ASYMMETRY BREAKDOWN (Side A forced-sell vs Side B forced-buy, 30m)",
        "-" * 78,
        f"  Side A (Forced SELL -> Fade BUYS):  n={result['asymmetry']['side_A_sell_fade_buys']['n']}, "
        f"MedRatio={result['asymmetry']['side_A_sell_fade_buys']['median_fade_ratio_30m']:.4f}, "
        f"DollarExp={result['asymmetry']['side_A_sell_fade_buys']['dollar_expectancy']:.4f}, "
        f"Bootstrap P={result['asymmetry']['side_A_sell_fade_buys']['cluster_p_ge_1_25']:.4f}"
        if result['asymmetry']['side_A_sell_fade_buys']['median_fade_ratio_30m'] else "  Side A: N/A",
        f"  Side B (Forced BUY  -> Fade SELLS): n={result['asymmetry']['side_B_buy_fade_sells']['n']}, "
        f"MedRatio={result['asymmetry']['side_B_buy_fade_sells']['median_fade_ratio_30m']:.4f}, "
        f"DollarExp={result['asymmetry']['side_B_buy_fade_sells']['dollar_expectancy']:.4f}, "
        f"Bootstrap P={result['asymmetry']['side_B_buy_fade_sells']['cluster_p_ge_1_25']:.4f}"
        if result['asymmetry']['side_B_buy_fade_sells']['median_fade_ratio_30m'] else "  Side B: N/A",
        "=" * 78,
    ])
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Item 14 Whale Cascade Sweeper Retrospective Replay (B15)"
    )
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB_PATH), help="Path to hyperliquid_data.db")
    parser.add_argument("--json", action="store_true", help="Print JSON result to stdout")
    parser.add_argument("--out", type=str, default=None, help="Save result JSON to file path")
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES, help="Cluster bootstrap draws")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for bootstrap")
    parser.add_argument("--include-controls", action="store_true", help="Include synthetic random-entry controls")
    parser.add_argument("--source", type=str, default=None, help="Filter event source (e.g. trade_sweep)")

    args = parser.parse_args()

    result = run_replay(
        db_path=args.db,
        resamples=args.resamples,
        seed=args.seed,
        include_controls=args.include_controls,
        source=args.source,
    )

    if args.out:
        # Atomic, matching the R102-2 exporter artifact: a reader must never see a partial verdict.
        out_file = Path(args.out)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_file.with_suffix(out_file.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        os.replace(tmp, out_file)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))


if __name__ == "__main__":
    main()
