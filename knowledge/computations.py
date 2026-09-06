"""Attested Computation pages: the dashboards' shell twins and the knowledge CLIs (Round 98, B6).

    python -m knowledge.computations [--force] [--at ISO]

OKF v0.2 defines the type for exactly what a "Shell twin" line already is: a
command an operator can run to reproduce a card. `runtime` is the execution
environment, `computation` the command, `executor.receipt` the fields the
`--json` form returns, `attester` the test module that pins the behaviour.
Per Ratification R95-C this is DECLARATIVE: nothing here runs a computation or
verifies a receipt; lint C1 only checks that the module and the test file
still exist (`dev.requires_files`). Only two dashboards print a shell twin
today; the others are a finding for Phase 4 (F1).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import DEV_ROOT, EXIT_HALT, EXIT_OK, GENERATED_BY, VAULT, halted
from .frontmatter import parse_iso8601
from .pages import Page, append_log, carry_human_fields, load_page, load_pages, make_meta, now_utc, page_path, write_index, write_page
from .registers import update_register

KTEST = "knowledge/tests/test_knowledge.py"
K_EXIT = {"0": "ok", "1": "findings", "3": "refused (HALT.flag, missing input)"}


@dataclass(frozen=True)
class Computation:
    stem: str
    title: str
    command: str
    module: str
    test: str
    receipt: tuple[str, ...]
    description: str
    kind: str                       # shell_twin | knowledge_cli
    exit_codes: dict[str, str]
    dashboard: str | None = None
    desk: int | None = None
    item: int | None = None


COMPUTATIONS: tuple[Computation, ...] = (
    Computation("lead_lag_check_data", "lead_lag --check-data (Item 18 readiness gate)",
                "python -m cross_market.lead_lag --check-data [--json]",
                "cross_market/lead_lag.py", "cross_market/tests/test_lead_lag.py",
                ("ready", "points", "points_total", "span_hours", "segment_start", "newest", "reasons", "eta", "checked_at"),
                "The Item 18 data-readiness sentinel on Cross_Market_Titans.md: is the stamped macro series long and dense enough for the maiden run.",
                "shell_twin", {"0": "ready", "3": "not ready"}, dashboard="Cross_Market_Titans.md", desk=3, item=18),
    Computation("risk_simulator_20000", "risk_simulator --iterations 20000 --json (Item 19)",
                "python -m cross_market.risk_simulator --iterations 20000 --json",
                "cross_market/risk_simulator.py", "cross_market/tests/test_risk_simulator.py",
                ("iterations", "horizon_days", "short_horizon_days", "seed", "start_equity", "ruin_fraction", "ruin", "max_drawdown"),
                "The multi-desk Monte Carlo behind Risk_Sentinel.md: ruin probabilities and drawdown VaR over the shared bankroll.",
                "shell_twin", {"0": "ok", "3": "HALT.flag"}, dashboard="Risk_Sentinel.md", desk=3, item=19),
    Computation("knowledge_seed", "knowledge.seed", "python -m knowledge.seed [--force] [--dry-run] [--at ISO]",
                "knowledge/seed.py", KTEST, ("written", "skipped", "index", "log"),
                "Compiles Desk, Item and Ruling pages from the Top 20 registry; skips existing pages unless --force.", "knowledge_cli", K_EXIT),
    Computation("knowledge_lint", "knowledge.lint", "python -m knowledge.lint [--drops DIR] [--json] [--fix-safe]",
                "knowledge/lint.py", KTEST, ("summary", "findings"),
                "L1-L5 structural checks and C1/C2/C3/C5; writes nothing unless --fix-safe (index, log, deprecate a gone Market).", "knowledge_cli", K_EXIT),
    Computation("knowledge_raw_manifest", "knowledge.raw_manifest", "python -m knowledge.raw_manifest [--dry-run]",
                "knowledge/raw_manifest.py", KTEST, ("streams",),
                "raw/index.md: every federated raw stream in the OKF index format.", "knowledge_cli", K_EXIT),
    Computation("knowledge_computations", "knowledge.computations", "python -m knowledge.computations [--force] [--at ISO]",
                "knowledge/computations.py", KTEST, ("written", "skipped"),
                "This page's own writer: the Attested Computation catalogue.", "knowledge_cli", K_EXIT),
    Computation("knowledge_ingest_experiments", "knowledge.ingest.experiments", "python -m knowledge.ingest.experiments [--dir DIR ...] [--force]",
                "knowledge/ingest/experiments.py", KTEST, ("written", "skipped", "ignored"),
                "Pre-registrations and archived controls -> Experiment pages with json_path-guarded bars.", "knowledge_cli", K_EXIT),
    Computation("knowledge_ingest_lead_lag", "knowledge.ingest.lead_lag", "python -m knowledge.ingest.lead_lag --result verdict.json --tier 1|2|2b",
                "knowledge/ingest/lead_lag.py", KTEST, ("classification", "history"),
                "A lead_lag --json verdict -> Experiment page + Regime history row (latest_verdict, regime_consensus_3).", "knowledge_cli", K_EXIT),
    Computation("knowledge_ingest_clob", "knowledge.ingest.clob", "python -m knowledge.ingest.clob --result curve.json --event EVENT",
                "knowledge/ingest/clob.py", KTEST, ("profiles", "event", "rows"),
                "A survival-curve --json -> Reaction Profile pages, the Event page, the latency-decay table.", "knowledge_cli", K_EXIT),
    Computation("knowledge_ingest_rulings", "knowledge.ingest.rulings", "python -m knowledge.ingest.rulings [--agents FILE] [--force]",
                "knowledge/ingest/rulings.py", KTEST, ("found", "written", "skipped"),
                "Directive / Ratification / Ruling N-N citations in AGENTS.md -> draft Ruling pages.", "knowledge_cli", K_EXIT),
    Computation("knowledge_ingest_calendar", "knowledge.ingest.calendar", "python -m knowledge.ingest.calendar [--dir DIR] [--force]",
                "knowledge/ingest/calendar.py", KTEST, ("written", "skipped"),
                "Committed calendar YAML (FOMC statements, estimated-tax deadlines) -> Event pages with windows.", "knowledge_cli", K_EXIT),
    Computation("knowledge_ingest_markets", "knowledge.ingest.markets", "python -m knowledge.ingest.markets [--drops DIR] [--family F ...] [--force]",
                "knowledge/ingest/markets.py", KTEST, ("written", "skipped"),
                "Tokens from rules, Experiment pages and the newest macro drop -> Market pages for lint C2.", "knowledge_cli", K_EXIT),
    Computation("knowledge_ingest_entities", "knowledge.ingest.entities", "python -m knowledge.ingest.entities [--limit-whales 100] [--limit-titans 100]",
                "knowledge/ingest/entities.py", KTEST, ("counts", "created", "updated"),
                "CRM seeds from the titan cache and three databases (mode=ro): titans, whales, sharps, sportsbooks; judgement kept, evidence appended.",
                "knowledge_cli", K_EXIT),
    Computation("knowledge_ratify", "knowledge.ratify", "python -m knowledge.ratify --type T [--tag TAG] --ruling N-N [--by ACTOR] [--dry-run]",
                "knowledge/ratify.py", KTEST, ("selected", "ratified", "already"),
                "Records an Antigravity ratification: appends `verified` and sets status on the selected pages; idempotent.", "knowledge_cli", K_EXIT),
    Computation("knowledge_journal", "knowledge.journal", "python -m knowledge.journal [--date D] [--create] | --predict ... | --score",
                "knowledge/journal.py", KTEST, ("receipts", "predictions_n", "debrief", "scored", "pending"),
                "The trading-day journal (paper executions, debrief) and the calibration ledger (predictions Brier-scored against Event payloads).",
                "knowledge_cli", K_EXIT),
    Computation("knowledge_views", "knowledge.views", "python -m knowledge.views [--force] [--dry-run]",
                "knowledge/views.py", KTEST, ("written", "skipped"),
                "Obsidian Bases views (wiki/_views/*.base) and human page templates (wiki/_templates/*.md) with OKF-valid frontmatter.",
                "knowledge_cli", K_EXIT),
    Computation("knowledge_ingest_theses", "knowledge.ingest.theses", "python -m knowledge.ingest.theses [--root DIR ...] [--force]",
                "knowledge/ingest/theses.py", KTEST, ("scanned", "written", "skipped"),
                "Titled docstring sections of the desk modules -> Concept pages, each heading pinned with dev:asserts (lint C1).",
                "knowledge_cli", K_EXIT),
)


def build_page(c: Computation, vault: Path, dev_root: Path, at: datetime, by: str = GENERATED_BY) -> Page:
    requires = [p for p in (c.module, c.test) if (dev_root / p).is_file()]
    body = [f"# {c.title}", "", f"> {c.description}", "",
            "# Computation", "", "```", c.command, "```", "",
            "## Receipt (the `--json` fields)", "", *[f"- `{k}`" for k in c.receipt], "",
            "## Exit codes", "", *[f"- `{k}`: {v}" for k, v in c.exit_codes.items()], ""]
    if c.dashboard:
        body += ["## Dashboard", "", f"Printed as the \"Shell twin\" on `{c.dashboard}` (exporter-owned).", ""]
    body += ["## Attestation", "", f"Declarative (R95-C): the module `{c.module}` and the test `{c.test}` must exist; nothing is executed by the wiki.", "",
             "## Related", "", "- [[computations_register|Computations register]]"]
    if c.desk:
        body.append({1: "- [[Desk_01_HyperLiquid_Monarch|Desk 1]]", 3: "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]"}.get(c.desk, ""))
    body.append("")
    dev: dict[str, Any] = {"kind": c.kind, "command": c.command, "exit_codes": c.exit_codes}
    if c.desk:
        dev["desk"] = c.desk
    if c.item:
        dev["item"] = c.item
    if c.dashboard:
        dev["dashboard"] = c.dashboard
    if requires:
        dev["requires_files"] = requires
    sources = ([{"id": "module", "resource": c.module, "title": c.module, "author": "human:operator"}]
               if (dev_root / c.module).is_file() else None)  # a source that is not on disk would be an L5 finding
    meta = make_meta("Attested Computation", c.title, c.description,
                     tags=["computation", c.kind.replace("_", "-")] + ([f"desk-{c.desk}"] if c.desk else ["module-23"]),
                     generated_by=by, at=at, status="draft",
                     runtime="python", computation=c.command,
                     executor={"resource": c.module, "receipt": list(c.receipt)},
                     attester={"resource": c.test},
                     sources=sources, dev=dev)
    path = page_path(vault, "Attested Computation", c.stem)
    carry_human_fields(load_page(path), meta)  # Ruling 99-2
    return Page(path, meta, "\n".join(body))


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def write_computations(vault: Path, dev_root: Path, *, at: datetime | None = None, by: str = GENERATED_BY,
                       force: bool = False) -> Report:
    at = at or now_utc()
    report = Report()
    for c in COMPUTATIONS:
        page = build_page(c, vault, dev_root, at, by)
        rel = page.path.relative_to(vault).as_posix()
        if page.path.exists() and not force:
            report.skipped.append(rel)
            continue
        write_page(page, vault, now=at)
        report.written.append(rel)
    if report.written:
        write_page(update_register(vault, "Attested Computation", at=at, by=by), vault, now=at)
        write_index(vault, load_pages(vault))
        append_log(vault, "Ingest", f"attested computations: {len(report.written)} page(s) written, {len(report.skipped)} kept "
                   f"({sum(1 for c in COMPUTATIONS if c.kind == 'shell_twin')} shell twins, "
                   f"{sum(1 for c in COMPUTATIONS if c.kind == 'knowledge_cli')} knowledge CLIs); [index](index.md) rebuilt.", when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.computations", description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--at", default=None)
    args = ap.parse_args(argv)
    if halted(args.dev_root):
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - computations refuses (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    report = write_computations(args.vault, args.dev_root, at=parse_iso8601(args.at) if args.at else None, force=args.force)
    for r in report.written:
        print("[WRITE] " + r, file=out)
    for r in report.skipped:
        print("[KEEP]  " + r, file=out)
    print(f"computations: {len(report.written)} written, {len(report.skipped)} kept of {len(COMPUTATIONS)}", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
