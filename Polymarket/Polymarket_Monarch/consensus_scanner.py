"""
================================================================================
Polymarket Monarch: Sharp Trader Consensus Scanner
================================================================================
Indexes the sharpest wallets found by pnl_scanner, pulls their recent trade
activity, and emits a signal when two or more of them independently take the
SAME side of the SAME market inside a short window.

The thesis: one sharp wallet buying YES is an opinion. Three of them buying YES
within three hours, without coordinating, is information.

--------------------------------------------------------------------------------
THE FILTER PROBLEM YOU MUST UNDERSTAND BEFORE TRUSTING ANY SIGNAL
--------------------------------------------------------------------------------
The specified bar was win_rate >= 60% and realized_pnl >= $5,000. Applied to the
live table that selects 12 wallets - and the top one has a 100% win rate on ONE
closed position. Several others sit at 100% on 1-5. A win rate over a handful of
closed positions is noise, and ranking by it selects whoever got lucky recently,
which is the classic way to build a copy-trading system that tracks survivorship
instead of skill.

So MIN_CLOSED_POSITIONS exists and defaults to 10. The cost is honest and steep:

    closed >=  1  ->  12 wallets      closed >= 20  ->  4 wallets
    closed >=  5  ->   9 wallets      closed >= 30  ->  2 wallets
    closed >= 10  ->   7 wallets      closed >= 50  ->  0 wallets

The directive asked for the "top 20 sharp wallets". Twenty do not exist at this
bar - seven do. Widening the filter to reach twenty would mean filling the roster
with 100%-on-one-trade wallets, which is worse than a smaller roster.

--------------------------------------------------------------------------------
WHAT THIS DOES NOT MODEL
--------------------------------------------------------------------------------
  * LATENCY. We see a trade only after it settles and the API serves it. The
    copy fills at the CURRENT ask, not the sharp's price, and `slippage_pct`
    records the gap. A signal whose slippage exceeds its edge is not tradeable,
    and the paper engine records that rather than hiding it.
  * Sharps exiting. Activity gives BUY and SELL; a consensus of SELLs on an
    outcome is treated as a consensus AGAINST it, not ignored.
  * Correlated wallets. Two wallets under one operator look like consensus and
    are indistinguishable from it at this level of data.
  * win_rate here is 7-day and recomputed by pnl_scanner; it is a rolling
    quality estimate, not a lifetime record.
================================================================================
"""

import os
import sys
import json
import time
import sqlite3
import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Ensure UTF-8 output on Windows consoles (market titles carry accents).
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich import box

from tax_gate import TaxGate, add_tax_arguments, build_gate

# tax_gate has already put DEV/ on sys.path, so the agent is importable here.
try:
    from Tax_Reserve_Agent.interfaces.monarch_hook import categorise, wilson_lower_bound
except Exception:  # agent unavailable - degrade, do not crash the scanner
    def categorise(symbol, patterns=None):        # type: ignore
        return "uncategorised"

    def wilson_lower_bound(wins, trials, z=1.0):  # type: ignore
        return (wins / trials) if trials else 0.0

console = Console()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "polymarket_whales.db"
PAPER_PATH = DATA_DIR / "consensus_paper_state.json"

DATA_API_BASE = "https://data-api.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
HEADERS = {"User-Agent": "PolymarketMonarch/1.0"}

