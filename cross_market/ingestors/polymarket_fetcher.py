"""
Polymarket sports questions -> `Sports_Desk/data/polymarket_drops/`.

WHAT THIS CLOSES. `Cross_Market_Arb.md` reported "0 questions loaded" because
nothing had ever written a JSON file into the drop folder the exporter reads.
The matcher, the asymmetric-tax engine and the two hurdles were all built and
had never seen a Polymarket question. This module is the collector that makes
the first one exist.

OFFLINE BY DEFAULT. The bundled sample carries questions on the SAME fixtures
`odds_fetcher.py` prices into `sports_market.db` (Chiefs/Ravens, Eagles/Cowboys),
phrased in the shapes `matcher.parse_polymarket_question` actually parses, so
the pipeline produces matched pairs rather than an empty table. Prices are
plausible, not live; every pair is expected to REJECT against the 16.75% hurdle,
because real cross-market arbs pay 1-3% and the sample does not pretend otherwise.

THE LIVE PATH, VERIFIED 2026-09-04 AGAINST GAMMA.
  * `?tag=sports` is IGNORED. Antigravity's handoff named it; a live call returned
    a crypto IPO event and a French-politics event. The filter Gamma honours is
    `tag_id=1`, and `/tags/slug/sports` confirms id 1 is the "Sports" tag.
  * `outcomes`, `outcomePrices` and `clobTokenIds` arrive as JSON-encoded STRINGS,
    not arrays (the tax ingestor learned this in Round 26).
  * Two market shapes exist. A binary ("Will Jannik Sinner win ...?") has outcomes
    ["Yes","No"] and the YES price is outcomePrices[0]. A FIXTURE market ("St.
    Louis Cardinals vs. Los Angeles Dodgers") has the two TEAMS as outcomes; it is
    not yes/no, and the matcher cannot read a bare "A vs B" because it does not
    say which side the share is long. So a fixture market is rewritten into two
    derived questions - "Will the A beat the B?" priced at outcome 0, "Will the B
    beat the A?" at outcome 1 - each carrying `derived_from` so nobody mistakes
    the wording for Polymarket's.
  * `bestAsk` is what a YES share costs to BUY, so it is the price used for the
    first outcome when present; otherwise `outcomePrices`. The basis is recorded.
  * Fees are NOT inferred. `takerBaseFee` appears on markets and its unit is not
    documented; guessing a fee into the hurdle would be a fabricated number. The
    raw value is carried for the record and `fee_rate` comes only from
    `--fee-rate`, which defaults to 0.0.

Questions are written in exactly the dict shape `hud.scan_cross_market` consumes:
`question`, `yes_price`, `token_id`, and optionally `sport` and `fee_rate`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

DEFAULT_DROP_DIR = (Path(__file__).resolve().parents[2]
                    / "Sports_Desk" / "data" / "polymarket_drops")
DEFAULT_DROP_NAME = "polymarket_sports.json"      # ONE current file, overwritten - see write_drop

GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"
SPORTS_TAG_ID = 1                                  # /tags/slug/sports -> {"id": "1", "label": "Sports"}
DEFAULT_SPORTS = ("NFL", "NBA", "MLB", "NHL")      # the leagues matcher.TEAMS can resolve
REQUIRED = ("question", "yes_price", "token_id")
DEAD_PRICE_FLOOR = 0.005                           # a share at 0.001 is a resolved market, not a quote
DEAD_PRICE_CEILING = 0.995


class FetchError(RuntimeError):
    """A live payload did not have the shape the drop folder accepts."""


# ---------------------------------------------------------------------------
# The bundled sample
# ---------------------------------------------------------------------------

def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sample_questions(now: Optional[datetime] = None,
                     hours_to_start: float = 3.0) -> List[Dict[str, Any]]:
    """
    Questions on the fixtures `odds_fetcher.SAMPLE_FIXTURES` prices.

    Pinnacle in that sample has Ravens +125 (44.4% implied) and Cowboys +215
    (31.7%), so a Chiefs YES at 0.55 hedged by Ravens at 2.25 sums to 0.994 - a
    0.6% gross arb - and a Cowboys YES at 0.22 hedged by Eagles at 1.385 sums to
    0.942, a 5.8% arb. Both are below the 16.75% capital hurdle, and that is the
    honest state of this market.
    """
    now = now or datetime.now(timezone.utc)
    starts = _iso(now + timedelta(hours=hours_to_start))
    fetched = _iso(now)

    def q(question, price, token, sport="NFL", slug="", **extra):
        row = {"question": question, "yes_price": price, "yes_bid": round(price - 0.01, 3),
               "token_id": token, "sport": sport, "fee_rate": 0.0, "event_slug": slug,
               "start_time": starts, "fetched_at": fetched, "source": "sample",
               "price_basis": "sample"}
        row.update(extra)
        return row

    return [
        q("Will the Chiefs beat the Ravens?", 0.55, "sample-kc-bal-kc", slug="nfl-kc-bal-sample"),
        q("Will the Ravens beat the Chiefs?", 0.46, "sample-kc-bal-bal", slug="nfl-kc-bal-sample"),
        q("Will the Chiefs vs Ravens total go over 47.5 points?", 0.50, "sample-kc-bal-o47.5",
          slug="nfl-kc-bal-sample"),
        q("Will the Eagles beat the Cowboys?", 0.74, "sample-phi-dal-phi", slug="nfl-phi-dal-sample"),
        q("Will the Cowboys beat the Eagles?", 0.22, "sample-phi-dal-dal", slug="nfl-phi-dal-sample"),
        q("Will the Eagles vs Cowboys total go under 44.5 points?", 0.51, "sample-phi-dal-u44.5",
          slug="nfl-phi-dal-sample"),
        # A spread question. Until Round 35 the book keyed both spread legs under
        # the home handicap and this could not match; each leg now carries its own
        # signed handicap (Ruling 5.B), so it hedges against Cowboys +6.5.
        q("Will the Eagles beat the Cowboys by more than 6.5 points?", 0.50, "sample-phi-dal-s6.5",
          slug="nfl-phi-dal-sample"),
    ]


# ---------------------------------------------------------------------------
# Gamma normalisation
# ---------------------------------------------------------------------------

def json_list(value: Any) -> List[Any]:
    """Gamma encodes list fields as JSON STRINGS. Accept either form."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return []


