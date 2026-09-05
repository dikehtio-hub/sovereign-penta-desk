"""Pre-registrations -> Experiment pages.

    python -m knowledge.ingest.experiments [--dir cross_market/experiments] [--force] [--at ISO]

Two registration shapes exist in cross_market/experiments/:
  *.meta.json   lead-lag tiers: experiment, registered_utc, status, bars {min_abs_corr,
                min_events, min_points, latency_minutes_*}, subfamilies, commands, caveats
  *.rules.json  sniper rules: experiment, registered_utc, release_utc, status, rules[]
                (label, market = YES token id, op, value, outcome_if_true, neg_risk),
                not_found_in_drop[], corrections[]
Files with "sample" in the name are skipped (placeholder tokens).

The page keeps the registration honest by construction: every numeric bar becomes a
`dev.parameters` entry pointing back at the JSON (lint C1), every token becomes
`dev.tokens` (lint C2), and a rules file's T-2..T+5 becomes `dev.window`
(write_page refuses inside it; lint C5 reports). Pages stay `status: draft`
until a verdict page exists.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..frontmatter import parse_iso8601
from ..pages import Page, append_log, iso, load_pages, make_meta, now_utc, page_path, write_index, write_page
from . import add_common_args, at_from, guard, rel_to

DEFAULT_DIR = Path("cross_market") / "experiments"
WINDOW_BEFORE = timedelta(minutes=2)
WINDOW_AFTER = timedelta(minutes=5)


def page_stem(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", path.stem)


def first_sentence(text: str, limit: int = 300) -> str:
    s = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    return (s[: limit - 1] + "…") if len(s) > limit else s


def _bars_parameters(bars: dict[str, Any], rel: str) -> list[dict[str, Any]]:
    """Bars as dev.parameters addressed by json_path: the same key name can occur in another
    block of the file (tier2b has readiness.min_points 200 and bars.min_points 60)."""
    out = []
    for k, v in bars.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append({"name": f"lead_lag_{k}", "value": v, "file": rel, "json_path": f"bars.{k}"})
    return out


def compile_lead_lag_registration(data: dict[str, Any], path: Path, vault: Path, dev_root: Path, at, by: str) -> Page:
    rel = rel_to(path, dev_root)
    name = str(data.get("experiment") or path.stem)
    bars = data.get("bars") if isinstance(data.get("bars"), dict) else {}
    subs = data.get("subfamilies") if isinstance(data.get("subfamilies"), dict) else {}
    body = [f"# Experiment: {name}", "", "> Pre-registration, Item 18 (lead-lag). Verdict pages link back here when they land.", "",
            "## Status at registration", "", str(data.get("status", "")), ""]
    if data.get("decision"):
        body += ["## Decision", "", str(data["decision"]), ""]
    if data.get("why"):
        body += ["## Why", "", str(data["why"]), ""]
    if bars:
        body += ["## Bars", "", "| Bar | Value |", "|---|---|"]
        body += [f"| `{k}` | {v} |" for k, v in bars.items()]
        body.append("")
    if subs:
        body += ["## Subfamilies", ""]
        for k, v in subs.items():
            if isinstance(v, dict):
                body.append(f"- **{k}**: {v.get('role', '')} {('· ' + str(v.get('reading'))) if v.get('reading') else ''}".rstrip())
            else:
                body.append(f"- **{k}**: {v}")
        body.append("")
    if data.get("reading_rule"):
        body += ["## Reading rule", "", str(data["reading_rule"]), ""]
    cmds = data.get("commands")
    if isinstance(cmds, list) and cmds:
        body += ["## Commands", "", "```", *[str(c) for c in cmds], "```", ""]
    if isinstance(data.get("caveats"), list):
        body += ["## Caveats", "", *[f"- {c}" for c in data["caveats"]], ""]
    if data.get("enforced_in_code"):
        body += ["## Enforced in code", "", str(data["enforced_in_code"]), ""]
    body += ["## Related", "", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]",
             "- [[Item_18_Cross_Market_Titan_Correlator_Macro_Crypto|Item 18: Cross-Market Titan Correlator]]", ""]
    dev: dict[str, Any] = {"desk": 3, "item": 18, "registration": rel, "kind": "lead_lag"}
    if data.get("registered_utc"):
        dev["registered_utc"] = str(data["registered_utc"])
    params = _bars_parameters(bars, rel)
    if params:
        dev["parameters"] = params
    meta = make_meta("Experiment", f"Experiment: {name}", first_sentence(str(data.get("status") or name)),
                     tags=["experiment", "desk-3", "item-18", "lead-lag", "pre-registered"],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "registration", "resource": rel, "title": path.name, "author": "human:operator"}],
                     dev=dev)
    return Page(page_path(vault, "Experiment", page_stem(path)), meta, "\n".join(body))


def compile_rules_registration(data: dict[str, Any], path: Path, vault: Path, dev_root: Path, at, by: str) -> Page:
    rel = rel_to(path, dev_root)
    name = str(data.get("experiment") or path.stem)
    rules = data.get("rules") if isinstance(data.get("rules"), list) else []
    release = parse_iso8601(data["release_utc"]) if data.get("release_utc") else None
    body = [f"# Experiment: {name}", "", "> Pre-registration, Item 12 (latency sniper). Reaction Profile pages link back here after the print.", "",
            "## Status at registration", "", str(data.get("status", "")), ""]
    if release:
        body += ["## Window", "", f"- release: `{iso(release)}`",
                 f"- window: `{iso(release - WINDOW_BEFORE)}` .. `{iso(release + WINDOW_AFTER)}` (T-2 .. T+5; this page is frozen inside it)", ""]
    if isinstance(data.get("event_schema"), dict):
        es = data["event_schema"]
        body += ["## Event schema", "", f"- kind: `{es.get('kind')}`", f"- payload: `{json.dumps(es.get('payload'))}`",
                 f"- source: {es.get('source')}", f"- confidence: {es.get('confidence')}", ""]
    if data.get("reading"):
        body += ["## Reading", "", str(data["reading"]), ""]
    if rules:
        body += ["## Rules", "", "| Label | Fires when | Outcome | YES at registration | neg_risk | Token |", "|---|---|---|---|---|---|"]
        for r in rules:
            body.append(f"| {r.get('label')} | `{r.get('field')} {r.get('op')} {r.get('value')}` | {r.get('outcome_if_true')} | "
                        f"{r.get('yes_price_at_registration')} | {r.get('neg_risk')} | `{str(r.get('market', ''))[:12]}…` |")
        body.append("")
    nf = data.get("not_found_in_drop")
    if isinstance(nf, list) and nf:
        body += ["## Not found in the drop at registration", "", *[f"- {x}" for x in nf], ""]
    corr = data.get("corrections")
    if isinstance(corr, list) and corr:
        body += ["## Corrections (all before the window)", ""]
        body += [f"- `{c.get('at_utc')}`: {c.get('what')} (before_window={c.get('before_window')})" for c in corr]
        body.append("")
    body += ["## Related", "", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]",
             "- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]",
             "- [[Ruling_R02|R2 - record the CLOB around a scheduled print]]", "- [[Ruling_R04|R4 - neg_risk books skip the NO side]]", ""]
    dev: dict[str, Any] = {"desk": 3, "item": 12, "registration": rel, "kind": "sniper_rules"}
    if data.get("registered_utc"):
        dev["registered_utc"] = str(data["registered_utc"])
    if release:
        dev["release_utc"] = iso(release)
        dev["window"] = {"start": iso(release - WINDOW_BEFORE), "end": iso(release + WINDOW_AFTER)}
    tokens = [str(r["market"]) for r in rules if isinstance(r, dict) and r.get("market")]
    if tokens:
        dev["tokens"] = tokens
    if isinstance(nf, list) and nf:
        dev["not_found_in_drop"] = [str(x) for x in nf]
    meta = make_meta("Experiment", f"Experiment: {name}", first_sentence(str(data.get("status") or name)),
                     tags=["experiment", "desk-3", "item-12", "latency-sniper", "pre-registered"],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "registration", "resource": rel, "title": path.name, "author": "human:operator"}],
                     dev=dev)
    return Page(page_path(vault, "Experiment", page_stem(path)), meta, "\n".join(body))


def compile_registration(path: Path, vault: Path, dev_root: Path, at, by: str = GENERATED_BY) -> Page | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("rules"), list) and "release_utc" in data:
        return compile_rules_registration(data, path, vault, dev_root, at, by)
    if isinstance(data.get("bars"), dict) or "experiment" in data:
        return compile_lead_lag_registration(data, path, vault, dev_root, at, by)
    return None


REGISTER_FILE = "experiments_register"


def update_register(vault: Path, *, at, by: str = GENERATED_BY) -> Page:
    """wiki/concepts/experiments_register.md: every Experiment page (registrations and
    verdicts), so none is an orphan and the Desk 3 page has one place to point at."""
    exps = sorted((p for p in load_pages(vault) if p.type == "Experiment"), key=lambda p: p.path.name)
    lines = ["# Experiments register", "",
             "> Every Experiment page in the wiki: pre-registrations (draft until a verdict lands) and verdicts as measured.",
             "> Maintained by the ingest adapters; hand edits are overwritten.", "",
             "| Page | Kind | Status | Generated |", "|---|---|---|---|"]
    for p in exps:
        dev = p.meta.get("dev") or {}
        gen = (p.meta.get("generated") or {}).get("at", "")
        lines.append(f"| [[{p.path.stem}\\|{p.title}]] | {dev.get('kind', '-')} | {p.meta.get('status', 'stable')} | {gen} |")
    lines += ["", "## Related", "", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]", ""]
    meta = make_meta("Concept", "Experiments register",
                     f"Index of the {len(exps)} Experiment page(s): pre-registrations and measured verdicts.",
                     tags=["concept", "desk-3", "experiments"], generated_by=by, at=at, status="draft",
                     sources=[{"id": "experiments", "resource": "obsidian_vault/wiki/experiments",
                               "title": "Experiment pages", "author": by}],
                     dev={"desk": 3, "count": len(exps), "pages": [p.path.stem for p in exps]})
    return Page(page_path(vault, "Concept", REGISTER_FILE), meta, "\n".join(lines))


@dataclass
class IngestReport:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)


def ingest_experiments(exp_dir: Path, vault: Path, dev_root: Path, *, at=None, by: str = GENERATED_BY,
                       force: bool = False) -> IngestReport:
    at = at or now_utc()
    report = IngestReport()
    for path in sorted(exp_dir.glob("*.json")):
        if "sample" in path.name.lower():
            report.ignored.append(path.name)
            continue
        page = compile_registration(path, vault, dev_root, at, by)
        if page is None:
            report.ignored.append(path.name)
            continue
        rel = page.path.relative_to(vault).as_posix()
        if page.path.exists() and not force:
            report.skipped.append(rel)
            continue
        write_page(page, vault, now=at)
        report.written.append(rel)
    if report.written:
        write_page(update_register(vault, at=at, by=by), vault, now=at)
        write_index(vault, load_pages(vault))
        append_log(vault, "Ingest", f"pre-registrations from `{rel_to(exp_dir, dev_root)}`: "
                   f"{len(report.written)} Experiment page(s) written, {len(report.skipped)} kept; [index](index.md) rebuilt.",
                   when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.experiments", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--dir", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_DIR.as_posix()}")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    exp_dir = args.dir or (args.dev_root / DEFAULT_DIR)
    if not exp_dir.is_dir():
        print(f"[REFUSE] experiments folder not found: {exp_dir} (exit 3)", file=out)
        return 3
    report = ingest_experiments(exp_dir, args.vault, args.dev_root, at=at_from(args), force=args.force)
    for r in report.written:
        print("[WRITE] " + r, file=out)
    for r in report.skipped:
        print("[KEEP]  " + r, file=out)
    for r in report.ignored:
        print("[SKIP]  " + r + " (sample or unrecognised)", file=out)
    print(f"experiments: {len(report.written)} written, {len(report.skipped)} kept, {len(report.ignored)} ignored", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
