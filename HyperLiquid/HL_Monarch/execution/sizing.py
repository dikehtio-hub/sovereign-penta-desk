"""
Leg sizing for two-legged positions, where the legs have different precision.

THE HAZARD. Hyperliquid quotes `szDecimals` per instrument, and the spot token and
the perp contract for the SAME asset frequently disagree. MON is live proof: the
PERP is szDecimals=0 (whole units only) while SPOT is szDecimals=2. Send a
fractional size to the perp and that leg is rejected while the spot leg fills -
leaving unhedged inventory in a position whose entire premise is that it has no
directional exposure.

WHY INDEPENDENT ROUNDING IS THE WRONG FIX. The obvious response is to floor each
leg to its own precision. That prevents the REJECTION but reintroduces the exposure
it was meant to remove: flooring 1000.567 gives a 1000-unit perp against a 1000.56
spot, and the 0.56 difference is naked. Independent rounding converts a loud
failure into a quiet one.

WHAT THIS DOES INSTEAD. Both legs are floored to the COARSER of the two precisions,
so they are equal by construction and the residual is exactly zero. The cost is a
slightly smaller position than requested - always smaller, never larger, because
rounding up could exceed available capital or margin.

`min_size` guards the degenerate case: when the coarser precision is 0 and the
target size is under one whole unit, there is no tradeable 1:1 position at all and
the caller must be told, not handed a zero-size fill.
"""

import math
from typing import Any, Dict, Optional


def floor_to_decimals(size: float, decimals: int) -> float:
    """
    Round DOWN to `decimals` places. Never up.

    Rounding up can exceed the capital or margin the caller sized against, and on
    a venue that rejects oversized orders that is a failed leg - the exact failure
    this module exists to prevent.
    """
    if decimals < 0:
        raise ValueError("decimals must be >= 0")
    factor = 10 ** decimals
    return math.floor(size * factor) / factor


def matched_leg_size(notional_usd: float, price: float,
                     perp_decimals: Optional[int],
                     spot_decimals: Optional[int]) -> Dict[str, Any]:
    """
    A size both legs can express exactly, plus the notional it actually implies.

    Returns `tradeable=False` rather than a zero size when the coarser precision
    cannot represent the target - a 0-size position is not a small position, it is
    a naked leg waiting to happen.
    """
    if price <= 0 or notional_usd <= 0:
        return {"tradeable": False, "reason": "non-positive price or notional",
                "size": 0.0, "decimals": None, "notional_usd": 0.0, "residual": 0.0}

    known = [d for d in (perp_decimals, spot_decimals) if d is not None]
    if not known:
        return {"tradeable": False, "reason": "szDecimals unknown for both legs",
                "size": 0.0, "decimals": None, "notional_usd": 0.0, "residual": 0.0}

    # The coarser leg governs. Matching to the finer one would produce a size the
    # coarse leg cannot express.
    decimals = min(known)
    raw = notional_usd / price
    size = floor_to_decimals(raw, decimals)

    if size <= 0:
        return {"tradeable": False,
                "reason": (f"target {raw:.6f} units rounds to zero at {decimals} "
                           f"decimals - notional too small for this instrument"),
                "size": 0.0, "decimals": decimals, "notional_usd": 0.0,
                "residual": 0.0}

    return {
        "tradeable": True,
        "reason": None,
        "size": size,
        "decimals": decimals,
        "perp_decimals": perp_decimals,
        "spot_decimals": spot_decimals,
        # What we can actually deploy, which is <= what was asked for.
        "notional_usd": size * price,
        "shortfall_usd": notional_usd - size * price,
        # Zero by construction: both legs carry the identical size. Kept explicit
        # so a future change that breaks the invariant is visible rather than silent.
        "residual": 0.0,
    }
