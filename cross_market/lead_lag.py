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
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DEV_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HL_DB = DEV_ROOT / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db"
DEFAULT_DROP_DIRS = [DEV_ROOT / "Sports_Desk" / "data" / "polymarket_drops", DEV_ROOT / "cross_market" / "data"]
MINUTE_MS = 60_000

# Round 56 (Directive 56-2): the empirical bar before the first live run.
READY_MIN_SPAN_HOURS = 24.0
READY_MIN_POINTS = 200
READY_MAX_GAP_MINUTES = 60.0            # a larger hole between stamps ends the continuous segment
EXIT_NOT_READY = 3


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


_UNPREFIXED_STAMP = re.compile(r"^polymarket_\d{8}T\d{6}_\d{6}Z\.json$")


def _file_matches_family(name: str, family: Optional[str]) -> bool:
    """
    Round 73 review: which drops belong to a tag family. macro -> polymarket_macro*.json;
    sports -> polymarket_sports*.json and the unprefixed single-tag stamps of Round 52;
    None / "any" -> every file (the Round 51 behaviour, which research fixtures rely on).
    """
    if not family or family == "any":
        return True
    if family == "macro":
        return name.startswith("polymarket_macro")
    if family == "sports":
        return name.startswith("polymarket_sports") or bool(_UNPREFIXED_STAMP.match(name))
    return name.startswith("polymarket_%s" % family)


# Round 74 (Ruling 74-2, Tier 2): inside the macro family a question carries the Gamma tag
# it was fetched under as its `sport` label (CRYPTO, FED-RATES). The diagnostic split reads
# that label; drops carry no tag_slug field. First tag wins in the fetcher's dedupe, so a
# market tagged both ways is labelled by the earlier --tags entry (crypto in the launcher).
SUBFAMILY_LABEL = "sport"
POLL_INTERVAL_MINUTES = 5.0                      # the watcher's cadence: a lag inside it is latency, not a lead


def record_subfamily(question: Dict[str, Any]) -> str:
    """The tag label a drop question was fetched under, lower-case ("crypto", "fed-rates"), or ""."""
    return str(question.get(SUBFAMILY_LABEL) or "").strip().lower()


