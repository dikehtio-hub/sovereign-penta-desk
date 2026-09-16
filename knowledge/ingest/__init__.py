"""Ingest adapters (Round 97, Phase 2): raw machine output -> compiled wiki pages.

Each adapter consumes an EXISTING --json output or registration file, read-only,
and writes only through pages.write_page. None of them imports a desk module,
opens a socket or touches a daemon-owned file. Every CLI refuses on HALT.flag
(exit 3) and appends one `**Ingest**` bullet to log.md per run.

  experiments  cross_market/experiments/*.json  -> Experiment pages (pre-registrations)
  lead_lag     lead_lag --json result           -> Experiment (verdict) + Regime history
  clob         latency_sniper --survival-curve --json -> Reaction Profile + Event + latency-decay Concept
  reading      raw/inbox/ links + raw/fetched/ snapshots -> Source Summary pages + the strategy family search
               (the snapshots are written by knowledge.fetch_reading, the package's only networked module)
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .. import DEV_ROOT, EXIT_HALT, VAULT, halted
from ..frontmatter import parse_iso8601
from ..pages import Page, load_page, md_cell, unchanged_but_for_stamp  # md_cell re-exported: adapters import it from here


def add_common_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--at", default=None, help="ISO 8601 instant for generated.at (default now)")


def guard(args: argparse.Namespace, out) -> int | None:
    """HALT.flag or a missing vault refuses. Returns an exit code, or None to proceed."""
    if halted(args.dev_root):
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - ingest refuses (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    return None


def at_from(args: argparse.Namespace) -> datetime | None:
    return parse_iso8601(args.at) if args.at else None


def rel_to(path: Path, dev_root: Path) -> str:
    try:
        return path.resolve().relative_to(dev_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def item_link(vault: Path, stem: str, label: str, suffix: str = "") -> str:
    """A `- [[stem|label]]` bullet for an Item page, or a plain bullet when it is not there.

    Round 105 (lint L8). Every adapter links the Item page for the desk item it compiles, and every
    seeded vault has all twenty - but a vault seeded from a shorter registry does not, and an
    adapter that hard-codes the link emits one that resolves to nothing. Degrading to plain text
    keeps the reference readable and keeps the vault lintable; the link returns on the next seed.
    """
    return link_if_exists(vault, "Item", stem, label, suffix, missing="Item page not seeded")


def link_if_exists(vault: Path, type_: str, stem: str, label: str, suffix: str = "",
                   missing: str = "page not compiled yet") -> str:
    """A `- [[stem|label]]` bullet, degrading to readable plain text when the page is absent."""
    from ..pages import page_path
    bullet = f"[[{stem}|{label}]]" if page_path(vault, type_, stem).is_file() else f"{label} ({missing})"
    return f"- {bullet}{suffix}"


def page_changed(page: Page, vault: Path) -> bool:
    """Whether writing this page would actually change anything (Ruling R104-3).

    write_page already declines to rewrite identical content, but an adapter also appends a line to
    log.md, and a log entry announcing a compilation that produced nothing is a false record - and
    it dirties git on every run, which is the noise the ruling is about. Call this BEFORE writing.
    """
    return not unchanged_but_for_stamp(load_page(page.path) if page.path.is_file() else None, page)


def fmt_s(v) -> str:
    return "-" if v is None else f"{float(v):g} s"


def fmt_usd(v) -> str:
    return "-" if v is None else f"${float(v):,.0f}"
