"""
Item 12, Phase 1 (Round 87): the Polymarket breaking-news / oracle latency sniper -
OFFLINE ENGINE AND MEASUREMENT INSTRUMENT. No orders, no sockets except one
read-only GET when the operator asks it to record order books.

THE THESIS. When a scheduled number prints (a Fed decision, a CPI release) or a
race is called, some limit orders on the matching Polymarket markets rest at
pre-news prices for a few seconds. Whoever resolves the market from the number
first can take those orders at a near-certain edge.

WHAT THIS PHASE DOES.
  1. A pre-registered RULE maps an event payload to ONE market's outcome (YES/NO)
     with no interpretation at run time. A market without a rule is never touched;
     an event kind a rule does not know is ignored.
  2. A BOOK (a CLOB depth snapshot) is walked from the best price outward. Each
     level is taken only while the outcome's confidence clears the Tax Reserve
     Agent's after-tax BREAKEVEN win probability at that level's fee-adjusted odds.
  3. Size is capped by quarter-Kelly of the safe deployable bankroll and by the
     hook's per-order ceiling; the smaller wins.
  4. HALT.flag refuses everything; confidence under 0.99 refuses everything; a book
     older than `max_book_age_s` is skipped (the orders are probably gone).
  5. Fills are PAPER receipts under cross_market/data/paper_receipts tagged
     strategy `latency_sniper`. There is no live path in this module at all.

WHAT IT DOES NOT CLAIM. The roadmap's "10-50% per event" is unmeasured. The first
job of this engine is to measure it: `--record` stamps CLOB depth for the watched
tokens around a scheduled release, and a replay of the rules against those stamps
says what was actually there to take, and for how long. Round 94: `--survival-curve`
replays the rules against every stamp of a `--record-loop` drill and reports that "for
how long" second by second - the pre-print baseline, the first change, the seconds to
half, a tenth and nothing, and the dollar-seconds of fillable notional after the print.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

DEV_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HALT_FLAG = DEV_ROOT / "HALT.flag"
PAPER_RECEIPTS_DIR = Path(__file__).resolve().parent / "data" / "paper_receipts"
DEFAULT_BOOKS_DIR = Path(__file__).resolve().parent / "data" / "clob_books"
SAMPLE_RULES = Path(__file__).resolve().parent / "experiments" / "sniper_rules.sample.json"
CLOB_BOOK_URL = "https://clob.polymarket.com/book?token_id=%s"

STRATEGY = "latency_sniper"
MIN_CONFIDENCE = 0.99
MAX_BOOK_AGE_S = 10.0
KELLY_FRACTION = 0.25
NOMINAL_BANKROLL = 1_000.0                      # --assume-defaults only: sizes are notional, the verdict is not
EXIT_HALTED = 3
OPS: Dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
    "in": lambda a, b: a in (b if isinstance(b, (list, tuple, set)) else [b]),
}
_STAMP_RE = re.compile(r"^clob_(?P<token>[^_]+)_(?P<stamp>\d{8}T\d{6}_\d{6})Z\.json$")


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ events and rules

@dataclass
class Event:
    kind: str
    payload: Dict[str, Any]
    source: str
    confidence: float
    observed_at: datetime

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(kind=str(data["kind"]).strip().lower(), payload=dict(data.get("payload") or {}),
                   source=str(data.get("source") or "unknown"), confidence=float(data.get("confidence") or 0.0),
                   observed_at=_utc(data.get("observed_at") or _now()))


@dataclass
class Rule:
    """`market` resolves to `outcome_if_true` when payload[field] <op> value, to the other side otherwise."""
    market: str
    kind: str
    field: str
    op: str
    value: Any
    outcome_if_true: str = "YES"
    label: str = ""

    def __post_init__(self):
        self.kind = str(self.kind).strip().lower()
        self.outcome_if_true = str(self.outcome_if_true).strip().upper()
        if self.op not in OPS:
            raise ValueError("rule %r: unknown op %r (one of %s)" % (self.label or self.market, self.op, sorted(OPS)))
        if self.outcome_if_true not in ("YES", "NO"):
            raise ValueError("rule %r: outcome_if_true must be YES or NO" % (self.label or self.market))

    def resolve(self, event: Event) -> Optional[str]:
        """YES / NO for this market given the event, or None when the event says nothing about it."""
        if event.kind != self.kind or self.field not in event.payload:
            return None
        actual = event.payload[self.field]
        sample = self.value[0] if isinstance(self.value, (list, tuple)) and self.value else self.value
        if isinstance(sample, (int, float)) and not isinstance(sample, bool):
            # A numeric rule needs a number. "twenty-five" is not -25 and must not resolve to NO either:
            # a payload of the wrong shape says nothing, and nothing is what gets traded on it.
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                return None
        try:
            hit = OPS[self.op](actual, self.value)
        except TypeError:
            return None
        if hit:
            return self.outcome_if_true
        return "NO" if self.outcome_if_true == "YES" else "YES"


def load_rules(path: Path) -> List[Rule]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("rules") if isinstance(data, dict) else data
    return [Rule(**{k: v for k, v in item.items() if k in Rule.__dataclass_fields__}) for item in (items or [])]


# ------------------------------------------------------------------ order books

@dataclass
class Level:
    price: float
    size: float                                     # shares


@dataclass
class Book:
    market: str
    bids: List[Level]                               # best (highest) first
    asks: List[Level]                               # best (lowest) first
    observed_at: datetime
    fee_rate: float = 0.0
    neg_risk: bool = False                          # Ruling R4: a multi-outcome event sharing collateral

    @classmethod
    def from_clob(cls, market: str, payload: Dict[str, Any], observed_at: Any, fee_rate: float = 0.0,
                  neg_risk: Optional[bool] = None) -> "Book":
        """The CLOB /book shape: {"bids": [{"price": "0.45", "size": "100"}], "asks": [...]}; junk levels skipped."""
        def levels(rows: Any) -> List[Level]:
            out = []
            for row in rows or []:
                try:
                    price, size = float(row["price"]), float(row["size"])
                except (TypeError, KeyError, ValueError):
                    continue
                if 0.0 < price < 1.0 and size > 0:
                    out.append(Level(price, size))
            return out
        bids = sorted(levels(payload.get("bids")), key=lambda l: -l.price)
        asks = sorted(levels(payload.get("asks")), key=lambda l: l.price)
        flag = payload.get("neg_risk") if neg_risk is None else neg_risk
        return cls(market=str(market), bids=bids, asks=asks, observed_at=_utc(observed_at), fee_rate=float(fee_rate),
                   neg_risk=bool(flag))

    def age_s(self, now: datetime) -> float:
        return (now - self.observed_at).total_seconds()


def stamp_name(token: str, when: datetime) -> str:
    return "clob_%s_%sZ.json" % (token, when.strftime("%Y%m%dT%H%M%S_%f"))


def stamp_books(tokens: Iterable[str], out_dir: Path, fetch: Callable[[str], Dict[str, Any]],
                now: Optional[datetime] = None, fee_rate: float = 0.0) -> List[Path]:
    """The measurement instrument: one stamped snapshot per token; a failed fetch is skipped, never fatal."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = now or _now()
    written: List[Path] = []
    for token in tokens:
        token = str(token).strip()
        if not token:
            continue
        try:
            payload = fetch(token)
        except Exception as exc:                            # noqa: BLE001
            print("[RECORD] %s: fetch failed (%s: %s)" % (token, type(exc).__name__, exc))
            continue
        if not isinstance(payload, dict):
            continue
        path = out_dir / stamp_name(token, now)
        # The live /book also carries min_order_size, neg_risk, last_trade_price and a book hash (seen
        # live, Round 87): kept on the stamp as provenance for the replay; the parser reads only bids/asks.
        extra = {key: payload.get(key) for key in ("market", "asset_id", "hash", "last_trade_price", "min_order_size", "neg_risk")
                 if key in payload}
        path.write_text(json.dumps(dict(extra, token_id=token, observed_at=now.isoformat(), fee_rate=fee_rate,
                                        bids=payload.get("bids") or [], asks=payload.get("asks") or [])), encoding="utf-8")
        written.append(path)
    return written


