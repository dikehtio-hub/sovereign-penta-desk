"""Lead-lag verdict -> Experiment page + Regime history.

    python -m cross_market.lead_lag --coin BTC --family macro --json > verdict.json
    python -m knowledge.ingest.lead_lag --result verdict.json --tier 1 [--at ISO]

Consumes the JSON that cross_market.lead_lag prints: events, price_points,
sufficient, reason, best_lag_minutes, correlation, n, interpretation, curve[],
latency_minutes, family, subfamily, subfamily_from. Writes:

  wiki/experiments/lead_lag_<tier>_<scope>_<stamp>.md   the verdict, as measured
  wiki/regimes/btc_macro_regime.md                       one history row per verdict,
                                                          current class per tier

CLASSIFICATION (fixed vocabulary, WIKI_SCHEMA.md s.7):
  insufficient       the module could not score (events or points under the bar)
  no-lead            |corr| at the peak below min_abs_corr
  contemporaneous    peak |lag| inside the poll interval: repricing, not a lead
  polymarket-leads   peak lag > 0 above the bar
  hyperliquid-leads  peak lag < 0 above the bar
  coincident         peak lag == 0 above the bar, no latency rule in force

Where Tier 2 and Tier 2b disagree the disagreement is a finding, not a tie
to break: both rows stay in the history and the Regime page says so.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc, page_path,
                     write_index, write_page)
from . import add_common_args, at_from, guard, item_link, rel_to, page_changed
from ..registers import write_register

REGIME_FILE = "btc_macro_regime"
DEFAULT_MIN_ABS_CORR = 0.2
# Ruling R102-2: the exporter serialises its own run result here whenever it refreshes
# Cross_Market_Titans.md, so the dashboard and the wiki describe the SAME run rather than two
# runs seconds apart. `--result` still accepts any file (a `lead_lag --json` capture, a fixture).
DEFAULT_RESULT = Path("cross_market") / "data" / "lead_lag_latest_verdict.json"
CLASSES = ("insufficient", "no-lead", "contemporaneous", "polymarket-leads", "hyperliquid-leads", "coincident")


def classify(result: dict[str, Any], min_abs_corr: float = DEFAULT_MIN_ABS_CORR) -> str:
    if not result.get("sufficient"):
        return "insufficient"
    corr = result.get("correlation")
    tau = result.get("best_lag_minutes")
    if corr is None or tau is None:
        return "insufficient"
    if abs(float(corr)) < min_abs_corr:
        return "no-lead"
    latency = float(result.get("latency_minutes") or 0.0)
    if latency > 0 and abs(int(tau)) <= latency:
        return "contemporaneous"
    if int(tau) > 0:
        return "polymarket-leads"
    if int(tau) < 0:
        return "hyperliquid-leads"
    return "coincident"


def scope_of(result: dict[str, Any]) -> str:
    fam = str(result.get("family") or "all")
    sub = result.get("subfamily")
    return f"{fam}_{sub}" if sub else fam


def compile_verdict(result: dict[str, Any], vault: Path, dev_root: Path, *, tier: str, source: str,
                    at: datetime | None = None, by: str = GENERATED_BY,
                    min_abs_corr: float = DEFAULT_MIN_ABS_CORR) -> Page:
    at = at or now_utc()
    cls = classify(result, min_abs_corr)
    scope = scope_of(result)
    stamp = at.strftime("%Y%m%dT%H%MZ")
    title = f"Lead-lag verdict: Tier {tier}, {scope.replace('_', ' / ')}, {at.strftime('%Y-%m-%d %H:%M')}Z"
    corr = result.get("correlation")
    tau = result.get("best_lag_minutes")
    body = [f"# {title}", "", f"> Class: **{cls}** · {result.get('interpretation') or result.get('reason') or ''}".rstrip(), "",
            "## Verdict", "", "| Field | Value |", "|---|---|",
            f"| tier | {tier} |", f"| family / subfamily | {result.get('family')} / {result.get('subfamily') or '-'} |",
            f"| membership | {result.get('subfamily_from') or 'label'} |",
            f"| sufficient | {result.get('sufficient')} |",
            f"| probability shifts (events) | {result.get('events')} |",
            f"| price points | {result.get('price_points')} |",
            f"| best lag (min, + = Polymarket leads) | {_lag(tau)} |",
            f"| correlation at peak | {_corr(corr)} |",
            f"| n at peak | {result.get('n')} |",
            f"| latency rule (min) | {result.get('latency_minutes')} |",
            f"| bar (min abs corr) | {min_abs_corr} |",
            f"| classification | **{cls}** |", ""]
    if result.get("reason"):
        body += ["## Reason", "", str(result["reason"]), ""]
    curve = [c for c in (result.get("curve") or []) if isinstance(c, dict) and c.get("correlation") is not None]
    if curve:
        top = sorted(curve, key=lambda c: -abs(float(c["correlation"])))[:5]
        body += ["## Strongest lags", "", "| Lag (min) | Corr | n |", "|---|---|---|"]
        body += [f"| {int(c['lag_minutes']):+d} | {float(c['correlation']):+.3f} | {c.get('n')} |" for c in top]
        body.append("")
    body += ["## Related", "", f"- [[{REGIME_FILE}|BTC macro regime]]",
             "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]",
             item_link(vault, "Item_18_Cross_Market_Titan_Correlator_Macro_Crypto", "Item 18: Cross-Market Titan Correlator"), ""]
    # B14: tests_run = how many verdicts this tier/scope has now been evaluated for (multiple-testing counter).
    # Round 121: the page being written is excluded, so re-ingesting the same verdict does not inflate it.
    own_stem = f"lead_lag_tier{tier}_{scope}_{stamp}"
    prior = sum(1 for p in load_pages(vault) if p.type == "Experiment" and (p.meta.get("dev") or {}).get("kind") == "lead_lag_verdict"
                and str((p.meta.get("dev") or {}).get("tier")) == str(tier) and scope_of(p.meta.get("dev") or {}) == scope
                and p.path.stem != own_stem)
    dev: dict[str, Any] = {
        "desk": 3, "item": 18, "kind": "lead_lag_verdict", "tier": str(tier),
        "family": result.get("family"), "subfamily": result.get("subfamily"),
        "membership": result.get("subfamily_from") or "label",
        "sufficient": bool(result.get("sufficient")), "best_lag_minutes": tau, "correlation": corr,
        "n": result.get("n"), "events": result.get("events"), "price_points": result.get("price_points"),
        "latency_minutes": result.get("latency_minutes"), "min_abs_corr": min_abs_corr, "classification": cls,
        "tests_run": prior + 1,
    }
    meta = make_meta("Experiment", title,
                     f"Tier {tier} lead-lag verdict for {scope.replace('_', ' / ')}: {cls}.",
                     tags=["experiment", "desk-3", "item-18", "lead-lag", "verdict", f"tier-{tier}", cls],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "verdict-json", "resource": source, "title": "cross_market.lead_lag --json output",
                               "author": "process:cross_market.lead_lag"}],
                     dev=dev)
    return Page(page_path(vault, "Experiment", f"lead_lag_tier{tier}_{scope}_{stamp}"), meta, "\n".join(body))


def _corr(v) -> str:
    return "-" if v is None else f"{float(v):+.3f}"


def _lag(v) -> str:
    return "-" if v is None else str(v)


def current_state(history: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per (tier, scope): the latest verdict and the trailing-3 consensus (Round 97 ruling A3).
    consensus is the class when the last three runs agree, `mixed` when they do not, and
    `insufficient-history` with fewer than three runs."""
    keyed: dict[str, list[dict[str, Any]]] = {}
    for r in history:
        keyed.setdefault(f"tier {r.get('tier')} {r.get('scope')}", []).append(r)
    out: dict[str, dict[str, Any]] = {}
    for key, rows in keyed.items():
        last3 = rows[-3:]
        latest = str(last3[-1].get("class"))
        if len(last3) < 3:
            consensus = "insufficient-history"
        elif len({str(r.get("class")) for r in last3}) == 1:
            consensus = latest
        else:
            consensus = "mixed"
        out[key] = {"latest_verdict": latest, "regime_consensus_3": consensus, "runs": len(rows)}
    return out


