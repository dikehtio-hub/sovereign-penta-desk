"""
Funding Rate Arbitrage Opportunity Matrix for HL_Monarch.
Scans all 436 perpetual assets across all DEXes to detect extreme funding yields
and delta-neutral basis/funding harvest opportunities.

Headline APR alone is not tradeability: the most extreme rates sit on illiquid or
near-dead markets where the spread eats the yield and size cannot be filled. Every
opportunity is therefore scored against an open-interest floor, a volume floor, and
(optionally) a live order-book spread check before being called tradeable.
"""
from typing import List, Dict, Any, Optional, Set, Tuple
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
    SPOT_MIN_DAY_VOLUME,
    SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE,
    ALLOW_SYNTHETIC_TRADFI_BASIS,
    SYNTHETIC_TRADFI_SYMBOLS,
    SPOT_NON_BASIS_TOKENS,
)


# Hyperliquid lists most large caps on spot only as bridged/wrapped tokens
# (UBTC, UETH, USOL), so a perp's base name alone does not settle whether a spot
# hedge exists. Both forms are checked before a market is called spot-backed.
SPOT_WRAPPER_PREFIXES = ("U",)

# Round 40 (Ruling 40-1): wrappers whose spot name is NOT "U" + the perp name.
# Authoritative and hand-kept - never fuzzy-matched on fullName, because a wrong
# alias hedges one asset with another. Verified on the live token list on
# 2026-09-04: UFART "Unit Fartcoin" ($570k/day), HPENGU "Pudgy Penguins", XMR1
# "XMR - Wagyu.xyz" ($16M/day), FXMR "Freedom XMR", FXRP. IXRP and WXRP exist
# with no pair today; the volume floor keeps them out until they trade.
SPOT_SYMBOL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "FARTCOIN": ("UFART",),
    "PENGU": ("HPENGU",),
    "XMR": ("XMR1", "FXMR"),
    "XRP": ("FXRP", "IXRP", "WXRP"),
    # Round 42 (Ruling 42-1): UUUSPX is "Unit SPX6900" - the memecoin the main-dex
    # SPX perp prices ($0.6009 beside $0.6007), NOT the S&P 500 (that is km:US500).
    "SPX": ("UUUSPX",),
}

# Round 41 (Ruling 41-1): tokenised EQUITIES. NVDAX "Wrapped NVIDIA xStock",
# TSLAX "Wrapped Tesla xStock", EQNVDA/EQTSLA "EQX Tokenized". They price a stock
# that trades five days a week while the HIP-3 perp trades seven. Reachable only
# while settings.ALLOW_SYNTHETIC_TRADFI_BASIS is True - and since Round 42 the
# perp itself is quarantined first (see is_synthetic_tradfi), so these matter
# only once that switch is on.
SYNTHETIC_TRADFI_ALIASES: Dict[str, Tuple[str, ...]] = {
    "NVDA": ("NVDAX", "EQNVDA"),
    "TSLA": ("TSLAX", "EQTSLA"),
}


def perp_base_symbol(coin: str) -> str:
    """Strip the HIP-3 dex prefix: 'xyz:GOLD' -> 'GOLD', 'BTC' -> 'BTC'."""
    return coin.split(":", 1)[1] if ":" in coin else coin


def is_synthetic_tradfi(coin: str, allow_synthetic_tradfi: Optional[bool] = None) -> bool:
    """
    True when this perp prices a stock, index, commodity, bond or FX pair AND the
    quarantine is in force (Round 42, Ruling 42-1). The underlying trades on an
    exchange with a weekend and a closing bell; the perp trades 24/7. A basis
    hedge across that seam is not the delta-neutral trade this strategy makes.
    """
    allow = ALLOW_SYNTHETIC_TRADFI_BASIS if allow_synthetic_tradfi is None else bool(allow_synthetic_tradfi)
    return (not allow) and perp_base_symbol(coin).upper() in SYNTHETIC_TRADFI_SYMBOLS


