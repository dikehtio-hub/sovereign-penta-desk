"""Market pages: the Polymarket tokens the wiki is bound to (Round 98, B9).

    python -m knowledge.ingest.markets [--drops DIR] [--experiments DIR] [--family FED-RATES ...] [--force]

Sources, all read-only: the token ids in every *.rules.json registration, the
`dev.tokens` of every Experiment page, and every record of the requested
families (default FED-RATES) in the newest macro drop. One page per token,
named by the market slug:

  wiki/markets/will-there-be-no-change-in-fed-interest-rates-...md

A Market page carries what does not change every poll: token_id, condition_id,
slugs, question, family, first_seen, neg_risk when a rules file says so. It
never carries a price (WIKI_SCHEMA.md s.6). Lint C2 warns when the token is
gone from the newest drops; `knowledge.lint --fix-safe` then sets
`status: deprecated`. Existing pages are kept unless --force. The Markets
register is rebuilt after every run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..lint import DEFAULT_DROPS, newest_drop
from ..pages import Page, append_log, carry_human_fields, load_page, load_pages, make_meta, now_utc, page_path, write_index, write_page
from ..registers import write_register
from . import add_common_args, at_from, guard, page_changed, rel_to

DEFAULT_EXPERIMENTS = Path("cross_market") / "experiments"
DEFAULT_FAMILIES = ("FED-RATES",)
REGISTER_FILE = "markets_register"


def slug_for(record: dict[str, Any], token: str) -> str:
    s = str(record.get("market_slug") or "").strip()
    s = re.sub(r"[^A-Za-z0-9_\-]+", "_", s).strip("_")
    return s[:100] if s else f"token_{token[:20]}"


def rules_tokens(exp_dir: Path, dev_root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not exp_dir.is_dir():
        return out
    for path in sorted(exp_dir.glob("*.rules.json")):
        if "sample" in path.name.lower():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for r in data.get("rules") or []:
            if isinstance(r, dict) and r.get("market"):
                out[str(r["market"])] = {"question": r.get("question"), "market_slug": r.get("market_slug"),
                                         "neg_risk": r.get("neg_risk"), "rule_label": r.get("label"),
                                         "rules_file": rel_to(path, dev_root)}
    return out


def experiment_tokens(vault: Path) -> set[str]:
    toks: set[str] = set()
    for p in load_pages(vault):
        if p.type == "Experiment":
            for t in (p.meta.get("dev") or {}).get("tokens") or []:
                toks.add(str(t))
    return toks


def path_for(vault: Path, token: str, record: dict[str, Any] | None, extra: dict[str, Any] | None) -> Path:
    """Where this market's page lives - the same slug compile_market will use."""
    record, extra = record or {}, extra or {}
    return page_path(vault, "Market", slug_for(record if record else {"market_slug": extra.get("market_slug")}, token))


def compile_market(token: str, record: dict[str, Any] | None, extra: dict[str, Any] | None, drop_rel: str | None,
                   vault: Path, at: datetime, by: str = GENERATED_BY) -> Page:
    record = record or {}
    extra = extra or {}
    question = str(record.get("question") or extra.get("question") or f"Polymarket token {token[:12]}…")
    family = str(record.get("sport") or "unknown")
    slug = slug_for(record if record else {"market_slug": extra.get("market_slug")}, token)
    body = [f"# Market: {question}", "", f"> Polymarket · family {family} · token `{token[:12]}…`", "",
            "## Identity", "", f"- token_id: `{token}`"]
    if record.get("condition_id"):
        body.append(f"- condition_id: `{record['condition_id']}`")
    if record.get("market_slug") or extra.get("market_slug"):
        body.append(f"- market_slug: `{record.get('market_slug') or extra.get('market_slug')}`")
    if record.get("event_slug"):
        body.append(f"- event: {record.get('event_title', '')} (`{record['event_slug']}`)")
    if record.get("start_time"):
        body.append(f"- start_time: `{record['start_time']}`")
    if extra.get("neg_risk") is not None:
        body.append(f"- neg_risk: {extra['neg_risk']} (from the rules registration; Ruling R4 applies)")
    body += ["", "## Bound by", ""]
    body.append(f"- rule `{extra['rule_label']}` in `{extra['rules_file']}`" if extra.get("rules_file") else "- no sniper rule; listed as part of the family")
    body += ["", "## Lifecycle", "", "- no prices here (s.6); the dashboards carry the live number",
             "- lint C2 warns when this token leaves the newest drops; `lint --fix-safe` deprecates the page", "",
             "## Related", "", f"- [[{REGISTER_FILE}|Markets register]]", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]", ""]
    dev: dict[str, Any] = {"desk": 3, "token_id": token, "family": family}
    for k in ("condition_id", "market_slug", "event_slug", "event_title", "start_time"):
        if record.get(k):
            dev[k] = record[k]
    if not dev.get("market_slug") and extra.get("market_slug"):
        dev["market_slug"] = extra["market_slug"]
    if record.get("fetched_at"):
        dev["first_seen"] = record["fetched_at"]
    # FIRST seen, not last. Round 106: until R105-2 these pages were written once and then skipped
    # forever, so this field was accidentally correct. Now that every page is re-admitted on every
    # run, each fresh drop would overwrite it with the LATEST sighting and quietly destroy the only
    # record of when the market appeared. The existing page wins whenever it is earlier.
    prior = ((load_page(path_for(vault, token, record, extra)) or Page(Path("x"), {})).meta.get("dev") or {}).get("first_seen")
    if prior and (not dev.get("first_seen") or str(prior) < str(dev["first_seen"])):
        dev["first_seen"] = prior
    if extra.get("neg_risk") is not None:
        dev["neg_risk"] = bool(extra["neg_risk"])
    if extra.get("rule_label"):
        dev["rule_label"] = extra["rule_label"]
    sources: list[dict[str, Any]] = []
    if drop_rel:
        sources.append({"id": "drop", "resource": drop_rel, "title": "newest macro drop", "author": "process:cross_market.ingestors.polymarket_fetcher"})
    if extra.get("rules_file"):
        sources.append({"id": "rules", "resource": extra["rules_file"], "title": "sniper rules registration", "author": "human:operator"})
    if not sources:
        sources.append({"id": "wiki", "resource": "obsidian_vault/wiki/experiments", "title": "Experiment dev.tokens", "author": by})
    meta = make_meta("Market", question, f"Polymarket market ({family}): {question}",
                     tags=["market", "polymarket", family.lower()], generated_by=by, at=at, status="draft",
                     resource=f"polymarket:token:{token}", sources=sources, dev=dev)
    path = page_path(vault, "Market", slug)
    carry_human_fields(load_page(path), meta)  # Ruling 99-2: a --force re-seed keeps a deprecation or a human verification
    return Page(path, meta, "\n".join(body))