def _f(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f


def sport_of(event: Dict[str, Any], sports: Sequence[str] = DEFAULT_SPORTS) -> Optional[str]:
    """The league a Gamma event belongs to, from its tags, or None if not one we trade."""
    wanted = {s.upper() for s in sports}
    for tag in event.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        for key in ("label", "slug"):
            value = str(tag.get(key) or "").upper()
            if value in wanted:
                return value
    return None


def _team_phrase(name: str) -> str:
    """'St. Louis Cardinals' -> 'the St. Louis Cardinals' for the matcher's WILL THE ... BEAT THE ... form."""
    name = str(name).strip()
    return name if name.upper().startswith("THE ") else "the %s" % name


def _priced(is_dead_ok: bool, price: Optional[float], basis: str) -> Optional[Dict[str, Any]]:
    if price is None:
        return None
    if not is_dead_ok and not (DEAD_PRICE_FLOOR <= price <= DEAD_PRICE_CEILING):
        return None
    return {"price": float(price), "basis": basis}


def _live_price(is_dead_ok: bool, ask: Optional[float], outcome_price: Optional[float]
                ) -> Optional[Dict[str, Any]]:
    if ask is not None and ask > 0:
        return _priced(is_dead_ok, ask, "best_ask")
    return _priced(is_dead_ok, outcome_price, "outcome_price")


def _second_leg_price(is_dead_ok: bool, outcome_price: Optional[float],
                      first_leg_bid: Optional[float]) -> Optional[Dict[str, Any]]:
    """
    The executable ask on outcome 1 when Gamma only quotes outcome 0's book.

    In a binary market, buying outcome 1 is selling outcome 0, so the ask on the
    second token is 1 - bid on the first. Taking the WORSE of that and the posted
    outcome price is the conservative reading (Round 35, Target 4): a hedge
    priced off the optimistic number reports an arbitrage that cannot be filled.
    """
    price, basis = outcome_price, "outcome_price"
    if first_leg_bid is not None and 0.0 < first_leg_bid < 1.0:
        mirrored = 1.0 - first_leg_bid
        if price is None or mirrored > price:
            price, basis = mirrored, "mirrored_bid"
    return _priced(is_dead_ok, price, basis)


_TOTAL_WORDS = re.compile(r"\b(OVER|UNDER)\b")
_SPREAD_MARK = re.compile(r"[+-]\s*\d")


def looks_like_team(outcome: str) -> bool:
    """
    Is this outcome a TEAM, rather than a total ("Over 47.5") or a spread
    ("Eagles -6.5")? Only a fixture whose two outcomes are both teams is rewritten
    into "Will A beat B?"; anything else would derive a moneyline question from a
    market that is not one.
    """
    text = str(outcome or "").strip().upper()
    if not text:
        return False
    if _TOTAL_WORDS.search(text) or _SPREAD_MARK.search(text):
        return False
    return True


def normalise_event(event: Dict[str, Any], sports: Sequence[str] = DEFAULT_SPORTS,
                    fee_rate: float = 0.0, fetched_at: Optional[str] = None,
                    keep_dead: bool = False) -> Dict[str, Any]:
    """
    One Gamma event -> the questions in it that the matcher can read.

    Returns {"questions": [...], "skipped": {reason: count}} so a live run can say
    what it threw away and why; a fetcher that silently dropped 90% of a payload
    would be indistinguishable from a quiet market.
    """
    out: Dict[str, Any] = {"questions": [], "skipped": {}}

    def skip(reason: str) -> None:
        out["skipped"][reason] = out["skipped"].get(reason, 0) + 1

    sport = sport_of(event, sports)
    if sport is None:
        skip("not_a_traded_league")
        return out
    fetched_at = fetched_at or _iso(datetime.now(timezone.utc))
    base = {
        "sport": sport, "fee_rate": float(fee_rate), "event_slug": event.get("slug", ""),
        "event_title": event.get("title", ""), "start_time": event.get("startDate") or "",
        "volume_24h": _f(event.get("volume24hr")) or 0.0, "fetched_at": fetched_at,
        "source": "gamma",
    }
    for market in event.get("markets") or []:
        if not isinstance(market, dict):
            skip("malformed_market")
            continue
        if market.get("closed") or market.get("active") is False:
            skip("closed_or_inactive")
            continue
        outcomes = [str(o) for o in json_list(market.get("outcomes"))]
        prices = [_f(p) for p in json_list(market.get("outcomePrices"))]
        tokens = [str(t) for t in json_list(market.get("clobTokenIds"))]
        if len(outcomes) != 2 or len(tokens) != 2:
            skip("not_two_outcomes")
            continue
        ask, bid = _f(market.get("bestAsk")), _f(market.get("bestBid"))
        common = dict(base, condition_id=str(market.get("conditionId") or ""),
                      market_slug=market.get("slug", ""), yes_bid=bid,
                      taker_base_fee_raw=market.get("takerBaseFee"),
                      start_time=market.get("startDate") or base["start_time"])

        if [o.upper() for o in outcomes] == ["YES", "NO"]:
            priced = _live_price(keep_dead, ask, prices[0] if prices else None)
            if priced is None:
                skip("dead_or_unpriced")
                continue
            out["questions"].append(dict(common, question=str(market.get("question") or ""),
                                         yes_price=priced["price"], price_basis=priced["basis"],
                                         token_id=tokens[0]))
            continue

        # A fixture market: the two teams are the outcomes. Derive both directions.
        a, b = outcomes
        if not (looks_like_team(a) and looks_like_team(b)):
            skip("not_a_fixture_market")
            continue
        first = _live_price(keep_dead, ask, prices[0] if prices else None)
        second = _second_leg_price(keep_dead, prices[1] if len(prices) > 1 else None, bid)
        original = str(market.get("question") or market.get("groupItemTitle") or "")
        if first is None and second is None:
            skip("dead_or_unpriced")
            continue
        if first is not None:
            out["questions"].append(dict(common, question="Will %s beat %s?" % (_team_phrase(a), _team_phrase(b)),
                                         yes_price=first["price"], price_basis=first["basis"],
                                         token_id=tokens[0], derived_from=original))
        if second is not None:
            out["questions"].append(dict(common, question="Will %s beat %s?" % (_team_phrase(b), _team_phrase(a)),
                                         yes_price=second["price"], price_basis=second["basis"],
                                         token_id=tokens[1], derived_from=original))
    if not out["questions"] and not out["skipped"]:
        skip("no_markets")
    return out


def normalise_events(events: Iterable[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
    questions: List[Dict[str, Any]] = []
    skipped: Dict[str, int] = {}
    seen = 0
    for event in events:
        seen += 1
        result = normalise_event(event, **kwargs)
        questions.extend(result["questions"])
        for reason, count in result["skipped"].items():
            skipped[reason] = skipped.get(reason, 0) + count
    return {"events": seen, "questions": questions, "skipped": skipped}


# ---------------------------------------------------------------------------
# Fetching, validation, writing
# ---------------------------------------------------------------------------

def fetch_events(url: str = GAMMA_EVENTS_URL, tag_id: int = SPORTS_TAG_ID,
                 limit: int = 100, pages: int = 3, timeout: float = 15.0,
                 getter: Optional[Callable[[str, Dict[str, Any], float], Any]] = None
                 ) -> List[Dict[str, Any]]:
    """
    Active sports events from Gamma, highest 24h volume first, paged.

    `requests` is imported lazily inside the default getter, so the offline path
    never touches a network library; a test passes `getter` to exercise paging
    and validation without a socket.
    """
    if getter is None:
        import requests  # noqa: WPS433 - deliberate lazy import

        def getter(target: str, params: Dict[str, Any], limit_s: float) -> Any:
            response = requests.get(target, params=params, timeout=limit_s,
                                    headers={"User-Agent": "MonarchCrossMarket/1.0"})
            response.raise_for_status()
            return response.json()

    events: List[Dict[str, Any]] = []
    offset = 0
    for _ in range(max(1, int(pages))):
        page = getter(url, {"tag_id": int(tag_id), "closed": "false", "limit": int(limit),
                            "offset": offset, "order": "volume24hr", "ascending": "false"}, timeout)
        if not isinstance(page, list):
            raise FetchError("Gamma returned %s, expected a JSON list of events" % type(page).__name__)
        if not page:
            break
        events.extend(e for e in page if isinstance(e, dict))
        offset += len(page)
        if len(page) < int(limit):
            break
    return events


def validate_questions(questions: Any) -> List[Dict[str, Any]]:
    """Refuse anything the exporter's consumer could not price. Checked BEFORE writing."""
    if not isinstance(questions, list):
        raise FetchError("questions must be a list, got %s" % type(questions).__name__)
    clean: List[Dict[str, Any]] = []
    for index, row in enumerate(questions):
        if not isinstance(row, dict):
            raise FetchError("question %d is not an object" % index)
        missing = [c for c in REQUIRED if row.get(c) in (None, "")]
        if missing:
            raise FetchError("question %d is missing %s" % (index, ", ".join(missing)))
        price = _f(row.get("yes_price"))
        if price is None or not (0.0 < price < 1.0):
            raise FetchError("question %d has yes_price %r, expected a share price in (0, 1)"
                             % (index, row.get("yes_price")))
        clean.append(row)
    if not clean:
        raise FetchError("no questions to write")
    return clean


def fingerprint(questions: Sequence[Dict[str, Any]]) -> str:
    """Identity of a question set by PRICES, not timestamps - so a re-fetch of an unchanged market is recognised."""
    digest = hashlib.sha256()
    for row in sorted(questions, key=lambda r: (str(r.get("token_id")), str(r.get("question")))):
        digest.update(("%s|%s|%.4f\n" % (row.get("token_id"), row.get("question"),
                                          float(row.get("yes_price") or 0.0))).encode("utf-8"))
    return digest.hexdigest()


def write_drop(questions: Sequence[Dict[str, Any]], drop_dir: Path = DEFAULT_DROP_DIR,
               name: Optional[str] = None) -> Path:
    """
    Write the questions as ONE JSON list. Overwrites `name` (default: a fixed
    filename), because the exporter reads every file in the folder and a folder
    of timestamped drops would price the same market once per drop, at prices
    that are no longer offered. Pass `name` to keep an archive on purpose.
    """
    drop_dir = Path(drop_dir)
    drop_dir.mkdir(parents=True, exist_ok=True)
    target = drop_dir / (name or DEFAULT_DROP_NAME)
    target.write_text(json.dumps(list(questions), indent=1), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

def poll(source: Callable[[], List[Dict[str, Any]]], drop_dir: Path = DEFAULT_DROP_DIR,
         name: Optional[str] = None, interval: float = 300.0,
         max_polls: Optional[int] = None, sleep: Callable[[float], None] = time.sleep,
         log: Callable[[str], None] = print) -> Dict[str, int]:
    """
    Re-fetch on a timer and write ONLY when the prices changed.

    A source that has not moved is skipped, not re-stamped: writing an identical
    set with a fresh `fetched_at` would manufacture a price history that was
    never quoted.
    """
    stats = {"polls": 0, "drops": 0, "skipped_unchanged": 0, "errors": 0}
    last: Optional[str] = None
    while True:
        stats["polls"] += 1
        try:
            questions = validate_questions(source())
        except Exception as exc:                            # noqa: BLE001 - keep polling
            stats["errors"] += 1
            log("[ERROR] poll %d: %s: %s" % (stats["polls"], type(exc).__name__, exc))
        else:
            current = fingerprint(questions)
            if current == last:
                stats["skipped_unchanged"] += 1
                log("[SKIP] poll %d: %d question(s) unchanged since the last drop - not re-stamped"
                    % (stats["polls"], len(questions)))
            else:
                target = write_drop(questions, drop_dir, name=name)
                stats["drops"] += 1
                last = current
                log("[DROP] poll %d: %d question(s) -> %s" % (stats["polls"], len(questions), target))
        if max_polls is not None and stats["polls"] >= max_polls:
            return stats
        sleep(interval)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Polymarket sports questions -> the cross-market drop folder")
    parser.add_argument("--sample", action="store_true",
                        help="write the bundled sample on the odds_fetcher fixtures (the default)")
    parser.add_argument("--live", action="store_true",
                        help="fetch active sports events from Gamma (tag_id=1); never touched otherwise")
    parser.add_argument("--url", default=GAMMA_EVENTS_URL)
    parser.add_argument("--tag-id", type=int, default=SPORTS_TAG_ID)
    parser.add_argument("--limit", type=int, default=100, help="events per page (default 100)")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--sports", default=",".join(DEFAULT_SPORTS),
                        help="leagues to keep, by Gamma tag label (default: %s)" % ",".join(DEFAULT_SPORTS))
    parser.add_argument("--fee-rate", type=float, default=0.0,
                        help="Polymarket taker fee as a fraction, if you know it (default 0.0 - not inferred)")
    parser.add_argument("--folder", type=Path, default=None, help="drop folder")
    parser.add_argument("--name", default=None, help="drop file name (default: %s, overwritten)" % DEFAULT_DROP_NAME)
    parser.add_argument("--watch", action="store_true", help="poll on --interval; write only on change")
    parser.add_argument("--interval", type=float, default=300.0)
    parser.add_argument("--max-polls", type=int, default=None)
    args = parser.parse_args(argv)

    folder = Path(args.folder or DEFAULT_DROP_DIR)
    sports = tuple(s.strip().upper() for s in args.sports.split(",") if s.strip())

    if args.live:
        def source() -> List[Dict[str, Any]]:
            events = fetch_events(args.url, tag_id=args.tag_id, limit=args.limit, pages=args.pages)
            result = normalise_events(events, sports=sports, fee_rate=args.fee_rate)
            if result["skipped"]:
                print("[GAMMA] %d event(s): kept %d question(s), skipped %s"
                      % (result["events"], len(result["questions"]), result["skipped"]))
            return result["questions"]
    else:
        def source() -> List[Dict[str, Any]]:
            return sample_questions()

    if args.watch:
        poll(source, folder, name=args.name, interval=args.interval, max_polls=args.max_polls)
        return 0
    questions = validate_questions(source())
    target = write_drop(questions, folder, name=args.name)
    print("[DROP] %d question(s) from %s -> %s" % (len(questions), "gamma" if args.live else "bundled sample", target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
