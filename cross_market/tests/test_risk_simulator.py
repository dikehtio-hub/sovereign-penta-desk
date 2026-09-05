"""
Item 19 - multi-desk Monte Carlo risk-of-ruin simulator (Round 58). Offline and
hermetic: small path counts under fixed seeds, temp files for the live loaders.
The point of these tests is that the engine is deterministic, that each desk's
risk moves the numbers in the direction it should, and that the inputs say
where they came from.
"""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from cross_market import risk_simulator as rs

NOW = datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc)


def quiet(**overrides):
    """A book with every desk switched off unless the test turns one on."""
    base = dict(equity=100_000.0, horizon_days=120, basis_positions=0, sports_bets_per_day=0, arb_per_day=0.0,
                tax_rate=0.0)
    base.update(overrides)
    return rs.RiskInputs(**base)


class TestEngine(unittest.TestCase):

    def test_is_deterministic_under_a_seed(self):
        inputs = rs.RiskInputs(horizon_days=60)
        a = rs.simulate(inputs, iterations=500, seed=11)
        b = rs.simulate(inputs, iterations=500, seed=11)
        c = rs.simulate(inputs, iterations=500, seed=12)
        self.assertEqual(a, b)
        self.assertNotEqual(a["terminal_equity"]["p50"], c["terminal_equity"]["p50"])
        self.assertEqual((a["iterations"], a["horizon_days"], a["short_horizon_days"]), (500, 60, 30))

    def test_a_switched_off_book_never_moves(self):
        res = rs.simulate(quiet(), iterations=200, seed=1)
        self.assertEqual(res["ruin"], {"hard_horizon": 0.0, "practical_horizon": 0.0, "hard_short": 0.0,
                                       "practical_short": 0.0})
        self.assertEqual(res["max_drawdown"]["var99_horizon"], 0.0)
        self.assertEqual(res["terminal_equity"]["p50"], 100_000.0)
        self.assertEqual(res["median_log_growth"], 0.0)
        self.assertEqual(res["desk_mean_pnl"], {"basis": 0.0, "sports": 0.0, "arb": 0.0, "tax": 0.0})

    def test_the_basis_book_earns_its_funding_and_leverage_brings_liquidations(self):
        # 1x, spot-backed: funding accrues, liquidations essentially never (a +95% move in a day).
        safe = quiet(basis_positions=2, basis_capital_per_position=20_000.0, basis_funding_apr=20.0,
                     basis_daily_vol=0.12, basis_leverage=1.0, basis_funding_half_life_days=0.0)
        res = rs.simulate(safe, iterations=400, seed=3)
        expected = 2 * 10_000.0 * 0.20 * 120 / 365                              # short notional x APR x time
        self.assertAlmostEqual(res["desk_mean_pnl"]["basis"], expected, delta=expected * 0.25)
        # A book opened at 600% APR decays toward the 25% long-run level: it earns more than a
        # 25% book and far less than a constant 600% one.
        hot_entry = quiet(basis_positions=2, basis_capital_per_position=20_000.0, basis_funding_apr=600.0,
                          basis_funding_long_run_apr=25.0, basis_funding_half_life_days=7.0, basis_daily_vol=0.0)
        decayed = rs.simulate(hot_entry, iterations=200, seed=3)["desk_mean_pnl"]["basis"]
        flat25 = 2 * 10_000.0 * 0.25 * 120 / 365
        flat600 = 2 * 10_000.0 * 6.00 * 120 / 365
        self.assertGreater(decayed, flat25 * 1.2)
        self.assertLess(decayed, flat600 * 0.25)
        # excess 575% x half-life/ln2 (10.1 d) -> ~ 20k x 5.75 x 10.1/365 = $3,180 of excess plus the 25% floor
        self.assertAlmostEqual(decayed, flat25 + 20_000.0 * 5.75 * (7.0 / 0.6931) / 365, delta=flat25 * 0.35)
        self.assertLess(res["liquidations_per_path"], 0.2)                   # t(3) tails: ~1 in 5 years at 12% vol
        # 10x with a 5% maintenance margin: a 5% adverse move before the rebalance liquidates.
        levered = quiet(basis_positions=2, basis_capital_per_position=20_000.0, basis_funding_apr=20.0,
                        basis_daily_vol=0.12, basis_leverage=10.0, basis_funding_half_life_days=0.0)
        hot = rs.simulate(levered, iterations=400, seed=3)
        self.assertGreater(hot["liquidations_per_path"], 5.0)
        self.assertLess(hot["desk_mean_pnl"]["basis"], res["desk_mean_pnl"]["basis"])
        # Negative funding is possible: a book with a negative APR loses money.
        neg = rs.simulate(quiet(basis_positions=2, basis_funding_apr=-20.0, basis_funding_long_run_apr=-20.0,
                                basis_leverage=1.0), iterations=300, seed=3)
        self.assertLess(neg["desk_mean_pnl"]["basis"], 0.0)

    def test_sports_edge_sign_and_size_drive_ruin(self):
        edge = quiet(sports_bets_per_day=5, sports_win_prob_mean=0.56, sports_win_prob_std=0.0,
                     sports_decimal_odds=1.95, sports_kelly_fraction=0.25, sports_max_stake_fraction=0.02,
                     sports_bankroll_fraction=0.5)
        good = rs.simulate(edge, iterations=400, seed=5)
        self.assertGreater(good["desk_mean_pnl"]["sports"], 0.0)
        self.assertGreater(good["median_log_growth"], 0.0)
        # No edge -> Kelly says zero stake -> nothing happens.
        flat = rs.simulate(rs.RiskInputs(**{**edge.to_dict(), "sports_win_prob_mean": 0.50, "provenance": {}}),
                           iterations=200, seed=5)
        self.assertEqual(flat["desk_mean_pnl"]["sports"], 0.0)
        # A desk that bets big against the odds is ruined more often than one that bets small.
        reckless = rs.RiskInputs(**{**edge.to_dict(), "sports_win_prob_mean": 0.45, "sports_kelly_fraction": 4.0,
                                     "sports_max_stake_fraction": 0.5, "sports_bankroll_fraction": 1.0, "provenance": {}})
        # Kelly is negative at p=0.45, so force stakes through the cap by pretending an edge exists:
        reckless.sports_win_prob_mean = 0.52
        reckless.sports_max_stake_fraction = 0.5
        reckless.sports_kelly_fraction = 30.0
        ruined = rs.simulate(reckless, iterations=400, seed=5)
        careful = rs.simulate(reckless.scaled(0.05), iterations=400, seed=5)
        self.assertGreater(ruined["ruin"]["practical_horizon"], careful["ruin"]["practical_horizon"])
        self.assertGreater(ruined["max_drawdown"]["var95_horizon"], careful["max_drawdown"]["var95_horizon"])

    def test_arb_leg_failures_cost_and_the_tax_desk_escrows_gains(self):
        arb = quiet(arb_per_day=2.0, arb_capital=5_000.0, arb_gross_return=0.02, arb_return_std=0.0,
                    arb_leg_fail_prob=0.0)
        clean = rs.simulate(arb, iterations=300, seed=9)
        expected = 2.0 * 120 * 5_000.0 * 0.02
        self.assertAlmostEqual(clean["desk_mean_pnl"]["arb"], expected, delta=expected * 0.15)
        failing = rs.simulate(rs.RiskInputs(**{**arb.to_dict(), "arb_leg_fail_prob": 0.5, "arb_desync_loss_max": 0.2,
                                               "provenance": {}}), iterations=300, seed=9)
        self.assertLess(failing["desk_mean_pnl"]["arb"], clean["desk_mean_pnl"]["arb"])
        # Tax: 32.37% of each quarter's positive gain leaves the bankroll (one quarter end at day 91).
        taxed = rs.simulate(rs.RiskInputs(**{**arb.to_dict(), "tax_rate": 0.3237, "tax_quarter_days": 91,
                                             "provenance": {}}), iterations=300, seed=9)
        self.assertLess(taxed["terminal_equity"]["p50"], clean["terminal_equity"]["p50"])
        gain_q1 = 2.0 * 91 * 5_000.0 * 0.02
        self.assertAlmostEqual(taxed["escrow"]["mean"], 0.3237 * gain_q1, delta=0.3237 * gain_q1 * 0.15)
        self.assertAlmostEqual(taxed["desk_mean_pnl"]["tax"], -taxed["escrow"]["mean"], places=6)
        # A losing quarter escrows nothing.
        losing = rs.simulate(quiet(arb_per_day=2.0, arb_capital=5_000.0, arb_gross_return=-0.02, arb_return_std=0.0,
                                   tax_rate=0.3237), iterations=100, seed=9)
        self.assertEqual(losing["escrow"]["mean"], 0.0)

    def test_hard_ruin_is_absorbing_and_practical_ruin_is_first_passage(self):
        # A desk that loses 2% of a full-equity bankroll five times a day is dead within the horizon.
        doom = quiet(horizon_days=200, sports_bets_per_day=5, sports_win_prob_mean=0.52, sports_win_prob_std=0.0,
                     sports_kelly_fraction=50.0, sports_max_stake_fraction=0.9, sports_bankroll_fraction=1.0,
                     sports_decimal_odds=1.95)                               # Kelly 1.5% x 50 -> capped at 90% a bet
        res = rs.simulate(doom, iterations=200, seed=2)
        self.assertGreater(res["ruin"]["practical_horizon"], 0.9)
        self.assertGreaterEqual(res["ruin"]["practical_horizon"], res["ruin"]["hard_horizon"])
        self.assertGreaterEqual(res["ruin"]["practical_horizon"], res["ruin"]["practical_short"])
        self.assertLessEqual(res["terminal_equity"]["p95"], 100_000.0 * 2)
        self.assertGreaterEqual(res["terminal_equity"]["p05"], 0.0)                 # never negative: absorbing