FETCH_HEADERS = {"User-Agent": "Mozilla/5.0 (PentaDesk latency_sniper recorder)", "Accept": "application/json"}


def default_fetch(token: str, timeout: float = 5.0) -> Dict[str, Any]:
    """
    The only network call in this module: a read-only GET of the public CLOB book.
    Cloudflare answers the default Python client with 403 / error 1010 (found live,
    Round 87); a browser-style User-Agent gets the book.
    """
    import urllib.request
    request = urllib.request.Request(CLOB_BOOK_URL % token, headers=FETCH_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


RATE_LIMIT_BACKOFF_S = 5.0                       # after an HTTP 429: wait this long per consecutive limited poll, capped
RATE_LIMIT_BACKOFF_MAX_S = 30.0


def record_loop(tokens: Sequence[str], out_dir: Path, fetch: Callable[[str], Dict[str, Any]], interval: float = 1.0,
                duration: float = 420.0, clock: Optional[Callable[[], float]] = None,
                sleep: Optional[Callable[[float], None]] = None, wall: Optional[Callable[[], datetime]] = None,
                halt_path: Path = DEFAULT_HALT_FLAG, fee_rate: float = 0.0, log: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """
    Ruling R2 (Round 93): stamp every token's book once per `interval` seconds for `duration`
    seconds - T-2 min to T+5 min around a release at the defaults. Sleeps interval minus the
    fetch time; stops cleanly at the duration, on HALT.flag, or on Ctrl-C. An HTTP 429 is
    counted and answered with a growing pause, never a crash. Read-only GETs only.
    """
    tick = clock or time.monotonic
    pause = sleep or time.sleep
    now_wall = wall or _now
    log = log or print                          # resolved at call time, never bound at import (Rounds 77-80)
    tokens = [str(t).strip() for t in tokens if str(t).strip()]
    stats: Dict[str, Any] = {"polls": 0, "stamps": 0, "failures": 0, "rate_limited": 0, "seconds": 0.0,
                             "stopped": "duration", "interval": float(interval), "duration": float(duration)}
    limited = {"count": 0}

    def guarded(token: str) -> Dict[str, Any]:
        try:
            return fetch(token)
        except Exception as exc:                            # noqa: BLE001 - classify, then let stamp_books skip it
            if getattr(exc, "code", None) == 429:
                limited["count"] += 1
            raise
    start = tick()
    try:
        while tick() - start < duration:
            if Path(halt_path).exists():
                log("[RECORD] HALT.flag present at %s - stopping" % halt_path)
                stats["stopped"] = "halt"
                break
            t0 = tick()
            before = limited["count"]
            written = stamp_books(tokens, out_dir, guarded, now=now_wall(), fee_rate=fee_rate)
            stats["polls"] += 1
            stats["stamps"] += len(written)
            stats["failures"] += len(tokens) - len(written)
            if limited["count"] > before:
                stats["rate_limited"] += 1
                backoff = min(RATE_LIMIT_BACKOFF_MAX_S, RATE_LIMIT_BACKOFF_S * stats["rate_limited"])
                log("[RECORD] rate limited (HTTP 429) - backing off %.0fs" % backoff)
                pause(backoff)
                continue
            pause(max(0.0, float(interval) - (tick() - t0)))
    except KeyboardInterrupt:
        stats["stopped"] = "interrupt"
        log("[RECORD] interrupted")
    stats["seconds"] = round(tick() - start, 2)
    log("[RECORD] done: %d poll(s), %d stamp(s), %d failure(s), %d rate-limited, %.0fs, stopped by %s"
        % (stats["polls"], stats["stamps"], stats["failures"], stats["rate_limited"], stats["seconds"], stats["stopped"]))
    return stats


def load_books(books_dir: Path, now: Optional[datetime] = None) -> Dict[str, Book]:
    """The newest stamped book per token observed at or before `now`; unreadable stamps are skipped."""
    now = now or _now()
    best: Dict[str, Tuple[datetime, Book]] = {}
    try:
        files = list(Path(books_dir).glob("clob_*.json"))
    except Exception:                                       # noqa: BLE001
        return {}
    for path in files:
        match = _STAMP_RE.match(path.name)
        if not match:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            observed = _utc(data.get("observed_at") or datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S_%f"))
            book = Book.from_clob(match.group("token"), data, observed, fee_rate=float(data.get("fee_rate") or 0.0))
        except Exception:                                   # noqa: BLE001
            continue
        if book.observed_at > now:
            continue
        if book.market not in best or book.observed_at > best[book.market][0]:
            best[book.market] = (book.observed_at, book)
    return {token: book for token, (_, book) in best.items()}


# ------------------------------------------------------------------ economics (the Tax Reserve Agent's, injectable)

def net_payoff_per_share(price: float, fee_rate: float) -> float:
    """A winning share pays 1; the venue's fee is taken on the profit (1 - price)."""
    return 1.0 - float(fee_rate) * (1.0 - float(price))


def effective_odds(price: float, fee_rate: float) -> float:
    return net_payoff_per_share(price, fee_rate) / float(price)


def hook_economics(hook: Any) -> Tuple[Callable[[float], float], Callable[[float, float], float]]:
    """(breakeven(odds) -> win probability, cap(win_prob, odds) -> notional) from the Tax Reserve Agent hook."""
    def breakeven(odds: float) -> float:
        return float(hook.after_tax_edge_hurdle(decimal_odds=odds)["breakeven_win_probability"])

    def cap(win_prob: float, odds: float) -> float:
        kelly = max(0.0, float(hook.after_tax_kelly_fraction(win_prob, odds)))
        return max(0.0, min(KELLY_FRACTION * kelly * float(hook.get_safe_bankroll()), float(hook.max_position_size())))
    return breakeven, cap


def assumed_economics(bankroll: float = NOMINAL_BANKROLL) -> Tuple[Callable[[float], float], Callable[[float, float], float]]:
    """No tax, nominal bankroll: for offline research when the ledger is absent. Sizes are notional."""
    def breakeven(odds: float) -> float:
        return 1.0 / float(odds)

    def cap(win_prob: float, odds: float) -> float:
        b = float(odds) - 1.0
        kelly = (win_prob * b - (1.0 - win_prob)) / b if b > 0 else 0.0
        return max(0.0, KELLY_FRACTION * kelly * float(bankroll))
    return breakeven, cap


# ------------------------------------------------------------------ the evaluation

@dataclass
class Fill:
    price: float
    shares: float
    odds: float
    breakeven: float
    edge_per_share: float                           # confidence * net payoff - price

    @property
    def notional(self) -> float:
        return self.price * self.shares


@dataclass
class Opportunity:
    market: str
    rule: str
    outcome: str
    side: str                                       # BUY_YES (lift asks) or BUY_NO (hit YES bids)
    fills: List[Fill]
    cap_notional: float
    capped_by: str                                  # "cap" | "depth" | "hurdle"
    book_age_s: float
    fee_rate: float

    @property
    def shares(self) -> float:
        return sum(f.shares for f in self.fills)

    @property
    def notional(self) -> float:
        return sum(f.notional for f in self.fills)

    @property
    def expected_profit(self) -> float:
        return sum(f.edge_per_share * f.shares for f in self.fills)

    @property
    def vwap(self) -> float:
        return self.notional / self.shares if self.shares else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"market": self.market, "rule": self.rule, "outcome": self.outcome, "side": self.side,
                "shares": round(self.shares, 4), "notional": round(self.notional, 2), "vwap": round(self.vwap, 4),
                "expected_profit": round(self.expected_profit, 2), "cap_notional": round(self.cap_notional, 2),
                "capped_by": self.capped_by, "book_age_s": round(self.book_age_s, 2), "fee_rate": self.fee_rate,
                "fills": [asdict(f) for f in self.fills]}


def walk_book(levels: Sequence[Level], outcome: str, confidence: float, fee_rate: float,
              breakeven: Callable[[float], float], cap: Callable[[float, float], float]) -> Tuple[List[Fill], float, str]:
    """
    Take levels from the best outward while confidence clears the after-tax breakeven at
    each level's fee-adjusted odds; stop at the cap (quarter-Kelly at the best level's
    odds, or the hook's ceiling). For a NO outcome the YES bids are hit: buying NO at
    (1 - bid) is the same trade, so the level's price for the maths is (1 - bid).
    """
    fills: List[Fill] = []
    cap_notional = 0.0
    stopped = "depth"
    remaining = None
    for level in levels:
        price = level.price if outcome == "YES" else 1.0 - level.price
        odds = effective_odds(price, fee_rate)
        be = breakeven(odds)
        if confidence < be:
            stopped = "hurdle"
            break
        if remaining is None:
            cap_notional = cap(confidence, odds)
            remaining = cap_notional
        if remaining <= 0:
            stopped = "cap"
            break
        take = min(level.size, remaining / price)
        fills.append(Fill(price=price, shares=take, odds=odds, breakeven=be,
                          edge_per_share=confidence * net_payoff_per_share(price, fee_rate) - price))
        remaining -= take * price
        if take < level.size:
            stopped = "cap"
            break
    return fills, cap_notional, stopped


def evaluate(event: Event, rules: Sequence[Rule], books: Dict[str, Book], breakeven: Callable[[float], float],
             cap: Callable[[float, float], float], now: Optional[datetime] = None, halt_path: Path = DEFAULT_HALT_FLAG,
             min_confidence: float = MIN_CONFIDENCE, max_book_age_s: float = MAX_BOOK_AGE_S) -> Dict[str, Any]:
    """Every reason to refuse is checked first; the result says what was taken, what was skipped, and why."""
    now = now or _now()
    out: Dict[str, Any] = {"event": {"kind": event.kind, "source": event.source, "confidence": event.confidence,
                                     "observed_at": event.observed_at.isoformat()},
                           "checked_at": now.isoformat(), "halted": False, "refused": None,
                           "opportunities": [], "skipped": []}
    if Path(halt_path).exists():
        out["halted"] = True
        out["refused"] = "HALT.flag present at %s" % halt_path
        return out
    if event.confidence < min_confidence:
        out["refused"] = "confidence %.3f < %.2f - unverified or ambiguous news is never traded" % (event.confidence, min_confidence)
        return out
    for rule in rules:
        outcome = rule.resolve(event)
        if outcome is None:
            continue
        book = books.get(rule.market)
        label = rule.label or rule.market
        if book is None:
            out["skipped"].append({"market": rule.market, "rule": label, "reason": "no book snapshot"})
            continue
        age = book.age_s(now)
        if age < 0 or age > max_book_age_s:
            out["skipped"].append({"market": rule.market, "rule": label, "reason": "book stale (age %.1fs > %.0fs)" % (age, max_book_age_s)})
            continue
        if outcome == "NO" and book.neg_risk:
            # Ruling R4 (Round 88): on a neg_risk event the outcomes share collateral, so hitting YES bids is
            # not the atomic "buy NO" it is on a standalone market. Phase 1 lifts YES asks on the winning
            # outcome token only; the NO side of neg_risk markets waits for Phase 2.
            out["skipped"].append({"market": rule.market, "rule": label,
                                   "reason": "neg_risk market: NO side deferred to Phase 2 (Ruling R4); only BUY_YES on the winning outcome"})
            continue
        levels = book.asks if outcome == "YES" else book.bids
        fills, cap_notional, capped_by = walk_book(levels, outcome, event.confidence, book.fee_rate, breakeven, cap)
        if not fills:
            out["skipped"].append({"market": rule.market, "rule": label,
                                   "reason": "no level clears the hurdle" if capped_by == "hurdle" else "no depth"})
            continue
        out["opportunities"].append(Opportunity(market=rule.market, rule=label, outcome=outcome,
                                                side="BUY_YES" if outcome == "YES" else "BUY_NO", fills=fills,
                                                cap_notional=cap_notional, capped_by=capped_by, book_age_s=age,
                                                fee_rate=book.fee_rate))
    return out


# ------------------------------------------------------------------ Option 2 (Round 92): what a resting book would give a sniper

def depth_report(book: Book, outcome: str, confidence: float, breakeven: Callable[[float], float],
                 now: Optional[datetime] = None, honour_r4: bool = True) -> Dict[str, Any]:
    """
    Level by level, what the resting book would hand a sniper that knew `outcome` with
    `confidence`: each level's price (for NO, 1 - bid), fee-adjusted odds, the after-tax
    breakeven at those odds, whether it clears, the edge per share, and the cumulative
    fillable shares, notional and VWAP. No cap is applied - this is the upper bound the
    book offers, before anyone pulls. Levels are ordered best-first, so the first level
    that fails ends the walk. A NO outcome on a neg_risk book is deferred (Ruling R4).
    """
    now = now or _now()
    side = "BUY_YES" if outcome == "YES" else "BUY_NO"
    out: Dict[str, Any] = {"market": book.market, "outcome": outcome, "side": side, "confidence": confidence,
                           "fee_rate": book.fee_rate, "neg_risk": book.neg_risk, "book_age_s": round(book.age_s(now), 1),
                           "deferred": None, "levels": [], "levels_clearing": 0, "fillable_shares": 0.0,
                           "fillable_notional": 0.0, "vwap": None, "expected_profit": 0.0, "best_price": None}
    if outcome == "NO" and book.neg_risk and honour_r4:
        out["deferred"] = "neg_risk market: NO side deferred to Phase 2 (Ruling R4)"
        return out
    cum_shares = 0.0
    cum_notional = 0.0
    for level in (book.asks if outcome == "YES" else book.bids):
        price = level.price if outcome == "YES" else 1.0 - level.price
        odds = effective_odds(price, book.fee_rate)
        be = breakeven(odds)
        if confidence < be:
            out["levels"].append({"price": round(price, 4), "size": level.size, "odds": round(odds, 4), "breakeven": round(be, 4),
                                  "clears": False})
            break
        edge = confidence * net_payoff_per_share(price, book.fee_rate) - price
        cum_shares += level.size
        cum_notional += price * level.size
        out["levels"].append({"price": round(price, 4), "size": level.size, "notional": round(price * level.size, 2),
                              "odds": round(odds, 4), "breakeven": round(be, 4), "clears": True,
                              "edge_per_share": round(edge, 4), "cum_shares": round(cum_shares, 2),
                              "cum_notional": round(cum_notional, 2), "vwap": round(cum_notional / cum_shares, 4)})
        out["expected_profit"] += edge * level.size
    clearing = [l for l in out["levels"] if l["clears"]]
    out.update(levels_clearing=len(clearing), fillable_shares=round(cum_shares, 2), fillable_notional=round(cum_notional, 2),
               vwap=round(cum_notional / cum_shares, 4) if cum_shares else None,
               expected_profit=round(out["expected_profit"], 2), best_price=clearing[0]["price"] if clearing else None)
    return out


def format_depth(reports: Sequence[Dict[str, Any]], economics_label: str) -> str:
    lines = ["DEPTH REPORT (Option 2) - what each recorded book would hand a sniper that knew the outcome; economics: %s" % economics_label]
    for r in reports:
        head = "  %s %s %s (book %.0fs old%s)" % (r["market"][:14], r["side"], "conf %.3f" % r["confidence"], r["book_age_s"],
                                                   ", neg_risk" if r["neg_risk"] else "")
        if r["deferred"]:
            lines.append(head + ": " + r["deferred"])
            continue
        if not r["levels_clearing"]:
            first = r["levels"][0] if r["levels"] else None
            lines.append(head + ": nothing clears" + (" (best %.2f, breakeven %.4f)" % (first["price"], first["breakeven"]) if first else " (empty side)"))
            continue
        lines.append(head + ": %d level(s) clear · fillable %.0f shares / $%.2f · vwap %.4f · best %.2f · expected profit $%.2f"
                     % (r["levels_clearing"], r["fillable_shares"], r["fillable_notional"], r["vwap"], r["best_price"], r["expected_profit"]))
        for l in r["levels"][:4]:
            if l["clears"]:
                lines.append("      %.2f x %.0f  odds %.3f  breakeven %.4f  edge/share %+.4f  cum $%.2f" % (
                    l["price"], l["size"], l["odds"], l["breakeven"], l["edge_per_share"], l["cum_notional"]))
    lines.append("  upper bound before anyone pulls; no cap applied; offline replay of recorded books; places nothing.")
    return "\n".join(lines)


# ------------------------------------------------------------------ Round 94: the survival curve - how long the edge lasts after the print

@dataclass
class Stamp:
    token: str
    observed_at: datetime
    book: Book
    book_hash: str = ""                             # the CLOB's own book hash when the stamp carries one
    name: str = ""

    def fingerprint(self) -> str:
        """The CLOB hash when present, else the levels themselves: any difference means the book moved."""
        if self.book_hash:
            return self.book_hash
        return repr([(l.price, l.size) for l in self.book.asks] + [(l.price, l.size) for l in self.book.bids])


def load_stamp_series(books_dir: Path, tokens: Optional[Iterable[str]] = None) -> List[Stamp]:
    """Every readable stamp under books_dir - not just the newest per token - oldest first; junk skipped."""
    wanted = {str(t).strip() for t in tokens} if tokens else None
    out: List[Stamp] = []
    try:
        files = list(Path(books_dir).glob("clob_*.json"))
    except Exception:                                       # noqa: BLE001
        return []
    for path in files:
        match = _STAMP_RE.match(path.name)
        if not match or (wanted is not None and match.group("token") not in wanted):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            observed = _utc(data.get("observed_at") or datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S_%f"))
            book = Book.from_clob(match.group("token"), data, observed, fee_rate=float(data.get("fee_rate") or 0.0))
        except Exception:                                   # noqa: BLE001
            continue
        out.append(Stamp(token=match.group("token"), observed_at=observed, book=book, book_hash=str(data.get("hash") or ""),
                         name=path.name))
    out.sort(key=lambda st: (st.observed_at, st.token))
    return out


def bucket_latest(stamps: Sequence[Stamp], anchor: datetime, step_s: float) -> List[Stamp]:
    """With a step, the last stamp inside each step-wide bucket measured from the anchor; step <= 0 keeps every stamp."""
    if step_s <= 0:
        return list(stamps)
    kept: Dict[Tuple[str, int], Stamp] = {}
    for st in stamps:                                       # oldest first, so the last write in a bucket wins
        kept[(st.token, int((st.observed_at - anchor).total_seconds() // step_s))] = st
    return sorted(kept.values(), key=lambda st: (st.observed_at, st.token))


def survival_summary(series: Sequence[Dict[str, Any]], step_s: float) -> Dict[str, Any]:
    """
    The curve in five numbers: the pre-print baseline (the last stamp before the event), the
    first post-print second the book differed from the stamp before it, the first second the
    fillable notional fell to half and to a tenth of the baseline, the first second nothing
    cleared, and the dollar-seconds of fillable notional after the print (size x survival).
    """
    pre = [r for r in series if r["delta_s"] < 0]
    post = [r for r in series if r["delta_s"] >= 0]
    base_row = pre[-1] if pre else (post[0] if post else None)
    baseline = base_row["fillable_notional"] if base_row else 0.0

    def first(pred: Callable[[Dict[str, Any]], bool]) -> Optional[float]:
        for r in post:
            if pred(r):
                return r["delta_s"]
        return None
    dollar_seconds = 0.0
    for i, r in enumerate(post):
        width = (post[i + 1]["delta_s"] - r["delta_s"]) if i + 1 < len(post) else max(step_s, 0.0)
        dollar_seconds += r["fillable_notional"] * width
    return {"baseline_notional": baseline, "baseline_delta_s": base_row["delta_s"] if base_row else None,
            "pre_print_stamps": len(pre), "post_print_stamps": len(post),
            "first_change_s": first(lambda r: r["changed"]),
            "half_s": first(lambda r: r["fillable_notional"] <= 0.5 * baseline) if baseline > 0 else None,
            "tenth_s": first(lambda r: r["fillable_notional"] <= 0.1 * baseline) if baseline > 0 else None,
            "gone_s": first(lambda r: r["clearing_levels"] == 0),
            "max_post_notional": round(max((r["fillable_notional"] for r in post), default=0.0), 2),
            "notional_seconds": round(dollar_seconds, 2)}


def survival_curve(stamps: Sequence[Stamp], rules: Sequence[Rule], event: Event, breakeven: Callable[[float], float],
                   step_s: float = 1.0, release_utc: Optional[datetime] = None, honour_r4: bool = True) -> Dict[str, Any]:
    """
    The measurement Rounds 91-93 were built for. For every market the rules resolve from the
    event: a time series of what each recorded book would have handed a sniper that knew the
    outcome (the uncapped depth walk), indexed by seconds from the event's observed_at
    (negative = before the print), plus survival_summary(). Uncapped on purpose: a Kelly-capped
    figure sits flat at the cap and hides the decay that is being measured. Places nothing.
    """
    anchor = event.observed_at
    out: Dict[str, Any] = {"anchor": anchor.isoformat(), "release_utc": release_utc.isoformat() if release_utc else None,
                           "anchor_minus_release_s": round((anchor - release_utc).total_seconds(), 3) if release_utc else None,
                           "event": {"kind": event.kind, "payload": event.payload, "confidence": event.confidence},
                           "step_seconds": step_s, "stamps": len(stamps), "markets": []}
    for rule in rules:
        outcome = rule.resolve(event)
        if outcome is None:
            continue
        own = [st for st in stamps if st.token == rule.market]
        market: Dict[str, Any] = {"market": rule.market, "rule": rule.label or rule.market, "outcome": outcome,
                                  "side": "BUY_YES" if outcome == "YES" else "BUY_NO", "stamps": len(own),
                                  "neg_risk": own[0].book.neg_risk if own else None, "deferred": None, "series": [], "summary": None}
        out["markets"].append(market)
        if not own:
            continue
        if outcome == "NO" and own[0].book.neg_risk and honour_r4:
            market["deferred"] = "neg_risk market: NO side deferred to Phase 2 (Ruling R4)"
            continue
        previous = None
        for st in bucket_latest(own, anchor, step_s):
            rep = depth_report(st.book, outcome, event.confidence, breakeven, now=st.observed_at, honour_r4=honour_r4)
            print_ = st.fingerprint()
            market["series"].append({"delta_s": round((st.observed_at - anchor).total_seconds(), 3),
                                     "observed_at": st.observed_at.isoformat(), "fillable_shares": rep["fillable_shares"],
                                     "fillable_notional": rep["fillable_notional"], "vwap": rep["vwap"],
                                     "clearing_levels": rep["levels_clearing"], "best_price": rep["best_price"],
                                     "expected_profit": rep["expected_profit"],
                                     "changed": previous is not None and print_ != previous, "stamp": st.name})
            previous = print_
        market["summary"] = survival_summary(market["series"], step_s)
    return out


def _fmt_s(value: Optional[float]) -> str:
    return "never" if value is None else "t%+.1fs" % value


def format_survival(result: Dict[str, Any], economics_label: str, max_rows: int = 24) -> str:
    lines = ["SURVIVAL CURVE (Round 94) - what the recorded books would have handed a sniper that knew the outcome, second by second",
             "  anchor %s (event observed_at)%s · step %g s · %d stamps · economics: %s" % (
                 result["anchor"],
                 " = release %+.1fs" % result["anchor_minus_release_s"] if result.get("anchor_minus_release_s") is not None else "",
                 result["step_seconds"], result["stamps"], economics_label)]
    for m in result["markets"]:
        head = "  %s %s '%s'%s - %d stamps" % (m["market"][:14], m["side"], m["rule"], " (neg_risk)" if m["neg_risk"] else "", m["stamps"])
        if m["deferred"]:
            lines.append(head + ": " + m["deferred"])
            continue
        if not m["series"]:
            lines.append(head + ": no stamps for this token")
            continue
        sm = m["summary"]
        lines.append(head)
        lines.append("      baseline $%.2f at %s · first change %s · half %s · tenth %s · gone %s · post-print $-seconds %.0f · peak post $%.2f" % (
            sm["baseline_notional"], _fmt_s(sm["baseline_delta_s"]), _fmt_s(sm["first_change_s"]), _fmt_s(sm["half_s"]),
            _fmt_s(sm["tenth_s"]), _fmt_s(sm["gone_s"]), sm["notional_seconds"], sm["max_post_notional"]))
        lines.append("      %8s %10s %12s %8s %6s %s" % ("t (s)", "shares", "notional $", "vwap", "lvls", "chg"))
        pre = [r for r in m["series"] if r["delta_s"] < 0][-2:]
        post = [r for r in m["series"] if r["delta_s"] >= 0]
        shown = pre + post[:max_rows]
        for r in shown:
            lines.append("      %+8.1f %10.0f %12.2f %8s %6d %s" % (r["delta_s"], r["fillable_shares"], r["fillable_notional"],
                                                                  "%.4f" % r["vwap"] if r["vwap"] is not None else "-",
                                                                  r["clearing_levels"], "*" if r["changed"] else ""))
        hidden = len(m["series"]) - len(shown)
        if hidden > 0:
            lines.append("      ... %d more row(s); --json for all" % hidden)
    lines.append("  uncapped upper bounds from recorded books (Ruling R4 honoured); offline replay; places nothing.")
    return "\n".join(lines)


def replay_economics(assume_defaults: bool) -> Tuple[Callable[[float], float], Callable[[float, float], float], str]:
    """The Tax Reserve Agent's breakeven when the hook loads, else the fair one - and a label saying which."""
    breakeven, cap = assumed_economics()
    if assume_defaults:
        return breakeven, cap, "assumed (fair breakeven)"
    try:
        from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
        breakeven, cap = hook_economics(get_hook())
        return breakeven, cap, "Tax Reserve Agent after-tax breakeven"
    except Exception as exc:                                # noqa: BLE001 - the ledger may be absent; say so
        return breakeven, cap, "assumed (hook unavailable: %s)" % type(exc).__name__


# ------------------------------------------------------------------ paper receipts (the only execution this module has)

def record_paper(opportunity: Opportunity, event: Event, receipts_dir: Optional[Path] = None, writer=None,
                 stamp: Optional[str] = None) -> Optional[Path]:
    """One PAPER receipt per opportunity under cross_market/data/paper_receipts - never the tax imports."""
    if writer is None:
        from Tax_Reserve_Agent.interfaces.receipts import log_execution_receipt as writer
    notes = ("paper:1; strategy:%s; event:%s; source:%s; confidence:%.3f; rule:%s; outcome:%s; side:%s; "
             "expected_profit:%.2f; capped_by:%s; book_age:%.1fs" % (
                 STRATEGY, event.kind, event.source, event.confidence, opportunity.rule, opportunity.outcome,
                 opportunity.side, opportunity.expected_profit, opportunity.capped_by, opportunity.book_age_s))
    try:
        return writer(symbol=opportunity.market, side="BUY" if opportunity.side == "BUY_YES" else "SELL",
                      quantity=round(opportunity.shares, 6), price=round(opportunity.vwap, 6), strategy=STRATEGY,
                      venue="polymarket", fee=round(opportunity.fee_rate * opportunity.notional, 6),
                      timestamp=stamp or _now().isoformat(), imports_dir=Path(receipts_dir or PAPER_RECEIPTS_DIR),
                      extra_notes=notes)
    except Exception as exc:                                # noqa: BLE001
        print("[WARN] paper receipt not written (%s: %s)" % (type(exc).__name__, exc))
        return None


# ------------------------------------------------------------------ CLI

def format_result(result: Dict[str, Any]) -> str:
    ev = result["event"]
    lines = ["LATENCY SNIPER (Item 12, Phase 1, PAPER) - event %s from %s, confidence %.3f, observed %s"
             % (ev["kind"], ev["source"], ev["confidence"], ev["observed_at"])]
    if result.get("refused"):
        lines.append("  REFUSED: %s" % result["refused"])
        return "\n".join(lines)
    for opp in result["opportunities"]:
        d = opp.to_dict() if isinstance(opp, Opportunity) else opp
        lines.append("  %s %s (%s): %.1f shares, vwap %.4f, notional $%.2f, expected profit $%.2f, cap $%.2f (%s), %d level(s), book %.1fs old"
                     % (d["side"], d["market"], d["rule"], d["shares"], d["vwap"], d["notional"], d["expected_profit"],
                        d["cap_notional"], d["capped_by"], len(d["fills"]), d["book_age_s"]))
    for skip in result["skipped"]:
        lines.append("  skipped %s (%s): %s" % (skip["market"], skip["rule"], skip["reason"]))
    if not result["opportunities"] and not result["skipped"]:
        lines.append("  no rule resolves this event")
    lines.append("  offline research only: reads an event, rules and stamped books; places nothing.")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Item 12 Phase 1 - Polymarket latency sniper (offline, paper)")
    parser.add_argument("--event", type=Path, help="event JSON: {kind, payload, source, confidence, observed_at}")
    parser.add_argument("--rules", type=Path, default=None, help="rules JSON (default: the committed sample)")
    parser.add_argument("--books", type=Path, default=None, help="stamped CLOB books dir (default %s)" % DEFAULT_BOOKS_DIR)
    parser.add_argument("--paper", action="store_true", help="write PAPER receipts for every opportunity")
    parser.add_argument("--receipts-dir", type=Path, default=None, help="with --paper: where (default cross_market/data/paper_receipts)")
    parser.add_argument("--halt-flag", type=Path, default=None)
    parser.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    parser.add_argument("--max-book-age", type=float, default=MAX_BOOK_AGE_S)
    parser.add_argument("--now", default=None, help="evaluate as of this ISO time (replay); default now")
    parser.add_argument("--assume-defaults", action="store_true", help="no tax ledger: fair breakeven and a nominal bankroll")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--record", action="store_true", help="stamp the CLOB book of --tokens into --books (read-only GET)")
    parser.add_argument("--tokens", default="", help="with --record: comma-separated YES token ids")
    parser.add_argument("--fee-rate", type=float, default=0.0, help="with --record: the fee rate stored on the stamps")
    parser.add_argument("--record-loop", action="store_true",
                        help="Ruling R2: stamp --tokens every --interval seconds for --duration seconds (default 1 s x 420 s "
                             "= T-2 to T+5 min); stops at the duration, on HALT.flag, or Ctrl-C; read-only GETs")
    parser.add_argument("--interval", type=float, default=1.0, help="with --record-loop: seconds between polls")
    parser.add_argument("--duration", type=float, default=420.0, help="with --record-loop: total seconds")
    parser.add_argument("--depth-report", action="store_true",
                        help="Option 2 (Round 92): for every recorded book, what a sniper knowing the outcome could take, "
                             "level by level, YES and NO (NO deferred on neg_risk books, Ruling R4)")
    parser.add_argument("--confidence", type=float, default=0.995, help="with --depth-report: the assumed outcome confidence")
    parser.add_argument("--survival-curve", action="store_true",
                        help="Round 94: replay --rules against every stamp in --books around --event and report, second by "
                             "second, what a sniper knowing the outcome could have taken and how long that lasted")
    parser.add_argument("--step-seconds", type=float, default=1.0,
                        help="with --survival-curve: bucket width, the latest stamp per bucket; <= 0 keeps every stamp")
    args = parser.parse_args(argv)
    if args.survival_curve:
        if not args.event or not args.rules:
            parser.error("--survival-curve needs --event and --rules (the pre-registered file, never the sample)")
        event = Event.from_dict(json.loads(Path(args.event).read_text(encoding="utf-8")))
        rules = load_rules(args.rules)
        release = None
        try:
            raw = json.loads(Path(args.rules).read_text(encoding="utf-8"))
            release = _utc(raw["release_utc"]) if isinstance(raw, dict) and raw.get("release_utc") else None
        except Exception:                                   # noqa: BLE001 - the release time is a courtesy, not an input
            release = None
        stamps = load_stamp_series(Path(args.books or DEFAULT_BOOKS_DIR), tokens=[r.market for r in rules])
        breakeven, _cap, label = replay_economics(args.assume_defaults)
        result = survival_curve(stamps, rules, event, breakeven, step_s=args.step_seconds, release_utc=release)
        print(json.dumps(result, indent=2, default=str) if args.json else format_survival(result, label))
        return 0 if any(m["series"] for m in result["markets"]) else 1
    if args.depth_report:
        books_dir = Path(args.books or DEFAULT_BOOKS_DIR)
        now = _utc(args.now) if args.now else _now()
        books = load_books(books_dir, now)
        breakeven, _cap, label = replay_economics(args.assume_defaults)
        reports = []
        for token in sorted(books):
            for outcome in ("YES", "NO"):
                reports.append(depth_report(books[token], outcome, args.confidence, breakeven, now=now))
        print(json.dumps(reports, indent=2, default=str) if args.json else format_depth(reports, label))
        return 0 if reports else 1
    books_dir = Path(args.books or DEFAULT_BOOKS_DIR)
    halt = Path(args.halt_flag or DEFAULT_HALT_FLAG)
    if args.record_loop:
        tokens = [t.strip() for t in args.tokens.split(",") if t.strip()]
        if not tokens:
            print("[RECORD] --tokens is empty")
            return 1
        stats = record_loop(tokens, books_dir, default_fetch, interval=args.interval, duration=args.duration,
                            halt_path=halt, fee_rate=args.fee_rate)
        return EXIT_HALTED if stats["stopped"] == "halt" else (0 if stats["stamps"] else 1)
    if args.record:
        tokens = [t.strip() for t in args.tokens.split(",") if t.strip()]
        if not tokens:
            print("[RECORD] --tokens is empty")
            return 1
        written = stamp_books(tokens, books_dir, default_fetch, fee_rate=args.fee_rate)
        for path in written:
            print("[RECORD] %s" % path.name)
        return 0 if written else 1
    if not args.event:
        parser.error("--event is required unless --record")
    event = Event.from_dict(json.loads(Path(args.event).read_text(encoding="utf-8")))
    rules = load_rules(args.rules or SAMPLE_RULES)
    now = _utc(args.now) if args.now else _now()
    books = load_books(books_dir, now)
    if args.assume_defaults:
        breakeven, cap = assumed_economics()
    else:
        from Tax_Reserve_Agent.interfaces.monarch_hook import get_hook
        breakeven, cap = hook_economics(get_hook())
    result = evaluate(event, rules, books, breakeven, cap, now=now, halt_path=halt,
                      min_confidence=args.min_confidence, max_book_age_s=args.max_book_age)
    if args.paper and result["opportunities"]:
        for opp in result["opportunities"]:
            path = record_paper(opp, event, receipts_dir=args.receipts_dir)
            print("[PAPER] %s -> %s" % (opp.market, path))
    printable = dict(result, opportunities=[o.to_dict() for o in result["opportunities"]])
    print(json.dumps(printable, indent=2) if args.json else format_result(printable))
    return EXIT_HALTED if result["halted"] else 0


if __name__ == "__main__":
    sys.exit(main())
