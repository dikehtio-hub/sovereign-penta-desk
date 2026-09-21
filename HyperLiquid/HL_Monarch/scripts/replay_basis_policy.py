#!/usr/bin/env python3
"""
Work Package 2 (Antigravity Section 99 s4): a slot-constrained replay of the basis
harvester's POLICY over the exchange's settled funding history.

WHY A POLICY REPLAY. Every level quoted on 2026-09-21 - 24 h, 96 h, 168 h "holds", pooled
or per-coin - was a window along a path, not a trade this bot makes. The bot as coded has
NO fixed hold: it fills its slots, holds through decay, and leaves only when should_exit
says so. The only honest measure of a gate is to run the policy hour by hour, under the
slot cap, paying the frictions, and see what the capital earned.

THE FOUR ARMS (Section 99 s4; parameters fixed in Sections 97-98, BEFORE this history was
pulled, so for A and D the store is out-of-sample as long as this runs once, untuned):
  P0       the bot as coded. Gate: current rate >= 25 % APR. Rank: current rate. No rotation.
  A        persistence. Gate: trailing-24h mean >= 25 % AND current >= 20 %.
           Rank: min(trailing, current).
  D        A, plus the rotation switch: with every slot full, replace the lowest-ranked
           held position when a candidate beats it by >= 25 points AND it is >= 48 h old.
  PASSIVE  continuous BTC basis: entered at the first hour, never closed.
Exits for P0 / A / D are the project's REAL BasisHarvester.should_exit, called unbound
through a shim so no harvester is instantiated and the live paper book is never touched.

NO LOOK-AHEAD. A settled rate for hour t is known only once t has closed. Every decision
at the close of t uses rates <= t, and a position opened then earns from t+1. It never
collects the spike that qualified it. tests/test_replay_basis_policy.py pins this.

FRICTIONS. The project's own ROUND_TRIP_FEE_PCT (0.0900 %) plus a round-trip spread
(default 20 bps, the entry gate's ceiling, per Section 99). Half on entry, half on exit;
positions still open at the end are MARKED OUT, so every arm pays whole round trips.

ACCOUNTING. One slot = one unit of notional. Idle slots earn 0 % - the harvester's own
docstring: "idle cash at 0 % outranks churning it". Net APR is on ALL slot capital, idle
included, because that is the capital the desk ties up.

[CHOICE]s - the ruling is silent; each stands only if ratified:
  1. trailing-24h mean needs >= 20 of its 24 hours present, else the coin fails A's gate.
  2. D compares like with like: the held position is ranked by the same
     min(trailing, current) as the candidate, and at most ONE rotation happens per hour.
  3. a coin with no settled rate at t is ineligible at t; a HELD coin with a hole keeps
     its position (should_exit treats an unknown rate as "not a reversal").
  4. breadth at t = share of eligible coins at or above the 25 % gate; with 13 names the
     regimes are coarse: low < 10 % is 0-1 hot coin, high >= 15 % is 2 or more.

WHAT THIS CANNOT SEE. Settled hourly funding only - not the live predicted quote, not spot
volume, not the order book - so the liquidity and spread gates are not replayed. The
universe is the 13 perps spot-backed on 2026-09-21: a LOOK-AHEAD for every earlier date.
P&L is funding minus frictions; basis drift, margin and liquidation are not modelled.
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from execution.basis_harvester import BasisHarvester, ROUND_TRIP_FEE_PCT  # noqa: E402

DEFAULT_DB = BASE_DIR / "data" / "funding_history_180d.db"
HOUR_MS = 3_600_000
HOURS_PER_YEAR = 8760.0

# --- policy parameters, fixed by ruling before the history existed -------------------
GATE_APR = 25.0                 # P0 gate, and A's trailing gate        (% APR)
A_CURRENT_MIN_APR = 20.0        # A's anti-collapse condition           (Section 97 s4)
TRAIL_HOURS = 24
TRAIL_MIN_PRESENT = 20          # [CHOICE 1]
ROTATE_MIN_GAIN_APR = 25.0      # D                                     (Section 97 s4)
ROTATE_MIN_AGE_HOURS = 48       # D
DEFAULT_SLOTS = 2               # BASIS_MAX_CONCURRENT                  (settings.py:595)
DEFAULT_SPREAD_BPS = 20.0       # Section 99 s4
FLASH_HOURS = 3                 # an episode under 3 h is a flash spike (Section 99 s2)
BREADTH_LOW, BREADTH_HIGH = 0.10, 0.15

Rates = Dict[str, Dict[int, float]]          # coin -> hour index -> settled HOURLY rate


def apr(rate: float) -> float:
    return rate * HOURS_PER_YEAR * 100.0


def real_should_exit(coin: str, current_apr: Optional[float], hours_held: float) -> Optional[str]:
    """The project's own exit rule, run against a one-position shim."""
    shim = SimpleNamespace(positions={coin: {"hours_held": float(hours_held)}})
    return BasisHarvester.should_exit(shim, coin, current_apr)


