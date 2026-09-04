"""
Round 12 tests: the reactive fade execution architecture.

The 24h predictive squeeze classifier was retired on 2026-08-31 after its
pre-registered validation returned lift 0.351 against a 1.25x floor. Execution is
now purely reactive: it acts on a verified sweep that has already printed and
consults no squeeze score anywhere.

Fully offline.
"""

import json
import tempfile
import unittest
from pathlib import Path

from execution.paper_trader import PaperTrader
from execution.strategies.liquidation_fade_strategy import LiquidationFadeStrategy
from config.settings import (
    FADE_LIMIT_OFFSET_PCT,
    FADE_ORDER_TTL_SECONDS,
    FADE_STOP_LOSS_PCT,
    FADE_TAKE_PROFIT_PCT,
    ROTATION_COOLDOWN_SECONDS,
    ROTATION_MAX_COINS,
    ROTATION_MIN_DAY_VOLUME,
)


def exotic(coin="SKR", side="A", notional=5_000.0):
    return {"coin": coin, "side": side, "notional": notional}


# --------------------------------------------------------------------------
# Reactive entry: sweep -> resting fade
# --------------------------------------------------------------------------

class TestReactiveFade(unittest.TestCase):
    def setUp(self):
        self.t = PaperTrader(100_000.0)
        self.s = LiquidationFadeStrategy(self.t, regime_enabled=False)

    def test_forced_sell_rests_a_buy_below_the_pre_cascade_mark(self):
        r = self.s.on_liquidation_sweep(exotic(side="A"), 10.0, notional_oi=1e6)
        self.assertEqual(r["side"], "BUY")
        self.assertAlmostEqual(r["limit_price"], 10.0 * (1 - FADE_LIMIT_OFFSET_PCT / 100.0), places=6)

    def test_forced_buy_rests_a_sell_above_the_pre_cascade_mark(self):
        r = self.s.on_liquidation_sweep(exotic(side="B"), 100.0, notional_oi=1e6)
        self.assertEqual(r["side"], "SELL")
        self.assertAlmostEqual(r["limit_price"], 100.0 * (1 + FADE_LIMIT_OFFSET_PCT / 100.0), places=6)

    def test_take_profit_is_a_symmetric_snapback_from_the_limit(self):
        """
        Re-geometried 2026-08-31. Targeting the pre-cascade mark exactly paired a
        ~0.5% reward with a 1.5% stop (~1:3, needing >75% wins to break even).
        Both legs now sit FADE_TAKE_PROFIT_PCT from the limit, which lands just
        beyond the pre-cascade mark - a reverting cascade usually overshoots its
        own origin rather than stopping dead on it.
        """
        for side, mark in (("A", 10.0), ("B", 100.0)):
            t = PaperTrader(100_000.0)
            r = LiquidationFadeStrategy(t, regime_enabled=False).on_liquidation_sweep(
                exotic(side=side), mark, notional_oi=1e6)
            lim = r["limit_price"]
            expected = (lim * (1 + FADE_TAKE_PROFIT_PCT / 100.0) if side == "A"
                        else lim * (1 - FADE_TAKE_PROFIT_PCT / 100.0))
            self.assertAlmostEqual(r["take_profit"], expected, places=9)

    def test_stop_loss_is_measured_from_the_limit_not_the_mark(self):
        r = self.s.on_liquidation_sweep(exotic(side="A"), 10.0, notional_oi=1e6)
        expected = r["limit_price"] * (1 - FADE_STOP_LOSS_PCT / 100.0)
        self.assertAlmostEqual(r["stop_loss"], expected, places=9)

    def test_reward_to_risk_is_one_to_one(self):
        """Breaks even at a 50% win rate rather than the previous ~75%."""
        self.assertEqual(FADE_STOP_LOSS_PCT, 0.65)
        self.assertEqual(FADE_TAKE_PROFIT_PCT, 0.65)
        r = self.s.on_liquidation_sweep(exotic(side="A"), 10.0, notional_oi=1e6)
        lim = r["limit_price"]
        reward = r["take_profit"] - lim
        risk = lim - r["stop_loss"]
        self.assertAlmostEqual(reward / risk, 1.0, places=6)

    def test_take_profit_sits_between_entry_and_the_wick_for_a_buy(self):
        r = self.s.on_liquidation_sweep(exotic(side="A"), 10.0, notional_oi=1e6)
        self.assertGreater(r["take_profit"], r["limit_price"])
        self.assertLess(r["stop_loss"], r["limit_price"])

    def test_take_profit_sits_below_entry_for_a_sell(self):
        r = self.s.on_liquidation_sweep(exotic(side="B"), 100.0, notional_oi=1e6)
        self.assertLess(r["take_profit"], r["limit_price"])
        self.assertGreater(r["stop_loss"], r["limit_price"])

    def test_no_squeeze_score_is_consulted(self):
        """
        The retired classifier must not creep back in. A sweep alone is enough;
        nothing in the module may reference a squeeze score.
        """
        src = (Path(__file__).resolve().parent.parent
               / "execution" / "strategies" / "liquidation_fade_strategy.py"
               ).read_text(encoding="utf-8")
        self.assertNotIn("squeeze_score", src)
        self.assertNotIn("scan_squeeze_candidates", src)

    def test_sweep_below_trigger_is_ignored(self):
        self.assertIsNone(self.s.on_liquidation_sweep(exotic(notional=500.0), 10.0, notional_oi=1e6))

    def test_zero_mark_is_ignored(self):
        self.assertIsNone(self.s.on_liquidation_sweep(exotic(), 0.0, notional_oi=1e6))

    def test_one_fade_per_coin_during_a_cascade(self):
        for _ in range(6):
            self.s.on_liquidation_sweep(exotic(), 10.0, notional_oi=1e6)
        self.assertEqual(len(self.t.open_orders), 1)

    def test_fill_uses_the_limit_price(self):
        r = self.s.on_liquidation_sweep(exotic(side="A"), 10.0, notional_oi=1e6)
        self.t.check_open_orders({"SKR": r["limit_price"] - 0.05})
        self.assertAlmostEqual(self.t.positions["SKR"]["entry_price"], r["limit_price"], places=9)

    def test_unfilled_fade_expires_at_ttl(self):
        r = self.s.on_liquidation_sweep(exotic(side="A"), 10.0, notional_oi=1e6)
        r["placed_at"] -= int((FADE_ORDER_TTL_SECONDS + 1) * 1000)
        self.assertEqual(self.t.check_open_orders({"SKR": 1.0}), [])
        self.assertEqual(self.t.open_orders, [])
        self.assertNotIn("SKR", self.t.positions)


