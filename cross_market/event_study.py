"""
Item 18 Phase 2 (Round 126, Rulings R125-2 sections 6-8): event-driven lead-lag around a
scheduled macro print, at 1-second resolution. OFFLINE, READ-ONLY: reads the drill's
stamped CLOB books and the collector's `trades` / `asset_snapshots` tables through a
read-only URI, places no orders, opens no sockets.

THE QUESTION. When a number prints (a Fed decision, a CPI release), which venue completes
HALF of its total post-print move first - the Polymarket book for the registered markets,
or the HyperLiquid BTC perp? Phase 1 asked the continuous-trading version of this at
minute resolution three times and found no lead; Phase 2 asks the discrete-shock version
where a 5-minute poll is blind.

WHAT IT MEASURES, in the order the registration fixes:
  1. Sufficiency of both legs. Polymarket: every registered token needs >= min_stamps stamps
     and no hole > max_hole_s inside [T0, T+post_s], where T0 is the recorder's first stamp
     (constraint T0 <= T-30 s). HyperLiquid: the whole trade feed (every coin) has no gap
     > 5 s inside [T-5 s, T+post_s], and the BTC baseline print at or before T-5 s is at
     most 15 s old. BTC-quiet seconds forward-fill and never void the run.
  2. Displacement bars. dP = P(T+300 s) - P(T-5 s) on each venue. Polymarket needs
     |dP| >= 0.02; HyperLiquid needs |dP|/P(T-5 s) >= max(10 bps, 3 x median |5-min move|
     over the previous hour of asset_snapshots marks). Either under its bar -> the print is
     `uninformative-shock` (exit 0; logged, not counted).
  3. Half-lives. t*50% = the earliest grid second with |P(t) - P(T-5 s)| >= 0.5 |dP|.
     lead_s = t*_HL - t*_PM. > +1 s polymarket-leads-event; < -1 s hyperliquid-leads-event;
     otherwise contemporaneous-event-repricing.

The registration (cross_market/experiments/lead_lag_phase2_fomc.meta.json) is the source of
every number here; this module reads them, it does not define them.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from cross_market.latency_sniper import _utc, load_stamp_series

DEV_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRATION = DEV_ROOT / "cross_market" / "experiments" / "lead_lag_phase2_fomc.meta.json"
DEFAULT_HL_DB = DEV_ROOT / "HyperLiquid" / "HL_Monarch" / "data" / "hyperliquid_data.db"
DEFAULT_BOOKS_ROOT = DEV_ROOT / "cross_market" / "data" / "clob_books"

CLASS_PM_LEADS = "polymarket-leads-event"
CLASS_HL_LEADS = "hyperliquid-leads-event"
CLASS_CONTEMPORANEOUS = "contemporaneous-event-repricing"
CLASS_UNINFORMATIVE = "uninformative-shock"
CLASSES = (CLASS_PM_LEADS, CLASS_HL_LEADS, CLASS_CONTEMPORANEOUS, CLASS_UNINFORMATIVE)

EXIT_OK = 0
EXIT_INSUFFICIENT = 2
EXIT_REFUSED = 3
T0_LATEST_BEFORE_T_S = 30.0                    # registration: T0 <= T-30 s


# ------------------------------------------------------------------ registration

def load_registration(path: Path = DEFAULT_REGISTRATION) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("protocol") != "event_study":
        raise ValueError("%s is not an event_study registration" % path)
    return data


def find_event(reg: Dict[str, Any], event_id: Optional[str]) -> Dict[str, Any]:
    events = [e for e in reg.get("events") or [] if isinstance(e, dict)]
    if not events:
        raise ValueError("the registration names no events")
    if event_id is None:
        return events[0]
    for e in events:
        if e.get("id") == event_id:
            return e
    raise ValueError("event %r is not registered (have: %s)" % (event_id, ", ".join(str(e.get("id")) for e in events)))


def tokens_for(event: Dict[str, Any], dev_root: Path = DEV_ROOT) -> List[Tuple[str, str]]:
    """(token, label) for every YES token the event's rules file registers; [] when none is registered yet."""
    rules_file = event.get("rules_file")
    if not rules_file:
        return []
    path = Path(rules_file)
    path = path if path.is_absolute() else dev_root / path
    data = json.loads(path.read_text(encoding="utf-8"))
    out: List[Tuple[str, str]] = []
    for r in data.get("rules") or []:
        if isinstance(r, dict) and r.get("market"):
            out.append((str(r["market"]), str(r.get("label") or r.get("question") or r["market"])))
    return out


