"""Survival curve -> Reaction Profile pages, an Event page and the latency-decay Concept.

    python -m cross_market.latency_sniper --survival-curve --event event.json \
        --rules cross_market/experiments/fomc_2026-09-16.rules.json \
        --books cross_market/data/clob_books/fomc_2026-09-16 --json > curve.json
    python -m knowledge.ingest.clob --result curve.json --event fomc_2026-09-16 [--at ISO]

Consumes the JSON latency_sniper.survival_curve() prints: anchor, release_utc,
anchor_minus_release_s, event{kind,payload,confidence}, step_seconds, stamps,
markets[{market, rule, outcome, side, stamps, neg_risk, deferred, series[...],
summary{baseline_notional, first_change_s, half_s, tenth_s, gone_s,
max_post_notional, notional_seconds, ...}}]. Writes:

  wiki/profiles/<event>__<rule-slug>.md   one Reaction Profile per market
  wiki/events/<event>.md                  the Event, linking its profiles
  wiki/concepts/latency_decay.md          one history row per (event, market):
                                          the cross-event table the sniper thesis needs

The full per-second series is NOT copied into the page (420 rows per market);
the page keeps the five summary numbers, a checkpoint table, and the source
path of the JSON so the series stays in the raw layer.
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
from ..pages import Page, append_log, iso, load_page, load_pages, make_meta, now_utc, page_path, write_index, write_page
from . import add_common_args, at_from, fmt_s, fmt_usd, guard, rel_to

CONCEPT_FILE = "latency_decay"
CHECKPOINTS_S = (-2, -1, 0, 1, 2, 3, 5, 10, 20, 30, 60, 120, 180, 300)


def slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return s[:60] or "market"


def _nearest(series: list[dict[str, Any]], target: float) -> dict[str, Any] | None:
    best, best_d = None, None
    for r in series:
        d = abs(float(r["delta_s"]) - target)
        if best_d is None or d < best_d:
            best, best_d = r, d
    return best if best is not None and best_d is not None and best_d <= 1.0 else None


def compile_profile(market: dict[str, Any], result: dict[str, Any], event_id: str, vault: Path, *, source: str,
                    at: datetime, by: str = GENERATED_BY) -> Page:
    rule = str(market.get("rule") or market.get("market"))
    sm = market.get("summary") or {}
    series = [r for r in (market.get("series") or []) if isinstance(r, dict)]
    title = f"Reaction profile: {rule}"
    body = [f"# {title}", "", f"> Event [[{event_id}]] · outcome {market.get('outcome')} ({market.get('side')}) · "
            f"neg_risk {market.get('neg_risk')} · {market.get('stamps')} stamp(s) at {result.get('step_seconds')} s", ""]
    if market.get("deferred"):
        body += ["## Deferred", "", str(market["deferred"]), ""]
    if sm:
        body += ["## Summary (uncapped depth walk, seconds from the event's observed_at)", "",
                 "| Measure | Value |", "|---|---|",
                 f"| pre-print baseline fillable notional | {fmt_usd(sm.get('baseline_notional'))} |",
                 f"| baseline stamp at | {fmt_s(sm.get('baseline_delta_s'))} |",
                 f"| first post-print change | {fmt_s(sm.get('first_change_s'))} |",
                 f"| half of baseline gone by | {fmt_s(sm.get('half_s'))} |",
                 f"| a tenth of baseline left by | {fmt_s(sm.get('tenth_s'))} |",
                 f"| nothing clears from | {fmt_s(sm.get('gone_s'))} |",
                 f"| max post-print fillable | {fmt_usd(sm.get('max_post_notional'))} |",
                 f"| post-print dollar-seconds | {fmt_usd(sm.get('notional_seconds'))}·s |",
                 f"| stamps pre / post | {sm.get('pre_print_stamps')} / {sm.get('post_print_stamps')} |", ""]
    if series:
        body += ["## Checkpoints", "", "| t (s) | fillable notional | shares | VWAP | clearing levels | changed |", "|---|---|---|---|---|---|"]
        seen = set()
        for cp in CHECKPOINTS_S:
            r = _nearest(series, cp)
            if r is None or r["delta_s"] in seen:
                continue
            seen.add(r["delta_s"])
            body.append(f"| {float(r['delta_s']):+g} | {fmt_usd(r.get('fillable_notional'))} | {r.get('fillable_shares')} | "
                        f"{r.get('vwap')} | {r.get('clearing_levels')} | {'yes' if r.get('changed') else ''} |")
        body.append("")
    body += ["## Related", "", f"- [[{event_id}|Event {event_id}]]", f"- [[{CONCEPT_FILE}|Latency decay across events]]",
             "- [[Ruling_R02|R2 - record the CLOB around a scheduled print]]", ""]
    dev: dict[str, Any] = {
        "desk": 3, "item": 12, "kind": "reaction_profile", "event": event_id, "token_id": str(market.get("market")),
        "rule": rule, "outcome": market.get("outcome"), "side": market.get("side"), "neg_risk": market.get("neg_risk"),
        "deferred": market.get("deferred"), "stamps": market.get("stamps"), "step_seconds": result.get("step_seconds"),
        "anchor": result.get("anchor"), "release_utc": result.get("release_utc"),
        "anchor_minus_release_s": result.get("anchor_minus_release_s"),
        "summary": {k: sm.get(k) for k in ("baseline_notional", "first_change_s", "half_s", "tenth_s", "gone_s",
                                             "max_post_notional", "notional_seconds", "pre_print_stamps", "post_print_stamps")},
    }
    meta = make_meta("Reaction Profile", title,
                     f"{event_id}: {rule} - half of the resting depth survived {fmt_s(sm.get('half_s'))} after the print; "
                     f"{fmt_usd(sm.get('notional_seconds'))} dollar-seconds post-print." if sm else f"{event_id}: {rule} (no series).",
                     tags=["reaction-profile", "desk-3", "item-12", event_id], generated_by=by, at=at, status="draft",
                     sources=[{"id": "survival-json", "resource": source, "title": "latency_sniper --survival-curve --json",
                               "author": "process:cross_market.latency_sniper"}],
                     dev=dev)
    return Page(page_path(vault, "Reaction Profile", f"{event_id}__{slug(rule)}"), meta, "\n".join(body))


def compile_event(result: dict[str, Any], event_id: str, profiles: list[Page], vault: Path, *, source: str,
                  at: datetime, by: str = GENERATED_BY) -> Page:
    ev = result.get("event") or {}
    path = page_path(vault, "Event", event_id)
    existing = load_page(path)
    prior = existing.meta.get("dev", {}).get("profiles", []) if existing else []
    names = sorted(set(prior) | {p.path.stem for p in profiles})
    body = [f"# Event: {event_id}", "", f"> kind `{ev.get('kind')}` · payload `{json.dumps(ev.get('payload'))}` · confidence {ev.get('confidence')}", "",
            "## Timing", "", f"- observed_at (anchor): `{result.get('anchor')}`", f"- release_utc: `{result.get('release_utc')}`",
            f"- anchor minus release: {result.get('anchor_minus_release_s')} s", f"- stamps replayed: {result.get('stamps')} at {result.get('step_seconds')} s", "",
            "## Reaction profiles", "", *[f"- [[{n}]]" for n in names], "",
            "## Related", "", f"- [[{CONCEPT_FILE}|Latency decay across events]]", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]",
            "- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]", ""]
    dev = {"desk": 3, "item": 12, "kind": str(ev.get("kind")), "payload": ev.get("payload"), "confidence": ev.get("confidence"),
           "anchor": result.get("anchor"), "release_utc": result.get("release_utc"), "profiles": names}
    meta = make_meta("Event", f"Event: {event_id}", f"{ev.get('kind')} event {event_id}: {len(names)} reaction profile(s) recorded.",
                     tags=["event", "desk-3", "item-12", str(ev.get("kind"))], generated_by=by, at=at, status="draft",
                     sources=[{"id": "survival-json", "resource": source, "title": "latency_sniper --survival-curve --json",
                               "author": "process:cross_market.latency_sniper"}],
                     dev=dev)
    return Page(path, meta, "\n".join(body))


def _render_concept(history: list[dict[str, Any]]) -> str:
    lines = ["# Latency decay across events", "",
             "> How many seconds resting Polymarket depth survives after a scheduled print, event by event. This is the",
             "> table the roadmap's \"10-50 % per event\" claim has to be checked against; each row is one recorded market.", "",
             "| Event | Market | Outcome | Baseline | First change | Half | Tenth | Gone | $-seconds | Profile |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in history:
        lines.append(f"| {r.get('event')} | {r.get('rule')} | {r.get('outcome')} | {fmt_usd(r.get('baseline_notional'))} | "
                     f"{fmt_s(r.get('first_change_s'))} | {fmt_s(r.get('half_s'))} | {fmt_s(r.get('tenth_s'))} | {fmt_s(r.get('gone_s'))} | "
                     f"{fmt_usd(r.get('notional_seconds'))} | [[{r.get('page')}]] |")
    lines += ["", "## Reading", "",
              "- `Half` and `Tenth` are the numbers that matter: the seconds a sniper has before the book is half gone and a tenth left.",
              "- `$-seconds` integrates fillable notional over the post-print window: the size of the opportunity times how long it lasted.",
              "- A deferred row (neg_risk NO side, Ruling R4) carries no numbers on purpose.", "",
              "## Related", "", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]",
              "- [[Item_12_Polymarket_Breaking_News_Oracle_Latency_Sniper|Item 12: Polymarket Breaking News & Oracle Latency Sniper]]", ""]
    return "\n".join(lines)


def update_concept(vault: Path, profiles: list[Page], event_id: str, *, at: datetime, by: str = GENERATED_BY) -> Page:
    path = page_path(vault, "Concept", CONCEPT_FILE)
    existing = load_page(path)
    history: list[dict[str, Any]] = []
    if existing is not None:
        history = [dict(r) for r in (existing.meta.get("dev") or {}).get("history", []) if isinstance(r, dict)]
    history = [r for r in history if r.get("event") != event_id]  # re-ingesting an event replaces its rows
    for p in profiles:
        d = p.meta["dev"]
        row = {"event": event_id, "rule": d["rule"], "token_id": d["token_id"], "outcome": d["outcome"], "page": p.path.stem}
        row.update({k: v for k, v in (d.get("summary") or {}).items()})
        history.append(row)
    meta = make_meta("Concept", "Latency decay across events",
                     "Seconds of resting depth that survive a scheduled print, per recorded event and market; the cross-event table for the sniper thesis.",
                     tags=["concept", "desk-3", "item-12", "latency-decay"], generated_by=by, at=at, status="draft",
                     sources=[{"id": "profiles", "resource": "obsidian_vault/wiki/profiles", "title": "Reaction Profile pages", "author": by}],
                     dev={"desk": 3, "item": 12, "history": history})
    return Page(path, meta, _render_concept(history))


def ingest_survival(result: dict[str, Any], vault: Path, dev_root: Path, *, event_id: str, source: str,
                    at: datetime | None = None, by: str = GENERATED_BY) -> tuple[list[Page], Page, Page]:
    at = at or now_utc()
    markets = [m for m in (result.get("markets") or []) if isinstance(m, dict)]
    profiles = [compile_profile(m, result, event_id, vault, source=source, at=at, by=by) for m in markets]
    for p in profiles:
        write_page(p, vault, now=at)
    event = compile_event(result, event_id, profiles, vault, source=source, at=at, by=by)
    write_page(event, vault, now=at)
    concept = update_concept(vault, profiles, event_id, at=at, by=by)
    write_page(concept, vault, now=at)
    write_index(vault, load_pages(vault))
    append_log(vault, "Ingest", f"survival curve for [[{event_id}]]: {len(profiles)} reaction profile(s); "
               f"[[{CONCEPT_FILE}]] now {len(concept.meta['dev']['history'])} row(s).", when=at)
    return profiles, event, concept


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.clob", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--result", type=Path, required=True, help="file holding `latency_sniper --survival-curve --json` output")
    ap.add_argument("--event", required=True, help="event id, e.g. fomc_2026-09-16 (becomes the Event page name)")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    if not args.result.is_file():
        print(f"[REFUSE] result file not found: {args.result} (exit 3)", file=out)
        return 3
    result = json.loads(args.result.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or "markets" not in result:
        print("[REFUSE] not a survival-curve JSON (no `markets` key) (exit 3)", file=out)
        return 3
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", args.event):
        print("[REFUSE] --event must be letters, digits, _ or - (exit 3)", file=out)
        return 3
    profiles, event, concept = ingest_survival(result, args.vault, args.dev_root, event_id=args.event,
                                               source=rel_to(args.result, args.dev_root), at=at_from(args))
    for p in profiles:
        print(f"[WRITE] {p.path.relative_to(args.vault).as_posix()}", file=out)
    print(f"[WRITE] {event.path.relative_to(args.vault).as_posix()}", file=out)
    print(f"[WRITE] {concept.path.relative_to(args.vault).as_posix()}  rows={len(concept.meta['dev']['history'])}", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
