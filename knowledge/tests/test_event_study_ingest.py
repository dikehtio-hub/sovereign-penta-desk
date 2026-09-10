"""Round 126: the Item 18 Phase 2 registration compiles to an Experiment page under every lint rule, and an
event-study result compiles to Reaction Profile pages plus the panel that applies the pre-registered stopping rules."""
import json
from datetime import timedelta
from pathlib import Path

from knowledge import frontmatter as fm, lint
from knowledge.ingest import event_study as ingest_es
from knowledge.ingest import experiments as ingest_exp
from knowledge.tests.test_knowledge import NOW, IngestFixture

REAL_META = Path(__file__).resolve().parents[2] / "cross_market" / "experiments" / "lead_lag_phase2_fomc.meta.json"


def _result(event_id="fomc_2026-09-16", pm_class="polymarket-leads-event", lead=2.0, informative=True):
    return {
        "experiment": "lead_lag_phase2_event_study", "protocol": "event_study",
        "event": {"id": event_id, "kind": "fed_rate", "label": "FOMC", "release_utc": "2026-09-16T18:00:00Z"},
        "coin": "BTC", "T_utc": "2026-09-16T18:00:00Z", "grid_s": 1, "T0_utc": "2026-09-16T17:59:02Z", "window_first_utc": "2026-09-16T17:59:02Z",
        "baseline_utc": "2026-09-16T17:59:55Z", "window_last_utc": "2026-09-16T18:05:00Z", "measured_at": "2026-09-16T18:10:00+00:00",
        "bars": {"pm_min_displacement": 0.02, "hl_bar_bps": 12.5, "hl_bar_source": "trailing_60m_relative", "hl_median_5m_bps": 4.17, "hl_marks": 358,
                 "lead_tolerance_s": 1.0, "half_life_fraction": 0.5, "panel_min_informative_events": 3},
        "sufficiency": {"polymarket": {}, "hyperliquid": {"prints": 9000, "largest_gap_s": 1.2, "baseline_age_s": 0.4, "ok": True, "reasons": []}},
        "hyperliquid": {"coin": "BTC", "prints": 9000, "baseline_px": 78000.0, "baseline_age_s": 0.4, "final_px": 78200.0, "dp_rel_bps": 25.64,
                        "t_star_utc": "2026-09-16T18:00:05Z", "t_star_rel_s": 5, "displaced": True},
        "markets": [
            {"token": "7000000000000000000000000000000000000000000000000000000000000000000000000001", "label": "FOMC 2026-09-16: no change", "stamps": 359,
             "sufficient": True, "reasons": [], "baseline": 0.5, "final": 0.9, "dp": 0.4, "displaced": True, "t_star_utc": "2026-09-16T18:00:03Z",
             "t_star_rel_s": 3, "lead_s": lead, "class": pm_class, "informative": informative},
            {"token": "7000000000000000000000000000000000000000000000000000000000000000000000000002", "label": "FOMC 2026-09-16: hike 25 bps", "stamps": 359,
             "sufficient": True, "reasons": ["uninformative: polymarket |dP| 0.0100 < 0.02"], "baseline": 0.5, "final": 0.51, "dp": 0.01, "displaced": False,
             "t_star_utc": None, "t_star_rel_s": None, "lead_s": None, "class": "uninformative-shock", "informative": False},
        ],
        "primary_market": {"token": "7000000000000000000000000000000000000000000000000000000000000000000000000001", "label": "FOMC 2026-09-16: no change"},
        "class": pm_class, "lead_s": lead, "informative": informative, "sufficient": True, "reasons": [],
    }


