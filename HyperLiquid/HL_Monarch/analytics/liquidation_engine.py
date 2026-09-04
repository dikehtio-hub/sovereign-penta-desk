"""
Liquidation Intelligence & Cluster Estimation Engine.
Identifies active liquidations and computes theoretical liquidation walls (Liquidation Heatmaps).
"""
import time
from typing import List, Dict, Any, Optional
from config.settings import (
    DEFAULT_LEVERAGE_TIERS,
    MAINTENANCE_MARGIN_FRACTIONS,
    EXOTIC_SWEEP_MIN_NOTIONAL,
    EXOTIC_SWEEP_MIN_SLIPPAGE_PCT,
    MAJOR_SWEEP_MIN_NOTIONAL,
    MAJOR_SWEEP_MIN_SLIPPAGE_PCT,
    WHALE_ORDER_MIN_NOTIONAL,
)

class LiquidationEngine:
    """
    Analyzes trades, blocks, and open interest to detect and model liquidation events.
    """

    @staticmethod
    def detect_liquidation_trade(trade: Dict[str, Any], mark_px: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Evaluate if a trade represents a liquidation or large sweep.
        """
        px = float(trade.get("px", 0))
        sz = float(trade.get("sz", 0))
        side = trade.get("side", "")
        notional = px * sz

        is_liq = False
        source = "trade_flow"
        note = ""

        # Aggressive fill printing away from mark. Two tiers, because a single
        # notional floor cannot serve both ends of the universe: the $25k/0.4%
        # rule was calibrated on BTC/ETH and locked exotics out entirely. Measured
        # over 10,443 exotic fills, the median was $69 and only 2 cleared $25k -
        # so SKR logged 3,046 trades and zero liquidation events, which is why the
        # precedence validator had 46 flagged windows and nothing to score.
        #
        # Small size with large slippage is the exotic signature: thin books mean a
        # forced exit moves price hard without needing size. Demanding 1.0% rather
        # than 0.4% keeps the small-notional tier from admitting ordinary noise.
        if mark_px and mark_px > 0:
            price_impact_pct = abs(px - mark_px) / mark_px * 100.0
            exotic_sweep = notional >= EXOTIC_SWEEP_MIN_NOTIONAL and price_impact_pct >= EXOTIC_SWEEP_MIN_SLIPPAGE_PCT
            major_sweep = notional >= MAJOR_SWEEP_MIN_NOTIONAL and price_impact_pct >= MAJOR_SWEEP_MIN_SLIPPAGE_PCT
            if exotic_sweep or major_sweep:
                is_liq = True
                source = "trade_sweep"
                note = f"High-impact sweep ({price_impact_pct:.2f}% slippage vs mark)"

        # Explicit liquidation users or metadata
        users = trade.get("users", [])
        if any("0x0000000000000000000000000000000000000000" in str(u) for u in users):
            is_liq = True
            source = "liquidation_fill"
            note = "Protocol backstop liquidation fill"

        # Whale-order fallback: size alone, regardless of slippage.
        if is_liq or notional >= WHALE_ORDER_MIN_NOTIONAL:
            return {
                "coin": trade.get("coin"),
                "side": side,
                "px": px,
                "sz": sz,
                "notional": notional,
                "time": trade.get("time", int(time.time() * 1000)),
                "source": source,
                "note": note or f"Whale order (${notional:,.2f})"
            }
        return None

    @staticmethod
    def calculate_liquidation_clusters(
        coin: str,
        mark_px: float,
        open_interest: float,
        max_leverage: int = 20,
        leverage_tiers: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Compute estimated long and short liquidation clusters based on OI and leverage tiers.
        Formula for Long Liq: P_liq = P_entry * (1 - 1/Lev + MMR)
        Formula for Short Liq: P_liq = P_entry * (1 + 1/Lev - MMR)
        """
        if mark_px <= 0 or open_interest <= 0:
            return []

        tiers = [lev for lev in (leverage_tiers or DEFAULT_LEVERAGE_TIERS) if lev <= max_leverage]
        if not tiers:
            tiers = [max_leverage]

        now_ts = int(time.time() * 1000)
        total_notional_oi = open_interest * mark_px
        clusters = []

        # Assume OI distribution across leverage tiers
        tier_weight = 1.0 / len(tiers)

        for lev in tiers:
            mmr = MAINTENANCE_MARGIN_FRACTIONS.get(lev, 1.0 / (lev * 2))
            
            # Estimated Long Liquidation Price (Longs get liquidated below mark price)
            long_liq_factor = 1.0 - (1.0 / lev) + mmr
            long_liq_px = max(0.0001, mark_px * long_liq_factor)
            long_distance_pct = (mark_px - long_liq_px) / mark_px * 100.0

            # Estimated Short Liquidation Price (Shorts get liquidated above mark price)
            short_liq_factor = 1.0 + (1.0 / lev) - mmr
            short_liq_px = mark_px * short_liq_factor
            short_distance_pct = (short_liq_px - mark_px) / mark_px * 100.0

            # Estimated notional volume concentrated at this tier
            tier_notional = total_notional_oi * tier_weight * 0.5

            # Risk classification based on proximity to mark price
            long_risk = "CRITICAL" if long_distance_pct < 2.5 else ("HIGH" if long_distance_pct < 5.0 else "MEDIUM")
            short_risk = "CRITICAL" if short_distance_pct < 2.5 else ("HIGH" if short_distance_pct < 5.0 else "MEDIUM")

            clusters.append({
                "timestamp": now_ts,
                "coin": coin,
                "side": "LONG_LIQ",
                "leverage": lev,
                "estimated_px": round(long_liq_px, 4),
                "distance_pct": round(long_distance_pct, 2),
                "estimated_notional": round(tier_notional, 2),
                "risk_level": long_risk
            })

            clusters.append({
                "timestamp": now_ts,
                "coin": coin,
                "side": "SHORT_LIQ",
                "leverage": lev,
                "estimated_px": round(short_liq_px, 4),
                "distance_pct": round(short_distance_pct, 2),
                "estimated_notional": round(tier_notional, 2),
                "risk_level": short_risk
            })

        return clusters

    @staticmethod
    def analyze_orderbook_depth(coin: str, book: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate spreads, 1% depth, and bid/ask volume imbalance from L2 book.
        """
        levels = book.get("levels", [[], []])
        bids = levels[0] if len(levels) > 0 else []
        asks = levels[1] if len(levels) > 1 else []

        if not bids or not asks:
            return {}

        best_bid = float(bids[0]["px"])
        best_ask = float(asks[0]["px"])
        mid_px = (best_bid + best_ask) / 2.0
        spread = best_ask - best_bid
        spread_bps = (spread / mid_px) * 10000.0 if mid_px > 0 else 0.0

        bid_depth_1pct = 0.0
        bid_depth_total = 0.0
        for b in bids:
            px = float(b["px"])
            sz = float(b["sz"])
            ntl = px * sz
            bid_depth_total += ntl
            if px >= mid_px * 0.99:
                bid_depth_1pct += ntl

        ask_depth_1pct = 0.0
        ask_depth_total = 0.0
        for a in asks:
            px = float(a["px"])
            sz = float(a["sz"])
            ntl = px * sz
            ask_depth_total += ntl
            if px <= mid_px * 1.01:
                ask_depth_1pct += ntl

        imbalance = (bid_depth_1pct / (bid_depth_1pct + ask_depth_1pct)) if (bid_depth_1pct + ask_depth_1pct) > 0 else 0.5

        return {
            "timestamp": int(time.time() * 1000),
            "coin": coin,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "spread_bps": spread_bps,
            "bid_depth_1pct": bid_depth_1pct,
            "ask_depth_1pct": ask_depth_1pct,
            "bid_depth_total": bid_depth_total,
            "ask_depth_total": ask_depth_total,
            "imbalance_ratio": imbalance
        }
