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
    def __init__(self, tokens, spreads=None):
        self.tokens = tokens
        self.spreads = spreads or {}

    def get_spot_meta(self):
        return {"tokens": [{"name": t} for t in self.tokens]}

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

        engine = FundingArbitrageEngine(client=Broken())
        res = engine.scan_funding_opportunities(min_apr_pct=10.0, snapshots=[_snap("BTC", 0.001)])
        self.assertFalse(res["short_harvest"][0]["is_spot_backed"])

    def test_spot_universe_is_cached(self):
        client = FakeSpotClient(["UBTC"])
        engine = FundingArbitrageEngine(client=client)
        calls = []
        orig = client.get_spot_meta

        def counting():
            calls.append(1)
            return orig()

        client.get_spot_meta = counting
        engine.get_spot_universe()
        engine.get_spot_universe()
        self.assertEqual(len(calls), 1)


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
