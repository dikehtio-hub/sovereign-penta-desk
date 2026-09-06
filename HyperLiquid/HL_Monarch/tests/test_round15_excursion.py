"""
Tests for the MFE/MAE excursion benchmark.

This is the module that decides whether the fade thesis lives or dies, so its
measurement semantics need to be pinned hard. In particular: a missing window is
not a zero excursion, the ratio is a ratio-of-means rather than a mean-of-ratios,
and the random-entry control is not optional decoration - the live run scored
0.513 against a control of 1.092, and without the control that 0.513 would have
been read against a nominal null of 1.00 and understated the gap.

Fully offline - synthetic price series throughout.
"""

import unittest

from analytics.wick_benchmark import (
    _aggregate, benchmark, cluster_bootstrap, concentration_hhi, excursion,
    reopening_gate, verdict, MIN_FORWARD_SAMPLES,
)

MIN = 60_000


def series(prices, step_ms=10_000, start=0):
    return [(start + i * step_ms, float(p)) for i, p in enumerate(prices)]


class TestExcursionMeasurement(unittest.TestCase):
    def test_a_long_measures_upside_as_favourable(self):
        s = series([100, 102, 98, 100, 101, 100, 100])
        r = excursion(s, 0, is_long=True, horizon_minutes=10)
        self.assertAlmostEqual(r["mfe"], 2.0, places=6)
        self.assertAlmostEqual(r["mae"], 2.0, places=6)

    def test_a_short_measures_downside_as_favourable(self):
        """Same series, opposite side: MFE and MAE swap. Getting this backwards
        would invert the verdict on every forced-buy cascade."""
        s = series([100, 104, 99, 100, 100, 100, 100])
        long_r = excursion(s, 0, is_long=True, horizon_minutes=10)
        short_r = excursion(s, 0, is_long=False, horizon_minutes=10)
        self.assertAlmostEqual(long_r["mfe"], short_r["mae"], places=9)
        self.assertAlmostEqual(long_r["mae"], short_r["mfe"], places=9)

    def test_only_the_forward_window_is_measured(self):
        """A spike after the horizon must not count - that is lookahead."""
        s = series([100, 100, 100, 100, 100, 100, 100, 500], step_ms=60_000)
        r = excursion(s, 0, is_long=True, horizon_minutes=5)
        self.assertAlmostEqual(r["mfe"], 0.0, places=9)

    def test_prior_prices_are_not_measured(self):
        """Entry is at the first sample AT or AFTER the event, never before it."""
        s = series([500, 100, 100, 100, 100, 100, 100], step_ms=60_000)
        r = excursion(s, 60_000, is_long=True, horizon_minutes=5)
        self.assertAlmostEqual(r["entry_px"], 100.0, places=9)
        self.assertAlmostEqual(r["mfe"], 0.0, places=9)

    def test_a_thin_window_is_none_not_zero(self):
        """
        The distinction that keeps the benchmark honest: an unmeasurable window
        must be DROPPED, because zero-filling it would drag both MFE and MAE
        toward zero and quietly pull the ratio toward 1.0.
        """
        s = series([100, 101])
        self.assertIsNone(excursion(s, 0, is_long=True, horizon_minutes=10))

    def test_exactly_the_minimum_samples_is_measurable(self):
        s = series([100] * (MIN_FORWARD_SAMPLES + 1))
        self.assertIsNotNone(excursion(s, 0, is_long=True, horizon_minutes=10))

    def test_an_event_after_the_series_ends_is_none(self):
        self.assertIsNone(excursion(series([100, 101, 102]), 10**13, True, 10))

    def test_a_flat_market_has_zero_excursion_both_ways(self):
        r = excursion(series([100] * 10), 0, is_long=True, horizon_minutes=10)
        self.assertEqual((r["mfe"], r["mae"]), (0.0, 0.0))


