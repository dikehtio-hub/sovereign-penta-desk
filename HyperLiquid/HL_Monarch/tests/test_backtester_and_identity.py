"""
Spot-backing classification, the amortised net-APR model, and the historical
funding backtester.

The cross-market identity tests that used to live here went with
cross_market_scanner.py in the post-pivot cut.

All offline: synthetic series, fake clients. No network.
"""

import unittest

from analytics.funding_arbitrage import (
    FundingArbitrageEngine,
    perp_base_symbol,
    spot_symbol_for,
)
from analytics.funding_backtester import (
    backtest_funding_harvest,
    rank_funding_backtests,
    summarise_coverage,
)

H = 3_600_000  # one hour in ms


# --------------------------------------------------------------------------
# Spot backing / net APR / backtester
# --------------------------------------------------------------------------

class FakeSpotClient:
    def __init__(self, tokens, spreads=None, volumes=None, decimals=None):
        self.tokens = tokens
        self.spreads = spreads or {}
        self.volumes = volumes or {}            # token -> 24h pair notional; unlisted tokens are liquid
        self.decimals = decimals or {}          # token -> szDecimals; unlisted tokens carry none

    def get_spot_meta(self):
        return {"tokens": [({"name": t, "szDecimals": self.decimals[t]} if t in self.decimals else {"name": t})
                           for t in self.tokens]}

    def get_spot_meta_and_asset_ctxs(self):
        """Live shape (Round 39): pair token refs are token INDEX fields, and the
        contexts are matched to pairs by `coin` name, never by position."""
        tokens = [{"name": "USDC", "index": 0}] + [{"name": t, "index": 10 + i} for i, t in enumerate(self.tokens)]
        universe = [{"name": "@%d" % (i + 1), "tokens": [10 + i, 0], "index": i + 1}
                    for i, _ in enumerate(self.tokens)]
        ctxs = [{"coin": "@%d" % (i + 1), "dayNtlVlm": str(self.volumes.get(t, 1_000_000.0))}
                for i, t in enumerate(self.tokens)]
        return [{"tokens": tokens, "universe": universe}, list(reversed(ctxs))]

    def get_l2_book(self, coin):
        if coin not in self.spreads:
            raise RuntimeError("no book")
        bid, ask = self.spreads[coin]
        return {"levels": [[{"px": str(bid), "sz": "10"}], [{"px": str(ask), "sz": "10"}]]}


def _snap(coin, funding, oi=50_000_000.0, vol=20_000_000.0, px=100.0):
    return {"coin": coin, "dex": "main", "mark_px": px, "notional_oi": oi,
            "day_ntl_vlm": vol, "funding_rate": funding}


