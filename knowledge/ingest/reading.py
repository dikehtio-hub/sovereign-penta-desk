"""Reading intake, offline half: inbox links + fetched snapshots -> Source Summary pages and the family search.

    python -m knowledge.ingest.reading [--inbox DIR] [--campaign-meta FILE]
    python -m knowledge.ingest.reading --pending
    python -m knowledge.ingest.reading --review STEM --from review.json [--by ACTOR]

THE AIM (operator, 2026-09-12): find a second strategy family for the autoresearch loop. Every source the
operator drops is read against that aim, so each page carries a fixed screen - family, mechanism, data
needed, horizon, tunables, evidence quality, verdict - and ``wiki/concepts/strategy_family_search.md``
ranks what the sources proposed against the numbers the harness actually enforces, read from the live
campaign registration and pinned with ``dev.parameters`` so lint C1 notices when the next campaign moves them.

WHO WRITES WHAT. This adapter never summarises: it has no model and opens no socket. It compiles what
exists (the inbox line, the snapshot's headers) and leaves two things to a reviewer - a Claude Code session
reading the snapshot under the constitution's Ingest protocol, or the operator - recorded with
``--review``. Re-ingest keeps the ``## Summary`` section and every review field, the CRM Judgement
invariant (Round 99) applied to sources. A review is ``generated``, never ``verified`` (constitution s.6).

VERDICTS are a closed vocabulary: ``candidate`` (fits the harness as registered), ``needs-harness-change``
(a real mechanism the fences refuse today, typically non-OHLCV data), ``reject`` (fails a criterion or is
already measured), ``not-a-strategy`` (background reading).
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

from .. import EXIT_HALT, EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, load_page, load_pages, make_meta, md_cell, now_utc,
                     page_path, safe_title, write_index, write_page)
from ..reading import INBOX_DIR, InboxItem, failure_path, parse_inbox, read_snapshot, snapshot_path
from ..registers import write_register
from . import add_common_args, at_from, guard, link_if_exists, page_changed, rel_to

KIND = "reading_source"
SEARCH_KIND = "strategy_family_search"
SEARCH_STEM = "strategy_family_search"
AIM = "Find a second strategy family for the autoresearch loop"
DEFAULT_CAMPAIGN_META = Path("qtl_autoresearch") / "research" / "autoresearch" / "campaign.meta.json"
VERDICTS = ("candidate", "needs-harness-change", "reject", "not-a-strategy")
REVIEW_FIELDS = ("family", "mechanism", "data_needed", "horizon", "tunables", "evidence", "reason")
SUMMARY_HEADING = "## Summary"
SUMMARY_PLACEHOLDER = ("_(pending review: a reviewer reads the snapshot and records the summary and verdict with "
                       "`python -m knowledge.ingest.reading --review <stem> --from review.json`; re-ingest keeps this section)_")
KIND_LABELS = {"youtube": "YouTube video", "arxiv": "arXiv paper", "github": "GitHub", "pdf": "PDF", "web": "Web page",
               "clip": "Clipped article"}

# (parameter name, json_path in the campaign registration, what the harness enforces)
CRITERIA: tuple[tuple[str, str, str], ...] = (
    ("autoresearch_timeframe", "timeframe", "Bar timeframe the loop scores"),
    ("autoresearch_gate_zero_hurdle_bps", "gate_zero.hurdle_bps",
     "Gate Zero: in-sample GROSS edge per trade, bps, at least (friction is ~10 bps round trip; checked before any campaign)"),
    ("autoresearch_max_tunables", "gates.max_tunables", "Tunable constructor kwargs, at most"),
    ("autoresearch_max_grid_combinations", "gates.max_grid_combinations", "In-sample grid points, at most"),
    ("autoresearch_min_oos_trades_per_asset", "gates.min_oos_trades_per_asset", "Pooled out-of-sample trades per asset, at least"),
    ("autoresearch_max_oos_drawdown_pct", "gates.max_oos_drawdown_pct_of_equity", "Out-of-sample max drawdown, % of equity, at most"),
    ("autoresearch_holdout_promotion_min_trades", "holdout_gates.promotion_min_trades", "Holdout trades before promotion, at least"),
)

# Historical and closed: every campaign so far searched ONE family. Sources are the closed registrations.
ALREADY_MEASURED: tuple[tuple[str, str, str], ...] = (
    ("Donchian channel breakout, 5m bars", "campaign 1 (`ledger_c1_5m_closed.tsv`)",
     "friction about 15x the gross edge: dead by timeframe, not by idea"),
    ("Follow, fade, reversion and campaign-2 signals, 5m bars", "5-minute gross-edge screen (`qtl_holdout/research/autoresearch/gross_edge_screen.py`)",
     "no family cleared 10 bps gross per trade at 5m; closes the TIMEFRAME, not reversion or fading at 1h and slower"),
    ("Donchian channel breakout, 1h bars", "campaign 2 (`campaign2_1h_closed.meta.json`)",
     "the kept trial failed its holdout"),
    ("Donchian breakout, 1h, global consensus selection, ~24h horizon", "campaign 3 (`campaign3_c3_closed.meta.json`)",
     "out-of-sample gross edge below the ~10 bps friction"),
    ("Donchian breakout, 1h, multi-day horizon", "campaign 4 (`campaign.meta.json`, holdout commit 628d6fe)",
     "champion t0030 passed the 2020-2022 holdout: THIS IS FAMILY 1"),
)


@dataclass
class ReadingReport:
    written: list[str] = field(default_factory=list)
    sources: int = 0
    pending: int = 0


def _json_path(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _section(body: str, heading: str) -> str | None:
    m = re.search(rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else None


def _short(text: str, n: int = 180) -> str:
    t = re.sub(r"\s+", " ", str(text)).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# ---------------------------------------------------------------- source pages

def build_source_page(vault: Path, dev_root: Path, stem: str, *, url: str, canonical: str, kind: str, note: str,
                      inbox_file: str | None, summary: str | None, review: dict[str, Any], at: datetime,
                      by: str = GENERATED_BY) -> Page:
    """The one renderer for a source page, used by ingest and by --review so the two can never drift."""
    path = page_path(vault, "Source Summary", stem)
    existing = load_page(path)
    snap = read_snapshot(snapshot_path(vault, stem))
    fail = read_snapshot(failure_path(vault, stem))
    h = snap[0] if snap else {}
    title = h.get("title") or (existing.title if existing and existing.title != stem else None) or canonical

    dev: dict[str, Any] = {"kind": KIND, "desk": 4, "aim": AIM, "source_kind": kind, "url": url, "canonical": canonical}
    if note:
        dev["note"] = note
    if inbox_file:
        dev["inbox_file"] = inbox_file
    sources = [{"id": "origin", "resource": canonical, "title": _short(title, 120)}]
    if h.get("author"):
        # a channel or byline is not an OKF actor (human:<id> | process:<id> | producer/version), so it is
        # recorded as free text rather than coerced into sources[].author, which lint L1 would reject
        dev["author"] = h["author"]
    snap_rel = rel_to(snapshot_path(vault, stem), dev_root)
    if snap:
        dev.update({"fetch_status": "ok", "fetched_at": h.get("fetched_at"), "fetcher": h.get("fetcher"),
                    "chars": int(h.get("chars", "0") or 0), "sha256": h.get("sha256")})
        if h.get("warning"):
            dev["fetch_warning"] = h["warning"]
        sources.append({"id": "snapshot", "resource": snap_rel, "title": "fetched text snapshot", "author": "process:knowledge.fetch_reading"})
        fetch_lines = [f"- status: **ok** - fetched {h.get('fetched_at', '-')} by `{h.get('fetcher', '-')}`, "
                       f"{int(h.get('chars', '0') or 0):,} characters, sha256 `{(h.get('sha256') or '')[:12]}`",
                       f"- snapshot: `{snap_rel}`"]
        if h.get("warning"):
            fetch_lines.append(f"- warning: {h['warning']}")
    elif fail:
        fh = fail[0]
        dev.update({"fetch_status": "failed", "fetch_error": fh.get("error"), "attempted_at": fh.get("attempted_at")})
        fetch_lines = [f"- status: **failed** at {fh.get('attempted_at', '-')}: {fh.get('error', '-')}",
                       "- retry: `python -m knowledge.fetch_reading` (failures are retried every run), or clip the page into `raw/inbox/`"]
    else:
        dev["fetch_status"] = "pending"
        fetch_lines = ["- status: **not fetched yet** - run `python -m knowledge.fetch_reading`"]

    verdict = review.get("verdict")
    dev["review_status"] = "reviewed" if verdict else "pending"
    for k in ("verdict",) + REVIEW_FIELDS:
        if review.get(k) not in (None, ""):
            dev[k] = review[k]
    if review.get("reviewed"):
        dev["reviewed"] = review["reviewed"]

    screen = [("Verdict", f"**{verdict}**" if verdict else "_pending_")] + [
        (k.replace("_", " ").capitalize(), md_cell(review[k]) if review.get(k) not in (None, "") else "-") for k in REVIEW_FIELDS]
    body = [f"# {title}", "",
            f"> **{KIND_LABELS.get(kind, kind)}** · [open the source]({canonical})" + (f" · from `raw/inbox/{inbox_file}`" if inbox_file else ""),
            f"> Operator note: {note or '-'}", "",
            SUMMARY_HEADING, "", (summary or "").strip() or SUMMARY_PLACEHOLDER, "",
            "## Strategy family screen", "", "| Check | Answer |", "|---|---|"]
    body += [f"| {k} | {v} |" for k, v in screen]
    body += ["", f"Screened against the harness criteria on [[{SEARCH_STEM}|the second strategy family search]].", "",
             "## Fetch", "", *fetch_lines, "",
             "## Related", "", f"- [[{SEARCH_STEM}|Second strategy family search]]", "- [[sources_register|Sources register]]",
             link_if_exists(vault, "Desk", "Desk_04_Quant_Trading_Lab", "Desk 4: Quant Trading Lab"), ""]

    if verdict:
        description = f"{verdict}: {_short(review.get('family') or title, 80)} - {_short(review.get('mechanism') or summary or '', 140)}"
    else:
        description = f"Pending review ({KIND_LABELS.get(kind, kind)}, fetch {dev['fetch_status']}): {_short(title, 140)}"
    meta = make_meta("Source Summary", _short(title, 200), description,
                     tags=["source-summary", "reading-intake", kind, "desk-4", "strategy-family-search"],
                     generated_by=by, at=at, status="draft", sources=sources, dev=dev)
    carry_human_fields(existing, meta)
    return Page(path, meta, "\n".join(body))


def _preserved(existing: Page | None) -> tuple[str | None, dict[str, Any]]:
    if existing is None:
        return None, {}
    summary = _section(existing.body, SUMMARY_HEADING)
    if summary == SUMMARY_PLACEHOLDER:
        summary = None
    dev = existing.meta.get("dev") or {}
    review = {k: dev[k] for k in ("verdict", "reviewed") + REVIEW_FIELDS if k in dev}
    return summary, review


def compile_item(item: InboxItem, vault: Path, dev_root: Path, at: datetime, by: str = GENERATED_BY) -> Page:
    existing = load_page(page_path(vault, "Source Summary", item.stem))
    summary, review = _preserved(existing)
    return build_source_page(vault, dev_root, item.stem, url=item.url, canonical=item.canonical, kind=item.kind,
                             note=item.note, inbox_file=item.file, summary=summary, review=review, at=at, by=by)


# ---------------------------------------------------------------- the search page

def source_pages(vault: Path) -> list[Page]:
    return sorted((p for p in load_pages(vault) if p.type == "Source Summary" and (p.meta.get("dev") or {}).get("kind") == KIND),
                  key=lambda p: p.path.stem)


def compile_search(vault: Path, dev_root: Path, *, campaign_meta: Path | None = None, at: datetime,
                   by: str = GENERATED_BY) -> Page:
    meta_file = campaign_meta or (dev_root / DEFAULT_CAMPAIGN_META)
    meta_rel = rel_to(meta_file, dev_root)
    registration = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.is_file() else None
    pages = source_pages(vault)

    parameters: list[dict[str, Any]] = []
    body = ["# Second strategy family search", "",
            f"> **Aim:** {AIM.lower()} - a market mechanism other than the Donchian channel breakout behind champion t0030, "
            "that the fenced harness can score.",
            "> Maintained by `knowledge.ingest.reading`; hand edits are overwritten. Summaries and verdicts live on each source page.", "",
            "## How to feed it", "",
            "1. Drop links in `obsidian_vault/raw/inbox/READING.md`: one per line, the URL first, then an optional ` — note`. "
            "Or clip a whole article into `raw/inbox/` (a `source:` property marks it as clipped).",
            "2. `python -m knowledge.fetch_reading` fetches every new link (YouTube transcripts, articles, arXiv papers, "
            "GitHub READMEs, PDFs) into `raw/fetched/` and recompiles this page.",
            "3. Ask Claude Code to review the reading inbox: it reads each snapshot and records a summary and verdict "
            "with `knowledge.ingest.reading --review`.", "",
            "## What a second family has to clear", ""]
    if registration is None:
        body += [f"> The campaign registration was not found at `{meta_rel}`, so no harness numbers are pinned here. "
                 "Pass `--campaign-meta` to point at the current one.", ""]
    else:
        assets = ", ".join(a.get("symbol", "?") for a in registration.get("assets", []) if isinstance(a, dict)) or "-"
        body += [f"Read from `{meta_rel}` (campaign `{registration.get('campaign_tag', '-')}`).", "",
                 "| Criterion | Harness value |", "|---|---|",
                 "| A different mechanism | not a channel or trend breakout: that is family 1 (below) |",
                 "| Diversifies family 1 | its trades should not win and lose with a trend breakout's. Time-series momentum, "
                 "moving-average crossovers and volatility-scaled trend are the SAME bet renamed, and Campaign 5's "
                 "portfolio drawdown gate judges the combined equity curve |",
                 "| Data inside the strategy | the traded symbol's OHLCV bars only: the import fence refuses file, network and data access, "
                 "so funding, open interest, order books, on-chain or news signals are `needs-harness-change` |",
                 f"| Assets | {md_cell(assets)} |"]
        for name, jpath, label in CRITERIA:
            value = _json_path(registration, jpath)
            if value is None:
                continue
            parameters.append({"name": name, "value": value, "file": meta_rel, "json_path": jpath})
            body.append(f"| {md_cell(label)} | `{md_cell(value)}` |")
        body += ["", "> Campaign 5's charter (per-asset parameters and grids, boundary mark-to-market, holding-period hooks, "
                 "a portfolio drawdown gate) is not registered yet. When it is, these numbers move and lint C1 flags this page "
                 "until the next ingest.", ""]

    body += ["## Already measured (do not re-propose)", "", "| Family | Where | Result |", "|---|---|---|"]
    body += [f"| {md_cell(f)} | {md_cell(w)} | {md_cell(r)} |" for f, w, r in ALREADY_MEASURED]
    body += [""]

    reviewed = [p for p in pages if (p.meta.get("dev") or {}).get("verdict")]
    pending = [p for p in pages if not (p.meta.get("dev") or {}).get("verdict")]
    order = {v: i for i, v in enumerate(VERDICTS)}
    reviewed.sort(key=lambda p: (order.get(p.meta["dev"]["verdict"], 9), str(p.meta["dev"].get("family", "")).lower(), p.path.stem))

    body += ["## Candidate families", ""]
    live = [p for p in reviewed if p.meta["dev"]["verdict"] in ("candidate", "needs-harness-change")]
    if live:
        body += ["| Verdict | Family | Mechanism | Data needed | Horizon | Source |", "|---|---|---|---|---|---|"]
        for p in live:
            d = p.meta["dev"]
            body.append(f"| **{d['verdict']}** | {md_cell(d.get('family', '-'))} | {md_cell(_short(d.get('mechanism', '-'), 160))} | "
                        f"{md_cell(d.get('data_needed', '-'))} | {md_cell(d.get('horizon', '-'))} | [[{p.path.stem}\\|{safe_title(_short(p.title, 60))}]] |")
    else:
        body.append("_None yet._ Drop links in the inbox and ask for a review.")
    body += ["", "## Rejected or background", ""]
    dead = [p for p in reviewed if p.meta["dev"]["verdict"] in ("reject", "not-a-strategy")]
    body += [f"- **{p.meta['dev']['verdict']}** - [[{p.path.stem}|{safe_title(_short(p.title, 80))}]]: "
             f"{_short(p.meta['dev'].get('reason') or p.meta['dev'].get('family') or '-', 160)}" for p in dead] or ["_None yet._"]
    body += ["", "## Awaiting review", ""]
    body += [f"- [[{p.path.stem}|{safe_title(_short(p.title, 80))}]] - {KIND_LABELS.get(p.meta['dev'].get('source_kind'), '-')}, "
             f"fetch {p.meta['dev'].get('fetch_status', '-')}" for p in pending] or ["_Nothing waiting._"]
    body += ["", f"{len(pages)} source(s): {len(live)} live, {len(dead)} rejected or background, {len(pending)} awaiting review.", "",
             "## Related", "", "- [[sources_register|Sources register]]",
             link_if_exists(vault, "Desk", "Desk_04_Quant_Trading_Lab", "Desk 4: Quant Trading Lab"),
             link_if_exists(vault, "Concept", "experiments_register", "Experiments register"), ""]

    history = [{"stem": p.path.stem, "verdict": p.meta["dev"]["verdict"], "family": p.meta["dev"].get("family"),
                "source_kind": p.meta["dev"].get("source_kind")} for p in reviewed]
    dev: dict[str, Any] = {"kind": SEARCH_KIND, "desk": 4, "aim": AIM, "sources_n": len(pages), "pending_n": len(pending),
                           "history": history}
    if parameters:
        dev["parameters"] = parameters
    sources = [{"id": "campaign", "resource": meta_rel, "title": "current autoresearch campaign registration", "author": "human:operator"}] \
        if registration is not None else None
    meta = make_meta("Concept", "Second strategy family search",
                     f"The operator's research aim: {AIM.lower()}. Harness criteria, families already measured, and every source "
                     f"ranked by verdict. {len(live)} live, {len(pending)} awaiting review.",
                     tags=["concept", "strategy-family-search", "autoresearch", "desk-4", "reading-intake"],
                     generated_by=by, at=at, status="draft", sources=sources, dev=dev)
    path = page_path(vault, "Concept", SEARCH_STEM)
    carry_human_fields(load_page(path), meta)
    return Page(path, meta, "\n".join(body))


def _finish(vault: Path, dev_root: Path, pages_changed: bool, *, campaign_meta: Path | None, at: datetime, by: str,
            action: str, text: str, report: ReadingReport) -> None:
    search = compile_search(vault, dev_root, campaign_meta=campaign_meta, at=at, by=by)
    changed = page_changed(search, vault)
    write_page(search, vault, now=at)
    if changed:
        report.written.append(search.rel(vault))
    _, reg_changed = write_register(vault, "Source Summary", at=at, by=by)
    if pages_changed or changed or reg_changed:
        write_index(vault, load_pages(vault))
        append_log(vault, action, text, when=at)


# ---------------------------------------------------------------- entry points

def ingest_reading(vault: Path, dev_root: Path, *, inbox: Path | None = None, campaign_meta: Path | None = None,
                   at: datetime | None = None, by: str = GENERATED_BY) -> ReadingReport:
    at = at or now_utc()
    report = ReadingReport()
    changed_any = False
    for item in parse_inbox(inbox or (vault / INBOX_DIR)):
        page = compile_item(item, vault, dev_root, at, by)
        if page_changed(page, vault):
            changed_any = True
            report.written.append(page.rel(vault))
        write_page(page, vault, now=at)
    all_sources = source_pages(vault)
    report.sources = len(all_sources)
    report.pending = sum(1 for p in all_sources if not (p.meta.get("dev") or {}).get("verdict"))
    _finish(vault, dev_root, changed_any, campaign_meta=campaign_meta, at=at, by=by, action="Ingest",
            text=f"reading inbox: {report.sources} source(s), {report.pending} awaiting review -> [[{SEARCH_STEM}]].", report=report)
    return report


def review_source(vault: Path, dev_root: Path, stem: str, review: dict[str, Any], *, campaign_meta: Path | None = None,
                  at: datetime | None = None, by: str = GENERATED_BY) -> Page:
    """Record a reviewer's summary and screen on one source page. Refuses an unknown stem or verdict."""
    at = at or now_utc()
    existing = load_page(page_path(vault, "Source Summary", stem))
    if existing is None or (existing.meta.get("dev") or {}).get("kind") != KIND:
        raise ValueError(f"no reading source page {stem!r}; run knowledge.ingest.reading first")
    summary = str(review.get("summary") or "").strip()
    if not summary:
        raise ValueError("a review needs a non-empty `summary`")
    if re.search(r"^#{1,2} ", summary, re.M):
        # the summary is preserved as the text between `## Summary` and the next `## `: a level-1 or -2
        # heading inside it would be cut off on the next re-ingest, silently. Level 3 and below are fine.
        raise ValueError("`summary` may not contain '# ' or '## ' headings (use ### or bold)")
    verdict = review.get("verdict")
    if verdict not in VERDICTS:
        raise ValueError(f"`verdict` must be one of {', '.join(VERDICTS)}; got {verdict!r}")
    unknown = sorted(set(review) - {"summary", "verdict", *REVIEW_FIELDS})
    if unknown:
        raise ValueError(f"unknown review field(s): {', '.join(unknown)}")
    dev = existing.meta["dev"]
    fields = {k: (str(review[k]).strip() if review.get(k) not in (None, "") else None) for k in REVIEW_FIELDS}
    fields = {k: v for k, v in fields.items() if v}
    prior = (dev.get("reviewed") or {})
    same = dev.get("verdict") == verdict and all(dev.get(k) == fields.get(k) for k in REVIEW_FIELDS) \
        and _section(existing.body, SUMMARY_HEADING) == summary
    reviewed = prior if same and prior else {"by": by, "at": at.strftime("%Y-%m-%dT%H:%M:%SZ")}
    page = build_source_page(vault, dev_root, stem, url=dev["url"], canonical=dev["canonical"], kind=dev["source_kind"],
                             note=dev.get("note", ""), inbox_file=dev.get("inbox_file"), summary=summary,
                             review={"verdict": verdict, "reviewed": reviewed, **fields}, at=at, by=by)
    changed = page_changed(page, vault)
    write_page(page, vault, now=at)
    report = ReadingReport(written=[page.rel(vault)] if changed else [])
    _finish(vault, dev_root, changed, campaign_meta=campaign_meta, at=at, by=by, action="Review",
            text=f"[[{stem}]] -> **{verdict}**: {_short(fields.get('family') or page.title, 90)}.", report=report)
    return page


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.reading", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--inbox", type=Path, default=None, help=f"default <vault>/{INBOX_DIR}")
    ap.add_argument("--campaign-meta", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_CAMPAIGN_META.as_posix()}")
    ap.add_argument("--pending", action="store_true", help="list sources awaiting review with their snapshot paths; writes nothing")
    ap.add_argument("--review", metavar="STEM", default=None, help="record a review on one source page")
    ap.add_argument("--from", dest="review_file", type=Path, default=None, help="review JSON: summary, verdict, family, mechanism, ...")
    ap.add_argument("--by", default=GENERATED_BY, help="actor string for the review (default this agent)")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    at = at_from(args)
    if args.pending:
        for p in source_pages(args.vault):
            d = p.meta.get("dev") or {}
            if not d.get("verdict"):
                snap = snapshot_path(args.vault, p.path.stem)
                where = rel_to(snap, args.dev_root) if snap.is_file() else f"(fetch {d.get('fetch_status', '-')})"
                print(f"[PENDING] {p.path.stem}  {d.get('source_kind', '-')}  {where}  {p.title}", file=out)
        return EXIT_OK
    if args.review:
        if args.review_file is None or not args.review_file.is_file():
            print("[REFUSE] --review needs --from <review.json>", file=out)
            return EXIT_HALT
        try:
            page = review_source(args.vault, args.dev_root, args.review, json.loads(args.review_file.read_text(encoding="utf-8")),
                                 campaign_meta=args.campaign_meta, at=at, by=args.by)
        except ValueError as e:
            print(f"[REFUSE] {e}", file=out)
            return EXIT_HALT
        print(f"[REVIEW] {page.rel(args.vault)}  {page.meta['dev']['verdict']}", file=out)
        return EXIT_OK
    rep = ingest_reading(args.vault, args.dev_root, inbox=args.inbox, campaign_meta=args.campaign_meta, at=at)
    for w in rep.written:
        print(f"[WRITE] {w}", file=out)
    print(f"{rep.sources} source page(s), {rep.pending} awaiting review -> wiki/concepts/{SEARCH_STEM}.md", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
