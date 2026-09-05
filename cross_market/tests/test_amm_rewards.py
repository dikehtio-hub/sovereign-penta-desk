"""
Item 13, Phase 1 (Round 90): the AMM quoting engine and rewards estimator, offline.
What must be true: long inventory shades both quotes down and the limit removes
the growing side; quotes sit on the tick grid inside (0, 1) and inside the rewards
window when asked; the rewards score follows the programme's shape (window, min
size, two sides in the band); the simulation is deterministic, refuses on HALT,
pulls on events and volatility spikes, and its accounting adds up; receipts are
PAPER and tagged polymarket_amm.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cross_market import amm_rewards as amm


class AmmBase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.halt = self.root / "HALT.flag"
        # gamma 0.05, sigma 0.01, tau 60: 200 shares shade the reservation price by 6 cents - visible, inside (0, 1)
        self.p = amm.QuoteParams(gamma=0.05, sigma=0.01, horizon_min=60.0, k=1.5, arrival_a=0.5, size=100.0, inventory_limit=300.0)

    def tearDown(self):
        self.temp.cleanup()


class TestQuoting(AmmBase):

    def test_inventory_shades_quotes_and_the_limit_makes_them_one_sided(self):
        flat = amm.quote(0.50, 0.0, self.p)
        self.assertTrue(flat.two_sided) ; self.assertLess(flat.bid, 0.50) ; self.assertGreater(flat.ask, 0.50)
        self.assertAlmostEqual(flat.reservation, 0.50)
        self.assertEqual(round(flat.bid / amm.TICK), flat.bid / amm.TICK)              # on the tick grid
        long = amm.quote(0.50, 200.0, self.p)
        short = amm.quote(0.50, -200.0, self.p)
        self.assertLess(long.reservation, 0.50) ; self.assertGreater(short.reservation, 0.50)
        # long: the bid backs off; the ask would shade down too but never below fair + one tick (the clamp)
        self.assertLess(long.bid, flat.bid) ; self.assertLessEqual(long.ask, flat.ask) ; self.assertGreaterEqual(long.ask, 0.50 + amm.TICK)
        self.assertGreater(short.ask, flat.ask) ; self.assertGreaterEqual(short.bid, flat.bid) ; self.assertLessEqual(short.bid, 0.50 - amm.TICK)
        self.assertAlmostEqual(long.reservation, 0.50 - 200 * 0.05 * 0.01 ** 2 * 60)              # 6 cents
        self.assertLess(long.bid, 0.50) ; self.assertGreater(short.ask, 0.50)                    # never cross fair
        capped = amm.quote(0.50, 300.0, self.p)
        self.assertIsNone(capped.bid) ; self.assertIsNotNone(capped.ask) ; self.assertIn("inventory limit", capped.reason)
        capped = amm.quote(0.50, -300.0, self.p)
        self.assertIsNone(capped.ask) ; self.assertIsNotNone(capped.bid)
        # clamped inside (0, 1), widened on a spike, and pulled inside the rewards window on request
        edge = amm.quote(0.995, 0.0, self.p)
        self.assertLessEqual(edge.ask, 0.99) ; self.assertLess(edge.bid, edge.ask)
        wide = amm.quote(0.50, 0.0, self.p, vol_multiple=3.0)
        self.assertGreater(wide.ask - wide.bid, flat.ask - flat.bid)
        windowed = amm.quote(0.50, 0.0, amm.QuoteParams(rewards_max_spread=0.03, sigma=0.05, horizon_min=600))
        self.assertLessEqual(0.50 - windowed.bid, 0.03) ; self.assertLessEqual(windowed.ask - 0.50, 0.03)
        self.assertGreaterEqual(amm.optimal_half_spread(amm.QuoteParams(gamma=0.0)), amm.TICK)


class TestRewards(AmmBase):

    def test_scores_follow_the_programme_shape(self):
        cfg = amm.RewardsConfig(pool_per_day=144.0, max_spread=0.03, min_size=50.0, competitor_q=100.0)
        self.assertAlmostEqual(amm.order_score(0.50, 100.0, 0.50, cfg), 100.0)          # at the mid: full score
        self.assertAlmostEqual(amm.order_score(0.485, 100.0, 0.50, cfg), 25.0)          # half way out: a quarter
        self.assertEqual(amm.order_score(0.46, 100.0, 0.50, cfg), 0.0)                  # outside the window
        self.assertEqual(amm.order_score(0.50, 10.0, 0.50, cfg), 0.0)                   # below the min size
        self.assertAlmostEqual(amm.q_min(0.49, 0.51, 100.0, 0.50, cfg), amm.order_score(0.49, 100.0, 0.50, cfg))
        self.assertEqual(amm.q_min(0.49, None, 100.0, 0.50, cfg), 0.0)                  # in the band: both sides needed
        self.assertGreater(amm.q_min(0.04, None, 100.0, 0.05, cfg), 0.0)                # outside: one side suffices
        self.assertAlmostEqual(amm.reward_per_minute(100.0, cfg), 144.0 / 1440 * 0.5)
        self.assertEqual(amm.reward_per_minute(0.0, cfg), 0.0)


class TestSimulation(AmmBase):

    def test_is_deterministic_accounts_correctly_and_pulls_on_events_and_spikes(self):
        path = amm.synthetic_fair_path(240, start=0.5, sigma=0.002, seed=3, jump_at=200, jump=0.08)
        cfg = amm.RewardsConfig(pool_per_day=144.0, competitor_q=1000.0)
        a = amm.simulate(path, self.p, cfg, seed=11, halt_path=self.halt, events=[(100, 110)], vol_threshold=0.004)
        b = amm.simulate(path, self.p, cfg, seed=11, halt_path=self.halt, events=[(100, 110)], vol_threshold=0.004)
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertEqual(a.minutes, 240)
        self.assertEqual(a.minutes_quoted + a.minutes_one_sided + a.minutes_pulled, 240)
        self.assertGreaterEqual(a.pulled_reasons.get("event window 100-110", 0), 11)
        self.assertTrue(any(k.startswith("volatility spike") for k in a.pulled_reasons), a.pulled_reasons)
        self.assertGreater(len(a.fills), 0)
        cash = sum(-f.price * f.shares if f.side == "BUY" else f.price * f.shares for f in a.fills)
        inv = sum(f.shares if f.side == "BUY" else -f.shares for f in a.fills)
        self.assertAlmostEqual(a.cash, cash, places=6) ; self.assertAlmostEqual(a.inventory, inv, places=6)
        self.assertAlmostEqual(a.mark_to_market, a.cash + a.inventory * path[-1], places=6)
        self.assertAlmostEqual(a.pnl, a.mark_to_market + a.rewards, places=6)
        self.assertLessEqual(a.max_abs_inventory, self.p.inventory_limit + self.p.size)   # one fill past the limit at most
        self.assertGreater(a.rewards, 0.0) ; self.assertLess(a.rewards, 144.0)
        self.assertEqual(a.assumptions["rewards"]["pool_per_day"], 144.0)
        self.assertIn("fill_model", a.assumptions)
        # the inventory limit shows up as one-sided minutes when fills pile up on one side
        greedy = amm.QuoteParams(arrival_a=5.0, k=0.1, size=100.0, inventory_limit=200.0, gamma=0.01)
        c = amm.simulate([0.5] * 60, greedy, None, seed=1, halt_path=self.halt)
        self.assertGreater(c.minutes_one_sided + c.minutes_quoted, 0)
        self.assertLessEqual(c.max_abs_inventory, 300.0)
        # HALT refuses before the first minute
        self.halt.write_text("{}", encoding="utf-8")
        h = amm.simulate(path, self.p, cfg, seed=11, halt_path=self.halt)
        self.assertEqual(h.fills, []) ; self.assertEqual(h.minutes_pulled, 240)
        self.assertIn("HALT.flag present - refused", h.pulled_reasons)
        self.assertIn("REFUSED: HALT.flag", amm.format_result(h, "M"))
        self.assertAlmostEqual(amm.rolling_sigma([0.5, 0.5, 0.5], 2, 10), 0.0)


class TestReceiptsAndCli(AmmBase):

    def test_paper_receipts_are_maker_tagged_and_the_cli_runs_offline(self):
        path = [0.5] * 30
        p = amm.QuoteParams(arrival_a=3.0, k=0.2, size=100.0, inventory_limit=1000.0)
        result = amm.simulate(path, p, None, seed=2, halt_path=self.halt)
        self.assertGreater(len(result.fills), 0)
        seen = []
        written = amm.record_paper_fills(result, "MKT", receipts_dir=self.root / "paper",
                                         writer=lambda **kw: seen.append(kw) or Path("r.csv"))
        self.assertEqual(len(written), len(result.fills))
        self.assertTrue(all(kw["strategy"] == "polymarket_amm" and kw["fee"] == 0.0 and "maker:1" in kw["extra_notes"] for kw in seen))
        self.assertTrue(all(kw["imports_dir"] == self.root / "paper" for kw in seen))
        real = amm.record_paper_fills(result, "MKT", receipts_dir=self.root / "real")
        self.assertEqual(len(real), len(result.fills)) ; self.assertTrue(all(r.exists() for r in real))
        self.assertTrue(str(amm.PAPER_RECEIPTS_DIR).replace("\\", "/").endswith("cross_market/data/paper_receipts"))
        fair = self.root / "fair.json"
        fair.write_text(json.dumps(path), encoding="utf-8")
        common = ["--fair-path", str(fair), "--halt-flag", str(self.halt), "--arrival", "3", "--k", "0.2", "--seed", "2"]
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(amm.main(common + ["--pool", "144", "--competitor-q", "500"]), 0)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("POLYMARKET AMM SIMULATION", printed) ; self.assertIn("rewards ASSUMED: pool $144.00/day", printed)
        self.assertIn("places nothing", printed)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(amm.main(common + ["--json", "--event", "5-8", "--vol-threshold", "0.01"]), 0)
        payload = json.loads(fake_print.call_args_list[0].args[0])
        self.assertEqual(payload["pulled_reasons"].get("event window 5-8"), 4)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(amm.main(common + ["--paper", "--receipts-dir", str(self.root / "cli_paper")]), 0)
        self.assertGreater(len(list((self.root / "cli_paper").glob("*.csv"))), 0)
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(amm.main(["--minutes", "30", "--seed", "4", "--halt-flag", str(self.halt)]), 0)   # synthetic path
        self.halt.write_text("{}", encoding="utf-8")
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(amm.main(common), amm.EXIT_HALTED)
        self.assertIn("REFUSED: HALT.flag", " ".join(str(c.args[0]) for c in fake_print.call_args_list))
