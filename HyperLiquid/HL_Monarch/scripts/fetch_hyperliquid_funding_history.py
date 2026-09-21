#!/usr/bin/env python3
"""
Work Package 1 (Antigravity Section 99 s4): pull the exchange's own SETTLED hourly funding
history for the tradeable perps into a store that nothing prunes.

WHY. On 2026-09-21 one statistic took three values in nine hours and every level either
agent quoted rested on a 192 h window that retention was eating from behind (the oldest
row moved from 09-13 05:32Z to 16:45Z during the argument). The exchange keeps funding
history for far longer than we do. This asks it.

SOURCE.  POST https://api.hyperliquid.xyz/info
         {"type": "fundingHistory", "coin": C, "startTime": ms, "endTime": ms}
Verified by probe 2026-09-21 17:30Z: 500 items a page, hourly, ASCENDING from startTime,
fields coin / fundingRate / premium / time. Paged with startTime = last.time + 1.

THE RATE LIMIT IS PER IP, THE PROJECT'S LIMITER IS PER PROCESS. The live collector was
measured at ~750 of the 1200 weight/min on this machine, so this script gets a PRIVATE
bucket, small on purpose (default 180/min), and also pays the endpoint's per-item
surcharge (+1 weight per 20 rows returned) that the flat REQUEST_WEIGHTS table does not
know about. On a 429 it stands down for 90 s rather than fight the collector for the
budget. Slow is the design: ~30 min for 13 coins x 180 d.

IDEMPOTENT. PRIMARY KEY (coin, timestamp) + INSERT OR IGNORE, and every coin resumes from
its last stored hour. A killed run costs nothing; run it again.

WHAT THIS STORE IS NOT.
  * SETTLED rates, not the live predicted quote the bot gates on. They agree at the hour;
    inside the hour the quote moves.
  * The default universe is the 13 perps that were spot-backed ON 2026-09-21 by the bot's
    own rule (spot_symbol_for, $100k floor). That is a LOOK-AHEAD: a name tradeable in
    April and not now is absent, and a name listed in August has no spring. Recorded in
    the store's meta table so no table built on it can forget.
  * No spot volume, no spread, no order book. Liquidity gates cannot be replayed from it.
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from api.rest_client import HyperliquidRestClient, TokenBucketRateLimiter  # noqa: E402

DEFAULT_DB = BASE_DIR / "data" / "funding_history_180d.db"
TRADEABLE_2026_09_21 = ("AVAX", "BTC", "ENA", "ETH", "FARTCOIN", "HYPE", "PENGU", "PUMP",
                        "PURR", "SOL", "XMR", "XPL", "ZEC")
HOUR_MS = 3_600_000
PAGE_BASE_WEIGHT = 20
ITEMS_PER_SURCHARGE_UNIT = 20
STAND_DOWN_SECONDS = 90.0
MAX_STAND_DOWNS = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS funding_history (
    coin         TEXT    NOT NULL,
    timestamp    INTEGER NOT NULL,          -- settlement hour, ms, floored to the hour (UTC)
    funding_rate REAL    NOT NULL,          -- per HOUR, as settled; APR = rate * 8760
    premium      REAL,
    raw_time     INTEGER NOT NULL,          -- the exchange's own stamp, a few ms past the hour
    PRIMARY KEY (coin, timestamp)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS spot_daily (
    coin      TEXT    NOT NULL,             -- the PERP this spot pair would hedge
    pair      TEXT    NOT NULL,             -- the spot PAIR name: "@260", "PURR/USDC". NOT a token index
    day       INTEGER NOT NULL,             -- candle open, ms, 00:00 UTC
    close     REAL    NOT NULL,
    notional  REAL    NOT NULL,             -- close * base volume: the day's spot turnover in USD
    PRIMARY KEY (coin, day)
) WITHOUT ROWID;
"""
SPOT_GENESIS_MS = 1_711_382_400_000        # 2024-03-25, Section 100 s4: early enough to find any genesis candle
ITEMS_PER_CANDLE_SURCHARGE_UNIT = 60