class TestAggregation(unittest.TestCase):
    def test_the_ratio_is_means_not_mean_of_ratios(self):
        """
        With one near-zero MAE, mean-of-ratios explodes while ratio-of-means stays
        bounded. The live data has plenty of quiet events, so this is the
        difference between a real number and a meaningless one.
        """
        rows = [{"mfe": 1.0, "mae": 0.001}, {"mfe": 1.0, "mae": 2.0}]
        agg = _aggregate(rows)
        self.assertAlmostEqual(agg["ratio"], 1.0 / 1.0005, places=6)
        self.assertLess(agg["ratio"], 2.0)   # mean-of-ratios would be ~500

    def test_zero_adverse_movement_yields_no_ratio_rather_than_infinity(self):
        self.assertIsNone(_aggregate([{"mfe": 1.0, "mae": 0.0}])["ratio"])

    def test_empty_input_is_reported_as_no_data(self):
        self.assertEqual(_aggregate([]), {"n": 0, "ratio": None})

    def test_win_share_counts_events_where_favourable_beat_adverse(self):
        rows = [{"mfe": 2.0, "mae": 1.0}, {"mfe": 1.0, "mae": 2.0},
                {"mfe": 3.0, "mae": 1.0}, {"mfe": 0.5, "mae": 1.0}]
        self.assertAlmostEqual(_aggregate(rows)["win_share"], 50.0, places=6)


class TestVerdict(unittest.TestCase):
    def horizons(self, ratio, control, n=100):
        return {"horizons": {30.0: {
            "signal": {"ratio": ratio, "n": n},
            "control": {"ratio": control, "n": n},
            "edge_vs_control": (ratio - control) if control else None,
        }}}

    def test_a_strong_signal_beating_its_control_confirms_alpha(self):
        self.assertEqual(verdict(self.horizons(1.80, 1.05))["verdict"], "ALPHA_CONFIRMED")

    def test_a_strong_ratio_matched_by_its_control_is_not_alpha(self):
        """
        The trap the control exists to catch: 1.60 looks like alpha until the
        control also scores 1.58, at which point it is a property of the tape.
        """
        self.assertEqual(verdict(self.horizons(1.60, 1.58))["verdict"],
                         "NO_EDGE_VS_CONTROL")

    def test_a_ratio_far_below_one_is_no_alpha(self):
        """The live result: 0.513 signal against a 1.092 control."""
        self.assertEqual(verdict(self.horizons(0.513, 1.092))["verdict"], "NO_ALPHA")

    def test_a_thin_sample_refuses_to_return_a_verdict(self):
        self.assertEqual(verdict(self.horizons(2.0, 1.0, n=5))["verdict"],
                         "INSUFFICIENT_DATA")

    def test_no_horizons_is_insufficient_rather_than_an_error(self):
        self.assertEqual(verdict({"horizons": {}})["verdict"], "INSUFFICIENT_DATA")


class _Cursor(list):
    """sqlite3 cursors are iterable AND expose fetchall(); the fake must be both."""

    def fetchall(self):
        return list(self)


