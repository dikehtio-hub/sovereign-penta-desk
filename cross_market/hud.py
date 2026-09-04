"""
The dual-execution HUD: what to click, on both venues, in order.

A cross-market hedge has to be executed on two venues that share nothing - no
account, no API, no clock. The window in which both prices exist is short, and
the operator is reading this panel while it closes. So the panel is built around
one rule: EVERY FIELD NEEDED TO PLACE THE ORDER IS ON THE LINE FOR THAT ORDER.
No cross-referencing, no lookup, no arithmetic left for the reader.

It also leads with the verdict rather than the opportunity. Most cross-market
pairs are gross arbitrages and after-tax losses, so a panel that listed them
neutrally and left the judgement to the reader would be an efficient way to lose
money quickly. A pair that does not clear is shown as REJECTED, with the number
it needed, and its execution detail is not rendered at all.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from cross_market.hybrid_arb import HybridArbResult

RULE = "=" * 78
THIN = "-" * 78


def render_cross_market(results: Sequence[HybridArbResult],
                        pairs: Optional[Sequence[Any]] = None,
                        show_rejected: bool = True) -> str:
    """Render the panel. `pairs` supplies the matcher rationale, when available."""
    lines: List[str] = [RULE, "CROSS-MARKET ARBITRAGE  -  Polymarket vs sportsbook", RULE]
    if not results:
        lines.append("  No matched cross-market pairs.")
        lines.append("")
        lines.append("  This is the normal state. A pair needs the same fixture, the")
        lines.append("  same market type and - on spreads and totals - the SAME line,")
        lines.append("  quoted on both venues at once. Unmatched markets are dropped")
        lines.append("  rather than approximated.")
        lines.append(RULE)
        return "\n".join(lines)

    by_pair = {id(r): (pairs[i] if pairs and i < len(pairs) else None)
               for i, r in enumerate(results)}
    viable = [r for r in results if r.viable]
    rejected = [r for r in results if not r.viable]

    for result in sorted(viable, key=lambda r: -r.worst_after_tax_pct):
        lines.extend(_render_one(result, by_pair.get(id(result))))

    if rejected and show_rejected:
        lines.append("")
        lines.append("REJECTED - gross arbitrage, after-tax loss")
        lines.append(THIN)
        for result in sorted(rejected, key=lambda r: -r.gross_arb):
            need = result.breakeven_gross_arb
            need_text = (("needs %+.2f%%" % (need * 100.0)) if need is not None
                         else "no book clears it")
            lines.append(
                "  %-30s book %+6.2f%%  worst %+7.2f%%  %s"
                % (_fixture(result)[:30], result.gross_arb * 100.0,
                   result.worst_after_tax_pct * 100.0, need_text))
        lines.append("")
        lines.append("  These pay the same either way in DOLLARS and lose money after")
        lines.append("  tax. The loser leg's deduction is the problem: a sportsbook")
        lines.append("  loss needs gambling winnings to net against under NJ")
        lines.append("  54A:5-1(g), and a Polymarket capital loss needs capital gains")
        lines.append("  under IRC 1211(b). In a hedge, the winning leg supplies")
        lines.append("  neither - it supplies the other kind of income.")

    if not viable:
        lines.append("")
        lines.append("  NOTHING IS ACTIONABLE. That is the expected outcome: real")
        lines.append("  cross-book arbitrage runs 1-3% and the after-tax hurdle here")
        lines.append("  is roughly 9% at best and 17% with no relief capacity.")
    lines.append(RULE)
    return "\n".join(lines)


def _adverse_hurdle(result: HybridArbResult) -> Optional[float]:
    """
    The same pair priced as though the Polymarket leg were a wager.

    Recomputed rather than cached, because it is a property of the shape and the
    tax reading, not of the live book - and because a stale adverse number
    silently attached to a re-quoted pair would be worse than none.
    """
    from cross_market.hybrid_arb import (HybridLeg, breakeven_gross_arb,
                                         prediction_as_wagering_tax)
    leg_b = result.leg_b
    ordinary = leg_b.tax.gain_rate
    state = leg_b.tax.relief_rate
    adverse_a = HybridLeg(
        venue=result.leg_a.venue, selection=result.leg_a.selection,
        decimal_odds=result.leg_a.decimal_odds,
        tax=prediction_as_wagering_tax(ordinary, state,
                                       leg_b.tax.relief_capacity),
        token_id=result.leg_a.token_id, limit_price=result.leg_a.limit_price,
        raw_price=result.leg_a.raw_price, fee_rate=result.leg_a.fee_rate)
    try:
        return breakeven_gross_arb(adverse_a, leg_b)
    except Exception:                                       # noqa: BLE001
        return None


def _fixture(result: HybridArbResult) -> str:
    return "%s / %s" % (result.leg_a.selection, result.leg_b.selection)


def _render_one(result: HybridArbResult, pair: Any = None) -> List[str]:
    a, b = result.leg_a, result.leg_b
    lines = ["", "CLEARS  %s" % _fixture(result), THIN,
             "  book %+.2f%%   worst branch %+.2f%%  ($%.2f on $%.2f)"
             % (result.gross_arb * 100.0, result.worst_after_tax_pct * 100.0,
                result.worst_after_tax, result.capital),
             "  naive pre-tax stakes would leave the branches %.2f%% apart"
             % ((result.tax_manufactured_variance / result.capital) * 100.0
                if result.capital else 0.0)]
    if result.breakeven_gross_arb is not None:
        lines.append("  after-tax hurdle for this shape: %+.2f%%   (IRC 1234A capital)"
                     % (result.breakeven_gross_arb * 100.0))
    # BOTH CHARACTERISATIONS, ALWAYS. Round 29 ruled 1234A capital the default and
    # kept the wagering reading available - which is only useful if the operator
    # can see what the adverse reading costs at the moment of deciding. Showing
    # one number turns a live legal question into a settled one.
    adverse = _adverse_hurdle(result)
    if adverse is not None:
        lines.append("  same shape if read as WAGERING:   %+.2f%%   (IRC 165(d) - "
                     "the IRS has not ruled)" % (adverse * 100.0))
    lines.append("")

    # LEG A first because it is the one with a limit price to set. A market order
    # on Polymarket against a thin book is how a priced arbitrage becomes a loss
    # between the two clicks.
    lines.append("  LEG A  POLYMARKET")
    lines.append("    token id     %s" % (a.token_id or "(unknown)"))
    lines.append("    side         BUY YES  %s" % a.selection)
    lines.append("    limit price  %s   (do NOT market-order; the edge is thinner"
                 % (("%.4f" % a.limit_price) if a.limit_price is not None else "n/a"))
    lines.append("                  than the spread you would pay crossing it)")
    lines.append("    size         $%.2f   ->  %.2f shares"
                 % (result.stake_a,
                    result.stake_a / a.limit_price if a.limit_price else 0.0))
    lines.append("    decimal odds %.4f%s"
                 % (a.decimal_odds,
                    "   (net of %.2f%% fee on proceeds)" % (a.fee_rate * 100.0)
                    if a.fee_rate else ""))
    lines.append("")
    lines.append("  LEG B  SPORTSBOOK")
    lines.append("    book         %s" % b.venue)
    lines.append("    selection    %s" % b.selection)
    lines.append("    decimal odds %.4f   (american %s)"
                 % (b.decimal_odds, _american(b.decimal_odds)))
    lines.append("    stake        $%.2f" % result.stake_b)
    if pair is not None and getattr(pair, "target", None) is not None:
        lines.append("")
        lines.append("    why this side: %s" % pair.target.rationale)
    for warning in result.warnings:
        lines.append("")
        for chunk in _wrap("  ! " + warning, 78):
            lines.append(chunk)
    return lines


def _american(decimal_odds: float) -> str:
    if decimal_odds >= 2.0:
        return "+%d" % round((decimal_odds - 1.0) * 100.0)
    return "%d" % round(-100.0 / (decimal_odds - 1.0))


def _wrap(text: str, width: int) -> List[str]:
    out, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = "    " + word
        else:
            line = (line + " " + word) if line else word
    if line:
        out.append(line)
    return out


def scan_cross_market(hook: Any, questions: Sequence[Dict[str, Any]],
                      db_path: Optional[Any] = None,
                      capital: float = 1000.0,
                      gambling_win_capacity: float = 0.0,
                      capital_gain_capacity: float = 0.0,
                      prediction_is_wagering: bool = False):
    """
    End to end: parse questions, match them to book quotes, price the pairs.

    `questions` are dicts with at least `question` and `yes_price`; `token_id`,
    `sport` and `fee_rate` are used when present. Returns (results, pairs) so the
    HUD can show the matcher's reasoning next to the price.
    """
    from cross_market.hybrid_arb import build_legs, evaluate_hybrid_arb
    from cross_market.matcher import (DEFAULT_DB_PATH, load_book_quotes,
                                      match_markets, parse_polymarket_question)

    markets = []
    for raw in questions:
        parsed = parse_polymarket_question(
            raw.get("question", ""), sport=raw.get("sport"),
            token_id=raw.get("token_id", ""), yes_price=raw.get("yes_price"))
        if parsed is not None and parsed.yes_price is not None:
            markets.append(parsed)

    quotes = load_book_quotes(db_path or DEFAULT_DB_PATH)
    pairs = match_markets(markets, quotes)

    results = []
    for pair in pairs:
        fee = 0.0
        for raw in questions:
            if raw.get("token_id") and raw["token_id"] == pair.market.token_id:
                fee = float(raw.get("fee_rate", 0.0) or 0.0)
                break
        leg_a, leg_b = build_legs(
            hook, polymarket_price=pair.market.yes_price,
            polymarket_selection=pair.market.yes_team.canonical
            if pair.market.yes_team else pair.market.question,
            book=pair.book, book_odds=pair.book_decimal_odds,
            book_selection=pair.book_selection, token_id=pair.market.token_id,
            polymarket_fee=fee, gambling_win_capacity=gambling_win_capacity,
            capital_gain_capacity=capital_gain_capacity,
            prediction_is_wagering=prediction_is_wagering)
        results.append(evaluate_hybrid_arb(leg_a, leg_b, capital=capital))
    return results, pairs
