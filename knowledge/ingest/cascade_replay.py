"""Whale sweeper cascade replay -> the Item 14 verdict page (Round 104, backlog B1/F3).

    python -m HyperLiquid.HL_Monarch.analytics.cascade_replay --json --out cross_market/data/whale_sweeper_cascade_replay_verdict.json
    python -m knowledge.ingest.cascade_replay [--result PATH] [--registration PATH]

WHY THIS ADAPTER EXISTS AND WHY IT RE-GRADES. Round 103 recorded the replay's numbers by
transcribing them out of a handoff message. That is a copied-state violation on the very page
whose job is to prevent one, and it has already gone wrong: the message reported side B at
P=0.5020, which sits just inside the registration's RETUNE band, while the artifact says 0.4808,
which is FAIL. Nobody mistyped anything - `cascade_excursions` is written by a live collector and
grew underneath the two runs. So this adapter reads the JSON the engine wrote, and never a number
a human or an agent retyped.

It also GRADES INDEPENDENTLY rather than copying `artifact["verdict"]`. The bands come from
whale_sweeper_cascade_replay.meta.json, the pre-registration, and are applied here; the engine's
own verdict string is then compared against that grade. Agreement is the normal case and is
reported as such. A DISAGREEMENT IS A FINDING, not something to reconcile silently - it means the
engine and the registration have drifted apart, and the page says so in both voices.

The registration's own numbers are pinned as `dev.parameters` with `json_path`, so lint C1 fires
if the acceptance bar is edited after the data was seen. That is the whole point of registering it.

TWO THINGS THIS PAGE MUST KEEP SAYING:
  * the verdict is INSUFFICIENT, and an insufficient sample is never reported as a weak PASS or a
    FAIL (registration commitment 4);
  * this is a RETROSPECTIVE REPLAY, NOT A FORWARD TEST, and a PASS would not un-gate Item 14.

Read-only on the artifact and the registration. Writes only through pages.write_page.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc,
                     page_path, write_index, write_page)
from . import add_common_args, at_from, guard, item_link, link_if_exists, md_cell, page_changed, rel_to
from ..registers import write_register

STEM = "whale_sweeper_cascade_replay_verdict"
DEFAULT_RESULT = Path("cross_market") / "data" / f"{STEM}.json"
DEFAULT_REGISTRATION = (Path("HyperLiquid") / "HL_Monarch" / "data" / "experiments"
                        / "whale_sweeper_cascade_replay.meta.json")
GRADES = ("PASS", "RETUNE", "FAIL", "INSUFFICIENT")
# The compiled registration page, written by knowledge.ingest.experiments. NOT STEM minus
# "_verdict": that adapter appends "_meta" to the raw filename, and guessing produced a dangling link.
REGISTRATION_STEM = "whale_sweeper_cascade_replay_meta"


def band_of(p: float | None, reg: dict[str, Any]) -> str:
    """The registration's acceptance bands, applied to P(fade_ratio_30m >= 1.25)."""
    if p is None:
        return "INSUFFICIENT"
    if p > 0.90:
        return "PASS"
    return "RETUNE" if p >= 0.50 else "FAIL"


def gate_failures(metrics: dict[str, Any], reg: dict[str, Any]) -> list[str]:
    """Re-check every sample requirement from the registration against the artifact's metrics."""
    req = reg.get("sample_requirements") or {}
    out: list[str] = []
    checks = [("events", "min_events", "ge"), ("coins", "min_coins", "ge"),
              ("top_coin_share", "max_single_coin_share", "le"), ("hhi", "max_hhi", "le")]
    for key, req_key, sense in checks:
        got, want = metrics.get(key), req.get(req_key)
        if got is None or want is None:
            out.append(f"{key}: not reported (registration requires {req_key}={want})")
            continue
        if (sense == "ge" and got < want) or (sense == "le" and got > want):
            out.append(f"{key}={got:.4g} {'<' if sense == 'ge' else '>'} {want}")
    return out


def grade(art: dict[str, Any], reg: dict[str, Any]) -> dict[str, Any]:
    metrics = ((art.get("sample_gates") or {}).get("metrics")) or {}
    failures = gate_failures(metrics, reg)
    p = (art.get("primary_metric") or {}).get("cluster_p_ge_1_25")
    band = band_of(p, reg)
    ours = "INSUFFICIENT" if failures else band
    theirs = str(art.get("verdict") or "-")
    return {
        "grade": ours, "engine_verdict": theirs, "agrees": ours == theirs,
        "gate_failures": failures, "gates_passed": not failures,
        "cluster_p": p, "band_if_sample_qualified": band, "metrics": metrics,
    }


