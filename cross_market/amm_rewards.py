"""
Item 13, Phase 1 (Round 90): the Polymarket two-sided quoting engine and liquidity
rewards estimator - OFFLINE SIMULATOR AND PAPER INSTRUMENT. No orders, no sockets.

THE THESIS. A maker resting a bid and an ask around fair value earns the spread on
retail fills and, on markets with a rewards programme, a share of a daily USDC pool
scored by how close and how large its orders rest. The roadmap's "20-40% APY" is
unmeasured: it depends on pool sizes and on how much competing liquidity shares
the pool, and this module takes both as INPUTS. It can say "if the pool is X and
the competition Y, the reward is Z"; it cannot say what X and Y are.

WHAT THIS PHASE DOES.
  1. Quotes: Avellaneda-Stoikov shading. Reservation price r = fair - q*gamma*sigma^2*tau
     (long inventory shades both quotes down), half-spread from the risk term plus
     the fill-intensity term, clamped to the tick grid inside (0, 1), and optionally
     pulled inside the rewards window so both orders score.
  2. Rewards: the programme's order score ((v - s) / v)^2 * size for an order resting
     s from the midpoint inside the max spread v with at least the min size; both
     sides are needed in the 0.10-0.90 band (Q_min), one side suffices outside it;
     the daily pool is shared by Q share against competitor liquidity.
  3. Simulation: per-minute loop over a fair-value path; retail fills arrive Poisson
     with intensity A*exp(-k*distance); inventory, cash, spread PnL, mark-to-market and
     rewards accrue; results carry every assumption that produced them.
  4. Guardrails, fail-closed: HALT.flag refuses; an inventory limit makes quoting
     one-sided (only the reducing side); a volatility spike widens, a larger one
     pulls; an event window pulls; every pulled minute is counted with its reason.
  5. Fills are PAPER receipts (strategy polymarket_amm) under
     cross_market/data/paper_receipts. No live path exists.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

DEV_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HALT_FLAG = DEV_ROOT / "HALT.flag"
PAPER_RECEIPTS_DIR = Path(__file__).resolve().parent / "data" / "paper_receipts"
STRATEGY = "polymarket_amm"
TICK = 0.01
MINUTES_PER_DAY = 1440
BOTH_SIDES_BAND = (0.10, 0.90)                  # the programme requires two-sided quotes when the mid is in here
EXIT_HALTED = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _round_tick(price: float, tick: float = TICK) -> float:
    return round(round(price / tick) * tick, 6)


# ------------------------------------------------------------------ quoting (Avellaneda-Stoikov, shaded and clamped)

@dataclass
class QuoteParams:
    gamma: float = 0.1                          # risk aversion per share^2: 100 shares, sigma 0.005, tau 60 -> ~1.5 cents of shading
    sigma: float = 0.01                         # fair-value volatility per sqrt(minute), in price units
    horizon_min: float = 60.0                   # tau: minutes until the quote is re-evaluated as "end of session"
    k: float = 1.5                              # fill-intensity decay per cent of distance (see fill_intensity)
    arrival_a: float = 0.5                      # fills per minute at zero distance, per side
    size: float = 100.0                         # shares per quote
    min_half_spread: float = TICK               # never quote tighter than one tick each side
    tick: float = TICK
    rewards_max_spread: Optional[float] = None  # when set, quotes are pulled inside the window so they score
    vol_widen: float = 2.0                      # half-spread multiplier on a volatility spike
    vol_pull_multiple: float = 2.0              # spike beyond this multiple of the threshold pulls quotes
    inventory_limit: float = 500.0              # |inventory| at which the growing side stops quoting


@dataclass
class Quote:
    bid: Optional[float]
    ask: Optional[float]
    reservation: float
    half_spread: float
    size: float
    reason: str = "quoted"                      # or why a side / both are missing

    @property
    def two_sided(self) -> bool:
        return self.bid is not None and self.ask is not None


def reservation_price(fair: float, inventory: float, p: QuoteParams) -> float:
    return float(fair) - float(inventory) * p.gamma * p.sigma ** 2 * p.horizon_min


def optimal_half_spread(p: QuoteParams) -> float:
    """
    Avellaneda-Stoikov: half-spread = gamma*sigma^2*tau/2 + (1/gamma) ln(1 + gamma/k), with k
    the fill-intensity decay PER PRICE UNIT. `p.k` is per cent (see fill_intensity), so it is
    scaled by 1/tick here - with k per unit the second term is ~57 cents and every quote
    clamps to the edges (found by the first test run).
    """
    risk_term = 0.5 * p.gamma * p.sigma ** 2 * p.horizon_min
    k_per_unit = p.k / p.tick
    intensity_term = (1.0 / p.gamma) * math.log(1.0 + p.gamma / k_per_unit) if p.gamma > 0 and k_per_unit > 0 else 0.0
    return max(p.min_half_spread, risk_term + intensity_term)


def quote(fair: float, inventory: float, p: QuoteParams, vol_multiple: float = 1.0) -> Quote:
    """
    Both quotes around the reservation price, on the tick grid, inside (0, 1). Long
    inventory shades both down (the bid backs off, the ask invites selling); a
    volatility spike widens; the inventory limit removes the side that would grow it.
    """
    r = reservation_price(fair, inventory, p)
    half = optimal_half_spread(p) * max(1.0, float(vol_multiple))
    if p.rewards_max_spread is not None:
        half = min(half, max(p.min_half_spread, p.rewards_max_spread - p.tick))   # rest inside the window, not on its edge
    bid = _round_tick(min(r - half, fair - p.min_half_spread), p.tick)
    ask = _round_tick(max(r + half, fair + p.min_half_spread), p.tick)
    bid = max(p.tick, bid)
    ask = min(1.0 - p.tick, ask)
    if ask - bid < 2 * p.tick - 1e-9:
        ask = _round_tick(bid + 2 * p.tick, p.tick)
    # Re-clamp after widening: near the edges the minimum spread can push a quote out of (0, 1)
    # (fair 0.995 -> ask 1.00, found by the first test run); the edge wins and the other side yields.
    if ask > 1.0 - p.tick + 1e-9:
        ask = _round_tick(1.0 - p.tick, p.tick)
        bid = min(bid, _round_tick(ask - 2 * p.tick, p.tick))
    if bid < p.tick - 1e-9:
        bid = _round_tick(p.tick, p.tick)
        ask = max(ask, _round_tick(bid + 2 * p.tick, p.tick))
    reason = "quoted"
    bid_out: Optional[float] = bid
    ask_out: Optional[float] = ask
    if inventory >= p.inventory_limit:
        bid_out, reason = None, "inventory limit: long %.0f >= %.0f, bid withdrawn" % (inventory, p.inventory_limit)
    elif inventory <= -p.inventory_limit:
        ask_out, reason = None, "inventory limit: short %.0f, ask withdrawn" % (-inventory)
    return Quote(bid=bid_out, ask=ask_out, reservation=r, half_spread=half, size=p.size, reason=reason)


# ------------------------------------------------------------------ the rewards programme

@dataclass
class RewardsConfig:
    pool_per_day: float                         # USDC the market pays out per day (an INPUT, from the market's config)
    max_spread: float = 0.03                    # v: orders farther than this from the mid score zero
    min_size: float = 50.0                      # orders smaller than this score zero
    competitor_q: float = 1000.0                # the rest of the book's Q_min (an INPUT; competition is unknown)


def order_score(price: float, size: float, mid: float, cfg: RewardsConfig) -> float:
    """((v - s) / v)^2 * size inside the window and above the min size; 0 otherwise."""
    s = abs(float(price) - float(mid))
    v = float(cfg.max_spread)
    if size < cfg.min_size or v <= 0 or s > v:
        return 0.0
    return ((v - s) / v) ** 2 * float(size)


def q_min(bid: Optional[float], ask: Optional[float], size: float, mid: float, cfg: RewardsConfig) -> float:
    """Two-sided in the 0.10-0.90 band (min of the two sides); one side suffices outside it (max)."""
    q_bid = order_score(bid, size, mid, cfg) if bid is not None else 0.0
    q_ask = order_score(ask, size, mid, cfg) if ask is not None else 0.0
    lo, hi = BOTH_SIDES_BAND
    return min(q_bid, q_ask) if lo <= mid <= hi else max(q_bid, q_ask)


def reward_per_minute(my_q: float, cfg: RewardsConfig) -> float:
    total = my_q + max(0.0, cfg.competitor_q)
    if my_q <= 0 or total <= 0:
        return 0.0
    return cfg.pool_per_day / MINUTES_PER_DAY * (my_q / total)


# ------------------------------------------------------------------ the simulation

def fill_intensity(distance: float, p: QuoteParams) -> float:
    """Fills per minute for an order `distance` (price units) from fair: A * exp(-k * distance_in_cents)."""
    return p.arrival_a * math.exp(-p.k * max(0.0, float(distance)) / TICK)


def synthetic_fair_path(minutes: int, start: float = 0.50, sigma: float = 0.005, seed: int = 7,
                        jump_at: Optional[int] = None, jump: float = 0.0) -> List[float]:
    rng = random.Random(seed)
    path = [start]
    for i in range(1, minutes):
        step = rng.gauss(0.0, sigma) + (jump if jump_at is not None and i == jump_at else 0.0)
        path.append(min(0.99, max(0.01, path[-1] + step)))
    return path


@dataclass
class PaperFill:
    minute: int
    side: str                                   # "BUY" (our bid was hit) or "SELL" (our ask was lifted)
    price: float
    shares: float
    fair: float

    @property
    def spread_capture(self) -> float:
        return (self.fair - self.price) * self.shares if self.side == "BUY" else (self.price - self.fair) * self.shares


@dataclass
class SimResult:
    minutes: int
    minutes_quoted: int
    minutes_one_sided: int
    minutes_pulled: int
    pulled_reasons: Dict[str, int]
    fills: List[PaperFill]
    inventory: float
    max_abs_inventory: float
    cash: float
    spread_capture: float
    mark_to_market: float
    rewards: float
    final_fair: float
    assumptions: Dict[str, Any]

    @property
    def pnl(self) -> float:
        return self.cash + self.inventory * self.final_fair + self.rewards

    def to_dict(self) -> Dict[str, Any]:
        d = {k: v for k, v in asdict(self).items() if k != "fills"}
        d.update(fills=len(self.fills), pnl=round(self.pnl, 4), spread_capture=round(self.spread_capture, 4),
                 mark_to_market=round(self.mark_to_market, 4), rewards=round(self.rewards, 4), cash=round(self.cash, 4))
        return d


def rolling_sigma(path: Sequence[float], end: int, window: int) -> float:
    start = max(1, end - window + 1)
    diffs = [path[i] - path[i - 1] for i in range(start, end + 1)]
    if len(diffs) < 2:
        return 0.0
    mean = sum(diffs) / len(diffs)
    return math.sqrt(sum((d - mean) ** 2 for d in diffs) / (len(diffs) - 1))


def simulate(fair_path: Sequence[float], p: QuoteParams, cfg: Optional[RewardsConfig] = None, seed: int = 7,
             halt_path: Path = DEFAULT_HALT_FLAG, events: Sequence[Tuple[int, int]] = (), vol_window: int = 15,
             vol_threshold: Optional[float] = None, halted: Optional[Callable[[], bool]] = None) -> SimResult:
    """
    One minute per fair-value point. `events` are (start_minute, end_minute) windows in
    which quotes are pulled (a scheduled release). `vol_threshold` (price units per
    sqrt-minute) widens quotes when the rolling sigma exceeds it and pulls them past
    `vol_pull_multiple` x. HALT.flag (or `halted()`) refuses before the first minute.
    """
    rng = random.Random(seed)
    is_halted = halted or (lambda: Path(halt_path).exists())
    assumptions = {"quote_params": asdict(p), "rewards": asdict(cfg) if cfg else None, "seed": seed,
                   "events": [list(e) for e in events], "vol_window": vol_window, "vol_threshold": vol_threshold,
                   "fill_model": "Poisson, intensity A*exp(-k*cents) per side per minute, one fill of `size` when it arrives",
                   "mid_for_rewards": "fair value (a live book's mid may differ)", "maker_fee": 0.0}
    result = SimResult(minutes=len(fair_path), minutes_quoted=0, minutes_one_sided=0, minutes_pulled=0, pulled_reasons={},
                       fills=[], inventory=0.0, max_abs_inventory=0.0, cash=0.0, spread_capture=0.0, mark_to_market=0.0,
                       rewards=0.0, final_fair=float(fair_path[-1]) if fair_path else 0.0, assumptions=assumptions)
    if is_halted():
        result.pulled_reasons["HALT.flag present - refused"] = len(fair_path)
        result.minutes_pulled = len(fair_path)
        return result
    inventory = 0.0
    cash = 0.0
    for minute, fair in enumerate(fair_path):
        fair = float(fair)
        pulled: Optional[str] = None
        for start, end in events:
            if start <= minute <= end:
                pulled = "event window %d-%d" % (start, end)
                break
        vol_multiple = 1.0
        if pulled is None and vol_threshold:
            sigma_now = rolling_sigma(fair_path, minute, vol_window)
            if sigma_now > vol_threshold * p.vol_pull_multiple:
                pulled = "volatility spike (sigma %.4f > %.4f x %g)" % (sigma_now, vol_threshold, p.vol_pull_multiple)
            elif sigma_now > vol_threshold:
                vol_multiple = p.vol_widen
        if pulled is not None:
            result.minutes_pulled += 1
            result.pulled_reasons[pulled.split(" (")[0]] = result.pulled_reasons.get(pulled.split(" (")[0], 0) + 1
            continue
        q = quote(fair, inventory, p, vol_multiple=vol_multiple)
        if q.two_sided:
            result.minutes_quoted += 1
        else:
            result.minutes_one_sided += 1
        if cfg is not None:
            result.rewards += reward_per_minute(q_min(q.bid, q.ask, q.size, fair, cfg), cfg)
        if q.bid is not None and rng.random() < 1.0 - math.exp(-fill_intensity(fair - q.bid, p)):
            fill = PaperFill(minute, "BUY", q.bid, q.size, fair)
            inventory += q.size
            cash -= q.bid * q.size
            result.fills.append(fill)
            result.spread_capture += fill.spread_capture
        if q.ask is not None and rng.random() < 1.0 - math.exp(-fill_intensity(q.ask - fair, p)):
            fill = PaperFill(minute, "SELL", q.ask, q.size, fair)
            inventory -= q.size
            cash += q.ask * q.size
            result.fills.append(fill)
            result.spread_capture += fill.spread_capture
        result.max_abs_inventory = max(result.max_abs_inventory, abs(inventory))
    result.inventory = inventory
    result.cash = cash
    result.mark_to_market = cash + inventory * result.final_fair
    return result


# ------------------------------------------------------------------ Ruling R6: competitor Q from recorded books

def book_mid(book: Any) -> Optional[float]:
    """(best bid + best ask) / 2 - the live programme's midpoint, not the simulator's fair value."""
    if not book.bids or not book.asks:
        return None
    return (book.bids[0].price + book.asks[0].price) / 2.0


def book_q(book: Any, cfg: RewardsConfig, mid: Optional[float] = None) -> Dict[str, float]:
    """
    The whole book's programme score at one stamp: every resting level inside the window
    and above the min size, per side. The score is linear in size, so scoring a price
    level is exactly scoring the orders resting at it. This IS the competitor Q the
    simulator has to assume - measured, per stamp.
    """
    mid = book_mid(book) if mid is None else mid
    if mid is None:
        return {"mid": None, "q_bid": 0.0, "q_ask": 0.0, "q_min": 0.0, "levels_in_window": 0}
    q_bid = sum(order_score(l.price, l.size, mid, cfg) for l in book.bids)
    q_ask = sum(order_score(l.price, l.size, mid, cfg) for l in book.asks)
    lo, hi = BOTH_SIDES_BAND
    in_window = sum(1 for l in list(book.bids) + list(book.asks) if abs(l.price - mid) <= cfg.max_spread and l.size >= cfg.min_size)
    return {"mid": mid, "q_bid": q_bid, "q_ask": q_ask, "q_min": min(q_bid, q_ask) if lo <= mid <= hi else max(q_bid, q_ask),
            "levels_in_window": in_window}


def replay_rewards(books_dir: Path, cfg: RewardsConfig, size: float, offset: float,
                   now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Ruling R6: over every recorded stamp, measure the book's Q and the share a
    hypothetical two-sided quote of `size` at mid +/- `offset` would earn against it,
    with the pool rate as the one remaining INPUT. Returns per-stamp rows and a summary.
    """
    from cross_market.latency_sniper import _STAMP_RE, Book, _utc
    import json as _json
    rows: List[Dict[str, Any]] = []
    for path in sorted(Path(books_dir).glob("clob_*.json")):
        match = _STAMP_RE.match(path.name)
        if not match:
            continue
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
            book = Book.from_clob(match.group("token"), data, data.get("observed_at") or datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S_%f"))
        except Exception:                                   # noqa: BLE001
            continue
        if now is not None and book.observed_at > now:
            continue
        q = book_q(book, cfg)
        if q["mid"] is None:
            rows.append({"token": book.market, "observed_at": book.observed_at.isoformat(), "mid": None, "reason": "one-sided book"})
            continue
        my_bid, my_ask = _round_tick(q["mid"] - offset), _round_tick(q["mid"] + offset)
        my_q = q_min(my_bid, my_ask, size, q["mid"], cfg)
        share = my_q / (my_q + q["q_min"]) if (my_q + q["q_min"]) > 0 else 0.0
        rows.append({"token": book.market, "observed_at": book.observed_at.isoformat(), "mid": round(q["mid"], 4),
                     "book_q_bid": round(q["q_bid"], 2), "book_q_ask": round(q["q_ask"], 2), "book_q_min": round(q["q_min"], 2),
                     "levels_in_window": q["levels_in_window"], "my_bid": my_bid, "my_ask": my_ask, "my_q": round(my_q, 2),
                     "share": round(share, 6), "reward_per_day": round(cfg.pool_per_day * share, 4)})
    scored = [r for r in rows if r.get("mid") is not None]
    summary: Dict[str, Any] = {"stamps": len(rows), "scored": len(scored), "size": size, "offset": offset,
                               "pool_per_day": cfg.pool_per_day, "max_spread": cfg.max_spread, "min_size": cfg.min_size,
                               "pool_is_assumed": True}
    if scored:
        shares = [r["share"] for r in scored]
        qs = [r["book_q_min"] for r in scored]
        summary.update(share_mean=round(sum(shares) / len(shares), 6), share_min=round(min(shares), 6), share_max=round(max(shares), 6),
                       book_q_min_mean=round(sum(qs) / len(qs), 2), book_q_min_min=round(min(qs), 2), book_q_min_max=round(max(qs), 2),
                       reward_per_day_mean=round(cfg.pool_per_day * sum(shares) / len(shares), 4),
                       tokens=sorted({r["token"] for r in scored}))
    return {"rows": rows, "summary": summary}


def format_replay(result: Dict[str, Any]) -> str:
    s = result["summary"]
    lines = ["REWARDS REPLAY (Ruling R6) - %d stamp(s), %d scored; quote %g shares at mid +/- %.2f; window %.2f, min size %g"
             % (s["stamps"], s["scored"], s["size"], s["offset"], s["max_spread"], s["min_size"])]
    for r in result["rows"][:20]:
        if r.get("mid") is None:
            lines.append("  %s %s: %s" % (r["token"][:12], r["observed_at"][11:19], r.get("reason")))
            continue
        lines.append("  %s %s: mid %.3f · book Q bid %.0f / ask %.0f / min %.0f (%d level(s) in window) · my Q %.0f · share %.2f%% · $%.4f/day"
                     % (r["token"][:12], r["observed_at"][11:19], r["mid"], r["book_q_bid"], r["book_q_ask"], r["book_q_min"],
                        r["levels_in_window"], r["my_q"], r["share"] * 100, r["reward_per_day"]))
    if len(result["rows"]) > 20:
        lines.append("  ... %d more" % (len(result["rows"]) - 20))
    if s.get("scored"):
        lines.append("  MEASURED competitor Q_min: mean %.0f (min %.0f, max %.0f) · my share mean %.2f%% (%.2f%%-%.2f%%)"
                     % (s["book_q_min_mean"], s["book_q_min_min"], s["book_q_min_max"], s["share_mean"] * 100, s["share_min"] * 100, s["share_max"] * 100))
        lines.append("  reward/day at the ASSUMED pool $%.2f: mean $%.4f - the pool rate is the only input left (Ruling R5)"
                     % (s["pool_per_day"], s["reward_per_day_mean"]))
    lines.append("  offline replay of recorded books; places nothing.")
    return "\n".join(lines)


# ------------------------------------------------------------------ paper receipts

def record_paper_fills(result: SimResult, market: str, receipts_dir: Optional[Path] = None, writer=None,
                       stamp: Optional[datetime] = None) -> List[Path]:
    """One PAPER maker receipt per simulated fill, strategy polymarket_amm, under the paper folder only."""
    if writer is None:
        from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt as writer
    base = stamp or _now()
    written: List[Path] = []
    for fill in result.fills:
        try:
            path = writer(symbol=market, side=fill.side, quantity=round(fill.shares, 6), price=round(fill.price, 6),
                          strategy=STRATEGY, venue="polymarket", fee=0.0,
                          timestamp=(base + timedelta(minutes=fill.minute)).isoformat(),
                          imports_dir=Path(receipts_dir or PAPER_RECEIPTS_DIR),
                          extra_notes="paper:1; strategy:%s; maker:1; minute:%d; fair:%.4f; capture:%.4f"
                                      % (STRATEGY, fill.minute, fill.fair, fill.spread_capture))
        except Exception as exc:                            # noqa: BLE001
            print("[WARN] paper receipt not written (%s: %s)" % (type(exc).__name__, exc))
            continue
        if path:
            written.append(Path(path))
    return written


# ------------------------------------------------------------------ CLI

def format_result(result: SimResult, market: str) -> str:
    lines = ["POLYMARKET AMM SIMULATION (Item 13, Phase 1, PAPER) - %s over %d minute(s)" % (market, result.minutes)]
    if result.pulled_reasons.get("HALT.flag present - refused"):
        lines.append("  REFUSED: HALT.flag present")
        return "\n".join(lines)
    lines.append("  quoted two-sided %d min · one-sided %d · pulled %d %s" % (
        result.minutes_quoted, result.minutes_one_sided, result.minutes_pulled,
        ("(%s)" % ", ".join("%s: %d" % kv for kv in result.pulled_reasons.items())) if result.pulled_reasons else ""))
    lines.append("  fills %d · final inventory %+.0f (max |%.0f|) · cash %+.2f · mark-to-market %+.2f"
                 % (len(result.fills), result.inventory, result.max_abs_inventory, result.cash, result.mark_to_market))
    lines.append("  spread capture %+.2f · rewards %+.2f · PnL incl. rewards %+.2f" % (result.spread_capture, result.rewards, result.pnl))
    rw = result.assumptions.get("rewards")
    if rw:
        lines.append("  rewards ASSUMED: pool $%.2f/day, window %.2f, min size %.0f, competitor Q %.0f - inputs, not measurements"
                     % (rw["pool_per_day"], rw["max_spread"], rw["min_size"], rw["competitor_q"]))
    lines.append("  offline simulator: synthetic or supplied fair path, Poisson retail fills; places nothing.")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Item 13 Phase 1 - Polymarket AMM + rewards simulator (offline, paper)")
    parser.add_argument("--market", default="SYNTHETIC")
    parser.add_argument("--fair-path", type=Path, default=None, help="JSON list of per-minute fair values")
    parser.add_argument("--minutes", type=int, default=MINUTES_PER_DAY, help="synthetic path length (default one day)")
    parser.add_argument("--start", type=float, default=0.50)
    parser.add_argument("--path-sigma", type=float, default=0.003)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--gamma", type=float, default=0.5)
    parser.add_argument("--sigma", type=float, default=0.005)
    parser.add_argument("--horizon", type=float, default=60.0)
    parser.add_argument("--k", type=float, default=1.5)
    parser.add_argument("--arrival", type=float, default=0.3)
    parser.add_argument("--size", type=float, default=100.0)
    parser.add_argument("--inventory-limit", type=float, default=500.0)
    parser.add_argument("--pool", type=float, default=None, help="rewards pool USDC/day (enables the estimator)")
    parser.add_argument("--max-spread", type=float, default=0.03)
    parser.add_argument("--min-size", type=float, default=50.0)
    parser.add_argument("--competitor-q", type=float, default=1000.0)
    parser.add_argument("--rewards-window-quotes", action="store_true", help="pull quotes inside the rewards window")
    parser.add_argument("--event", action="append", default=[], help="start-end minutes to pull quotes, e.g. 600-620")
    parser.add_argument("--vol-threshold", type=float, default=None)
    parser.add_argument("--halt-flag", type=Path, default=None)
    parser.add_argument("--paper", action="store_true")
    parser.add_argument("--receipts-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--replay-books", type=Path, default=None,
                        help="Ruling R6: measure competitor Q and a hypothetical quote's share over recorded CLOB stamps")
    parser.add_argument("--quote-offset", type=float, default=0.01, help="with --replay-books: my quotes at mid +/- this")
    args = parser.parse_args(argv)
    if args.replay_books:
        if args.pool is None:
            parser.error("--replay-books needs --pool (the daily rate; an INPUT until Ruling R5 records it)")
        cfg = RewardsConfig(pool_per_day=args.pool, max_spread=args.max_spread, min_size=args.min_size)
        result = replay_rewards(args.replay_books, cfg, size=args.size, offset=args.quote_offset)
        print(json.dumps(result, indent=2, default=str) if args.json else format_replay(result))
        return 0 if result["summary"]["scored"] else 1
    if args.fair_path:
        path = [float(x) for x in json.loads(Path(args.fair_path).read_text(encoding="utf-8"))]
    else:
        path = synthetic_fair_path(args.minutes, start=args.start, sigma=args.path_sigma, seed=args.seed)
    cfg = RewardsConfig(pool_per_day=args.pool, max_spread=args.max_spread, min_size=args.min_size,
                        competitor_q=args.competitor_q) if args.pool is not None else None
    params = QuoteParams(gamma=args.gamma, sigma=args.sigma, horizon_min=args.horizon, k=args.k, arrival_a=args.arrival,
                         size=args.size, inventory_limit=args.inventory_limit,
                         rewards_max_spread=args.max_spread if (cfg and args.rewards_window_quotes) else None)
    events = []
    for spec in args.event:
        start, _, end = spec.partition("-")
        events.append((int(start), int(end or start)))
    result = simulate(path, params, cfg, seed=args.seed, halt_path=Path(args.halt_flag or DEFAULT_HALT_FLAG),
                      events=events, vol_threshold=args.vol_threshold)
    if args.paper and result.fills and not result.pulled_reasons.get("HALT.flag present - refused"):
        written = record_paper_fills(result, args.market, receipts_dir=args.receipts_dir)
        print("[PAPER] %d receipt(s) -> %s" % (len(written), args.receipts_dir or PAPER_RECEIPTS_DIR))
    print(json.dumps(result.to_dict(), indent=2, default=str) if args.json else format_result(result, args.market))
    return EXIT_HALTED if result.pulled_reasons.get("HALT.flag present - refused") else 0


if __name__ == "__main__":
    sys.exit(main())
