"""Pre-registrations and archived controls -> Experiment pages.

    python -m knowledge.ingest.experiments [--dir DIR ...] [--force] [--at ISO]

Default folders (Round 98, B3): cross_market/experiments/ AND
HyperLiquid/HL_Monarch/data/experiments/. Three registration shapes exist:
  *.meta.json (lead-lag tiers)   experiment, registered_utc, status, bars {...}, subfamilies, commands
  *.rules.json (sniper rules)    experiment, registered_utc, release_utc, status, rules[] (market = YES
                                 token id, op, value, outcome_if_true, neg_risk), not_found_in_drop[]
  *.meta.json (HL paper desk)    experiment, registered_utc | archived_utc, control, changes_vs_control,
                                 acceptance_bar, commitments, amendments, known_defect_not_fixed, or an
                                 archived control's result fields (closed_trades, win_rate_pct, ...)
Files with "sample" in the name are skipped; a data file without an `experiment`
key (the N=12 baseline itself) is not a registration and is ignored, but the
registration that cites it lists it under `dev.requires_files`, so deleting or
overwriting the control is a lint C1 finding.

Every numeric bar becomes a `dev.parameters` entry addressed by `json_path`
(lint C1; the same key can occur in several blocks), every token becomes
`dev.tokens` (lint C2), a rules file's T-2..T+5 becomes `dev.window`
(write_page refuses inside it; lint C5 reports). Pages stay `status: draft`
until a verdict page exists. The Experiments register is rebuilt after every run.
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
from ..lint import rules_from_raw
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc, page_path,
                     write_index, write_page)
from ..registers import update_register as _update_register
from . import add_common_args, at_from, guard, item_link, rel_to

DEFAULT_DIRS = (Path("cross_market") / "experiments", Path("HyperLiquid") / "HL_Monarch" / "data" / "experiments")
WINDOW_BEFORE = timedelta(minutes=2)
WINDOW_AFTER = timedelta(minutes=5)
REGISTER_FILE = "experiments_register"

DESK_LINKS = {
    1: "[[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]",
    3: "[[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]",
}


def page_stem(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", path.stem)


def first_sentence(text: str, limit: int = 300) -> str:
    s = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    return (s[: limit - 1] + "…") if len(s) > limit else s


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").lower()


def _numeric_leaves(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """(dotted path, value) for every int/float inside nested mappings (lists are not descended)."""
    out: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out.append((path, v))
            elif isinstance(v, dict):
                out.extend(_numeric_leaves(v, path))
    return out


def _bars_parameters(bars: dict[str, Any], rel: str) -> list[dict[str, Any]]:
    return [{"name": f"lead_lag_{k}", "value": v, "file": rel, "json_path": f"bars.{k}"}
            for k, v in bars.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _render_value(val: Any, out: list[str]) -> None:
    if isinstance(val, dict):
        out += ["| Key | Value |", "|---|---|"]
        for k, v in val.items():
            s = v if isinstance(v, str) else json.dumps(v)
            out.append(f"| `{k}` | {str(s)[:240]} |")
        out.append("")
    elif isinstance(val, list):
        for item in val:
            if isinstance(item, dict):
                out.append("- " + "; ".join(f"**{k}**: {str(v)[:200]}" for k, v in item.items()))
            else:
                out.append(f"- {item}")
        out.append("")
    else:
        out += [str(val), ""]


# ---------------------------------------------------------------- lead-lag (Desk 3)

def compile_lead_lag_registration(data: dict[str, Any], path: Path, vault: Path, dev_root: Path, at, by: str) -> Page:
    rel = rel_to(path, dev_root)
    name = str(data.get("experiment") or path.stem)
    bars = data.get("bars") if isinstance(data.get("bars"), dict) else {}
    subs = data.get("subfamilies") if isinstance(data.get("subfamilies"), dict) else {}
    body = [f"# Experiment: {name}", "", "> Pre-registration, Item 18 (lead-lag). Verdict pages link back here when they land.", "",
            "## Status at registration", "", str(data.get("status", "")), ""]
    for key in ("decision", "why", "tier1_unchanged", "differs_from_tier2_only_in"):
        if data.get(key):
            body += [f"## {key.replace('_', ' ').capitalize()}", "", str(data[key]), ""]
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
    body += ["## Related", "", f"- {DESK_LINKS[3]}",
             item_link(vault, "Item_18_Cross_Market_Titan_Correlator_Macro_Crypto", "Item 18: Cross-Market Titan Correlator"),
             f"- [[{REGISTER_FILE}|Experiments register]]", ""]
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


# ---------------------------------------------------------------- sniper rules (Desk 3)

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
    body += ["## Related", "", f"- {DESK_LINKS[3]}",
             "- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]",
             "- [[Ruling_R02|R2 - record the CLOB around a scheduled print]]", "- [[Ruling_R04|R4 - neg_risk books skip the NO side]]",
             f"- [[{REGISTER_FILE}|Experiments register]]", ""]
    dev: dict[str, Any] = {"desk": 3, "item": 12, "registration": rel, "kind": "sniper_rules"}
    if data.get("registered_utc"):
        dev["registered_utc"] = str(data["registered_utc"])
    if release:
        dev["release_utc"] = iso(release)
        dev["window"] = {"start": iso(release - WINDOW_BEFORE), "end": iso(release + WINDOW_AFTER)}
    # Ruling R107-1.E: the rules go into the FRONTMATTER, structured. The drill card used to parse
    # them back out of the rendered markdown table, which truncates token ids to 12 characters for
    # readability - so at T-2 the card showed `561528276087…`, a token nobody can paste. Reading
    # structured data is also proof against a future edit to the table's column layout.
    # ONE transform, shared with lint.check_rules_drift (Ruling R108-1.E). Two independent
    # transcriptions of the same mapping would drift exactly the way that check exists to catch,
    # and the check would be comparing its own idea of the rules against the page's.
    dev["rules"] = rules_from_raw(data)
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


# ---------------------------------------------------------------- generic registration / archived control (Desk 1)

PARAM_BLOCKS = ("acceptance_bar", "sample_requirements", "reopening_bar", "state_at_registration")
RESULT_KEYS = ("closed_trades", "wins", "losses", "win_rate_pct", "profit_factor", "net_pnl", "gross_pnl", "fees_paid")


def compile_generic_registration(data: dict[str, Any], path: Path, vault: Path, dev_root: Path, at, by: str) -> Page:
    rel = rel_to(path, dev_root)
    name = str(data.get("experiment") or path.stem)
    desk = 1 if "HyperLiquid" in path.resolve().parts else 3
    archived = "archived_utc" in data
    kind = "archived_control" if archived else "registration"
    head = ("Archived control: the result is frozen; its numbers below are guarded by lint C1, so overwriting the file is a finding."
            if archived else "Pre-registration: bars fixed before the data. Amendments are listed, never applied silently.")
    status = data.get("status") or data.get("why") or data.get("key_finding") or name
    body = [f"# Experiment: {name}", "", f"> {head}", ""]
    for key, val in data.items():
        if key == "experiment":
            continue
        body.append(f"## {key.replace('_', ' ').capitalize()}")
        body.append("")
        _render_value(val, body)
    requires: list[str] = []
    ctrl = data.get("control")
    if isinstance(ctrl, str):
        # HL registrations name the control relative to the HL_Monarch root (data/experiments/...)
        candidate = (path.parents[2] / ctrl) if len(path.parents) > 2 else (path.parent / ctrl)
        if candidate.is_file():
            requires.append(rel_to(candidate, dev_root))
    if archived:
        sibling = path.with_name(path.name.replace(".meta.json", ".json"))
        if sibling != path and sibling.is_file():
            requires.append(rel_to(sibling, dev_root))
    params: list[dict[str, Any]] = []
    for block in PARAM_BLOCKS:
        if isinstance(data.get(block), dict):
            for leaf, v in _numeric_leaves(data[block], block):
                params.append({"name": f"{_safe(name)}_{_safe(leaf)}", "value": v, "file": rel, "json_path": leaf})
    if archived:
        for k in RESULT_KEYS:
            v = data.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                params.append({"name": f"{_safe(name)}_{k}", "value": v, "file": rel, "json_path": k})
    body += ["## Related", "", f"- {DESK_LINKS.get(desk, DESK_LINKS[3])}"]
    if desk == 1:  # Round 99 ruling: primary Item 14 (whale cascade sweeper), Item 8 (basis harvester) cross-referenced
        body += [item_link(vault, "Item_14_Hyperliquid_Whale_Cascade_Sweeper", "Item 14: Hyperliquid Whale Cascade Sweeper", " (primary)"),
                 item_link(vault, "Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester", "Item 8: Hyperliquid Delta-Neutral Funding Rate Harvester", " (cross-reference)")]
    body += [f"- [[{REGISTER_FILE}|Experiments register]]", ""]
    dev: dict[str, Any] = {"desk": desk, "registration": rel, "kind": kind}
    if desk == 1:
        dev["item"] = 14
        dev["related_items"] = [8]
    stamp = data.get("registered_utc") or data.get("archived_utc")
    if stamp:
        dev["registered_utc"] = str(stamp)
    if params:
        dev["parameters"] = params
    if requires:
        dev["requires_files"] = requires
    meta = make_meta("Experiment", f"Experiment: {name}", first_sentence(str(status)),
                     tags=["experiment", f"desk-{desk}", kind.replace("_", "-")],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "registration", "resource": rel, "title": path.name, "author": "human:operator"}],
                     dev=dev)
    return Page(page_path(vault, "Experiment", page_stem(path)), meta, "\n".join(l for l in body if l is not None))


def compile_registration(path: Path, vault: Path, dev_root: Path, at, by: str = GENERATED_BY) -> Page | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "experiment" not in data:
        return None
    if isinstance(data.get("rules"), list) and "release_utc" in data:
        page = compile_rules_registration(data, path, vault, dev_root, at, by)
    elif isinstance(data.get("bars"), dict):
        page = compile_lead_lag_registration(data, path, vault, dev_root, at, by)
    else:
        page = compile_generic_registration(data, path, vault, dev_root, at, by)
    page.meta.setdefault("dev", {}).setdefault("tests_run", 0)  # B14: a registration has seen no data yet
    carry_human_fields(load_page(page.path), page.meta)          # Ruling 99-2: --force never drops a ratification
    return page


def update_register(vault: Path, *, at, by: str = GENERATED_BY) -> Page:
    """Kept for callers that import it from here (lead_lag); delegates to registers."""
    return _update_register(vault, "Experiment", at=at, by=by)


@dataclass
class IngestReport:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)


def ingest_experiments(exp_dirs, vault: Path, dev_root: Path, *, at=None, by: str = GENERATED_BY,
                       force: bool = False) -> IngestReport:
    at = at or now_utc()
    dirs = [exp_dirs] if isinstance(exp_dirs, Path) else list(exp_dirs)
    report = IngestReport()
    for exp_dir in dirs:
        if not exp_dir.is_dir():
            continue
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
        append_log(vault, "Ingest", f"registrations from {', '.join('`' + rel_to(d, dev_root) + '`' for d in dirs if d.is_dir())}: "
                   f"{len(report.written)} Experiment page(s) written, {len(report.skipped)} kept; [index](index.md) rebuilt.",
                   when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.experiments", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--dir", type=Path, action="append", default=None,
                    help="registration folder (repeatable); default: " + " and ".join(d.as_posix() for d in DEFAULT_DIRS))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    dirs = args.dir or [args.dev_root / d for d in DEFAULT_DIRS]
    if not any(d.is_dir() for d in dirs):
        print(f"[REFUSE] no registration folder found among {[d.as_posix() for d in dirs]} (exit 3)", file=out)
        return 3
    report = ingest_experiments(dirs, args.vault, args.dev_root, at=at_from(args), force=args.force)
    for r in report.written:
        print("[WRITE] " + r, file=out)
    for r in report.skipped:
        print("[KEEP]  " + r, file=out)
    for r in report.ignored:
        print("[SKIP]  " + r + " (sample, data file or unrecognised)", file=out)
    print(f"experiments: {len(report.written)} written, {len(report.skipped)} kept, {len(report.ignored)} ignored", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
