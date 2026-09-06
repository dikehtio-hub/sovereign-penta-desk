"""Realised basis funding windows -> the Desk 1 funding regime page (Round 104, backlog B2).

    python -m knowledge.ingest.funding [--db PATH] [--at ISO] [--force]

Reads `basis_realised_windows` from hyperliquid_data.db (file:...?mode=ro) and compiles
wiki/regimes/hl_funding_regime.md: what the delta-neutral basis book ACTUALLY realised,
measured against the two bars the harvester enters on
(settings.BASIS_MIN_FUNDING_APR = 25.0 gross, BASIS_MIN_NET_APR = 20.0 net), both pinned
as `dev.parameters` so lint C1 catches the day someone edits a constant and forgets the page.

THE DISTINCTION THAT MAKES THIS HONEST. Two populations live in this table and they answer
different questions:
  * ALL windows - every candidate the measurement grid opened on a stride, most of which the
    harvester would never have entered. Their median realised APR says what funding pays on
    average, which is not what the strategy earns.
  * ENTRY-QUALIFYING windows - `quote_apr_entry >= BASIS_MIN_FUNDING_APR`, i.e. the ones the
    harvester's own entry rule would have taken. This is the population the hurdle is about.
Reporting only the first understates the strategy; reporting only the second hides how selective
it has to be. The page carries both, side by side, and says which is which.

THE NET BAR IS MOSTLY UNMEASURABLE and the page says so rather than quietly falling back to
gross: `net_apr_after_fees` is NULL wherever `fee_basis` is 'unmeasured', which is the large
majority of rows, because spreads were not recorded for most windows. A net verdict is issued
only over the measured subset, with its size stated.

Read-only on the database. Never writes outside the vault.
"""
from __future__ import annotations

import argparse
import sqlite3
import statistics as st
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import EXIT_OK, GENERATED_BY
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc,
                     page_path, write_index, write_page)
from . import add_common_args, at_from, guard, rel_to

DEFAULT_DB = Path("HyperLiquid") / "HL_Monarch" / "data" / "hyperliquid_data.db"
SETTINGS_FILE = Path("HyperLiquid") / "HL_Monarch" / "config" / "settings.py"
REGIME_FILE = "hl_funding_regime"
GROSS_BAR_NAME, NET_BAR_NAME = "BASIS_MIN_FUNDING_APR", "BASIS_MIN_NET_APR"


def read_bars(dev_root: Path) -> dict[str, float]:
    """The two entry bars, read from settings.py so the page never invents them."""
    import re
    text = (dev_root / SETTINGS_FILE).read_text(encoding="utf-8", errors="replace")
    out: dict[str, float] = {}
    for name in (GROSS_BAR_NAME, NET_BAR_NAME):
        m = re.search(rf"^{name}\s*=\s*([0-9.]+)", text, re.M)
        if m:
            out[name] = float(m.group(1))
    return out


def load_windows(db: Path) -> list[dict[str, Any]]:
    if not db.is_file():
        return []
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=8)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM basis_realised_windows")]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _pct(v: list[float], p: float) -> float | None:
    if not v:
        return None
    s = sorted(v)
    return round(s[max(0, min(len(s) - 1, int(p * len(s))))], 2)


def describe(values: list[float], bar: float | None) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    d: dict[str, Any] = {
        "n": len(values), "median": round(st.median(values), 2), "mean": round(st.fmean(values), 2),
        "p10": _pct(values, 0.10), "p25": _pct(values, 0.25), "p75": _pct(values, 0.75), "p90": _pct(values, 0.90),
        "negative_pct": round(100.0 * sum(1 for x in values if x < 0) / len(values), 1),
    }
    if bar is not None:
        d["at_or_above_bar"] = sum(1 for x in values if x >= bar)
        d["at_or_above_bar_pct"] = round(100.0 * d["at_or_above_bar"] / len(values), 1)
    return d


