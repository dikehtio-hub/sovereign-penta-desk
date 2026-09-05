"""
Item 18 - lead-lag between Polymarket probability shifts and HyperLiquid price
moves. OFFLINE RESEARCH ONLY (Round 51, Directive 51-2): reads drop files and a
read-only copy of the snapshot database, places no orders, opens no sockets.

THE QUESTION. When a Polymarket market's implied probability moves, does the
HyperLiquid perp for the related asset move before it, with it, or after it -
and by how many minutes? The answer is a lag: the offset tau at which the
cross-correlation between the minute series of probability changes and the
minute series of log returns peaks. tau > 0 means the perp moved AFTER the
probability (Polymarket leads); tau < 0 means the perp moved first.

WHAT THE INPUTS ARE. Probability series come from timestamped Polymarket drop
files (a list of questions with `question`, `token_id`, `yes_price`, `fetched_at`)
or a flat CSV of (ts, key, probability). Prices come from asset_snapshots in
hyperliquid_data.db, ~10s cadence, binned to minutes (last mark in the minute).

WHAT IT REFUSES TO SAY. Fewer than `min_events` shifts, or fewer than
`min_points` overlapping minutes, and the result is `sufficient: False` with the
reason; a peak correlation under `min_abs_corr` is reported as "no measurable
lead-lag", not as a lag. A single coincidence is not a lead.

KNOWN LIMIT TODAY. The Polymarket fetcher overwrites one drop file in place, so
there is no probability time series on disk yet; this module runs on synthetic
data in its tests and on real data once the fetcher keeps timestamped drops.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DEV_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HL_DB = DEV_ROOT / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db"
DEFAULT_DROP_DIRS = [DEV_ROOT / "Sports_Desk" / "data" / "polymarket_drops", DEV_ROOT / "cross_market" / "data"]
MINUTE_MS = 60_000


# ------------------------------------------------------------------ inputs

def _epoch_ms(value: Any) -> Optional[int]:
    """Milliseconds since epoch from ISO text, seconds, or milliseconds; None when unreadable."""
    if value is None or value == "":
        return None
    try:
        num = float(value)
        return int(num if num > 1e11 else num * 1000.0)
    except (TypeError, ValueError):
        pass
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def load_drop_records(drop_dirs: Iterable[Path]) -> List[Dict[str, Any]]:
    """
    Every question in every *.json drop under `drop_dirs` as
    {ts_ms, key, probability, question, file}. A question's key is its token_id,
    else its text. Unreadable files and unpriced questions are skipped.
    """
    records: List[Dict[str, Any]] = []
    for directory in drop_dirs:
        try:
            files = sorted(Path(directory).glob("*.json"))
        except Exception:                                   # noqa: BLE001
            continue
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:                               # noqa: BLE001
                continue
            items = data if isinstance(data, list) else (data.get("questions") if isinstance(data, dict) else None) or []
            for q in items:
                if not isinstance(q, dict):
                    continue
                ts = _epoch_ms(q.get("fetched_at") or q.get("ts") or q.get("timestamp"))
                price = q.get("yes_price") if q.get("yes_price") not in (None, "") else q.get("yes_bid")
                try:
                    prob = float(price)
                except (TypeError, ValueError):
                    continue
                if ts is None:
                    continue
                key = str(q.get("token_id") or q.get("question") or "")
                if not key:
                    continue
                records.append({"ts_ms": ts, "key": key, "probability": prob,
                                "question": str(q.get("question") or ""), "file": path.name})
    records.sort(key=lambda r: (r["ts_ms"], r["key"]))
    return records


def load_event_csv(path: Path) -> List[Dict[str, Any]]:
    """A flat (ts, key, probability) CSV, header optional; same record shape as the drops."""
    records: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 3:
                continue
            ts = _epoch_ms(row[0])
            try:
                prob = float(row[2])
            except ValueError:
                continue
            if ts is None:
                continue
            records.append({"ts_ms": ts, "key": row[1], "probability": prob, "question": row[1], "file": Path(path).name})
    records.sort(key=lambda r: (r["ts_ms"], r["key"]))
    return records


def probability_series(records: Iterable[Dict[str, Any]]) -> Dict[str, List[Tuple[int, float]]]:
    """{key: [(ts_ms, probability), ...]} in time order."""
    series: Dict[str, List[Tuple[int, float]]] = {}
    for r in records:
        series.setdefault(r["key"], []).append((int(r["ts_ms"]), float(r["probability"])))
    for key in series:
        series[key].sort()
    return series


def probability_shifts(series: Dict[str, List[Tuple[int, float]]], min_shift: float = 0.02) -> List[Dict[str, Any]]:
    """
    The moments a market's probability moved by at least `min_shift` between
    consecutive observations: [{ts_ms, key, delta}], time-ordered. The event
    is stamped at the LATER observation - the first time the move was visible.
    """
    shifts: List[Dict[str, Any]] = []
    for key, points in series.items():
        for (t0, p0), (t1, p1) in zip(points, points[1:]):
            delta = p1 - p0
            if abs(delta) >= min_shift:
                shifts.append({"ts_ms": t1, "key": key, "delta": delta})
    shifts.sort(key=lambda s: (s["ts_ms"], s["key"]))
    return shifts


def load_mark_series(db_path: Path, coin: str, start_ms: int, end_ms: int) -> List[Tuple[int, float]]:
    """(ts_ms, mark_px) for `coin` between the bounds, from a READ-ONLY connection."""
    uri = "file:" + Path(db_path).as_posix() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute("SELECT timestamp, mark_px FROM asset_snapshots WHERE coin = ? AND timestamp BETWEEN ? AND ? "
                           "AND mark_px IS NOT NULL ORDER BY timestamp", (coin, int(start_ms), int(end_ms))).fetchall()
    finally:
        con.close()
    return [(int(ts), float(px)) for ts, px in rows if px]


# ------------------------------------------------------------------ maths

def minute_bins(points: Iterable[Tuple[int, float]]) -> Dict[int, float]:
    """{minute_index: last value observed in that minute}."""
    out: Dict[int, float] = {}
    for ts, value in points:
        out[int(ts) // MINUTE_MS] = float(value)
    return out


def minute_log_returns(marks: Dict[int, float]) -> Dict[int, float]:
    """
    {minute: ln(px[minute] / px[previous observed minute])}. A gap in the
    marks yields one return spanning it, stamped at the later minute.
    """
    out: Dict[int, float] = {}
    previous: Optional[Tuple[int, float]] = None
    for minute in sorted(marks):
        px = marks[minute]
        if previous is not None and previous[1] > 0 and px > 0:
            out[minute] = math.log(px / previous[1])
        previous = (minute, px)
    return out


def shift_bins(shifts: Iterable[Dict[str, Any]]) -> Dict[int, float]:
    """{minute: summed probability delta} - several markets moving in one minute add up."""
    out: Dict[int, float] = {}
    for s in shifts:
        minute = int(s["ts_ms"]) // MINUTE_MS
        out[minute] = out.get(minute, 0.0) + float(s["delta"])
    return out


def _pearson(pairs: Sequence[Tuple[float, float]]) -> Optional[float]:
    n = len(pairs)
    if n < 3:
        return None
    mean_a = sum(a for a, _ in pairs) / n
    mean_b = sum(b for _, b in pairs) / n
    cov = sum((a - mean_a) * (b - mean_b) for a, b in pairs)
    var_a = sum((a - mean_a) ** 2 for a, _ in pairs)
    var_b = sum((b - mean_b) ** 2 for _, b in pairs)
    if var_a <= 0 or var_b <= 0:
        return None
    return cov / math.sqrt(var_a * var_b)


def cross_correlation(shifts: Dict[int, float], returns: Dict[int, float], max_lag: int) -> List[Dict[str, Any]]:
    """
    For each lag tau in [-max_lag, max_lag]: Pearson correlation between the
    shift series at minute m and the return series at minute m + tau, over the
    minutes where a return exists inside the window spanned by the shifts
    (shift value 0 where no market moved). tau > 0: returns AFTER shifts.
    """
    if not shifts or not returns:
        return []
    lo, hi = min(shifts), max(shifts)
    window = range(lo - max_lag, hi + max_lag + 1)
    results: List[Dict[str, Any]] = []
    for tau in range(-max_lag, max_lag + 1):
        pairs = [(shifts.get(m, 0.0), returns[m + tau]) for m in window if (m + tau) in returns]
        corr = _pearson(pairs)
        results.append({"lag_minutes": tau, "correlation": corr, "n": len(pairs)})
    return results


def lead_lag_report(shifts: List[Dict[str, Any]], marks: List[Tuple[int, float]], max_lag: int = 60,
                    min_events: int = 5, min_points: int = 60, min_abs_corr: float = 0.2) -> Dict[str, Any]:
    """
    The lag at which probability shifts and price returns line up best, with
    the evidence behind it - or the reason there is no answer.
    """
    result: Dict[str, Any] = {"events": len(shifts), "price_points": len(marks), "max_lag": max_lag,
                              "sufficient": False, "reason": "", "best_lag_minutes": None, "correlation": None,
                              "n": 0, "interpretation": "", "curve": []}
    if len(shifts) < min_events:
        result["reason"] = f"{len(shifts)} probability shifts < {min_events} required"
        return result
    returns = minute_log_returns(minute_bins(marks))
    binned = shift_bins(shifts)
    curve = cross_correlation(binned, returns, max_lag)
    result["curve"] = curve
    scored = [c for c in curve if c["correlation"] is not None and c["n"] >= min_points]
    if not scored:
        result["reason"] = f"fewer than {min_points} overlapping minutes at every lag"
        return result
    best = max(scored, key=lambda c: (abs(c["correlation"]), -abs(c["lag_minutes"])))
    result.update({"sufficient": True, "best_lag_minutes": best["lag_minutes"],
                   "correlation": best["correlation"], "n": best["n"]})
    tau, corr = best["lag_minutes"], best["correlation"]
    if abs(corr) < min_abs_corr:
        result["interpretation"] = f"no measurable lead-lag (peak |corr| {abs(corr):.2f} < {min_abs_corr})"
    elif tau > 0:
        result["interpretation"] = f"Polymarket leads HyperLiquid by {tau} min (corr {corr:+.2f}, n={best['n']})"
    elif tau < 0:
        result["interpretation"] = f"HyperLiquid leads Polymarket by {-tau} min (corr {corr:+.2f}, n={best['n']})"
    else:
        result["interpretation"] = f"coincident within a minute (corr {corr:+.2f}, n={best['n']})"
    return result


# ------------------------------------------------------------------ CLI

def format_report(result: Dict[str, Any], coin: str, keys: int) -> str:
    lines = ["", f"ITEM 18 - LEAD-LAG: Polymarket probability shifts vs HyperLiquid {coin} returns",
             f"  markets: {keys}   probability shifts: {result['events']}   price points: {result['price_points']}   "
             f"max lag: +/-{result['max_lag']} min"]
    if not result["sufficient"]:
        lines.append(f"  insufficient data: {result['reason']}")
    else:
        lines.append(f"  best lag: {result['best_lag_minutes']:+d} min   corr {result['correlation']:+.3f}   n={result['n']}")
        lines.append(f"  {result['interpretation']}")
        top = sorted((c for c in result["curve"] if c["correlation"] is not None),
                     key=lambda c: -abs(c["correlation"]))[:5]
        if top:
            lines.append("  strongest lags: " + "  ".join(f"{c['lag_minutes']:+d}m {c['correlation']:+.2f}" for c in top))
    lines.append("  offline research only - reads drops and a read-only database; places nothing.")
    lines.append("")
    return "\n".join(lines)


def run(coin: str, drop_dirs: Sequence[Path], db_path: Path, max_lag: int, min_shift: float,
        min_events: int, min_points: int, events_csv: Optional[Path] = None) -> Tuple[Dict[str, Any], int]:
    records = load_event_csv(events_csv) if events_csv else load_drop_records(drop_dirs)
    series = probability_series(records)
    shifts = probability_shifts(series, min_shift=min_shift)
    marks: List[Tuple[int, float]] = []
    if shifts:
        start = min(s["ts_ms"] for s in shifts) - (max_lag + 1) * MINUTE_MS
        end = max(s["ts_ms"] for s in shifts) + (max_lag + 1) * MINUTE_MS
        try:
            marks = load_mark_series(db_path, coin, start, end)
        except Exception:                                   # noqa: BLE001 - a missing database is "no prices"
            marks = []
    return lead_lag_report(shifts, marks, max_lag=max_lag, min_events=min_events, min_points=min_points), len(series)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Item 18 - Polymarket vs HyperLiquid lead-lag (offline research)")
    parser.add_argument("--coin", default="BTC", help="HyperLiquid perp whose returns to correlate (default BTC)")
    parser.add_argument("--drops", nargs="*", default=None, help="Drop directories (default: the Polymarket drop dirs)")
    parser.add_argument("--events", default=None, help="Flat CSV of ts,key,probability instead of drops")
    parser.add_argument("--db", default=None, help="hyperliquid_data.db path (read-only)")
    parser.add_argument("--max-lag", type=int, default=60, help="Lag window in minutes each side (default 60)")
    parser.add_argument("--min-shift", type=float, default=0.02, help="Probability move that counts as an event (default 0.02)")
    parser.add_argument("--min-events", type=int, default=5, help="Shifts required before a lag is reported (default 5)")
    parser.add_argument("--min-points", type=int, default=60, help="Overlapping minutes required at a lag (default 60)")
    args = parser.parse_args(argv)
    drop_dirs = [Path(d) for d in args.drops] if args.drops else DEFAULT_DROP_DIRS
    result, keys = run(args.coin.upper(), drop_dirs, Path(args.db) if args.db else DEFAULT_HL_DB, args.max_lag,
                       args.min_shift, args.min_events, args.min_points,
                       events_csv=Path(args.events) if args.events else None)
    print(format_report(result, args.coin.upper(), keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
