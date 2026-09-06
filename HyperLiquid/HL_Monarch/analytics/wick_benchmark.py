"""
MFE/MAE excursion benchmark: does the liquidation entry signal have any edge?

THE QUESTION. After a forced-sell cascade the fade buys, betting on a snapback.
For every historical event we measure, over a forward window:

    MFE = maximum favourable excursion  (how far it moved our way)
    MAE = maximum adverse excursion     (how far it moved against us)

MFE/MAE >= 1.50 means the signal genuinely leads to asymmetric moves.
MFE/MAE ~= 1.00 means it does not, and the fade thesis should be retired.

WHY THERE IS A CONTROL, AND WHY THE NUMBER IS MEANINGLESS WITHOUT ONE.
A driftless random walk produces MFE/MAE ~= 1.00 by construction, so 1.00 is the
null - but only if nothing else biases the measurement. Sampling gaps, uneven
snapshot density around volatile moments, and the trending tape all shift the
ratio on their own. So every run also measures RANDOM entries on the same coins
over the same window lengths. The signal's edge is the DIFFERENCE between the two,
not the raw ratio. A signal scoring 1.20 against a control of 1.20 has no edge
whatsoever, and reporting the 1.20 alone would have looked like a partial success.

TWO EVENT SOURCES, AND ONLY ONE IS THE STRATEGY'S.
  trade_sweep - the cascade detector the fade actually trades. ~476 events.
  trade_flow  - ANY fill >= $50k, liquidation or not. ~9,353 events, and mostly
                plain whale orders. It is reported separately because averaging
                the two would let the larger, contaminated set dominate and
                answer a question nobody asked.

MEASUREMENT NOTES.
  * Excursions are measured from the MARK at event time, not from the fade's
    limit price. That isolates the SIGNAL from the execution geometry, which is
    the whole point - the limit may never fill, and a filled entry sits at a
    better price, which would flatter MFE.
  * Ratios are aggregated as mean(MFE)/mean(MAE), not mean(MFE/MAE). Per-event
    ratios explode when MAE is near zero, and averaging them would let a handful
    of quiet events dominate the result.
  * Events whose forward window is not covered by snapshots are DROPPED, not
    zero-filled. Coverage is reported so a thin result cannot masquerade as a
    clean one.
"""

import random
import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple

from storage.repository import MarketRepository

MS_PER_MINUTE = 60_000
DEFAULT_HORIZONS = (5.0, 15.0, 30.0)
# A window needs at least this many forward samples to be measurable at all;
# two points cannot describe an excursion.
MIN_FORWARD_SAMPLES = 5


