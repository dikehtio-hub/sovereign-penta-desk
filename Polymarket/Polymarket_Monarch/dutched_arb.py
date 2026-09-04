"""
================================================================================
Polymarket Monarch: Negative-Risk Dutching Scanner
================================================================================
Finds multi-outcome (negative-risk) events where you can buy YES on EVERY
mutually exclusive outcome for less than $1 in total. Exactly one outcome must
resolve YES and pay $1, so a total cost below $1 is a locked profit regardless
of which one wins - a "dutch book".

    edge = 1.00 - sum(best_ask_yes across all outcomes)

TWO THINGS THAT MAKE THE NAIVE VERSION WRONG. Both were found by running it.

1. EMPTY BOOKS INFLATE THE SUM INTO NONSENSE. Illiquid long-tail outcomes quote
   bestAsk at or near 1.00 with no real offer behind it. Summing those gives
   totals like 77.0 and 88.0 on real 128-outcome election events. Worse, the
   failure is not symmetric: a leg you cannot actually buy makes an event look
   un-arbable, while a leg with a stale thin ask can make one look arbable when
   the size is $3. Every leg is therefore required to have a genuine two-sided
   book before the event's sum is treated as meaningful at all.

2. TOP-OF-BOOK IS NOT A TRADE. bestAsk is one price level. The real position is
   capped by the SMALLEST leg's depth - buy 500 of a 32-outcome event and you
   need 500 available on all 32 legs. A flagged event is therefore re-priced
   against the full CLOB book, walking each leg's asks to find the size actually
   executable and the true average cost. `--no-depth` skips this, and is only
   for eyeballing the distribution.

EXPECT ZERO HITS. A 4%+ risk-free return on fully collateralised, instantly
settling inventory is the most competitive trade on the venue; it is arbitraged
in seconds by bots co-located far closer than this script. This tool is built to
report the DISTRIBUTION - how close the tightest books actually get to 1.00 - so
an empty result is an informative measurement rather than a blank screen. If it
ever does fire, treat it as a data error until proven otherwise.

NOT PRICED HERE: gas/approval costs, the risk that a leg fills partially and
leaves you directionally exposed, and the possibility that the event's outcome
set is not truly exhaustive (a "none of the above" resolution breaks the whole
premise - check the resolution criteria before believing any edge).
================================================================================
"""

import os
import sys
import json
import time
import argparse
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

from tax_gate import TaxGate, GatedSize, add_tax_arguments, build_gate

console = Console()

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
HEADERS = {"User-Agent": "PolymarketMonarch/1.0"}

# Cloudflare fronts these endpoints and starts 429ing on bursts; the same 200ms
# floor pnl_scanner.py uses.
_MIN_REQUEST_GAP = 0.20
_last_request_ts = 0.0

DEFAULT_MAX_ASK_SUM = 0.96
DEFAULT_MIN_OUTCOMES = 3
DEFAULT_EVENT_LIMIT = 400


def _get(url: str, params: Optional[Dict] = None, timeout: int = 20) -> Optional[requests.Response]:
    """Rate-limited GET. Returns None rather than raising so one bad book cannot end a scan."""
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


def fetch_events(limit: int = DEFAULT_EVENT_LIMIT) -> List[Dict[str, Any]]:
    """Active events, highest 24h volume first, paged 100 at a time."""
    events: List[Dict[str, Any]] = []
    offset = 0
    while len(events) < limit:
        page = _get(f"{GAMMA_API_BASE}/events", {
            "closed": "false",
            "limit": min(100, limit - len(events)),
            "offset": offset,
            "order": "volume24hr",
            "ascending": "false",
        })
        if page is None:
            break
        batch = page.json()
        if not batch:
            break
        events.extend(batch)
        offset += len(batch)
        if len(batch) < 100:
            break
    return events