def load_drop_records(drop_dirs: Iterable[Path], family: Optional[str] = None,
                      subfamily: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Every question in every *.json drop under `drop_dirs` as
    {ts_ms, key, probability, question, file, label}. A question's key is its token_id,
    else its text. Unreadable files and unpriced questions are skipped. `family`
    keeps only that tag family's drops, so a macro correlation is not fed 400
    NFL questions (the sentinel gates on macro stamps; the regression should read
    the same series). `subfamily` (Round 74, Tier 2) keeps only the questions whose
    tag label matches, e.g. "fed-rates" or "crypto" inside the macro drops.
    """
    records: List[Dict[str, Any]] = []
    wanted = str(subfamily).strip().lower() if subfamily else None
    for directory in drop_dirs:
        try:
            files = sorted(Path(directory).glob("*.json"))
        except Exception:                                   # noqa: BLE001
            continue
        for path in files:
            if not _file_matches_family(path.name, family):
                continue
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
                label = record_subfamily(q)
                if wanted is not None and label != wanted:
                    continue
                records.append({"ts_ms": ts, "key": key, "probability": prob,
                                "question": str(q.get("question") or ""), "file": path.name, "label": label})
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
                    min_events: int = 5, min_points: int = 60, min_abs_corr: float = 0.2,
                    latency_minutes: float = 0.0) -> Dict[str, Any]:
    """
    The lag at which probability shifts and price returns line up best, with
    the evidence behind it - or the reason there is no answer. `latency_minutes`
    (Round 74, Tier 2, pre-registered) is the poll cadence: a peak whose |lag| sits
    inside it is reported as contemporaneous repricing - a market whose question
    IS the price ("BTC above $80,000 today") re-marks when BTC moves, and the
    watcher sees it up to one poll later. That is latency, never a lead. 0 = off
    (the Tier 1 reading, unchanged).
    """
    result: Dict[str, Any] = {"events": len(shifts), "price_points": len(marks), "max_lag": max_lag,
                              "sufficient": False, "reason": "", "best_lag_minutes": None, "correlation": None,
                              "n": 0, "interpretation": "", "curve": [], "latency_minutes": float(latency_minutes)}
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
    elif latency_minutes > 0 and abs(tau) <= latency_minutes:
        result["interpretation"] = (f"contemporaneous repricing within the {latency_minutes:g}-min poll interval "
                                    f"(lag {tau:+d} min, corr {corr:+.2f}, n={best['n']}): latency, not a lead")
    elif tau > 0:
        result["interpretation"] = f"Polymarket leads HyperLiquid by {tau} min (corr {corr:+.2f}, n={best['n']})"
    elif tau < 0:
        result["interpretation"] = f"HyperLiquid leads Polymarket by {-tau} min (corr {corr:+.2f}, n={best['n']})"
    else:
        result["interpretation"] = f"coincident within a minute (corr {corr:+.2f}, n={best['n']})"
    return result


# ------------------------------------------------------------------ CLI

def format_report(result: Dict[str, Any], coin: str, keys: int) -> str:
    scope = " / ".join(str(s) for s in (result.get("family"), result.get("subfamily")) if s)
    lines = ["", f"ITEM 18 - LEAD-LAG: Polymarket probability shifts vs HyperLiquid {coin} returns"
             + (f"  [{scope}]" if scope else ""),
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
        min_events: int, min_points: int, events_csv: Optional[Path] = None,
        family: Optional[str] = None, subfamily: Optional[str] = None,
        latency_minutes: float = 0.0) -> Tuple[Dict[str, Any], int]:
    records = (load_event_csv(events_csv) if events_csv
               else load_drop_records(drop_dirs, family=family, subfamily=subfamily))
    series = probability_series(records)
    shifts = probability_shifts(series, min_shift=min_shift)
    marks: List[Tuple[int, float]] = []
    price_error = ""
    if shifts:
        start = min(s["ts_ms"] for s in shifts) - (max_lag + 1) * MINUTE_MS
        end = max(s["ts_ms"] for s in shifts) + (max_lag + 1) * MINUTE_MS
        try:
            marks = load_mark_series(db_path, coin, start, end)
        except Exception as exc:                            # noqa: BLE001 - a missing or locked database is NOT "no prices"
            marks = []
            price_error = "%s: %s" % (type(exc).__name__, exc)
    report = lead_lag_report(shifts, marks, max_lag=max_lag, min_events=min_events, min_points=min_points,
                             latency_minutes=latency_minutes)
    report["family"], report["subfamily"] = family, subfamily
    # Round 75: a database that could not be read is a failed run, not an "insufficient data" verdict.
    # The refresher must not record it (a 24 h cooldown on a transient lock would bury the maiden run).
    report["price_error"] = price_error
    if price_error and not report["sufficient"]:
        report["reason"] = "price series unreadable (%s)" % price_error
    return report, len(series)


# ------------------------------------------------------------------ data readiness (Round 56)

def stamped_moments(drop_dirs: Iterable[Path], family: str = "macro") -> List[datetime]:
    """
    Sorted UTC stamps of the stamped drops of `family` under `drop_dirs`, read
    from the file NAMES (Round 52: a copied file's mtime lies, its name does
    not). Unprefixed stamps are sports (single-tag runs); "any" takes all.
    """
    from cross_market.ingestors.polymarket_fetcher import STAMPED_PATTERN, stamp_of
    out: List[datetime] = []
    for directory in drop_dirs:
        try:
            files = list(Path(directory).glob("polymarket_*.json"))
        except Exception:                                   # noqa: BLE001
            continue
        for path in files:
            match = STAMPED_PATTERN.match(path.name)
            if not match:
                continue
            if family != "any" and (match.group(1) or "sports") != family:
                continue
            stamp = stamp_of(path)
            if stamp is not None:
                out.append(stamp)
    return sorted(out)


def data_readiness(stamps: Sequence[datetime], now: Optional[datetime] = None,
                   min_span_hours: float = READY_MIN_SPAN_HOURS, min_points: int = READY_MIN_POINTS,
                   max_gap_minutes: float = READY_MAX_GAP_MINUTES) -> Dict[str, Any]:
    """
    Whether the stamped series clears the bar for a first live run. Only the
    LATEST CONTINUOUS SEGMENT counts - stamps separated by more than
    max_gap_minutes belong to different runs (a dead watcher leaves a hole and
    a hole is not data). Ready = segment span >= min_span_hours AND segment
    points >= min_points AND the newest stamp is not itself older than the
    gap (a stalled watcher is not accumulating). The ETA is the later of the
    span clock and the points clock at the observed stamp rate; None when
    nothing is accumulating.
    """
    now = now or datetime.now(timezone.utc)
    info: Dict[str, Any] = {
        "points_total": len(stamps), "points": 0, "span_hours": 0.0, "segment_start": None, "newest": None,
        "newest_age_min": None, "largest_gap_min": None, "breaks": 0, "rate_per_hour": None,
        "min_span_hours": min_span_hours, "min_points": min_points, "max_gap_minutes": max_gap_minutes,
        "ready": False, "reasons": [], "eta": None, "checked_at": now.isoformat(),
    }
    if not stamps:
        info["reasons"].append("no stamped drops")
        return info
    stamps = sorted(stamps)
    max_gap = timedelta(minutes=max_gap_minutes)
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    info["largest_gap_min"] = round(max(gaps).total_seconds() / 60.0, 1) if gaps else 0.0
    info["breaks"] = sum(1 for g in gaps if g > max_gap)
    start = len(stamps) - 1
    while start > 0 and (stamps[start] - stamps[start - 1]) <= max_gap:
        start -= 1
    segment = stamps[start:]
    points = len(segment)
    span_h = (segment[-1] - segment[0]).total_seconds() / 3600.0
    rate = (points - 1) / span_h if span_h > 0 else None
    info.update(points=points, span_hours=round(span_h, 2), segment_start=segment[0].isoformat(),
                newest=segment[-1].isoformat(), newest_age_min=round((now - segment[-1]).total_seconds() / 60.0, 1),
                rate_per_hour=round(rate, 2) if rate else None)
    stalled = (now - segment[-1]) > max_gap
    if stalled:
        info["reasons"].append("newest stamp is %.0f min old (> %.0f min): the watcher is not adding"
                               % (info["newest_age_min"], max_gap_minutes))
    eta_candidates = []
    if span_h < min_span_hours:
        info["reasons"].append("span %.1fh < %.0fh" % (span_h, min_span_hours))
        eta_candidates.append(segment[0] + timedelta(hours=min_span_hours))
    if points < min_points:
        info["reasons"].append("points %d < %d" % (points, min_points))
        if rate:
            eta_candidates.append(now + timedelta(hours=(min_points - points) / rate))
    info["ready"] = not info["reasons"]
    if eta_candidates and not stalled:
        info["eta"] = max(eta_candidates).isoformat()
    return info


def format_readiness(info: Dict[str, Any], family: str) -> str:
    lines = ["[DATA] %s series: %d stamped point(s) in the latest continuous segment (%d on disk)"
             % (family, info["points"], info["points_total"])]
    if info["segment_start"]:
        lines.append("[DATA]   segment %s -> %s  span %.1fh  newest age %.0f min  rate %s/h"
                     % (info["segment_start"], info["newest"], info["span_hours"], info["newest_age_min"],
                        info["rate_per_hour"] if info["rate_per_hour"] is not None else "n/a"))
        lines.append("[DATA]   largest gap %s min, %d break(s) > %.0f min"
                     % (info["largest_gap_min"], info["breaks"], info["max_gap_minutes"]))
    lines.append("[DATA] bar: span >= %.0fh and points >= %d, no gap > %.0f min"
                 % (info["min_span_hours"], info["min_points"], info["max_gap_minutes"]))
    if info["ready"]:
        lines.append("[DATA] READY - the first live lead-lag run is honest now")
    else:
        lines.append("[DATA] NOT READY - " + "; ".join(info["reasons"]))
        lines.append("[DATA] ETA %s" % (info["eta"] or "none while nothing is accumulating (restart the watcher)"))
    return "\n".join(lines)


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
    parser.add_argument("--check-data", "--status", dest="check_data", action="store_true",
                        help="Round 56: report whether the stamped series clears the bar for a first live run "
                             "(exit 0 = ready, %d = not ready); no database needed" % EXIT_NOT_READY)
    parser.add_argument("--family", default=None, choices=("macro", "sports", "any"),
                        help="which tag family to read: with --check-data the sentinel's series (default macro); "
                             "for the correlation the drops to correlate (default: every drop, the Round 51 behaviour)")
    parser.add_argument("--subfamily", default=None,
                        help="Round 74 (Tier 2, pre-registered in cross_market/experiments/lead_lag_tier2.meta.json): "
                             "keep only questions fetched under this tag label inside the family, e.g. fed-rates "
                             "(exogenous policy) or crypto (self-referential price milestones)")
    parser.add_argument("--latency-minutes", type=float, default=0.0,
                        help="Tier 2 reading rule: a peak within this many minutes of zero is contemporaneous "
                             "repricing (poll latency), not a lead; the Tier 2 crypto run passes %g. Default 0 = off"
                             % POLL_INTERVAL_MINUTES)
    parser.add_argument("--min-span-hours", type=float, default=READY_MIN_SPAN_HOURS)
    parser.add_argument("--min-ready-points", type=int, default=READY_MIN_POINTS)
    parser.add_argument("--max-gap-minutes", type=float, default=READY_MAX_GAP_MINUTES)
    parser.add_argument("--json", action="store_true", help="with --check-data: print JSON instead of lines")
    parser.add_argument("--force", action="store_true",
                        help="Round 57 (Directive 57-2): run the correlation on the live drop dirs even when "
                             "--check-data says NOT READY (explicit --drops / --events are never gated)")
    args = parser.parse_args(argv)
    drop_dirs = [Path(d) for d in args.drops] if args.drops else DEFAULT_DROP_DIRS
    if args.check_data:
        family = args.family or "macro"
        info = data_readiness(stamped_moments(drop_dirs, family), min_span_hours=args.min_span_hours,
                              min_points=args.min_ready_points, max_gap_minutes=args.max_gap_minutes)
        print(json.dumps(info, indent=2) if args.json else format_readiness(info, family))
        return 0 if info["ready"] else EXIT_NOT_READY
    if not args.drops and not args.events and not args.force:
        # Round 57 (Directive 57-2): the first live evaluation waits for the sentinel.
        info = data_readiness(stamped_moments(drop_dirs, "macro"))
        if not info["ready"]:
            print(format_readiness(info, "macro"))
            print("[GATE] the live drop dirs are not ready for an honest run - refusing (exit %d); "
                  "pass --force to run anyway, or --drops / --events for research data" % EXIT_NOT_READY)
            return EXIT_NOT_READY
    result, keys = run(args.coin.upper(), drop_dirs, Path(args.db) if args.db else DEFAULT_HL_DB, args.max_lag,
                       args.min_shift, args.min_events, args.min_points,
                       events_csv=Path(args.events) if args.events else None, family=args.family,
                       subfamily=args.subfamily, latency_minutes=args.latency_minutes)
    print(format_report(result, args.coin.upper(), keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
