"""The trading-day journal and the calibration ledger (Round 100, B10; Ratification R95-F).

    python -m knowledge.journal --date 2026-09-05 [--create] [--receipts DIR] [--at ISO]
    python -m knowledge.journal --predict --event fomc_2026-09-16 --field change_bps --op == --value 0 --p 0.9 [--date D]
    python -m knowledge.journal --score [--at ISO]

ONE PAGE PER TRADING DAY, journal/YYYY-MM-DD.md, written when PAPER receipts exist
for that day or on --create (a quiet day is a legitimate entry). Five sections:
  Plan                 human; preserved across re-runs like a CRM judgement
  Executions           machine; one row per CSV receipt under cross_market/data/paper_receipts
                       (the Tax Reserve Agent writer's columns: timestamp, symbol, side,
                       quantity, price, fee, tx_hash, source, notes); paper by location
  Calibration ledger   machine; rows from dev.predictions (see below)
  Debrief              machine; the day's paper notional against the quant lab's daily
                       killswitch as a drawdown budget, per-strategy totals, and an honest
                       UNCHECKED for the after-tax hurdle: the receipt writer records no edge
  Open                 human; preserved

THE CALIBRATION LEDGER. `--predict` records a probability BEFORE an event as a row
{event, field, op, value, p, at, by: human:operator, outcome: null, brier: null}.
`--score` resolves every unscored row against the Event page's `dev.payload`
(written by knowledge.ingest.clob after the print): outcome = 1 if `field op value`
holds, Brier = (p - outcome)^2, and rebuilds wiki/concepts/calibration.md (count,
mean Brier against the 0.25 always-0.5 baseline, a reliability table by p-bin). A
prediction is never edited after it is written.

The debrief places no orders and changes no threshold (R95-F). Journal pages are
never stale (B14). The Journal register is rebuilt after every run.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from . import DEV_ROOT, EXIT_HALT, EXIT_OK, GENERATED_BY, VAULT, halted
from .frontmatter import parse_iso8601
from .pages import (Page, append_log, carry_human_fields, iso, load_page, load_pages, make_meta, now_utc, page_path,
                    write_index, write_page)
from .registers import write_register

DEFAULT_RECEIPTS = Path("cross_market") / "data" / "paper_receipts"
KILLSWITCH_FILE = Path("quant_trading_lab") / "CLAUDE.md"
KILLSWITCH_PATTERN = r"Hard Daily Drawdown Killswitch: \$([0-9,\.]+)"
CALIBRATION_FILE = "calibration"
OPS = ("==", "!=", ">=", "<=", ">", "<")
PLAN_HEADING, OPEN_HEADING = "## Plan", "## Open"
PLAN_PLACEHOLDER = "_(operator: intent, desks in play, the Risk Sentinel buffer, events registered today)_"
OPEN_PLACEHOLDER = "_(operator and agent: questions that became Concept pages, rulings requested, lint items)_"


# ---------------------------------------------------------------- receipts

@dataclass
class Execution:
    at: str
    symbol: str
    side: str
    quantity: float
    price: float
    fee: float
    venue: str
    strategy: str
    file: str
    edge: float | None = None     # from notes `edge:0.9950;` (Round 101, Ruling 100-b)
    hurdle: float | None = None   # from notes `hurdle:0.9820;`

    @property
    def notional(self) -> float:
        return round(self.quantity * self.price, 2)

    @property
    def hurdle_check(self) -> str:
        if self.edge is None or self.hurdle is None:
            return "UNCHECKED"
        return "PASS" if self.edge >= self.hurdle else "FLAG"


def _strategy_of(row: dict[str, str], filename: str) -> str:
    m = re.search(r"strategy[=:]\s*([A-Za-z0-9_\-]+)", row.get("notes") or "", re.I)
    if m:
        return m.group(1)
    parts = filename.split("_")
    return parts[2] if filename.startswith("fills_") and len(parts) > 3 else "unknown"


def _note_number(row: dict[str, str], key: str) -> float | None:
    m = re.search(rf"\b{key}[=:]\s*(-?[0-9]*\.?[0-9]+)", row.get("notes") or "", re.I)
    return float(m.group(1)) if m else None


def load_executions(receipts_dir: Path, day: date) -> list[Execution]:
    out: list[Execution] = []
    if not receipts_dir.is_dir():
        return out
    for path in sorted(receipts_dir.glob("*.csv")):
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    ts = str(row.get("timestamp") or "")
                    if not ts.startswith(day.isoformat()):
                        continue
                    out.append(Execution(
                        at=ts, symbol=str(row.get("symbol") or ""), side=str(row.get("side") or "").upper(),
                        quantity=float(row.get("quantity") or 0), price=float(row.get("price") or 0),
                        fee=float(row.get("fee") or 0), venue=str(row.get("source") or ""),
                        strategy=_strategy_of(row, path.name), file=path.name,
                        edge=_note_number(row, "edge"), hurdle=_note_number(row, "hurdle")))
        except (OSError, ValueError, csv.Error):
            continue
    return out


def _killswitch(dev_root: Path) -> tuple[float | None, dict[str, Any] | None]:
    f = dev_root / KILLSWITCH_FILE
    if not f.is_file():
        return None, None
    m = re.search(KILLSWITCH_PATTERN, f.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return None, None
    value = float(m.group(1).replace(",", ""))
    return value, {"name": "daily_drawdown_killswitch_usd", "value": m.group(1), "file": KILLSWITCH_FILE.as_posix(),
                   "pattern": KILLSWITCH_PATTERN}


# ---------------------------------------------------------------- sections kept across runs

def _section(existing: Page | None, heading: str, placeholder: str) -> str:
    if existing is None:
        return placeholder
    m = re.search(rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", existing.body, re.S | re.M)
    text = m.group(1).strip() if m else ""
    return text or placeholder


# ---------------------------------------------------------------- the page

def claim_text(p: dict[str, Any]) -> str:
    if p.get("claim"):
        return str(p["claim"])
    return f"{p.get('field')} {p.get('op')} {p.get('value')}"


def _brier(v: Any) -> str:
    return "-" if v is None else f"{float(v):.4f}"


def build_journal(day: date, executions: list[Execution], predictions: list[dict[str, Any]], vault: Path, dev_root: Path,
                  at: datetime, by: str = GENERATED_BY) -> Page:
    path = page_path(vault, "Journal Entry", day.isoformat())
    existing = load_page(path)
    budget, param = _killswitch(dev_root)
    total = round(sum(e.notional for e in executions), 2)
    by_strategy: dict[str, float] = {}
    for e in executions:
        by_strategy[e.strategy] = round(by_strategy.get(e.strategy, 0.0) + e.notional, 2)
    body = [f"# Journal {day.isoformat()}", "", f"> {len(executions)} paper execution(s) · {len(predictions)} prediction(s) on the ledger", "",
            PLAN_HEADING, "", _section(existing, PLAN_HEADING, PLAN_PLACEHOLDER), "",
            "## Executions (paper receipts; paper by location)", ""]
    if executions:
        body += ["| at | venue | strategy | symbol | side | qty | price | notional | fee | edge | hurdle | check | receipt |",
                 "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        body += [f"| {e.at} | {e.venue} | {e.strategy} | {e.symbol} | {e.side} | {e.quantity:g} | {e.price:g} | ${e.notional:,.2f} | {e.fee:g} | "
                 f"{'-' if e.edge is None else f'{e.edge:.4f}'} | {'-' if e.hurdle is None else f'{e.hurdle:.4f}'} | {e.hurdle_check} | `{e.file}` |"
                 for e in executions]
    else:
        body.append("_(no paper receipts for this day)_")
    body += ["", "## Calibration ledger", ""]
    if predictions:
        body += ["| at | event | claim | p | outcome | Brier | scored |", "|---|---|---|---|---|---|---|"]
        body += [f"| {p.get('at')} | [[{p.get('event')}]] | `{claim_text(p)}` | {float(p.get('p')):.2f} | "
                 f"{'-' if p.get('outcome') is None else p.get('outcome')} | {_brier(p.get('brier'))} | "
                 f"{p.get('scored_at') or '-'} |" for p in predictions]
    else:
        body.append("_(no predictions recorded; `knowledge.journal --predict --event E --field F --op OP --value V --p P`)_")
    body += ["", "## Debrief (machine; paper only, R95-F)", ""]
    debrief: dict[str, Any] = {"executions": len(executions), "turnover_total": total, "by_strategy": by_strategy}
    if executions:
        # Ruling 100-c: the killswitch is a cumulative realised-loss budget, not a volume ceiling. Receipts are
        # fills, so realised net loss needs paired closes; until then the drawdown check is honestly UNCHECKED
        # and the volume is labelled for what it is.
        body.append(f"- Daily Paper Notional Turnover: ${total:,.2f}" + (f" (reference: quant lab daily killswitch ${budget:,.2f}, a realised-loss budget, "
                    "not a turnover ceiling)" if budget is not None else ""))
        debrief["drawdown_check"] = "UNCHECKED"
        debrief["drawdown_budget_usd"] = budget
        body.append("- drawdown vs killswitch: UNCHECKED - receipts are fills; realised net loss needs paired closes (Ruling 100-c)")
        checks = [e.hurdle_check for e in executions]
        if "FLAG" in checks:
            debrief["hurdle_check"] = "FLAG"
        elif "PASS" in checks:
            debrief["hurdle_check"] = "PASS"
        else:
            debrief["hurdle_check"] = "UNCHECKED"
        debrief["hurdle_counts"] = {k: checks.count(k) for k in ("PASS", "FLAG", "UNCHECKED") if checks.count(k)}
        body.append(f"- after-tax hurdle (from receipt notes `edge:`/`hurdle:`, Ruling 100-b): **{debrief['hurdle_check']}** · "
                    + ", ".join(f"{k} {v}" for k, v in debrief["hurdle_counts"].items())
                    + ("; an UNCHECKED fill carries no edge/hurdle on its receipt" if "UNCHECKED" in checks else ""))
        body += [f"- per strategy turnover: " + ", ".join(f"{k} ${v:,.2f}" for k, v in sorted(by_strategy.items()))]
    else:
        debrief["drawdown_check"] = debrief["hurdle_check"] = "N/A"
        body.append("- nothing to check: no paper executions today")
    body += ["", OPEN_HEADING, "", _section(existing, OPEN_HEADING, OPEN_PLACEHOLDER), "",
             "## Related", ""]
    # Round 105 (lint L8): the calibration ledger is written by --score, so a day page compiled
    # before any prediction has been scored would link a page that is not there.
    body += [f"- [[{CALIBRATION_FILE}|Calibration]]" if page_path(vault, "Concept", CALIBRATION_FILE).is_file()
             else "- Calibration ledger - not written yet (no scored predictions)"]
    body += ["- [[journal_register|Journal register]]", ""]
    dev: dict[str, Any] = {"date": day.isoformat(), "receipts": len(executions), "turnover_total": total, "predictions_n": len(predictions),
                           "predictions": predictions, "debrief": debrief}
    if param:
        dev["parameters"] = [param]
    scored = [p for p in predictions if p.get("brier") is not None]
    desc = (f"Journal {day.isoformat()}: {len(executions)} paper execution(s), ${total:,.0f} turnover"
            + (f", {len(scored)}/{len(predictions)} prediction(s) scored" if predictions else "") + ".")
    meta = make_meta("Journal Entry", f"Journal {day.isoformat()}", desc, tags=["journal", day.isoformat()[:7]],
                     generated_by=by, at=at, status="draft", dev=dev)
    carry_human_fields(existing, meta)
    return Page(path, meta, "\n".join(body))


def existing_predictions(vault: Path, day: date) -> list[dict[str, Any]]:
    page = load_page(page_path(vault, "Journal Entry", day.isoformat()))
    if page is None:
        return []
    return [dict(p) for p in (page.meta.get("dev") or {}).get("predictions", []) if isinstance(p, dict)]


def write_day(vault: Path, dev_root: Path, day: date, *, receipts_dir: Path | None = None, at: datetime | None = None,
              by: str = GENERATED_BY, create: bool = False, predictions: list[dict[str, Any]] | None = None) -> Page | None:
    at = at or now_utc()
    execs = load_executions(receipts_dir or (dev_root / DEFAULT_RECEIPTS), day)
    preds = predictions if predictions is not None else existing_predictions(vault, day)
    exists = page_path(vault, "Journal Entry", day.isoformat()).exists()
    if not execs and not preds and not create and not exists:
        return None
    page = build_journal(day, execs, preds, vault, dev_root, at, by)
    write_page(page, vault, now=at)
    write_register(vault, "Journal Entry", at=at, by=by)
    write_index(vault, load_pages(vault))
    return page


# ---------------------------------------------------------------- predictions and scoring

def add_prediction(vault: Path, dev_root: Path, day: date, *, event: str, p: float, field_: str | None = None, op: str | None = None,
                   value: Any = None, claim: str | None = None, at: datetime | None = None, by_human: str = "human:operator") -> Page:
    """A mechanical rule {field, op, value} (scored against the Event payload) or a free-text `claim`
    (scored by hand with --score --event E --outcome 0|1; Ruling 100-a)."""
    if claim is None:
        if op not in OPS:
            raise ValueError(f"op must be one of {OPS}")
        if not field_ or value is None:
            raise ValueError("a mechanical prediction needs field, op and value")
    elif not str(claim).strip():
        raise ValueError("a free-text claim must not be empty")
    if not (0.0 < float(p) < 1.0):
        raise ValueError("p must be strictly between 0 and 1")
    at = at or now_utc()
    preds = existing_predictions(vault, day)
    row: dict[str, Any] = {"event": event, "p": float(p), "at": iso(at), "by": by_human, "outcome": None, "brier": None, "scored_at": None}
    if claim is None:
        row.update({"field": field_, "op": op, "value": value})
    else:
        row["claim"] = str(claim).strip()
    preds.append(row)
    page = write_day(vault, dev_root, day, at=at, create=True, predictions=preds)
    assert page is not None
    append_log(vault, "Journal", f"prediction on [[{event}]]: `{claim_text(row)}` with p={float(p):.2f} recorded in [[{day.isoformat()}]].", when=at)
    return page


def _holds(actual: Any, op: str, value: Any) -> bool | None:
    try:
        a, v = float(actual), float(value)
    except (TypeError, ValueError):
        a, v = str(actual), str(value)
        if op not in ("==", "!="):
            return None
    return {"==": a == v, "!=": a != v, ">=": a >= v, "<=": a <= v, ">": a > v, "<": a < v}[op]


def score_predictions(vault: Path, dev_root: Path, *, at: datetime | None = None, by: str = GENERATED_BY,
                      event: str | None = None, manual_outcome: int | None = None) -> dict[str, int]:
    """Mechanical rules score against the Event payload. A free-text claim scores only when the operator
    passes `event` and `manual_outcome` (0|1), which is recorded as `scored_by: human:operator`."""
    at = at or now_utc()
    scored = pending = 0
    for page in load_pages(vault):
        if page.type != "Journal Entry":
            continue
        preds = [dict(p) for p in (page.meta.get("dev") or {}).get("predictions", []) if isinstance(p, dict)]
        changed = False
        for p in preds:
            if p.get("brier") is not None:
                continue
            if p.get("claim"):                                   # free text: manual outcome for this event only
                if manual_outcome is None or event is None or p.get("event") != event:
                    pending += 1
                    continue
                outcome = 1 if int(manual_outcome) else 0
                p["scored_by"] = "human:operator"
            else:
                ev = load_page(page_path(vault, "Event", str(p.get("event"))))
                payload = (ev.meta.get("dev") or {}).get("payload") if ev else None
                if not isinstance(payload, dict) or p.get("field") not in payload:
                    pending += 1
                    continue
                holds = _holds(payload[p["field"]], str(p.get("op")), p.get("value"))
                if holds is None:
                    pending += 1
                    continue
                outcome = 1 if holds else 0
            p["outcome"] = outcome
            p["brier"] = round((float(p["p"]) - outcome) ** 2, 4)
            p["scored_at"] = iso(at)
            scored += 1
            changed = True
        if changed:
            day = date.fromisoformat(str((page.meta.get("dev") or {}).get("date")))
            write_day(vault, dev_root, day, at=at, by=by, create=True, predictions=preds)
    write_page(build_calibration(vault, at, by), vault, now=at)
    write_index(vault, load_pages(vault))
    if scored:
        append_log(vault, "Journal", f"scored {scored} prediction(s) against Event payloads; {pending} still pending; [[{CALIBRATION_FILE}]] rebuilt.", when=at)
    return {"scored": scored, "pending": pending}


def build_calibration(vault: Path, at: datetime, by: str = GENERATED_BY) -> Page:
    rows: list[dict[str, Any]] = []
    for page in load_pages(vault):
        if page.type != "Journal Entry":
            continue
        for p in (page.meta.get("dev") or {}).get("predictions", []):
            if isinstance(p, dict) and p.get("brier") is not None:
                rows.append(dict(p, journal=page.path.stem))
    rows.sort(key=lambda r: str(r.get("at")))
    n = len(rows)
    mean = round(sum(float(r["brier"]) for r in rows) / n, 4) if n else None
    bins = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
    table = ["| p bin | n | mean p | observed | gap |", "|---|---|---|---|---|"]
    reliability: list[dict[str, Any]] = []
    for lo, hi in bins:
        sel = [r for r in rows if lo <= float(r["p"]) < hi or (hi == 1.0 and float(r["p"]) == 1.0)]
        if not sel:
            continue
        mp = sum(float(r["p"]) for r in sel) / len(sel)
        obs = sum(int(r["outcome"]) for r in sel) / len(sel)
        reliability.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(sel), "mean_p": round(mp, 3), "observed": round(obs, 3)})
        table.append(f"| {lo:.1f}-{hi:.1f} | {len(sel)} | {mp:.2f} | {obs:.2f} | {obs - mp:+.2f} |")
    body = ["# Calibration", "", "> Every scored prediction from the journal ledgers. Brier = (p - outcome)^2; 0.25 is the always-0.5 baseline,",
            "> 0 is perfect. A reliability gap near 0 in every bin means the operator's 90 % is a 90 %.", "",
            "## Summary", "", f"- scored predictions: {n}", f"- mean Brier: {mean if mean is not None else '-'}", "",
            "## Reliability", ""] + (table if len(table) > 2 else ["_(no scored predictions yet)_"]) + ["", "## Ledger", ""]
    if rows:
        body += ["| at | journal | event | claim | p | outcome | Brier |", "|---|---|---|---|---|---|---|"]
        body += [f"| {r.get('at')} | [[{r['journal']}]] | [[{r.get('event')}]] | `{claim_text(r)}` | {float(r['p']):.2f} | {r['outcome']} | {float(r['brier']):.4f} |"
                 for r in rows]
    else:
        body.append("_(empty)_")
    body += ["", "## Related", "", "- [[journal_register|Journal register]]", "- [[Desk_03_Cross_Market_Desk|Desk 3: Cross-Market Desk]]", ""]
    meta = make_meta("Concept", "Calibration", f"Operator calibration across {n} scored prediction(s); mean Brier {mean if mean is not None else '-'}.",
                     tags=["concept", "calibration", "journal"], generated_by=by, at=at, status="draft",
                     dev={"count": n, "mean_brier": mean, "reliability": reliability, "history": rows})
    path = page_path(vault, "Concept", CALIBRATION_FILE)
    carry_human_fields(load_page(path), meta)
    return Page(path, meta, "\n".join(body))


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="knowledge.journal", description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", type=Path, default=VAULT)
    ap.add_argument("--dev-root", type=Path, default=DEV_ROOT)
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today in UTC, or the date of --at)")
    ap.add_argument("--at", default=None)
    ap.add_argument("--create", action="store_true", help="write the day's page even with no receipts and no predictions")
    ap.add_argument("--receipts", type=Path, default=None, help=f"default <dev-root>/{DEFAULT_RECEIPTS.as_posix()}")
    ap.add_argument("--predict", action="store_true")
    ap.add_argument("--event")
    ap.add_argument("--field")
    ap.add_argument("--op", choices=OPS)
    ap.add_argument("--value")
    ap.add_argument("--p", type=float)
    ap.add_argument("--claim", default=None, help="free-text prediction (scored later with --score --event E --outcome 0|1)")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--outcome", type=int, choices=[0, 1], default=None, help="with --score --event: manual outcome for free-text claims")
    args = ap.parse_args(argv)
    if halted(args.dev_root):
        print(f"[HALT] {args.dev_root / 'HALT.flag'} present - journal refuses (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    if not args.vault.is_dir():
        print(f"[REFUSE] vault not found: {args.vault} (exit {EXIT_HALT})", file=out)
        return EXIT_HALT
    at = parse_iso8601(args.at) if args.at else now_utc()
    day = date.fromisoformat(args.date) if args.date else at.astimezone(timezone.utc).date()
    if args.predict:
        mechanical = args.field and args.op and args.value is not None
        if not (args.event and args.p is not None and (mechanical or args.claim)):
            print("[REFUSE] --predict needs --event --p and either --field --op --value or --claim (exit 3)", file=out)
            return EXIT_HALT
        value: Any = args.value
        if mechanical:
            try:
                value = int(value) if re.fullmatch(r"-?\d+", value) else float(value)
            except ValueError:
                pass
        try:
            page = add_prediction(args.vault, args.dev_root, day, event=args.event, p=args.p, at=at,
                                  field_=args.field if mechanical else None, op=args.op if mechanical else None,
                                  value=value if mechanical else None, claim=None if mechanical else args.claim)
        except ValueError as exc:
            print(f"[REFUSE] {exc} (exit 3)", file=out)
            return EXIT_HALT
        print(f"[WRITE] {page.path.relative_to(args.vault).as_posix()}  prediction recorded", file=out)
        return EXIT_OK
    if args.score:
        if args.outcome is not None and not args.event:
            print("[REFUSE] --outcome needs --event (exit 3)", file=out)
            return EXIT_HALT
        res = score_predictions(args.vault, args.dev_root, at=at, event=args.event, manual_outcome=args.outcome)
        print(f"journal: scored {res['scored']}, pending {res['pending']}; calibration rebuilt", file=out)
        return EXIT_OK
    page = write_day(args.vault, args.dev_root, day, receipts_dir=args.receipts, at=at, create=args.create)
    if page is None:
        print(f"journal: no paper receipts and no predictions for {day.isoformat()}; nothing written (use --create for a quiet-day entry)", file=out)
        return EXIT_OK
    print(f"[WRITE] {page.path.relative_to(args.vault).as_posix()}  {page.meta['dev']['receipts']} execution(s), "
          f"{page.meta['dev']['predictions_n']} prediction(s)", file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
