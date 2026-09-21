#!/usr/bin/env python3
"""
Out-of-sample null confirmation: does HyperLiquid perp funding differ between the
daytime block (07Z-16Z) and the evening block the harvester has sampled since 09-17?

Supersedes scripts/eval_intraday_funding_profile.py, whose Cohort B was withdrawn on
2026-09-21 (no power at its 10 % gate - 86 % of admitted coins sit on the venue's fixed
10.95 % APR interest component - and no validity at any gate: selecting on evening APR
and re-measuring manufactures regression to the mean, which a placebo on two halves of
the SAME evening reproduced in full).

WRITTEN AND HASHED BEFORE THE DATA EXISTS. The day window it judges (2026-09-21 07Z-16Z)
was still accruing, and had not been read by anyone, when this file was frozen. The
script enforces that itself: it refuses to run before --day-end.

ESTIMATOR (ratified 2026-09-21 07:05Z). Paired per coin: dAPR = (f_day - f_eve) * 8760,
where f is the row mean of funding_rate over the window.
  PRIMARY    liquidity universe: mean day_ntl_vlm >= $100k in BOTH windows. Nothing is
             selected on funding, so nothing regresses.
  SECONDARY  D-1 cohort: mean APR >= 25 % and volume >= $100k over a SELECTION window
             that ends before the evening window starts.
  CORE       BTC, ETH, SOL.

TWO CRITERIA SETS ARE PRINTED, AND WHY. The 07:05Z set is reproduced verbatim. Scored
against 09-14 / 09-15 / 09-16 - three days on which the null had ALREADY been accepted -
it REJECTS all three: "core each < 2.0 %" fails every day (SOL alone moves +/-8.6 %), and
the coin-level sign test fails two of three with OPPOSITE signs (z = +3.93, -2.81, 0.00).
Opposite signs are not a time-of-day effect; they are market-wide funding drifting
between the blocks and carrying most coins with it. Coins are not independent draws: the
unit of replication is the DAY. The D-1 cohort's raw dAPR is also biased by the cohort's
own decay - the same clock hours 24 h apart moved +4.96 / -20.31 / +6.29 % APR with no
day/night contrast in them at all - so its certifying statistic is the SANDWICH, day
minus the mean of the two flanking evenings, which cancels a linear trend.
The amended set is printed beside the ratified one. Which set is the verdict of record
is whichever Antigravity has ratified by --day-end; this script does not choose.

One night can flag a LARGE effect and add one post-09-17 day to the tally. It cannot
certify a small one: that takes sign-consistent nights, per the standing
three-consecutive-nights rule.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data" / "hyperliquid_data.db"
HOURS_PER_YEAR = 8760.0
CORE_COINS = ("BTC", "ETH", "SOL")
TIE_EPS = 1e-8                       # |dAPR| below this is a structural tie, not a sign

# --- pre-registered constants. Changing one after --day-end voids the run. -----------
MIN_VOLUME_USD = 100_000.0
COHORT_MIN_APR = 0.25                # the harvester's own gross gate, BASIS_MIN_FUNDING_APR
COVERAGE_MIN = 0.80                  # distinct BTC minutes / minutes in the day window
COHORT_MIN_N = 10

RATIFIED = {                         # Antigravity, 2026-09-21 07:05Z, verbatim
    "primary_median_abs_lt": 0.010,
    "sign_z_abs_le": 1.96,
    "cohort_median_abs_lt": 0.025,
    "core_each_abs_lt": 0.020,
}
AMENDED = {                          # proposed 2026-09-21 ~08Z, calibrated on 09-14..09-16 only
    "primary_median_abs_lt": 0.010,  # kept: passed 3/3 (+0.04 / -0.10 / -0.00 %)
    "btc_abs_lt": 0.025,             # BTC only: -0.70 / -1.44 / +1.23 %. ETH, SOL descriptive
    "sandwich_median_abs_lt": 0.050, # cohort, decay removed: -4.88 (n=9, void) / -2.03 / +1.87 %
}
HISTORY_NOTE = ("ratified set scored on 09-14/15/16, where the null was already accepted: "
                "REJECTS 3 of 3 (core fails 3/3; sign test fails 2/3 with opposite signs)")


def to_ms(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def median(values: List[float]) -> float:
    s = sorted(values)
    n = len(s)
    if not n:
        return float("nan")
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def sign_test(deltas: List[float]) -> Tuple[int, int, int, float]:
    """(pos, neg, ties, z). Ties are DROPPED, never counted as failures."""
    pos = sum(1 for x in deltas if x > TIE_EPS)
    neg = sum(1 for x in deltas if x < -TIE_EPS)
    z = (pos - neg) / math.sqrt(pos + neg) if pos + neg else 0.0
    return pos, neg, len(deltas) - pos - neg, z


def window_means(conn: sqlite3.Connection, a: int, b: int) -> Dict[str, Tuple[float, float, int]]:
    """coin -> (mean funding_rate, mean day_ntl_vlm, rows) over [a, b)."""
    out: Dict[str, Tuple[float, float, int]] = {}
    for coin, f, v, n in conn.execute(
            "SELECT coin, AVG(funding_rate), AVG(day_ntl_vlm), COUNT(*) FROM asset_snapshots "
            "WHERE timestamp >= ? AND timestamp < ? AND funding_rate IS NOT NULL GROUP BY coin",
            (a, b)):
        if f is not None:
            out[str(coin)] = (float(f), float(v or 0.0), int(n))
    return out


def btc_minutes(conn: sqlite3.Connection, a: int, b: int) -> int:
    row = conn.execute(
        "SELECT COUNT(DISTINCT CAST(timestamp / 60000 AS INTEGER)) FROM asset_snapshots "
        "WHERE coin = 'BTC' AND timestamp >= ? AND timestamp < ?", (a, b)).fetchone()
    return int(row[0] or 0)


def pf(ok: Optional[bool]) -> str:
    return "n/a " if ok is None else ("PASS" if ok else "FAIL")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--sel-start", default="2026-09-20T00:00:00Z", help="D-1 selection window (only 00:00-06:21Z exists)")
    ap.add_argument("--sel-end", default="2026-09-21T00:00:00Z")
    ap.add_argument("--eve-start", default="2026-09-21T02:05:00Z", help="evening-before; truncated by the 19.7 h outage")
    ap.add_argument("--eve-end", default="2026-09-21T06:00:00Z")
    ap.add_argument("--day-start", default="2026-09-21T07:00:00Z")
    ap.add_argument("--day-end", default="2026-09-21T16:00:00Z")
    ap.add_argument("--aft-start", default="2026-09-21T17:00:00Z", help="evening-after, for the sandwich")
    ap.add_argument("--aft-end", default="2026-09-22T06:00:00Z")
    ap.add_argument("--allow-early", action="store_true",
                    help="run before --day-end. BREAKS THE BLIND; the output says so.")
    args = ap.parse_args()

    sel = (to_ms(args.sel_start), to_ms(args.sel_end))
    eve = (to_ms(args.eve_start), to_ms(args.eve_end))
    day = (to_ms(args.day_start), to_ms(args.day_end))
    aft = (to_ms(args.aft_start), to_ms(args.aft_end))
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    # Line endings normalised first: git's autocrlf may rewrite this file on a checkout,
    # and a changed byte that is not a changed character must not read as tampering.
    digest = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()

    if sel[1] > eve[0]:
        print("REFUSED: the selection window must END before the evening window STARTS, or the "
              "cohort is selected on the thing being measured.", file=sys.stderr)
        return 2
    if now < day[1] and not args.allow_early:
        print(f"REFUSED: the day window closes at {iso(day[1])}; it is {iso(now)}. Reading it early "
              "would break the blind this run depends on. (--allow-early overrides, and says so.)\n"
              f"script sha256 (LF-normalised): {digest}", file=sys.stderr)
        return 2

    print("=" * 96)
    print("INTRADAY FUNDING - OUT-OF-SAMPLE NULL CONFIRMATION")
    print("=" * 96)
    print(f"script sha256 : {digest}")
    print(f"run at        : {iso(now)}" + ("   *** --allow-early: BLIND BROKEN ***" if now < day[1] else ""))
    for label, w in (("selection", sel), ("evening-before", eve), ("day", day), ("evening-after", aft)):
        print(f"{label:<14}: {iso(w[0])} -> {iso(w[1])}")

    conn = sqlite3.connect(f"file:{args.db.as_posix()}?mode=ro", uri=True)
    try:
        day_minutes = (day[1] - day[0]) // 60000
        seen = btc_minutes(conn, *day)
        coverage = seen / day_minutes if day_minutes else 0.0
        S, E, D = window_means(conn, *sel), window_means(conn, *eve), window_means(conn, *day)
        A = window_means(conn, *aft) if now >= aft[0] else {}
    finally:
        conn.close()

    print(f"\nday coverage  : {seen} of {day_minutes} distinct BTC minutes = {coverage:.1%} "
          f"(need >= {COVERAGE_MIN:.0%})")
    if coverage < COVERAGE_MIN:
        print("\nVERDICT: INSUFFICIENT COVERAGE - no pass or fail is called on a window with holes this size.")
        return 3
    aft_complete = bool(A) and now >= aft[1]

    # ---- PRIMARY ---------------------------------------------------------------------
    uni = [c for c in set(E) & set(D) if E[c][1] >= MIN_VOLUME_USD and D[c][1] >= MIN_VOLUME_USD]
    d_uni = [(D[c][0] - E[c][0]) * HOURS_PER_YEAR for c in uni]
    pos, neg, ties, z = sign_test(d_uni)
    m_uni = median(d_uni)
    unpinned = [x for x in d_uni if abs(x) >= TIE_EPS]
    print("\n--- PRIMARY: liquidity universe (volume >= $100k in both windows, no funding filter) ---")
    print(f"n = {len(d_uni)}   median dAPR = {m_uni * 100:+.3f} %   median excluding ties = {median(unpinned) * 100:+.3f} %")
    print(f"sign test: {pos} up / {neg} down / {ties} tied   z = {z:+.2f}   "
          "(DESCRIPTIVE under the amended set: coins move together within a day)")

    # ---- SECONDARY -------------------------------------------------------------------
    cohort = [c for c in S if S[c][0] * HOURS_PER_YEAR >= COHORT_MIN_APR and S[c][1] >= MIN_VOLUME_USD
              and c in E and c in D]
    d_coh = [(D[c][0] - E[c][0]) * HOURS_PER_YEAR for c in cohort]
    m_coh = median(d_coh)
    sw = [(D[c][0] - (E[c][0] + A[c][0]) / 2.0) * HOURS_PER_YEAR for c in cohort if c in A]
    m_sw = median(sw)
    print(f"\n--- SECONDARY: D-1 cohort (selection mean APR >= {COHORT_MIN_APR:.0%}, volume >= $100k) ---")
    print(f"n = {len(d_coh)}" + ("   *** below the minimum of %d: VOID ***" % COHORT_MIN_N if len(d_coh) < COHORT_MIN_N else ""))
    if d_coh:
        lv = lambda W: median([W[c][0] * HOURS_PER_YEAR for c in cohort]) * 100
        print(f"cohort level, median APR: selection {lv(S):.1f} %  ->  evening {lv(E):.1f} %  ->  day {lv(D):.1f} %")
        print(f"raw median dAPR      = {m_coh * 100:+.2f} %   (PROVISIONAL: carries the cohort's own decay)")
    if sw and aft_complete:
        print(f"SANDWICH median dAPR = {m_sw * 100:+.2f} %   (n = {len(sw)}; decay removed; the certifying statistic)")
    elif sw:
        print(f"sandwich, PARTIAL evening-after = {m_sw * 100:+.2f} %   (n = {len(sw)}; not final until {iso(aft[1])})")
    else:
        print(f"sandwich: PENDING - needs the evening-after window; re-run after {iso(aft[1])}")

    # ---- CORE ------------------------------------------------------------------------
    core = {c: (D[c][0] - E[c][0]) * HOURS_PER_YEAR for c in CORE_COINS if c in E and c in D}
    print("\n--- CORE ---")
    for c in CORE_COINS:
        if c in core:
            print(f"{c:<4} evening {E[c][0] * HOURS_PER_YEAR * 100:>7.2f} %   day {D[c][0] * HOURS_PER_YEAR * 100:>7.2f} %   dAPR {core[c] * 100:>+7.2f} %")
        else:
            print(f"{c:<4} missing from a window")

    # ---- VERDICTS --------------------------------------------------------------------
    coh_ok = len(d_coh) >= COHORT_MIN_N
    r = {
        "primary |median| < 1.0 %": abs(m_uni) < RATIFIED["primary_median_abs_lt"] if d_uni else None,
        "sign test |z| <= 1.96": abs(z) <= RATIFIED["sign_z_abs_le"] if d_uni else None,
        "cohort raw |median| < 2.5 %": (abs(m_coh) < RATIFIED["cohort_median_abs_lt"]) if coh_ok else None,
        "core EACH |dAPR| < 2.0 %": (all(abs(v) < RATIFIED["core_each_abs_lt"] for v in core.values())
                                     if len(core) == len(CORE_COINS) else None),
    }
    sw_ok = len(sw) >= COHORT_MIN_N and aft_complete
    a = {
        "primary |median| < 1.0 %": abs(m_uni) < AMENDED["primary_median_abs_lt"] if d_uni else None,
        "BTC |dAPR| < 2.5 %": abs(core["BTC"]) < AMENDED["btc_abs_lt"] if "BTC" in core else None,
        "cohort SANDWICH |median| < 5.0 %": (abs(m_sw) < AMENDED["sandwich_median_abs_lt"]) if sw_ok else None,
    }

    def call(checks: Dict[str, Optional[bool]]) -> str:
        if any(v is False for v in checks.values()):
            return "NULL NOT CONFIRMED"
        if any(v is None for v in checks.values()):
            return "PROVISIONAL - a criterion is pending or void"
        return "NULL CONFIRMED"

    print("\n" + "=" * 96)
    print("RATIFIED 07:05Z (verbatim)")
    for k, v in r.items():
        print(f"  [{pf(v)}] {k}")
    print(f"  => {call(r)}")
    print(f"  calibration: {HISTORY_NOTE}")
    print("-" * 96)
    print("AMENDED (proposed ~08Z; verdict of record ONLY if ratified before the day window closed)")
    for k, v in a.items():
        print(f"  [{pf(v)}] {k}")
    print(f"  => {call(a)}")
    print("=" * 96)
    print("One night flags a LARGE effect and adds one post-09-17 day to the tally (so far: +, -, 0).")
    print("It does not certify a small one; that takes sign-consistent nights.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