def fetch_spot_daily(client: HyperliquidRestClient, conn: sqlite3.Connection, coins: List[str], end_ms: int) -> None:
    """
    Section 100 s4: when did each perp's spot hedge first trade, and how much a day?

    The pair is resolved by the bot's OWN rule (spot_symbol_for at its own volume floor),
    so the mapping is as of today; what this recovers is the HISTORY of that pair. Candles
    are keyed by the spot PAIR name. The ruling wrote "@<token_index>"; probed 2026-09-21,
    XMR1 is token 404 and pair "@260" - "@404" returns HTTP 500, "@260" returns candles.
    """
    from types import SimpleNamespace
    from analytics.funding_arbitrage import (FundingArbitrageEngine, effective_spot_min_volume,
                                             spot_symbol_for)
    meta, ctxs = client.get_spot_meta_and_asset_ctxs()
    shim = SimpleNamespace(client=SimpleNamespace(get_spot_meta_and_asset_ctxs=lambda: (meta, ctxs)),
                           _spot_volumes=None)                  # the project's parser, no engine, no DB handle
    volumes = FundingArbitrageEngine.get_spot_volumes(shim) or {}
    universe = {t for t, v in volumes.items() if v >= effective_spot_min_volume()}
    names = {int(t["index"]): str(t["name"]).upper() for t in meta.get("tokens", [])}
    pair_volume = {str(c.get("coin")): float(c.get("dayNtlVlm") or 0.0) for c in ctxs or []}
    for coin in coins:
        token = spot_symbol_for(coin, universe, volumes)
        pairs = [(pair_volume.get(str(p["name"]), 0.0), str(p["name"])) for p in meta.get("universe", [])
                 if p.get("tokens") and names.get(int(p["tokens"][0])) == token]
        if not token or not pairs:
            print(f"   {coin}: no spot hedge by the bot's rule today - skipped", flush=True)
            continue
        pair = max(pairs)[1]
        candles = client._post({"type": "candleSnapshot", "req": {
            "coin": pair, "interval": "1d", "startTime": SPOT_GENESIS_MS, "endTime": end_ms}})
        client.rate_limiter.acquire(len(candles) / ITEMS_PER_CANDLE_SURCHARGE_UNIT)
        with conn:
            conn.executemany("INSERT OR REPLACE INTO spot_daily VALUES (?, ?, ?, ?, ?)",
                             [(coin, pair, int(x["t"]), float(x["c"]), float(x["c"]) * float(x["v"])) for x in candles])
        first = iso(int(candles[0]["t"])) if candles else "none"
        print(f"   {coin}: {token} on {pair}, {len(candles)} daily candles, first {first}", flush=True)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def fetch_coin(client: HyperliquidRestClient, conn: sqlite3.Connection, coin: str,
               start_ms: int, end_ms: int) -> int:
    """Page one coin forward from its last stored hour. Returns rows newly stored."""
    row = conn.execute("SELECT MAX(raw_time) FROM funding_history WHERE coin = ?", (coin,)).fetchone()
    cursor = max(start_ms, (row[0] or 0) + 1)
    added = failures = 0
    while cursor < end_ms:
        try:
            page = client._post({"type": "fundingHistory", "coin": coin,
                                 "startTime": cursor, "endTime": end_ms})
        except Exception as exc:                       # the client has already retried; stand down
            failures += 1
            if failures > MAX_STAND_DOWNS:             # never spin against a dead endpoint; resume later
                print(f"   {coin}: giving up after {failures} failures - re-run to resume from {iso(cursor)}", flush=True)
                break
            print(f"   {coin}: request failed ({exc}); standing down {STAND_DOWN_SECONDS:.0f} s", flush=True)
            time.sleep(STAND_DOWN_SECONDS)
            continue
        if not page:
            break
        client.rate_limiter.acquire(len(page) / ITEMS_PER_SURCHARGE_UNIT)      # the per-item surcharge
        rows = [(coin, int(x["time"]) // HOUR_MS * HOUR_MS, float(x["fundingRate"]),
                 float(x["premium"]) if x.get("premium") is not None else None, int(x["time"]))
                for x in page]
        with conn:
            before = conn.total_changes
            conn.executemany("INSERT OR IGNORE INTO funding_history VALUES (?, ?, ?, ?, ?)", rows)
            added += conn.total_changes - before
        last = int(page[-1]["time"])
        if last < cursor:                              # defensive: never loop on a non-advancing page
            break
        cursor = last + 1
        print(f"   {coin}: +{len(page):>3} rows, through {iso(last)}", flush=True)
    return added