class TestShrinkageAndInputs(unittest.TestCase):

    def test_shrinkage_picks_the_best_feasible_multiplier_and_reports_the_grid(self):
        inputs = rs.RiskInputs(horizon_days=90)
        out = rs.kelly_shrinkage(inputs, iterations=150, seed=4, grid=(0.5, 1.0, 2.0), tolerance=0.05)
        self.assertEqual([r["multiplier"] for r in out["grid"]], [0.5, 1.0, 2.0])
        self.assertIn(out["recommended_multiplier"], (0.5, 1.0, 2.0))
        self.assertTrue(out["feasible"])
        for row in out["grid"]:
            for key in ("median_log_growth", "practical_ruin", "hard_ruin", "var95_horizon", "terminal_p50"):
                self.assertIn(key, row)
        # Nothing feasible: the least-ruin multiplier wins.
        doom = quiet(horizon_days=120, sports_bets_per_day=5, sports_win_prob_mean=0.52, sports_win_prob_std=0.0,
                     sports_kelly_fraction=50.0, sports_max_stake_fraction=0.9, sports_bankroll_fraction=1.0,
                     sports_decimal_odds=1.95)
        out = rs.kelly_shrinkage(doom, iterations=100, seed=4, grid=(1.0, 2.0), tolerance=0.0)
        self.assertFalse(out["feasible"])
        self.assertEqual(out["recommended_multiplier"], 1.0)
        self.assertEqual(out["binding"], "none")
        # Allocation bound: a book whose capital exceeds the equity is never recommended, however safe.
        fat = rs.RiskInputs(horizon_days=30, equity=100_000.0, basis_positions=2, basis_capital_per_position=30_000.0,
                            sports_bankroll_fraction=0.10, arb_capital=1_000.0)
        self.assertAlmostEqual(rs.allocation_fraction(fat), 0.71, places=6)
        out = rs.kelly_shrinkage(fat, iterations=60, seed=4, grid=(0.5, 1.0, 1.5, 2.0))
        allocations = {r["multiplier"]: r["allocation"] for r in out["grid"]}
        self.assertGreater(allocations[1.5], 1.0)
        self.assertLessEqual(out["recommended_multiplier"], 1.0)
        self.assertEqual(out["binding"], "allocation")                      # ruin never bound; capital did
        # scaled() multiplies sizing only.
        s = inputs.scaled(0.5)
        self.assertEqual((s.basis_capital_per_position, s.sports_kelly_fraction, s.arb_capital),
                         (inputs.basis_capital_per_position * 0.5, inputs.sports_kelly_fraction * 0.5,
                          inputs.arb_capital * 0.5))
        self.assertEqual((s.basis_daily_vol, s.tax_rate, s.equity), (inputs.basis_daily_vol, inputs.tax_rate, inputs.equity))

    def test_buffer_recommendation_and_report_text(self):
        inputs = rs.RiskInputs(horizon_days=60)
        inputs.provenance = {"equity": "measured (x)", "arb_capital": "assumed"}
        res = rs.simulate(inputs, iterations=200, seed=8)
        shrink = rs.kelly_shrinkage(inputs, iterations=60, seed=8, grid=(0.5, 1.0))
        buf = rs.buffer_recommendation(res, shrink)
        self.assertAlmostEqual(buf["buffer_usd"], res["start_equity"] * res["max_drawdown"]["var99_horizon"])
        self.assertEqual(buf["sizing_multiplier"], shrink["recommended_multiplier"])
        text = rs.format_report(res, inputs, shrink)
        self.assertIn(shrink["binding"], ("allocation", "ruin"))
        for needle in ("[RISK] ruin: hard", "practical (-50%)", "max drawdown VaR", "Kelly shrinkage grid",
                       "<- recommended", "binding constraint:", "inputs measured: equity",
                       "inputs assumed:  arb_capital", "buffer: keep $"):
            self.assertIn(needle, text)
        note = rs.render_note(res, inputs, shrink, now=NOW)
        for needle in ("# 🛡 Risk Sentinel", "last_synced: \"2026-09-05 03:00:00 UTC\"", "## 📉 Ruin & Drawdown",
                       "## 🎯 Cross-Desk Kelly Shrinkage", "**recommended**", "**Binding constraint**",
                       "| `equity` |", "measured (x)",
                       "Desk 4 (Quant Trading Lab) is outside"):
            self.assertIn(needle, note)
        self.assertIn("| — | — | — | — | — | grid not run |", rs.render_note(res, inputs, None, now=NOW))

    def test_inputs_round_trip_and_ignore_unknown_keys(self):
        inputs = rs.RiskInputs(equity=5.0, basis_positions=3)
        inputs.provenance = {"equity": "measured (t)"}
        data = inputs.to_dict()
        data["mystery"] = 1
        back = rs.RiskInputs.from_dict(data)
        self.assertEqual((back.equity, back.basis_positions, back.provenance), (5.0, 3, {"equity": "measured (t)"}))

    def test_live_inputs_are_measured_where_files_exist_and_assumed_elsewhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "basis_paper_state.json"
            state.write_text(json.dumps({"cash": 60_000.0, "positions": {
                "XPL": {"coin": "XPL", "capital": 20_000.0, "entry_funding_apr": 30.0},
                "para:ANSEM": {"coin": "para:ANSEM", "capital": 20_000.0, "entry_funding_apr": 20.0}}}), encoding="utf-8")
            db = root / "hl.db"
            con = sqlite3.connect(str(db))
            con.execute("CREATE TABLE asset_snapshots (timestamp INTEGER, coin TEXT, dex TEXT, funding_rate REAL, mark_px REAL)")
            px = 1.0
            for hour in range(72):                                     # 3 days, hourly, both coins
                px *= 1.0 + (0.01 if hour % 3 else -0.02)
                for coin in ("XPL", "para:ANSEM"):
                    con.execute("INSERT INTO asset_snapshots VALUES (?,?,?,?,?)",
                                (hour * 3_600_000, coin, "main", 2e-5 + (1e-5 if hour % 2 else -1e-5), px))
            con.commit()
            con.close()
            inputs = rs.load_live_inputs(state, db, root / "missing_sports.db", use_tax_config=False)
            self.assertEqual((inputs.equity, inputs.basis_positions, inputs.basis_capital_per_position),
                             (100_000.0, 2, 20_000.0))
            # The DB mean (2e-5/h -> 17.52% APR) replaces the entry APR (25%), which stays as context.
            self.assertAlmostEqual(inputs.basis_funding_apr, 2e-5 * 8760 * 100, places=6)
            self.assertIn("book entry APR 25.0%", inputs.provenance["basis_funding_apr"])
            self.assertTrue(inputs.provenance["basis_funding_apr"].startswith("measured (hl.db"))
            self.assertTrue(inputs.provenance["equity"].startswith("measured (basis_paper_json)".replace("json", "state.json")))
            # Without a DB the entry APR is the estimate and says so.
            entry_only = rs.load_live_inputs(state, root / "none.db", root / "none2.db", use_tax_config=False)
            self.assertEqual(entry_only.basis_funding_apr, 25.0)
            self.assertIn("entry APR 25.0% (no DB history)", entry_only.provenance["basis_funding_apr"])
            self.assertTrue(inputs.provenance["basis_funding_hourly_std"].startswith("measured (hl.db, XPL, para:ANSEM"))
            self.assertAlmostEqual(inputs.basis_funding_hourly_std, 1e-5, places=7)
            self.assertGreater(inputs.basis_daily_vol, 0.0)
            self.assertEqual(inputs.provenance["sports_win_prob_mean"], "assumed")
            self.assertEqual(inputs.provenance["tax_rate"], "assumed")
            self.assertEqual(inputs.provenance["arb_capital"], "assumed")
            self.assertEqual(inputs.provenance["basis_funding_half_life_days"], "assumed")
            # A sports DB with positive-Kelly edges is measured.
            sdb = root / "sports.db"
            con = sqlite3.connect(str(sdb))
            con.execute("CREATE TABLE edge_opportunities (sharp_fair_prob REAL, retail_offered_odds REAL)")
            con.executemany("INSERT INTO edge_opportunities VALUES (?,?)",
                            [(0.55, 2.0), (0.60, 1.9), (0.40, 1.5), (0.52, 2.1)])       # the 0.40 row has no edge
            con.commit()
            con.close()
            inputs = rs.load_live_inputs(state, db, sdb, use_tax_config=False)
            self.assertIn("3 positive-Kelly rows", inputs.provenance["sports_win_prob_mean"])
            self.assertAlmostEqual(inputs.sports_win_prob_mean, (0.55 + 0.60 + 0.52) / 3, places=6)
            self.assertAlmostEqual(inputs.sports_decimal_odds, 2.0, places=6)
            # No files at all: everything assumed, nothing raised.
            bare = rs.load_live_inputs(root / "none.json", root / "none.db", root / "none2.db", use_tax_config=False)
            self.assertEqual(bare.provenance["equity"], "assumed")
            self.assertEqual(bare.equity, 100_000.0)

    def test_the_tax_rate_comes_from_the_tax_agent_config(self):
        rate = rs._tax_rate_from_config()
        self.assertIsNotNone(rate)
        self.assertAlmostEqual(rate, 0.3237, places=4)


