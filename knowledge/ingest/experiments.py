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
from ..lint import STALL_DAYS, rules_from_raw
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc, page_path,
                     write_index, write_page)
from ..registers import update_register as _update_register, write_register
from . import add_common_args, at_from, guard, item_link, page_changed, rel_to

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


PAPER_STATE = Path("HyperLiquid") / "HL_Monarch" / "data" / "paper_trading_state.json"
HL_DB = Path("HyperLiquid") / "HL_Monarch" / "data" / "hyperliquid_data.db"


def _gate(value: float, bar: float, op: str) -> dict[str, Any]:
    return {"value": value, "bar": bar, "pass": bool(value >= bar) if op == ">=" else bool(value <= bar)}


def event_gates(reqs: dict[str, Any], *, n: int, coins: int, top_share: float, span_days: float,
                hhi: float | None = None) -> dict[str, Any]:
    """Ruling R112-1.C, corrected: `ready` means EVERY sample requirement the registration wrote down
    passes, not that one count crossed its floor.

    passive_fade_rebenchmark binds itself to wick_benchmark.reopening_gate(): >=500 events, >=20
    coins, no coin over 20% of the sample, a 7-day window. Round 104's sibling verdict was INSUFFICIENT
    precisely because the share gate failed (PONS 22.5%) while the count was 38x its floor. This is a
    read-only SQL mirror of that gate over the same rows `accumulated` counts; the authoritative gate
    runs inside the benchmark, and recording every value here is what makes a disagreement visible.
    """
    out = {"min_events": _gate(n, int(reqs["min_events"]), ">=")}
    if isinstance(reqs.get("min_coins"), (int, float)):
        out["min_coins"] = _gate(coins, int(reqs["min_coins"]), ">=")
    if isinstance(reqs.get("max_single_coin_share"), (int, float)):
        out["max_single_coin_share"] = _gate(round(top_share, 4), float(reqs["max_single_coin_share"]), "<=")
    if isinstance(reqs.get("window_days"), (int, float)):
        out["window_days"] = _gate(round(span_days, 2), float(reqs["window_days"]), ">=")
    if isinstance(reqs.get("max_hhi"), (int, float)) and hhi is not None:
        out["max_hhi"] = _gate(round(hhi, 4), float(reqs["max_hhi"]), "<=")
    return out


def parked_note(data: dict[str, Any]) -> dict[str, Any]:
    """The dated amendment that parked this registration, if any (the file's OWN protocol)."""
    for a in data.get("amendments") or []:
        if isinstance(a, dict) and a.get("action") == "parked":
            return a
    return {}