@dataclass
class Trade:
    coin: str
    opened: int
    closed: Optional[int] = None
    reason: str = ""
    funding: float = 0.0
    entry_metric: float = 0.0
    breadth: float = 0.0
    episode_hours: int = 0

    @property
    def hours(self) -> int:
        return (self.closed if self.closed is not None else self.opened) - self.opened


@dataclass
class Result:
    arm: str
    slots: int
    hours: List[int]
    friction: float
    trades: List[Trade] = field(default_factory=list)
    curve: List[float] = field(default_factory=list)       # cumulative NET pnl per unit of total slot capital
    gross: float = 0.0
    costs: float = 0.0
    occupied: int = 0

    @property
    def span(self) -> int:
        return len(self.hours)

    def net_apr(self) -> float:
        return (self.gross - self.costs) / (self.slots * self.span) * HOURS_PER_YEAR * 100.0 if self.span else 0.0

    def gross_apr(self) -> float:
        return self.gross / (self.slots * self.span) * HOURS_PER_YEAR * 100.0 if self.span else 0.0

    def max_drawdown_pct(self) -> float:
        peak = worst = 0.0
        for v in self.curve:
            peak = max(peak, v)
            worst = min(worst, v - peak)
        return worst * 100.0


def trailing_apr(rates: Rates, coin: str, t: int) -> Optional[float]:
    xs = [rates[coin][k] for k in range(t - TRAIL_HOURS + 1, t + 1) if k in rates[coin]]
    return apr(sum(xs) / len(xs)) if len(xs) >= TRAIL_MIN_PRESENT else None


def metric(rates: Rates, arm: str, coin: str, t: int) -> Optional[float]:
    """The ranking number at the close of hour t, or None when the coin fails the arm's gate."""
    r = rates[coin].get(t)
    if r is None:
        return None
    cur = apr(r)
    if arm == "P0":
        return cur if cur >= GATE_APR else None
    tr = trailing_apr(rates, coin, t)
    if tr is None or tr < GATE_APR or cur < A_CURRENT_MIN_APR:
        return None
    return min(tr, cur)


def held_rank(rates: Rates, coin: str, t: int) -> Optional[float]:
    r = rates[coin].get(t)
    if r is None:
        return None
    tr = trailing_apr(rates, coin, t)
    return min(tr, apr(r)) if tr is not None else apr(r)


def episode_length(rates: Rates, coin: str, t: int) -> int:
    """Hours in the contiguous >= gate run containing t. Descriptive only - it looks forward."""
    n, k = 0, t
    while k in rates[coin] and apr(rates[coin][k]) >= GATE_APR:
        n, k = n + 1, k - 1
    k = t + 1
    while k in rates[coin] and apr(rates[coin][k]) >= GATE_APR:
        n, k = n + 1, k + 1
    return n