class TestBenchmarkIntegration(unittest.TestCase):
    class FakeRepo:
        def __init__(self, events, series_map):
            self._events, self._series = events, series_map
            outer = self

            class Conn:
                def __enter__(self_c): return self_c
                def __exit__(self_c, *a): return False

                def execute(self_c, sql, params=()):
                    if "liquidation_events" in sql:
                        rows = [dict(e) for e in outer._events]
                    else:
                        coin = params[0]
                        rows = [{"timestamp": t, "mark_px": p}
                                for t, p in outer._series.get(coin, [])]
                    return _Cursor(rows)

            class DB:
                connection = Conn()
            self.db = DB()

    def test_a_mean_reverting_signal_scores_above_its_control(self):
        # Price dips then recovers above entry: favourable for a long fade.
        prices = [100, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
        repo = self.FakeRepo(
            [{"coin": "X", "side": "A", "px": 100.0, "notional": 1e5,
              "time": 0, "source": "trade_sweep"}],
            {"X": series(prices, step_ms=30_000)},
        )
        r = benchmark(repo=repo, source="trade_sweep", horizons=(5.0,), control_multiple=1)
        self.assertEqual(r["events"], 1)
        self.assertGreater(r["horizons"][5.0]["signal"]["ratio"], 1.0)

    def test_a_continuation_signal_scores_below_one(self):
        """What the live data actually shows: price keeps going against the fade."""
        prices = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89]
        repo = self.FakeRepo(
            [{"coin": "X", "side": "A", "px": 100.0, "notional": 1e5,
              "time": 0, "source": "trade_sweep"}],
            {"X": series(prices, step_ms=30_000)},
        )
        r = benchmark(repo=repo, source="trade_sweep", horizons=(5.0,), control_multiple=1)
        self.assertLess(r["horizons"][5.0]["signal"]["ratio"], 1.0)

    def test_coverage_is_reported_so_a_thin_result_cannot_hide(self):
        repo = self.FakeRepo(
            [{"coin": "X", "side": "A", "px": 100.0, "notional": 1e5, "time": 0,
              "source": "trade_sweep"},
             {"coin": "MISSING", "side": "A", "px": 100.0, "notional": 1e5, "time": 0,
              "source": "trade_sweep"}],
            {"X": series([100] * 12, step_ms=30_000)},
        )
        r = benchmark(repo=repo, source="trade_sweep", horizons=(5.0,), control_multiple=1)
        self.assertAlmostEqual(r["horizons"][5.0]["coverage_pct"], 50.0, places=6)
        self.assertEqual(r["horizons"][5.0]["skipped"], 1)

    def test_no_events_is_an_empty_result_not_a_crash(self):
        r = benchmark(repo=self.FakeRepo([], {}), source="trade_sweep")
        self.assertEqual(r["events"], 0)

    def test_the_run_is_deterministic_for_a_fixed_seed(self):
        """The control is random; a wandering verdict would be unauditable."""
        repo = self.FakeRepo(
            [{"coin": "X", "side": "A", "px": 100.0, "notional": 1e5, "time": 0,
              "source": "trade_sweep"}],
            {"X": series([100 + (i % 5) for i in range(60)], step_ms=10_000)},
        )
        a = benchmark(repo=repo, source="trade_sweep", horizons=(5.0,), seed=15)
        b = benchmark(repo=repo, source="trade_sweep", horizons=(5.0,), seed=15)
        self.assertEqual(a["horizons"][5.0]["control"], b["horizons"][5.0]["control"])


if __name__ == "__main__":
    unittest.main()


class TestConcentrationAudit(unittest.TestCase):
    """
    The auditing standard adopted after the first excursion run was reported at
    "p < 1e-15" on data where two microcaps supplied 83% of events. These numbers
    now appear on every run so the same mistake cannot be made silently.
    """

    def test_hhi_of_evenly_spread_events_is_one_over_k(self):
        self.assertAlmostEqual(concentration_hhi([10, 10, 10, 10]), 0.25, places=9)

    def test_hhi_of_a_single_dominant_asset_approaches_one(self):
        self.assertGreater(concentration_hhi([990, 5, 5]), 0.95)

    def test_hhi_matches_the_two_microcap_case_that_prompted_it(self):
        """CASHCAT 199 + PONS 197 of 476 -> two ~42% shares dominate."""
        self.assertGreater(concentration_hhi([199, 197, 28, 17, 7, 6, 5, 3]), 0.30)

    def test_hhi_of_no_events_is_zero_not_a_division_error(self):
        self.assertEqual(concentration_hhi([]), 0.0)
        self.assertEqual(concentration_hhi([0, 0]), 0.0)


