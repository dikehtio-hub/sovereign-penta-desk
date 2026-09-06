"""Cascade microstructure -> wiki/concepts/cascade_anatomy.md (Round 105, backlog B1).

    python -m knowledge.ingest.cascade_anatomy [--result PATH]

The verdict page answers "did fading cascades pay?" (no: INSUFFICIENT, and FAIL on the probability
had the sample qualified). This page answers the different question of WHAT THE DATA LOOKS LIKE -
the two structural facts a reader needs before they trust or dispute that verdict:

  1. THE TWO SIDES BEHAVE DIFFERENTLY, AND NEITHER IS A FINDING. Side A (fade a sell cascade by
     buying) has a median ratio far below 1: price kept falling, momentum persisted. Side B (fade a
     buy cascade by selling) has a median ratio ABOVE the 1.25 acceptance threshold. That is the one
     eye-catching number in the whole experiment and it does not survive: its own cluster P is well
     under the PASS bar, its dollar expectancy is NEGATIVE, and the registration grades the POOLED
     metric only - the sides are a required separate report (commitment 5), never separately graded.
  2. HALF THE TABLE IS SYNTHETIC. `EXCURSION_CONTROL_MULTIPLE = 1` means every persisted event gets
     exactly one matched random-entry control row, so `raw_loaded / total_in_table` is 0.5 by
     construction. An exact half looks like a truncation bug until you know that; this page pins the
     constant with `dev.parameters` so the claim cannot drift away from the code.

THE MEDIAN/MEAN DIVERGENCE IS THE REAL STORY. Side B's median ratio is above 1 while its MEAN ratio
is well below 1. Typical B cascades revert modestly; the tail runs violently against the fade. That
is why a median above the threshold coexists with a negative dollar expectancy, and it is the exact
shape of risk that a median-only reading hides. Recorded here because it is the strongest argument
for the pre-registration's choice of a clustered, pooled metric.

Compiled from the engine's own artifact - never from numbers quoted in a message. The figures move:
between Round 104's run and this one the table grew 262 rows and side B's ratio moved 1.7378 ->
1.7135 with its P 0.4808 -> 0.4823.

Read-only. Writes only through pages.write_page.
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
from ..pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc,
                     page_path, write_index, write_page)
from . import add_common_args, at_from, guard, item_link, link_if_exists, md_cell, page_changed, rel_to
from .cascade_replay import DEFAULT_RESULT, STEM as VERDICT_STEM, written_at

STEM = "cascade_anatomy"
SETTINGS_FILE = Path("HyperLiquid") / "HL_Monarch" / "config" / "settings.py"
CONTROL_CONST = "EXCURSION_CONTROL_MULTIPLE"
SIDES = (("side_A_sell_fade_buys", "A", "sell cascade, faded by buying"),
         ("side_B_buy_fade_sells", "B", "buy cascade, faded by selling"))


def read_control_multiple(dev_root: Path) -> int | None:
    """The constant that makes the table exactly half synthetic, read from settings.py."""
    try:
        text = (dev_root / SETTINGS_FILE).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(rf"^{CONTROL_CONST}\s*=\s*(\d+)", text, re.M)
    return int(m.group(1)) if m else None


def control_audit(art: dict[str, Any], multiple: int | None) -> dict[str, Any]:
    """Check the 1-to-1 control claim ARITHMETICALLY rather than asserting it."""
    a = art.get("data_audit") or {}
    total, loaded = a.get("total_in_table"), a.get("raw_loaded")
    share = round(loaded / total, 6) if total else None
    expected = round(1.0 / (1 + multiple), 6) if multiple is not None else None
    return {
        "total_in_table": total, "raw_loaded": loaded, "treatment_share": share,
        "control_multiple": multiple, "expected_share": expected,
        "holds": share is not None and expected is not None and abs(share - expected) < 1e-6,
        "qualifying": a.get("qualifying_count"), "truncated": a.get("truncated_count"),
        "null_30m": a.get("null_30m_count"),
        "excluded": (loaded - a["qualifying_count"]) if loaded is not None and a.get("qualifying_count") is not None else None,
        # derived, not assumed: if the exclusions number exactly the nulls, truncation is contained in them
        "truncation_within_null": (loaded is not None and a.get("qualifying_count") is not None
                                   and a.get("null_30m_count") is not None
                                   and loaded - a["qualifying_count"] == a["null_30m_count"]),
    }


def _f(v, spec: str = ".4f") -> str:
    return "-" if v is None else format(float(v), spec)


def build_page(art: dict[str, Any], vault: Path, dev_root: Path, result: Path, at: datetime,
               multiple: int | None, by: str = GENERATED_BY) -> Page:
    asym = art.get("asymmetry") or {}
    audit = control_audit(art, multiple)
    stamp, stamp_from = written_at(art, result)
    threshold = (art.get("primary_metric") or {}).get("acceptance_threshold", 1.25)
    path = page_path(vault, "Concept", STEM)
    existing = load_page(path)
    history = [dict(r) for r in ((existing.meta.get("dev") or {}).get("history") or [])] if existing else []
    row = {"at": iso(at), "artifact_written_at": stamp, "rows_in_table": audit["total_in_table"],
           "side_a_median": (asym.get(SIDES[0][0]) or {}).get("median_fade_ratio_30m"),
           "side_b_median": (asym.get(SIDES[1][0]) or {}).get("median_fade_ratio_30m"),
           "side_b_cluster_p": (asym.get(SIDES[1][0]) or {}).get("cluster_p_ge_1_25")}
    if history and history[-1].get("artifact_written_at") == row["artifact_written_at"]:
        row["at"] = history[-1].get("at", row["at"])   # same artifact, same observation (R104-3)
        history[-1] = row
    else:
        history.append(row)

    body = [
        "# Cascade anatomy", "",
        "> What the cascade excursion data looks like structurally. The verdict is on the replay "
        "verdict page; this page is the shape of the data underneath it.", "",
        "## 1. The two sides are not symmetric", "",
        f"| Side | direction | n | median ratio 30m | mean ratio 30m | $ expectancy | P(>= {threshold}) |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, letter, direction in SIDES:
        d = asym.get(key) or {}
        body.append(f"| **{letter}** | {md_cell(direction)} | {d.get('n', 0):,} | "
                    f"{_f(d.get('median_fade_ratio_30m'))} | {_f(d.get('mean_fade_ratio_30m'))} | "
                    f"{_f(d.get('dollar_expectancy'))} | {_f(d.get('cluster_p_ge_1_25'))} |")
    a, b = (asym.get(SIDES[0][0]) or {}), (asym.get(SIDES[1][0]) or {})
    body += [
        "", "### Side A: momentum persists", "",
        f"A median ratio of **{_f(a.get('median_fade_ratio_30m'))}** means the adverse excursion was "
        f"roughly {1 / float(a.get('median_fade_ratio_30m') or 1):.1f}x the favourable one. Buying into a "
        "sell cascade did not catch a reversal; it caught more selling. With a cluster P of "
        f"**{_f(a.get('cluster_p_ge_1_25'))}** this is the clearest single result in the experiment, and it "
        "is a negative one.", "",
        "### Side B: the number that looks like alpha and is not", "",
        f"A median ratio of **{_f(b.get('median_fade_ratio_30m'))}** sits above the {threshold} acceptance "
        "threshold, and it is the only figure anywhere in this experiment that does. Three things stop it "
        "from being a finding:", "",
        f"1. **Its own cluster P is {_f(b.get('cluster_p_ge_1_25'))}**, nowhere near the 0.90 a PASS needs. "
        "Resampling coins - not events, because forward windows on one coin overlap - dissolves it.",
        f"2. **Its dollar expectancy is {_f(b.get('dollar_expectancy'))}**, i.e. negative. A ratio above 1 "
        "that loses money is telling you the ratio is not measuring what pays.",
        "3. **The registration does not grade sides.** The acceptance bar governs the pooled "
        "`fade_ratio_30m`; both sides are a required separate report (commitment 5). Grading a side split "
        "against the pooled bands is a post-hoc test the pre-registration exists to forbid.", "",
        "### The median/mean divergence is the real signal", "",
    ]
    bm, bmean = b.get("median_fade_ratio_30m"), b.get("mean_fade_ratio_30m")
    if bm and bmean:
        body += [
            f"Side B's median ratio is **{_f(bm)}** while its mean ratio is **{_f(bmean)}**. The typical buy "
            "cascade reverts modestly; the average one does not, because a minority run violently against the "
            "fade and dominate the mean. That single fact reconciles a median above the threshold with a "
            "negative expectancy, and it is the exact risk shape a median-only reading conceals: many small "
            "wins, occasional large losses. It is also the strongest argument for the pre-registration's "
            "insistence on a clustered, pooled metric rather than a headline median.", "",
        ]
    body += [
        "## 2. Half the table is synthetic, by construction", "",
        f"`{CONTROL_CONST} = {multiple}` in `{SETTINGS_FILE.as_posix()}`: every persisted event gets exactly "
        f"{multiple} matched random-entry control row. So of **{audit['total_in_table']:,}** rows in "
        f"`cascade_excursions`, the replay loads **{audit['raw_loaded']:,}** treatment rows - a share of "
        f"**{audit['treatment_share']}** against an expected **{audit['expected_share']}**: "
        + ("**the identity holds**." if audit["holds"] else "**THE IDENTITY DOES NOT HOLD - investigate.**"), "",
        "An exact 50/50 split reads like a truncation bug to anyone who has not seen the constant, which is "
        "why it is pinned here rather than described. Controls are excluded by "
        "`event_id > 0 AND source NOT LIKE 'control:%'`; they exist so a future run can ask whether cascade "
        "entries beat random ones, a question this replay does not attempt.", "",
        "### The two exclusion filters overlap", "",
        f"Of {audit['raw_loaded']:,} loaded rows, **{audit['qualifying']:,}** qualify: {audit['excluded']:,} are "
        f"excluded. But the two reported filters are {audit['truncated']:,} truncated (incomplete forward "
        f"series) and {audit['null_30m']:,} null at 30 minutes, which sum to "
        f"{audit['truncated'] + audit['null_30m']:,} - more than the exclusions, because a row can fail both. "
        + (f"In this artifact the excluded count equals the null count exactly, so **every truncated row is "
           "also a null-30m row**: truncation is a subset of nullity here, not an independent filter."
           if audit["truncation_within_null"] else
           "The two sets are not in a containment relationship in this artifact.")
        + " Stated because adding the two filters will not reproduce the qualifying count.", "",
        "## Provenance", "",
        f"- artifact written **{stamp}** (source: {stamp_from})",
        "- These figures move between runs because the collector is live. Round 104 measured side B at "
        "1.7378 with P 0.4808 over 29,350 rows; this page recompiles from whatever the artifact currently "
        "says, which is the only reason the two can be compared at all.", "",
        "## History", "", "| At | artifact written | rows | side A median | side B median | side B P |",
        "|---|---|---|---|---|---|",
    ]
    body += [f"| {h['at']} | {h.get('artifact_written_at')} | {h.get('rows_in_table'):,} | "
             f"{_f(h.get('side_a_median'))} | {_f(h.get('side_b_median'))} | {_f(h.get('side_b_cluster_p'))} |"
             for h in history]
    body += ["", "## Related", "",
             link_if_exists(vault, "Experiment", VERDICT_STEM, "The replay verdict"),
             link_if_exists(vault, "Experiment", "whale_sweeper_cascade_replay_meta",
                            "The pre-registration (B15)"),
             item_link(vault, "Item_14_Hyperliquid_Whale_Cascade_Sweeper", "Item 14: Whale Cascade Sweeper"),
             "- [[Desk_01_HyperLiquid_Monarch|Desk 1: HyperLiquid Monarch]]", ""]

    dev: dict[str, Any] = {
        "desk": 1, "item": 14, "kind": "cascade_anatomy", "control_audit": audit,
        "asymmetry": {letter: asym.get(key) for key, letter, _ in SIDES},
        "artifact_written_at": stamp, "artifact_written_at_from": stamp_from,
        "requires_files": [SETTINGS_FILE.as_posix()], "history": history,
    }
    if multiple is not None:
        dev["parameters"] = [{"name": "excursion_control_multiple", "value": multiple,
                              "file": SETTINGS_FILE.as_posix(),
                              "pattern": rf"^{CONTROL_CONST}\s*=\s*(\d+)"}]
    meta = make_meta("Concept", "Cascade anatomy",
                     f"Microstructure of the cascade excursion table: side A median "
                     f"{_f(a.get('median_fade_ratio_30m'))} (momentum persists) against side B "
                     f"{_f(b.get('median_fade_ratio_30m'))} (which does not survive clustering, P "
                     f"{_f(b.get('cluster_p_ge_1_25'))}), and the 1-to-1 synthetic control matching that makes "
                     "the table exactly half controls.",
                     tags=["concept", "desk-1", "item-14", "cascade", "microstructure"],
                     generated_by=by, at=at, status="draft",
                     sources=[{"id": "replay-json", "resource": rel_to(result, dev_root),
                               "title": "cascade_replay --json artifact",
                               "author": "process:HyperLiquid.HL_Monarch.analytics.cascade_replay"},
                              {"id": "control-constant", "resource": SETTINGS_FILE.as_posix(),
                               "title": f"{CONTROL_CONST}", "author": "human:operator"}],
                     dev=dev)
    carry_human_fields(existing, meta)
    return Page(path, meta, "\n".join(body))


def ingest_anatomy(vault: Path, dev_root: Path, *, result: Path | None = None, at: datetime | None = None,
                   by: str = GENERATED_BY) -> Page | None:
    at = at or now_utc()
    result = result or (dev_root / DEFAULT_RESULT)
    if not result.is_file():
        return None
    art = json.loads(result.read_text(encoding="utf-8"))
    if not (art.get("asymmetry") and art.get("data_audit")):
        return None
    page = build_page(art, vault, dev_root, result, at, read_control_multiple(dev_root), by)
    changed = page_changed(page, vault)
    write_page(page, vault, now=at)
    write_index(vault, load_pages(vault))
    if changed:
        audit = page.meta["dev"]["control_audit"]
        append_log(vault, "Ingest", f"cascade anatomy: {audit['total_in_table']:,} row(s), treatment share "
                   f"{audit['treatment_share']} ({'1-to-1 control identity holds' if audit['holds'] else 'IDENTITY BROKEN'}) "
                   f"-> [[{STEM}]].", when=at)
    return page


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.ingest.cascade_anatomy", description=__doc__.split("\n\n")[0])
    add_common_args(ap)
    ap.add_argument("--result", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_RESULT.as_posix()}")
    args = ap.parse_args(argv)
    code = guard(args, out)
    if code is not None:
        return code
    page = ingest_anatomy(args.vault, args.dev_root, result=args.result, at=at_from(args))
    if page is None:
        print("[REFUSE] the replay artifact is missing or carries no asymmetry/data_audit block. Run:\n"
              "  python -m HyperLiquid.HL_Monarch.analytics.cascade_replay --json --out "
              f"{DEFAULT_RESULT.as_posix()}\n(exit 3)", file=out)
        return 3
    audit = page.meta["dev"]["control_audit"]
    print(f"[WRITE] {page.path.relative_to(args.vault).as_posix()}", file=out)
    print(f"anatomy: {audit['total_in_table']:,} rows · treatment share {audit['treatment_share']} · "
          f"control identity {'holds' if audit['holds'] else 'BROKEN'}", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