@dataclass
class MarketsReport:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    tokens: int = 0


def ingest_markets(vault: Path, dev_root: Path, *, drops: Path | None = None, exp_dir: Path | None = None,
                   families=DEFAULT_FAMILIES, at: datetime | None = None, by: str = GENERATED_BY,
                   force: bool = False) -> MarketsReport:
    at = at or now_utc()
    drops = drops or (dev_root / DEFAULT_DROPS)
    exp_dir = exp_dir or (dev_root / DEFAULT_EXPERIMENTS)
    extras = rules_tokens(exp_dir, dev_root)
    wanted: set[str] = set(extras) | experiment_tokens(vault)
    records: dict[str, dict[str, Any]] = {}
    in_drop: set[str] = set()          # tokens the NEWEST drop actually carries, vs ones recovered below
    drop_rel: str | None = None
    newest = newest_drop(drops, "polymarket_macro") if drops.is_dir() else None
    if newest is not None:
        try:
            data = json.loads(newest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []
        drop_rel = rel_to(newest, dev_root)
        fams = {f.upper() for f in families}
        for r in data if isinstance(data, list) else []:
            if not isinstance(r, dict) or not r.get("token_id"):
                continue
            tok = str(r["token_id"])
            records[tok] = r
            in_drop.add(tok)
            if str(r.get("sport", "")).upper() in fams:
                wanted.add(tok)

    # Ruling R105-2: every token that already has a page is re-admitted, so a market ageing out of
    # the drop is refreshed rather than frozen. BUT a naive union would be destructive here, which
    # the ruling's sketch does not anticipate: with no drop record compile_market falls back to the
    # placeholder question "Polymarket token abc123…", family "unknown", AND a token-derived slug -
    # so it would write a DEGRADED DUPLICATE at a new path and leave the good page orphaned. The
    # page's own dev block is the record of record for an aged-out market, so recover identity from
    # it and let the compile refresh only what the code derives.
    for page in load_pages(vault):
        if page.type != "Market":
            continue
        d = page.meta.get("dev") or {}
        tok = str(d.get("token_id") or "")
        if not tok:
            continue
        wanted.add(tok)
        if tok not in records:
            records[tok] = {k: v for k, v in {
                "question": page.meta.get("title"), "sport": d.get("family"),
                "market_slug": d.get("market_slug"), "condition_id": d.get("condition_id"),
                "event_slug": d.get("event_slug"), "event_title": d.get("event_title"),
                "start_time": d.get("start_time"), "fetched_at": d.get("first_seen"),
            }.items() if v is not None}
    report = MarketsReport(tokens=len(wanted))
    for tok in sorted(wanted):
        page = compile_market(tok, records.get(tok), extras.get(tok), drop_rel if tok in in_drop else None, vault, at, by)
        rel = page.path.relative_to(vault).as_posix()
        # Ruling R105-2 + R104-3: an existing page is no longer skipped, because skipping is exactly
        # what froze it. write_page declines to rewrite identical content, so re-admitting every page
        # costs nothing and `--force` is no longer the only way a market page ever gets refreshed.
        if not page_changed(page, vault):
            report.skipped.append(rel)
            continue
        write_page(page, vault, now=at)
        report.written.append(rel)
    if report.written:
        write_register(vault, "Market", at=at, by=by)
        write_index(vault, load_pages(vault))
        append_log(vault, "Ingest", f"markets: {len(wanted)} token(s) from rules, Experiment pages and the newest macro drop "
                   f"(families {', '.join(families)}); {len(report.written)} page(s) written, {len(report.skipped)} kept; [index](index.md) rebuilt.",
                   when=at)
    return report


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.markets", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--drops", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_DROPS.as_posix()}")
    ap.add_argument("--experiments", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_EXPERIMENTS.as_posix()}")
    ap.add_argument("--family", action="append", default=None, help="drop `sport` families to include (default FED-RATES)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    report = ingest_markets(args.vault, args.dev_root, drops=args.drops, exp_dir=args.experiments,
                            families=tuple(args.family) if args.family else DEFAULT_FAMILIES, at=at_from(args), force=args.force)
    for r in report.written:
        print("[WRITE] " + r, file=out)
    print(f"markets: {report.tokens} token(s); {len(report.written)} written, {len(report.skipped)} kept", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
