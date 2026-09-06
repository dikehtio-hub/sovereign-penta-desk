"""passive_fade_rebenchmark: the reopening question, asked of the persisted excursions, answered as JSON.

    cd HyperLiquid/HL_Monarch
    python -m analytics.fade_rebenchmark [--db PATH] [--out PATH] [--source trade_sweep]
                                         [--resamples 20000] [--seed 7] [--json]

Round 114 (Ruling R113-1.C, option 3). The registration passive_fade_rebenchmark.meta.json asks
one question - may the retired passive fade be reconsidered? - and binds the answer to
`wick_benchmark.reopening_gate()` (the sample gate: >=500 events, >=20 coins, no coin over 20%,
retention covering a 7-day window and, since Round 115, rows that actually span it) and to the bar `P(ratio >= 1.25) > 0.90` under a CLUSTER
bootstrap resampling coins. This module runs exactly that over the rows the collector has
persisted into `cascade_excursions`, and writes a JSON artifact for the knowledge layer to grade
INDEPENDENTLY (knowledge.ingest.fade_rebenchmark). Numbers reach the vault from this file only;
nothing is transcribed.

THE POPULATION IS ONE SOURCE, NOT THE TABLE. `cascade_excursions` holds two treatment sources,
trade_sweep and trade_flow, and measurement_schema.sql keeps the `source` column because "the two
event sources answer different questions and must never be pooled". The fade's events are sweeps
(the registration's own status line; the `excursion` command's default), so the registered
population is `trade_sweep`. Round 113's progress mirror pooled both and read the sample as ready;
over trade_sweep alone two gates fail. That correction is the reason this file names its source
in the artifact and in the registration's `population` block.

THE DECISION HORIZON IS 30 MINUTES because it is the longest of the horizons the registration
enumerates in state_at_registration (5m, 15m, 30m) and the engine's pre-registered read is "the
longest horizon with usable coverage". The persisted 60m column post-dates the registration; it is
reported, never graded.

Read-only: the database is opened with mode=ro. The only write is the artifact.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.wick_benchmark import (REOPEN_CONFIDENCE, REOPEN_MAX_COIN_SHARE, REOPEN_MIN_COINS,  # noqa: E402
                                      REOPEN_MIN_EVENTS, REOPEN_RATIO, _aggregate, cluster_bootstrap,
                                      concentration_hhi, reopening_gate)
from storage.incremental_persistence import control_source  # noqa: E402

DEFAULT_DB = ROOT / "data" / "hyperliquid_data.db"
DEFAULT_OUT = ROOT / "data" / "experiments" / "passive_fade_rebenchmark.verdict.json"
EXPERIMENT = "passive_fade_rebenchmark"
DEFAULT_SOURCE = "trade_sweep"
REGISTERED_HORIZONS: Sequence[float] = (5.0, 15.0, 30.0)   # state_at_registration enumerates these
SUPPLEMENTARY_HORIZONS: Sequence[float] = (60.0,)          # persisted later; reported, never graded
DECISION_HORIZON = 30.0
WINDOW_DAYS = 7.0
MS_PER_DAY = 86_400_000.0


def load_by_coin(conn: sqlite3.Connection, source: str, horizon: float) -> Dict[str, List[Dict[str, float]]]:
    col_m, col_a = "mfe_%dm" % int(horizon), "mae_%dm" % int(horizon)
    by_coin: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    for coin, mfe, mae in conn.execute(
            f"SELECT coin, {col_m}, {col_a} FROM cascade_excursions WHERE source = ? "
            f"AND {col_m} IS NOT NULL AND {col_a} IS NOT NULL", (source,)):
        by_coin[str(coin)].append({"mfe": float(mfe), "mae": float(mae)})
    return dict(by_coin)


def _ms_iso(ms: Any) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def run(db: Path, source: str = DEFAULT_SOURCE, resamples: int = 20_000, seed: int = 7,
        window_days: float = WINDOW_DAYS) -> Dict[str, Any]:
    conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True, timeout=8)
    try:
        total_in_table = int(conn.execute("SELECT COUNT(*) FROM cascade_excursions").fetchone()[0])
        n_src, lo, hi = conn.execute(
            "SELECT COUNT(*), MIN(timestamp_utc), MAX(timestamp_utc) FROM cascade_excursions WHERE source = ?",
            (source,)).fetchone()
        n_ctl = int(conn.execute("SELECT COUNT(*) FROM cascade_excursions WHERE source = ?",
                                 (control_source(source),)).fetchone()[0])
        horizons: Dict[float, Dict[str, Any]] = {}
        for h in tuple(REGISTERED_HORIZONS) + tuple(SUPPLEMENTARY_HORIZONS):
            sig = load_by_coin(conn, source, h)
            ctl = load_by_coin(conn, control_source(source), h)
            sig_agg = _aggregate([r for rows in sig.values() for r in rows])
            ctl_agg = _aggregate([r for rows in ctl.values() for r in rows])
            counts = {c: len(v) for c, v in sig.items()}
            n_sig = sum(counts.values())
            top_coin = max(counts, key=counts.get) if counts else None
            edge = None
            if sig_agg["ratio"] is not None and ctl_agg.get("ratio"):
                edge = sig_agg["ratio"] - ctl_agg["ratio"]
            horizons[float(h)] = {
                "signal": sig_agg, "control": ctl_agg, "edge_vs_control": edge,
                "coins_measured": len(sig), "hhi": concentration_hhi(list(counts.values())),
                "top_coin_share": (counts[top_coin] / n_sig) if top_coin else 0.0, "top_coin": top_coin,
                "cluster_p_ge_1": cluster_bootstrap(sig, threshold=1.0, resamples=resamples, seed=seed) if sig else None,
                "cluster_p_ge_reopen": cluster_bootstrap(sig, threshold=REOPEN_RATIO, resamples=resamples, seed=seed) if sig else None,
                "registered": float(h) in REGISTERED_HORIZONS,
            }
    finally:
        conn.close()

    # The gate exactly as the engine defines it, over the REGISTERED horizons only (it reads the
    # longest usable one), retention checked first.
    span_days = ((float(hi) - float(lo)) / MS_PER_DAY) if (lo is not None and hi is not None) else 0.0
    gate = reopening_gate({"horizons": {h: horizons[h] for h in REGISTERED_HORIZONS}, "span_days": round(span_days, 4)},
                          window_days=window_days)      # Round 115: the engine checks the covered span itself
    window_ok = span_days >= window_days
    d = horizons[DECISION_HORIZON]
    p = d["cluster_p_ge_reopen"]
    reasons: List[str] = []
    if not gate.get("eligible"):
        reasons.append(f"engine gate {gate.get('status')}: {gate.get('detail')}")
    if reasons:
        verdict = "INSUFFICIENT"
    elif p is not None and p > REOPEN_CONFIDENCE:
        verdict = "PASS"
        reasons.append(f"P(ratio_30m >= {REOPEN_RATIO}) = {p:.4f} > {REOPEN_CONFIDENCE}")
    else:
        verdict = "FAIL"
        reasons.append(f"P(ratio_30m >= {REOPEN_RATIO}) = {p if p is None else round(p, 4)} <= {REOPEN_CONFIDENCE}: the reopening bar is not cleared; the fade stays retired")

    return {
        "_artifact": {
            "written_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "writer": "HyperLiquid.HL_Monarch.analytics.fade_rebenchmark",
            "rows_in_table": total_in_table, "seed": seed, "resamples": resamples, "db": str(db),
        },
        "experiment": EXPERIMENT,
        "source": source,
        "verdict": verdict,
        "verdict_reasons": reasons,
        "decision_horizon_minutes": DECISION_HORIZON,
        "registered_horizons_minutes": list(REGISTERED_HORIZONS),
        "reopening_bar": {"ratio": REOPEN_RATIO, "confidence": REOPEN_CONFIDENCE,
                          "min_events": REOPEN_MIN_EVENTS, "min_coins": REOPEN_MIN_COINS,
                          "max_single_coin_share": REOPEN_MAX_COIN_SHARE, "window_days": window_days},
        "primary_metric": {"name": "ratio_30m", "value": d["signal"].get("ratio"), "n": d["signal"].get("n"),
                           "cluster_p_ge_1_25": p, "cluster_p_ge_1": d["cluster_p_ge_1"],
                           "control_ratio": d["control"].get("ratio"), "edge_vs_control": d["edge_vs_control"]},
        "sample_gates": {
            "engine": gate,
            "metrics": {"events": int(n_src or 0), "coins": d["coins_measured"], "top_coin_share": d["top_coin_share"],
                        "top_coin": d["top_coin"], "hhi": d["hhi"], "span_days": round(span_days, 2),
                        "window_days_required": window_days, "window_covered": window_ok},
        },
        "horizons": {f"{int(h)}m": v for h, v in horizons.items()},
        "data_audit": {"total_in_table": total_in_table, "treatment_rows": int(n_src or 0), "control_rows": n_ctl,
                       "first_event_utc": _ms_iso(lo), "last_event_utc": _ms_iso(hi),
                       "measurable_at_decision_horizon": d["signal"].get("n"),
                       "note": "one source only; trade_flow rows are a different event class and are not pooled"},
    }


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="analytics.fade_rebenchmark", description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="artifact path (default next to the registration)")
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--resamples", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", action="store_true", help="also print the artifact to stdout")
    a = ap.parse_args(argv)
    result = run(a.db, source=a.source, resamples=a.resamples, seed=a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    pm, g = result["primary_metric"], result["sample_gates"]["metrics"]
    print(f"{EXPERIMENT}: {result['verdict']}  source={a.source}  events={g['events']:,} coins={g['coins']} "
          f"top={g['top_coin']} {g['top_coin_share']:.4f} span={g['span_days']} d  ratio_30m={pm['value']}  "
          f"P(>=1.25)={pm['cluster_p_ge_1_25']}  -> {a.out}")
    for r in result["verdict_reasons"]:
        print("  - " + r)
    if a.json:
        print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