class TestClusterBootstrap(unittest.TestCase):
    def test_a_uniformly_adverse_signal_almost_never_resamples_above_one(self):
        by_coin = {f"C{i}": [{"mfe": 1.0, "mae": 2.0}] * 5 for i in range(10)}
        self.assertLess(cluster_bootstrap(by_coin, threshold=1.0, resamples=2000), 0.01)

    def test_a_favourable_signal_almost_always_resamples_above_one(self):
        by_coin = {f"C{i}": [{"mfe": 2.0, "mae": 1.0}] * 5 for i in range(10)}
        self.assertGreater(cluster_bootstrap(by_coin, threshold=1.0, resamples=2000), 0.99)

    def test_a_result_carried_by_one_coin_is_reported_as_uncertain(self):
        """
        The property that matters. Event-level resampling of this data would look
        decisive because the dominant coin supplies most rows; resampling COINS
        exposes that the answer depends on whether that coin is drawn.
        """
        by_coin = {"DOMINANT": [{"mfe": 3.0, "mae": 1.0}] * 100}
        by_coin.update({f"C{i}": [{"mfe": 1.0, "mae": 1.2}] for i in range(5)})
        p = cluster_bootstrap(by_coin, threshold=1.0, resamples=4000)
        self.assertGreater(p, 0.05)
        self.assertLess(p, 0.95)

    def test_it_is_deterministic_for_a_fixed_seed(self):
        by_coin = {f"C{i}": [{"mfe": 1.0, "mae": 1.1}] * 3 for i in range(6)}
        a = cluster_bootstrap(by_coin, resamples=500, seed=3)
        b = cluster_bootstrap(by_coin, resamples=500, seed=3)
        self.assertEqual(a, b)

    def test_no_coins_yields_none(self):
        self.assertIsNone(cluster_bootstrap({}))


class TestReopeningGate(unittest.TestCase):
    """
    Deliberately asymmetric: retiring took p=0.024 on a narrow sample, so coming
    back must cost more than leaving did.
    """

    def gate_input(self, n=600, coins=25, share=0.15, span=8.0):
        return {"span_days": span, "horizons": {30.0: {
            "signal": {"ratio": 1.30, "n": n},
            "coins_measured": coins, "top_coin_share": share,
        }}}

    def test_a_broad_sample_is_eligible(self):
        g = reopening_gate(self.gate_input())
        self.assertEqual(g["status"], "SAMPLE_ADEQUATE")
        self.assertTrue(g["eligible"])

    def test_too_few_events_is_not_eligible(self):
        self.assertFalse(reopening_gate(self.gate_input(n=400))["eligible"])

    def test_too_few_coins_is_not_eligible(self):
        self.assertFalse(reopening_gate(self.gate_input(coins=12))["eligible"])

    def test_a_dominant_coin_disqualifies_an_otherwise_large_sample(self):
        """The exact failure of the original verdict: n was fine, breadth was not."""
        g = reopening_gate(self.gate_input(n=2000, coins=25, share=0.43))
        self.assertFalse(g["eligible"])
        self.assertIn("top coin", g["detail"])

    def test_the_live_sample_that_produced_the_verdict_is_too_narrow(self):
        g = reopening_gate(self.gate_input(n=482, coins=14, share=0.43))
        self.assertEqual(g["status"], "SAMPLE_TOO_NARROW")

    def test_a_short_covered_span_is_not_eligible(self):
        """Round 115: retention could hold 7 days, but the rows only span 5.5 - not a qualifying sample."""
        g = reopening_gate(self.gate_input(span=5.5))
        self.assertEqual(g["status"], "SAMPLE_TOO_NARROW")
        self.assertIn("span", g["detail"])

    def test_an_unreported_span_fails_closed(self):
        r = self.gate_input()
        r.pop("span_days")
        self.assertFalse(reopening_gate(r)["eligible"])

    def test_no_data_is_reported_rather_than_raising(self):
        self.assertFalse(reopening_gate({"horizons": {}})["eligible"])
