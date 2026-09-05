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


class TestSystemicStress(unittest.TestCase):

    def test_shock_days_hit_the_basis_and_arb_desks_together_and_zero_is_the_baseline(self):
        # Tax escrow off so drawdowns come from the desks, not from quarter ends; 800 paths so the
        # percentiles are stable enough to compare (VaR99 on a few hundred paths is one path).
        base = rs.RiskInputs(horizon_days=120, basis_funding_half_life_days=0.0, sports_bets_per_day=0,
                             basis_daily_vol=0.10, arb_per_day=3.0, arb_capital=5_000.0, tax_rate=0.0)
        calm = rs.simulate(base, iterations=800, seed=21)
        again = rs.simulate(rs.RiskInputs(**{**base.to_dict(), "stress_correlation": 0.0, "provenance": {}}),
                            iterations=800, seed=21)
        self.assertEqual(calm, again)                                          # zero correlation = the baseline
        self.assertEqual(calm["stress"]["correlation"], 0.0)
        self.assertGreater(calm["stress"]["shock_days_per_path"], 0.0)         # the mask is drawn regardless
        hot = rs.RiskInputs(**{**base.to_dict(), "stress_correlation": 1.0, "stress_day_prob": 0.25,
                               "stress_vol_multiplier": 4.0, "provenance": {}})
        stressed = rs.simulate(hot, iterations=800, seed=21)
        self.assertAlmostEqual(stressed["stress"]["shock_days_per_path"], 30.0, delta=3.0)
        self.assertLess(stressed["desk_mean_pnl"]["basis"], calm["desk_mean_pnl"]["basis"])   # funding compressed/flipped
        self.assertLess(stressed["desk_mean_pnl"]["arb"], calm["desk_mean_pnl"]["arb"])       # leg failures doubled
        self.assertGreater(stressed["liquidations_per_path"], calm["liquidations_per_path"])  # vol x4 on shock days
        self.assertGreater(stressed["max_drawdown"]["var95_horizon"], calm["max_drawdown"]["var95_horizon"])
        self.assertGreater(stressed["max_drawdown"]["median_horizon"], calm["max_drawdown"]["median_horizon"])
        self.assertLess(stressed["terminal_equity"]["p50"], calm["terminal_equity"]["p50"])
        self.assertEqual(stressed["desk_mean_pnl"]["sports"], 0.0)                            # untouched by design
        impact = rs.stress_impact(hot, iterations=800, seed=21, stressed=stressed)
        self.assertEqual(impact["stressed"]["var99_horizon"], stressed["max_drawdown"]["var99_horizon"])
        self.assertEqual(impact["baseline"]["var99_horizon"], calm["max_drawdown"]["var99_horizon"])
        self.assertGreater(impact["delta"]["var95_horizon"], 0.0)
        self.assertGreater(impact["delta"]["liquidations_per_path"], 0.0)
        self.assertLess(impact["delta"]["basis_pnl"], 0.0)
        self.assertLess(impact["delta"]["arb_pnl"], 0.0)
        self.assertIsNone(rs.stress_impact(base, iterations=10, seed=1))
        text = rs.format_report(stressed, hot, None, impact)
        self.assertIn("systemic stress: correlation 1.00", text)
        self.assertIn("VaR99 120d baseline", text)
        self.assertIn("systemic stress: off", rs.format_report(calm, base, None, None))
        note = rs.render_note(stressed, hot, None, now=NOW, stress=impact)
        self.assertIn("## ⚡ Systemic Stress", note)
        self.assertIn("| Recommended cash buffer |", note)
        self.assertIn("_Systemic stress is off_", rs.render_note(calm, base, None, now=NOW))

    def test_cli_stress_flags_override_and_report(self):
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(rs.main(["--iterations", "200", "--horizon-days", "30", "--assume-defaults", "--no-grid",
                                      "--no-vault", "--json", "--stress-correlation", "0.8", "--stress-day-prob", "0.3",
                                      "--stress-vol-multiplier", "5"]), 0)
        payload = json.loads(fake_print.call_args_list[0].args[0])
        self.assertEqual(payload["inputs"]["stress_correlation"], 0.8)
        self.assertEqual(payload["inputs"]["provenance"]["stress_day_prob"], "override (cli)")
        self.assertEqual(set(payload["stress"]), {"correlation", "day_prob", "vol_multiplier", "shock_days_per_path",
                                                  "baseline", "stressed", "delta"})
        self.assertEqual(payload["stress"]["vol_multiplier"], 5.0)


