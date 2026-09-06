"""
Tests for Item 14 Whale Cascade Sweeper Replay Engine (cascade_replay.py).
Fully offline with synthetic fixtures.
"""

import unittest

from analytics.cascade_replay import (
    classify_verdict,
    cluster_bootstrap,
    compute_horizon_stats,
    concentration_hhi,
    evaluate_sample_gates,
    REOPEN_MAX_COIN_SHARE,
    REOPEN_MAX_HHI,
    REOPEN_MIN_COINS,
    REOPEN_MIN_EVENTS,
)


class TestCascadeReplay(unittest.TestCase):

    def test_concentration_hhi(self):
        # 1. Single dominant coin = 1.0
        self.assertAlmostEqual(concentration_hhi([100]), 1.0)

        # 2. Two equal coins = 0.50
        self.assertAlmostEqual(concentration_hhi([50, 50]), 0.50)

        # 3. Four equal coins = 0.25
        self.assertAlmostEqual(concentration_hhi([25, 25, 25, 25]), 0.25)

        # 4. Empty = 0.0
        self.assertEqual(concentration_hhi([]), 0.0)

    def test_sample_gates_pass(self):
        # 600 events evenly distributed across 30 coins
        rows = []
        for i in range(600):
            coin = f"COIN_{i % 30}"
            rows.append({"coin": coin})

        res = evaluate_sample_gates(rows)
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "SAMPLE_ADEQUATE")
        self.assertEqual(res["metrics"]["events"], 600)
        self.assertEqual(res["metrics"]["coins"], 30)
        self.assertAlmostEqual(res["metrics"]["top_coin_share"], 1 / 30, places=3)
        self.assertLess(res["metrics"]["hhi"], REOPEN_MAX_HHI)

    def test_sample_gates_failures(self):
        # 1. Under minimum events (< 500)
        rows_few = [{"coin": f"COIN_{i % 25}"} for i in range(400)]
        res_few = evaluate_sample_gates(rows_few)
        self.assertFalse(res_few["passed"])
        self.assertTrue(any("events=" in f for f in res_few["failures"]))

        # 2. Under minimum coins (< 20)
        rows_coins = [{"coin": f"COIN_{i % 10}"} for i in range(600)]
        res_coins = evaluate_sample_gates(rows_coins)
        self.assertFalse(res_coins["passed"])
        self.assertTrue(any("coins=" in f for f in res_coins["failures"]))

        # 3. Top coin share exceeds 20%
        # 300 events in COIN_0, 300 events spread across 25 coins
        rows_top = [{"coin": "COIN_0"} for _ in range(300)]
        for i in range(300):
            rows_top.append({"coin": f"COIN_{1 + (i % 25)}"})
        res_top = evaluate_sample_gates(rows_top)
        self.assertFalse(res_top["passed"])
        self.assertTrue(any("top_coin_share=" in f for f in res_top["failures"]))

        # 4. HHI exceeds 0.15
        self.assertTrue(any("hhi=" in f for f in res_top["failures"]))

    def test_compute_horizon_stats(self):
        rows = [
            {"mfe_30m": 2.0, "mae_30m": 1.0, "notional_usd": 100.0},
            {"mfe_30m": 4.0, "mae_30m": 2.0, "notional_usd": 200.0},
            {"mfe_30m": 6.0, "mae_30m": 3.0, "notional_usd": 300.0},
        ]
        stats = compute_horizon_stats(rows, "30m")

        self.assertEqual(stats["n"], 3)
        self.assertAlmostEqual(stats["median_mfe"], 4.0)
        self.assertAlmostEqual(stats["median_mae"], 2.0)
        self.assertAlmostEqual(stats["median_fade_ratio"], 2.0)
        self.assertAlmostEqual(stats["mean_fade_ratio"], 2.0)
        self.assertAlmostEqual(stats["win_share"], 100.0)
        self.assertAlmostEqual(stats["median_net_move"], 2.0)

        # Dollar expectancy: ( (2-1)*100 + (4-2)*200 + (6-3)*300 ) / 600 = (100 + 400 + 900) / 600 = 1400 / 600 = 2.3333
        self.assertAlmostEqual(stats["dollar_expectancy"], 1400.0 / 600.0, places=4)

    def test_cluster_bootstrap_reproducibility(self):
        # Synthetic fixture across 5 coins
        rows = []
        for i in range(100):
            coin = f"COIN_{i % 5}"
            # High MFE vs MAE
            rows.append({"coin": coin, "mfe_30m": 3.0, "mae_30m": 1.0})

        res1 = cluster_bootstrap(rows, threshold=1.25, resamples=500, seed=42)
        res2 = cluster_bootstrap(rows, threshold=1.25, resamples=500, seed=42)

        self.assertEqual(res1["hits"], res2["hits"])
        self.assertEqual(res1["p_ge_threshold"], res2["p_ge_threshold"])
        self.assertEqual(res1["p_ge_threshold"], 1.0)

    def test_cluster_bootstrap_low_ratio(self):
        # Adverse excursions outweigh favorable
        rows = []
        for i in range(100):
            coin = f"COIN_{i % 5}"
            rows.append({"coin": coin, "mfe_30m": 1.0, "mae_30m": 3.0})

        res = cluster_bootstrap(rows, threshold=1.25, resamples=500, seed=42)
        self.assertEqual(res["p_ge_threshold"], 0.0)

    def test_classify_verdict(self):
        pass_gates = {"passed": True}
        fail_gates = {"passed": False}

        # 1. Gate fail -> INSUFFICIENT
        self.assertEqual(classify_verdict(fail_gates, 0.95), "INSUFFICIENT")

        # 2. None p-value -> INSUFFICIENT
        self.assertEqual(classify_verdict(pass_gates, None), "INSUFFICIENT")

        # 3. P < 0.50 -> FAIL
        self.assertEqual(classify_verdict(pass_gates, 0.42), "FAIL")

        # 4. 0.50 <= P <= 0.90 -> RETUNE
        self.assertEqual(classify_verdict(pass_gates, 0.75), "RETUNE")

        # 5. P > 0.90 symmetric -> PASS
        self.assertEqual(classify_verdict(pass_gates, 0.95, cluster_p_side_a=0.91, cluster_p_side_b=0.88), "PASS")

        # 6. P > 0.90 with one side failing (< 0.50) -> PASS-ASYMMETRIC
        self.assertEqual(classify_verdict(pass_gates, 0.92, cluster_p_side_a=0.98, cluster_p_side_b=0.45), "PASS-ASYMMETRIC")


if __name__ == "__main__":
    unittest.main()