def spot_symbol_candidates(coin: str, allow_synthetic_tradfi: Optional[bool] = None) -> List[str]:
    """
    Every spot name that could hedge this perp, in precedence order, deduplicated.

    Round 41: the "U" wrapper comes BEFORE the bare name. Unit tokens are the
    canonical bridged assets; a bare-named token of the same symbol is usually a
    third-party deployment (ANSEM $1.5k/day beside UANSEM $928k). Then the
    crypto-native aliases, then - only if allowed - the tokenised equities.

    Round 42: a quarantined TradFi perp has NO candidates at all. The Round 41
    quarantine covered only the equity aliases, which left the bare-name and
    wrapper paths open; this closes the perp, not the token.
    """
    if is_synthetic_tradfi(coin, allow_synthetic_tradfi):
        return []
    allow = ALLOW_SYNTHETIC_TRADFI_BASIS if allow_synthetic_tradfi is None else bool(allow_synthetic_tradfi)
    base = perp_base_symbol(coin).upper()
    ordered = [prefix + base for prefix in SPOT_WRAPPER_PREFIXES] + [base]
    ordered += list(SPOT_SYMBOL_ALIASES.get(base, ()))
    if allow:
        ordered += list(SYNTHETIC_TRADFI_ALIASES.get(base, ()))
    out: List[str] = []
    for sym in ordered:
        if sym and sym not in out:
            out.append(sym)
    return out


def spot_symbol_for(coin: str, spot_universe: Set[str],
                    spot_volumes: Optional[Dict[str, float]] = None,
                    allow_synthetic_tradfi: Optional[bool] = None) -> Optional[str]:
    """
    The spot ticker that could hedge this perp, or None when none exists.

    Without a spot leg the position is not a basis arbitrage at all - it is a
    directional bet that happens to earn funding, which is a materially different
    risk profile and must not be labelled "delta-neutral".

    Round 40 (Ruling 40-2): when several candidates are in the universe and
    `spot_volumes` (token -> 24h notional) is supplied, the MOST LIQUID one is
    the hedge - para:ANSEM resolves to UANSEM ($928k/day), not the bare ANSEM
    ($1.5k/day) it was first booked against. Ties, and calls without volumes,
    follow the precedence order: "U" wrapper, bare name, aliases (Round 41).
    A synthetic TradFi perp has no hedge at all unless `allow_synthetic_tradfi`
    (default: settings.ALLOW_SYNTHETIC_TRADFI_BASIS) says otherwise.
    """
    candidates = spot_symbol_candidates(coin, allow_synthetic_tradfi=allow_synthetic_tradfi)
    present = [sym for sym in candidates if sym in spot_universe]
    if not present:
        return None
    if spot_volumes:
        def liquidity(sym: str):
            try:
                volume = float(spot_volumes.get(sym, 0.0) or 0.0)
            except (TypeError, ValueError):
                volume = 0.0
            return (volume, -present.index(sym))            # ties keep the precedence order
        return max(present, key=liquidity)
    return present[0]


def effective_spot_min_volume(cfg: Any = None) -> float:
    """
    The spot-leg volume floor in force (Ruling 41-3): the larger of
    SPOT_MIN_DAY_VOLUME and SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE x the configured
    per-leg notional. A $10k leg needs a $50k/day pair; a $25k leg $125k. Reads
    the hot-reloaded Bot_Config when no `cfg` is given; falls back to the
    constant if the config is unreadable.
    """
    if cfg is None:
        try:
            from config.dynamic_config import get_dynamic_config
            cfg = get_dynamic_config()
        except Exception:
            cfg = None
    try:
        notional = float(getattr(cfg, "basis_notional_usd", 0.0) or 0.0)
    except (TypeError, ValueError):
        notional = 0.0
    return max(float(SPOT_MIN_DAY_VOLUME), notional * float(SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE))