class EventStudyRegistrationTests(IngestFixture):
    def setUp(self):
        super().setUp()
        (self.exp_dir / "lead_lag_phase2_fomc.meta.json").write_text(REAL_META.read_text(encoding="utf-8"), encoding="utf-8")

    def test_the_real_registration_compiles_with_parameters_tokens_and_window(self):
        report = ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        self.assertIn("wiki/experiments/lead_lag_phase2_fomc_meta.md", report.written)
        meta, body = fm.parse((self.vault / "wiki/experiments/lead_lag_phase2_fomc_meta.md").read_text(encoding="utf-8"))
        dev = meta["dev"]
        self.assertEqual((dev["kind"], dev["item"], dev["tests_run"]), ("event_study", 18, 0))
        names = {p["name"]: p["value"] for p in dev["parameters"]}
        self.assertEqual(names["event_study_pm_min_displacement"], 0.02)
        self.assertEqual(names["event_study_lead_tolerance_s"], 1.0)
        self.assertEqual(names["event_study_panel_min_informative_events"], 3)
        self.assertTrue(all(p["json_path"].startswith("bars.") for p in dev["parameters"]))
        self.assertEqual(dev["window"], {"start": "2026-09-16T17:58:00Z", "end": "2026-09-16T18:05:00Z"})
        self.assertEqual(len(dev["tokens"]), 2)                       # the fixture's rules file has two markets
        self.assertEqual([e["id"] for e in dev["events"]], ["fomc_2026-09-16", "cpi_2026-10-14", "fomc_2026-10-28"])
        self.assertIn("rule_1_contemporaneous", dev["stopping_rules"])
        self.assertIn("| `pm_min_displacement` | 0.02 |", body)
        self.assertIn("## Stopping rules (pre-registered)", body)
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        # C1 guards the bars: corrupt one number in the file and lint must fire
        data = json.loads(REAL_META.read_text(encoding="utf-8"))
        data["bars"]["lead_tolerance_s"] = 2.0
        (self.exp_dir / "lead_lag_phase2_fomc.meta.json").write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(any(x.code == "C1" and "event_study_lead_tolerance_s" in x.message
                            for x in lint.lint_vault(self.vault, self.dev_root, now=NOW)))

    def test_writes_are_refused_inside_the_first_events_window(self):
        from knowledge import pages
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        inside = fm.parse_iso8601("2026-09-16T18:01:00Z")
        with self.assertRaises(pages.WriteRefused):
            ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=inside, force=True)


