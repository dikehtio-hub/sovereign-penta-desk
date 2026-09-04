"""
Round 4 tests:
  Task 1 - Squeeze & Funding Exhaustion engine
  Task 3 - Backtester coverage safety gate

Fully offline: synthetic series.
"""


import unittest


from analytics.squeeze_engine import (
    CLASS_LONG_CASCADE,
    CLASS_NEUTRAL,
    CLASS_SHORT_SQUEEZE,
    analyse_coin,
    classify_squeeze,
    compute_funding_persistence,
    compute_oi_expansion,
    compute_squeeze_score,
    is_regime_aligned,
    percentile_rank,
    summarise_squeeze,
)
from analytics.funding_backtester import (
    backtest_funding_harvest,
    coverage_threshold_for,
    insufficient_history_label,
)

H = 3_600_000
M = 60_000


def _series(rates, ois=None, pxs=None, step=M):
    """(ts, funding, oi, px) tuples at a fixed cadence."""
    n = len(rates)
    ois = ois or [1_000_000.0] * n
    pxs = pxs or [100.0] * n
    return [(i * step, rates[i], ois[i], pxs[i]) for i in range(n)]


# --------------------------------------------------------------------------
# Task 1: squeeze engine
# --------------------------------------------------------------------------

class TestSqueezeComponents(unittest.TestCase):
    def test_percentile_rank_basic(self):
        self.assertAlmostEqual(percentile_rank([1, 2, 3, 4], 4), 87.5)
        self.assertAlmostEqual(percentile_rank([1, 2, 3, 4], 1), 12.5)

    def test_flat_series_ranks_neutral(self):
        """A constant rate is neither extreme; it must not score as stretched."""
        self.assertAlmostEqual(percentile_rank([5, 5, 5, 5], 5), 50.0)

    def test_empty_series_is_neutral(self):
        self.assertEqual(percentile_rank([], 1.0), 50.0)

    def test_oi_expansion_measures_growth(self):
        s = _series([0.001] * 3, ois=[100.0, 150.0, 200.0])
        self.assertAlmostEqual(compute_oi_expansion(s), 100.0)

    def test_oi_contraction_is_negative(self):
        s = _series([0.001] * 3, ois=[200.0, 150.0, 100.0])
        self.assertAlmostEqual(compute_oi_expansion(s), -50.0)

    def test_oi_expansion_safe_on_degenerate_input(self):
        self.assertEqual(compute_oi_expansion([]), 0.0)
        self.assertEqual(compute_oi_expansion(_series([0.001] * 3, ois=[0.0, 0.0, 0.0])), 0.0)

    def test_persistence_full_when_sign_never_flips(self):
        self.assertAlmostEqual(compute_funding_persistence(_series([0.001] * 10)), 1.0)

    def test_persistence_partial_when_sign_flips(self):
        s = _series([-0.001] * 5 + [0.001] * 5)
        self.assertAlmostEqual(compute_funding_persistence(s), 0.5)

    def test_persistence_zero_when_current_rate_is_zero(self):
        self.assertEqual(compute_funding_persistence(_series([0.001, 0.0])), 0.0)


class TestRegimeAlignment(unittest.TestCase):
    def test_high_percentile_aligns_with_positive_regime(self):
        self.assertTrue(is_regime_aligned(95.0, mean_funding=0.001))

    def test_low_percentile_does_not_align_with_positive_regime(self):
        """Crowded-long that has stopped paying is exhaustion, not crowding."""
        self.assertFalse(is_regime_aligned(2.0, mean_funding=0.001))

    def test_low_percentile_aligns_with_negative_regime(self):
        self.assertTrue(is_regime_aligned(3.0, mean_funding=-0.001))

    def test_misaligned_extremity_does_not_inflate_score(self):
        aligned = compute_squeeze_score(95.0, 20.0, 1.0, 100.0, mean_funding=0.001)
        misaligned = compute_squeeze_score(2.0, 20.0, 1.0, 100.0, mean_funding=0.001)
        self.assertGreater(aligned, misaligned)


class TestSqueezeScore(unittest.TestCase):
    def test_score_is_bounded(self):
        self.assertLessEqual(compute_squeeze_score(100.0, 1e9, 1.0, 1e9, 0.001), 100.0)
        self.assertGreaterEqual(compute_squeeze_score(50.0, -1e9, 0.0, 0.0, 0.0), 0.0)

    def test_neutral_market_scores_low(self):
        self.assertLess(compute_squeeze_score(50.0, 0.0, 0.0, 0.0, 0.0), 10.0)

    def test_crowded_persistent_expanding_scores_high(self):
        score = compute_squeeze_score(98.0, 60.0, 1.0, 250.0, mean_funding=0.001)
        self.assertGreater(score, 90.0)

    def test_oi_contraction_contributes_nothing(self):
        shrinking = compute_squeeze_score(95.0, -80.0, 1.0, 100.0, 0.001)
        flat = compute_squeeze_score(95.0, 0.0, 1.0, 100.0, 0.001)
        self.assertAlmostEqual(shrinking, flat)