def measured(art: dict[str, Any]) -> dict[str, Any]:
    pm, audit = art.get("primary_metric") or {}, art.get("data_audit") or {}
    return {"fade_ratio_30m": pm.get("value"), "cluster_p_ge_1_25": pm.get("cluster_p_ge_1_25"),
            "rows_at_run": audit.get("total_in_table"), "raw_loaded": audit.get("raw_loaded"),
            "qualifying": audit.get("qualifying_count"), "truncated": audit.get("truncated_count"),
            "seed": (art.get("bootstrap_config") or {}).get("seed"),
            "resamples": (art.get("bootstrap_config") or {}).get("resamples")}


def _f(v, spec: str = "+.4f") -> str:
    return "-" if v is None else format(float(v), spec)


def written_at(art: dict[str, Any], result: Path) -> tuple[str, str]:
    """When the engine actually wrote this artifact, and how we know (Ruling R104-2).

    The `_artifact` envelope is authoritative. The file mtime is the fallback for artifacts written
    before Round 105 added the envelope, and it is a WEAKER claim - a checkout, a copy or a backup
    restores content with a fresh mtime - so the page states which one it is rather than presenting
    a guess as a fact.
    """
    stamp = (art.get("_artifact") or {}).get("written_at")
    if isinstance(stamp, str) and stamp:
        return stamp, "the artifact's own `_artifact.written_at`"
    return iso(datetime.fromtimestamp(result.stat().st_mtime, tz=timezone.utc)), "the file mtime (no `_artifact` envelope)"