MIN_WIN_RATE = 60.0
MIN_REALIZED_PNL = 5_000.0
MIN_CLOSED_POSITIONS = 10      # see the filter note in the module docstring
MAX_WALLETS = 20
CONSENSUS_WINDOW_HOURS = 3.0
MIN_CONSENSUS_WALLETS = 2
COPY_SIZE_USD = 100.0
# Front-run guard. Sharps entering at 0.35 push the contract to 0.65; a copy filling
# at the new price buys after the edge is gone. Above this much appreciation versus
# their fill, the trade is refused rather than sized down - the move IS the signal
# being consumed.
MAX_ENTRY_APPRECIATION_PCT = 15.0
# A wallet placing more than this many trades on ONE market inside the window is
# quoting it, not taking a view. Real conviction is a few fills, not fifty.
MAX_TRADES_PER_WALLET = 8.0
# Markets resolving faster than this are the domain of quoting bots, not
# forecasters. A 5m/15m/1h "Bitcoin Up or Down" has no thesis to have an edge on,
# while 6h+ admits same-day macro, economic prints (CPI), and sports.
MIN_MARKET_DURATION_HOURS = 6.0
# AFTER-TAX BREAK-EVEN. A copy is only worth taking if its expected edge survives
# fees AND tax. Under gross-of-fees accounting the tax lands on the GROSS gain
# while fees come out of pocket unrecorded, so break-even is fee/(1-tax), not fee:
# a 2% round trip at a 35% composite rate needs 3.08%, and a 2.5% "edge" clears
# its fees and still loses money. Overridden at runtime by the Tax Reserve Agent's
# computed figure; this constant is the fallback when the agent is unavailable.
MIN_AFTER_TAX_EDGE = 0.0308
GAMMA_BATCH = 20

_MIN_REQUEST_GAP = 0.20
_last_request_ts = 0.0


def _get(url: str, params: Optional[Dict] = None, timeout: int = 20) -> Optional[requests.Response]:
    """Rate-limited GET. Cloudflare 429s on bursts; one bad wallet must not end a sweep."""
    global _last_request_ts
    gap = time.monotonic() - _last_request_ts
    if gap < _MIN_REQUEST_GAP:
        time.sleep(_MIN_REQUEST_GAP - gap)
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        _last_request_ts = time.monotonic()
        return resp if resp.status_code == 200 else None
    except requests.RequestException:
        _last_request_ts = time.monotonic()
        return None


# ------------------------------------------------------------------ roster

def load_sharp_wallets(db_path: Path = DB_PATH,
                       min_win_rate: float = MIN_WIN_RATE,
                       min_pnl: float = MIN_REALIZED_PNL,
                       min_closed: int = MIN_CLOSED_POSITIONS,
                       limit: int = MAX_WALLETS) -> List[Dict[str, Any]]:
    """
    The sharp roster, ranked by realized PnL.

    Ranked by PnL rather than win rate deliberately: win rate over a handful of
    closed positions is dominated by luck, and ranking on it would put the
    100%-on-one-trade wallets at the top of the roster.
    """
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT wallet, proxy_wallet, pseudonym, win_rate, realized_pnl_7d,
                   closed_positions_7d, volume_7d, trades_7d
            FROM sharp_traders
            WHERE win_rate >= ? AND realized_pnl_7d >= ? AND closed_positions_7d >= ?
            ORDER BY realized_pnl_7d DESC
            LIMIT ?
            """,
            (min_win_rate, min_pnl, min_closed, limit),
        ).fetchall()
    finally:
        conn.close()
    return [{
        "wallet": r["proxy_wallet"] or r["wallet"],
        "pseudonym": r["pseudonym"] or "Anonymous",
        "win_rate": float(r["win_rate"] or 0.0),
        "realized_pnl": float(r["realized_pnl_7d"] or 0.0),
        "closed_positions": int(r["closed_positions_7d"] or 0),
    } for r in rows]


# ------------------------------------------------------------------ activity

def fetch_activity(wallet: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Recent trades for one wallet, normalised. TRADE rows only - not redemptions or splits."""
    resp = _get(f"{DATA_API_BASE}/activity", {"user": wallet, "limit": limit})
    if resp is None:
        return []
    out = []
    for a in resp.json() or []:
        if str(a.get("type", "")).upper() != "TRADE":
            continue
        try:
            out.append({
                "wallet": wallet,
                "condition_id": a.get("conditionId"),
                "title": a.get("title") or "?",
                "slug": a.get("slug") or a.get("eventSlug") or "",
                "outcome": a.get("outcome") or "?",
                "side": str(a.get("side", "")).upper(),      # BUY / SELL
                "price": float(a.get("price") or 0.0),
                "usd": float(a.get("usdcSize") or 0.0),
                "timestamp": int(a.get("timestamp") or 0),   # seconds
                "asset": a.get("asset"),
            })
        except (TypeError, ValueError):
            continue
    return out


