"""Ingest adapters (Round 97, Phase 2): raw machine output -> compiled wiki pages.

Each adapter consumes an EXISTING --json output or registration file, read-only,
and writes only through pages.write_page. None of them imports a desk module,
opens a socket or touches a daemon-owned file. Every CLI refuses on HALT.flag
(exit 3) and appends one `**Ingest**` bullet to log.md per run.

  experiments  cross_market/experiments/*.json  -> Experiment pages (pre-registrations)
  lead_lag     lead_lag --json result           -> Experiment (verdict) + Regime history
  clob         latency_sniper --survival-curve --json -> Reaction Profile + Event + latency-decay Concept
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .. import DEV_ROOT, EXIT_HALT, VAULT, halted
from ..frontmatter import parse_iso8601


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


def md_cell(v) -> str:
    """A value safe inside a markdown table cell (Round 104).

    Distinct from pages.safe_title, which SUBSTITUTES `|` with `/` because a wiki link's own grammar
    cannot carry a pipe at all. Here the value is data, not a title - `VOL_HIGH|FUND_FLAT` is a literal
    regime_tag in hyperliquid_data.db - so the pipe is ESCAPED and the reader sees the real key. The
    unescaped version silently split the regime table into a phantom extra column.
    """
    return str(v).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def fmt_s(v) -> str:
    return "-" if v is None else f"{float(v):g} s"


def fmt_usd(v) -> str:
    return "-" if v is None else f"${float(v):,.0f}"