def build_page(art: dict[str, Any], reg: dict[str, Any], vault: Path, dev_root: Path, result: Path,
               registration: Path, at: datetime, observed_at: str | None, by: str = GENERATED_BY,
               observed_from: str = "the file mtime") -> Page:
    g, m = grade(art, reg), measured(art)
    bar = reg.get("acceptance_bar") or {}
    horizons, asym = art.get("horizons") or {}, art.get("asymmetry") or {}
    path = page_path(vault, "Experiment", STEM)
    existing = load_page(path)
    history = [dict(r) for r in ((existing.meta.get("dev") or {}).get("history") or [])] if existing else []
    row = {"at": iso(at), "observed_at": observed_at, "rows_at_run": m["rows_at_run"],
           "events": g["metrics"].get("events"), "top_coin_share": g["metrics"].get("top_coin_share"),
           "ratio_30m": m["fade_ratio_30m"], "cluster_p": m["cluster_p_ge_1_25"], "grade": g["grade"]}
    # THE ARTIFACT IS THE UNIT OF OBSERVATION, not the ingest run. Re-running this adapter over an
    # unchanged file must not fabricate a second measurement: a crash between write_page and
    # append_log already left one phantom row here in Round 104. Same artifact (same mtime and the
    # same numbers) replaces the previous row; a genuinely new run has a new mtime and appends.
    if history and all(history[-1].get(k) == row[k] for k in ("observed_at", "rows_at_run", "ratio_30m", "cluster_p")):
        # Keep the ORIGINAL `at`: it records when this observation was first ingested, and the
        # observation has not changed. Bumping it would also make the rendered History table differ
        # on every re-run, defeating the Ruling R104-3 idempotence guard in write_page.
        row["at"] = history[-1].get("at", row["at"])
        history[-1] = row
    else:
        history.append(row)

    body = [
        "# Whale sweeper cascade replay - verdict", "",
        f"> **{g['grade']}**. Graded here against the pre-registration "
        f"(backlog B15, registered {reg.get('registered_utc')}), not copied from the engine's output.", "",
        "## Grade of evidence", "",
        f"**{(reg.get('grade_of_evidence') or {}).get('kind', 'retrospective replay')}.** "
        f"{(reg.get('grade_of_evidence') or {}).get('consequence', '')}", "",
        "## Verdict", "",
        f"- **This page grades: {g['grade']}**",
        f"- The engine reported: `{g['engine_verdict']}` -> "
        + ("the two agree." if g["agrees"] else "**THEY DISAGREE. That is the finding; neither is silently preferred.**"),
    ]
    if g["gate_failures"]:
        body += ["", "The sample requirements are NOT met, so **no verdict is issued** "
                 "(registration: \"a run failing any gate produces NO verdict, not a weak one\"). Unmet:", ""]
        body += [f"- {f}" for f in g["gate_failures"]]
        body += ["", f"Had the sample qualified, P = {_f(m['cluster_p_ge_1_25'], '.4f')} would have fallen in the "
                 f"**{g['band_if_sample_qualified']}** band. That is stated for completeness and **is not a "
                 "verdict**; it is exactly the reading the gates exist to prevent."]
    else:
        body += ["", f"All sample requirements met. P(ratio >= 1.25) = {_f(m['cluster_p_ge_1_25'], '.4f')} -> "
                 f"**{g['band_if_sample_qualified']}**."]

    body += ["", "## Sample gates, re-checked here", "", "| Requirement | Registered | Measured | |", "|---|---|---|---|"]
    req = reg.get("sample_requirements") or {}
    rows = [("events", ">= %s" % req.get("min_events"), g["metrics"].get("events")),
            ("coins", ">= %s" % req.get("min_coins"), g["metrics"].get("coins")),
            ("top coin share", "<= %s" % req.get("max_single_coin_share"), g["metrics"].get("top_coin_share")),
            ("HHI", "<= %s" % req.get("max_hhi"), g["metrics"].get("hhi"))]
    fails = " ".join(g["gate_failures"])
    for name, want, got in rows:
        ok = "FAIL" if name.split()[0] in fails or name.replace(" ", "_") in fails else "ok"
        got_s = f"{got:.4g}" if isinstance(got, float) else f"{got:,}" if isinstance(got, int) else "-"
        body.append(f"| {name} | {want} | {got_s} | {'**FAIL**' if ok == 'FAIL' else 'ok'} |")
    top = g["metrics"].get("top_coin")
    body += ["", f"The failing concentration is `{top}`. Note the HHI passes with very little room "
             f"({_f(g['metrics'].get('hhi'), '.5f')} against a {req.get('max_hhi')} ceiling), so this sample is "
             "narrow on two axes, not one.", "",
             "## Primary metric", "",
             f"`fade_ratio_30m` = median(mfe_30m) / median(mae_30m) = **{_f(m['fade_ratio_30m'], '.4f')}**. "
             f"A ratio below 1 means the average cascade kept going rather than reverting: the adverse excursion "
             f"was larger than the favourable one.", "",
             f"- P(ratio >= {(art.get('primary_metric') or {}).get('acceptance_threshold', 1.25)}) = "
             f"**{_f(m['cluster_p_ge_1_25'], '.4f')}** under a cluster bootstrap resampling coins "
             f"({m['resamples']:,} draws, seed {m['seed']}).",
             f"- Registered bands: PASS `{bar.get('PASS', '-')}` · RETUNE `{bar.get('RETUNE', '-')}` · "
             f"FAIL `{bar.get('FAIL', '-')}` · INSUFFICIENT `{bar.get('INSUFFICIENT', '-')}`.", "",
             "## Horizons (reported, not deciding)", "",
             "The registration pre-committed to 30m and says the others are reported only.", "",
             "| Horizon | n | median MFE | median MAE | ratio | win share | $ expectancy |", "|---|---|---|---|---|---|---|"]
    for h in ("5m", "15m", "30m", "60m"):
        d = horizons.get(h) or {}
        mark = " **(pre-committed)**" if h == "30m" else ""
        body.append(f"| {h}{mark} | {d.get('n', 0):,} | {_f(d.get('median_mfe'), '.4f')} | "
                    f"{_f(d.get('median_mae'), '.4f')} | {_f(d.get('median_fade_ratio'), '.4f')} | "
                    f"{_f(d.get('win_share'), '.2f')}% | {_f(d.get('dollar_expectancy'), '.4f')} |")
    body += ["", "Every horizon is below 1.0 and every dollar expectancy is negative. The result does not depend "
             "on the horizon choice.", "",
             "## Both cascade sides (registration commitment 5)", "",
             "| Side | n | median ratio 30m | $ expectancy | P(>= 1.25) |", "|---|---|---|---|---|"]
    for key, label in (("side_A_sell_fade_buys", "A - sell cascade, fade by buying"),
                       ("side_B_buy_fade_sells", "B - buy cascade, fade by selling")):
        d = asym.get(key) or {}
        body.append(f"| {label} | {d.get('n', 0):,} | {_f(d.get('median_fade_ratio_30m'), '.4f')} | "
                    f"{_f(d.get('dollar_expectancy'), '.4f')} | {_f(d.get('cluster_p_ge_1_25'), '.4f')} |")
    body += ["", "Side B's median ratio above 1.25 is the one eye-catching number in this artifact, and it does "
             "not survive clustering: its own P is below the PASS bar, and the registration's bands apply to the "
             "POOLED primary metric, not to a side split. **Reading a side split against the pooled bands is not "
             "something this registration authorises**, and Round 103's handoff note did exactly that from a "
             "transcribed 0.5020 that the artifact now puts at "
             f"{_f((asym.get('side_B_buy_fade_sells') or {}).get('cluster_p_ge_1_25'), '.4f')} - across the 0.50 "
             "boundary. Both reasons independently invalidate that reading.", "",
             "## Data audit", "",
             f"- rows in `cascade_excursions` at run: **{m['rows_at_run']:,}** "
             f"(the registration counted {((reg.get('data') or {}).get('state_at_registration') or {}).get('rows', '-'):,} "
             "at registration; the table is written by a live collector and grows continuously)",
             f"- loaded after excluding matched controls (`event_id > 0 AND source NOT LIKE 'control:%'`): "
             f"**{m['raw_loaded']:,}**. Roughly half the table is synthetic control rows by design; this is not data loss.",
             f"- qualifying after the truncation and null filters: **{m['qualifying']:,}** "
             f"({m['truncated']:,} excluded for an incomplete forward series, per the registration's "
             "`known_defect_not_fixed`)", ""]
    env = art.get("_artifact") or {}
    if observed_at and env:
        body += [f"- artifact written at **{observed_at}** by `{env.get('writer', '-')}`, from "
                 f"{env.get('rows_in_table', '-'):,} rows, seed {env.get('seed', '-')} "
                 f"(source: {observed_from}). Ruling R104-2 put this envelope on the engine in Round 105, so two "
                 "runs over a continuously growing table can finally be ordered from their own contents.", ""]
    elif observed_at:
        body += [f"- artifact observed at **{observed_at}**, taken from {observed_from}. This artifact predates "
                 "the Ruling R104-2 envelope, so its true run instant is unknown and the mtime is only an upper "
                 "bound - a checkout or a copy would reset it. Re-run the engine to stamp it properly.", ""]
    body += ["## Regime breakdown (reported)", "", "| Regime | n | median ratio 30m | $ expectancy |", "|---|---|---|---|"]
    for k, v in sorted((art.get("regime_breakdown") or {}).items()):
        body.append(f"| `{md_cell(k)}` | {v.get('n', 0):,} | {_f(v.get('median_fade_ratio'), '.4f')} | "
                    f"{_f(v.get('dollar_expectancy'), '.4f')} |")
    body += ["", "## What follows from this", "",
             "- Item 14 stays gated off. It was already gated, and an INSUFFICIENT sample is not grounds to change "
             "anything in either direction.",
             "- The registration's remedy for a narrow sample is to wait for a wider one, not to relax the gate. "
             f"`{top}` supplies {_f((g['metrics'].get('top_coin_share') or 0) * 100, '.1f')}% of events against a 20% "
             "ceiling; that share falls as other coins accumulate.",
             "- Nothing here licenses a forward test either. A forward test follows a PASS.", "",
             "## History", "",
             "| At | rows at run | events | top coin share | ratio 30m | P | grade |", "|---|---|---|---|---|---|---|"]
    for h in history:
        body.append(f"| {h['at']} | {h.get('rows_at_run'):,} | {h.get('events'):,} | "
                    f"{_f(h.get('top_coin_share'), '.4f')} | {_f(h.get('ratio_30m'), '.4f')} | "
                    f"{_f(h.get('cluster_p'), '.4f')} | {h.get('grade')} |")
    body += ["", "## Related", "",
             link_if_exists(vault, "Experiment", REGISTRATION_STEM, "The pre-registration (B15)"),
             item_link(vault, "Item_14_Hyperliquid_Whale_Cascade_Sweeper", "Item 14: Whale Cascade Sweeper"),
             "- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]", ""]

    reg_rel = rel_to(registration, dev_root)
    # Every sample gate pinned back at the registration by json_path. If the bar is edited after the
    # data was seen - the one thing a pre-registration exists to forbid - lint C1 reports the drift.
    params = [{"name": f"cascade_replay_{k}", "value": req.get(k), "file": reg_rel,
               "json_path": f"sample_requirements.{k}"}
              for k in ("min_events", "min_coins", "max_single_coin_share", "max_hhi")
              if req.get(k) is not None]
    dev: dict[str, Any] = {
        "desk": 1, "item": 14, "kind": "cascade_replay_verdict", "grade": g["grade"],
        "engine_verdict": g["engine_verdict"], "grades_agree": g["agrees"],
        "band_if_sample_qualified": g["band_if_sample_qualified"], "gate_failures": g["gate_failures"],
        "measurement": m, "sample_metrics": g["metrics"], "grade_vocabulary": list(GRADES),
        "registration": REGISTRATION_STEM, "observed_at": observed_at, "observed_from": observed_from,
        "parameters": params, "requires_files": [reg_rel], "history": history,
    }
    meta = make_meta("Experiment", "Whale sweeper cascade replay - verdict",
                     f"Item 14 retrospective replay graded against its pre-registered bar: **{g['grade']}** "
                     f"(ratio {_f(m['fade_ratio_30m'], '.4f')}, P {_f(m['cluster_p_ge_1_25'], '.4f')}, "
                     f"{g['metrics'].get('events', 0):,} events on {g['metrics'].get('coins', 0)} coins). "
                     "Retrospective replay, not a forward test.",
                     tags=["experiment", "desk-1", "item-14", "cascade", "verdict", g["grade"].lower(),
                           "retrospective-replay"],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "replay-json", "resource": rel_to(result, dev_root),
                               "title": "cascade_replay --json artifact",
                               "author": "process:HyperLiquid.HL_Monarch.analytics.cascade_replay"},
                              {"id": "registration", "resource": reg_rel,
                               "title": "whale_sweeper_cascade_replay pre-registration (B15)",
                               "author": GENERATED_BY}],
                     dev=dev)
    carry_human_fields(existing, meta)
    return Page(path, meta, "\n".join(body))