def _render_regime(history: list[dict[str, Any]], vault: Path) -> str:
    latest: dict[str, dict[str, Any]] = {}
    for row in history:  # history is chronological; the last row per (tier, scope) wins
        latest[f"{row.get('tier')}|{row.get('scope')}"] = row
    state = current_state(history)
    lines = ["# BTC macro regime", "",
             "> One row per lead-lag verdict. The class vocabulary is fixed in WIKI_SCHEMA.md s.7; where Tier 2 and",
             "> Tier 2b disagree for the same scope, that disagreement is the finding (the dual-tagged markets carry it).",
             "> `Consensus (3)` is the class only when the last three runs of that tier and scope agree.", "",
             "## Current, per tier and scope", "",
             "| Tier | Scope | Membership | Latest | Consensus (3) | Lag (min) | Corr | n | As of |", "|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(latest):
        r = latest[key]
        st = state.get(f"tier {r.get('tier')} {r.get('scope')}", {})
        lines.append(f"| {r.get('tier')} | {r.get('scope')} | {r.get('membership')} | **{r.get('class')}** | {st.get('regime_consensus_3', '-')} | "
                     f"{_lag(r.get('lag'))} | {_corr(r.get('corr'))} | {r.get('n')} | {r.get('at')} |")
    lines += ["", "## Disagreements", ""]
    by_scope: dict[str, dict[str, str]] = {}
    for key, r in latest.items():
        by_scope.setdefault(str(r.get("scope")), {})[str(r.get("tier"))] = str(r.get("class"))
    dis = [(s, t) for s, t in by_scope.items() if len(set(t.values())) > 1]
    lines += [f"- **{s}**: " + ", ".join(f"Tier {k} says {v}" for k, v in sorted(t.items())) for s, t in dis] or ["- none"]
    lines += ["", "## History", "", "| At | Tier | Scope | Membership | Class | Lag | Corr | n | Verdict page |", "|---|---|---|---|---|---|---|---|---|"]
    for r in history:
        lines.append(f"| {r.get('at')} | {r.get('tier')} | {r.get('scope')} | {r.get('membership')} | {r.get('class')} | "
                     f"{_lag(r.get('lag'))} | {_corr(r.get('corr'))} | {r.get('n')} | [[{r.get('page')}]] |")
    lines += ["", "## Related", "", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]",
              item_link(vault, "Item_18_Cross_Market_Titan_Correlator_Macro_Crypto", "Item 18: Cross-Market Titan Correlator"), ""]
    return "\n".join(lines)