def load_events(repo: MarketRepository, source: Optional[str] = None,
                min_notional: float = 0.0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    sql = "SELECT coin, side, px, notional, time, source FROM liquidation_events WHERE notional >= ?"
    params: List[Any] = [min_notional]
    if source:
        sql += " AND source = ?"
        params.append(source)
    sql += " ORDER BY time ASC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with repo.db.connection as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_coin_series(repo: MarketRepository, coins: Sequence[str]) -> Dict[str, List[Tuple[int, float]]]:
    """All marks per coin, oldest first. Loaded once - per-event queries would be thousands of reads."""
    series: Dict[str, List[Tuple[int, float]]] = {}
    with repo.db.connection as conn:
        for coin in set(coins):
            rows = conn.execute(
                "SELECT timestamp, mark_px FROM asset_snapshots "
                "WHERE coin = ? AND mark_px > 0 ORDER BY timestamp ASC",
                (coin,),
            ).fetchall()
            if rows:
                series[coin] = [(int(r["timestamp"]), float(r["mark_px"])) for r in rows]
    return series


def _bisect(series: List[Tuple[int, float]], ts: int) -> int:
    lo, hi = 0, len(series)
    while lo < hi:
        mid = (lo + hi) // 2
        if series[mid][0] < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def excursion(series: List[Tuple[int, float]], ts: int, is_long: bool,
              horizon_minutes: float) -> Optional[Dict[str, float]]:
    """
    (mfe_pct, mae_pct) from the mark at `ts` over the forward window, or None.

    Both are reported as POSITIVE percentages of the entry price: MFE is the best
    move in our favour, MAE the worst against us. A window with no forward
    coverage returns None rather than zeros - a zero excursion is a real
    measurement and must not be confused with a missing one.
    """
    i = _bisect(series, ts)
    if i >= len(series):
        return None
    entry_ts, entry_px = series[i]
    if entry_px <= 0:
        return None
    end = ts + int(horizon_minutes * MS_PER_MINUTE)

    hi = lo = entry_px
    n = 0
    for k in range(i + 1, len(series)):
        t, px = series[k]
        if t > end:
            break
        hi = px if px > hi else hi
        lo = px if px < lo else lo
        n += 1
    if n < MIN_FORWARD_SAMPLES:
        return None

    up = (hi - entry_px) / entry_px * 100.0
    down = (entry_px - lo) / entry_px * 100.0
    # Long fade: favourable is up. Short fade: favourable is down.
    mfe, mae = (up, down) if is_long else (down, up)
    return {"mfe": mfe, "mae": mae, "entry_px": entry_px, "samples": n,
            "lag_ms": entry_ts - ts}


def concentration_hhi(counts: Sequence[int]) -> float:
    """
    Herfindahl-Hirschman index of per-coin event shares, 0..1.

    Adopted as a standing audit after the first excursion run was reported at
    "p < 1e-15" on a dataset where CASHCAT and PONS supplied 83% of all events.
    HHI makes that visible in one number: 1/k for k evenly weighted coins, and
    approaching 1.0 when one asset dominates. Two equal coins score 0.50.
    """
    total = sum(counts)
    if total <= 0:
        return 0.0
    return sum((c / total) ** 2 for c in counts)


def cluster_bootstrap(rows_by_coin: Dict[str, List[Dict[str, float]]],
                      threshold: float = 1.0,
                      resamples: int = 20_000,
                      seed: int = 7) -> Optional[float]:
    """
    P(ratio >= threshold), resampling COINS rather than individual events.

    The event-level bootstrap that was used first is invalid here: 30-minute
    forward windows on events minutes apart on the same coin overlap almost
    completely, so 466 events are nowhere near 466 independent observations. It
    reported 0/20,000; resampling coins reported 0.024 on the same data. The
    difference is the whole reason this function exists.
    """
    coins = list(rows_by_coin)
    if not coins:
        return None
    rng = random.Random(seed)
    hits = 0
    for _ in range(resamples):
        picked = [coins[rng.randrange(len(coins))] for _ in coins]
        rows = [r for c in picked for r in rows_by_coin[c]]
        agg = _aggregate(rows)
        if agg["ratio"] is not None and agg["ratio"] >= threshold:
            hits += 1
    return hits / resamples


def _aggregate(rows: List[Dict[str, float]]) -> Dict[str, Any]:
    """
    mean(MFE)/mean(MAE), not mean(MFE/MAE).

    Per-event ratios diverge as MAE approaches zero, so averaging them lets a few
    quiet events dominate. The ratio of means is the estimator that answers
    "across all these trades, did favourable moves outweigh adverse ones".
    """
    if not rows:
        return {"n": 0, "ratio": None}
    mfe = [r["mfe"] for r in rows]
    mae = [r["mae"] for r in rows]
    mean_mfe, mean_mae = statistics.mean(mfe), statistics.mean(mae)
    return {
        "n": len(rows),
        "mean_mfe": mean_mfe,
        "mean_mae": mean_mae,
        "median_mfe": statistics.median(mfe),
        "median_mae": statistics.median(mae),
        "ratio": (mean_mfe / mean_mae) if mean_mae > 0 else None,
        "win_share": sum(1 for r in rows if r["mfe"] > r["mae"]) / len(rows) * 100.0,
    }


def _span_days(times) -> float:
    """Days between the earliest and latest event, from millisecond timestamps; 0.0 below two events.
    Round 115 (Ruling R114-1.F): the gate checks the span the rows actually COVER, not only that
    retention could hold the window."""
    ts = [float(t) for t in times if t is not None]
    return (max(ts) - min(ts)) / 86_400_000.0 if len(ts) >= 2 else 0.0


def benchmark(repo: Optional[MarketRepository] = None,
              source: Optional[str] = "trade_sweep",
              horizons: Sequence[float] = DEFAULT_HORIZONS,
              min_notional: float = 0.0,
              control_multiple: int = 3,
              seed: int = 15) -> Dict[str, Any]:
    """
    Run the benchmark for one event source, with a matched random-entry control.

    The control draws `control_multiple` random timestamps per real event, on the
    same coin and inside the same observed time range, so it inherits the same
    coverage gaps and the same market conditions.
    """
    repo = repo or MarketRepository()
    events = load_events(repo, source=source, min_notional=min_notional)
    if not events:
        return {"source": source, "events": 0, "horizons": {}}

    series = load_coin_series(repo, [e["coin"] for e in events])
    rng = random.Random(seed)

    out: Dict[str, Any] = {
        "source": source,
        "events": len(events),
        "coins": len(series),
        "min_notional": min_notional,
        "span_days": _span_days([e.get("time") for e in events]),
        "horizons": {},
    }

    for h in horizons:
        signal_rows: List[Dict[str, float]] = []
        control_rows: List[Dict[str, float]] = []
        skipped = 0

        by_coin: Dict[str, List[Dict[str, float]]] = {}
        for e in events:
            s = series.get(e["coin"])
            if not s:
                skipped += 1
                continue
            # side "A" = forced SELL hitting bids -> the fade BUYS (long).
            is_long = str(e.get("side", "")).upper() == "A"
            r = excursion(s, int(e["time"]), is_long, h)
            if r is None:
                skipped += 1
                continue
            signal_rows.append(r)
            by_coin.setdefault(e["coin"], []).append(r)

            lo_t, hi_t = s[0][0], s[-1][0] - int(h * MS_PER_MINUTE)
            if hi_t > lo_t:
                for _ in range(control_multiple):
                    c = excursion(s, rng.randint(lo_t, hi_t), is_long, h)
                    if c is not None:
                        control_rows.append(c)

        sig = _aggregate(signal_rows)
        ctl = _aggregate(control_rows)
        edge = None
        if sig["ratio"] is not None and ctl["ratio"]:
            edge = sig["ratio"] - ctl["ratio"]

        counts = [len(v) for v in by_coin.values()]
        hhi = concentration_hhi(counts)
        top_share = (max(counts) / sum(counts)) if counts else 0.0

        out["horizons"][h] = {
            "hhi": hhi,
            "coins_measured": len(by_coin),
            "top_coin_share": top_share,
            "cluster_p_ge_1": cluster_bootstrap(by_coin, threshold=1.0),
            "signal": sig,
            "control": ctl,
            "edge_vs_control": edge,
            "skipped": skipped,
            "coverage_pct": len(signal_rows) / len(events) * 100.0,
        }
    return out


def verdict(result: Dict[str, Any], alpha_threshold: float = 1.50) -> Dict[str, Any]:
    """
    The pre-registered read, applied to the longest horizon with usable coverage.

    The control matters as much as the threshold: a signal ratio clearing 1.50
    while the control also clears it is a property of the tape, not of the signal.
    """
    usable = [(h, d) for h, d in sorted(result.get("horizons", {}).items())
              if d["signal"]["ratio"] is not None and d["signal"]["n"] >= 30]
    if not usable:
        return {"verdict": "INSUFFICIENT_DATA",
                "reason": "no horizon had >=30 measurable events"}

    h, d = usable[-1]
    ratio = d["signal"]["ratio"]
    ctl = d["control"]["ratio"]
    edge = d["edge_vs_control"]

    if ratio >= alpha_threshold and (edge is None or edge > 0.10):
        v = "ALPHA_CONFIRMED"
    elif ctl is not None and edge is not None and abs(edge) <= 0.10:
        v = "NO_EDGE_VS_CONTROL"
    elif ratio < 1.10:
        v = "NO_ALPHA"
    else:
        v = "INCONCLUSIVE"
    return {"verdict": v, "horizon_minutes": h, "ratio": ratio,
            "control_ratio": ctl, "edge_vs_control": edge, "n": d["signal"]["n"]}


# Pre-registered 2026-09-01, before any of this data existed. The fade may only be
# reconsidered on a sample that is genuinely broad - the first verdict was drawn
# from 15.2 hours in which two microcaps supplied 83% of events.
REOPEN_MIN_EVENTS = 500
REOPEN_MIN_COINS = 20
REOPEN_MAX_COIN_SHARE = 0.20
REOPEN_RATIO = 1.25
REOPEN_CONFIDENCE = 0.90


def retention_covers_window(window_days: float = 7.0,
                            forward_minutes: float = 30.0) -> Dict[str, Any]:
    """
    Can the price series still hold every event in the registration's window?

    ROUND 32 FOUND THE GATE UNREACHABLE BY CONSTRUCTION. The registration asks
    for a 7-day window; excursions are measured against asset_snapshots; and
    those were pruned at 72 hours, so events older than three days had no price
    series to measure against no matter how long the collector ran. The sample
    could grow forever and never qualify. This check is what makes that visible
    - and it is asked FIRST, because a sample verdict on a window the database
    cannot hold is a verdict on nothing.
    """
    from config.settings import SNAPSHOT_RETENTION_HOURS
    needed = float(window_days) * 24.0 + float(forward_minutes) / 60.0
    covers = float(SNAPSHOT_RETENTION_HOURS) >= needed
    return {
        "covers": covers,
        "retention_hours": float(SNAPSHOT_RETENTION_HOURS),
        "needed_hours": needed,
        "detail": ("snapshots retained %.0fh >= %.1fh needed for a %g-day window"
                   % (SNAPSHOT_RETENTION_HOURS, needed, window_days)) if covers else
                  ("snapshots retained %.0fh < %.1fh needed for a %g-day window: "
                   "events age out before they can be measured"
                   % (SNAPSHOT_RETENTION_HOURS, needed, window_days)),
    }


def reopening_gate(result: Dict[str, Any], window_days: float = 7.0) -> Dict[str, Any]:
    """
    The sample gate, with the retention check in front of it.

    Retention is checked first and overrides the sample verdict, because a
    "SAMPLE_ADEQUATE" on a window the database cannot hold would be the most
    misleading status this function could return.
    """
    retention = retention_covers_window(window_days)
    out = _reopening_sample_gate(result, window_days)
    out["retention"] = retention
    if not retention["covers"]:
        out.update({"status": "RETENTION_TOO_SHORT", "eligible": False,
                    "detail": retention["detail"]})
    return out


def _reopening_sample_gate(result: Dict[str, Any], window_days: float = 7.0) -> Dict[str, Any]:
    """
    Whether the sample is broad enough to reconsider the retired fade at all.

    Deliberately asymmetric. Retiring took a p of 0.024 on a narrow sample;
    RE-OPENING requires >=500 events across >=20 coins with no coin over 20% of
    the sample, and then 90% confidence that the ratio clears 1.25. Since Round 115
    the rows must also COVER the registered window (`span_days` on the result; a
    result that does not report its span fails closed). A strategy
    already measured as sub-random should have to clear a higher bar to come
    back than it did to leave.
    """
    usable = [(h, d) for h, d in sorted(result.get("horizons", {}).items())
              if d["signal"]["ratio"] is not None]
    if not usable:
        return {"status": "NO_DATA", "detail": "nothing measurable", "eligible": False}

    h, d = usable[-1]
    n, coins, share = d["signal"]["n"], d["coins_measured"], d["top_coin_share"]
    fails = []
    if n < REOPEN_MIN_EVENTS:
        fails.append(f"n={n} < {REOPEN_MIN_EVENTS}")
    if coins < REOPEN_MIN_COINS:
        fails.append(f"{coins} coins < {REOPEN_MIN_COINS}")
    if share > REOPEN_MAX_COIN_SHARE:
        fails.append(f"top coin {share * 100:.0f}% > {REOPEN_MAX_COIN_SHARE * 100:.0f}%")
    span = result.get("span_days")
    if span is None:
        fails.append("covered span not reported (span_days)")
    elif float(span) < float(window_days):
        fails.append(f"span {float(span):.2f} d < {window_days:g} d window")
    if fails:
        return {"status": "SAMPLE_TOO_NARROW", "detail": "; ".join(fails),
                "eligible": False}
    return {"status": "SAMPLE_ADEQUATE",
            "detail": f"n={n}, {coins} coins, top coin {share * 100:.0f}%",
            "eligible": True}


def format_report(results: Sequence[Dict[str, Any]], alpha_threshold: float = 1.50) -> str:
    lines = ["", "MFE/MAE EXCURSION BENCHMARK",
             f"  alpha bar: MFE/MAE >= {alpha_threshold:.2f} AND a real margin over the "
             f"random-entry control", ""]
    for res in results:
        if not res.get("events"):
            lines.append(f"  [{res.get('source')}] no events found")
            continue
        lines.append(f"  SOURCE: {res['source']}   {res['events']:,} events "
                     f"across {res['coins']} coins")
        lines.append(f"  {'horizon':>9}{'n':>7}{'MFE':>9}{'MAE':>9}{'ratio':>8}"
                     f"{'control':>9}{'edge':>8}{'cover':>8}")
        for h, d in sorted(res["horizons"].items()):
            s, c = d["signal"], d["control"]
            if s["ratio"] is None:
                lines.append(f"  {h:>7.0f}m{s['n']:>7}   (not measurable)")
                continue
            ctl_txt = f"{c['ratio']:.3f}" if c["ratio"] else "n/a"
            edge_txt = (f"{d['edge_vs_control']:+.3f}"
                        if d["edge_vs_control"] is not None else "n/a")
            lines.append(
                f"  {h:>7.0f}m{s['n']:>7}{s['mean_mfe']:>8.3f}%{s['mean_mae']:>8.3f}%"
                f"{s['ratio']:>8.3f}{ctl_txt:>9}{edge_txt:>8}{d['coverage_pct']:>7.0f}%"
            )
            cp = d.get("cluster_p_ge_1")
            lines.append(
                f"           [audit] {d['coins_measured']} coins  HHI {d['hhi']:.3f}  "
                f"top coin {d['top_coin_share'] * 100:.0f}%  "
                f"cluster P(ratio>=1.0) "
                f"{(f'{cp:.4f}' if cp is not None else 'n/a')}"
            )
        v = verdict(res, alpha_threshold)
        lines.append("")
        gate = reopening_gate(res)
        lines.append(f"  SAMPLE GATE: {gate['status']}  ({gate['detail']})")
        lines.append(f"  VERDICT: {v['verdict']}")
        if v["verdict"] != "INSUFFICIENT_DATA":
            lines.append(f"    at {v['horizon_minutes']:.0f}m: signal {v['ratio']:.3f} vs "
                         f"control {v['control_ratio']:.3f} "
                         f"(edge {v['edge_vs_control']:+.3f}) on n={v['n']:,}")
        lines.append("")
    return "\n".join(lines)