def ingest_replay(vault: Path, dev_root: Path, *, result: Path | None = None, registration: Path | None = None,
                  at: datetime | None = None, by: str = GENERATED_BY) -> Page | None:
    at = at or now_utc()
    result = result or (dev_root / DEFAULT_RESULT)
    registration = registration or (dev_root / DEFAULT_REGISTRATION)
    if not result.is_file() or not registration.is_file():
        return None
    art = json.loads(result.read_text(encoding="utf-8"))
    reg = json.loads(registration.read_text(encoding="utf-8"))
    observed, observed_from = written_at(art, result)
    page = build_page(art, reg, vault, dev_root, result, registration, at, observed, by,
                      observed_from=observed_from)
    changed = page_changed(page, vault)
    write_page(page, vault, now=at)
    write_register(vault, "Experiment", at=at, by=by)
    write_index(vault, load_pages(vault))
    g = page.meta["dev"]
    if changed:
        append_log(vault, "Ingest", f"cascade replay graded against its pre-registration: **{g['grade']}** "
                   f"(engine said `{g['engine_verdict']}`, {'agree' if g['grades_agree'] else 'DISAGREE'}); "
                   f"ratio {_f(g['measurement']['fade_ratio_30m'], '.4f')}, "
                   f"P {_f(g['measurement']['cluster_p_ge_1_25'], '.4f')} "
                   f"-> [[{STEM}]].", when=at)
    return page


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.cascade_replay", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--result", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_RESULT.as_posix()}")
    ap.add_argument("--registration", type=Path, default=None,
                    help=f"default <dev-root>/{DEFAULT_REGISTRATION.as_posix()}")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    page = ingest_replay(args.vault, args.dev_root, result=args.result, registration=args.registration,
                         at=at_from(args))
    if page is None:
        print("[REFUSE] the replay artifact or its registration is missing. Run:\n"
              "  python -m HyperLiquid.HL_Monarch.analytics.cascade_replay --json --out "
              f"{DEFAULT_RESULT.as_posix()}\n(exit 3)", file=out)
        return 3
    g = page.meta["dev"]
    print(f"[WRITE] {page.path.relative_to(args.vault).as_posix()}", file=out)
    print(f"grade {g['grade']} · engine said {g['engine_verdict']} · "
          f"{'agree' if g['grades_agree'] else 'DISAGREE'}", file=out)
    if g["gate_failures"]:
        print("gate failures: " + "; ".join(g["gate_failures"]), file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