def _f(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f


def evaluate_event(event: Dict[str, Any], min_outcomes: int = DEFAULT_MIN_OUTCOMES) -> Optional[Dict[str, Any]]:
    """
    Price one event's dutch book, or None if it cannot be priced honestly.

    Rejects rather than guesses. An event with any one-sided leg is unpriceable,
    not cheap - see point 1 in the module docstring.
    """
    markets = event.get("markets") or []
    if len(markets) < min_outcomes:
        return None

    legs: List[Dict[str, Any]] = []
    for m in markets:
        ask, bid = _f(m.get("bestAsk")), _f(m.get("bestBid"))
        # A leg with no ask cannot be bought; a leg with no bid has no genuine
        # two-sided market behind its quote. Either makes the sum meaningless.
        if ask is None or bid is None or ask <= 0 or bid <= 0 or ask >= 1.0:
            return None
        token_ids = m.get("clobTokenIds")
        if isinstance(token_ids, str):
            try:
                token_ids = json.loads(token_ids)
            except json.JSONDecodeError:
                token_ids = []
        legs.append({
            "question": m.get("groupItemTitle") or m.get("question") or "?",
            "best_ask": ask,
            "best_bid": bid,
            "yes_token_id": token_ids[0] if token_ids else None,
        })

    ask_sum = sum(l["best_ask"] for l in legs)
    return {
        "title": event.get("title", "?"),
        "slug": event.get("slug", ""),
        "neg_risk": bool(event.get("negRisk")),
        "outcomes": len(legs),
        "ask_sum": ask_sum,
        "edge_pct": (1.0 - ask_sum) * 100.0,
        "volume_24h": _f(event.get("volume24hr")) or 0.0,
        "legs": legs,
    }


def walk_asks(token_id: str, shares: float) -> Optional[Tuple[float, float]]:
    """
    (avg_price, fillable_shares) for buying `shares` of one leg, walking the book.

    The CLOB returns asks price-DESCENDING, so the best price is the last entry.
    Getting that backwards silently prices the arb off the worst level in the
    book - which is why the traversal is explicit here rather than [0].
    """
    resp = _get(f"{CLOB_API_BASE}/book", {"token_id": token_id})
    if resp is None:
        return None
    asks = resp.json().get("asks") or []
    levels = sorted(
        ((_f(a.get("price")), _f(a.get("size"))) for a in asks),
        key=lambda p: (p[0] is None, p[0]),
    )
    spent = 0.0
    filled = 0.0
    for price, size in levels:
        if price is None or size is None or price >= 1.0:
            continue
        take = min(size, shares - filled)
        if take <= 0:
            break
        spent += take * price
        filled += take
        if filled >= shares:
            break
    if filled <= 0:
        return None
    return spent / filled, filled


def price_with_depth(candidate: Dict[str, Any], shares: float) -> Dict[str, Any]:
    """
    Re-price a flagged candidate against real book depth.

    The executable size is the MINIMUM fillable across legs: an arb you can only
    complete on 31 of 32 outcomes is not an arb, it is a directional position.
    """
    total_avg_cost = 0.0
    executable = shares
    priced_legs = 0
    for leg in candidate["legs"]:
        tid = leg.get("yes_token_id")
        if not tid:
            candidate["depth_error"] = "missing CLOB token id"
            return candidate
        walked = walk_asks(tid, shares)
        if walked is None:
            candidate["depth_error"] = f"no book for '{leg['question'][:30]}'"
            return candidate
        avg, fillable = walked
        leg["avg_price"] = avg
        leg["fillable"] = fillable
        total_avg_cost += avg
        executable = min(executable, fillable)
        priced_legs += 1

    candidate["depth_ask_sum"] = total_avg_cost
    candidate["depth_edge_pct"] = (1.0 - total_avg_cost) * 100.0
    candidate["executable_shares"] = executable
    candidate["profit_usd"] = (1.0 - total_avg_cost) * executable
    candidate["legs_priced"] = priced_legs
    return candidate


def gate_shares(shares: float, gate: Optional[TaxGate],
                cost_per_share: float = 1.0) -> GatedSize:
    """
    Clamps the target position size to what the Tax Reserve Agent says is risk
    capital.

    A complete negative-risk set costs the summed ask across every leg - about
    $1 by construction, which is why the notional is `shares * ask_sum` rather
    than `shares * one_leg`. Pure and separated from `scan()` so it can be tested
    without touching the network.
    """
    if gate is None:
        return GatedSize(shares, shares, cost_per_share, False, "tax gate not configured")
    return gate.clamp_shares(shares, cost_per_share)


def scan(max_ask_sum: float = DEFAULT_MAX_ASK_SUM,
         min_outcomes: int = DEFAULT_MIN_OUTCOMES,
         event_limit: int = DEFAULT_EVENT_LIMIT,
         shares: float = 100.0,
         check_depth: bool = True,
         neg_risk_only: bool = True,
         gate: Optional[TaxGate] = None,
         min_edge: float = 0.0) -> Dict[str, Any]:
    events = fetch_events(event_limit)
    priced: List[Dict[str, Any]] = []
    unpriceable = 0

    for ev in events:
        if neg_risk_only and not ev.get("negRisk"):
            continue
        result = evaluate_event(ev, min_outcomes)
        if result is None:
            unpriceable += 1
            continue
        priced.append(result)

    priced.sort(key=lambda c: c["ask_sum"])
    flagged = [c for c in priced if c["ask_sum"] < max_ask_sum]

    # MINIMUM EDGE AFTER FEES AND TAX. A dutch book is only worth taking if the
    # edge survives both, and under gross-of-fees accounting the tax is assessed on
    # the GROSS gain while the fees come out of pocket unrecorded:
    #
    #     after_tax = (e - f) - t*e  ->  break-even at e = f / (1 - t)
    #
    # At a 2% round trip and a 35% composite rate that is 3.08%, not 2%. An edge of
    # 2.5% looks like free money, clears the fees, and still loses after tax - which
    # is exactly the trade this scanner would otherwise put in front of you.
    below_threshold = [c for c in flagged if (c["edge_pct"] / 100.0) < min_edge]
    hits = [c for c in flagged if (c["edge_pct"] / 100.0) >= min_edge]

    # Size against risk capital BEFORE walking the book. Depth pricing answers
    # "can I fill this size?", and asking it about a size the bankroll cannot
    # fund produces an executable number and a profit figure for a trade that
    # was never placeable - the most misleading possible output.
    sizing = gate_shares(shares, gate, cost_per_share=max_ask_sum)
    tradeable_shares = sizing.approved_shares if sizing.gated else shares

    if check_depth and tradeable_shares > 0:
        for h in hits:
            price_with_depth(h, tradeable_shares)

    return {
        "scanned": len(events),
        "priced": priced,
        "unpriceable": unpriceable,
        "hits": hits,
        "below_threshold": below_threshold,
        "min_edge": min_edge,
        "max_ask_sum": max_ask_sum,
        "shares": tradeable_shares,
        "requested_shares": shares,
        "sizing": sizing,
        "checked_depth": check_depth and tradeable_shares > 0,
    }


def render(result: Dict[str, Any], show: int = 15, gate: Optional[TaxGate] = None) -> None:
    console.print()
    console.print(
        f"[bold]Negative-risk dutching scan[/bold]  ·  {result['scanned']} events fetched  ·  "
        f"{len(result['priced'])} priceable  ·  {result['unpriceable']} skipped (one-sided book)"
    )

    min_edge = result.get("min_edge", 0.0)
    if min_edge > 0:
        console.print(f"[dim]After-tax break-even edge: {min_edge * 100:.2f}% "
                      f"(fees / (1 - tax rate)) - anything below this loses money "
                      f"after tax.[/dim]")
    dropped = result.get("below_threshold") or []
    if dropped:
        console.print(f"[yellow]{len(dropped)} event(s) priced below 1.00 but under the "
                      f"{min_edge * 100:.2f}% after-tax threshold - NOT shown as hits:[/yellow]")
        for c in dropped[:5]:
            console.print(f"    [dim]{c['title'][:56]}  edge {c['edge_pct']:+.2f}%[/dim]")

    if gate is not None:
        status = gate.status_line()
        console.print(f"[dim]{status}[/dim]" if gate.available else f"[yellow]{status}[/yellow]")
    sizing = result.get("sizing")
    if sizing is not None and sizing.gated and sizing.approved_shares < sizing.requested_shares:
        console.print(
            f"[yellow]Position size clamped to {sizing.approved_shares:,.0f} shares "
            f"(asked for {sizing.requested_shares:,.0f}): {sizing.reason}[/yellow]"
        )
    if sizing is not None and sizing.blocked:
        console.print("[bold red]No deployable capital - depth pricing skipped. "
                      "Edges below are top-of-book only and are NOT tradeable evidence.[/bold red]")

    hits = result["hits"]
    if hits:
        console.print(f"\n[bold green]{len(hits)} DUTCH BOOK(S) under "
                      f"{result['max_ask_sum']:.2f}[/bold green]")
        for h in hits:
            console.print(f"\n  [bold]{h['title'][:70]}[/bold]  ({h['outcomes']} outcomes)")
            console.print(f"    top-of-book sum: {h['ask_sum']:.4f}   edge {h['edge_pct']:+.2f}%")
            if "depth_error" in h:
                console.print(f"    [yellow]depth unverified: {h['depth_error']} - "
                              f"treat the edge above as unconfirmed[/yellow]")
            elif "depth_ask_sum" in h:
                console.print(
                    f"    depth-adjusted:  {h['depth_ask_sum']:.4f}   "
                    f"edge {h['depth_edge_pct']:+.2f}%   "
                    f"executable {h['executable_shares']:,.0f} shares   "
                    f"profit ${h['profit_usd']:,.2f}"
                )
            console.print(f"    https://polymarket.com/event/{h['slug']}")
    else:
        console.print(f"\n[yellow]No event priced below {result['max_ask_sum']:.2f}.[/yellow] "
                      "Expected - see the distribution below for how close the market gets.")

    table = Table(title=f"\nTightest {show} books (closest to a dutch book)", box=box.SIMPLE)
    table.add_column("Event", style="cyan", max_width=44)
    table.add_column("Outs", justify="right")
    table.add_column("Ask sum", justify="right")
    table.add_column("Edge", justify="right")
    table.add_column("24h vol", justify="right")
    for c in result["priced"][:show]:
        edge = c["edge_pct"]
        table.add_row(
            c["title"][:44],
            str(c["outcomes"]),
            f"{c['ask_sum']:.4f}",
            f"[green]{edge:+.2f}%[/green]" if edge > 0 else f"[dim]{edge:+.2f}%[/dim]",
            f"${c['volume_24h']:,.0f}",
        )
    console.print(table)
    console.print(
        "[dim]An ask sum above 1.00 is the normal state: it is the market's spread and "
        "the venue's margin. Only a sum below 1.00 is a free lunch, and it will not last.[/dim]\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Polymarket negative-risk dutching scanner: buy every outcome for under $1"
    )
    parser.add_argument("--max-ask-sum", type=float, default=DEFAULT_MAX_ASK_SUM,
                        help=f"Flag events whose YES asks total below this (default: {DEFAULT_MAX_ASK_SUM})")
    parser.add_argument("--min-outcomes", type=int, default=DEFAULT_MIN_OUTCOMES,
                        help="Minimum mutually exclusive outcomes (default: 3)")
    parser.add_argument("--events", type=int, default=DEFAULT_EVENT_LIMIT,
                        help="How many active events to fetch (default: 400)")
    parser.add_argument("--shares", type=float, default=100.0,
                        help="Target position size in shares when checking depth (default: 100)")
    parser.add_argument("--no-depth", action="store_true",
                        help="Skip CLOB depth verification (top-of-book only - not tradeable evidence)")
    parser.add_argument("--all-events", action="store_true",
                        help="Include non-negative-risk events (their outcomes may not be exhaustive)")
    parser.add_argument("--show", type=int, default=15, help="Rows in the distribution table (default: 15)")
    parser.add_argument("--min-edge", type=float, default=None,
                        help="Minimum gross edge as a decimal (e.g. 0.0308). Default: the "
                             "after-tax break-even computed from the Tax Reserve Agent")
    add_tax_arguments(parser)
    args = parser.parse_args()

    gate = build_gate(args)
    # An explicit --min-edge wins; otherwise ask the agent what fees and tax cost.
    # No explicit override -> ask the agent; if it is unreachable the shim returns
    # its failsafe rather than 0, so a missing ledger cannot silently disable the
    # filter and surface sub-break-even "arbitrage".
    min_edge = args.min_edge if args.min_edge is not None else gate.breakeven_gross_edge()
    console.print("[dim]Fetching active events from Gamma...[/dim]")
    result = scan(
        max_ask_sum=args.max_ask_sum,
        min_outcomes=args.min_outcomes,
        event_limit=args.events,
        shares=args.shares,
        check_depth=not args.no_depth,
        neg_risk_only=not args.all_events,
        gate=gate,
        min_edge=min_edge,
    )
    render(result, show=args.show, gate=gate)


if __name__ == "__main__":
    main()
