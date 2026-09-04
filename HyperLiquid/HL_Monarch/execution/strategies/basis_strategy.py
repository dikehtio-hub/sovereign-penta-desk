"""
Delta-neutral basis trade: long spot, short perp, harvest the funding.

WHY THIS IS A THIN LAYER. The scanning half of this already existed before Round
15 - `analytics/funding_arbitrage.py` does the spot-pair mapping, the OI/volume
gates, the live spread check and the amortised net-APR maths, and
`funding_backtester.py` measures whether a rate actually persisted. Rebuilding
any of that here would have produced two implementations of the same cost model
that could silently disagree. This module does only the part that was missing:
turning a scanned opportunity into a concrete, sized, two-leg position with an
explicit PnL projection.

WHAT MAKES IT DELTA-NEUTRAL - and the constraint on direction.
Positive funding means longs pay shorts. You short the perp to collect it, and
buy the same notional of spot so the price exposure cancels: 1:1, no net delta,
the funding is the entire return.

The mirror trade does NOT exist here. Negative funding would want long perp +
SHORT spot, and Hyperliquid spot has no borrow to short against. A negative-APR
row is a directional bet on funding, not a basis trade, and this module refuses
to dress it up as one - see `build_position`.

WHAT THIS IS NOT. Funding is quoted hourly and is not a term rate: it can flip
to zero or negative the hour after you enter. Every APR here is an
*extrapolation of the current instantaneous rate*, which is exactly the error
`funding_backtester.py` was written to catch. Treat `projected_pnl_usd` as
"what this pays if the rate holds", never as an expectation. Real risks this
model does not price: funding flipping sign, spot/perp basis moving against the
entry, liquidation of the perp leg if the spot leg is not margin-linked, and
withdrawal/transfer frictions between the spot and perp wallets.
"""

from typing import Any, Dict, List, Optional

from analytics.funding_arbitrage import FundingArbitrageEngine
from config.settings import (
    ARB_MAX_SPREAD_BPS,
    BASIS_HOLDING_DAYS,
    BASIS_MIN_FUNDING_APR,
    BASIS_MIN_NET_APR,
    BASIS_NOTIONAL_USD,
    MAKER_FEE_PCT,
    TAKER_FEE_PCT,
)

# Both legs are opened and closed: 4 fills. Assume the worst realistic case -
# taker in, maker out - rather than maker on all four, which would flatter the
# result on exactly the trades that are marginal.
FILLS_PER_ROUND_TRIP = 2  # per leg
LEGS = 2


def round_trip_fee_pct() -> float:
    """Total fee cost of opening and closing both legs, as a percent of one leg's notional."""
    return (TAKER_FEE_PCT + MAKER_FEE_PCT) * 100.0 * LEGS


def build_position(
    opportunity: Dict[str, Any],
    notional_usd: float = BASIS_NOTIONAL_USD,
    holding_days: float = BASIS_HOLDING_DAYS,
) -> Optional[Dict[str, Any]]:
    """
    Turn one scanned opportunity into a sized two-leg position, or None.

    Returns None - rather than a position with a warning flag - when the row
    cannot be constructed as delta-neutral. A structure that cannot be built
    should not be representable downstream.
    """
    if not opportunity.get("is_spot_backed") or not opportunity.get("spot_symbol"):
        return None
    # Direction constraint: no spot borrow, so only positive funding works.
    apr = float(opportunity.get("funding_apr") or 0.0)
    if apr <= 0:
        return None

    mark = float(opportunity.get("mark_px") or 0.0)
    if mark <= 0 or notional_usd <= 0:
        return None

    net_apr = FundingArbitrageEngine.net_apr_after_spread(
        opportunity, holding_period_days=holding_days, hedge_legs=LEGS
    )

    # Funding accrues on the perp notional only; the spot leg is an unlevered
    # hedge and pays nothing. Fees are charged on both legs.
    funding_pct = net_apr * (holding_days / 365.0)
    fee_pct = round_trip_fee_pct()
    net_pct = funding_pct - fee_pct

    return {
        "coin": opportunity["coin"],
        "spot_symbol": opportunity["spot_symbol"],
        "structure": "LONG_SPOT_SHORT_PERP",
        "mark_px": mark,
        "notional_per_leg_usd": notional_usd,
        "total_capital_usd": notional_usd * LEGS,
        "size": notional_usd / mark,
        "funding_apr": apr,
        "net_apr": net_apr,
        "spread_bps": opportunity.get("spread_bps"),
        "perp_sz_decimals": opportunity.get("perp_sz_decimals"),
        "spot_sz_decimals": opportunity.get("spot_sz_decimals"),
        "holding_days": holding_days,
        "gross_funding_usd": funding_pct / 100.0 * notional_usd,
        "fees_usd": fee_pct / 100.0 * notional_usd,
        "projected_pnl_usd": net_pct / 100.0 * notional_usd,
        "projected_return_pct": net_pct,
        # Return on the capital actually tied up, which is both legs - the
        # headline APR is quoted against one leg and overstates this ~2x.
        "return_on_capital_pct": net_pct / LEGS,
    }