def measure(rows: list[dict[str, Any]], bars: dict[str, float]) -> dict[str, Any]:
    gross_bar = bars.get(GROSS_BAR_NAME)
    net_bar = bars.get(NET_BAR_NAME)
    realised = [r["realised_apr"] for r in rows if r["realised_apr"] is not None]
    qualifying = [r for r in rows
                  if r.get("quote_apr_entry") is not None and gross_bar is not None
                  and r["quote_apr_entry"] >= gross_bar and r["realised_apr"] is not None]
    net_measured = [r for r in rows if r.get("net_apr_after_fees") is not None]
    coverage = [r["coverage"] for r in rows if r.get("coverage") is not None]
    return {
        "rows": len(rows),
        "assets": len({r["asset"] for r in rows}),
        "realised_present": len(realised),
        "all_windows": describe(realised, gross_bar),
        "entry_qualifying": describe([r["realised_apr"] for r in qualifying], gross_bar),
        "entry_qualifying_n": len(qualifying),
        "net": {
            "measured_rows": len(net_measured),
            "measured_pct": round(100.0 * len(net_measured) / len(rows), 1) if rows else 0.0,
            "distribution": describe([r["net_apr_after_fees"] for r in net_measured], net_bar),
            "verdict": ("UNMEASURABLE - the net bar cannot be judged on this data"
                        if len(net_measured) < 500 else "measured"),
        },
        "median_coverage": round(st.median(coverage), 3) if coverage else None,
        "regimes": {k: sum(1 for r in rows if r.get("regime_tag") == k)
                    for k in sorted({str(r.get("regime_tag")) for r in rows})},
    }


def _table(name: str, d: dict[str, Any]) -> list[str]:
    if not d.get("n"):
        return [f"| {name} | no rows | | | | | |"]
    return [f"| {name} | {d['n']:,} | {d['median']} | {d['mean']} | {d['p10']} | {d['p90']} | "
            f"{d.get('at_or_above_bar_pct', '-')}% | {d['negative_pct']}% |"]


def build_page(m: dict[str, Any], bars: dict[str, float], vault: Path, dev_root: Path, db: Path,
               at: datetime, by: str = GENERATED_BY) -> Page:
    gross_bar, net_bar = bars.get(GROSS_BAR_NAME), bars.get(NET_BAR_NAME)
    path = page_path(vault, "Regime", REGIME_FILE)
    existing = load_page(path)
    history = [dict(r) for r in ((existing.meta.get("dev") or {}).get("history") or [])] if existing else []
    history.append({"at": iso(at), "rows": m["rows"], "assets": m["assets"],
                    "all_median": m["all_windows"].get("median"), "qual_n": m["entry_qualifying_n"],
                    "qual_median": m["entry_qualifying"].get("median"),
                    "qual_at_bar_pct": m["entry_qualifying"].get("at_or_above_bar_pct"),
                    "net_measured_pct": m["net"]["measured_pct"]})
    aw, eq = m["all_windows"], m["entry_qualifying"]
    body = [
        "# HyperLiquid funding regime (Desk 1, Item 8)", "",
        f"> What the delta-neutral basis book ACTUALLY realised across {m['rows']:,} recorded windows on "
        f"{m['assets']} assets, against the harvester's own entry bars.", "",
        "## The two populations", "",
        "The table holds every candidate window the measurement grid opened on a stride, most of which the",
        "harvester would never have entered. Judging the strategy on all of them understates it; judging it",
        "only on the ones it would have taken hides how selective it has to be. Both are below.", "",
        f"Of the {m['rows']:,} windows, **{m['realised_present']:,} carry a `realised_apr`**; the rest closed "
        "without one and are counted nowhere below. Percentages are shares of each population, not of the table.", "",
        f"| Population | n | median APR | mean | p10 | p90 | >= {gross_bar} bar | negative |",
        "|---|---|---|---|---|---|---|---|",
        *_table("All recorded windows", aw),
        *_table(f"Entry-qualifying (quote_apr_entry >= {gross_bar})", eq),
        "",
        "## Reading", "",
    ]
    if eq.get("n") and aw.get("median") is not None:
        body += [
            f"- The entry rule is doing work: qualifying windows realise a median **{eq['median']}%** against "
            f"**{aw['median']}%** across all windows.",
            f"- But only **{eq.get('at_or_above_bar_pct')}%** of the windows that qualified on the quoted APR "
            f"actually realised at or above the {gross_bar}% bar, and **{eq['negative_pct']}%** went negative. "
            "Entering on a quoted rate is not the same as earning it.",
            f"- Spread between p10 and p90 on qualifying windows: {eq['p10']}% to {eq['p90']}%.",
        ]
    body += [
        "", "## The net bar", "",
        f"`{NET_BAR_NAME} = {net_bar}` is the bar that matters after paying spread on both legs. It is "
        f"**{m['net']['verdict']}**: only {m['net']['measured_rows']:,} of {m['rows']:,} rows "
        f"({m['net']['measured_pct']}%) carry a measured `net_apr_after_fees`; the rest have "
        "`fee_basis = 'unmeasured'` because spreads were not recorded when the window closed. No net verdict "
        "is issued over a 2% sample, and the gross figure is NOT substituted for it.", "",
        "## Coverage and regimes", "",
        f"- median window coverage: {m['median_coverage']}",
        "- windows by regime tag: " + ", ".join(f"`{k}` {v:,}" for k, v in m["regimes"].items()), "",
        "## History", "", "| At | rows | assets | all median | qualifying n | qualifying median | >= bar | net measured |",
        "|---|---|---|---|---|---|---|---|",
    ]
    body += [f"| {h['at']} | {h['rows']:,} | {h['assets']} | {h['all_median']} | {h['qual_n']} | "
             f"{h['qual_median']} | {h['qual_at_bar_pct']}% | {h['net_measured_pct']}% |" for h in history]
    body += ["", "## Related", "", "- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]",
             "- [[Item_08_Hyperliquid_Delta_Neutral_Funding_Rate_Harvester|Item 8: Delta-Neutral Funding Rate Harvester]]", ""]

    settings_rel = SETTINGS_FILE.as_posix()
    params = [{"name": "basis_min_funding_apr", "value": gross_bar, "file": settings_rel,
               "pattern": rf"^{GROSS_BAR_NAME}\s*=\s*([0-9.]+)"},
              {"name": "basis_min_net_apr", "value": net_bar, "file": settings_rel,
               "pattern": rf"^{NET_BAR_NAME}\s*=\s*([0-9.]+)"}]
    dev: dict[str, Any] = {"desk": 1, "item": 8, "kind": "funding_regime", "measurement": m,
                           "parameters": [p for p in params if p["value"] is not None],
                           "requires_files": [settings_rel], "history": history}
    meta = make_meta("Regime", "HyperLiquid funding regime",
                     f"Realised basis funding across {m['rows']:,} windows: all-window median "
                     f"{aw.get('median')}%, entry-qualifying median {eq.get('median')}% with "
                     f"{eq.get('at_or_above_bar_pct')}% clearing the {gross_bar}% bar; the net bar is "
                     f"{m['net']['verdict'].split(' - ')[0].lower()}.",
                     tags=["regime", "desk-1", "item-8", "funding", "basis"], generated_by=by, at=at, status="draft",
                     sources=[{"id": "basis-windows", "resource": rel_to(db, dev_root),
                               "title": "hyperliquid_data.db basis_realised_windows (mode=ro)",
                               "author": "process:HL_Monarch.storage.incremental_persistence"},
                              {"id": "bars", "resource": settings_rel, "title": "the harvester's entry bars",
                               "author": "human:operator"}],
                     dev=dev)
    carry_human_fields(existing, meta)
    return Page(path, meta, "\n".join(body))


