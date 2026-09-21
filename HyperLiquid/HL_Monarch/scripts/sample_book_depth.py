#!/usr/bin/env python3
"""
WP3 preparation (Antigravity Section 101 s3.3): sample what a basis round trip COSTS AT A
SIZE, both legs, for the tradeable perps - as a distribution instead of one afternoon's
two snapshots.

WHY A STANDALONE SCRIPT FIRST. The measurement belongs in collectors/orderbook_sampler.py,
but that module is imported by the LIVE collector: an edit on master deploys itself at the
next restart, against this project's own staging rule. So the integration waits for a
branch and a deploy window, and this script lets the distribution start accruing without
touching the collector at all - separate process, separate SQLite file, separate (small)
API budget. Both will call analytics/book_walk.py, so there is one definition of "cost".

WHAT IT RECORDS, per coin, per pass, per size in {$1,000, $2,500, $5,000, $10,000}:
the perp leg's round trip, the spot leg's, their total, and each leg's visible depth on its
thinner side. A size the visible book cannot absorb is stored as NULL - an unfillable size
is a different fact from a cheap one, and the report counts it as a FILL RATE rather than
averaging it away.

BOUNDED BY DEFAULT: one pass, then exit. --passes and --interval make it loop, and it still
ends. It is not a daemon and does not try to be one.

BUDGET. One spotMetaAndAssetCtxs (20) per run, then 2 l2Book calls (2 each) per coin per
pass: 13 coins = 52 weight a pass. The exchange meters per IP and the live collector was
measured at ~750 of 1200/min, so this runs on a PRIVATE 120/min bucket. A coin that fails is
recorded by name and the pass goes on - one 429 must not cost the other twelve books.

LIMITS. l2Book shows 20 levels a side: hidden and iceberg liquidity, and the refill after a
fill, are invisible. The pair for each perp is resolved by the bot's own spot_symbol_for as
of NOW. Costs assume crossing the book on all four fills - a taker - which is the strategy
Section 101 s3 is judging.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from analytics import book_walk as bw  # noqa: E402
from api.rest_client import HyperliquidRestClient, TokenBucketRateLimiter  # noqa: E402

DEFAULT_DB = BASE_DIR / "data" / "book_depth_samples.db"
TRADEABLE_2026_09_21 = ("AVAX", "BTC", "ENA", "ETH", "FARTCOIN", "HYPE", "PENGU", "PUMP",
                        "PURR", "SOL", "XMR", "XPL", "ZEC")
SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    ts             INTEGER NOT NULL,        -- pass time, ms
    coin           TEXT    NOT NULL,        -- the perp
    pair           TEXT    NOT NULL,        -- its spot hedge's PAIR name
    size_usd       INTEGER NOT NULL,        -- per leg
    perp_rt_bps    REAL,                    -- NULL = the visible perp book could not absorb it
    spot_rt_bps    REAL,
    total_rt_bps   REAL,                    -- NULL if either leg is NULL
    perp_depth_usd REAL    NOT NULL,        -- visible, thinner side
    spot_depth_usd REAL    NOT NULL,
    perp_touch_bps REAL    NOT NULL,
    spot_touch_bps REAL    NOT NULL,
    PRIMARY KEY (ts, coin, size_usd)
) WITHOUT ROWID;
"""


def resolve_spot_pairs(client: HyperliquidRestClient, coins: List[str]) -> Dict[str, str]:
    """perp -> spot PAIR name, by the bot's own rule. A perp with no hedge today is left out."""
    from analytics.funding_arbitrage import FundingArbitrageEngine, effective_spot_min_volume, spot_symbol_for
    meta, ctxs = client.get_spot_meta_and_asset_ctxs()
    shim = SimpleNamespace(client=SimpleNamespace(get_spot_meta_and_asset_ctxs=lambda: (meta, ctxs)),
                           _spot_volumes=None)
    volumes = FundingArbitrageEngine.get_spot_volumes(shim) or {}
    universe = {t for t, v in volumes.items() if v >= effective_spot_min_volume()}
    names = {int(t["index"]): str(t["name"]).upper() for t in meta.get("tokens", [])}
    pair_volume = {str(c.get("coin")): float(c.get("dayNtlVlm") or 0.0) for c in ctxs or []}
    out: Dict[str, str] = {}
    for coin in coins:
        token = spot_symbol_for(coin, universe, volumes)
        pairs = [(pair_volume.get(str(p["name"]), 0.0), str(p["name"])) for p in meta.get("universe", [])
                 if p.get("tokens") and names.get(int(p["tokens"][0])) == token]
        if token and pairs:
            out[coin] = max(pairs)[1]
    return out


