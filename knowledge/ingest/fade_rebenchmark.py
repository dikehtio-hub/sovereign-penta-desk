"""passive_fade_rebenchmark -> its verdict page (Round 114, Ruling R113-1.C option 3).

    cd HyperLiquid/HL_Monarch && python -m analytics.fade_rebenchmark --out data/experiments/passive_fade_rebenchmark.verdict.json
    python -m knowledge.ingest.fade_rebenchmark [--result PATH] [--registration PATH]

WHAT THIS PAGE ANSWERS. The registration asks whether the retired passive fade may be RECONSIDERED,
and binds the answer to a sample gate (>=500 events, >=20 coins, no coin over 20%, a 7-day window)
and a bar (P(ratio >= 1.25) > 0.90 under a cluster bootstrap resampling coins). This adapter reads
the JSON the engine wrote and GRADES IT INDEPENDENTLY against the registration - the gates are
re-checked here from the registration's own numbers, the bar is parsed from the registration's own
rule text, and the engine's verdict string is then compared against that grade. Agreement is the
normal case. A disagreement is a finding, stated in both voices, never reconciled silently. Same
doctrine as knowledge.ingest.cascade_replay (Round 104), for the same reason: Round 103 transcribed
two numbers that had moved.

THE POPULATION IS PART OF THE PROTOCOL. The registration names `population.source` (trade_sweep,
recorded Round 114); an artifact measured over any other population - including the pooled table -
is INSUFFICIENT here regardless of its numbers, because it answers a different question.

INSUFFICIENT IS NOT A VERDICT. It means "come back when the sample qualifies", and the registration
page keeps saying `accumulating`, with the failing gates named, until a PASS or FAIL exists.

Read-only on the artifact and the registration. Writes only through pages.write_page.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc,
                     page_path, write_index, write_page)
from ..registers import write_register
from . import add_common_args, at_from, guard, link_if_exists, page_changed, rel_to
from .cascade_replay import _f, written_at
from .data_gaps import overlapping_gaps

STEM = "passive_fade_rebenchmark_verdict"
REGISTRATION_STEM = "passive_fade_rebenchmark_meta"
EXP_DIR = Path("HyperLiquid") / "HL_Monarch" / "data" / "experiments"
DEFAULT_RESULT = EXP_DIR / "passive_fade_rebenchmark.verdict.json"
DEFAULT_REGISTRATION = EXP_DIR / "passive_fade_rebenchmark.meta.json"
GRADES = ("PASS", "FAIL", "INSUFFICIENT")
RULE_RE = re.compile(r"ratio\s*>=\s*([0-9.]+)\s*\)\s*>\s*([0-9.]+)")
RUNNER = "cd HyperLiquid/HL_Monarch && python -m analytics.fade_rebenchmark"


def bar_of(reg: dict[str, Any]) -> tuple[float, float]:
    """(ratio bar, confidence) parsed from the registration's own rule text, e.g. `P(ratio >= 1.25) > 0.90`."""
    rule = str((reg.get("reopening_bar") or {}).get("rule") or "")
    m = RULE_RE.search(rule)
    if not m:
        raise ValueError(f"reopening_bar.rule is not parseable as P(ratio >= X) > Y: {rule!r}")
    return float(m.group(1)), float(m.group(2))


def gate_failures(metrics: dict[str, Any], reg: dict[str, Any], source: str | None) -> list[str]:
    """Every sample requirement re-checked from the registration, plus the population."""
    req = reg.get("sample_requirements") or {}
    out: list[str] = []
    want_src = (reg.get("population") or {}).get("source") if isinstance(reg.get("population"), dict) else None
    if want_src and source != want_src:
        out.append(f"population: artifact measured `{source}`, registration names `{want_src}`")
    checks = [("events", "min_events", "ge"), ("coins", "min_coins", "ge"),
              ("top_coin_share", "max_single_coin_share", "le"), ("span_days", "window_days", "ge"),
              ("hhi", "max_hhi", "le")]
    for key, req_key, sense in checks:
        want = req.get(req_key)
        if want is None:
            continue
        got = metrics.get(key)
        if got is None:
            out.append(f"{key}: not reported (registration requires {req_key}={want})")
            continue
        if (sense == "ge" and got < want) or (sense == "le" and got > want):
            out.append(f"{key}={got:.4g} {'<' if sense == 'ge' else '>'} {want}")
    return out