class TestSpotBacking(unittest.TestCase):
    def test_perp_base_symbol_strips_dex_prefix(self):
        self.assertEqual(perp_base_symbol("xyz:GOLD"), "GOLD")
        self.assertEqual(perp_base_symbol("BTC"), "BTC")

    def test_direct_spot_match(self):
        self.assertEqual(spot_symbol_for("HYPE", {"HYPE"}), "HYPE")

    def test_wrapped_spot_match(self):
        """BTC/ETH/SOL exist on Hyperliquid spot only as UBTC/UETH/USOL."""
        self.assertEqual(spot_symbol_for("BTC", {"UBTC"}), "UBTC")
        self.assertEqual(spot_symbol_for("ETH", {"UETH"}), "UETH")

    def test_no_spot_leg_returns_none(self):
        self.assertIsNone(spot_symbol_for("CASHCAT", {"UBTC", "HYPE"}))

    def test_scan_flags_spot_backed_and_directional(self):
        engine = FundingArbitrageEngine(client=FakeSpotClient(["UBTC"]))
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=[_snap("BTC", 0.001), _snap("CASHCAT", 0.001)]
        )
        by_coin = {i["coin"]: i for i in res["short_harvest"]}
        self.assertTrue(by_coin["BTC"]["is_spot_backed"])
        self.assertEqual(by_coin["BTC"]["spot_symbol"], "UBTC")
        self.assertEqual(by_coin["BTC"]["trade_type"], "BASIS_ARB")
        self.assertFalse(by_coin["CASHCAT"]["is_spot_backed"])
        self.assertEqual(by_coin["CASHCAT"]["trade_type"], "DIRECTIONAL_FUNDING")

    def test_recommendation_does_not_promise_an_impossible_hedge(self):
        """Advising 'Long Spot' for a coin with no spot market is unactionable."""
        engine = FundingArbitrageEngine(client=FakeSpotClient([]))
        res = engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=[_snap("CASHCAT", 0.001)])
        self.assertIn("DIRECTIONAL", res["short_harvest"][0]["recommendation"])

    def test_spot_lookup_failure_does_not_claim_backing(self):
        class Broken:
            def get_spot_meta(self):
                raise RuntimeError("down")

            def get_spot_meta_and_asset_ctxs(self):
                raise RuntimeError("down")

        engine = FundingArbitrageEngine(client=Broken())
        res = engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=[_snap("BTC", 0.001)])
        self.assertFalse(res["short_harvest"][0]["is_spot_backed"])

    def test_spot_universe_is_cached(self):
        client = FakeSpotClient(["UBTC"])
        engine = FundingArbitrageEngine(client=client)
        calls = []
        orig = client.get_spot_meta_and_asset_ctxs

        def counting():
            calls.append(1)
            return orig()

        client.get_spot_meta_and_asset_ctxs = counting
        engine.get_spot_universe()
        engine.get_spot_universe()
        engine.get_spot_universe(min_spot_volume=0.0)      # a different floor filters the same cached volumes
        self.assertEqual(len(calls), 1)

    def test_a_spot_token_with_a_dead_pair_is_not_spot_backed(self):
        """
        Round 39. Measured live: TSLA and AVGO spot turned over $0 in 24h while
        their HIP-3 perps traded tens of millions; CRCL under $2k. A token is not
        a market, and a basis trade hedged on a dead pair has no hedge.
        """
        client = FakeSpotClient(["TSLA", "AVGO", "HYPE", "CRCL"],
                                volumes={"TSLA": 0.0, "AVGO": 34.18, "CRCL": 1_983.91})
        engine = FundingArbitrageEngine(client=client)
        self.assertEqual(engine.get_spot_universe(), {"HYPE"})
        self.assertEqual(engine.get_spot_universe(min_spot_volume=1_000.0), {"HYPE", "CRCL"})
        self.assertEqual(engine.get_spot_volumes()["AVGO"], 34.18)
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=[_snap("xyz:TSLA", 0.001), _snap("HYPE", 0.001)])
        by_coin = {i["coin"]: i for i in res["short_harvest"]}
        self.assertFalse(by_coin["xyz:TSLA"]["is_spot_backed"])
        self.assertEqual(by_coin["xyz:TSLA"]["trade_type"], "DIRECTIONAL_FUNDING")
        self.assertTrue(by_coin["HYPE"]["is_spot_backed"])

    def test_aliases_find_wrappers_the_prefix_rule_cannot(self):
        """Round 40 (Ruling 40-1). FARTCOIN's liquid spot is UFART and XMR's is XMR1 - neither is 'U' + name."""
        from analytics.funding_arbitrage import SPOT_SYMBOL_ALIASES, spot_symbol_candidates
        self.assertEqual(spot_symbol_for("FARTCOIN", {"UFART"}), "UFART")
        self.assertEqual(spot_symbol_for("XMR", {"XMR1", "FXMR"}), "XMR1")          # table order without volumes
        self.assertIsNone(spot_symbol_for("FARTCOIN", {"HYPE"}))                     # an alias not listed is no hedge
        self.assertEqual(spot_symbol_candidates("XMR"), ["UXMR", "XMR", "XMR1", "FXMR"])   # Round 41: wrapper first
        for base, aliases in SPOT_SYMBOL_ALIASES.items():
            for alias in aliases:
                self.assertEqual(spot_symbol_for(base, {alias}), alias)

    def test_synthetic_tradfi_perps_have_no_hedge_unless_allowed(self):
        """
        Round 42 (Ruling 42-1). A stock, index, commodity, bond or FX perp prices
        an underlying with a weekend and a closing bell against a perp that
        trades 24/7. Round 41 quarantined the equity ALIASES, which left the
        bare-name and wrapper paths open; the quarantine is now on the PERP.
        """
        from config.settings import ALLOW_SYNTHETIC_TRADFI_BASIS, SYNTHETIC_TRADFI_SYMBOLS
        from analytics.funding_arbitrage import (SPOT_SYMBOL_ALIASES, SYNTHETIC_TRADFI_ALIASES,
                                                 is_synthetic_tradfi, spot_symbol_candidates)
        self.assertFalse(ALLOW_SYNTHETIC_TRADFI_BASIS)
        for base in ("NVDA", "TSLA", "GOLD", "US500", "USOIL", "SPY", "QQQ", "HOOD", "AVGO", "MU", "10Y", "EUR"):
            self.assertIn(base, SYNTHETIC_TRADFI_SYMBOLS)
        self.assertTrue(set(SYNTHETIC_TRADFI_ALIASES).isdisjoint(SPOT_SYMBOL_ALIASES))
        # No candidates at all - bare, wrapper or alias - regardless of what spot lists.
        everything = {"NVDA", "UNVDA", "NVDAX", "EQNVDA", "GOLD", "UGOLD", "XAUT0", "US500", "UUS500"}
        for coin in ("xyz:NVDA", "km:NVDA", "NVDA", "xyz:GOLD", "flx:GOLD", "km:US500", "cash:USA500"):
            self.assertEqual(spot_symbol_candidates(coin), [], coin)
            self.assertIsNone(spot_symbol_for(coin, everything, {t: 1e6 for t in everything}), coin)
            self.assertTrue(is_synthetic_tradfi(coin), coin)
        # Crypto-native perps are untouched, dex prefix or not.
        self.assertFalse(is_synthetic_tradfi("para:ANSEM"))
        self.assertEqual(spot_symbol_candidates("BTC"), ["UBTC", "BTC"])
        # Allowed: the perp resolves through every path, equity aliases last.
        self.assertEqual(spot_symbol_candidates("xyz:NVDA", allow_synthetic_tradfi=True),
                         ["UNVDA", "NVDA", "NVDAX", "EQNVDA"])
        self.assertEqual(spot_symbol_for("xyz:NVDA", {"NVDAX"}, allow_synthetic_tradfi=True), "NVDAX")
        self.assertEqual(spot_symbol_for("xyz:GOLD", {"GOLD"}, allow_synthetic_tradfi=True), "GOLD")
        self.assertFalse(is_synthetic_tradfi("xyz:GOLD", allow_synthetic_tradfi=True))
        # The scan inherits the quarantine: a liquid bare GOLD token does not make xyz:GOLD a basis trade.
        engine = FundingArbitrageEngine(client=FakeSpotClient(["GOLD", "NVDAX", "UBTC"]))
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=[_snap("xyz:GOLD", 0.001), _snap("xyz:NVDA", 0.001), _snap("BTC", 0.001)])
        by_coin = {i["coin"]: i for i in res["short_harvest"]}
        self.assertFalse(by_coin["xyz:GOLD"]["is_spot_backed"])
        self.assertFalse(by_coin["xyz:NVDA"]["is_spot_backed"])
        self.assertTrue(by_coin["BTC"]["is_spot_backed"])
        # Telemetry still counts a quarantined perp's tokens as mapped (blocked is not missing).
        rows = engine.get_unmapped_liquid_spot(perp_coins=["xyz:GOLD", "xyz:NVDA", "BTC"], min_spot_volume=50_000.0)
        self.assertEqual(rows, [])

    def test_the_dex_itself_quarantines_whatever_lists_there(self):
        """
        Round 43 (Ruling 43-1). Everything on xyz, km, cash and flx prices a
        stock, index, commodity, bond or FX pair, so a name nobody has put in
        the symbol set is caught by its address. The symbol set still covers
        the mixed para dex and the main dex.
        """
        from config.settings import TRADFI_DEXES
        from analytics.funding_arbitrage import is_synthetic_tradfi, perp_dex, spot_symbol_candidates
        self.assertEqual(TRADFI_DEXES, frozenset({"xyz", "km", "cash", "flx", "mkts", "io", "vntl"}))
        self.assertEqual(perp_dex("xyz:GOLD"), "xyz")
        self.assertEqual(perp_dex("BTC"), "main")
        # Round 44: mkts (Kinetiq index perps) and io (EntropyIO pre-IPO equities) by address too.
        # Round 46: vntl (Ventuals - ANTHROPIC, OPENAI, SPACEX, MAG7, SOY, WHEAT...) classified TradFi.
        for coin in ("xyz:NEWCO", "km:WHATEVER", "cash:X", "flx:GAS", "XYZ:UPPER", "mkts:US500", "io:OAI",
                     "io:ANTHROPIC", "vntl:SPACEX", "vntl:MAG7", "vntl:WHEAT"):
            self.assertTrue(is_synthetic_tradfi(coin), coin)
            self.assertEqual(spot_symbol_candidates(coin), [], coin)
            self.assertIsNone(spot_symbol_for(coin, {"NEWCO", "UNEWCO", "WHATEVER", "X", "GAS", "UPPER"}), coin)
        self.assertTrue(is_synthetic_tradfi("para:AVGO"))                      # mixed dex: the symbol set
        self.assertTrue(is_synthetic_tradfi("para:10Y"))
        self.assertFalse(is_synthetic_tradfi("para:ANSEM"))
        self.assertFalse(is_synthetic_tradfi("UNI"))
        self.assertFalse(is_synthetic_tradfi("xyz:NEWCO", allow_synthetic_tradfi=True))
        self.assertEqual(spot_symbol_candidates("xyz:ANSEM", allow_synthetic_tradfi=True), ["UANSEM", "ANSEM"])

    def test_unclassified_dexes_fail_closed_with_no_switch(self):
        """
        Round 45 (Ruling 45-2). vntl, hyna and abcd are on the live perpDexs list
        and nobody has looked at what trades there. Not polled, not a basis leg,
        not a sampling candidate - and no runtime flag changes that; only an
        edit to settings after a human has classified the dex.
        """
        from config.settings import ACTIVE_DEXES, TRADFI_DEXES, UNCLASSIFIED_DEXES
        from analytics.funding_arbitrage import is_unclassified_dex, is_synthetic_tradfi, spot_symbol_candidates
        from collectors.orderbook_sampler import top_funding_candidates
        from config.settings import CRYPTO_DEXES, MIXED_DEXES
        self.assertEqual(CRYPTO_DEXES, frozenset({"main"}))                        # Round 48: main is the only crypto-wide dex
        self.assertEqual(MIXED_DEXES, frozenset({"para"}))                         # admitted symbol by symbol
        self.assertEqual(UNCLASSIFIED_DEXES, frozenset({"abcd", "hyna"}))         # known, deliberately refused
        sets = (CRYPTO_DEXES, MIXED_DEXES, TRADFI_DEXES, UNCLASSIFIED_DEXES)
        for i, a in enumerate(sets):
            for b in sets[i + 1:]:
                self.assertTrue(a.isdisjoint(b))
        self.assertTrue(UNCLASSIFIED_DEXES.isdisjoint({str(d).lower() for d in ACTIVE_DEXES}))
        self.assertTrue({str(d).lower() for d in ACTIVE_DEXES} <= CRYPTO_DEXES | MIXED_DEXES | TRADFI_DEXES)
        # Round 47: STRUCTURAL - a dex in neither set is refused before anyone has heard of it.
        for coin in ("abcd:BTC", "abcd:HYPE", "novel:TOKEN", "launched_today:BTC", "hyna:HYPE"):
            self.assertTrue(is_unclassified_dex(coin), coin)
            self.assertFalse(is_synthetic_tradfi(coin), coin)                    # unclassified, not TradFi
            self.assertEqual(spot_symbol_candidates(coin), [], coin)
            self.assertEqual(spot_symbol_candidates(coin, allow_synthetic_tradfi=True), [], coin)
            self.assertIsNone(spot_symbol_for(coin, {"HYPE", "UBTC", "SPACEX"}, {"HYPE": 1e9}), coin)
        self.assertFalse(is_unclassified_dex("BTC"))
        self.assertFalse(is_unclassified_dex("para:ANSEM"))
        self.assertFalse(is_unclassified_dex("para:SMCI"))                         # mixed dex: classified, refused by allow-list
        self.assertFalse(is_unclassified_dex("xyz:GOLD"))                          # TradFi is classified, just refused elsewhere
        # hyna is mixed like para but NOT admitted: refused structurally, while its GOLD is TradFi by symbol too.
        self.assertTrue(is_unclassified_dex("hyna:HYPE"))
        self.assertEqual(spot_symbol_candidates("hyna:HYPE"), [])
        self.assertTrue(is_synthetic_tradfi("hyna:GOLD"))
        # The drift detector names only dexes NO settings set knows; null is the main dex.
        from analytics.funding_arbitrage import unclassified_dex_names
        self.assertEqual(unclassified_dex_names([None, "xyz", "flx", "vntl", "hyna", "km", "abcd", "cash",
                                                 "para", "mkts", "io"]), [])
        self.assertEqual(unclassified_dex_names([None, "NEWDEX", "xyz", "", "Other ", "newdex"]), ["newdex", "other"])
        # The scan and the sampler inherit it.
        engine = FundingArbitrageEngine(client=FakeSpotClient(["HYPE", "UBTC"]))
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=[_snap("abcd:BTC", 0.001), _snap("BTC", 0.001)])
        by_coin = {i["coin"]: i for i in res["short_harvest"]}
        self.assertFalse(by_coin["abcd:BTC"]["is_spot_backed"])
        self.assertTrue(by_coin["BTC"]["is_spot_backed"])
        snaps = [{"coin": "abcd:HYPE", "funding_rate": 0.01, "notional_oi": 1e7, "day_ntl_vlm": 1e7},
                 {"coin": "HYPE", "funding_rate": 0.001, "notional_oi": 1e7, "day_ntl_vlm": 1e7}]
        self.assertEqual(top_funding_candidates(snaps, n=5, spot_universe={"HYPE"}), ["HYPE"])

    def test_a_mixed_dex_admits_only_its_crypto_allow_list(self):
        """
        Round 48 (Ruling 48-1). para lists 33 perps and four are crypto (TOTAL2,
        OTHERS, BTCD, ANSEM); the rest are equities, rates and pre-IPO names.
        Quarantining names one at a time loses to every new listing, so the
        logic is inverted: on a mixed dex a perp is TradFi unless allow-listed.
        """
        from config.settings import MIXED_DEX_CRYPTO_ALLOWLIST
        from analytics.funding_arbitrage import is_mixed_dex_tradfi, is_synthetic_tradfi, spot_symbol_candidates
        self.assertEqual(MIXED_DEX_CRYPTO_ALLOWLIST, {"para": frozenset({"ANSEM", "TOTAL2", "BTCD", "OTHERS"})})
        for coin in ("para:ANSEM", "para:TOTAL2", "para:BTCD", "para:OTHERS"):
            self.assertFalse(is_mixed_dex_tradfi(coin), coin)
            self.assertFalse(is_synthetic_tradfi(coin), coin)
            self.assertTrue(spot_symbol_candidates(coin), coin)
        self.assertEqual(spot_symbol_candidates("para:ANSEM"), ["UANSEM", "ANSEM"])
        self.assertEqual(spot_symbol_for("para:ANSEM", {"UANSEM"}), "UANSEM")
        # Everything else on the dex - listed today or tomorrow - is TradFi with no edit.
        for coin in ("para:SMCI", "para:RDDT", "para:CRWD", "para:ANTH", "para:10Y", "para:UNKNOWN", "para:NEWSTOCK"):
            self.assertTrue(is_mixed_dex_tradfi(coin), coin)
            self.assertTrue(is_synthetic_tradfi(coin), coin)
            self.assertEqual(spot_symbol_candidates(coin), [], coin)
            self.assertIsNone(spot_symbol_for(coin, {"SMCI", "USMCI", "RDDT", "ANTH", "UNKNOWN", "NEWSTOCK"}), coin)
        # The allow-list is dex-scoped: SMCI on the main dex is judged by the symbol set alone.
        self.assertFalse(is_mixed_dex_tradfi("SMCI"))
        self.assertFalse(is_mixed_dex_tradfi("xyz:SMCI"))
        # The TradFi switch still opens the door, as for every other quarantine.
        self.assertFalse(is_synthetic_tradfi("para:SMCI", allow_synthetic_tradfi=True))
        self.assertEqual(spot_symbol_candidates("para:SMCI", allow_synthetic_tradfi=True), ["USMCI", "SMCI"])
        # The scan inherits it.
        engine = FundingArbitrageEngine(client=FakeSpotClient(["UANSEM", "SMCI"]))
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=[_snap("para:ANSEM", 0.001), _snap("para:SMCI", 0.001)])
        by_coin = {i["coin"]: i for i in res["short_harvest"]}
        self.assertTrue(by_coin["para:ANSEM"]["is_spot_backed"])
        self.assertEqual(by_coin["para:ANSEM"]["spot_symbol"], "UANSEM")
        self.assertFalse(by_coin["para:SMCI"]["is_spot_backed"])

    def test_canonical_spot_base_names_the_underlying(self):
        """Round 43 (Ruling 43-2): ANSEM and UANSEM are one asset; so are FARTCOIN, UFART; XMR, XMR1, FXMR."""
        from analytics.funding_arbitrage import canonical_spot_base
        for sym, base in (("UFART", "FARTCOIN"), ("XMR1", "XMR"), ("FXMR", "XMR"), ("UUUSPX", "SPX"),
                          ("NVDAX", "NVDA"), ("EQTSLA", "TSLA"), ("UANSEM", "ANSEM"), ("UBTC", "BTC"),
                          ("ANSEM", "ANSEM"), ("HYPE", "HYPE"), ("uanem", "ANEM"), ("UNI", "UNI"),
                          ("UMA", "UMA"), ("UP", "UP")):
            self.assertEqual(canonical_spot_base(sym), base, sym)
        self.assertIsNone(canonical_spot_base(None))
        self.assertIsNone(canonical_spot_base(""))

    def test_thresholds_read_the_hot_reloaded_config_first(self):
        """Round 43 (Ruling 43-6): Bot_Config fields override the settings constants without a restart."""
        from analytics.funding_arbitrage import effective_spot_min_volume, allow_synthetic_tradfi_basis
        from config.dynamic_config import BotConfig
        from config.settings import SPOT_MIN_DAY_VOLUME, SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE

        cfg = BotConfig()
        self.assertFalse(cfg.allow_synthetic_tradfi_basis)
        self.assertEqual(cfg.spot_min_volume_notional_multiple, SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE)
        self.assertEqual(cfg.spot_min_day_volume, SPOT_MIN_DAY_VOLUME)
        self.assertEqual(effective_spot_min_volume(cfg), 100_000.0)
        cfg.spot_min_volume_notional_multiple, cfg.spot_min_day_volume = 20.0, 400_000.0
        self.assertEqual(effective_spot_min_volume(cfg), 400_000.0)               # the floor wins
        cfg.basis_notional_usd = 25_000.0
        self.assertEqual(effective_spot_min_volume(cfg), 500_000.0)               # 20 x 25k beats it
        self.assertEqual(BotConfig(spot_min_day_volume=1.0).validate_and_clamp().spot_min_day_volume, 10_000.0)  # Round 44 floor
        # An explicit override always wins over the config.
        self.assertTrue(allow_synthetic_tradfi_basis(True))
        self.assertFalse(allow_synthetic_tradfi_basis(False))

    def test_spx_is_the_memecoin_and_resolves_to_its_unit_wrapper(self):
        """
        Round 42. UUUSPX is "Unit SPX6900" - the main-dex SPX perp prices it
        ($0.6009 beside $0.6007). It is not the S&P 500; that is km:US500, which
        is quarantined. The alias must not leak across.
        """
        from analytics.funding_arbitrage import SPOT_SYMBOL_ALIASES
        self.assertEqual(SPOT_SYMBOL_ALIASES["SPX"], ("UUUSPX",))
        self.assertEqual(spot_symbol_for("SPX", {"UUUSPX"}), "UUUSPX")
        self.assertEqual(spot_symbol_for("SPX", {"USPX", "UUUSPX"}, {"USPX": 1.0, "UUUSPX": 70_447.0}), "UUUSPX")
        self.assertIsNone(spot_symbol_for("km:US500", {"UUUSPX", "US500"}))
        self.assertIsNone(spot_symbol_for("cash:USA500", {"UUUSPX"}, allow_synthetic_tradfi=True))

    def test_the_spot_floor_scales_with_the_configured_leg(self):
        """Round 41 (Ruling 41-3): max(SPOT_MIN_DAY_VOLUME, 5 x notional) - a $25k leg needs a $125k/day pair."""
        from analytics.funding_arbitrage import effective_spot_min_volume
        from config.settings import SPOT_MIN_DAY_VOLUME, SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE

        class Cfg:
            def __init__(self, notional):
                self.basis_notional_usd = notional

        self.assertEqual(SPOT_MIN_VOLUME_NOTIONAL_MULTIPLE, 10.0)                        # Round 42: 10x, <= 10% ADV
        self.assertEqual(effective_spot_min_volume(Cfg(10_000.0)), 100_000.0)
        self.assertEqual(effective_spot_min_volume(Cfg(25_000.0)), 250_000.0)
        self.assertEqual(effective_spot_min_volume(Cfg(1_000.0)), SPOT_MIN_DAY_VOLUME)     # the floor of the floor
        self.assertEqual(effective_spot_min_volume(Cfg(None)), SPOT_MIN_DAY_VOLUME)
        self.assertEqual(effective_spot_min_volume(object()), SPOT_MIN_DAY_VOLUME)
        # The default universe uses the floor in force; an explicit floor overrides it.
        engine = FundingArbitrageEngine(client=FakeSpotClient(["A", "B"], volumes={"A": 60_000.0, "B": 300_000.0}))
        self.assertEqual(engine.get_spot_universe(), engine.get_spot_universe(min_spot_volume=effective_spot_min_volume()))
        self.assertEqual(engine.get_spot_universe(min_spot_volume=effective_spot_min_volume(Cfg(25_000.0))), {"B"})
        self.assertEqual(engine.get_spot_universe(min_spot_volume=effective_spot_min_volume(Cfg(40_000.0))), set())

    def test_unmapped_liquid_spot_lists_wrappers_no_perp_resolves_to(self):
        """
        Round 41 (Ruling 41-4). A hand-kept alias table goes stale silently, so
        the engine reports liquid tokens nothing maps to. A quarantined equity
        alias is mapped-but-blocked, not missing; stablecoins are never a leg.
        """
        client = FakeSpotClient(["UBTC", "UFART", "NVDAX", "HFUN", "USDC", "THIN", "FXMR"],
                                volumes={"THIN": 100.0, "HFUN": 300_000.0, "FXMR": 80_000.0})
        engine = FundingArbitrageEngine(client=client)
        rows = engine.get_unmapped_liquid_spot(perp_coins=["BTC", "FARTCOIN", "xyz:NVDA", "XMR"],
                                               min_spot_volume=50_000.0)
        self.assertEqual(rows, [{"token": "HFUN", "day_volume": 300_000.0}])
        # With only a BTC perp, every other liquid token surfaces - NVDAX included, since
        # nothing maps to it now - most liquid first, ties by name.
        rows = engine.get_unmapped_liquid_spot(perp_coins=["BTC"], min_spot_volume=50_000.0)
        self.assertEqual([r["token"] for r in rows], ["NVDAX", "UFART", "HFUN", "FXMR"])
        self.assertEqual(engine.get_unmapped_liquid_spot(perp_coins=[], min_spot_volume=1e12), [])

    def test_the_most_liquid_hedge_wins_when_several_exist(self):
        """Round 40 (Ruling 40-2). para:ANSEM was booked against ANSEM ($1.5k/day) while UANSEM did $928k."""
        universe = {"ANSEM", "UANSEM"}
        self.assertEqual(spot_symbol_for("para:ANSEM", universe), "UANSEM")           # Round 41: the wrapper leads
        self.assertEqual(spot_symbol_for("para:ANSEM", universe, {"ANSEM": 1_515.0, "UANSEM": 927_818.0}), "UANSEM")
        self.assertEqual(spot_symbol_for("para:ANSEM", universe, {"ANSEM": 927_818.0, "UANSEM": 1_515.0}), "ANSEM")
        self.assertEqual(spot_symbol_for("para:ANSEM", universe, {"ANSEM": 5.0, "UANSEM": 5.0}), "UANSEM")  # tie: wrapper
        wrappers = {"XMR1", "FXMR"}
        self.assertEqual(spot_symbol_for("XMR", wrappers, {"XMR1": 15_995_011.0, "FXMR": 10_743.0}), "XMR1")
        self.assertEqual(spot_symbol_for("XMR", wrappers, {"XMR1": 1.0, "FXMR": 2.0}), "FXMR")
        self.assertEqual(spot_symbol_for("XMR", wrappers, {}), "XMR1")                # no volumes: precedence
        self.assertEqual(spot_symbol_for("XMR", wrappers, {"XMR1": 5.0, "FXMR": 5.0}), "XMR1")       # tie: precedence
        self.assertEqual(spot_symbol_for("XMR", wrappers, {"XMR1": "junk", "FXMR": 5.0}), "FXMR")    # junk counts as 0

    def test_the_scan_hedges_with_the_liquid_wrapper_and_its_own_decimals(self):
        """Ruling 40-4: spot_sz_decimals looked up the perp base name, so every wrapped hedge came back None."""
        client = FakeSpotClient(["ANSEM", "UANSEM", "UBTC"],
                                volumes={"ANSEM": 60_000.0, "UANSEM": 927_818.0},
                                decimals={"ANSEM": 1, "UANSEM": 0, "UBTC": 5})
        engine = FundingArbitrageEngine(client=client)
        res = engine.scan_funding_opportunities(
            min_apr_pct=10.0, snapshots=[_snap("para:ANSEM", 0.001), _snap("BTC", 0.001)])
        by_coin = {i["coin"]: i for i in res["short_harvest"]}
        self.assertEqual(by_coin["para:ANSEM"]["spot_symbol"], "UANSEM")
        self.assertEqual(by_coin["para:ANSEM"]["spot_sz_decimals"], 0)              # zero is an answer, not a miss
        self.assertEqual(by_coin["BTC"]["spot_symbol"], "UBTC")
        self.assertEqual(by_coin["BTC"]["spot_sz_decimals"], 5)

    def test_a_token_with_no_pair_at_all_is_a_shell(self):
        """COIN and NVDA have a token entry and no pair - the payload's other trap,
        alongside index-based token refs and name-matched contexts."""
        class Shells:
            def get_spot_meta_and_asset_ctxs(self):
                return [{"tokens": [{"name": "USDC", "index": 0}, {"name": "COIN", "index": 5},
                                    {"name": "PURR", "index": 1}],
                         "universe": [{"name": "PURR/USDC", "tokens": [1, 0], "index": 0}]},
                        [{"coin": "@77", "dayNtlVlm": "5"}, {"coin": "PURR/USDC", "dayNtlVlm": "2589841.64"}]]

        engine = FundingArbitrageEngine(client=Shells())
        self.assertEqual(engine.get_spot_volumes(), {"PURR": 2589841.64})
        self.assertEqual(engine.get_spot_universe(), {"PURR"})

    def test_a_failed_volume_lookup_is_not_cached_and_claims_nothing(self):
        class Flaky:
            calls = 0

            def get_spot_meta_and_asset_ctxs(self):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("down")
                return [{"tokens": [{"name": "USDC", "index": 0}, {"name": "HYPE", "index": 1}],
                         "universe": [{"name": "HYPE/USDC", "tokens": [1, 0], "index": 0}]},
                        [{"coin": "HYPE/USDC", "dayNtlVlm": "1e6"}]]

        engine = FundingArbitrageEngine(client=Flaky())
        self.assertEqual(engine.get_spot_universe(), set())        # the failed attempt claims nothing
        self.assertIsNone(engine._spot_volumes)                    # and the failure is not cached
        self.assertEqual(engine.get_spot_universe(), {"HYPE"})     # retried on the next call, then cached
        self.assertEqual(engine.get_spot_universe(), {"HYPE"})
        self.assertEqual(engine.client.calls, 2)


