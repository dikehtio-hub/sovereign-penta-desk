"""
Funding Rate Arbitrage Opportunity Matrix for HL_Monarch.
Scans all 436 perpetual assets across all DEXes to detect extreme funding yields
and delta-neutral basis/funding harvest opportunities.

Headline APR alone is not tradeability: the most extreme rates sit on illiquid or
near-dead markets where the spread eats the yield and size cannot be filled. Every
opportunity is therefore scored against an open-interest floor, a volume floor, and
(optionally) a live order-book spread check before being called tradeable.
"""
from typing import List, Dict, Any, Optional, Set
from analytics.market_intelligence import MarketIntelligence
from storage.repository import MarketRepository
from api.rest_client import HyperliquidRestClient
from analytics.liquidation_engine import LiquidationEngine
from config.settings import (
    ARB_MIN_NOTIONAL_OI,
    ARB_MIN_DAY_VOLUME,
    ARB_MAX_SPREAD_BPS,
    ARB_SPREAD_CHECK_LIMIT,
    ARB_DEFAULT_HOLDING_DAYS,
    ARB_FUNDING_INTERVAL_HOURS,
)


# Hyperliquid lists most large caps on spot only as bridged/wrapped tokens
# (UBTC, UETH, USOL), so a perp's base name alone does not settle whether a spot
# hedge exists. Both forms are checked before a market is called spot-backed.
SPOT_WRAPPER_PREFIXES = ("U",)


def perp_base_symbol(coin: str) -> str:
    """Strip the HIP-3 dex prefix: 'xyz:GOLD' -> 'GOLD', 'BTC' -> 'BTC'."""
    return coin.split(":", 1)[1] if ":" in coin else coin


def spot_symbol_for(coin: str, spot_universe: Set[str]) -> Optional[str]:
    """
    The spot ticker that could hedge this perp, or None when none exists.

    Without a spot leg the position is not a basis arbitrage at all - it is a
    directional bet that happens to earn funding, which is a materially different
    risk profile and must not be labelled "delta-neutral".
    """
    base = perp_base_symbol(coin)
    if base in spot_universe:
        return base
    for prefix in SPOT_WRAPPER_PREFIXES:
        wrapped = f"{prefix}{base}"
        if wrapped in spot_universe:
            return wrapped
    return None