def grade(art: dict[str, Any], reg: dict[str, Any]) -> dict[str, Any]:
    ratio_bar, conf = bar_of(reg)
    metrics = (art.get("sample_gates") or {}).get("metrics") or {}
    failures = gate_failures(metrics, reg, art.get("source"))
    p = (art.get("primary_metric") or {}).get("cluster_p_ge_1_25")
    band = "INSUFFICIENT" if p is None else ("PASS" if p > conf else "FAIL")
    ours = "INSUFFICIENT" if failures else band
    theirs = str(art.get("verdict") or "-")
    eng = art.get("reopening_bar") or {}
    drift = []
    if eng.get("ratio") is not None and float(eng["ratio"]) != ratio_bar:
        drift.append(f"engine ratio bar {eng['ratio']} != registered {ratio_bar}")
    if eng.get("confidence") is not None and float(eng["confidence"]) != conf:
        drift.append(f"engine confidence {eng['confidence']} != registered {conf}")
    return {"grade": ours, "engine_verdict": theirs, "agrees": ours == theirs, "gate_failures": failures,
            "gates_passed": not failures, "cluster_p": p, "band_if_sample_qualified": band, "metrics": metrics,
            "ratio_bar": ratio_bar, "confidence_bar": conf, "bar_drift": drift}


def measured(art: dict[str, Any]) -> dict[str, Any]:
    pm, audit, env = art.get("primary_metric") or {}, art.get("data_audit") or {}, art.get("_artifact") or {}
    return {"ratio_30m": pm.get("value"), "n_30m": pm.get("n"), "cluster_p_ge_1_25": pm.get("cluster_p_ge_1_25"),
            "cluster_p_ge_1": pm.get("cluster_p_ge_1"), "control_ratio_30m": pm.get("control_ratio"),
            "edge_vs_control": pm.get("edge_vs_control"), "source": art.get("source"),
            "rows_at_run": audit.get("total_in_table"), "treatment_rows": audit.get("treatment_rows"),
            "control_rows": audit.get("control_rows"), "first_event_utc": audit.get("first_event_utc"),
            "last_event_utc": audit.get("last_event_utc"), "seed": env.get("seed"), "resamples": env.get("resamples")}


