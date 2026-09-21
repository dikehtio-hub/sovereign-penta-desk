#!/usr/bin/env python3
"""
Nightly intraday-funding read under the Section 97 recurrence protocol.

Successor to eval_intraday_null_confirmation.py (DEV 9c79170), which was hard-wired to
2026-09-21 and computed the sandwich for the D-1 cohort only. On its pre-registered run
that script returned NULL NOT CONFIRMED (broad median +1.895 %, BTC +17.03 %): one large
day, event-shaped by the hour. Section 97 s6 therefore asks a different question - does
it RECUR - and makes the SANDWICH the primary statistic, because the raw day-minus-evening
contrast loads any same-day market move onto itself whole.

For a day D, all times UTC:
    selection       [D-1 00:00, D-1 17:00)   picks the D-1 cohort; ends before anything measured
    evening-before  [D-1 17:00, D   06:00)
    day             [D   07:00, D   16:00)
    evening-after   [D   17:00, D+1 06:00)
06-07Z and 16-17Z belong to no block: ratified transition buffers (Section 95 Q3).

    sandwich(coin) = ( f_day - (f_eve_before + f_eve_after) / 2 ) * 8760
A linear drift across the three windows cancels exactly. A step does not cancel fully -
half of it survives - which is why ONE night certifies nothing and the unit of
replication is the DAY.

THE BLIND IS STRUCTURAL. The script refuses to run until the evening-after window has
closed, so a night cannot be read early and then re-specified.

WHAT SECTION 97 FIXED, and what this file had to decide for itself. Each item marked
[CHOICE] is NOT in the ruling and stands only if ratified:
  P1-S  liquidity universe (mean day_ntl_vlm >= $100k in ALL THREE windows): median
        sandwich. A night FLAGS with sign(median) when |median| >= 1.0 % APR.
        [CHOICE] Two-sided. s6.1 reads ">= +1.0 %", which could never certify a profile
        in which the day runs BELOW the evening; "consistent sign" implies both.
  P4-S  D-1 cohort (selection mean APR >= 25 %, volume >= $100k): median sandwich,
        n >= 10, band 5.0 % APR (Section 95).
        [CHOICE] VOID when the selection window holds under 360 minutes of data. Raw rows
        age out after 192 h, so an old night's selection window can shrink to minutes.
  CERTIFY a diurnal profile: the same non-zero flag on >= 4 of 5 consecutive UNBROKEN nights.
        [CHOICE] UNBROKEN = >= 80 % of distinct BTC minutes in each of the three windows.
        [CHOICE] A broken night is VOID: it is not counted and it does not reset the run -
        missing data is not evidence.
  SESSION-OPEN read: DESCRIPTIVE ONLY. s6.3 names a hypothesis and two windows but no
        statistic, no threshold and no null, so there is nothing to gate on yet. It also
        puts the European cash open at 08:00Z; under summer time Xetra, Euronext and the
        LSE all open at 07:00Z (checked with zoneinfo for 2026-09-22). Both the ruled
        window and the corrected one are printed. The hypothesis was read off 09-21's
        hourly trace, so it can only ever be tested on nights after it was written down.
  BTC / ETH / SOL sandwiches: descriptive.
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data" / "hyperliquid_data.db"
HOURS_PER_YEAR = 8760.0
CORE_COINS = ("BTC", "ETH", "SOL")

# --- pre-registered constants. Changing one after a night's data exists voids that night.
MIN_VOLUME_USD = 100_000.0
COHORT_MIN_APR = 0.25
COHORT_MIN_N = 10
COVERAGE_MIN = 0.80
SEL_MIN_MINUTES = 360          # [CHOICE] a cohort picked from under six hours of selection data is VOID.
                               # Found by replay: once retention had pruned 09-13 back to its last 15 minutes,
                               # the 09-14 cohort swelled from 9 coins to 41 coins of noise and printed +3.21 %.
P1_FLAG_ABS = 0.010            # |median sandwich| >= 1.0 % APR flags the night
P4_BAND_ABS = 0.050            # cohort |median sandwich| < 5.0 % APR
CERTIFY_K, CERTIFY_N = 4, 5

# name -> (start minutes after D 00:00Z, end minutes)
SESSIONS = {
    "EU open AS RULED   08:00-10:00Z": (8 * 60, 10 * 60),
    "EU open CORRECTED  07:00-09:00Z": (7 * 60, 9 * 60),
    "US open            13:30-15:30Z": (13 * 60 + 30, 15 * 60 + 30),
}


def utc(d: datetime) -> int:
    return int(d.replace(tzinfo=timezone.utc).timestamp() * 1000)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%m-%d %H:%MZ")


def median(values: List[float]) -> float:
    s = sorted(values)
    n = len(s)
    if not n:
        return float("nan")
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def windows_for(day: datetime) -> Dict[str, Tuple[int, int]]:
    p, n = day - timedelta(days=1), day + timedelta(days=1)
    w = {
        "sel": (utc(p), utc(p.replace(hour=17))),
        "eb": (utc(p.replace(hour=17)), utc(day.replace(hour=6))),
        "day": (utc(day.replace(hour=7)), utc(day.replace(hour=16))),
        "ea": (utc(day.replace(hour=17)), utc(n.replace(hour=6))),
    }
    for i, (a, b) in enumerate(SESSIONS.values()):
        w[f"s{i}"] = (utc(day) + a * 60000, utc(day) + b * 60000)
    return w


def scan(conn: sqlite3.Connection, w: Dict[str, Tuple[int, int]]):
    """ONE pass over the night. coin -> {window: (sum funding, rows, sum volume)}."""
    keys = list(w)
    parts = []
    for k in keys:
        a, b = w[k]
        cond = f"timestamp >= {a} AND timestamp < {b}"
        parts += [f"SUM(CASE WHEN {cond} THEN funding_rate END)", f"COUNT(CASE WHEN {cond} THEN 1 END)",
                  f"SUM(CASE WHEN {cond} THEN day_ntl_vlm END)"]
    lo, hi = min(a for a, _ in w.values()), max(b for _, b in w.values())
    out: Dict[str, Dict[str, Tuple[float, int, float]]] = {}
    for row in conn.execute(
            f"SELECT coin, {', '.join(parts)} FROM asset_snapshots WHERE timestamp >= ? AND timestamp < ? "
            "AND funding_rate IS NOT NULL GROUP BY coin", (lo, hi)):
        out[str(row[0])] = {k: (float(row[1 + 3 * i] or 0.0), int(row[2 + 3 * i] or 0), float(row[3 + 3 * i] or 0.0))
                            for i, k in enumerate(keys)}
    return out


def btc_coverage(conn: sqlite3.Connection, a: int, b: int) -> float:
    seen = conn.execute("SELECT COUNT(DISTINCT CAST(timestamp / 60000 AS INTEGER)) FROM asset_snapshots "
                        "WHERE coin = 'BTC' AND timestamp >= ? AND timestamp < ?", (a, b)).fetchone()[0] or 0
    return seen / ((b - a) / 60000)


def night(conn: sqlite3.Connection, day: datetime, verbose: bool = True) -> Optional[int]:
    """Read one night. Returns its flag (+1 / -1 / 0), or None when the night is VOID."""
    w = windows_for(day)
    cov = {k: btc_coverage(conn, *w[k]) for k in ("eb", "day", "ea")}
    unbroken = all(v >= COVERAGE_MIN for v in cov.values())
    data = scan(conn, w)

    def mean(c: str, k: str) -> Optional[float]:
        s, n, _ = data[c][k]
        return s / n if n else None

    def vol(c: str, k: str) -> float:
        _, n, v = data[c][k]
        return v / n if n else 0.0

    def sandwich(c: str) -> Optional[float]:
        e, d, a = mean(c, "eb"), mean(c, "day"), mean(c, "ea")
        return None if None in (e, d, a) else (d - (e + a) / 2.0) * HOURS_PER_YEAR

    uni = [c for c in data if all(vol(c, k) >= MIN_VOLUME_USD for k in ("eb", "day", "ea"))]
    sw = [x for x in (sandwich(c) for c in uni) if x is not None]
    raw = [(mean(c, "day") - mean(c, "eb")) * HOURS_PER_YEAR for c in uni]
    drift = [(mean(c, "ea") - mean(c, "eb")) * HOURS_PER_YEAR for c in uni]
    m = median(sw)
    flag = 0 if abs(m) < P1_FLAG_ABS else (1 if m > 0 else -1)

    cohort = [c for c in data if (mean(c, "sel") or 0.0) * HOURS_PER_YEAR >= COHORT_MIN_APR
              and vol(c, "sel") >= MIN_VOLUME_USD]
    csw = [x for x in (sandwich(c) for c in cohort) if x is not None]
    mc = median(csw)

    if verbose:
        print(f"\n{'=' * 92}\nNIGHT OF {day:%Y-%m-%d}   " + ("UNBROKEN" if unbroken else "*** VOID: coverage below 80 % ***"))
        print("coverage  " + "   ".join(f"{k} {cov[k]:.0%}" for k in ("eb", "day", "ea"))
              + f"      eve-before {iso(w['eb'][0])}->{iso(w['eb'][1])}  day {iso(w['day'][0])}->{iso(w['day'][1])}"
              + f"  eve-after {iso(w['ea'][0])}->{iso(w['ea'][1])}")
        print(f"P1-S  liquidity universe n = {len(sw)}   MEDIAN SANDWICH {m * 100:+.3f} %   "
              f"flag {'+' if flag > 0 else '-' if flag < 0 else '0'}   (bar |.| >= {P1_FLAG_ABS:.1%})")
        print(f"      for scale:  raw day-eve_before {median(raw) * 100:+.3f} %    null contrast eve_after-eve_before {median(drift) * 100:+.3f} %")
        sel_min = btc_coverage(conn, *w["sel"]) * (w["sel"][1] - w["sel"][0]) / 60000
        p4 = (f"VOID (selection window holds {sel_min:.0f} min of data, need {SEL_MIN_MINUTES})" if sel_min < SEL_MIN_MINUTES
              else f"VOID (n < {COHORT_MIN_N})" if len(csw) < COHORT_MIN_N
              else "PASS" if abs(mc) < P4_BAND_ABS else "FAIL")
        print(f"P4-S  D-1 cohort n = {len(csw)}   median sandwich {mc * 100:+.2f} %   {p4}   (band < {P4_BAND_ABS:.1%})")
        print("core  " + "   ".join(f"{c} {sandwich(c) * 100:+.2f} %" for c in CORE_COINS
                                     if c in data and sandwich(c) is not None) + "   (descriptive)")
        print("session-open, DESCRIPTIVE ONLY - median over the universe of (mean inside the window) minus "
              "(mean over the rest of the day block):")
        for i, name in enumerate(SESSIONS):
            a, b = w[f"s{i}"]
            lo, hi = max(a, w["day"][0]), min(b, w["day"][1])
            diffs = []
            for c in uni:
                s_in, n_in, _ = data[c][f"s{i}"]
                s_d, n_d, _ = data[c]["day"]
                if (a, b) != (lo, hi):            # a window poking outside the day block: not comparable, skip
                    continue
                if n_in and n_d - n_in > 0:
                    diffs.append((s_in / n_in - (s_d - s_in) / (n_d - n_in)) * HOURS_PER_YEAR)
            print(f"      {name}   " + (f"{median(diffs) * 100:+.3f} %  (n = {len(diffs)})" if diffs
                                        else "n/a - window not inside the day block"))
    return flag if unbroken else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--day", required=True, help="the day D whose 07Z-16Z block is judged, YYYY-MM-DD")
    ap.add_argument("--nights", type=int, default=1, help="also re-read the N-1 nights before D, for the tally")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--allow-early", action="store_true", help="run before the evening-after window closes. BREAKS THE BLIND.")
    args = ap.parse_args()

    last = datetime.strptime(args.day, "%Y-%m-%d")
    digest = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    closes = windows_for(last)["ea"][1]
    if now < closes and not args.allow_early:
        print(f"REFUSED: the night of {args.day} closes at {iso(closes)}; it is {iso(now)}. Reading it early would "
              f"break the blind.\nscript sha256 (LF-normalised): {digest}", file=sys.stderr)
        return 2

    print("=" * 92 + "\nINTRADAY FUNDING - NIGHTLY SANDWICH READ (Section 97 recurrence protocol)\n" + "=" * 92)
    print(f"script sha256 : {digest}\nrun at        : {iso(now)}" + ("   *** --allow-early: BLIND BROKEN ***" if now < closes else ""))
    conn = sqlite3.connect(f"file:{args.db.as_posix()}?mode=ro", uri=True)
    try:
        flags = [(d, night(conn, d)) for d in (last - timedelta(days=i) for i in range(args.nights - 1, -1, -1))]
    finally:
        conn.close()

    live = [(d, f) for d, f in flags if f is not None]
    print("\n" + "=" * 92 + "\nTALLY   " + "   ".join(
        f"{d:%m-%d} {'VOID' if f is None else '+' if f > 0 else '-' if f < 0 else '0'}" for d, f in flags))
    recent = [f for _, f in live][-CERTIFY_N:]
    verdict = "NOT YET - fewer than %d unbroken nights" % CERTIFY_N
    if len(recent) == CERTIFY_N:
        pos, neg = sum(1 for f in recent if f > 0), sum(1 for f in recent if f < 0)
        verdict = ("DIURNAL PROFILE CERTIFIED (day ABOVE evening)" if pos >= CERTIFY_K else
                   "DIURNAL PROFILE CERTIFIED (day BELOW evening)" if neg >= CERTIFY_K else
                   f"NOT CERTIFIED: {pos} up / {neg} down / {CERTIFY_N - pos - neg} flat - alternating or flat signs are drift")
    print(f"last {CERTIFY_N} unbroken nights -> {verdict}\n" + "=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