# --------------------------------------------------------------------------
# Paper account persistence
# --------------------------------------------------------------------------

class TestPaperPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "paper.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_realized_pnl_is_tracked_separately_from_cash(self):
        t = PaperTrader(100_000.0)
        t.place_market_order("SKR", "BUY", 100.0, 10.0)
        t.place_market_order("SKR", "SELL", 100.0, 11.0)
        s = t.get_account_summary()
        self.assertAlmostEqual(s["realized_pnl"], 100.0, places=6)
        self.assertEqual(s["closed_trades"], 1)

    def test_round_trip_preserves_state(self):
        t = PaperTrader(100_000.0)
        t.place_limit_order("SKR", "BUY", 100.0, 9.5)
        t.place_market_order("XMR", "BUY", 1.0, 100.0)
        t.save(self.path)

        r = PaperTrader.load(self.path)
        self.assertEqual(len(r.open_orders), 1)
        self.assertIn("XMR", r.positions)
        self.assertAlmostEqual(r.cash_balance, t.cash_balance, places=9)

    def test_missing_file_yields_a_fresh_account(self):
        r = PaperTrader.load(self.path.parent / "absent.json")
        self.assertEqual(r.cash_balance, 100_000.0)
        self.assertEqual(r.positions, {})

    def test_corrupt_file_yields_a_fresh_account_rather_than_raising(self):
        """A simulator refusing to start over a bad state file is worse than restarting."""
        self.path.write_text("{ not json", encoding="utf-8")
        r = PaperTrader.load(self.path)
        self.assertEqual(r.cash_balance, 100_000.0)

    def test_save_is_atomic(self):
        t = PaperTrader(100_000.0)
        t.save(self.path)
        self.assertTrue(self.path.exists())
        self.assertFalse(self.path.with_suffix(".json.tmp").exists())
        json.loads(self.path.read_text(encoding="utf-8"))

    def test_trade_history_is_bounded_on_save(self):
        """The file is rewritten on every flush; unbounded history slows each write."""
        t = PaperTrader(1_000_000.0)
        for i in range(260):
            t.trade_history.append({"order_id": f"x{i}"})
        t.save(self.path)
        self.assertEqual(len(json.loads(self.path.read_text(encoding="utf-8"))["trade_history"]), 200)

    def test_expired_orders_are_counted(self):
        t = PaperTrader(100_000.0)
        o = t.place_limit_order("SKR", "BUY", 10.0, 9.5)
        o["placed_at"] -= int((FADE_ORDER_TTL_SECONDS + 1) * 1000)
        t.expire_stale_orders()
        self.assertEqual(t.get_account_summary()["expired_orders"], 1)


# --------------------------------------------------------------------------
# Volume-driven rotation (squeeze score no longer gates the feed)
# --------------------------------------------------------------------------

class TestVolumeRotationConfig(unittest.TestCase):
    def test_rotation_constants(self):
        self.assertEqual(ROTATION_MAX_COINS, 35)
        self.assertEqual(ROTATION_COOLDOWN_SECONDS, 1200.0)
        self.assertEqual(ROTATION_MIN_DAY_VOLUME, 100_000.0)

    def test_collector_ranks_by_volume_not_squeeze_score(self):
        """
        Gating the feed on an anti-predictive classifier was actively selecting
        the markets least likely to liquidate. Liquidations happen where flow is.
        """
        src = (Path(__file__).resolve().parent.parent
               / "collectors" / "market_collector.py").read_text(encoding="utf-8")
        self.assertIn("_compute_rotation_candidates", src)
        self.assertNotIn("_compute_squeeze_candidates", src)
        self.assertNotIn("scan_squeeze_candidates", src)

    def test_collector_places_fades_reactively(self):
        src = (Path(__file__).resolve().parent.parent
               / "collectors" / "market_collector.py").read_text(encoding="utf-8")
        self.assertIn("on_liquidation_sweep", src)
        self.assertIn("LiquidationFadeStrategy", src)


class TestSqueezeEngineRetainedAsInformational(unittest.TestCase):
    """Retired from execution, kept as a read-only monitoring surface."""

    def test_squeeze_engine_module_still_exists(self):
        from analytics import squeeze_engine
        self.assertTrue(hasattr(squeeze_engine, "scan_squeeze_candidates"))

    def test_squeeze_command_still_registered(self):
        src = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        self.assertIn('"squeeze"', src)

    def test_execution_layer_does_not_import_the_squeeze_engine(self):
        for rel in ("execution/paper_trader.py",
                    "execution/strategies/liquidation_fade_strategy.py"):
            src = (Path(__file__).resolve().parent.parent / rel).read_text(encoding="utf-8")
            self.assertNotIn("squeeze_engine", src, f"{rel} still couples execution to the classifier")


if __name__ == "__main__":
    unittest.main()