def coverage(conn: sqlite3.Connection, coins: List[str], start_ms: int, end_ms: int) -> None:
    print("\nCOVERAGE  [Pop: perps spot-backed on 2026-09-21 by the bot's own rule | settled hourly funding]")
    print(f"{'coin':<10}{'rows':>7}{'first':>20}{'last':>20}{'of listed span':>16}{'holes > 1 h':>13}{'mean APR':>11}{'hours < 0':>11}")
    total = 0
    for coin in coins:
        ts = [r[0] for r in conn.execute(
            "SELECT timestamp FROM funding_history WHERE coin = ? AND timestamp >= ? AND timestamp < ? "
            "ORDER BY timestamp", (coin, start_ms, end_ms))]
        if not ts:
            print(f"{coin:<10}{'none':>7}")
            continue
        total += len(ts)
        span = (ts[-1] - ts[0]) // HOUR_MS + 1
        holes = sum(1 for a, b in zip(ts, ts[1:]) if b - a > HOUR_MS)
        mean, neg = conn.execute(
            "SELECT AVG(funding_rate) * 8760 * 100, SUM(funding_rate < 0) FROM funding_history "
            "WHERE coin = ? AND timestamp >= ? AND timestamp < ?", (coin, start_ms, end_ms)).fetchone()
        print(f"{coin:<10}{len(ts):>7}{iso(ts[0]):>20}{iso(ts[-1]):>20}{100 * len(ts) / span:>15.1f}%"
              f"{holes:>13}{mean:>10.1f}%{100 * (neg or 0) / len(ts):>10.1f}%")
    print(f"[n={total:,} coin-hours, m={len(coins)} coins | horizon {iso(start_ms)} .. {iso(end_ms)}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--coins", nargs="*", default=list(TRADEABLE_2026_09_21))
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--weight-per-minute", type=int, default=180,
                    help="PRIVATE budget. The IP ceiling is 1200 and the live collector uses ~750 of it.")
    ap.add_argument("--coverage-only", action="store_true", help="report what the store holds; fetch nothing")
    ap.add_argument("--spot-daily", action="store_true",
                    help="pull each perp's spot-hedge daily candles instead of funding (Section 100 s4)")
    args = ap.parse_args()

    end_ms = int(time.time() * 1000) // HOUR_MS * HOUR_MS
    start_ms = end_ms - args.days * 24 * HOUR_MS
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(args.db))
    conn.executescript(SCHEMA)
    try:
        if args.spot_daily:
            client = HyperliquidRestClient(
                rate_limiter=TokenBucketRateLimiter(weight_per_minute=args.weight_per_minute, safety_factor=1.0))
            print(f"spot-hedge daily candles for {len(args.coins)} perps at {args.weight_per_minute} weight/min "
                  f"-> {args.db}", flush=True)
            fetch_spot_daily(client, conn, list(args.coins), int(time.time() * 1000))
            return 0
        if not args.coverage_only:
            digest = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            with conn:
                for k, v in (("source", "POST https://api.hyperliquid.xyz/info fundingHistory (settled, hourly)"),
                             ("universe", "perps spot-backed on 2026-09-21 by spot_symbol_for at the $100k floor - "
                                          "a LOOK-AHEAD for any earlier date"),
                             ("last_fetch_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                             ("days_requested", str(args.days)), ("fetcher_sha256", digest)):
                    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, v))
            client = HyperliquidRestClient(
                rate_limiter=TokenBucketRateLimiter(weight_per_minute=args.weight_per_minute, safety_factor=1.0))
            print(f"fetching {args.days} d for {len(args.coins)} coins at {args.weight_per_minute} weight/min "
                  f"-> {args.db}", flush=True)
            for coin in args.coins:
                added = fetch_coin(client, conn, coin, start_ms, end_ms)
                print(f"{coin}: {added} new rows", flush=True)
        coverage(conn, list(args.coins), start_ms, end_ms)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
