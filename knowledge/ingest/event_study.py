"""Event-study result -> Reaction Profile pages (Experiment kind) + the Phase 2 panel.

    python -m cross_market.event_study --event fomc_2026-09-16 --json > cross_market/experiments/event_study_fomc_2026-09-16.json
    python -m knowledge.ingest.event_study --result cross_market/experiments/event_study_fomc_2026-09-16.json [--at ISO]

Consumes the JSON cross_market.event_study prints: event, T_utc, T0_utc, baseline_utc,
window_last_utc, bars{...}, sufficiency{...}, hyperliquid{...}, markets[{token, label,
stamps, sufficient, baseline, final, dp, t_star_rel_s, lead_s, class, informative,
reasons}], primary_market, class, lead_s, informative, sufficient, reasons. Writes:

  wiki/experiments/reaction_profile_<event>__<market>.md   one per registered token per event,
                                                            as measured (Ruling R125-2 s.6.4:
                                                            panel key = (event, market_token))
  wiki/experiments/lead_lag_phase2_panel.md                 every profile in one table, the count
                                                            of informative events, and the
                                                            pre-registered stopping rules applied
                                                            to the sequence (s.8.4)

A print under either displacement bar is written (it IS the event history) but is
`informative: false` and does not count toward the N >= 3 panel. The registration page's
`dev.tests_run` counts distinct events with a profile, via knowledge.ingest.experiments.
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
from ..pages import (Page, append_log, carry_human_fields, load_page, load_pages, make_meta, now_utc, page_path,
                     write_index, write_page)
from ..registers import write_register
from . import add_common_args, at_from, guard, item_link, link_if_exists, page_changed, rel_to
from .data_gaps import overlapping_gaps

PANEL_STEM = "lead_lag_phase2_panel"
REGISTRATION_STEM = "lead_lag_phase2_fomc_meta"
REGISTRATION_REL = "cross_market/experiments/lead_lag_phase2_fomc.meta.json"
KIND_PROFILE = "event_study_profile"
KIND_PANEL = "event_study_panel"
TERMINAL_CLASSES = ("contemporaneous-event-repricing", "hyperliquid-leads-event")


def slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(text)).strip("_")
    return s[:60] or "market"


def _f(v: Any, fmt: str = "{:g}") -> str:
    return "n/a" if v is None else (fmt.format(v) if isinstance(v, (int, float)) else str(v))


def compile_profile(result: dict[str, Any], market: dict[str, Any], vault: Path, *, source: str, at: datetime,
                    by: str = GENERATED_BY) -> Page:
    ev = result.get("event") or {}
    event_id = str(ev.get("id"))
    label = str(market.get("label") or market.get("token"))
    hl = result.get("hyperliquid") or {}
    bars = result.get("bars") or {}
    klass = market.get("class") or ("insufficient" if not market.get("sufficient") else None)
    title = f"Reaction profile: {event_id} / {label}"
    body = [f"# {title}", "",
            f"> Event `{event_id}` ({ev.get('label')}) · T `{result.get('T_utc')}` · class **{klass}** · lead {_f(market.get('lead_s'))} s · "
            f"{'counted toward the panel' if market.get('informative') else 'NOT counted toward the panel'}", "",
            "## Measurement", "", "| Field | Polymarket (this market) | HyperLiquid (BTC) |", "|---|---|---|",
            f"| baseline P(T-5 s) | {_f(market.get('baseline'))} | {_f(hl.get('baseline_px'))} (print age {_f(hl.get('baseline_age_s'))} s) |",
            f"| final P(T+300 s) | {_f(market.get('final'))} | {_f(hl.get('final_px'))} |",
            f"| displacement | {_f(market.get('dp'))} | {_f(hl.get('dp_rel_bps'))} bps |",
            f"| bar | {_f(bars.get('pm_min_displacement'))} | {_f(bars.get('hl_bar_bps'))} bps ({bars.get('hl_bar_source')}) |",
            f"| displaced | {market.get('displaced')} | {hl.get('displaced')} |",
            f"| t*50% (s from T) | {_f(market.get('t_star_rel_s'))} | {_f(hl.get('t_star_rel_s'))} |",
            f"| stamps / prints in window | {_f(market.get('stamps'))} | {_f(hl.get('prints'))} |", "",
            "## Grid", "", f"- T0 (first stamp): `{result.get('T0_utc')}`; baseline `{result.get('baseline_utc')}`; window end `{result.get('window_last_utc')}`; grid {result.get('grid_s')} s",
            f"- lead_s = t*HL - t*PM = {_f(market.get('lead_s'))}; tolerance ±{_f(bars.get('lead_tolerance_s'))} s; half-life fraction {_f(bars.get('half_life_fraction'))}", ""]
    reasons = list(market.get("reasons") or []) + ([] if result.get("sufficient") else list(result.get("reasons") or []))
    if reasons:
        body += ["## Reasons", "", *[f"- {r}" for r in reasons], ""]
    body += ["## Related", "", f"- [[{REGISTRATION_STEM}|Phase 2 registration]]", f"- [[{PANEL_STEM}|Phase 2 panel]]",
             link_if_exists(vault, "Regime", "btc_macro_regime", "BTC macro regime (Phase 1 consensus)"),
             item_link(vault, "Item_18_Cross_Market_Titan_Correlator_Macro_Crypto", "Item 18: Cross-Market Titan Correlator"), ""]
    dev: dict[str, Any] = {
        "desk": 3, "item": 18, "kind": KIND_PROFILE, "event": event_id, "event_kind": ev.get("kind"), "token_id": str(market.get("token")),
        "label": label, "registration": REGISTRATION_REL, "release_utc": result.get("T_utc"), "classification": klass,
        "lead_s": market.get("lead_s"), "informative": bool(market.get("informative")), "sufficient": bool(market.get("sufficient")) and bool(result.get("sufficient")),
        "primary": bool((result.get("primary_market") or {}).get("token") == market.get("token")),
        "pm": {k: market.get(k) for k in ("baseline", "final", "dp", "displaced", "t_star_rel_s", "stamps")},
        "hl": {k: hl.get(k) for k in ("coin", "baseline_px", "baseline_age_s", "final_px", "dp_rel_bps", "displaced", "t_star_rel_s", "prints")},
        "bars": dict(bars),
        "measurement": {"first_event_utc": result.get("T0_utc"), "last_event_utc": result.get("window_last_utc"),
                        "baseline_utc": result.get("baseline_utc")},
        "data_gaps": overlapping_gaps(vault, result.get("T0_utc"), result.get("window_last_utc")),
    }
    meta = make_meta("Experiment", title,
                     f"{event_id}: {label} - {klass}" + (f", lead {_f(market.get('lead_s'))} s" if market.get("lead_s") is not None else "") + ".",
                     tags=["experiment", "desk-3", "item-18", "lead-lag", "event-study", "reaction-profile", str(klass), event_id],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "event-study-json", "resource": source, "title": "cross_market.event_study --json", "author": "process:cross_market.event_study"}],
                     dev=dev)
    return Page(page_path(vault, "Experiment", f"reaction_profile_{event_id}__{slug(label)}"), meta, "\n".join(body))


def _profiles(vault: Path) -> list[Page]:
    return sorted((p for p in load_pages(vault) if p.type == "Experiment" and (p.meta.get("dev") or {}).get("kind") == KIND_PROFILE),
                  key=lambda p: (str((p.meta.get("dev") or {}).get("release_utc")), p.path.name))


def panel_status(events: list[dict[str, Any]], *, min_informative: int) -> dict[str, Any]:
    """The pre-registered stopping rules (R125-2 s.8.4) applied to the event sequence, oldest first."""
    informative = [e for e in events if e.get("informative")]
    out: dict[str, Any] = {"events": len(events), "informative_events": len(informative), "min_informative_events": min_informative,
                           "verdict": "insufficient (%d of %d informative events)" % (len(informative), min_informative), "stopping": None}
    classes = [e.get("classification") for e in informative]
    for a, b in zip(classes, classes[1:]):
        if a in TERMINAL_CLASSES and b in TERMINAL_CLASSES:
            out["stopping"] = "rule 1: two consecutive informative events contemporaneous or hyperliquid-leads -> line terminated"
            break
    if len(events) >= 3 and all(e.get("classification") == "uninformative-shock" for e in events[-3:]):
        out["stopping"] = out["stopping"] or "rule 2: three consecutive registered prints uninformative -> line retired 2026-11-01"
    if len(informative) >= min_informative:
        pm = sum(1 for c in classes if c == "polymarket-leads-event")
        out["verdict"] = ("polymarket-leads-event on %d of %d informative events" % (pm, len(informative)))
        out["capital_bar_met"] = pm >= 2
    return out


def compile_panel(vault: Path, *, at: datetime, by: str = GENERATED_BY, min_informative: int = 3) -> Page:
    profiles = _profiles(vault)
    rows = []
    by_event: dict[str, dict[str, Any]] = {}
    for p in profiles:
        d = p.meta.get("dev") or {}
        rows.append(f"| [[{p.path.stem}\\|{d.get('event')}]] | {d.get('label')} | {d.get('classification')} | {_f(d.get('lead_s'))} | "
                    f"{'yes' if d.get('informative') else 'no'} | {'primary' if d.get('primary') else ''} | {(d.get('release_utc') or '')[:10]} |")
        if d.get("primary"):
            by_event[str(d.get("event"))] = {"event": d.get("event"), "classification": d.get("classification"), "informative": bool(d.get("informative")),
                                             "release_utc": d.get("release_utc"), "lead_s": d.get("lead_s")}
    events = sorted(by_event.values(), key=lambda e: str(e.get("release_utc")))
    status = panel_status(events, min_informative=min_informative)
    body = ["# Item 18 Phase 2 panel: event-driven lead-lag", "",
            f"> {status['informative_events']} informative event(s) of {status['min_informative_events']} required · verdict: **{status['verdict']}**"
            + (f" · stopping rule fired: {status['stopping']}" if status.get("stopping") else ""), "",
            "## Profiles", "", "| Event | Market | Class | Lead (s) | Counted | Primary | Print |", "|---|---|---|---|---|---|---|",
            *(rows or ["| (none yet) | | | | | | |"]), "",
            "## Sequence of primary markets", "", "| Print | Event | Class | Lead (s) | Counted |", "|---|---|---|---|---|",
            *([f"| {(e.get('release_utc') or '')[:10]} | {e.get('event')} | {e.get('classification')} | {_f(e.get('lead_s'))} | {'yes' if e.get('informative') else 'no'} |" for e in events]
              or ["| (none yet) | | | | |"]), "",
            "## Stopping rules (pre-registered, R125-2 s.8.4)", "",
            "- non-displacing print: uninformative-shock, logged, not counted",
            "- rule 1: two consecutive informative events contemporaneous or hyperliquid-leads -> the line is terminated",
            "- rule 2: the three registered prints all uninformative -> retired 2026-11-01",
            "- capital bar: polymarket-leads-event on at least 2 of 3 informative events", "",
            "## Related", "", f"- [[{REGISTRATION_STEM}|Phase 2 registration]]",
            link_if_exists(vault, "Regime", "btc_macro_regime", "BTC macro regime (Phase 1 consensus)"),
            "- [[experiments_register|Experiments register]]", ""]
    dev = {"desk": 3, "item": 18, "kind": KIND_PANEL, "registration": REGISTRATION_REL, "profiles": [p.path.stem for p in profiles],
           "events": events, "status": status}
    meta = make_meta("Experiment", "Item 18 Phase 2 panel", f"Event-driven lead-lag panel: {status['verdict']}.",
                     tags=["experiment", "desk-3", "item-18", "lead-lag", "event-study", "panel"], generated_by=by, at=at, status="draft",
                     sources=[{"id": "profiles", "resource": "obsidian_vault/wiki/experiments", "title": "reaction_profile_* pages", "author": by}],
                     dev=dev)
    return Page(page_path(vault, "Experiment", PANEL_STEM), meta, "\n".join(body))


def ingest_event_study(result: dict[str, Any], vault: Path, dev_root: Path, *, source: str, at: datetime | None = None,
                       by: str = GENERATED_BY) -> tuple[list[Page], Page]:
    at = at or now_utc()
    profiles = []
    changed = 0
    for market in result.get("markets") or []:
        page = compile_profile(result, market, vault, source=source, at=at, by=by)
        carry_human_fields(load_page(page.path), page.meta)
        if page_changed(page, vault):
            changed += 1
        write_page(page, vault, now=at)
        profiles.append(page)
    min_inf = int(((result.get("bars") or {}).get("panel_min_informative_events")) or 3)
    panel = compile_panel(vault, at=at, by=by, min_informative=min_inf)
    carry_human_fields(load_page(panel.path), panel.meta)
    if page_changed(panel, vault):
        changed += 1
    write_page(panel, vault, now=at)
    if changed:
        write_register(vault, "Experiment", at=at, by=by)
        write_index(vault, load_pages(vault))
        ev = (result.get("event") or {}).get("id")
        append_log(vault, "Ingest", f"event study for `{ev}`: {len(profiles)} reaction profile(s) ({result.get('class')}, lead {result.get('lead_s')} s, "
                   f"{'counted' if result.get('informative') else 'not counted'}); [[{PANEL_STEM}]] {panel.meta['dev']['status']['verdict']}.", when=at)
    return profiles, panel


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.event_study", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--result", type=Path, required=True, help="cross_market.event_study --json output")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    if not args.result.is_file():
        print(f"[REFUSE] result file not found: {args.result} (exit 3)", file=out)
        return 3
    result = json.loads(args.result.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("protocol") != "event_study" or "markets" not in result:
        print("[REFUSE] not an event_study result JSON (exit 3)", file=out)
        return 3
    profiles, panel = ingest_event_study(result, args.vault, args.dev_root, source=rel_to(args.result, args.dev_root), at=at_from(args))
    for p in profiles:
        print(f"[WRITE] {p.path.relative_to(args.vault).as_posix()}  class={p.meta['dev']['classification']}  counted={p.meta['dev']['informative']}", file=out)
    print(f"[WRITE] {panel.path.relative_to(args.vault).as_posix()}  {panel.meta['dev']['status']['verdict']}", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
