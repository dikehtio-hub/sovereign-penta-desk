"""
Results drop-folder watcher.

Drop a CSV of settled outcomes into `Sports_Desk/data/results_drops/` and every
forecast the desk made about those selections becomes scoreable. Same three
failure modes as `odds_watcher` - half-written files, guessed data, double
imports - handled the same way, because a results file corrupts a calibration
score as quietly as an odds file corrupts an edge.

WHY THIS EXISTS. Until an outcome is recorded, nothing in this desk can tell a
good fair probability from a bad one. Closing-line value is a proxy and a useful
one, but it measures agreement with the market rather than agreement with
reality, and a book that is systematically wrong in the same direction as the
market will look excellent by CLV forever. A Brier score against settled results
is the only thing that closes that loop - and it is what should eventually
replace the hardcoded `SHARP_BOOKS` list, because sharpness is a property you
measure, not a name you recognise.

WHAT A RESULT ROW MEANS
  win / won / w / 1      this selection came in
  loss / lost / l / 0    it did not
  push / void / tie      NO OUTCOME TO SCORE. Recorded as voided and excluded
                         from every Brier computation - squaring a forecast
                         against a push is not a small error, it is a category
                         error, and it drags a real score toward the mean.

EXPECTED CSV SHAPE (column order irrelevant, names flexible):

    event_id,sport,market_type,line,selection,result,settled_at
    NFL_KC_BAL,NFL,moneyline,,Chiefs,win,2026-09-03T23:15:00Z
    NFL_KC_BAL,NFL,moneyline,,Ravens,loss,2026-09-03T23:15:00Z
    NFL_KC_BAL,NFL,spread,-3.5,Chiefs,push,2026-09-03T23:15:00Z

The key must match the odds side exactly - (event_id, market_type, line,
selection) - or the forecast and the outcome never meet and the row scores
nothing. Selections are matched on the same normalised key the odds watcher
uses, so case and whitespace are forgiven and nothing else is.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Sports_Desk.data.db import (DEFAULT_DB_PATH, already_imported_result,
                                 brier_score, init_market_db,
                                 record_brier_snapshot, record_result_import,
                                 record_settled_result, settle_placed_bets)
from Sports_Desk.ingestors.odds_watcher import _first, _truthy, content_hash

DEFAULT_RESULTS_FOLDER = Path(__file__).resolve().parent.parent / "data" / "results_drops"

WIN_WORDS = frozenset({"WIN", "WON", "W", "1", "TRUE", "YES", "WINNER", "HIT"})
LOSS_WORDS = frozenset({"LOSS", "LOST", "L", "0", "FALSE", "NO", "LOSER", "MISS"})
VOID_WORDS = frozenset({"PUSH", "VOID", "VOIDED", "TIE", "CANCELLED", "CANCELED",
                        "NO_ACTION", "REFUND", "REFUNDED", "POSTPONED"})

# Snapshots are only worth freezing once there is enough settled history for the
# number to mean anything. Below this a Brier score is noise wearing a decimal
# point, and storing it would put a trend line through nothing.
MIN_FORECASTS_FOR_SNAPSHOT = 20

DEFAULT_STABILITY_SECONDS = 1.0


class ResultImportError(ValueError):
    """A result row that cannot be interpreted. Never guessed - always raised."""


@dataclass
class ResultsReport:
    """What one file produced. Returned rather than printed so tests can assert."""
    filename: str = ""
    content_hash: str = ""
    rows_read: int = 0
    settled: int = 0
    voided: int = 0
    bets_settled: int = 0
    skipped: List[str] = field(default_factory=list)
    snapshots: List[Dict[str, Any]] = field(default_factory=list)
    duplicate: bool = False

    def summary(self) -> str:
        if self.duplicate:
            return f"[SKIP] {self.filename}: identical content already imported."
        parts = [f"[OK  ] {self.filename}: {self.rows_read} row(s), "
                 f"{self.settled} settled, {self.voided} voided"
                 + (f", {self.bets_settled} placed bet(s) closed out"
                    if self.bets_settled else "")]
        for snapshot in self.snapshots:
            skill = snapshot.get("skill_score")
            parts.append(
                f"[CAL ] {snapshot['sportsbook']}: Brier {snapshot['brier']:.4f} "
                f"vs baseline {snapshot['baseline_brier']:.4f} "
                f"(skill {skill:+.3f}) over {snapshot['forecasts']} forecast(s)")
        for reason in self.skipped:
            parts.append(f"[WARN] {reason}")
        return "\n".join(parts)


def parse_outcome(text: str) -> Tuple[int, bool]:
    """
    `(outcome, voided)`. Raises rather than guessing an unknown word, because a
    misread result is worse than an absent one: it scores a forecast against
    something that did not happen.
    """
    token = str(text or "").strip().upper().replace(" ", "_").replace("-", "_")
    if token in WIN_WORDS:
        return 1, False
    if token in LOSS_WORDS:
        return 0, False
    if token in VOID_WORDS:
        return 0, True
    raise ResultImportError(
        f"unknown result {text!r}. Known: win / loss / push / void.")


def parse_results_csv(path: Path) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """Reads a results drop file. Bad rows are skipped with a reason, never dropped."""
    rows: List[Dict[str, Any]] = []
    skipped: List[str] = []
    rows_read = 0

    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for line_no, raw in enumerate(csv.DictReader(handle), start=2):
            row = {str(k).strip().lower(): (v or "").strip()
                   for k, v in raw.items() if k}
            rows_read += 1
            event_id = _first(row, "event_id", "event", "game_id", "match_id")
            selection = _first(row, "selection", "outcome_name", "runner", "team", "pick")
            result = _first(row, "result", "outcome", "status", "settlement")
            if not (event_id and selection and result):
                skipped.append(f"{path.name}:{line_no} missing event/selection/result")
                continue
            try:
                outcome, voided = parse_outcome(result)
            except ResultImportError as e:
                skipped.append(f"{path.name}:{line_no} {e}")
                continue
            rows.append({
                "event_id": event_id,
                "sport": _first(row, "sport", "league") or "SPORTS",
                "market_type": _first(row, "market_type", "market", "bet_type") or "moneyline",
                "line": _first(row, "line", "handicap", "spread", "total", "points"),
                "selection": selection,
                "outcome": outcome,
                "voided": voided,
                "settled_at": _first(row, "settled_at", "settled", "timestamp",
                                     "completed_at", "date"),
            })
    return rows, rows_read, skipped


class ResultsWatcher:
    """
    Polls a results drop folder, settles what lands in it, and re-scores.

    `scan_once()` is the whole engine; `watch()` calls it on a timer. Both are
    safe to run repeatedly - a file is processed once because its content hash is
    recorded, and then MOVED out of the folder.
    """

    def __init__(self, drop_folder: Optional[Path] = None,
                 db_path: Optional[Path] = None,
                 stability_seconds: float = DEFAULT_STABILITY_SECONDS,
                 brier_window: Optional[int] = None,
                 min_forecasts: int = MIN_FORECASTS_FOR_SNAPSHOT,
                 archive: bool = True):
        self.drop_folder = Path(drop_folder or DEFAULT_RESULTS_FOLDER)
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.stability_seconds = float(stability_seconds)
        self.brier_window = brier_window
        self.min_forecasts = int(min_forecasts)
        self.archive = archive
        self._seen: Dict[Path, Tuple[int, float, float]] = {}
        self.drop_folder.mkdir(parents=True, exist_ok=True)
        init_market_db(self.db_path)

    def _is_stable(self, path: Path, now: Optional[float] = None) -> bool:
        """Identical size and mtime on two polls, `stability_seconds` apart."""
        now = time.time() if now is None else now
        try:
            stat = path.stat()
        except OSError:
            return False
        current = (stat.st_size, stat.st_mtime)
        previous = self._seen.get(path)
        if previous is None or previous[:2] != current:
            self._seen[path] = (current[0], current[1], now)
            return False
        return (now - previous[2]) >= self.stability_seconds

    def process_file(self, path: Path) -> ResultsReport:
        """Settles one file and re-scores every book it touched."""
        report = ResultsReport(filename=path.name)
        report.content_hash = content_hash(path)
        if already_imported_result(report.content_hash, db_path=self.db_path):
            report.duplicate = True
            return report

        rows, rows_read, skipped = parse_results_csv(path)
        report.rows_read = rows_read
        report.skipped.extend(skipped)
        now_ts = datetime.now(timezone.utc).isoformat()

        for row in rows:
            record_settled_result(
                event_id=row["event_id"], sport=row["sport"],
                market_type=row["market_type"], line=row["line"],
                selection=row["selection"], outcome=row["outcome"],
                voided=row["voided"], settled_at=row["settled_at"] or now_ts,
                source_file=path.name, content_hash=report.content_hash,
                db_path=self.db_path)
            if row["voided"]:
                report.voided += 1
            else:
                report.settled += 1

        # BRIDGE B: an outcome is only useful once it reaches the bets that were
        # actually staked on it. Without this join the desk has CLV and a Brier
        # score - a leading indicator and a grade for the BOOK - and no answer at
        # all to "did I make money".
        report.bets_settled = settle_placed_bets(db_path=self.db_path)
        report.snapshots = self.rescore(now_ts)
        record_result_import(report.content_hash, path.name, report.rows_read,
                             report.settled, timestamp=now_ts, db_path=self.db_path)
        return report

    def rescore(self, measured_at: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Recomputes the rolling Brier for every book with scored forecasts, and
        freezes a snapshot for those with enough history to mean anything.
        """
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        try:
            books = [r[0] for r in conn.execute(
                "SELECT DISTINCT sportsbook FROM fair_odds_measurements")]
        finally:
            conn.close()

        snapshots = []
        for book in sorted(books):
            score = brier_score(book, None, self.brier_window, db_path=self.db_path)
            if not score["forecasts"] or score["skill_score"] is None:
                continue
            snapshots.append(score)
            if score["forecasts"] >= self.min_forecasts:
                record_brier_snapshot(book, "*", self.brier_window,
                                      measured_at=measured_at, db_path=self.db_path)
        return snapshots

    def scan_once(self, now: Optional[float] = None) -> List[ResultsReport]:
        """One pass over the drop folder. Returns a report per file processed."""
        reports: List[ResultsReport] = []
        for path in sorted(self.drop_folder.glob("*.csv")):
            if not path.is_file() or not self._is_stable(path, now):
                continue
            try:
                report = self.process_file(path)
                destination = "processed"
            except Exception as e:                          # noqa: BLE001
                report = ResultsReport(filename=path.name)
                report.skipped.append(f"{path.name} failed to import - {e}")
                destination = "failed"
            reports.append(report)
            self._seen.pop(path, None)
            if self.archive:
                self._move(path, destination)
        return reports

    def _move(self, path: Path, destination: str) -> None:
        target_dir = self.drop_folder / destination
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / path.name
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            target = target_dir / f"{path.stem}_{stamp}{path.suffix}"
        shutil.move(str(path), str(target))

    def watch(self, poll_interval: float = 30.0) -> None:
        """Blocking poll loop. Ctrl-C to stop."""
        print(f"[WATCH] {self.drop_folder} every {poll_interval:.0f}s")
        while True:
            for report in self.scan_once():
                print(report.summary())
            time.sleep(poll_interval)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sports_Desk results drop-folder watcher")
    parser.add_argument("--folder", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--once", action="store_true", help="single pass, then exit")
    parser.add_argument("--poll", type=float, default=30.0)
    parser.add_argument("--window", type=int, default=None,
                        help="score only the most recent N settled forecasts")
    parser.add_argument("--no-archive", action="store_true")
    args = parser.parse_args(argv)

    watcher = ResultsWatcher(drop_folder=args.folder, db_path=args.db,
                             brier_window=args.window, archive=not args.no_archive)
    if args.once:
        watcher.scan_once()
        for report in watcher.scan_once(now=time.time() + watcher.stability_seconds + 1):
            print(report.summary())
        return 0
    watcher.watch(args.poll)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