class TestNetAprModel(unittest.TestCase):
    def test_longer_hold_amortises_the_spread(self):
        """A 7-day hold must be penalised ~7x less than a 1-day hold."""
        item = {"funding_apr": 300.0, "spread_bps": 10.0, "is_spot_backed": False}
        one = FundingArbitrageEngine.net_apr_after_spread(item, holding_period_days=1.0)
        seven = FundingArbitrageEngine.net_apr_after_spread(item, holding_period_days=7.0)
        self.assertLess(one, seven)
        self.assertAlmostEqual(300.0 - one, (300.0 - seven) * 7.0, places=4)

    def test_default_holding_period_is_seven_days(self):
        item = {"funding_apr": 300.0, "spread_bps": 10.0, "is_spot_backed": False}
        self.assertAlmostEqual(
            FundingArbitrageEngine.net_apr_after_spread(item),
            FundingArbitrageEngine.net_apr_after_spread(item, holding_period_days=7.0),
        )

    def test_item_carries_its_own_holding_period(self):
        item = {"funding_apr": 300.0, "spread_bps": 10.0, "holding_period_days": 30.0,
                "is_spot_backed": False}
        self.assertAlmostEqual(
            FundingArbitrageEngine.net_apr_after_spread(item),
            FundingArbitrageEngine.net_apr_after_spread(item, holding_period_days=30.0),
        )

    def test_hedged_trade_pays_two_legs_of_spread(self):
        """A basis trade crosses the spread on the perp AND the spot leg."""
        hedged = {"funding_apr": 300.0, "spread_bps": 10.0, "is_spot_backed": True}
        naked = {"funding_apr": 300.0, "spread_bps": 10.0, "is_spot_backed": False}
        cost_hedged = 300.0 - FundingArbitrageEngine.net_apr_after_spread(hedged)
        cost_naked = 300.0 - FundingArbitrageEngine.net_apr_after_spread(naked)
        self.assertAlmostEqual(cost_hedged, cost_naked * 2.0, places=6)

    def test_cost_reduces_magnitude_in_both_directions(self):
        pos = FundingArbitrageEngine.net_apr_after_spread(
            {"funding_apr": 300.0, "spread_bps": 10.0, "is_spot_backed": False})
        neg = FundingArbitrageEngine.net_apr_after_spread(
            {"funding_apr": -300.0, "spread_bps": 10.0, "is_spot_backed": False})
        self.assertLess(pos, 300.0)
        self.assertGreater(neg, -300.0)

    def test_unmeasured_spread_is_not_charged(self):
        self.assertEqual(
            FundingArbitrageEngine.net_apr_after_spread(
                {"funding_apr": 300.0, "spread_bps": None}),
            300.0,
        )

    def test_expected_pnl_is_the_period_return_not_annualised(self):
        item = {"funding_apr": 365.0, "spread_bps": None, "holding_period_days": 7.0}
        self.assertAlmostEqual(FundingArbitrageEngine.expected_pnl_pct(item), 7.0, places=6)

    def test_funding_payments_over_a_week(self):
        self.assertEqual(FundingArbitrageEngine.funding_payments_over(7.0), 168)