@dataclass
class FundingReport:
    written: bool = False
    rows: int = 0


def ingest_funding(vault: Path, dev_root: Path, *, db: Path | None = None, at: datetime | None = None,
                   by: str = GENERATED_BY) -> tuple[FundingReport, Page | None]:
    at = at or now_utc()
    db = db or (dev_root / DEFAULT_DB)
    rows = load_windows(db)
    if not rows:
        return FundingReport(False, 0), None
    bars = read_bars(dev_root)          # read ONCE: two reads could straddle an edit to settings.py
    page = build_page(measure(rows, bars), bars, vault, dev_root, db, at, by)
    write_page(page, vault, now=at)
    # No register for the Regime type (registers.SPECS has none); the desk page carries the inbound
    # link instead, via seed.COMPILED_PAGES, which is what keeps lint L3 quiet.
    write_index(vault, load_pages(vault))
    append_log(vault, "Ingest", f"basis funding windows: {len(rows):,} row(s) from `{rel_to(db, dev_root)}` -> "
               f"[[{REGIME_FILE}]]; entry-qualifying median "
               f"{page.meta['dev']['measurement']['entry_qualifying'].get('median')}% vs all-window "
               f"{page.meta['dev']['measurement']['all_windows'].get('median')}%.", when=at)
    return FundingReport(True, len(rows)), page


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.funding", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--db", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_DB.as_posix()}")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    report, page = ingest_funding(args.vault, args.dev_root, db=args.db, at=at_from(args))
    if not report.written:
        print("[REFUSE] no basis_realised_windows rows readable (exit 3)", file=out)
        return 3
    m = page.meta["dev"]["measurement"]
    print(f"[WRITE] {page.path.relative_to(args.vault).as_posix()}", file=out)
    print(f"funding: {report.rows:,} window(s), {m['assets']} assets · all median {m['all_windows'].get('median')}% · "
          f"entry-qualifying {m['entry_qualifying_n']} median {m['entry_qualifying'].get('median')}% · "
          f"net {m['net']['measured_pct']}% measured", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