def update_regime(vault: Path, verdict: Page, *, at: datetime, by: str = GENERATED_BY) -> Page:
    path = page_path(vault, "Regime", REGIME_FILE)
    existing = load_page(path)
    history: list[dict[str, Any]] = []
    if existing is not None:
        dev = existing.meta.get("dev") or {}
        history = [dict(r) for r in dev.get("history", []) if isinstance(r, dict)]
    d = verdict.meta["dev"]
    row = {"at": iso(at), "tier": d["tier"], "scope": scope_of(d), "membership": d["membership"],
           "class": d["classification"], "lag": d["best_lag_minutes"], "corr": d["correlation"], "n": d["n"],
           "page": verdict.path.stem}
    # Round 121 (R120-1.C): the verdict PAGE is the unit of observation. Re-ingesting the same verdict (an
    # artifact that moved, a fixed adapter) replaces its row in place; it must not append a second one.
    idx = next((i for i, r in enumerate(history) if r.get("page") == row["page"]), None)
    if idx is None:
        history.append(row)
    else:
        history[idx] = row
    current = current_state(history)
    meta = make_meta("Regime", "BTC macro regime",
                     "Rolling classification of the Polymarket macro / Hyperliquid BTC lead-lag verdicts, per tier and scope, with the full history.",
                     tags=["regime", "desk-3", "item-18", "lead-lag"], generated_by=by, at=at, status="draft",
                     sources=[{"id": "verdicts", "resource": "obsidian_vault/wiki/experiments",
                               "title": "lead-lag verdict pages", "author": by}],
                     dev={"desk": 3, "item": 18, "current": current, "classes": list(CLASSES), "history": history})
    carry_human_fields(existing, meta)  # Ruling 99-2
    return Page(path, meta, _render_regime(history, vault))