def simulate(rates: Rates, arm: str, slots: int = DEFAULT_SLOTS, spread_bps: float = DEFAULT_SPREAD_BPS,
             hours: Optional[List[int]] = None) -> Result:
    friction = ROUND_TRIP_FEE_PCT / 100.0 + spread_bps / 10_000.0
    if hours is None:
        lo = min(min(v) for v in rates.values() if v)
        hi = max(max(v) for v in rates.values() if v)
        hours = list(range(lo, hi + 1))
    if arm == "PASSIVE":
        slots = 1
    res = Result(arm=arm, slots=slots, hours=hours, friction=friction)
    held: Dict[str, Trade] = {}
    net = 0.0

    def open_(coin: str, t: int, m: float, breadth: float) -> None:
        nonlocal net
        held[coin] = Trade(coin=coin, opened=t, entry_metric=m, breadth=breadth,
                           episode_hours=episode_length(rates, coin, t) if arm != "PASSIVE" else 0)
        res.costs += friction / 2
        net -= friction / 2

    def close_(coin: str, t: int, reason: str) -> None:
        nonlocal net
        tr = held.pop(coin)
        tr.closed, tr.reason = t, reason
        res.trades.append(tr)
        res.costs += friction / 2
        net -= friction / 2

    for t in hours:
        # 1. accrue hour t on what was held through it (opened at t-1 or earlier)
        for coin, tr in held.items():
            r = rates[coin].get(t)
            if r is not None:
                tr.funding += r
                res.gross += r
                net += r
        res.occupied += len(held)

        # 2. exits, decided at the close of t on rates <= t
        if arm != "PASSIVE":
            for coin in list(held):
                r = rates[coin].get(t)
                why = real_should_exit(coin, apr(r) if r is not None else None, t - held[coin].opened)
                if why:
                    close_(coin, t, why)

        # 3. entries, same information set; they earn from t+1
        if arm == "PASSIVE":
            if not held and not res.trades and "BTC" in rates and t in rates["BTC"]:
                open_("BTC", t, apr(rates["BTC"][t]), 0.0)
        else:
            eligible = [c for c in rates if t in rates[c]]
            breadth = (sum(1 for c in eligible if apr(rates[c][t]) >= GATE_APR) / len(eligible)) if eligible else 0.0
            cands = sorted(((m, c) for c in eligible if c not in held
                            for m in [metric(rates, arm if arm != "D" else "A", c, t)] if m is not None), reverse=True)
            for m, c in cands[: max(0, slots - len(held))]:
                open_(c, t, m, breadth)
            if arm == "D" and len(held) >= slots:                       # [CHOICE 2]
                rest = [(m, c) for m, c in cands if c not in held]
                ranked = [(held_rank(rates, c, t), c) for c in held]
                ranked = [(m, c) for m, c in ranked if m is not None]
                if rest and ranked:
                    low_m, low_c = min(ranked)
                    best_m, best_c = rest[0]
                    if best_m - low_m >= ROTATE_MIN_GAIN_APR and t - held[low_c].opened >= ROTATE_MIN_AGE_HOURS:
                        close_(low_c, t, f"rotated out for {best_c} (+{best_m - low_m:.0f} pts)")
                        open_(best_c, t, best_m, breadth)
        res.curve.append(net / slots)

    last = hours[-1] if hours else 0
    for coin in list(held):                                              # mark the survivors out
        close_(coin, last, "open at end of data - marked out")
        res.curve[-1] = net / slots
    return res