class TestSqueezeClassification(unittest.TestCase):
    def test_positive_funding_is_a_long_cascade(self):
        """Longs pay shorts => longs are crowded => the unwind is downward."""
        self.assertEqual(classify_squeeze(0.001, score=80.0), CLASS_LONG_CASCADE)

    def test_negative_funding_is_a_short_squeeze(self):
        self.assertEqual(classify_squeeze(-0.001, score=80.0), CLASS_SHORT_SQUEEZE)

    def test_low_score_stays_neutral(self):
        self.assertEqual(classify_squeeze(0.001, score=10.0), CLASS_NEUTRAL)

    def test_zero_funding_is_neutral_regardless_of_score(self):
        self.assertEqual(classify_squeeze(0.0, score=99.0), CLASS_NEUTRAL)


class TestAnalyseCoin(unittest.TestCase):
    def test_insufficient_samples_returns_neutral(self):
        r = analyse_coin("T", series=_series([0.001] * 3), min_samples=20)
        self.assertFalse(r["sufficient_data"])
        self.assertEqual(r["classification"], CLASS_NEUTRAL)
        self.assertEqual(r["squeeze_score"], 0.0)

    def test_crowded_short_is_flagged_as_squeeze(self):
        # Sustained negative funding, deepening, with OI growing.
        rates = [-0.0005] * 20 + [-0.002] * 5
        ois = [1_000_000.0 + i * 40_000 for i in range(25)]
        r = analyse_coin("T", series=_series(rates, ois=ois), min_samples=20)
        self.assertTrue(r["sufficient_data"])
        self.assertEqual(r["classification"], CLASS_SHORT_SQUEEZE)
        self.assertGreater(r["squeeze_score"], 60.0)
        self.assertTrue(r["regime_aligned"])

    def test_crowded_long_is_flagged_as_cascade(self):
        rates = [0.0005] * 20 + [0.002] * 5
        ois = [1_000_000.0 + i * 40_000 for i in range(25)]
        r = analyse_coin("T", series=_series(rates, ois=ois), min_samples=20)
        self.assertEqual(r["classification"], CLASS_LONG_CASCADE)

    def test_exhausting_market_is_marked_and_scored_lower(self):
        """Sustained positive regime whose rate has collapsed toward neutral."""
        rates = [0.002] * 20 + [0.00001] * 5
        r = analyse_coin("T", series=_series(rates), min_samples=20)
        self.assertFalse(r["regime_aligned"])
        self.assertTrue(r["is_exhausting"])

    def test_flat_market_scores_low(self):
        r = analyse_coin("T", series=_series([0.00001] * 30), min_samples=20)
        self.assertLess(r["squeeze_score"], 60.0)

    def test_summarise_counts_by_class(self):
        rows = [
            {"classification": CLASS_SHORT_SQUEEZE, "squeeze_score": 80.0},
            {"classification": CLASS_LONG_CASCADE, "squeeze_score": 70.0},
            {"classification": CLASS_NEUTRAL, "squeeze_score": 10.0},
        ]
        s = summarise_squeeze(rows)
        self.assertEqual((s["short_squeeze"], s["long_cascade"], s["neutral"]), (1, 1, 1))
        self.assertEqual(s["max_score"], 80.0)

    def test_summarise_handles_empty(self):
        self.assertEqual(summarise_squeeze([])["scanned"], 0)


# --------------------------------------------------------------------------
# Task 2: titan pipeline
# --------------------------------------------------------------------------

HL_ADDR = "0x" + "a" * 40
PM_PROXY = "0x" + "b" * 40
class TestCoverageGate(unittest.TestCase):
    def test_apr_suppressed_below_threshold(self):
        thin = [(0, 0.001, 100.0), (H, 0.001, 100.0), (50 * H, 0.001, 100.0)]
        r = backtest_funding_harvest("T", hours=72, series=thin, now_ms=72 * H, max_gap_hours=1.5)
        self.assertLess(r["coverage_pct"], coverage_threshold_for(72.0))
        self.assertIsNone(r["realised_apr"])
        self.assertEqual(r["realised_apr_label"], insufficient_history_label(72.0))

    def test_apr_reported_above_threshold(self):
        full = [(i * H, 0.001, 100.0) for i in range(11)]
        r = backtest_funding_harvest("T", hours=10, series=full, now_ms=10 * H, max_gap_hours=1.5)
        self.assertGreaterEqual(r["coverage_pct"], coverage_threshold_for(10.0))
        self.assertIsNotNone(r["realised_apr"])
        self.assertIsNone(r["realised_apr_label"])

    def test_threshold_scales_with_window_length(self):
        """Superseded the flat 70% bar: a fixed % is not a fixed amount of evidence."""
        self.assertEqual(coverage_threshold_for(24.0), 75.0)
        self.assertEqual(coverage_threshold_for(168.0), 50.0)
        self.assertGreater(coverage_threshold_for(72.0), 50.0)
        self.assertLess(coverage_threshold_for(72.0), 75.0)

    def test_empty_series_is_labelled_not_annualised(self):
        r = backtest_funding_harvest("T", hours=72, series=[], now_ms=0)
        self.assertIsNone(r["realised_apr"])
        self.assertEqual(r["realised_apr_label"], insufficient_history_label(72.0))

    def test_funding_pnl_still_reported_when_apr_suppressed(self):
        """The measured return is real; only the extrapolation is withheld."""
        thin = [(0, 0.001, 100.0), (H, 0.001, 100.0), (50 * H, 0.001, 100.0)]
        r = backtest_funding_harvest("T", hours=72, series=thin, now_ms=72 * H, max_gap_hours=1.5)
        self.assertAlmostEqual(r["funding_pnl_pct"], 0.1, places=6)


if __name__ == "__main__":
    unittest.main()