def measure_progress(data: dict[str, Any], path: Path, vault: Path, dev_root: Path, archived: bool,
                     at) -> dict[str, Any] | None:
    """How far a registration has got toward its own sample bar (Ruling R112-OOB.2).

    WHY THIS EXISTS. regime_filtered_v1 sat at N=0 for five days with no process running, and the
    vault rendered it identically to an experiment being carefully respected. A pre-registration
    that cannot accumulate evidence must SAY so on its own page, or "no mid-flight changes before
    N=50" is honoured trivially and nobody notices there is no flight.

    Every read here is read-only and every source is optional: a fixture without the paper state
    file gets `accumulated: None` and `status: unmeasured`, never a guess. Statuses:
      completed    an archived control - its N is final
      parked       the registration carries a dated `action: parked` amendment
      evaluated    a `<stem>_verdict` page exists in the vault
      unmeasured   the source this unit reads from is not present
      accumulating everything else
    """
    from ..pages import iso
    bar = data.get("acceptance_bar") or {}
    reqs = data.get("sample_requirements") or {}
    unit, target, accumulated = None, None, None
    if archived:
        sibling = path.with_name(path.name.replace(".meta.json", ".json"))
        n = None
        if sibling.is_file():
            try:
                n = json.loads(sibling.read_text(encoding="utf-8")).get("closed_trades")
            except (OSError, json.JSONDecodeError, AttributeError):
                n = None
        return {"accumulated": n, "target": n, "unit": "closed_trades", "status": "completed",
                "measured_at": iso(at)}
    gates: dict[str, Any] = {}
    population = "pooled"
    if isinstance(bar.get("min_closed_trades"), (int, float)):
        unit, target = "closed_trades", int(bar["min_closed_trades"])
        state = dev_root / PAPER_STATE
        if state.is_file():
            try:
                accumulated = int(json.loads(state.read_text(encoding="utf-8")).get("closed_trades", 0))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                accumulated = None
        if accumulated is not None:
            gates = {"min_closed_trades": _gate(accumulated, target, ">=")}
    elif isinstance(reqs.get("min_events"), (int, float)):
        unit, target = "events", int(reqs["min_events"])
        db = dev_root / HL_DB
        if db.is_file():
            try:
                import sqlite3
                conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=8)
                pop = data.get("population") if isinstance(data.get("population"), dict) else {}
                source = pop.get("source")
                pooled = source in (None, "", "pooled", "all")
                if not pooled:  # Round 114: the registration names its population; one source, never pooled
                    where, params = "FROM cascade_excursions WHERE source = ?", (str(source),)
                else:           # pooled - either declared so (Round 115) or unnamed: every treatment row
                    where, params = "FROM cascade_excursions WHERE event_id > 0 AND source NOT LIKE 'control:%'", ()
                msm = reqs.get("min_samples_60m_per_event")
                if isinstance(msm, (int, float)):
                    # Round 115: the registration counts only events with a complete forward series, and so
                    # does its engine (cascade_replay filters samples_60m). The raw count put ZEC at 19.84%;
                    # the engine's qualifying rows put it at 20.20% - the mirror must count the same rows.
                    where, params = where + " AND samples_60m >= ?", params + (float(msm),)
                n, coins, lo, hi = conn.execute(
                    f"SELECT COUNT(*), COUNT(DISTINCT coin), MIN(timestamp_utc), MAX(timestamp_utc) {where}", params).fetchone()
                counts = [int(r[0]) for r in conn.execute(f"SELECT COUNT(*) {where} GROUP BY coin", params)]
                conn.close()
                accumulated = int(n)
                gates = event_gates(reqs, n=int(n), coins=int(coins or 0),
                                    top_share=(max(counts) / n) if (counts and n) else 0.0,
                                    span_days=((hi - lo) / 86_400_000.0) if (lo is not None and hi is not None) else 0.0,
                                    hhi=(sum((c / n) ** 2 for c in counts) if n else 0.0))
                population = "pooled" if pooled else str(source)
            except Exception:  # noqa: BLE001 - a missing table is "unmeasured", not a crash
                accumulated = None
    else:
        return None
    verdict_page = load_page(vault / "wiki" / "experiments" / f"{page_stem(path).removesuffix('_meta')}_verdict.md")
    last_verdict: dict[str, Any] | None = None
    if verdict_page is not None:
        vdev = verdict_page.meta.get("dev") or {}
        last_verdict = {"grade": vdev.get("grade"), "page": verdict_page.path.stem,
                        "at": vdev.get("observed_at") or (verdict_page.meta.get("generated") or {}).get("at")}
    terminal = verdict_page is not None and last_verdict.get("grade") != "INSUFFICIENT"
    if parked_note(data):
        status = "parked"
    elif terminal:
        status = "evaluated"
    elif accumulated is None:
        status = "unmeasured"
    elif gates and all(g["pass"] for g in gates.values()):
        status = "ready"          # every gate passes and nobody has evaluated it: the mirror of a stall
    else:
        status = "accumulating"
    out = {"accumulated": accumulated, "target": target, "unit": unit, "status": status,
           "measured_at": iso(at)}
    if gates:
        out["gates"] = gates
    if unit == "events" and accumulated is not None:
        out["population"] = population
    if last_verdict:
        out["last_verdict"] = last_verdict
    return out


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
    progress = measure_progress(data, path, vault, dev_root, archived, at)
    if progress is not None:
        # measured_at means WHEN THIS MEASUREMENT WAS TAKEN, and an unchanged measurement was not
        # taken again just because the compiler ran. Left as `at`, every run re-stamped it, which
        # rewrote every registration page, the experiments register, the hub above it and log.md -
        # the Ruling R104-3 restamp problem, one field down. The page on disk keeps its stamp
        # whenever accumulated/target/unit/status are all unchanged.
        prior = ((load_page(page_path(vault, "Experiment", page_stem(path))) or Page(Path("x"), {}))
                 .meta.get("dev") or {}).get("progress")
        if isinstance(prior, dict) and all(prior.get(k) == progress.get(k)
                                           for k in ("accumulated", "target", "unit", "status")):
            progress["measured_at"] = prior.get("measured_at", progress["measured_at"])
        if progress.get("status") == "ready":
            carried = prior.get("ready_since") if isinstance(prior, dict) and prior.get("status") == "ready" else None
            progress["ready_since"] = carried or iso(at)
        dev["progress"] = progress
        if progress.get("status") == "parked":
            note = parked_note(data)
            body[3:3] = ["> [!NOTE]", f"> **PARKED ({note.get('utc', '')[:10]})**: {note.get('why', '')}", ""]
        elif progress.get("status") == "ready":
            gates_txt = "; ".join(f"{k} {g['value']} vs {g['bar']}" for k, g in (progress.get("gates") or {}).items())
            body[3:3] = ["> [!NOTE]",
                         f"> **READY (since {str(progress.get('ready_since', ''))[:10]})**: every sample gate passes "
                         f"({gates_txt}) and no verdict page exists. Evaluate it under the registered bar or retire "
                         f"it; lint L11 warns once this has stood for {STALL_DAYS} days.", ""]
        elif progress.get("status") == "accumulating" and progress.get("gates"):
            gts = progress["gates"]
            failing = [f"{k} {g['value']} vs {g['bar']}" for k, g in gts.items() if not g.get("pass")]
            lv = progress.get("last_verdict") or {}
            tail = (f" Last evaluation {str(lv.get('at', ''))[:10]}: **{lv.get('grade')}** ([[{lv.get('page')}]]) - "
                    "an insufficient sample is never a verdict, so the question stays open." if lv else "")
            body[3:3] = ["> [!NOTE]",
                         f"> **ACCUMULATING** - {sum(1 for g in gts.values() if g.get('pass'))}/{len(gts)} sample gates pass "
                         f"over population `{progress.get('population', 'pooled')}`."
                         + (f" Failing: {'; '.join(failing)}." if failing else "") + tail, ""]
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
    if isinstance(data, dict) and "_artifact" in data:
        # An engine ARTIFACT (Ruling R104-2 envelope) beside the registrations, e.g. *.verdict.json. Its own
        # adapter compiles it; compiling it here too made two writers of one page (Round 114 finding).
        return None
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
            # Ruling R104-3, finally applied here too: `written` means the page MOVED. Counting every
            # forced write as written made --force append a log line - and dirty git - on runs that
            # changed nothing, the last adapter still doing so after Round 105 converted the others.
            changed = page_changed(page, vault)
            write_page(page, vault, now=at)
            (report.written if changed else report.skipped).append(rel)
    if report.written:
        write_register(vault, "Experiment", at=at, by=by)
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
        print("[SKIP]  " + r + " (sample, engine artifact, data file or unrecognised)", file=out)
    print(f"experiments: {len(report.written)} written, {len(report.skipped)} kept, {len(report.ignored)} ignored", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