# ------------------------------------------------------------------ duration

def _parse_iso(value: Optional[str]) -> Optional[float]:
    """Gamma timestamps are ISO-8601 with a trailing Z; return epoch seconds."""
    if not value:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def fetch_market_durations(condition_ids: List[str]) -> Dict[str, float]:
    """
    TRADEABLE WINDOW in hours, keyed by conditionId.

    NOT endDate - startDate. That was the first attempt and it silently failed on
    exactly the markets this exists to catch: for a 15-minute "Bitcoin Up or Down",
    Gamma reports startDate as when the market OBJECT was created (~24h earlier)
    and endDate as the real resolution, giving a phantom ~23.9h lifetime. Every
    micro-market clustered just under the 24h threshold by accident.

    `eventStartTime` is when the window actually opens, so:

        window = endDate - eventStartTime   (falls back to startDate if absent)

    which correctly reports 0.25h for the 15-minute market and months for a
    macro one.

    Batched (Gamma accepts repeated condition_ids), with an explicit limit -
    without it the endpoint returns a short default page and most of the batch
    comes back unresolved, which reads as "unknown duration" and defeats the filter.
    """
    out: Dict[str, float] = {}
    unique = [c for c in dict.fromkeys(condition_ids) if c]
    for i in range(0, len(unique), GAMMA_BATCH):
        chunk = unique[i:i + GAMMA_BATCH]
        # Two passes. Gamma's /markets returns only OPEN markets by default, and a
        # 5-minute binary from an hour ago is closed - so the markets this filter
        # most needs to see were the exact ones missing from the response.
        rows = []
        for extra in ([("limit", str(len(chunk)))],
                      [("limit", str(len(chunk))), ("closed", "true")]):
            resp = _get(f"{GAMMA_API_BASE}/markets",
                        [("condition_ids", c) for c in chunk] + extra)
            if resp is not None:
                rows.extend(resp.json() or [])
        for m in rows:
            cid = m.get("conditionId")
            end = _parse_iso(m.get("endDate"))
            # eventStartTime is the real window open; startDate is object creation.
            start = _parse_iso(m.get("eventStartTime")) or _parse_iso(m.get("startDate"))
            if cid and start is not None and end is not None and end > start:
                out[cid] = (end - start) / 3600.0
    return out


def filter_by_duration(trades: List[Dict[str, Any]],
                       durations: Dict[str, float],
                       min_hours: float = MIN_MARKET_DURATION_HOURS
                       ) -> Tuple[List[Dict[str, Any]], int]:
    """
    Drop trades on markets too short-lived to carry a forecast.

    This is a PROXY for "is this a market maker", and a blunt one - a long-dated
    market can be quoted too. It complements rather than replaces the direct
    tests in _suppress_market_making, which catch the behaviour itself. Both are
    kept because they fail differently.

    A market whose duration could not be fetched is KEPT, not dropped: an
    unknown duration is not evidence of a short one, and silently discarding
    unresolvable markets would bias the sample toward whatever Gamma happens to
    serve. The suppression guards still apply to it downstream.
    """
    kept, dropped = [], 0
    for t in trades:
        d = durations.get(t.get("condition_id"))
        if d is not None and d < min_hours:
            dropped += 1
            continue
        kept.append(t)
    return kept, dropped


# ------------------------------------------------------------------ consensus