def one_pass(client: HyperliquidRestClient, conn: sqlite3.Connection, pairs: Dict[str, str]) -> Dict[str, str]:
    ts = int(time.time() * 1000)
    failures: Dict[str, str] = {}
    rows = []
    for coin, pair in pairs.items():
        try:
            perp, spot = client._post({"type": "l2Book", "coin": coin}), client._post({"type": "l2Book", "coin": pair})
            pb, pa = bw.parse_book(perp)
            sb, sa = bw.parse_book(spot)
            for size in bw.SIZES_USD:
                r = bw.basis_round_trip_bps(perp, spot, size)
                rows.append((ts, coin, pair, size, r["perp"], r["spot"], r["total"],
                             bw.thinner_side_usd(perp), bw.thinner_side_usd(spot),
                             bw.touch_spread_bps(pb, pa), bw.touch_spread_bps(sb, sa)))
        except Exception as exc:                           # noqa: BLE001 - isolate per coin, as the collector's sampler does
            failures[coin] = f"{type(exc).__name__}: {exc}"
    with conn:
        conn.executemany("INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    return failures


def report(conn: sqlite3.Connection) -> None:
    span = conn.execute("SELECT MIN(ts), MAX(ts), COUNT(DISTINCT ts) FROM samples").fetchone()
    if not span or not span[2]:
        print("no samples yet")
        return
    iso = lambda ms: datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%m-%d %H:%M:%SZ")      # noqa: E731
    coins = [r[0] for r in conn.execute("SELECT DISTINCT coin FROM samples ORDER BY coin")]
    print(f"BASIS ROUND TRIP, BOTH LEGS, TAKER, bps of notional - median / p95, and the share of passes the visible book could fill")
    print(f"[n={span[2]} passes, m={len(coins)} coins | Pop: perps spot-backed by the bot's rule when sampled | {iso(span[0])} .. {iso(span[1])} | l2Book, 20 levels]")
    print(f"{'coin':<10}" + "".join(f"{'$%s a leg' % format(s, ','):>26}" for s in bw.SIZES_USD) + f"{'thinner-side depth, median (perp / spot)':>44}")
    for coin in coins:
        cells = []
        for size in bw.SIZES_USD:
            allr = conn.execute("SELECT total_rt_bps FROM samples WHERE coin=? AND size_usd=?", (coin, size)).fetchall()
            ok = sorted(r[0] for r in allr if r[0] is not None)
            fill = 100.0 * len(ok) / len(allr) if allr else 0.0
            cells.append(f"{bw.percentile(ok, .5):>7.1f} /{bw.percentile(ok, .95):>7.1f}  {fill:>4.0f}%" if ok else f"{'unfillable':>17}  {fill:>4.0f}%")
        pd = sorted(r[0] for r in conn.execute("SELECT perp_depth_usd FROM samples WHERE coin=? AND size_usd=?", (coin, bw.SIZES_USD[0])))
        sd = sorted(r[0] for r in conn.execute("SELECT spot_depth_usd FROM samples WHERE coin=? AND size_usd=?", (coin, bw.SIZES_USD[0])))
        print(f"{coin:<10}" + "".join(f"{c:>26}" for c in cells) + f"{'$%s / $%s' % (format(int(bw.percentile(pd, .5)), ','), format(int(bw.percentile(sd, .5)), ',')):>44}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--coins", nargs="*", default=list(TRADEABLE_2026_09_21))
    ap.add_argument("--passes", type=int, default=1, help="how many passes before exiting. It always exits.")
    ap.add_argument("--interval", type=float, default=300.0, help="seconds between passes")
    ap.add_argument("--weight-per-minute", type=int, default=120, help="PRIVATE budget; the IP ceiling is shared with the live collector")
    ap.add_argument("--report", action="store_true", help="print the distribution held in the store; sample nothing")
    args = ap.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(args.db))
    conn.executescript(SCHEMA)
    try:
        if not args.report:
            client = HyperliquidRestClient(
                rate_limiter=TokenBucketRateLimiter(weight_per_minute=args.weight_per_minute, safety_factor=1.0))
            pairs = resolve_spot_pairs(client, list(args.coins))
            missing = [c for c in args.coins if c not in pairs]
            print(f"{len(pairs)} perps with a spot hedge" + (f"; none today for {', '.join(missing)}" if missing else ""), flush=True)
            for i in range(max(1, args.passes)):
                failures = one_pass(client, conn, pairs)
                stamp = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"pass {i + 1}/{args.passes} at {stamp}: {len(pairs) - len(failures)} books walked"
                      + (f", FAILED {failures}" if failures else ""), flush=True)
                if i + 1 < args.passes:
                    time.sleep(max(0.0, args.interval))
        report(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