def load_rates(db: Path) -> Rates:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        rates: Rates = {}
        for coin, ts, r in conn.execute("SELECT coin, timestamp, funding_rate FROM funding_history"):
            rates.setdefault(str(coin), {})[int(ts) // HOUR_MS] = float(r)
        return rates
    finally:
        conn.close()


def day(h: int) -> str:
    return datetime.fromtimestamp(h * 3600, tz=timezone.utc).strftime("%Y-%m-%d")


def report(res: Result, pop: str) -> None:
    closed = [t for t in res.trades if t.hours > 0 or t.reason]
    n, m = len(closed), len({t.coin for t in closed})
    k = len({day(t.opened) for t in closed})
    holds = [t.hours for t in closed]
    util = 100.0 * res.occupied / (res.slots * res.span) if res.span else 0.0
    print(f"\n--- {res.arm}   [n={n} entries, m={m} coins, K={k} entry-days | Pop: {pop} | "
          f"{day(res.hours[0])} .. {day(res.hours[-1])}, {res.span:,} h] ---")
    print(f"    NET APR {res.net_apr():+7.2f} %   gross {res.gross_apr():+7.2f} %   friction "
          f"{res.gross_apr() - res.net_apr():6.2f} %   ({res.friction * 100:.2f} % a round trip)")
    print(f"    round trips {n:>4}   median hold {statistics.median(holds) if holds else 0:>7.0f} h   "
          f"slot use {util:5.1f} %   max drawdown {res.max_drawdown_pct():+6.2f} % of capital")
    if res.arm != "PASSIVE" and closed:
        sus = sum(1 for t in closed if t.episode_hours >= FLASH_HOURS)
        lo = sum(1 for t in closed if t.breadth < BREADTH_LOW)
        hi = sum(1 for t in closed if t.breadth >= BREADTH_HIGH)
        top = statistics.median(sorted((t.funding for t in closed), reverse=True)[:1])
        tot = sum(t.funding for t in closed)
        print(f"    entries on a sustained episode (>= {FLASH_HOURS} h) {100 * sus / n:4.0f} %   "
              f"low-breadth {lo}   high-breadth {hi}   top trade = {100 * top / tot if tot else 0:4.0f} % of gross funding")
        why: Dict[str, int] = {}
        for t in closed:
            key = ("adverse" if "adverse" in t.reason else "stale" if "stale" in t.reason else
                   "rotated" if "rotated" in t.reason else "marked out")
            why[key] = why.get(key, 0) + 1
        print("    exits: " + "   ".join(f"{a} {b}" for a, b in sorted(why.items(), key=lambda kv: -kv[1])))


def monthly(results: List[Result]) -> None:
    print("\nNET APR BY CALENDAR MONTH  (the P&L booked in the month, on all slot capital)")
    months = sorted({day(h)[:7] for h in results[0].hours})
    print(f"{'month':<9}{'hours':>7}" + "".join(f"{r.arm:>11}" for r in results))
    for mo in months:
        idx = [i for i, h in enumerate(results[0].hours) if day(h)[:7] == mo]
        row = f"{mo:<9}{len(idx):>7}"
        for r in results:
            a = r.curve[idx[0] - 1] if idx[0] > 0 else 0.0
            row += f"{(r.curve[idx[-1]] - a) / len(idx) * HOURS_PER_YEAR * 100:>+10.1f}%"
        print(row)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--slots", type=int, default=DEFAULT_SLOTS)
    ap.add_argument("--spread-bps", type=float, default=DEFAULT_SPREAD_BPS)
    args = ap.parse_args()

    digest = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    rates = load_rates(args.db)
    if not rates:
        print("the store is empty - run fetch_hyperliquid_funding_history.py first", file=sys.stderr)
        return 1
    pop = f"{len(rates)} perps spot-backed on 2026-09-21 (look-ahead), settled hourly funding"
    print("=" * 100 + "\nBASIS POLICY REPLAY (Section 99 WP2)\n" + "=" * 100)
    print(f"script sha256 : {digest}\nslots {args.slots}   spread {args.spread_bps:.0f} bps   fee {ROUND_TRIP_FEE_PCT:.4f} % a round trip")
    results = [simulate(rates, arm, args.slots, args.spread_bps) for arm in ("P0", "A", "D", "PASSIVE")]
    for r in results:
        report(r, pop)
    monthly(results)
    print("\nSPREAD SENSITIVITY - NET APR")
    print(f"{'spread':<10}" + "".join(f"{a:>11}" for a in ("P0", "A", "D", "PASSIVE")))
    for bps in (0.0, 10.0, 20.0):
        print(f"{bps:>4.0f} bps  " + "".join(f"{simulate(rates, a, args.slots, bps).net_apr():>+10.2f}%" for a in ("P0", "A", "D", "PASSIVE")))
    p0, a, d, pas = (r.net_apr() for r in results)
    print("\nSECTION 98 s4 HURDLE FOR D: beat P0 by >= +3.0 % net AND passive BTC by >= +3.0 % net")
    print(f"    D - P0 = {d - p0:+.2f} %    D - PASSIVE = {d - pas:+.2f} %    ->  "
          + ("CLEARS BOTH" if d - p0 >= 3.0 and d - pas >= 3.0 else "DOES NOT CLEAR"))
    print(f"    A - P0 = {a - p0:+.2f} %    A - PASSIVE = {a - pas:+.2f} %")
    print("    A verdict needs Section 99 s2's sample too: >= 30 episodes, >= 8 coins, >= 15 start-days, both regimes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