class FundingArbitrageEngine:
    def __init__(self, client: Optional[HyperliquidRestClient] = None):
        self.repo = MarketRepository()
        self.client = client or HyperliquidRestClient()
        self._spot_universe: Optional[Set[str]] = None

    def get_spot_universe(self, refresh: bool = False) -> Set[str]:
        """
        Tradeable spot tickers, cached for the life of the engine.

        Returns an empty set if the lookup fails; callers treat that as "unknown"
        and fall back to not claiming spot backing, never to claiming it falsely.
        """
        if self._spot_universe is not None and not refresh:
            return self._spot_universe
        try:
            meta = self.client.get_spot_meta()
            self._spot_universe = {
                str(t.get("name", "")).upper() for t in (meta or {}).get("tokens", []) if t.get("name")
            }
        except Exception:
            self._spot_universe = set()
        return self._spot_universe

    def _perp_sz_decimals(self, dex: Optional[str] = None) -> Dict[str, int]:
        """
        Cached {coin: szDecimals} for perps, per dex.

        Dex-aware because coins carry a prefix (`para:ANSEM`, `xyz:HOOD`) and the
        default metaAndAssetCtxs call returns only the MAIN universe - every
        alternate-dex perp came back with unknown precision until this was split
        per dex. Each miss silently downgrades the sizing guard to whatever the
        spot leg alone reports.
        """
        if getattr(self, "_perp_dec_cache", None) is None:
            self._perp_dec_cache = {}
        key = dex or "main"
        if key not in self._perp_dec_cache:
            table = {}
            try:
                meta = self.client.get_meta_and_asset_ctxs(dex=dex) if dex                     else self.client.get_meta_and_asset_ctxs()
                for u in (meta[0].get("universe") or []):
                    if u.get("name") is not None and u.get("szDecimals") is not None:
                        table[u["name"]] = int(u["szDecimals"])
            except Exception:
                # Unknown precision is handled downstream by matched_leg_size,
                # which sizes off whichever leg IS known rather than guessing.
                table = {}
            self._perp_dec_cache[key] = table
        return self._perp_dec_cache[key]

    def _spot_sz_decimals(self) -> Dict[str, int]:
        """Cached {token: szDecimals} for spot tokens."""
        if getattr(self, "_spot_dec_cache", None) is None:
            self._spot_dec_cache = {}
            try:
                for t in (self.client.get_spot_meta().get("tokens") or []):
                    if t.get("name") is not None and t.get("szDecimals") is not None:
                        self._spot_dec_cache[t["name"]] = int(t["szDecimals"])
            except Exception:
                self._spot_dec_cache = {}
        return self._spot_dec_cache

    def _perp_decimals_for(self, coin: str, dex: Optional[str]) -> Optional[int]:
        """szDecimals for one perp, tolerant of prefixed vs bare naming."""
        table = self._perp_sz_decimals(dex if dex not in (None, "", "main") else None)
        if coin in table:
            return table[coin]
        return table.get(perp_base_symbol(coin))

    def scan_funding_opportunities(
        self,
        min_apr_pct: float = 10.0,
        snapshots: Optional[List[Dict[str, Any]]] = None,
        min_notional_oi: float = ARB_MIN_NOTIONAL_OI,
        min_day_volume: float = ARB_MIN_DAY_VOLUME,
        check_spreads: bool = False,
        max_spread_bps: float = ARB_MAX_SPREAD_BPS,
        spread_check_limit: int = ARB_SPREAD_CHECK_LIMIT,
        holding_period_days: float = ARB_DEFAULT_HOLDING_DAYS,
        classify_spot: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scan market snapshots for positive (short harvest) and negative (long harvest) funding yields.

        Args:
            min_notional_oi: open-interest floor in USD. A market nobody holds cannot
                absorb a delta-neutral position regardless of its quoted funding.
            min_day_volume: 24h volume floor in USD. OI without turnover means the
                position cannot be exited.
            check_spreads: fetch live L2 books for the top candidates and reject any
                whose spread is too wide to harvest. Costs one l2Book call (weight 2)
                per checked market, so it is opt-in and capped.
            holding_period_days: horizon the one-off spread cost is amortised over
                when computing net APR. Longer holds dilute the entry/exit cost.
            classify_spot: tag each opportunity with whether a spot hedge exists.
                Without one the trade is directional, not delta-neutral.

        Returns:
            {
                "long_harvest": [...],   # High negative funding -> Long pays you funding
                "short_harvest": [...],  # High positive funding -> Short pays you funding
                "rejected": [...]        # Passed the APR bar but failed a liquidity gate
            }
        """
        if snapshots is None:
            snapshots = self.repo.get_latest_snapshots()

        long_harvest: List[Dict[str, Any]] = []
        short_harvest: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        spot_universe = self.get_spot_universe() if classify_spot else set()

        for s in snapshots:
            funding_1h = float(s.get("funding_rate") or 0.0)
            mark_px = float(s.get("mark_px") or 0.0)
            ntl_oi = float(s.get("notional_oi") or 0.0)
            day_vol = float(s.get("day_ntl_vlm") or 0.0)
            coin = s.get("coin", "")

            if mark_px <= 0:
                continue

            apr = MarketIntelligence.calculate_annualized_funding_apr(funding_1h)
            if abs(apr) < min_apr_pct:
                continue

            item = {
                "coin": coin,
                "dex": s.get("dex", "main"),
                "mark_px": mark_px,
                "notional_oi": ntl_oi,
                "day_vol": day_vol,
                "funding_1h": funding_1h,
                "funding_apr": apr,
                "daily_yield_pct": (funding_1h * 24.0) * 100.0,
                "spread_bps": None,
                # Explicit so no consumer can mistake an uncosted gross APR for a
                # net one. `net_apr_after_spread` deliberately returns gross when
                # no book was fetched (never fabricate a cost), which means the
                # net bar is a silent no-op on uncosted rows. The `arb` command
                # legitimately displays gross; a BASIS trade must not, so it
                # checks this flag and refuses - see basis_strategy.
                "cost_measured": False,
                "tradeable": True,
                "reject_reason": None,
                "holding_period_days": holding_period_days,
                "is_spot_backed": None,
                "spot_symbol": None,
                # Size precision per leg. They frequently disagree (MON: perp 0,
                # spot 2), and a fractional size sent to a whole-unit perp is a
                # rejected leg against a filled one - see execution/sizing.py.
                # Alt-dex universes key on the FULL prefixed name (para:TOTAL2),
                # the main universe on the bare one - so try both.
                "perp_sz_decimals": self._perp_decimals_for(coin, s.get("dex")),
                "spot_sz_decimals": None,
            }

            if classify_spot:
                spot = spot_symbol_for(coin, spot_universe)
                item["spot_symbol"] = spot
                item["is_spot_backed"] = spot is not None
                if spot:
                    item["spot_sz_decimals"] = self._spot_sz_decimals().get(
                        perp_base_symbol(coin))

            # Liquidity gates. An extreme rate on a market with no OI or no turnover
            # is a quoting artifact, not an edge.
            if ntl_oi < min_notional_oi:
                item["tradeable"] = False
                item["reject_reason"] = f"OI {ntl_oi:,.0f} < {min_notional_oi:,.0f} floor"
            elif day_vol < min_day_volume:
                item["tradeable"] = False
                item["reject_reason"] = f"24h volume {day_vol:,.0f} < {min_day_volume:,.0f} floor"

            spot_backed = bool(item.get("is_spot_backed"))
            spot_sym = item.get("spot_symbol")
            if apr >= min_apr_pct:
                # Positive funding: Longs pay Shorts. Action: SHORT the perp.
                item["strategy"] = "SHORT_HARVEST"
                item["recommendation"] = (
                    f"Short Perp + Long {spot_sym} spot" if spot_backed
                    else "Short Perp (DIRECTIONAL - no spot hedge)"
                )
                bucket = short_harvest
            else:
                # Negative funding: Shorts pay Longs. Action: LONG the perp.
                item["strategy"] = "LONG_HARVEST"
                item["recommendation"] = (
                    f"Long Perp + Short {spot_sym} spot" if spot_backed
                    else "Long Perp (DIRECTIONAL - no spot hedge)"
                )
                bucket = long_harvest
            item["trade_type"] = "BASIS_ARB" if spot_backed else "DIRECTIONAL_FUNDING"

            (bucket if item["tradeable"] else rejected).append(item)

        # Sort by absolute APR yield
        short_harvest.sort(key=lambda x: x["funding_apr"], reverse=True)
        long_harvest.sort(key=lambda x: x["funding_apr"], reverse=False)
        rejected.sort(key=lambda x: abs(x["funding_apr"]), reverse=True)

        if check_spreads:
            self._apply_spread_filter(
                short_harvest, long_harvest, rejected,
                max_spread_bps=max_spread_bps,
                limit=spread_check_limit,
            )

        return {
            "short_harvest": short_harvest,
            "long_harvest": long_harvest,
            "rejected": rejected,
        }

    def _apply_spread_filter(
        self,
        short_harvest: List[Dict[str, Any]],
        long_harvest: List[Dict[str, Any]],
        rejected: List[Dict[str, Any]],
        max_spread_bps: float,
        limit: int,
    ):
        """
        Price-check the top candidates against the live book, in place.

        Only the head of each list is checked: these are ranked by APR, the tail is
        never displayed, and each check spends real rate-limit budget.
        """
        for bucket in (short_harvest, long_harvest):
            checked = 0
            for item in list(bucket):
                if checked >= limit:
                    break
                checked += 1
                spread_bps = self.fetch_spread_bps(item["coin"])
                item["spread_bps"] = spread_bps
                item["cost_measured"] = spread_bps is not None
                if spread_bps is None:
                    # No book / fetch failed: leave it listed but unverified rather
                    # than silently dropping a possibly good opportunity.
                    continue
                if spread_bps > max_spread_bps:
                    item["tradeable"] = False
                    item["reject_reason"] = f"spread {spread_bps:.1f}bps > {max_spread_bps:.0f}bps max"
                    bucket.remove(item)
                    rejected.append(item)

        rejected.sort(key=lambda x: abs(x["funding_apr"]), reverse=True)

    def fetch_spread_bps(self, coin: str) -> Optional[float]:
        """Live top-of-book spread in basis points, or None if unavailable."""
        try:
            book = self.client.get_l2_book(coin)
            depth = LiquidationEngine.analyze_orderbook_depth(coin, book)
            if not depth:
                return None
            return float(depth.get("spread_bps") or 0.0)
        except Exception:
            return None

    @staticmethod
    def is_costed(item: Dict[str, Any]) -> bool:
        """Whether this row's execution cost was actually measured, not assumed."""
        return item.get("spread_bps") is not None

    @staticmethod
    def net_apr_after_spread(
        item: Dict[str, Any],
        holding_period_days: Optional[float] = None,
        hedge_legs: Optional[int] = None,
    ) -> float:
        """
        Funding APR net of execution cost, amortised over a realistic hold.

        Cost model. Opening and closing costs roughly one full spread per leg
        (crossing a half-spread each way). A delta-neutral basis trade has two
        legs - perp and spot - so it pays that twice; a directional funding trade
        has one. That charge is a *one-off*, so annualising it means spreading it
        over the holding period: a 7-day hold dilutes it ~7x versus a 1-day hold,
        which is why the previous 1-day assumption over-penalised every row.

            annualised_cost% = spread% x legs x (365 / holding_days)

        The result reduces the *magnitude* of the yield in both directions: a
        long-harvest opportunity is quoted as a negative APR, and its cost makes
        it less negative, not more.

        Returns the gross APR unchanged when no spread has been measured, so an
        unverified row is never given a fabricated cost.
        """
        apr = float(item.get("funding_apr") or 0.0)
        spread_bps = item.get("spread_bps")
        if spread_bps is None:
            return apr

        days = holding_period_days or item.get("holding_period_days") or ARB_DEFAULT_HOLDING_DAYS
        days = max(float(days), 1e-6)
        if hedge_legs is None:
            hedge_legs = 2 if item.get("is_spot_backed") else 1

        spread_pct = float(spread_bps) / 100.0
        annualised_cost_pct = spread_pct * hedge_legs * (365.0 / days)
        return apr - annualised_cost_pct if apr > 0 else apr + annualised_cost_pct

    @staticmethod
    def expected_pnl_pct(item: Dict[str, Any], holding_period_days: Optional[float] = None) -> float:
        """
        Expected funding PnL over the holding period itself, in percent of notional.

        More decision-useful than an annualised rate for a position nobody intends
        to hold for a year: it answers "what does this actually pay me this week,
        after getting in and out".
        """
        days = holding_period_days or item.get("holding_period_days") or ARB_DEFAULT_HOLDING_DAYS
        days = max(float(days), 1e-6)
        net_apr = FundingArbitrageEngine.net_apr_after_spread(item, holding_period_days=days)
        return net_apr * (days / 365.0)

    @staticmethod
    def funding_payments_over(days: float) -> int:
        """How many funding settlements a position of this length collects."""
        return max(0, int((days * 24.0) / ARB_FUNDING_INTERVAL_HOURS))