def scan_basis_opportunities(
    scanner: Optional[FundingArbitrageEngine] = None,
    min_funding_apr: float = BASIS_MIN_FUNDING_APR,
    min_net_apr: float = BASIS_MIN_NET_APR,
    notional_usd: float = BASIS_NOTIONAL_USD,
    holding_days: float = BASIS_HOLDING_DAYS,
    check_spreads: bool = True,
    snapshots: Optional[List[Dict[str, Any]]] = None,
    max_spread_bps: float = ARB_MAX_SPREAD_BPS,
) -> Dict[str, Any]:
    """
    Every constructible basis trade clearing the gross bar, the net bar AND the
    spread ceiling.

    `check_spreads` defaults True here even though it costs live L2 calls: with
    no measured spread `net_apr_after_spread` returns the gross APR unchanged,
    so the net bar would be a no-op and every row would trivially "pass". A
    basis trade whose cost has not been measured has not been evaluated.

    ROUND 38 - THE CEILING REACHES EVERY COSTED ROW. The scanner applies
    `max_spread_bps` only to the head of its ranked list (ARB_SPREAD_CHECK_LIMIT
    rows); the rows costed on demand below were judged against the net bar
    alone. A wide spread amortised over a 7-day hold can still clear that bar -
    para:AVGO entered the paper book at 35.05 bps against a 25 bps ceiling with
    a net APR of 41% - so the ceiling is enforced here on whatever spread the
    row carries, whoever measured it.
    """
    scanner = scanner or FundingArbitrageEngine()
    scan = scanner.scan_funding_opportunities(
        min_apr_pct=min_funding_apr,
        snapshots=snapshots,
        check_spreads=check_spreads,
        max_spread_bps=max_spread_bps,
        holding_period_days=holding_days,
        classify_spot=True,
    )

    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for opp in scan.get("short_harvest", []):
        pos = build_position(opp, notional_usd=notional_usd, holding_days=holding_days)
        if pos is None:
            rejected.append({**opp, "basis_reject": "no spot leg - directional, not neutral"})
            continue
        # An unmeasured spread is not a zero spread. `net_apr_after_spread`
        # returns the gross APR untouched when no book was fetched, so accepting
        # such a row would pass it through a net bar it was never tested against.
        #
        # The upstream spread filter only probes the head of the ranked list, and
        # spot-backed rows are a small minority that routinely sit below that cap
        # - which is why the first live run costed neither candidate. Since the
        # candidate set here is tiny (single digits), cost them directly rather
        # than discarding them uncosted: one l2Book call each, weight 2.
        if check_spreads and not FundingArbitrageEngine.is_costed(opp):
            measured = scanner.fetch_spread_bps(opp["coin"])
            if measured is None:
                rejected.append({**opp, "basis_reject": "spread unavailable - cost unknown"})
                continue
            opp["spread_bps"] = measured
            opp["cost_measured"] = True
            pos = build_position(opp, notional_usd=notional_usd, holding_days=holding_days)
        if pos["net_apr"] < min_net_apr:
            rejected.append({
                **opp,
                "basis_reject": f"net APR {pos['net_apr']:.1f}% < {min_net_apr:.1f}% bar",
            })
            continue
        spread = opp.get("spread_bps")
        if spread is not None and float(spread) > float(max_spread_bps):
            rejected.append({
                **opp,
                "basis_reject": f"spread {float(spread):.1f}bps > {float(max_spread_bps):.1f}bps max",
            })
            continue
        accepted.append(pos)

    accepted.sort(key=lambda p: p["net_apr"], reverse=True)
    return {
        "accepted": accepted,
        "rejected": rejected,
        "min_funding_apr": min_funding_apr,
        "min_net_apr": min_net_apr,
        "max_spread_bps": max_spread_bps,
        "holding_days": holding_days,
        "notional_per_leg_usd": notional_usd,
        "total_projected_pnl_usd": sum(p["projected_pnl_usd"] for p in accepted),
    }


def format_report(result: Dict[str, Any]) -> str:
    """Human-readable summary for the `basis` CLI subcommand."""
    lines = [
        "",
        "DELTA-NEUTRAL BASIS SCAN  (long spot + short perp)",
        f"  bars: funding APR >= {result['min_funding_apr']:.0f}%, "
        f"net APR > {result['min_net_apr']:.0f}%  |  "
        f"hold {result['holding_days']:.0f}d  |  "
        f"${result['notional_per_leg_usd']:,.0f}/leg",
        "",
    ]
    accepted = result["accepted"]
    if not accepted:
        lines.append("  No constructible basis trade clears both bars right now.")
        lines.append("  (A spot-backed market with persistent >25% funding is rare; that")
        lines.append("   the scan is empty is a finding, not a failure.)")
    else:
        lines.append(f"  {'COIN':<12}{'SPOT':<12}{'GROSS':>9}{'NET':>9}{'SPRD':>8}{'PNL':>12}")
        for p in accepted:
            spread = f"{p['spread_bps']:.1f}" if p["spread_bps"] is not None else "n/a"
            lines.append(
                f"  {p['coin']:<12}{p['spot_symbol']:<12}"
                f"{p['funding_apr']:>8.1f}%{p['net_apr']:>8.1f}%{spread:>8}"
                f"{p['projected_pnl_usd']:>11,.2f}"
            )
        lines.append("")
        lines.append(f"  Total projected over {result['holding_days']:.0f}d: "
                     f"${result['total_projected_pnl_usd']:,.2f}")
        lines.append("  Projection assumes the CURRENT hourly rate persists. It usually")
        lines.append("  does not - check `python main.py backtest` before sizing anything.")

    rejected = result["rejected"]
    if rejected:
        lines.append("")
        lines.append(f"  Rejected ({len(rejected)}):")
        for r in rejected[:8]:
            lines.append(f"    {r['coin']:<12} {r.get('basis_reject', '')}")
    lines.append("")
    return "\n".join(lines)