class EventStudyIngestTests(IngestFixture):
    def setUp(self):
        super().setUp()
        (self.exp_dir / "lead_lag_phase2_fomc.meta.json").write_text(REAL_META.read_text(encoding="utf-8"), encoding="utf-8")
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW)
        (self.dev_root / "es.json").write_text(json.dumps(_result()), encoding="utf-8")

    def test_profiles_and_panel_are_written_registered_and_lint_clean(self):
        profiles, panel = ingest_es.ingest_event_study(_result(), self.vault, self.dev_root, source="es.json", at=NOW)
        self.assertEqual([p.path.name for p in profiles],
                         ["reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_no_change.md", "reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_hike_25_bps.md"])
        meta, body = fm.parse(profiles[0].path.read_text(encoding="utf-8"))
        d = meta["dev"]
        self.assertEqual((d["kind"], d["classification"], d["lead_s"], d["informative"], d["primary"]), ("event_study_profile", "polymarket-leads-event", 2.0, True, True))
        self.assertEqual(d["pm"]["t_star_rel_s"], 3)
        self.assertEqual(d["hl"]["t_star_rel_s"], 5)
        self.assertEqual(d["data_gaps"], [])
        self.assertIn("| t*50% (s from T) | 3 | 5 |", body)
        meta2, _ = fm.parse(profiles[1].path.read_text(encoding="utf-8"))
        self.assertEqual((meta2["dev"]["classification"], meta2["dev"]["informative"], meta2["dev"]["primary"]), ("uninformative-shock", False, False))
        pmeta, pbody = fm.parse(panel.path.read_text(encoding="utf-8"))
        self.assertEqual(pmeta["dev"]["status"]["informative_events"], 1)
        self.assertTrue(pmeta["dev"]["status"]["verdict"].startswith("insufficient (1 of 3"))
        self.assertIsNone(pmeta["dev"]["status"]["stopping"])
        self.assertIn("| 2026-09-16 | fomc_2026-09-16 | polymarket-leads-event | 2 | yes |", pbody)
        reg, _ = fm.parse((self.vault / "wiki/concepts/experiments_register.md").read_text(encoding="utf-8"))
        self.assertIn("lead_lag_phase2_panel", reg["dev"]["pages"])
        self.assertIn("reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_no_change", reg["dev"]["pages"])
        self.assertEqual(lint.lint_vault(self.vault, self.dev_root, now=NOW), [])
        # the registration's counter now sees one event
        ingest_exp.ingest_experiments(self.exp_dir, self.vault, self.dev_root, at=NOW, force=True)
        rmeta, _ = fm.parse((self.vault / "wiki/experiments/lead_lag_phase2_fomc_meta.md").read_text(encoding="utf-8"))
        self.assertEqual(rmeta["dev"]["tests_run"], 1)
        # idempotent: a second ingest of the same result appends nothing to the log
        log_before = (self.vault / "log.md").read_text(encoding="utf-8").count("**Ingest**")
        ingest_es.ingest_event_study(_result(), self.vault, self.dev_root, source="es.json", at=NOW + timedelta(hours=1))
        self.assertEqual((self.vault / "log.md").read_text(encoding="utf-8").count("**Ingest**"), log_before)

    def test_cli_refuses_a_non_event_study_file_and_writes_the_pages(self):
        import io
        bad = self.dev_root / "bad.json"
        bad.write_text(json.dumps({"sufficient": True}), encoding="utf-8")
        out = io.StringIO()
        self.assertEqual(ingest_es.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--result", str(bad)], out=out), 3)
        self.assertIn("not an event_study result", out.getvalue())
        out = io.StringIO()
        self.assertEqual(ingest_es.main(["--vault", str(self.vault), "--dev-root", str(self.dev_root), "--result", str(self.dev_root / "es.json"),
                                         "--at", "2026-09-16T18:10:00Z"], out=out), 0)
        self.assertIn("[WRITE] wiki/experiments/reaction_profile_fomc_2026-09-16__FOMC_2026_09_16_no_change.md  class=polymarket-leads-event  counted=True", out.getvalue())
        self.assertIn("[WRITE] wiki/experiments/lead_lag_phase2_panel.md  insufficient (1 of 3 informative events)", out.getvalue())


class PanelStatusTests(IngestFixture):
    def test_the_stopping_rules_fire_on_the_registered_sequences(self):
        ev = lambda i, c, inf: {"event": f"e{i}", "classification": c, "informative": inf, "release_utc": f"2026-1{i}-01T00:00:00Z"}
        s = ingest_es.panel_status([ev(0, "contemporaneous-event-repricing", True), ev(1, "hyperliquid-leads-event", True)], min_informative=3)
        self.assertTrue(s["stopping"].startswith("rule 1"))
        s = ingest_es.panel_status([ev(0, "uninformative-shock", False), ev(1, "uninformative-shock", False), ev(2, "uninformative-shock", False)], min_informative=3)
        self.assertTrue(s["stopping"].startswith("rule 2"))
        self.assertEqual(s["informative_events"], 0)
        s = ingest_es.panel_status([ev(0, "polymarket-leads-event", True), ev(1, "uninformative-shock", False), ev(2, "polymarket-leads-event", True),
                                    ev(3, "contemporaneous-event-repricing", True)], min_informative=3)
        self.assertIsNone(s["stopping"])
        self.assertEqual(s["verdict"], "polymarket-leads-event on 2 of 3 informative events")
        self.assertTrue(s["capital_bar_met"])
        s = ingest_es.panel_status([ev(0, "polymarket-leads-event", True), ev(1, "hyperliquid-leads-event", True), ev(2, "polymarket-leads-event", True)], min_informative=3)
        self.assertEqual(s["verdict"], "polymarket-leads-event on 2 of 3 informative events")
        self.assertIsNone(s["stopping"])