class TestCalibrationFromHistory(unittest.TestCase):
    """Round 60: measured stress parameters and sports cadence replace assumptions when history exists."""

    @staticmethod
    def marks_db(path, days, shock_days=(), coin="XPL"):
        """Hourly marks: +/-0.5% alternating on calm days, +/-3% on shock days (6x the vol)."""
        con = sqlite3.connect(str(path))
        con.execute("CREATE TABLE asset_snapshots (timestamp INTEGER, coin TEXT, dex TEXT, funding_rate REAL, mark_px REAL)")
        px = 100.0
        for hour in range(days * 24):
            step = 0.03 if (hour // 24) in shock_days else 0.005
            px *= (1.0 + step) if hour % 2 else (1.0 - step)
            con.execute("INSERT INTO asset_snapshots VALUES (?,?,?,?,?)", (hour * 3_600_000, coin, "main", 1e-5, px))
        con.commit()
        con.close()

    def test_shock_days_are_counted_against_three_times_the_median_vol(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "hl.db"
            self.marks_db(db, days=20, shock_days=(3, 11))
            prob, multiplier, days, shocks, coin_days = rs._measure_stress_from_vol(db, ["XPL"])
            self.assertEqual((days, shocks, coin_days), (20, 2, 20))
            self.assertAlmostEqual(prob, 0.10, places=6)
            self.assertAlmostEqual(multiplier, 6.0, delta=0.3)                # 3% / 0.5% moves
            # Through the loader: measured provenance, values applied.
            state = Path(tmp) / "book.json"
            state.write_text(json.dumps({"cash": 50_000.0, "positions": {"XPL": {"coin": "XPL", "capital": 20_000.0}}}))
            inputs = rs.load_live_inputs(state, db, Path(tmp) / "none.db", use_tax_config=False)
            self.assertAlmostEqual(inputs.stress_day_prob, 0.10, places=6)
            self.assertTrue(inputs.provenance["stress_day_prob"].startswith("measured (hl.db vol quantiles, 20 days"))
            self.assertIn("2 shock coin-day(s) of 20", inputs.provenance["stress_vol_multiplier"])
            # No shock day at all: the probability is measured as 0, the multiplier stays assumed.
            calm = Path(tmp) / "calm.db"
            self.marks_db(calm, days=15)
            prob, multiplier, days, shocks, _ = rs._measure_stress_from_vol(calm, ["XPL"])
            self.assertEqual((prob, multiplier, days, shocks), (0.0, None, 15, 0))
            inputs = rs.load_live_inputs(state, calm, Path(tmp) / "none.db", use_tax_config=False)
            self.assertEqual(inputs.stress_vol_multiplier, 3.0)
            self.assertEqual(inputs.provenance["stress_vol_multiplier"], "assumed (no shock day in 15 days)")
            # Fewer than 14 days: nothing measured, defaults kept and labelled.
            thin = Path(tmp) / "thin.db"
            self.marks_db(thin, days=13, shock_days=(2,))
            self.assertIsNone(rs._measure_stress_from_vol(thin, ["XPL"]))
            inputs = rs.load_live_inputs(state, thin, Path(tmp) / "none.db", use_tax_config=False)
            self.assertEqual((inputs.stress_day_prob, inputs.stress_vol_multiplier), (0.02, 3.0))
            self.assertEqual(inputs.provenance["stress_day_prob"], "assumed (< 14 days of marks)")

    def test_per_coin_medians_keep_a_high_beta_token_from_moving_a_majors_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "hl.db"
            self.marks_db(db, days=20, shock_days=(3, 11), coin="XPL")            # 0.5% moves, 2 shock days
            # ANSEM: 1.5% baseline moves (3x XPL's) and ONE 9% shock day. Pooled with XPL, every
            # ANSEM day would read as a shock; per coin it is 1 of 20.
            con = sqlite3.connect(str(db))
            px = 10.0
            for hour in range(20 * 24):
                step = 0.09 if (hour // 24) == 7 else 0.015
                px *= (1.0 + step) if hour % 2 else (1.0 - step)
                con.execute("INSERT INTO asset_snapshots VALUES (?,?,?,?,?)", (hour * 3_600_000, "para:ANSEM", "para", 1e-5, px))
            con.commit()
            con.close()
            cal = rs.stress_calibration(db, ["XPL", "para:ANSEM"])
            self.assertEqual(cal["qualifying"], ["XPL", "para:ANSEM"])
            self.assertEqual((cal["coins"]["XPL"]["shocks"], cal["coins"]["para:ANSEM"]["shocks"]), (2, 1))
            self.assertAlmostEqual(cal["coins"]["para:ANSEM"]["median"], 3 * cal["coins"]["XPL"]["median"], delta=0.01)
            self.assertAlmostEqual(cal["prob"], (2 / 20 + 1 / 20) / 2, places=6)  # unweighted mean over coins
            self.assertAlmostEqual(cal["multiplier"], 6.0, delta=0.3)              # both coins: shock = 6x their own median
            self.assertEqual((cal["shocks"], cal["coin_days"], cal["days"]), (3, 40, 20))
            prob, multiplier, days, shocks, coin_days = rs._measure_stress_from_vol(db, ["XPL", "para:ANSEM"])
            self.assertAlmostEqual(prob, 0.075, places=6)
            # A coin without 14 days is skipped, not averaged in.
            thin = rs.stress_calibration(db, ["XPL", "NOPE"])
            self.assertEqual(thin["qualifying"], ["XPL"])
            self.assertFalse(thin["coins"]["NOPE"]["qualifies"])
            self.assertAlmostEqual(thin["prob"], 0.10, places=6)
            text = rs.format_calibration_report({"coins": ["XPL", "NOPE"], "stress": thin, "sports": None, "arbs": None})
            self.assertIn("XPL          20 days", text)
            self.assertIn("<- SHOCK", text)
            self.assertIn("NOPE          0 day(s)", text)
            self.assertIn("portfolio: shock-day prob 0.100", text)
            self.assertIn("sports settlement: < 20 settled wagers", text)
            self.assertIn("arb receipts: < 10 fills", text)

    @staticmethod
    def receipts(folder, executions, start="2026-09-01", prices=(0.48, 0.49), qty=100.0, processed_from=None):
        """One two-leg dutched arb per execution, one receipt file per leg, `days` apart."""
        import csv
        import uuid
        from datetime import date, timedelta
        Path(folder).mkdir(parents=True, exist_ok=True)
        (Path(folder) / "processed").mkdir(exist_ok=True)
        first = date.fromisoformat(start)
        for i in range(executions):
            stamp = "%s 14:%02d:00" % ((first + timedelta(days=i)).isoformat(), i % 60)
            target = Path(folder) / ("processed" if processed_from is not None and i >= processed_from else "")
            for leg, price in enumerate(prices):
                path = target / ("fills_polymarket_dutched_arb_%s_%s.csv" % (stamp.replace(" ", "_").replace(":", ""),
                                                                            uuid.uuid4().hex[:8]))
                with open(path, "w", newline="", encoding="utf-8") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(["timestamp", "symbol", "side", "quantity", "price", "fee", "tx_hash", "source", "notes"])
                    writer.writerow([stamp, "MKT_%d_%s" % (i, "YES" if leg == 0 else "NO"), "BUY", "%.6f" % qty,
                                     "%.6f" % price, "0", "k%d%d" % (i, leg), "polymarket", "strategy:dutched_arb;"])

    def test_arb_receipts_replace_the_assumed_desk_at_ten_fills(self):
        with tempfile.TemporaryDirectory() as tmp:
            imports = Path(tmp) / "imports"
            self.receipts(imports, executions=6, processed_from=3)              # 12 fills, 3 files in processed/
            arbs = rs._measure_arb_history(imports)
            self.assertEqual((arbs["fills"], arbs["executions"], arbs["files"], arbs["span_days"]), (12, 6, 12, 6))
            self.assertAlmostEqual(arbs["arb_per_day"], 1.0, places=6)
            self.assertAlmostEqual(arbs["gross_return_mean"], 1 / 0.97 - 1, places=6)   # 3.09% dutch
            self.assertAlmostEqual(arbs["gross_return_std"], 0.0, places=6)
            self.assertAlmostEqual(arbs["capital_mean"], 97.0, places=6)
            state = Path(tmp) / "book.json"
            state.write_text(json.dumps({"cash": 50_000.0, "positions": {}}))
            inputs = rs.load_live_inputs(state, Path(tmp) / "none.db", Path(tmp) / "none2.db", use_tax_config=False,
                                         imports_dir=imports)
            self.assertAlmostEqual(inputs.arb_per_day, 1.0, places=6)
            self.assertAlmostEqual(inputs.arb_capital, 97.0, places=6)
            self.assertEqual(inputs.provenance["arb_per_day"],
                             "measured (imports receipts, 12 fills / 6 arbs over 6 calendar days)")
            self.assertEqual(inputs.provenance["arb_gross_return"], inputs.provenance["arb_per_day"])
            self.assertEqual(inputs.provenance["arb_leg_fail_prob"], "assumed")   # receipts say nothing about failures
            # Nine fills: assumed, and it says why. A folder that does not exist: the same.
            few = Path(tmp) / "few"
            self.receipts(few, executions=4)
            (sorted(few.glob("*.csv"))[0]).unlink()                                # 7 fills
            self.assertIsNone(rs._measure_arb_history(few))
            inputs = rs.load_live_inputs(state, Path(tmp) / "none.db", Path(tmp) / "none2.db", use_tax_config=False,
                                         imports_dir=few)
            self.assertEqual(inputs.provenance["arb_per_day"], "assumed (< 10 arb fills)")
            self.assertEqual(inputs.arb_per_day, 1.0)
            self.assertIsNone(rs._measure_arb_history(Path(tmp) / "missing"))
            # The audit report shows the receipts and the CLI prints it.
            report = rs.calibration_report(state, Path(tmp) / "none.db", Path(tmp) / "none2.db", imports)
            self.assertEqual(report["coins"], ["BTC"])
            self.assertEqual(report["arbs"]["executions"], 6)
            text = rs.format_calibration_report(report)
            self.assertIn("arb receipts: 12 fills in 12 file(s) -> 6 executions over 6 calendar days = 1.00/day", text)
            self.assertIn("gross return 0.0309", text)
            with mock.patch("builtins.print") as fake_print:
                self.assertEqual(rs.main(["--calibration-report", "--paper-state", str(state), "--hl-db",
                                          str(Path(tmp) / "none.db"), "--sports-db", str(Path(tmp) / "none2.db"),
                                          "--imports-dir", str(imports)]), 0)
            printed = fake_print.call_args_list[0].args[0]
            self.assertIn("[CAL] stress calibration", printed)
            self.assertIn("unavailable:", printed)                                 # no hl.db at that path
            self.assertIn("6 executions", printed)
            with mock.patch("builtins.print") as fake_print:
                self.assertEqual(rs.main(["--calibration-report", "--json", "--paper-state", str(state), "--hl-db",
                                          str(Path(tmp) / "none.db"), "--sports-db", str(Path(tmp) / "none2.db"),
                                          "--imports-dir", str(imports)]), 0)
            self.assertEqual(json.loads(fake_print.call_args_list[0].args[0])["arbs"]["fills"], 12)

    @staticmethod
    def bets_db(path, outcomes, days=8, odds=1.91):
        con = sqlite3.connect(str(path))
        con.execute("""CREATE TABLE placed_bets (id INTEGER PRIMARY KEY AUTOINCREMENT, placed_at TEXT NOT NULL,
                       event_id TEXT NOT NULL, sport TEXT NOT NULL, market_type TEXT NOT NULL, line TEXT NOT NULL DEFAULT '',
                       selection TEXT NOT NULL, book TEXT NOT NULL, decimal_odds REAL NOT NULL, stake REAL NOT NULL,
                       outcome TEXT, settled_at TEXT)""")
        for i, outcome in enumerate(outcomes):
            con.execute("INSERT INTO placed_bets (placed_at, event_id, sport, market_type, selection, book, decimal_odds, "
                        "stake, outcome, settled_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        ("2026-09-%02dT18:00:00Z" % (1 + i % days), "E%d" % i, "NFL", "moneyline", "Home", "book",
                         odds + 0.1 * (i % 3), 50.0, outcome, "2026-09-%02dT23:00:00Z" % (1 + i % days) if outcome else None))
        con.commit()
        con.close()

    def test_settled_wagers_replace_the_assumed_cadence_and_win_rate_at_twenty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sports.db"
            self.bets_db(db, ["WIN"] * 13 + ["LOSS"] * 9 + ["PUSH"] * 2 + [None] * 3, days=8)   # 24 settled, 3 open
            cadence, win_prob, odds, wagers, days, pushes = rs._measure_sports_history(db)
            self.assertEqual((wagers, days, pushes), (24, 8, 2))
            self.assertAlmostEqual(cadence, 3.0, places=6)
            self.assertAlmostEqual(win_prob, 13 / 22, places=6)                # pushes are neither
            self.assertAlmostEqual(odds, 2.01, delta=0.02)
            state = Path(tmp) / "book.json"
            state.write_text(json.dumps({"cash": 50_000.0, "positions": {}}))
            inputs = rs.load_live_inputs(state, Path(tmp) / "none.db", db, use_tax_config=False)
            self.assertAlmostEqual(inputs.sports_bets_per_day, 3.0, places=6)
            self.assertAlmostEqual(inputs.sports_win_prob_mean, 13 / 22, places=6)
            self.assertEqual(inputs.provenance["sports_bets_per_day"],
                             "measured (sports.db placed_bets, 24 wagers over 8 calendar days, 2 push(es) excluded)")
            # Ruling 61-3: calendar days, not active days. 20 wagers on two dates two weeks apart
            # is 20 / 14 a day, not 20 / 2.
            sparse = Path(tmp) / "sparse.db"
            self.bets_db(sparse, ["WIN"] * 11 + ["LOSS"] * 9, days=2)          # day 1 and day 2 only
            con = sqlite3.connect(str(sparse))
            con.execute("UPDATE placed_bets SET placed_at = '2026-09-14T18:00:00Z' WHERE placed_at LIKE '2026-09-02%'")
            con.commit()
            con.close()
            cadence, _, _, wagers, span, _ = rs._measure_sports_history(sparse)
            self.assertEqual((wagers, span), (20, 14))
            self.assertAlmostEqual(cadence, 20 / 14, places=6)
            self.assertEqual(inputs.provenance["sports_win_prob_mean"], inputs.provenance["sports_bets_per_day"])
            # Nineteen settled: still assumed, and it says why.
            few = Path(tmp) / "few.db"
            self.bets_db(few, ["WIN"] * 10 + ["LOSS"] * 9)
            self.assertIsNone(rs._measure_sports_history(few))
            inputs = rs.load_live_inputs(state, Path(tmp) / "none.db", few, use_tax_config=False)
            self.assertEqual(inputs.sports_bets_per_day, 3.0)
            self.assertEqual(inputs.provenance["sports_bets_per_day"], "assumed (< 20 settled wagers)")
            # A settled table with only pushes cannot give a win rate.
            pushes = Path(tmp) / "pushes.db"
            self.bets_db(pushes, ["PUSH"] * 25)
            self.assertIsNone(rs._measure_sports_history(pushes))

    def test_fractional_cadence_places_the_remainder_as_one_probable_wager(self):
        base = dict(horizon_days=120, basis_positions=0, arb_per_day=0.0, tax_rate=0.0, sports_win_prob_mean=0.60,
                    sports_win_prob_std=0.0, sports_bankroll_fraction=0.5)
        two = rs.simulate(rs.RiskInputs(sports_bets_per_day=2.0, **base), iterations=600, seed=13)
        half = rs.simulate(rs.RiskInputs(sports_bets_per_day=2.5, **base), iterations=600, seed=13)
        three = rs.simulate(rs.RiskInputs(sports_bets_per_day=3.0, **base), iterations=600, seed=13)
        self.assertLess(two["desk_mean_pnl"]["sports"], half["desk_mean_pnl"]["sports"])
        self.assertLess(half["desk_mean_pnl"]["sports"], three["desk_mean_pnl"]["sports"])
        self.assertAlmostEqual(half["desk_mean_pnl"]["sports"] / three["desk_mean_pnl"]["sports"], 2.5 / 3.0, delta=0.08)
        self.assertEqual(rs.simulate(rs.RiskInputs(sports_bets_per_day=2, **base), iterations=100, seed=1),
                         rs.simulate(rs.RiskInputs(sports_bets_per_day=2.0, **base), iterations=100, seed=1))


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
            self.assertEqual(inputs.provenance["sports_bets_per_day"], "assumed (< 20 settled wagers)")
            self.assertEqual(inputs.provenance["stress_day_prob"], "assumed (< 14 days of marks)")
            self.assertEqual(inputs.provenance["arb_per_day"], "assumed (< 10 arb fills)")
            self.assertEqual(inputs.provenance["tax_rate"], "assumed")
            self.assertEqual(inputs.provenance["arb_capital"], "assumed (< 10 arb fills)")
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
            self.assertEqual(set(payload), {"result", "shrinkage", "buffer", "stress", "inputs", "note"})
            self.assertIsNone(payload["shrinkage"])
            self.assertEqual(payload["note"], "not written (--no-vault)")
            self.assertEqual(payload["inputs"]["provenance"]["equity"], "assumed")
            self.assertIsNone(payload["stress"])
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
