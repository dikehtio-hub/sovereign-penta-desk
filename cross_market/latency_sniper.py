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
says what was actually there to take, and for how long.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
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

    @classmethod
    def from_clob(cls, market: str, payload: Dict[str, Any], observed_at: Any, fee_rate: float = 0.0) -> "Book":
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
        return cls(market=str(market), bids=bids, asks=asks, observed_at=_utc(observed_at), fee_rate=float(fee_rate))

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
    args = parser.parse_args(argv)
    books_dir = Path(args.books or DEFAULT_BOOKS_DIR)
    halt = Path(args.halt_flag or DEFAULT_HALT_FLAG)
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