def build_page(art: dict[str, Any], reg: dict[str, Any], vault: Path, dev_root: Path, result: Path,
               registration: Path, at: datetime, observed_at: str | None, by: str = GENERATED_BY,
               observed_from: str = "the file mtime") -> Page:
    g, m = grade(art, reg), measured(art)
    req = reg.get("sample_requirements") or {}
    bar = reg.get("reopening_bar") or {}
    pop = reg.get("population") if isinstance(reg.get("population"), dict) else {}
    horizons = art.get("horizons") or {}
    path = page_path(vault, "Experiment", STEM)
    existing = load_page(path)
    history = [dict(r) for r in ((existing.meta.get("dev") or {}).get("history") or [])] if existing else []
    row = {"at": iso(at), "observed_at": observed_at, "rows_at_run": m["rows_at_run"],
           "events": g["metrics"].get("events"), "top_coin_share": g["metrics"].get("top_coin_share"),
           "span_days": g["metrics"].get("span_days"), "ratio_30m": m["ratio_30m"],
           "cluster_p": m["cluster_p_ge_1_25"], "grade": g["grade"]}
    # The artifact is the unit of observation (same rule as cascade_replay): the same artifact
    # replaces the last row and keeps its original `at`; a new run appends.
    if history and all(history[-1].get(k) == row[k] for k in ("observed_at", "rows_at_run", "ratio_30m", "cluster_p")):
        row["at"] = history[-1].get("at", row["at"])
        history[-1] = row
    else:
        history.append(row)

    mt = g["metrics"]
    body = [
        "# Passive fade rebenchmark - verdict", "",
        f"> **{g['grade']}**. Graded here against the pre-registration (registered {reg.get('registered_utc')}), "
        "not copied from the engine's output.", "",
        "## The question", "",
        f"May the retired passive fade be reconsidered? The registration's bar: `{bar.get('rule', '-')}`. "
        f"{bar.get('rationale', '')}", "",
        "## Verdict", "",
        f"- **This page grades: {g['grade']}**",
        f"- The engine reported: `{g['engine_verdict']}` -> "
        + ("the two agree." if g["agrees"] else "**THEY DISAGREE. That is the finding; neither is silently preferred.**"),
    ]
    if g["bar_drift"]:
        body += [f"- **Bar drift**: {'; '.join(g['bar_drift'])}. The registration's text is authoritative."]
    if g["gate_failures"]:
        body += ["", "The sample requirements are NOT met, so **no verdict is issued** - an insufficient sample is never "
                 "read as a weak PASS or a FAIL. Unmet:", ""]
        body += [f"- {f}" for f in g["gate_failures"]]
        body += ["", f"Had the sample qualified, P(ratio_30m >= {g['ratio_bar']}) = {_f(m['cluster_p_ge_1_25'], '.4f')} "
                 f"would have fallen in the **{g['band_if_sample_qualified']}** band. Stated for completeness; **it is "
                 "not a verdict**, and it is exactly the reading the gates exist to prevent."]
    else:
        body += ["", f"All sample requirements met over population `{m['source']}`. "
                 f"P(ratio_30m >= {g['ratio_bar']}) = {_f(m['cluster_p_ge_1_25'], '.4f')} against a > {g['confidence_bar']} bar -> "
                 f"**{g['band_if_sample_qualified']}**."]

    fails = " ".join(g["gate_failures"])
    body += ["", "## Sample gates, re-checked here", "", "| Requirement | Registered | Measured | |", "|---|---|---|---|"]
    rows = [("events", f">= {req.get('min_events')}", mt.get("events")),
            ("coins", f">= {req.get('min_coins')}", mt.get("coins")),
            ("top_coin_share", f"<= {req.get('max_single_coin_share')}", mt.get("top_coin_share")),
            ("span_days", f">= {req.get('window_days')}", mt.get("span_days"))]
    if req.get("max_hhi") is not None:
        rows.append(("hhi", f"<= {req.get('max_hhi')}", mt.get("hhi")))
    for name, want, got in rows:
        bad = f"{name}=" in fails
        got_s = f"{got:.4g}" if isinstance(got, float) else f"{got:,}" if isinstance(got, int) else "-"
        body.append(f"| {name} | {want} | {got_s} | {'**FAIL**' if bad else 'ok'} |")
    body += ["", f"Top coin: `{mt.get('top_coin', '-')}`. HHI {_f(mt.get('hhi'), '.4f')} (reported).", "",
             "## Population", "",
             f"Population `{m['source']}` - {'the registered population' if pop.get('source') == m['source'] else '**NOT the registered population**'} "
             f"(registration names `{pop.get('source', 'none')}`, recorded {str(pop.get('recorded_utc', '-'))[:10]}). "
             "`cascade_excursions` also holds `trade_flow` rows; the desk's schema keeps the source column because the two "
             "event sources answer different questions and must never be pooled. Round 113's progress mirror pooled them "
             "and read this sample as ready; over the registered population it is not.", "",
             "## Primary metric", "",
             f"`ratio_30m` = mean(MFE) / mean(MAE) over the fade direction at 30 minutes = **{_f(m['ratio_30m'], '.4f')}** "
             f"on n = {m['n_30m'] or 0:,} measurable events. Below 1 means the cascade kept going: the adverse excursion "
             "outweighed the favourable one.", "",
             f"- P(ratio_30m >= {g['ratio_bar']}) = **{_f(m['cluster_p_ge_1_25'], '.4f')}** under a cluster bootstrap "
             f"resampling coins ({(m['resamples'] or 0):,} draws, seed {m['seed']}). Bar: > {g['confidence_bar']}.",
             f"- P(ratio_30m >= 1.0) = {_f(m['cluster_p_ge_1'], '.4f')} (context; the retirement's own statistic).",
             f"- Matched random-entry control ratio {_f(m['control_ratio_30m'], '.4f')}; edge vs control {_f(m['edge_vs_control'])}.", "",
             "## Horizons (5m, 15m, 30m registered; 60m reported only)", "",
             "| Horizon | n | ratio | control | P(>= 1.0) | P(>= bar) | coins | top share |", "|---|---|---|---|---|---|---|---|"]
    for h in ("5m", "15m", "30m", "60m"):
        d = horizons.get(h) or {}
        sig, ctl = d.get("signal") or {}, d.get("control") or {}
        mark = " **(decision)**" if h == "30m" else ("" if d.get("registered", h != "60m") else " (reported)")
        body.append(f"| {h}{mark} | {sig.get('n', 0):,} | {_f(sig.get('ratio'), '.4f')} | {_f(ctl.get('ratio'), '.4f')} | "
                    f"{_f(d.get('cluster_p_ge_1'), '.4f')} | {_f(d.get('cluster_p_ge_reopen'), '.4f')} | "
                    f"{d.get('coins_measured', '-')} | {_f(d.get('top_coin_share'), '.4f')} |")
    env = art.get("_artifact") or {}
    gaps = overlapping_gaps(vault, m.get("first_event_utc"), m.get("last_event_utc"))   # Round 121, lint L12
    body += ["", "## Data audit", "",
             f"- rows in `cascade_excursions` at run: **{(m['rows_at_run'] or 0):,}**; treatment rows for `{m['source']}`: "
             f"**{(m['treatment_rows'] or 0):,}**; matched control rows: {(m['control_rows'] or 0):,}",
             f"- events span {m['first_event_utc'] or '-'} .. {m['last_event_utc'] or '-'} ({_f(mt.get('span_days'), '.2f')} days)",
             f"- measurable at the decision horizon: {(m['n_30m'] or 0):,}",
             ("- **data gaps inside this span**: " + ", ".join(f"[[{g}]]" for g in gaps) + " - no forward excursions were "
              "measured there; the count above is what the stream recorded, not what happened") if gaps else
             "- no known data gap inside this span",
             f"- artifact written at **{observed_at}** by `{env.get('writer', '-')}` (source: {observed_from}); "
             f"resamples {(m['resamples'] or 0):,}, seed {m['seed']}", "",
             "## What follows from this", "",
             "- The fade stays retired and PASSIVE. Nothing on this page enables execution; a PASS would be a decision for "
             "the architect and the operator, not an automatic consequence.",
             ("- The remedy for a narrow sample is a wider one, not a relaxed gate. " +
              ("; ".join(g["gate_failures"]) + " - those are what block.") if g["gate_failures"] else
              "- Every gate passes; the bar decides."),
             "- The registration page keeps reporting progress against these gates until a PASS or FAIL exists; an "
             "INSUFFICIENT evaluation does not close the question.", "",
             "## History", "",
             "| At | rows at run | events | top coin share | span d | ratio 30m | P(>= bar) | grade |",
             "|---|---|---|---|---|---|---|---|"]
    for h in history:
        body.append(f"| {h['at']} | {(h.get('rows_at_run') or 0):,} | {(h.get('events') or 0):,} | "
                    f"{_f(h.get('top_coin_share'), '.4f')} | {_f(h.get('span_days'), '.2f')} | {_f(h.get('ratio_30m'), '.4f')} | "
                    f"{_f(h.get('cluster_p'), '.4f')} | {h.get('grade')} |")
    body += ["", "## Related", "",
             link_if_exists(vault, "Experiment", REGISTRATION_STEM, "The pre-registration"),
             "- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]", ""]

    reg_rel, res_rel = rel_to(registration, dev_root), rel_to(result, dev_root)
    params = [{"name": f"fade_rebenchmark_{k}", "value": req.get(k), "file": reg_rel, "json_path": f"sample_requirements.{k}"}
              for k in ("min_events", "min_coins", "max_single_coin_share", "window_days", "max_hhi") if req.get(k) is not None]
    if pop.get("source"):
        params.append({"name": "fade_rebenchmark_population", "value": pop["source"], "file": reg_rel, "json_path": "population.source"})
    dev: dict[str, Any] = {
        "desk": 1, "kind": "rebenchmark_verdict", "grade": g["grade"], "engine_verdict": g["engine_verdict"],
        "grades_agree": g["agrees"], "band_if_sample_qualified": g["band_if_sample_qualified"],
        "gate_failures": g["gate_failures"], "bar_drift": g["bar_drift"], "bar": {"ratio": g["ratio_bar"], "confidence": g["confidence_bar"]},
        "measurement": m, "sample_metrics": mt, "grade_vocabulary": list(GRADES), "registration": REGISTRATION_STEM,
        "observed_at": observed_at, "observed_from": observed_from, "parameters": params,
        "requires_files": [reg_rel, res_rel], "history": history, "data_gaps": gaps,
    }
    meta = make_meta("Experiment", "Passive fade rebenchmark - verdict",
                     f"Reopening question graded against the pre-registered bar: **{g['grade']}** over `{m['source']}` "
                     f"(ratio_30m {_f(m['ratio_30m'], '.4f')}, P {_f(m['cluster_p_ge_1_25'], '.4f')}, "
                     f"{(mt.get('events') or 0):,} events on {mt.get('coins', 0)} coins, top coin {_f(mt.get('top_coin_share'), '.3f')}). "
                     "The fade stays retired either way.",
                     tags=["experiment", "desk-1", "fade", "verdict", g["grade"].lower(), "rebenchmark"],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "artifact", "resource": res_rel, "title": "fade_rebenchmark artifact",
                               "author": "process:HyperLiquid.HL_Monarch.analytics.fade_rebenchmark"},
                              {"id": "registration", "resource": reg_rel, "title": "passive_fade_rebenchmark pre-registration",
                               "author": GENERATED_BY}],
                     dev=dev)
    carry_human_fields(existing, meta)
    return Page(path, meta, "\n".join(body))