REGISTRATION_FOR_TIER = {"2": "lead_lag_tier2_meta", "2b": "lead_lag_tier2b_meta"}  # Tier 1 has no meta file (the maiden run)


def annotate_registration(vault: Path, tier: str, *, at: datetime) -> Page | None:
    """Ruling 100-e: write the running verdict count back onto the registration PAGE (never the raw meta file)."""
    stem = REGISTRATION_FOR_TIER.get(str(tier))
    if not stem:
        return None
    reg = load_page(page_path(vault, "Experiment", stem))
    if reg is None:
        return None
    from .experiments import lead_lag_verdict_count      # one definition of the counter (Round 121)
    reg.meta.setdefault("dev", {})["tests_run"] = lead_lag_verdict_count(vault, str(tier))
    write_page(reg, vault, now=at)
    return reg


def ingest_verdict(result: dict[str, Any], vault: Path, dev_root: Path, *, tier: str, source: str,
                   at: datetime | None = None, by: str = GENERATED_BY) -> tuple[Page, Page]:
    at = at or now_utc()
    verdict = compile_verdict(result, vault, dev_root, tier=tier, source=source, at=at, by=by)
    changed = page_changed(verdict, vault)                 # Round 121 (R104-3): log only what moved
    write_page(verdict, vault, now=at)
    annotate_registration(vault, tier, at=at)
    regime = update_regime(vault, verdict, at=at, by=by)
    write_page(regime, vault, now=at)
    write_register(vault, "Experiment", at=at, by=by)
    write_index(vault, load_pages(vault))
    if changed:
        append_log(vault, "Ingest", f"lead-lag Tier {tier} verdict ({scope_of(result)}): **{verdict.meta['dev']['classification']}** -> "
                   f"[[{verdict.path.stem}]]; [[{REGIME_FILE}]] history now {len(regime.meta['dev']['history'])} row(s).", when=at)
    return verdict, regime


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.lead_lag", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--result", type=Path, default=None,
                    help=f"file holding a lead_lag verdict dict; default <dev-root>/{DEFAULT_RESULT.as_posix()}, "
                         "which the exporter writes whenever it refreshes Cross_Market_Titans.md (Ruling R102-2)")
    ap.add_argument("--tier", required=True, choices=["1", "2", "2b"])
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    result_path = args.result or (args.dev_root / DEFAULT_RESULT)
    if not result_path.is_file():
        hint = ("" if args.result else
                " - the exporter writes it on each refresh (Ruling R102-2); pass --result to use another file")
        print(f"[REFUSE] result file not found: {result_path}{hint} (exit 3)", file=out)
        return 3
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or "sufficient" not in result:
        print("[REFUSE] not a lead_lag verdict JSON (no `sufficient` key) (exit 3)", file=out)
        return 3
    verdict, regime = ingest_verdict(result, args.vault, args.dev_root, tier=args.tier,
                                     source=rel_to(result_path, args.dev_root), at=at_from(args))
    print(f"[WRITE] {verdict.path.relative_to(args.vault).as_posix()}  class={verdict.meta['dev']['classification']}", file=out)
    print(f"[WRITE] {regime.path.relative_to(args.vault).as_posix()}  history={len(regime.meta['dev']['history'])}", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