# --------------------------------------------------------------------------
# Task 3: historical backtester
# --------------------------------------------------------------------------

class TestFundingBacktester(unittest.TestCase):
    def test_constant_rate_integrates_exactly(self):
        series = [(i * H, 0.001, 100.0) for i in range(11)]
        r = backtest_funding_harvest("T", hours=10, series=series, now_ms=10 * H, max_gap_hours=1.5)
        self.assertAlmostEqual(r["funding_pnl_pct"], 1.0, places=6)
        self.assertEqual(r["side"], "short")
        self.assertAlmostEqual(r["observed_hours"], 10.0)

    def test_negative_funding_is_harvested_by_going_long(self):
        series = [(i * H, -0.001, 100.0) for i in range(11)]
        r = backtest_funding_harvest("T", hours=10, series=series, now_ms=10 * H, max_gap_hours=1.5)
        self.assertEqual(r["side"], "long")
        self.assertAlmostEqual(r["funding_pnl_pct"], 1.0, places=6)

    def test_accrual_is_time_weighted_not_sample_averaged(self):
        """
        A dense burst at a high rate must not outvote a long quiet stretch.
        Sampling density varies hugely (8s while collecting, hours when not).
        """
        dense = [(i * 60_000, 0.01, 100.0) for i in range(60)]      # 1h @ 0.01
        sparse = [(60 * 60_000 + i * H, 0.0001, 100.0) for i in range(10)]  # 9h @ 0.0001
        r = backtest_funding_harvest("T", hours=10, series=dense + sparse,
                                     now_ms=10 * H, max_gap_hours=1.5)
        # Exact expectation: 1h at 0.01 plus 9h at 0.0001 = 0.0109 -> 1.09%.
        self.assertAlmostEqual(r["funding_pnl_pct"], 1.09, places=6)

        # Averaging over samples instead would weight the 60 dense points equally
        # against the 10 sparse ones and land ~8x too high.
        naive = (sum(x[1] for x in dense + sparse) / len(dense + sparse)) * 10 * 100
        self.assertGreater(naive, 5.0)
        self.assertLess(r["funding_pnl_pct"], naive / 4.0)

    def test_outage_is_excluded_not_extrapolated(self):
        series = [(0, 0.001, 100.0), (H, 0.001, 100.0), (20 * H, 0.001, 100.0)]
        r = backtest_funding_harvest("T", hours=24, series=series, now_ms=24 * H, max_gap_hours=1.5)
        self.assertAlmostEqual(r["observed_hours"], 1.0)
        self.assertAlmostEqual(r["gap_hours"], 19.0)
        self.assertAlmostEqual(r["funding_pnl_pct"], 0.1, places=6)

    def test_coverage_reports_how_much_was_actually_observed(self):
        series = [(0, 0.001, 100.0), (H, 0.001, 100.0), (20 * H, 0.001, 100.0)]
        r = backtest_funding_harvest("T", hours=24, series=series, now_ms=24 * H, max_gap_hours=1.5)
        self.assertLess(r["coverage_pct"], 10.0)

    def test_hedged_position_excludes_the_price_leg(self):
        series = [(0, 0.001, 100.0), (H, 0.001, 110.0)]
        naked = backtest_funding_harvest("T", hours=1, series=series, now_ms=H,
                                         max_gap_hours=1.5, is_spot_backed=False)
        hedged = backtest_funding_harvest("T", hours=1, series=series, now_ms=H,
                                          max_gap_hours=1.5, is_spot_backed=True)
        # Short into a +10% move: unhedged loses far more than the funding earns.
        self.assertLess(naked["net_pnl_pct"], -9.0)
        self.assertAlmostEqual(hedged["net_pnl_pct"], hedged["funding_pnl_pct"], places=6)

    def test_empty_and_single_sample_series_are_safe(self):
        for series in ([], [(0, 0.001, 100.0)]):
            r = backtest_funding_harvest("T", hours=10, series=series, now_ms=10 * H)
            self.assertEqual(r["funding_pnl_pct"], 0.0)
            self.assertFalse(r["sufficient_data"])

    def test_all_gap_series_reports_zero_coverage(self):
        series = [(0, 0.001, 100.0), (50 * H, 0.001, 100.0)]
        r = backtest_funding_harvest("T", hours=72, series=series, now_ms=72 * H, max_gap_hours=0.5)
        self.assertEqual(r["observed_hours"], 0.0)
        self.assertFalse(r["sufficient_data"])

    def test_zero_and_backwards_intervals_are_ignored(self):
        series = [(H, 0.001, 100.0), (H, 0.001, 100.0), (0, 0.001, 100.0), (2 * H, 0.001, 100.0)]
        r = backtest_funding_harvest("T", hours=10, series=series, now_ms=10 * H, max_gap_hours=1.5)
        self.assertGreaterEqual(r["observed_hours"], 0.0)

    def test_realised_apr_annualises_the_observed_window(self):
        series = [(i * H, 0.001, 100.0) for i in range(11)]
        r = backtest_funding_harvest("T", hours=10, series=series, now_ms=10 * H, max_gap_hours=1.5)
        self.assertAlmostEqual(r["realised_apr"], 1.0 * (8760.0 / 10.0), places=2)

    def test_summarise_coverage_handles_empty(self):
        self.assertEqual(summarise_coverage([])["coins"], 0)

    def test_rank_drops_results_below_coverage_floor(self):
        class StubRepo:
            def get_latest_snapshots(self, coins=None):
                return [{"coin": "T"}]

        # 1h observed out of a 72h ask -> ~1.4% coverage, far below the floor.
        series = [(0, 0.001, 100.0), (H, 0.001, 100.0)]
        import analytics.funding_backtester as bt
        orig = bt.load_funding_series
        bt.load_funding_series = lambda coin, hours, repo=None, now_ms=None: series
        try:
            out = rank_funding_backtests(coins=["T"], hours=72, repo=StubRepo(), min_coverage_pct=25.0)
            self.assertEqual(out, [])
        finally:
            bt.load_funding_series = orig


if __name__ == "__main__":
    unittest.main()