def ingest_rebenchmark(vault: Path, dev_root: Path, *, result: Path | None = None, registration: Path | None = None,
                       at: datetime | None = None, by: str = GENERATED_BY) -> Page | None:
    at = at or now_utc()
    result = result or (dev_root / DEFAULT_RESULT)
    registration = registration or (dev_root / DEFAULT_REGISTRATION)
    if not result.is_file() or not registration.is_file():
        return None
    art = json.loads(result.read_text(encoding="utf-8"))
    reg = json.loads(registration.read_text(encoding="utf-8"))
    observed, observed_from = written_at(art, result)
    page = build_page(art, reg, vault, dev_root, result, registration, at, observed, by, observed_from=observed_from)
    changed = page_changed(page, vault)
    write_page(page, vault, now=at)
    write_register(vault, "Experiment", at=at, by=by)
    write_index(vault, load_pages(vault))
    g = page.meta["dev"]
    if changed:
        append_log(vault, "Ingest", f"passive fade rebenchmark graded against its pre-registration: **{g['grade']}** "
                   f"(engine said `{g['engine_verdict']}`, {'agree' if g['grades_agree'] else 'DISAGREE'}); "
                   f"population `{g['measurement']['source']}`, ratio_30m {_f(g['measurement']['ratio_30m'], '.4f')}, "
                   f"P {_f(g['measurement']['cluster_p_ge_1_25'], '.4f')} -> [[{STEM}]].", when=at)
    return page


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.fade_rebenchmark", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--result", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_RESULT.as_posix()}")
    ap.add_argument("--registration", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_REGISTRATION.as_posix()}")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    page = ingest_rebenchmark(args.vault, args.dev_root, result=args.result, registration=args.registration, at=at_from(args))
    if page is None:
        print(f"[REFUSE] the rebenchmark artifact or its registration is missing. Run:\n  {RUNNER} --out "
              f"data/experiments/passive_fade_rebenchmark.verdict.json\n(exit 3)", file=out)
        return 3
    g = page.meta["dev"]
    print(f"[WRITE] {page.path.relative_to(args.vault).as_posix()}", file=out)
    print(f"grade {g['grade']} · engine said {g['engine_verdict']} · {'agree' if g['grades_agree'] else 'DISAGREE'}", file=out)
    if g["gate_failures"]:
        print("gate failures: " + "; ".join(g["gate_failures"]), file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