class FundingArbitrageEngine:
    def __init__(self, client: Optional[HyperliquidRestClient] = None):
        self.repo = MarketRepository()
        self.client = client or HyperliquidRestClient()
        self._spot_volumes: Optional[Dict[str, float]] = None

    def get_spot_volumes(self, refresh: bool = False) -> Optional[Dict[str, float]]:
        """
        {TOKEN: best 24h notional volume across its spot pairs}, cached for the
        life of the engine; None when the lookup failed (not cached, so the next
        call retries).

        ROUND 39. Two facts about the live payload that a naive parse gets wrong:
        `universe[i].tokens` holds token INDEX fields, not list positions, and the
        asset contexts are NOT aligned with the pair list (718 contexts for 326
        pairs on 2026-09-04) - a context is matched to its pair by `coin` name. A
        token that appears in no pair at all (COIN, NVDA) is a shell and gets no
        entry, so it can never be called spot-backed.
        """
        if self._spot_volumes is not None and not refresh:
            return self._spot_volumes
        try:
            meta, ctxs = self.client.get_spot_meta_and_asset_ctxs()
            names: Dict[int, str] = {}
            for t in (meta or {}).get("tokens", []) or []:
                if t.get("name") is not None and t.get("index") is not None:
                    names[int(t["index"])] = str(t["name"]).upper()
            pair_volume: Dict[str, float] = {}
            for ctx in ctxs or []:
                try:
                    pair_volume[str(ctx.get("coin"))] = float(ctx.get("dayNtlVlm") or 0.0)
                except (TypeError, ValueError, AttributeError):
                    continue
            volumes: Dict[str, float] = {}
            for pair in (meta or {}).get("universe", []) or []:
                refs = pair.get("tokens") or []
                base = names.get(int(refs[0])) if refs else None
                if base is None:
                    continue
                volumes[base] = max(volumes.get(base, 0.0), pair_volume.get(str(pair.get("name")), 0.0))
        except Exception:
            return None
        self._spot_volumes = volumes
        return volumes

    def get_spot_universe(self, refresh: bool = False,
                          min_spot_volume: Optional[float] = None) -> Set[str]:
        """
        Spot tokens with a TRADEABLE pair: best pair 24h notional >= `min_spot_volume`
        (default: effective_spot_min_volume(), which scales with the configured leg).

        Before Round 39 this was every token name in spotMeta, and a token is not
        a market: TSLA and AVGO spot turned over $0 while their HIP-3 perps traded
        tens of millions, so the "hedge" the harvester booked against them could
        not have been filled. Returns an empty set if the lookup fails; callers
        treat that as "unknown" and never claim spot backing on it.
        """
        volumes = self.get_spot_volumes(refresh=refresh)
        if not volumes:
            return set()
        floor = float(min_spot_volume) if min_spot_volume is not None else effective_spot_min_volume()
        return {token for token, volume in volumes.items() if volume >= floor}

    def get_unmapped_liquid_spot(self, perp_coins: Optional[List[str]] = None,
                                 min_spot_volume: Optional[float] = None,
                                 refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Liquid spot tokens that NO perp resolves to, most liquid first (Ruling 41-4).

        A hand-kept alias table goes stale silently: a new wrapper lists, trades
        millions, and the harvester never sees it. Each row here is either a
        wrapper missing from SPOT_SYMBOL_ALIASES (verify its fullName on the live
        token list before adding it) or an asset with no perp, which is nothing to
        harvest. Every candidate name a perp could use counts as mapped, including
        quarantined equity aliases - NVDAX is mapped-but-blocked, not missing - and
        stablecoins are left out because they are never a basis leg.
        """
        volumes = self.get_spot_volumes(refresh=refresh) or {}
        floor = float(min_spot_volume) if min_spot_volume is not None else effective_spot_min_volume()
        liquid = {token for token, volume in volumes.items() if volume >= floor}
        if perp_coins is None:
            try:
                perp_coins = [str(s.get("coin") or "") for s in self.repo.get_latest_snapshots()]
            except Exception:
                perp_coins = []
        mapped: Set[str] = set()
        for coin in perp_coins:
            if not coin:
                continue
            for sym in spot_symbol_candidates(coin, allow_synthetic_tradfi=True):
                if sym in liquid:
                    mapped.add(sym)
        excluded = {str(t).upper() for t in SPOT_NON_BASIS_TOKENS}
        rows = [{"token": token, "day_volume": float(volumes[token])}
                for token in liquid if token not in mapped and token not in excluded]
        rows.sort(key=lambda r: (-r["day_volume"], r["token"]))
        return rows

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
                        self._spot_dec_cache[str(t["name"]).upper()] = int(t["szDecimals"])
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
        # The cached volume map behind that universe (None if the lookup failed):
        # it picks the most liquid of several hedges without a second request.
        spot_volumes = self._spot_volumes if classify_spot else None

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
                spot = spot_symbol_for(coin, spot_universe, spot_volumes)
                item["spot_symbol"] = spot
                item["is_spot_backed"] = spot is not None
                if spot:
                    # Round 40 (Ruling 40-4): the SPOT symbol's own precision first.
                    # This looked up the perp base name, so every wrapped hedge
                    # (UBTC, UFART, UANSEM) came back None and the sizing guard
                    # fell back to the perp leg alone. Zero decimals is a real
                    # answer (whole units), so the test is "is None", not truthiness.
                    decimals = self._spot_sz_decimals()
                    found = decimals.get(spot.upper())
                    if found is None:
                        found = decimals.get(perp_base_symbol(coin).upper())
                    item["spot_sz_decimals"] = found

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