class TestCli(unittest.TestCase):

    def test_cli_runs_hermetically_writes_the_note_once_and_reports_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            argv = ["--iterations", "300", "--horizon-days", "40", "--assume-defaults", "--no-grid",
                    "--seed", "3", "--vault", str(vault)]
            with mock.patch("builtins.print") as fake_print:
                self.assertEqual(rs.main(argv), 0)
            printed = "\n".join(str(c.args[0]) for c in fake_print.call_args_list)
            self.assertIn("[RISK] Item 19 - 300 paths x 40d, seed 3", printed)
            self.assertIn("Risk_Sentinel.md written", printed)
            self.assertTrue((vault / "Risk_Sentinel.md").exists())
            with mock.patch("builtins.print") as fake_print:
                self.assertEqual(rs.main(argv), 0)
            self.assertIn("Risk_Sentinel.md unchanged", "\n".join(str(c.args[0]) for c in fake_print.call_args_list))
            with mock.patch("builtins.print") as fake_print:
                self.assertEqual(rs.main(argv + ["--json", "--no-vault"]), 0)
            payload = json.loads(fake_print.call_args_list[0].args[0])
            self.assertEqual(set(payload), {"result", "shrinkage", "buffer", "inputs", "note"})
            self.assertIsNone(payload["shrinkage"])
            self.assertEqual(payload["note"], "not written (--no-vault)")
            self.assertEqual(payload["inputs"]["provenance"]["equity"], "assumed")
            # --inputs overrides fields and is labelled; the grid runs with --grid-iterations.
            overrides = Path(tmp) / "inputs.json"
            overrides.write_text(json.dumps({"equity": 50_000.0, "basis_positions": 0}), encoding="utf-8")
            with mock.patch("builtins.print") as fake_print:
                self.assertEqual(rs.main(["--iterations", "200", "--horizon-days", "30", "--assume-defaults",
                                          "--inputs", str(overrides), "--grid-iterations", "50", "--json",
                                          "--no-vault"]), 0)
            payload = json.loads(fake_print.call_args_list[0].args[0])
            self.assertEqual(payload["result"]["start_equity"], 50_000.0)
            self.assertEqual(payload["inputs"]["provenance"]["equity"], "override (inputs.json)")
            self.assertEqual(payload["shrinkage"]["iterations"], 50)
            self.assertEqual(len(payload["shrinkage"]["grid"]), len(rs.SHRINKAGE_GRID))


if __name__ == "__main__":
    unittest.main()