def iso_utc(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ Polymarket leg

def polymarket_second_series(stamps: Iterable[Any], t_start: int, t_end: int) -> Tuple[Dict[int, float], List[int]]:
    """{second: midpoint} for the LAST stamp inside each second with a two-sided book, plus the sorted list of
    every stamp second (two-sided or not) inside [t_start, t_end] - the second list is what sufficiency counts."""
    mids: Dict[int, float] = {}
    seconds: List[int] = []
    for st in stamps:
        sec = int(st.observed_at.timestamp())
        if sec < t_start or sec > t_end:
            continue
        seconds.append(sec)
        book = st.book
        if book.bids and book.asks:
            mids[sec] = (book.bids[0].price + book.asks[0].price) / 2.0
    return mids, sorted(seconds)


def forward_fill(points: Dict[int, float], t_start: int, t_end: int) -> Dict[int, float]:
    """A value for every grid second in [t_start, t_end], carried forward; seconds before the first point are absent."""
    out: Dict[int, float] = {}
    last: Optional[float] = None
    for sec in range(int(t_start), int(t_end) + 1):
        if sec in points:
            last = points[sec]
        if last is not None:
            out[sec] = last
    return out


def series_sufficiency(seconds: List[int], t_start: int, t_end: int, *, min_stamps: int, max_hole_s: float) -> Dict[str, Any]:
    """The Polymarket leg's bar: enough stamps and no hole longer than max_hole_s inside the window (edges included)."""
    reasons: List[str] = []
    n = len(seconds)
    if n < min_stamps:
        reasons.append("polymarket stamps %d < %d inside the window" % (n, min_stamps))
    largest = 0.0
    if seconds:
        edges = [t_start] + seconds + [t_end]
        largest = float(max(b - a for a, b in zip(edges, edges[1:])))
        if largest > max_hole_s:
            reasons.append("polymarket hole %.0f s > %.0f s inside the window (recorder downtime)" % (largest, max_hole_s))
    else:
        reasons.append("no polymarket stamps inside the window")
    return {"stamps": n, "largest_gap_s": largest, "ok": not reasons, "reasons": reasons}


# ------------------------------------------------------------------ HyperLiquid leg

def load_trades(db_path: Path, t_start_ms: int, t_end_ms: int) -> List[Tuple[int, str, float]]:
    """(time_ms, coin, px) for every print of every coin inside the bounds, read-only, oldest first."""
    uri = "file:" + Path(db_path).as_posix() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute("SELECT time, coin, px FROM trades WHERE time BETWEEN ? AND ? ORDER BY time",
                           (int(t_start_ms), int(t_end_ms))).fetchall()
    finally:
        con.close()
    return [(int(t), str(c), float(p)) for t, c, p in rows if p is not None]


def hyperliquid_second_series(trades: Iterable[Tuple[int, str, float]], coin: str) -> Tuple[Dict[int, float], Dict[int, int]]:
    """{second: px of the LAST print of `coin` in that second} and {second: ms of that print} (for the baseline age)."""
    px: Dict[int, float] = {}
    when: Dict[int, int] = {}
    for t_ms, c, p in trades:                          # oldest first: the last write per second wins
        if c != coin:
            continue
        sec = t_ms // 1000
        px[sec] = p
        when[sec] = t_ms
    return px, when


def feed_liveness(trades: Iterable[Tuple[int, str, float]], t_start_ms: int, t_end_ms: int, *, max_gap_s: float) -> Dict[str, Any]:
    """The whole feed, every coin: no gap longer than max_gap_s inside [t_start, t_end], edges included."""
    times = sorted(t for t, _, _ in trades if t_start_ms <= t <= t_end_ms)
    reasons: List[str] = []
    if not times:
        return {"prints": 0, "largest_gap_s": None, "ok": False, "reasons": ["no trade prints at all inside the window (collector down)"]}
    edges = [t_start_ms] + times + [t_end_ms]
    largest = max(b - a for a, b in zip(edges, edges[1:])) / 1000.0
    if largest > max_gap_s:
        reasons.append("hyperliquid feed gap %.1f s > %.0f s inside the window (WebSocket stall or collector death)" % (largest, max_gap_s))
    return {"prints": len(times), "largest_gap_s": round(largest, 2), "ok": not reasons, "reasons": reasons}


def noise_bar(db_path: Path, coin: str, t_release_s: int, *, window_minutes: int, min_marks: int, floor_bps: float,
              multiplier: float, baseline_offset_s: int) -> Dict[str, Any]:
    """Bar_HL = max(floor, multiplier x median |5-minute move|) from asset_snapshots marks over [T-window, T-5 s];
    the floor with bar_source=floor_fallback when fewer than min_marks marks exist (Ruling R125-2 s.7.1)."""
    lo = (t_release_s - window_minutes * 60) * 1000
    hi = (t_release_s + baseline_offset_s) * 1000
    marks: List[Tuple[int, float]] = []
    try:
        uri = "file:" + Path(db_path).as_posix() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        try:
            marks = [(int(t), float(p)) for t, p in con.execute(
                "SELECT timestamp, mark_px FROM asset_snapshots WHERE coin = ? AND mark_px IS NOT NULL AND timestamp BETWEEN ? AND ? "
                "ORDER BY timestamp", (coin, lo, hi)).fetchall() if p]
        finally:
            con.close()
    except Exception as exc:                            # noqa: BLE001 - an unreadable table is the floor, said so
        return {"bps": floor_bps, "source": "floor_fallback", "median_5m_bps": None, "marks": 0,
                "note": "asset_snapshots unreadable (%s: %s)" % (type(exc).__name__, exc)}
    if len(marks) < min_marks:
        return {"bps": floor_bps, "source": "floor_fallback", "median_5m_bps": None, "marks": len(marks)}
    moves: List[float] = []
    j = 0
    for i, (t_i, p_i) in enumerate(marks):
        target = t_i + 300_000
        if j < i:
            j = i
        while j + 1 < len(marks) and marks[j + 1][0] <= target:
            j += 1
        t_j, p_j = marks[j]
        if t_j - t_i >= 240_000 and p_i > 0:           # a 5-minute move needs a mark at least 4 minutes on
            moves.append(abs(p_j / p_i - 1.0) * 1e4)
    if len(moves) < min_marks:
        return {"bps": floor_bps, "source": "floor_fallback", "median_5m_bps": None, "marks": len(marks)}
    med = float(statistics.median(moves))
    return {"bps": round(max(floor_bps, multiplier * med), 4), "source": "trailing_60m_relative",
            "median_5m_bps": round(med, 4), "marks": len(marks), "moves": len(moves)}


# ------------------------------------------------------------------ the measurement

def half_life_second(series: Dict[int, float], t_from: int, t_to: int, baseline: float, total: float,
                     fraction: float) -> Optional[int]:
    """The earliest grid second in [t_from, t_to] whose displacement from the baseline reaches fraction x |total|."""
    need = fraction * abs(total)
    for sec in range(int(t_from), int(t_to) + 1):
        if sec in series and abs(series[sec] - baseline) >= need:
            return sec
    return None


def classify(lead_s: Optional[float], tolerance_s: float) -> str:
    if lead_s is None:
        return CLASS_UNINFORMATIVE
    if lead_s > tolerance_s:
        return CLASS_PM_LEADS
    if lead_s < -tolerance_s:
        return CLASS_HL_LEADS
    return CLASS_CONTEMPORANEOUS


def evaluate(reg: Dict[str, Any], event: Dict[str, Any], *, books_dir: Path, db_path: Path, coin: str = "BTC",
             now: Optional[datetime] = None, force: bool = False, dev_root: Path = DEV_ROOT) -> Dict[str, Any]:
    """The full Phase 2 measurement for one event, as a dict (the JSON the adapter consumes)."""
    bars = reg["bars"]
    win = reg["window"]
    suf = reg["sufficiency"]
    now = now or datetime.now(timezone.utc)
    T = int(_utc(event["release_utc"]).timestamp())
    post_s, base_off = int(win["post_s"]), int(win["baseline_offset_s"])
    t_base, t_end = T + base_off, T + post_s
    result: Dict[str, Any] = {
        "experiment": reg.get("experiment"), "protocol": "event_study",
        "event": {k: event.get(k) for k in ("id", "kind", "label", "release_utc")},
        "coin": coin, "T_utc": iso_utc(T), "grid_s": int(win.get("grid_s", 1)),
        "baseline_utc": iso_utc(t_base), "window_last_utc": iso_utc(t_end), "measured_at": now.isoformat(),
        "sufficient": False, "reasons": [], "markets": [], "class": None, "lead_s": None, "informative": False,
    }
    if now.timestamp() < t_end and not force:
        result["reasons"].append("window not complete: now %s < T+%d s (%s); pass --force to evaluate anyway"
                                 % (iso_utc(now.timestamp()), post_s, iso_utc(t_end)))
        return result
    tokens = tokens_for(event, dev_root)
    if not tokens:
        result["reasons"].append("event %s has no registered tokens (rules_file missing or empty)" % event.get("id"))
        return result

    # --- Polymarket leg ---
    stamps = load_stamp_series(books_dir, [t for t, _ in tokens])
    if not stamps:
        result["reasons"].append("no stamped books under %s" % books_dir)
        return result
    T0 = int(min(st.observed_at.timestamp() for st in stamps))
    result["T0_utc"] = iso_utc(T0)
    result["window_first_utc"] = iso_utc(T0)
    if T0 > T - T0_LATEST_BEFORE_T_S:
        result["reasons"].append("grid start T0 %s is later than T-%.0f s (recorder started late)" % (iso_utc(T0), T0_LATEST_BEFORE_T_S))
    pm_suf = suf["polymarket"]
    by_token = {t: [st for st in stamps if st.token == t] for t, _ in tokens}

    # --- HyperLiquid leg ---
    hl_suf = suf["hyperliquid"]
    trades = load_trades(db_path, (T0 - 60) * 1000, t_end * 1000 + 999)
    live = feed_liveness(trades, t_base * 1000, t_end * 1000, max_gap_s=float(hl_suf["feed_liveness_max_all_coin_gap_s"]))
    px_raw, _px_when = hyperliquid_second_series(trades, coin)
    hl_series = forward_fill(px_raw, T0, t_end)
    hl_reasons = list(live["reasons"])
    # The baseline is the last print AT OR BEFORE THE INSTANT T-5 s (registration), not the bucket [T-5, T-4): a
    # print at T-4.5 s sits inside second T-5's bucket but is after the baseline instant and must not anchor it.
    base_prints = [(t_ms, p) for t_ms, c, p in trades if c == coin and t_ms <= t_base * 1000]
    baseline_age = None
    if not base_prints:
        hl_reasons.append("no %s print at or before the baseline instant %s" % (coin, iso_utc(t_base)))
    else:
        base_ms, base_px = base_prints[-1]
        baseline_age = round((t_base * 1000 - base_ms) / 1000.0, 3)
        if baseline_age > float(hl_suf["baseline_max_age_s"]):
            hl_reasons.append("%s baseline print is %.1f s old (> %.0f s)" % (coin, baseline_age, float(hl_suf["baseline_max_age_s"])))
        hl_series[t_base] = base_px                    # the grid's baseline second carries the baseline print, exactly
    result["sufficiency"] = {"polymarket": {}, "hyperliquid": dict(live, baseline_age_s=baseline_age, ok=not hl_reasons, reasons=hl_reasons)}
    bar = noise_bar(db_path, coin, T, window_minutes=int(bars["hl_noise_window_minutes"]), min_marks=int(bars["hl_noise_min_marks"]),
                    floor_bps=float(bars["hl_min_displacement_bps_floor"]), multiplier=float(bars["hl_noise_multiplier"]),
                    baseline_offset_s=base_off)
    result["bars"] = {"pm_min_displacement": float(bars["pm_min_displacement"]), "hl_bar_bps": bar["bps"], "hl_bar_source": bar["source"],
                      "hl_median_5m_bps": bar.get("median_5m_bps"), "hl_marks": bar.get("marks"),
                      "lead_tolerance_s": float(bars["lead_tolerance_s"]), "half_life_fraction": float(bars["half_life_fraction"])}
    hl: Dict[str, Any] = {"coin": coin, "prints": sum(1 for _, c, _ in trades if c == coin), "baseline_px": None, "baseline_age_s": baseline_age,
                          "final_px": None, "dp_rel_bps": None, "t_star_utc": None, "t_star_rel_s": None, "displaced": None}
    if not hl_reasons:
        hl["baseline_px"] = hl_series.get(t_base)
        hl["final_px"] = hl_series.get(t_end)
        if hl["baseline_px"] and hl["final_px"] is not None:
            dp_hl = hl["final_px"] - hl["baseline_px"]
            hl["dp_rel_bps"] = round(dp_hl / hl["baseline_px"] * 1e4, 4)
            hl["displaced"] = abs(hl["dp_rel_bps"]) >= bar["bps"]
            if hl["displaced"]:
                ts = half_life_second(hl_series, t_base, t_end, hl["baseline_px"], dp_hl, float(bars["half_life_fraction"]))
                hl["t_star_utc"], hl["t_star_rel_s"] = iso_utc(ts), (ts - T) if ts is not None else None
        else:
            hl_reasons.append("%s series has no value at the baseline or the window end" % coin)
            result["sufficiency"]["hyperliquid"]["ok"] = False
            result["sufficiency"]["hyperliquid"]["reasons"] = hl_reasons
    result["hyperliquid"] = hl

    # --- per market ---
    markets: List[Dict[str, Any]] = []
    for token, label in tokens:
        mids, seconds = polymarket_second_series(by_token.get(token, []), T0, t_end)
        s = series_sufficiency(seconds, T0, t_end, min_stamps=int(pm_suf["min_stamps"]), max_hole_s=float(pm_suf["max_hole_s"]))
        result["sufficiency"]["polymarket"][token] = s
        m: Dict[str, Any] = {"token": token, "label": label, "stamps": s["stamps"], "sufficient": s["ok"], "reasons": list(s["reasons"]),
                             "baseline": None, "final": None, "dp": None, "displaced": None, "t_star_utc": None, "t_star_rel_s": None,
                             "lead_s": None, "class": None, "informative": False}
        if s["ok"]:
            series = forward_fill(mids, T0, t_end)
            m["baseline"], m["final"] = series.get(t_base), series.get(t_end)
            if m["baseline"] is None or m["final"] is None:
                m["sufficient"] = False
                m["reasons"].append("no two-sided book value at the baseline or the window end")
            else:
                m["dp"] = round(m["final"] - m["baseline"], 6)
                m["displaced"] = abs(m["dp"]) >= float(bars["pm_min_displacement"])
                if m["displaced"]:
                    ts = half_life_second(series, t_base, t_end, m["baseline"], m["dp"], float(bars["half_life_fraction"]))
                    m["t_star_utc"], m["t_star_rel_s"] = iso_utc(ts), (ts - T) if ts is not None else None
                if not hl_reasons:
                    if m["displaced"] and hl["displaced"] and m["t_star_rel_s"] is not None and hl["t_star_rel_s"] is not None:
                        m["lead_s"] = float(hl["t_star_rel_s"] - m["t_star_rel_s"])
                        m["class"] = classify(m["lead_s"], float(bars["lead_tolerance_s"]))
                        m["informative"] = True
                    else:
                        m["class"] = CLASS_UNINFORMATIVE
                        under = []
                        if not m["displaced"]:
                            under.append("polymarket |dP| %.4f < %.2f" % (abs(m["dp"]), float(bars["pm_min_displacement"])))
                        if not hl["displaced"]:
                            under.append("hyperliquid |dP| %.2f bps < bar %.2f bps" % (abs(hl["dp_rel_bps"] or 0.0), bar["bps"]))
                        m["reasons"].append("uninformative: " + "; ".join(under))
        markets.append(m)
    result["markets"] = markets

    # --- event verdict ---
    if hl_reasons:
        result["reasons"].extend(hl_reasons)
    usable = [m for m in markets if m["sufficient"] and m["dp"] is not None]
    if not usable:
        result["reasons"].append("no registered token passed the polymarket sufficiency bar")
    if result["reasons"]:
        return result
    primary = max(usable, key=lambda m: abs(m["dp"]))
    result["primary_market"] = {"token": primary["token"], "label": primary["label"]}
    result["class"], result["lead_s"], result["informative"] = primary["class"], primary["lead_s"], primary["informative"]
    result["sufficient"] = True
    return result


# ------------------------------------------------------------------ CLI

def format_report(r: Dict[str, Any]) -> str:
    ev = r.get("event") or {}
    lines = ["EVENT STUDY: %s (%s)  T=%s  offline research only" % (ev.get("id"), ev.get("label"), r.get("T_utc"))]
    lines.append("  grid: T0=%s .. %s at %s s; baseline %s" % (r.get("T0_utc"), r.get("window_last_utc"), r.get("grid_s"), r.get("baseline_utc")))
    b = r.get("bars") or {}
    if b:
        lines.append("  bars: polymarket |dP| >= %.2f; hyperliquid |dP| >= %.2f bps (%s, median 5-min move %s bps over %s marks); lead tolerance %.1f s"
                     % (b["pm_min_displacement"], b["hl_bar_bps"], b["hl_bar_source"], b.get("hl_median_5m_bps"), b.get("hl_marks"), b["lead_tolerance_s"]))
    hl = r.get("hyperliquid") or {}
    if hl:
        lines.append("  %s: %s prints; baseline %s (age %s s) -> %s; dP %s bps; t*50%% %s (T%+s s)"
                     % (hl.get("coin"), hl.get("prints"), hl.get("baseline_px"), hl.get("baseline_age_s"), hl.get("final_px"),
                        hl.get("dp_rel_bps"), hl.get("t_star_utc"), hl.get("t_star_rel_s") if hl.get("t_star_rel_s") is not None else "?"))
    for m in r.get("markets") or []:
        lines.append("  market %s (%s...): stamps %s; baseline %s -> %s; dP %s; t*50%% %s; lead %s s; class %s%s"
                     % (m.get("label"), str(m.get("token"))[:12], m.get("stamps"), m.get("baseline"), m.get("final"), m.get("dp"),
                        m.get("t_star_rel_s"), m.get("lead_s"), m.get("class"), ("; " + "; ".join(m["reasons"])) if m.get("reasons") else ""))
    if r.get("sufficient"):
        pm = r.get("primary_market") or {}
        lines.append("VERDICT: %s  lead %s s  (primary market: %s)%s" % (r.get("class"), r.get("lead_s"), pm.get("label"),
                                                                       "" if r.get("informative") else "  [not counted toward the panel]"))
    else:
        lines.append("INSUFFICIENT: " + "; ".join(r.get("reasons") or ["?"]))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Item 18 Phase 2 - event-driven lead-lag around a scheduled print (offline research)")
    parser.add_argument("--registration", type=Path, default=DEFAULT_REGISTRATION)
    parser.add_argument("--event", default=None, help="event id from the registration (default: the first)")
    parser.add_argument("--books", type=Path, default=None, help="stamped books dir (default: the event's books_dir)")
    parser.add_argument("--db", type=Path, default=DEFAULT_HL_DB, help="hyperliquid_data.db (read-only)")
    parser.add_argument("--coin", default="BTC")
    parser.add_argument("--now", default=None, help="ISO instant standing in for the wall clock (tests)")
    parser.add_argument("--force", action="store_true", help="evaluate before T+post_s has passed")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        reg = load_registration(args.registration)
        event = find_event(reg, args.event)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("[REFUSE] %s" % exc)
        return EXIT_REFUSED
    books = args.books
    if books is None:
        bd = event.get("books_dir")
        books = (DEV_ROOT / bd) if bd else (DEFAULT_BOOKS_ROOT / str(event.get("id")))
    now = _utc(args.now) if args.now else None
    result = evaluate(reg, event, books_dir=Path(books), db_path=Path(args.db), coin=args.coin.upper(), now=now, force=args.force)
    if args.json:
        result["_artifact"] = {"written_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "writer": "cross_market.event_study",
                               "registration": str(args.registration), "books_dir": str(books), "db": str(args.db),
                               "argv": list(argv) if argv is not None else sys.argv[1:]}
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_report(result))
    return EXIT_OK if result.get("sufficient") else EXIT_INSUFFICIENT


if __name__ == "__main__":
    raise SystemExit(main())