def find_consensus(trades: List[Dict[str, Any]],
                   wallets_by_addr: Dict[str, Dict[str, Any]],
                   window_hours: float = CONSENSUS_WINDOW_HOURS,
                   min_wallets: int = MIN_CONSENSUS_WALLETS) -> List[Dict[str, Any]]:
    """
    Clusters of >= min_wallets DISTINCT sharp wallets on the same market/outcome/side.

    Distinct wallets is the whole point: one wallet scaling into a position across
    six fills is one opinion, and counting those six as consensus would fire a
    signal on every large order a single sharp places.

    The window slides over each group rather than being bucketed to a wall clock,
    so two trades 10 minutes apart always cluster - a fixed 3-hour bucket would
    miss them whenever they straddle a boundary.
    """
    window = window_hours * 3600.0
    groups: Dict[Tuple[Any, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for t in trades:
        if not t.get("condition_id"):
            continue
        groups[(t["condition_id"], t["outcome"], t["side"])].append(t)

    signals: List[Dict[str, Any]] = []
    for (cid, outcome, side), rows in groups.items():
        rows.sort(key=lambda r: r["timestamp"])
        i = 0
        for j in range(len(rows)):
            while rows[j]["timestamp"] - rows[i]["timestamp"] > window:
                i += 1
            cluster = rows[i:j + 1]
            distinct = {r["wallet"] for r in cluster}
            if len(distinct) < min_wallets:
                continue

            # Keep the strongest cluster per group rather than one per trade.
            metas = [wallets_by_addr[w] for w in distinct if w in wallets_by_addr]
            combined = sum(r["usd"] for r in cluster)
            sig = {
                "condition_id": cid,
                "title": cluster[-1]["title"],
                "slug": cluster[-1]["slug"],
                "outcome": outcome,
                "side": side,
                "wallets": sorted(distinct),
                "wallet_names": [m["pseudonym"] for m in metas],
                "n_wallets": len(distinct),
                "n_trades": len(cluster),
                "combined_usd": combined,
                "avg_price": (sum(r["price"] * r["usd"] for r in cluster) / combined
                              if combined > 0 else 0.0),
                "aggregate_win_rate": (sum(m["win_rate"] for m in metas) / len(metas)
                                       if metas else 0.0),
                # Sample size behind that win rate. Carried so the edge filter can
                # shrink it - a 70% rate over 12 closed positions is a different
                # claim from the same rate over 300.
                "aggregate_closed": sum(m.get("closed_positions", 0) for m in metas),
                "aggregate_pnl": sum(m["realized_pnl"] for m in metas),
                "first_ts": cluster[0]["timestamp"],
                "last_ts": cluster[-1]["timestamp"],
                "span_hours": (cluster[-1]["timestamp"] - cluster[0]["timestamp"]) / 3600.0,
                "asset": cluster[-1].get("asset"),
            }
            existing = next((s for s in signals if s["condition_id"] == cid
                             and s["outcome"] == outcome and s["side"] == side), None)
            if existing is None:
                signals.append(sig)
            elif (sig["n_wallets"], sig["combined_usd"]) > (existing["n_wallets"],
                                                            existing["combined_usd"]):
                signals[signals.index(existing)] = sig

    signals, suppressed = _suppress_market_making(signals)
    signals.sort(key=lambda s: (s["n_wallets"], s["combined_usd"]), reverse=True)
    suppressed.sort(key=lambda s: s["combined_usd"], reverse=True)
    return signals, suppressed


def _suppress_market_making(signals: List[Dict[str, Any]],
                            max_trades_per_wallet: float = MAX_TRADES_PER_WALLET
                            ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Drop clusters that are liquidity provision rather than conviction.

    THE FIRST LIVE RUN FOUND EXACTLY THIS and it would have been ruinous. The same
    two wallets fired "consensus" on BUY Up AND BUY Down of the same 5-minute
    Bitcoin market - 50 and 53 trades inside six minutes. They were not disagreeing
    with themselves; they were market-making a binary. Copying both legs means
    buying both outcomes at the ask and paying the spread twice, on a market that
    resolves in five minutes.

    Two independent tests, because either alone is escapable:
      1. CONTRADICTION - the same wallets appear on opposing outcomes of one
         market. A directional view cannot point both ways.
      2. CHURN - trades per wallet inside the window. Conviction is a handful of
         fills; twenty-five is a quote stream.
    """
    by_market: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for sig in signals:
        by_market[sig["condition_id"]].append(sig)

    kept, dropped = [], []
    for cid, group in by_market.items():
        contradictory = set()
        for a in group:
            for b in group:
                if a is b or a["outcome"] == b["outcome"]:
                    continue
                if set(a["wallets"]) & set(b["wallets"]):
                    contradictory.add(id(a))
                    contradictory.add(id(b))

        for sig in group:
            churn = sig["n_trades"] / max(sig["n_wallets"], 1)
            if id(sig) in contradictory:
                sig["suppressed_reason"] = ("same wallets on opposing outcomes - "
                                            "market making, not conviction")
                dropped.append(sig)
            elif churn > max_trades_per_wallet:
                sig["suppressed_reason"] = (f"{churn:.0f} trades per wallet in the window - "
                                            f"quoting, not taking a view")
                dropped.append(sig)
            else:
                kept.append(sig)
    return kept, dropped


def current_ask(asset_id: Optional[str]) -> Optional[float]:
    """Best ask for the outcome token, used to price the copy honestly."""
    if not asset_id:
        return None
    resp = _get("https://clob.polymarket.com/book", {"token_id": asset_id})
    if resp is None:
        return None
    asks = resp.json().get("asks") or []
    prices = []
    for a in asks:
        try:
            p = float(a.get("price"))
        except (TypeError, ValueError):
            continue
        if 0 < p < 1:
            prices.append(p)
    return min(prices) if prices else None


# ------------------------------------------------------------------ paper book

class ConsensusPaperBook:
    """
    Paper copy-trading on consensus signals.

    Deliberately records `slippage_pct` on every entry - the gap between the
    sharps' average fill and the price we can actually get now. A copy-trading
    system that reports the sharps' price as its own entry is measuring their
    edge, not ours.
    """

    def __init__(self, starting_cash: float = 10_000.0, path: Path = PAPER_PATH):
        self.path = Path(path)
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self.skipped_no_book = 0
        self.skipped_priced_in = 0

    skipped_below_breakeven = 0

    def key(self, sig: Dict[str, Any]) -> str:
        return f"{sig['condition_id']}|{sig['outcome']}|{sig['side']}"

    @staticmethod
    def shrunk_win_rate(win_rate_pct: Optional[float], closed_positions: Optional[int]) -> float:
        """
        Wilson lower bound on the sharps' aggregate win rate.

        THE RAW RATE IS BIASED HIGH AND CANNOT BE USED AS p. These wallets are on
        the roster BECAUSE they won - `MIN_WIN_RATE = 60` and
        `MIN_REALIZED_PNL = $5,000` select for it - so their historical rate is a
        survivorship artefact, not an unbiased forecast. Feeding it straight into
        an edge makes the filter too permissive, which is the wrong direction for
        something whose entire job is to REJECT.

        Shrinking against the sample size behind it is the cheap correction: a 70%
        rate over 12 closed positions comes back around 0.53, while the same rate
        over 300 barely moves. It does not remove selection bias - nothing here
        can - but it stops a small, lucky sample from clearing the threshold.
        """
        if not win_rate_pct or win_rate_pct <= 0:
            return 0.0
        n = int(closed_positions or 0)
        if n <= 0:
            # No sample behind the number. MIN_CLOSED_POSITIONS is the weakest
            # roster that could have produced it, so assume exactly that.
            n = MIN_CLOSED_POSITIONS
        p_hat = min(max(float(win_rate_pct) / 100.0, 0.0), 1.0)
        wins = int(round(p_hat * n))
        return wilson_lower_bound(wins, n)

    @staticmethod
    def expected_edge(win_rate_pct: Optional[float], ask: Optional[float],
                      closed_positions: Optional[int] = None) -> Optional[float]:
        """
        Expected gross edge per dollar staked on a copy, or None if unmeasurable.

        Buying one share at `ask` returns $1 when the thesis lands, so per dollar
        staked the expectation is (p - ask) / ask, with p the SHRUNK win rate.
        """
        if win_rate_pct is None or ask is None or ask <= 0 or ask >= 1.0:
            return None
        p = ConsensusPaperBook.shrunk_win_rate(win_rate_pct, closed_positions)
        return (p - float(ask)) / float(ask)

    def copy(self, sig: Dict[str, Any], size_usd: float = COPY_SIZE_USD,
             ask: Optional[float] = None,
             max_appreciation_pct: float = MAX_ENTRY_APPRECIATION_PCT,
             min_edge: float = 0.0
             ) -> Optional[Dict[str, Any]]:
        k = self.key(sig)
        if k in self.positions:
            return None                       # one copy per consensus, never pyramided
        if ask is None or ask <= 0 or ask >= 1.0:
            self.skipped_no_book += 1
            return None

        sharp_px = sig["avg_price"] or ask
        slippage = (ask - sharp_px) / sharp_px * 100.0 if sharp_px > 0 else 0.0

        # ALREADY PRICED IN. Refused, not sized down: if the contract has already
        # moved this far toward the sharps' thesis, the information is in the price
        # and we would be buying the exhausted end of their edge.
        if slippage > max_appreciation_pct:
            self.skipped_priced_in += 1
            return None

        # BELOW AFTER-TAX BREAK-EVEN. Distinct from the priced-in guard above: that
        # one asks whether the sharps' move is already spent, this one asks whether
        # what remains can survive fees and tax at all. A signal can be perfectly
        # fresh and still not clear 3.08%.
        edge = self.expected_edge(sig.get("aggregate_win_rate"), ask,
                                  sig.get("aggregate_closed"))
        if min_edge > 0 and edge is not None and edge < min_edge:
            self.skipped_below_breakeven += 1
            return None

        if size_usd > self.cash:
            return None
        pos = {
            "key": k,
            "title": sig["title"],
            "outcome": sig["outcome"],
            "side": sig["side"],
            "entry_price": ask,
            "sharp_avg_price": sharp_px,
            "slippage_pct": slippage,
            "expected_edge_pct": (edge * 100.0) if edge is not None else None,
            "category": categorise(f"{sig.get('slug', '')}-{sig.get('outcome', '')}"),
            "shares": size_usd / ask,
            "cost_usd": size_usd,
            "n_wallets": sig["n_wallets"],
            "aggregate_win_rate": sig["aggregate_win_rate"],
            "opened_at": int(time.time()),
        }
        self.cash -= size_usd
        self.positions[k] = pos
        self.history.append({**pos, "event": "OPEN"})
        return pos

    def summary(self) -> Dict[str, Any]:
        slips = [p["slippage_pct"] for p in self.positions.values()]
        return {
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "skipped_below_breakeven": self.skipped_below_breakeven,
            "open_positions": len(self.positions),
            "deployed_usd": sum(p["cost_usd"] for p in self.positions.values()),
            "mean_slippage_pct": (sum(slips) / len(slips)) if slips else None,
            "skipped_no_book": self.skipped_no_book,
            "skipped_priced_in": self.skipped_priced_in,
        }

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "positions": self.positions,
            "history": self.history[-500:],
            "skipped_no_book": self.skipped_no_book,
            "skipped_priced_in": self.skipped_priced_in,
            "saved_at": int(time.time()),
        }, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def load(self) -> bool:
        if not self.path.exists():
            return False
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        self.starting_cash = d.get("starting_cash", self.starting_cash)
        self.cash = d.get("cash", self.starting_cash)
        self.positions = d.get("positions", {})
        self.history = d.get("history", [])
        self.skipped_no_book = d.get("skipped_no_book", 0)
        self.skipped_priced_in = d.get("skipped_priced_in", 0)
        return True


# ------------------------------------------------------------------ scan

def scan(min_win_rate: float = MIN_WIN_RATE,
         min_pnl: float = MIN_REALIZED_PNL,
         min_closed: int = MIN_CLOSED_POSITIONS,
         max_wallets: int = MAX_WALLETS,
         window_hours: float = CONSENSUS_WINDOW_HOURS,
         min_wallets: int = MIN_CONSENSUS_WALLETS,
         activity_limit: int = 100,
         min_duration_hours: float = MIN_MARKET_DURATION_HOURS,
         db_path: Path = DB_PATH) -> Dict[str, Any]:
    roster = load_sharp_wallets(db_path, min_win_rate, min_pnl, min_closed, max_wallets)
    by_addr = {w["wallet"]: w for w in roster}

    trades: List[Dict[str, Any]] = []
    for w in roster:
        trades.extend(fetch_activity(w["wallet"], limit=activity_limit))

    durations = fetch_market_durations([t["condition_id"] for t in trades]) if trades else {}
    filtered, short_dropped = filter_by_duration(trades, durations, min_duration_hours)

    signals, suppressed = find_consensus(filtered, by_addr, window_hours, min_wallets)
    return {
        "suppressed": suppressed,
        "short_market_trades_dropped": short_dropped,
        "min_duration_hours": min_duration_hours,
        "markets_dated": len(durations),
        "roster": roster,
        "roster_size": len(roster),
        "requested_wallets": max_wallets,
        "trades_scanned": len(trades),
        "signals": signals,
        "window_hours": window_hours,
        "min_wallets": min_wallets,
        "min_closed": min_closed,
    }


def render(result: Dict[str, Any], book: Optional[ConsensusPaperBook] = None) -> None:
    console.print()
    roster, n = result["roster"], result["roster_size"]
    console.print(f"[bold]Sharp consensus scan[/bold]  ·  roster {n}/"
                  f"{result['requested_wallets']} wallets  ·  "
                  f"{result['trades_scanned']} trades  ·  "
                  f">={result['min_wallets']} wallets within {result['window_hours']:.0f}h")

    if n < result["requested_wallets"]:
        console.print(f"[yellow]Only {n} wallets clear the bar (win rate, PnL, and "
                      f">={result['min_closed']} closed positions). Loosening the closed-position "
                      f"floor would fill the roster with 100%-on-one-trade wallets.[/yellow]")

    if roster:
        t = Table(title="\nSharp roster", box=box.SIMPLE)
        t.add_column("Trader", style="cyan", max_width=24)
        t.add_column("Win", justify="right")
        t.add_column("7d PnL", justify="right")
        t.add_column("Closed", justify="right")
        for w in roster:
            t.add_row(w["pseudonym"][:24], f"{w['win_rate']:.0f}%",
                      f"${w['realized_pnl']:,.0f}", str(w["closed_positions"]))
        console.print(t)

    dropped = result.get("short_market_trades_dropped", 0)
    if dropped:
        console.print(f"[dim]{dropped} trade(s) dropped on markets resolving in under "
                      f"{result['min_duration_hours']:.0f}h - quoting bots, not forecasters[/dim]")

    suppressed = result.get("suppressed", [])
    if suppressed:
        console.print(f"\n[yellow]{len(suppressed)} cluster(s) suppressed as market "
                      f"making, not conviction:[/yellow]")
        for s_ in suppressed[:6]:
            console.print(f"    {s_['side']} {s_['outcome']:<6} {s_['title'][:44]:46s} "
                          f"[dim]{s_['suppressed_reason']}[/dim]")

    signals = result["signals"]
    if not signals:
        console.print("\n[yellow]No consensus found.[/yellow] Sharps are trading different "
                      "markets, or their recent activity does not overlap in time.")
        return

    console.print(f"\n[bold green]{len(signals)} SHARP CONSENSUS SIGNAL(S)[/bold green]")
    for s in signals:
        console.print(f"\n  [bold][SHARP CONSENSUS SIGNAL][/bold] {s['title'][:64]}")
        console.print(f"    {s['side']} {s['outcome']}  ·  {s['n_wallets']} wallets  ·  "
                      f"{s['n_trades']} trades over {s['span_hours']:.1f}h")
        console.print(f"    combined ${s['combined_usd']:,.0f} @ avg {s['avg_price']:.3f}  ·  "
                      f"aggregate win rate {s['aggregate_win_rate']:.0f}%  ·  "
                      f"combined 7d PnL ${s['aggregate_pnl']:,.0f}")
        console.print(f"    {', '.join(n[:18] for n in s['wallet_names'])}")
        if s["slug"]:
            console.print(f"    https://polymarket.com/event/{s['slug']}")

    if book is not None:
        b = book.summary()
        console.print(f"\n  [bold]Paper copy book[/bold]  cash ${b['cash']:,.2f}  ·  "
                      f"open {b['open_positions']}  ·  deployed ${b['deployed_usd']:,.2f}")
        if b["mean_slippage_pct"] is not None:
            console.print(f"    mean slippage vs sharp entry: {b['mean_slippage_pct']:+.2f}% "
                          f"[dim](we fill after them, never with them)[/dim]")
        if b.get("skipped_priced_in"):
            console.print(f"    [yellow]{b['skipped_priced_in']} signal(s) refused - "
                          f"price already moved >{MAX_ENTRY_APPRECIATION_PCT:.0f}% past "
                          f"the sharps' entry[/yellow]")
        if b["skipped_no_book"]:
            console.print(f"    [dim]{b['skipped_no_book']} signal(s) skipped - no live book[/dim]")
    console.print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket sharp trader consensus scanner")
    parser.add_argument("--min-win-rate", type=float, default=MIN_WIN_RATE)
    parser.add_argument("--min-pnl", type=float, default=MIN_REALIZED_PNL)
    parser.add_argument("--min-closed", type=int, default=MIN_CLOSED_POSITIONS,
                        help="Minimum closed positions - guards against 100%%-on-one-trade wallets")
    parser.add_argument("--wallets", type=int, default=MAX_WALLETS, help="Roster size cap")
    parser.add_argument("--window", type=float, default=CONSENSUS_WINDOW_HOURS,
                        help="Consensus window in hours (default: 3)")
    parser.add_argument("--min-wallets", type=int, default=MIN_CONSENSUS_WALLETS,
                        help="Distinct sharp wallets needed to fire (default: 2)")
    parser.add_argument("--min-duration", type=float, default=MIN_MARKET_DURATION_HOURS,
                        help="Ignore markets resolving sooner than this many hours (default: 24)")
    parser.add_argument("--paper", action="store_true", help="Simulate copy trades on signals")
    parser.add_argument("--min-edge", type=float, default=None,
                        help="Minimum expected gross edge as a decimal (e.g. 0.0308). Default: "
                             "the after-tax break-even from the Tax Reserve Agent")
    parser.add_argument("--size", type=float, default=COPY_SIZE_USD, help="USD per copy trade")
    args = parser.parse_args()

    console.print("[dim]Loading sharp roster and pulling recent activity...[/dim]")
    result = scan(min_win_rate=args.min_win_rate, min_pnl=args.min_pnl,
                  min_closed=args.min_closed, max_wallets=args.wallets,
                  window_hours=args.window, min_wallets=args.min_wallets,
                  min_duration_hours=args.min_duration)

    book = None
    if args.paper:
        gate = build_gate(args) if hasattr(args, "no_tax_gate") else TaxGate()
        min_edge = (args.min_edge if args.min_edge is not None
                    else gate.breakeven_gross_edge(MIN_AFTER_TAX_EDGE))
        console.print(f"[dim]Sharp win rates are Wilson-shrunk against their own sample "
                      f"size before the edge is computed (they were selected for having "
                      f"won).[/dim]")
        console.print(f"[dim]{gate.status_line()}[/dim]")
        console.print(f"[dim]After-tax break-even edge: {min_edge * 100:.2f}% - copies below "
                      f"this lose money after fees and tax.[/dim]")
        book = ConsensusPaperBook()
        book.load()
        for sig in result["signals"]:
            if sig["side"] == "BUY":          # only long copies; a SELL consensus needs inventory
                ask = current_ask(sig.get("asset"))
                sized = args.size
                # Same category derivation as bot orders, so a copy is subject to
                # the same measured drawdown clamps rather than the flat cap.
                category = categorise(f"{sig.get('slug', '')}-{sig.get('outcome', '')}")
                gated = gate.clamp_shares(args.size / ask, cost_per_share=ask,
                                          category=category, strategy="consensus_copy")                     if (gate.available and ask and 0 < ask < 1.0) else None
                if gated is not None and gated.gated:
                    sized = gated.approved_shares * ask
                if sized > 0:
                    book.copy(sig, size_usd=sized, ask=ask, min_edge=min_edge)
        book.save()

    render(result, book)


if __name__ == "__main__":
    main()
