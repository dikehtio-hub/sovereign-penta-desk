"""
SQLite persistence layer for Sports_Desk.

Records full provenance of fair-odds measurements and sharp-vs-retail edges into
`DEV/Sports_Desk/data/sports_market.db`.

WHY EVERY ROW CARRIES ITS INPUTS. A stored probability is unfalsifiable on its
own: months later, when a bet that showed a 4% edge has lost, the only useful
question is what the prices actually were, which book they came from, and whether
the estimator agreed with its own cross-check at the time. So each row keeps the
raw quotes for EVERY leg of the market as JSON, the solved Shin z, the Power k,
and the oracle verdict. Storage is free; a number nobody can reconstruct is not.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from Sports_Desk.engine.fair_value import FairValueResult

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "sports_market.db"


def init_market_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Creates the schema. Idempotent, so every entry point may call it."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fair_odds_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sport TEXT NOT NULL,
                market_type TEXT NOT NULL,
                line TEXT NOT NULL DEFAULT '',
                sportsbook TEXT NOT NULL,
                raw_quotes_json TEXT NOT NULL,
                selection TEXT NOT NULL,
                offered_odds REAL NOT NULL,
                implied_prob_raw REAL NOT NULL,
                fair_prob REAL NOT NULL,
                fair_odds REAL NOT NULL,
                expected_value REAL NOT NULL,
                quarter_kelly REAL NOT NULL,
                overround REAL NOT NULL,
                shin_z REAL NOT NULL,
                power_k REAL NOT NULL,
                divergent INTEGER NOT NULL,
                max_oracle_delta REAL NOT NULL,
                is_closing INTEGER NOT NULL DEFAULT 0,
                is_live INTEGER NOT NULL DEFAULT 0,
                quoted_at TEXT,
                start_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fair_odds_lookup
            ON fair_odds_measurements (sport, event_id, market_type, line, selection)
        """)

        # ONE CLOSE PER SELECTION, ENFORCED BY THE DATABASE.
        #
        # `measure_clv` takes the LAST closing row it finds, so two competing
        # closes do not error - they silently pick a winner, and the CLV of every
        # bet on that selection changes depending on which file was imported
        # second. A partial unique index makes that unrepresentable rather than
        # merely discouraged.
        #
        # Note the writer DEMOTES an existing close rather than colliding with it
        # (see `record_fair_value_measurement`): a book genuinely re-closes a
        # market, and an IntegrityError on a legitimate update would be a worse
        # failure than the one this prevents.

        # THE EDGE TABLE. A fair probability is not a trade; the trade is the GAP
        # between a sharp book's devigged fair price and what a retail book is
        # offering. Both sides live on one row on purpose.
        #
        #   sharp_*   the reference (Pinnacle / Circa), DEVIGGED
        #   retail_*  the book you would actually place at, RAW and never
        #             devigged - you bet the offered price, not a fair one
        conn.execute("""
            CREATE TABLE IF NOT EXISTS edge_opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sport TEXT NOT NULL,
                market_type TEXT NOT NULL,
                line TEXT NOT NULL DEFAULT '',
                selection TEXT NOT NULL,
                sharp_book TEXT NOT NULL,
                sharp_offered_odds REAL NOT NULL,
                sharp_fair_prob REAL NOT NULL,
                sharp_fair_odds REAL NOT NULL,
                sharp_overround REAL NOT NULL,
                sharp_quotes_json TEXT NOT NULL,
                sharp_divergent INTEGER NOT NULL,
                sharp_trustworthy INTEGER NOT NULL,
                retail_book TEXT NOT NULL,
                retail_offered_odds REAL NOT NULL,
                retail_implied_prob REAL NOT NULL,
                gross_edge REAL NOT NULL,
                after_tax_hurdle REAL,
                clears_hurdle INTEGER,
                source_file TEXT,
                content_hash TEXT,
                is_closing INTEGER NOT NULL DEFAULT 0,
                is_live INTEGER NOT NULL DEFAULT 0,
                quoted_at TEXT,
                start_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_lookup
            ON edge_opportunities (sport, event_id, market_type, line, selection, retail_book)
        """)

        # Content-addressed import log. A file re-dropped must be a no-op, and the
        # only reliable identity for a CSV is its bytes: a name or an mtime can
        # change without the content changing, and the content can change without
        # either changing.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_odds_files (
                content_hash TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                rows_read INTEGER NOT NULL,
                markets_priced INTEGER NOT NULL,
                edges_found INTEGER NOT NULL
            )
        """)
        # SETTLED OUTCOMES. What actually happened, which is the only thing that
        # can tell you whether a fair probability was any good. Kept separate from
        # the measurements so a re-scored event never rewrites the forecast that
        # was made before it - a calibration score computed against an edited
        # forecast measures nothing.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settled_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                settled_at TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sport TEXT NOT NULL,
                market_type TEXT NOT NULL,
                line TEXT NOT NULL DEFAULT '',
                selection TEXT NOT NULL,
                outcome INTEGER NOT NULL,          -- 1 won, 0 lost
                voided INTEGER NOT NULL DEFAULT 0, -- push/void: no outcome to score
                source_file TEXT,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(event_id, market_type, line, selection) ON CONFLICT REPLACE
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_lookup
            ON settled_results (sport, event_id, market_type, line, selection)
        """)

        # ROLLING CALIBRATION. A Brier snapshot per book per import, so the sharp
        # list stops being a hardcoded opinion and becomes a measurement.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS brier_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                measured_at TEXT NOT NULL,
                sportsbook TEXT NOT NULL,
                sport TEXT NOT NULL,
                window_size INTEGER NOT NULL,
                forecasts INTEGER NOT NULL,
                brier REAL NOT NULL,
                baseline_brier REAL NOT NULL,
                skill_score REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # WHAT WAS ACTUALLY STAKED. Distinct from `edge_opportunities`, which is
        # what was OFFERED - the gap between the two is the whole point. An edge
        # you saw and did not take teaches nothing; an edge you took at a worse
        # price than you saw is execution slippage, and it is invisible unless
        # both numbers are kept.
        #
        # `fair_prob_at_placement` is frozen here on purpose. Re-deriving it later
        # from the measurements table would score the bet against a fair value
        # that did not exist when the money went down.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS placed_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placed_at TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sport TEXT NOT NULL,
                market_type TEXT NOT NULL,
                line TEXT NOT NULL DEFAULT '',
                selection TEXT NOT NULL,
                book TEXT NOT NULL,
                decimal_odds REAL NOT NULL,
                stake REAL NOT NULL,
                fair_prob_at_placement REAL,
                fair_odds_at_placement REAL,
                edge_at_placement REAL,
                after_tax_hurdle REAL,
                kelly_fraction REAL,
                bet_kind TEXT NOT NULL DEFAULT 'single',
                arb_group TEXT,
                -- The BOOK's own ticket id, captured at stake time. It is the
                -- only thing that lets the tax export produce the same tx_hash
                -- the sportsbook CSV will produce, so a later import collides and
                -- is ignored instead of booking the wager a second time.
                ticket_id TEXT,
                outcome TEXT,              -- WIN | LOSS | PUSH, once settled
                realized_pnl REAL,
                settled_at TEXT,
                exported_at TEXT,          -- when it was handed to the tax ledger
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_placed_lookup
            ON placed_bets (event_id, market_type, line, selection)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_results_files (
                content_hash TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                rows_read INTEGER NOT NULL,
                settled INTEGER NOT NULL
            )
        """)
        _migrate(conn)
        # AFTER the migration: a pre-existing database may hold duplicate closes,
        # and the index cannot be created until they are demoted.
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_single_close
            ON fair_odds_measurements (event_id, market_type, line, selection)
            WHERE is_closing = 1
        """)
        conn.commit()
    finally:
        conn.close()


# Columns added after the first schema shipped. A database written by an earlier
# build is missing them, and CREATE TABLE IF NOT EXISTS will not add them - so the
# migration is explicit rather than implied, and idempotent so it can run on
# every open.
_MIGRATIONS = (
    ("fair_odds_measurements", "line", "TEXT NOT NULL DEFAULT ''"),
    ("fair_odds_measurements", "is_closing", "INTEGER NOT NULL DEFAULT 0"),
    ("fair_odds_measurements", "is_live", "INTEGER NOT NULL DEFAULT 0"),
    ("fair_odds_measurements", "quoted_at", "TEXT"),
    ("fair_odds_measurements", "start_time", "TEXT"),
    ("edge_opportunities", "line", "TEXT NOT NULL DEFAULT ''"),
    ("edge_opportunities", "is_closing", "INTEGER NOT NULL DEFAULT 0"),
    ("edge_opportunities", "is_live", "INTEGER NOT NULL DEFAULT 0"),
    ("edge_opportunities", "quoted_at", "TEXT"),
    ("edge_opportunities", "start_time", "TEXT"),
    ("placed_bets", "ticket_id", "TEXT"),
    ("placed_bets", "outcome", "TEXT"),
    ("placed_bets", "realized_pnl", "REAL"),
    ("placed_bets", "settled_at", "TEXT"),
    ("placed_bets", "exported_at", "TEXT"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    for table, column, spec in _MIGRATIONS:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")

    # A database written before the single-close invariant may already hold
    # duplicates, and CREATE UNIQUE INDEX would fail outright on it. Demote all
    # but the newest close per selection first, so the index can be built and the
    # invariant starts holding rather than the migration blocking on old data.
    try:
        duplicates = conn.execute("""
            SELECT event_id, market_type, line, selection
            FROM fair_odds_measurements WHERE is_closing = 1
            GROUP BY event_id, market_type, line, selection HAVING COUNT(*) > 1
        """).fetchall()
    except sqlite3.OperationalError:
        return
    for event_id, market_type, line, selection in duplicates:
        conn.execute("""
            UPDATE fair_odds_measurements SET is_closing = 0
            WHERE event_id = ? AND market_type = ? AND line = ? AND selection = ?
              AND is_closing = 1
              AND id <> (SELECT id FROM fair_odds_measurements
                         WHERE event_id = ? AND market_type = ? AND line = ?
                           AND selection = ? AND is_closing = 1
                         ORDER BY timestamp DESC, id DESC LIMIT 1)
        """, (event_id, market_type, line, selection,
              event_id, market_type, line, selection))
        print(f"[WARN] {event_id}/{market_type}/{selection}: multiple closing lines "
              f"found; kept the newest and demoted the rest.")


def record_fair_value_measurement(
    event_id: str,
    sport: str,
    selections: Sequence[str],
    market_type: str,
    sportsbook: str,
    result: FairValueResult,
    timestamp: Optional[str] = None,
    line: str = "",
    is_closing: bool = False,
    is_live: bool = False,
    quoted_at: Optional[str] = None,
    start_time: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
    lines: Optional[Sequence[Optional[str]]] = None,
) -> List[int]:
    """
    Persists a complete market fair-value assessment with provenance.

    `lines`, when given, is the per-selection line: on a spread each leg is
    stored under ITS OWN signed handicap (Chiefs -3.5, Ravens +3.5), which is what
    the cross-market matcher and a results file both key on. `line` remains the
    fallback for any selection without one, and for totals and moneylines.
    """
    init_market_db(db_path)
    now_ts = timestamp or datetime.now(timezone.utc).isoformat()

    def line_for(idx: int) -> str:
        if lines is not None and idx < len(lines) and lines[idx] not in (None, ""):
            return str(lines[idx])
        return str(line or "")
    raw_quotes_dict = {
        (selections[i] if i < len(selections) else f"Outcome_{i + 1}"): o.offered_odds
        for i, o in enumerate(result.outcomes)
    }
    raw_quotes_json = json.dumps(raw_quotes_dict, sort_keys=True)

    inserted_ids = []
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        for idx, outcome in enumerate(result.outcomes):
            sel = selections[idx] if idx < len(selections) else f"Outcome_{idx + 1}"
            row_line = line_for(idx)
            if is_closing:
                # Demote any prior close for this selection. There is exactly one
                # closing line and it is the most recently declared one; the
                # partial unique index guarantees the invariant, and this is what
                # keeps a legitimate re-close from hitting it.
                cursor.execute("""
                    UPDATE fair_odds_measurements SET is_closing = 0
                    WHERE event_id = ? AND market_type = ? AND line = ?
                      AND selection = ? AND is_closing = 1
                """, (event_id, market_type, row_line, sel))
            cursor.execute("""
                INSERT INTO fair_odds_measurements (
                    timestamp, event_id, sport, market_type, line, sportsbook,
                    raw_quotes_json, selection, offered_odds, implied_prob_raw,
                    fair_prob, fair_odds, expected_value, quarter_kelly, overround,
                    shin_z, power_k, divergent, max_oracle_delta, is_closing,
                    is_live, quoted_at, start_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?)
            """, (
                now_ts, event_id, sport, market_type, row_line, sportsbook,
                raw_quotes_json, sel, outcome.offered_odds, outcome.implied_prob_raw,
                outcome.fair_prob, outcome.fair_odds, outcome.expected_value,
                outcome.quarter_kelly, result.overround, result.shin_z, result.power_k,
                1 if result.divergent else 0, result.max_oracle_delta,
                1 if is_closing else 0, 1 if is_live else 0, quoted_at, start_time
            ))
            inserted_ids.append(cursor.lastrowid)
        conn.commit()
    finally:
        conn.close()
    return inserted_ids


def record_edge_opportunity(
    event_id: str,
    sport: str,
    market_type: str,
    selection: str,
    sharp_book: str,
    sharp_offered_odds: float,
    sharp_fair_prob: float,
    sharp_overround: float,
    sharp_quotes: Dict[str, float],
    sharp_divergent: bool,
    sharp_trustworthy: bool,
    retail_book: str,
    retail_offered_odds: float,
    gross_edge: float,
    after_tax_hurdle: Optional[float] = None,
    source_file: Optional[str] = None,
    content_hash: Optional[str] = None,
    timestamp: Optional[str] = None,
    line: str = "",
    is_closing: bool = False,
    is_live: bool = False,
    quoted_at: Optional[str] = None,
    start_time: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """
    Records one sharp-vs-retail edge with both prices and the sharp book's whole
    market attached.

    `after_tax_hurdle` is optional because this module has no business knowing a
    tax treatment - the caller reads it from `monarch_hook.breakeven_gross_edge`
    and passes it in. When supplied, `clears_hurdle` is stored beside it, so a
    later reader never has to reconstruct which tax rules applied on the day.
    """
    init_market_db(db_path)
    now_ts = timestamp or datetime.now(timezone.utc).isoformat()
    clears = None if after_tax_hurdle is None else int(gross_edge > after_tax_hurdle)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO edge_opportunities (
                timestamp, event_id, sport, market_type, line, selection,
                sharp_book, sharp_offered_odds, sharp_fair_prob, sharp_fair_odds,
                sharp_overround, sharp_quotes_json, sharp_divergent, sharp_trustworthy,
                retail_book, retail_offered_odds, retail_implied_prob, gross_edge,
                after_tax_hurdle, clears_hurdle, source_file, content_hash, is_closing,
                is_live, quoted_at, start_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?)
        """, (
            now_ts, event_id, sport, market_type, str(line or ""), selection,
            sharp_book, float(sharp_offered_odds), float(sharp_fair_prob),
            (1.0 / sharp_fair_prob) if sharp_fair_prob > 0 else float("inf"),
            float(sharp_overround), json.dumps(sharp_quotes, sort_keys=True),
            1 if sharp_divergent else 0, 1 if sharp_trustworthy else 0,
            retail_book, float(retail_offered_odds),
            1.0 / float(retail_offered_odds), float(gross_edge),
            after_tax_hurdle, clears, source_file, content_hash,
            1 if is_closing else 0, 1 if is_live else 0, quoted_at, start_time,
        ))
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def query_edges(event_id: Optional[str] = None, min_edge: float = 0.0,
                clears_hurdle_only: bool = False,
                db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Edges, best first. `clears_hurdle_only` drops rows that never cleared tax."""
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM edge_opportunities WHERE gross_edge >= ?"
        params: List[Any] = [float(min_edge)]
        if event_id:
            sql += " AND event_id = ?"
            params.append(event_id)
        if clears_hurdle_only:
            sql += " AND clears_hurdle = 1"
        sql += " ORDER BY gross_edge DESC, id ASC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def measure_clv(event_id: Optional[str] = None,
                db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Closing-line value, measured on FAIR PROBABILITIES rather than on prices.

    WHY PROBABILITIES AND NOT PRICES. A retail price moves for reasons that have
    nothing to do with the outcome - a promotion, a limit change, one book being
    slow. The devigged fair probability of the SHARP market is the closest thing
    available to the market consensus, so comparing entry fair probability to
    closing fair probability measures whether the market moved TOWARD the side
    taken. That is the only honest read on whether a model has an edge, and it is
    available long before enough bets settle to measure anything from results.

    Positive `clv_prob_delta` means the closing market thought the selection was
    MORE likely than it did at entry - the line moved your way.

    ENTRY IS DEFINED AS THE EARLIEST NON-CLOSING MEASUREMENT for that market and
    selection, not as the price of a bet, because nothing here records bets yet.
    When that changes this function should take a stake timestamp instead.

    TWO GUARDRAILS, both of which produce a plausible-looking number when absent:

      * `t_close > t_entry`. A close recorded at or before the entry is not a
        close - it is the same observation, or the file was imported out of
        order, and the CLV it yields is zero or reversed.
      * `is_live == 0` on BOTH ends. An in-play price is not comparable to a
        pre-game one: the game state has changed the true probability, so the
        move measures the scoreboard rather than the market disagreeing with you.
    """
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = ("SELECT event_id, sport, market_type, line, selection, timestamp, "
               "fair_prob, fair_odds, is_closing, is_live "
               "FROM fair_odds_measurements WHERE is_live = 0")
        params: List[Any] = []
        if event_id:
            sql += " AND event_id = ?"
            params.append(event_id)
        sql += " ORDER BY timestamp ASC, id ASC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()

    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for row in rows:
        key = (row["event_id"], row["market_type"], row["line"], row["selection"])
        grouped.setdefault(key, []).append(row)

    results: List[Dict[str, Any]] = []
    for (event, market_type, line, selection), history in grouped.items():
        closing = [r for r in history if r["is_closing"]]
        entries = [r for r in history if not r["is_closing"]]
        if not closing or not entries:
            # Nothing to compare against. Reported rather than dropped so a caller
            # can see WHICH markets have no close recorded yet.
            results.append({
                "event_id": event, "market_type": market_type, "line": line,
                "selection": selection, "entry_fair_prob": entries[-1]["fair_prob"] if entries else None,
                "closing_fair_prob": closing[-1]["fair_prob"] if closing else None,
                "clv_prob_delta": None, "clv_pct": None, "beat_close": None,
                "measurements": len(history),
            })
            continue
        entry = entries[0]
        close = closing[-1]
        if close["timestamp"] <= entry["timestamp"]:
            # Same observation, or an out-of-order import. Reported as
            # unmeasurable rather than as a CLV of zero, which would silently
            # drag a real average toward "no skill".
            results.append({
                "event_id": event, "market_type": market_type, "line": line,
                "selection": selection,
                "entry_fair_prob": float(entry["fair_prob"]),
                "closing_fair_prob": float(close["fair_prob"]),
                "clv_prob_delta": None, "clv_pct": None, "beat_close": None,
                "measurements": len(history),
                "note": "close is not strictly after entry",
            })
            continue
        delta = float(close["fair_prob"]) - float(entry["fair_prob"])
        pct = (float(close["fair_prob"]) / float(entry["fair_prob"]) - 1.0
               if entry["fair_prob"] else None)
        results.append({
            "event_id": event, "market_type": market_type, "line": line,
            "selection": selection,
            "entry_timestamp": entry["timestamp"], "closing_timestamp": close["timestamp"],
            "entry_fair_prob": float(entry["fair_prob"]),
            "closing_fair_prob": float(close["fair_prob"]),
            "entry_fair_odds": float(entry["fair_odds"]),
            "closing_fair_odds": float(close["fair_odds"]),
            "clv_prob_delta": delta, "clv_pct": pct, "beat_close": delta > 0,
            "measurements": len(history),
        })
    return results


def record_settled_result(event_id: str, sport: str, market_type: str, line: str,
                          selection: str, outcome: int, voided: bool = False,
                          settled_at: Optional[str] = None,
                          source_file: Optional[str] = None,
                          content_hash: Optional[str] = None,
                          db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Records what actually happened. Re-settling one selection REPLACES the row
    (books do correct results), but never touches the forecast that was made
    before it - a calibration score computed against an edited forecast measures
    nothing at all.
    """
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settled_results
            (settled_at, event_id, sport, market_type, line, selection, outcome,
             voided, source_file, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (settled_at or datetime.now(timezone.utc).isoformat(), event_id, sport,
              market_type, str(line or ""), selection, int(bool(outcome)),
              1 if voided else 0, source_file, content_hash))
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def query_results(event_id: Optional[str] = None,
                  db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM settled_results"
        params: List[Any] = []
        if event_id:
            sql += " WHERE event_id = ?"
            params.append(event_id)
        sql += " ORDER BY settled_at ASC, id ASC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def scored_forecasts(sportsbook: Optional[str] = None, sport: Optional[str] = None,
                     window: Optional[int] = None,
                     db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Forecasts joined to the outcomes that settled them, newest first.

    Uses the CLOSING measurement where one exists and the latest otherwise: the
    close is the market's final word, and scoring an early price would measure
    how much the line moved rather than how good the book is.

    VOIDED SELECTIONS ARE EXCLUDED. A push has no outcome, so squaring a forecast
    against it is not a small error, it is a category error.
    """
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = """
            SELECT m.sportsbook, m.sport, m.event_id, m.market_type, m.line,
                   m.selection, m.fair_prob, m.timestamp, m.is_closing,
                   r.outcome, r.settled_at
            FROM fair_odds_measurements m
            JOIN settled_results r
              ON r.event_id = m.event_id AND r.market_type = m.market_type
             AND r.line = m.line AND r.selection = m.selection
            WHERE r.voided = 0 AND m.is_live = 0
        """
        params: List[Any] = []
        if sportsbook:
            sql += " AND m.sportsbook = ?"
            params.append(sportsbook)
        if sport:
            sql += " AND m.sport = ?"
            params.append(sport)
        # One forecast per settled selection: the closing row wins, else the last.
        sql += """
            AND m.id = (
                SELECT id FROM fair_odds_measurements x
                WHERE x.event_id = m.event_id AND x.market_type = m.market_type
                  AND x.line = m.line AND x.selection = m.selection
                  AND x.sportsbook = m.sportsbook AND x.is_live = 0
                ORDER BY x.is_closing DESC, x.timestamp DESC, x.id DESC LIMIT 1
            )
            ORDER BY r.settled_at DESC, r.id DESC
        """
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
    return rows[:window] if window else rows


def brier_score(sportsbook: Optional[str] = None, sport: Optional[str] = None,
                window: Optional[int] = None,
                db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Rolling Brier score for a book's devigged fair probabilities.

        brier = mean((forecast - outcome)^2)      LOWER IS BETTER, 0 is perfect

    A raw Brier is close to meaningless on its own, because it depends on how
    lopsided the markets were - forecasting a field of heavy favourites scores
    well by saying nothing. So the SKILL SCORE is reported beside it:

        skill = 1 - brier / baseline_brier

    where the baseline is the base rate of this very sample. Positive skill means
    the book beat "predict the average"; zero or negative means it did not, and
    no amount of a good-looking raw Brier changes that.

    THIS IS WHAT SHOULD EVENTUALLY REPLACE THE HARDCODED `SHARP_BOOKS` LIST -
    sharpness is a property you measure, not a name you recognise.
    """
    rows = scored_forecasts(sportsbook, sport, window, db_path)
    forecasts = len(rows)
    if not forecasts:
        return {"sportsbook": sportsbook or "*", "sport": sport or "*",
                "forecasts": 0, "brier": None, "baseline_brier": None,
                "skill_score": None, "window": window}
    brier = sum((float(r["fair_prob"]) - float(r["outcome"])) ** 2 for r in rows) / forecasts
    base_rate = sum(float(r["outcome"]) for r in rows) / forecasts
    baseline = sum((base_rate - float(r["outcome"])) ** 2 for r in rows) / forecasts
    skill = (1.0 - brier / baseline) if baseline > 0 else None
    return {"sportsbook": sportsbook or "*", "sport": sport or "*",
            "forecasts": forecasts, "brier": brier, "baseline_brier": baseline,
            "skill_score": skill, "base_rate": base_rate, "window": window}


def record_brier_snapshot(sportsbook: str, sport: str = "*",
                          window: Optional[int] = None,
                          measured_at: Optional[str] = None,
                          db_path: Path = DEFAULT_DB_PATH) -> Optional[int]:
    """Freezes the current rolling score so calibration can be tracked over time."""
    score = brier_score(sportsbook, None if sport == "*" else sport, window, db_path)
    if not score["forecasts"] or score["skill_score"] is None:
        return None
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO brier_snapshots
            (measured_at, sportsbook, sport, window_size, forecasts, brier,
             baseline_brier, skill_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (measured_at or datetime.now(timezone.utc).isoformat(), sportsbook, sport,
              int(window or 0), score["forecasts"], score["brier"],
              score["baseline_brier"], score["skill_score"]))
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def query_brier_snapshots(sportsbook: Optional[str] = None,
                          db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM brier_snapshots"
        params: List[Any] = []
        if sportsbook:
            sql += " WHERE sportsbook = ?"
            params.append(sportsbook)
        sql += " ORDER BY measured_at DESC, id DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def settled_event_ids(db_path: Path = DEFAULT_DB_PATH) -> set:
    """Events with any settled selection - used to drop them from the hotlist."""
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        return {row[0] for row in conn.execute("SELECT DISTINCT event_id FROM settled_results")}
    finally:
        conn.close()


def already_imported_result(content_hash: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM processed_results_files WHERE content_hash = ?",
            (content_hash,)).fetchone()
        return row is not None
    finally:
        conn.close()


def record_result_import(content_hash: str, filename: str, rows_read: int,
                         settled: int, timestamp: Optional[str] = None,
                         db_path: Path = DEFAULT_DB_PATH) -> None:
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO processed_results_files
            (content_hash, filename, imported_at, rows_read, settled)
            VALUES (?, ?, ?, ?, ?)
        """, (content_hash, filename,
              timestamp or datetime.now(timezone.utc).isoformat(),
              int(rows_read), int(settled)))
        conn.commit()
    finally:
        conn.close()


def record_placed_bet(event_id: str, sport: str, market_type: str, line: str,
                      selection: str, book: str, decimal_odds: float, stake: float,
                      fair_prob_at_placement: Optional[float] = None,
                      edge_at_placement: Optional[float] = None,
                      after_tax_hurdle: Optional[float] = None,
                      kelly_fraction: Optional[float] = None,
                      bet_kind: str = "single", arb_group: Optional[str] = None,
                      ticket_id: Optional[str] = None,
                      notes: str = "", placed_at: Optional[str] = None,
                      db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Records a wager that was actually staked.

    THIS IS NOT A TAX RECORD. The ledger in `Tax_Reserve_Agent` is the tax record
    and it is fed by the book's own export, because what the escrow must reserve
    against is what the book says happened, not what this desk intended. Rows
    here exist to measure EXECUTION - the price taken against the price seen, and
    the fair value at placement against the closing line.
    """
    init_market_db(db_path)
    fair_odds = (1.0 / fair_prob_at_placement
                 if fair_prob_at_placement else None)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO placed_bets
            (placed_at, event_id, sport, market_type, line, selection, book,
             decimal_odds, stake, fair_prob_at_placement, fair_odds_at_placement,
             edge_at_placement, after_tax_hurdle, kelly_fraction, bet_kind,
             arb_group, ticket_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (placed_at or datetime.now(timezone.utc).isoformat(), event_id, sport,
              market_type, str(line or ""), selection, book, float(decimal_odds),
              float(stake), fair_prob_at_placement, fair_odds,
              edge_at_placement, after_tax_hurdle, kelly_fraction, bet_kind,
              arb_group, ticket_id, notes))
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def query_placed_bets(event_id: Optional[str] = None,
                      db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM placed_bets"
        params: List[Any] = []
        if event_id:
            sql += " WHERE event_id = ?"
            params.append(event_id)
        sql += " ORDER BY placed_at DESC, id DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def execution_clv(event_id: Optional[str] = None,
                  db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Closing-line value on the bets ACTUALLY PLACED, not on every quote observed.

    `measure_clv` answers "did the market move toward the prices we were
    watching". This answers the only question that costs money: did the market
    move toward the price WE TOOK, at the size we took it.

    Two numbers per bet, and they are different things:

      * `clv_prob_delta` - closing fair probability minus the fair probability at
        placement. Positive means the market came to you: the classic CLV test.
      * `beat_closing_price` - whether the odds you actually got were better than
        the closing FAIR odds. This is the one that says whether the bet was
        priced well, independent of which way the line then moved.

    A bet can beat the close on probability and still have been a bad price, and
    vice versa. Reporting one without the other hides half the story.
    """
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = """
            SELECT b.*, m.fair_prob AS closing_fair_prob, m.timestamp AS closing_at
            FROM placed_bets b
            LEFT JOIN fair_odds_measurements m
              ON m.event_id = b.event_id AND m.market_type = b.market_type
             AND m.line = b.line AND m.selection = b.selection
             AND m.is_closing = 1 AND m.is_live = 0
        """
        params: List[Any] = []
        if event_id:
            sql += " WHERE b.event_id = ?"
            params.append(event_id)
        sql += " ORDER BY b.placed_at DESC, b.id DESC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()

    results: List[Dict[str, Any]] = []
    for row in rows:
        closing = row.get("closing_fair_prob")
        entry = row.get("fair_prob_at_placement")
        record = dict(row)
        if closing is None or entry is None:
            record.update({"clv_prob_delta": None, "clv_pct": None,
                           "beat_close": None, "beat_closing_price": None,
                           "note": "no closing line recorded yet"})
        elif row.get("closing_at") and str(row["closing_at"]) <= str(row["placed_at"]):
            record.update({"clv_prob_delta": None, "clv_pct": None,
                           "beat_close": None, "beat_closing_price": None,
                           "note": "close is not strictly after placement"})
        else:
            delta = float(closing) - float(entry)
            record.update({
                "clv_prob_delta": delta,
                "clv_pct": (delta / float(entry)) if entry else None,
                "beat_close": delta > 0,
                # Took better odds than the closing fair price implies.
                "beat_closing_price": float(row["decimal_odds"]) > (1.0 / float(closing)),
                "note": "",
            })
        results.append(record)
    return results


def query_measurements(event_id: Optional[str] = None, include_live: bool = False,
                       db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Every recorded fair-value measurement, newest last.

    `query_latest_measurements` needs an event id; this does not, because the
    arbitrage scan has to sweep the whole book. It is also the only place a
    SHARP-ONLY leg is visible: `edge_opportunities` holds one row per RETAIL
    quote, so a selection nobody but the sharp book priced has no edge row at all.
    """
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM fair_odds_measurements"
        clauses: List[str] = []
        params: List[Any] = []
        if not include_live:
            clauses.append("is_live = 0")
        if event_id:
            clauses.append("event_id = ?")
            params.append(event_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY timestamp ASC, id ASC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def settle_placed_bets(db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Joins `settled_results` onto `placed_bets` and writes the outcome and the
    realised P&L. Returns how many rows it settled.

    REALISED P&L IS THE ONLY THING THAT ANSWERS "DID I MAKE MONEY". CLV is a
    leading indicator and the Brier score grades the BOOK, not us; neither can be
    cashed. Until this join existed the desk could report a healthy edge for a
    season and never notice it was down.

        WIN   stake * (odds - 1)
        LOSS  -stake
        PUSH  0

    Voided results settle as a PUSH: the stake comes back, so the bet neither made
    nor lost anything, and scoring it either way would bias the record.
    """
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT b.id, b.stake, b.decimal_odds, r.outcome, r.voided, r.settled_at
            FROM placed_bets b
            JOIN settled_results r
              ON r.event_id = b.event_id AND r.market_type = b.market_type
             AND r.line = b.line AND r.selection = b.selection
            WHERE b.outcome IS NULL
        """).fetchall()
        settled = 0
        for row in rows:
            if row["voided"]:
                outcome, pnl = "PUSH", 0.0
            elif row["outcome"]:
                outcome = "WIN"
                pnl = float(row["stake"]) * (float(row["decimal_odds"]) - 1.0)
            else:
                outcome, pnl = "LOSS", -float(row["stake"])
            conn.execute("""
                UPDATE placed_bets SET outcome = ?, realized_pnl = ?, settled_at = ?
                WHERE id = ?
            """, (outcome, pnl, row["settled_at"], row["id"]))
            settled += 1
        conn.commit()
        return settled
    finally:
        conn.close()


def desk_performance(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    What the desk actually did with real money.

    Pushes are excluded from the win rate and from turnover - a returned stake is
    not a bet that was won or lost, and counting it drags every ratio toward the
    middle. They stay in the bet count so nothing goes missing.

    `expected_win_rate` is the average fair probability the MODEL assigned to the
    bets that settled. Comparing it to the realised rate is the sharpest test
    available: a model whose 40% shots come in 25% of the time is not unlucky, it
    is miscalibrated, and no amount of positive CLV rescues it.
    """
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM placed_bets WHERE outcome IS NOT NULL").fetchall()]
        pending = conn.execute(
            "SELECT COUNT(*) FROM placed_bets WHERE outcome IS NULL").fetchone()[0]
    finally:
        conn.close()

    decided = [r for r in rows if r["outcome"] in ("WIN", "LOSS")]
    turnover = sum(float(r["stake"]) for r in decided)
    pnl = sum(float(r["realized_pnl"] or 0.0) for r in rows)
    wins = sum(1 for r in decided if r["outcome"] == "WIN")
    modelled = [float(r["fair_prob_at_placement"]) for r in decided
                if r["fair_prob_at_placement"] is not None]
    clv_rows = [r for r in execution_clv(db_path=db_path)
                if r.get("clv_prob_delta") is not None]
    return {
        "bets_settled": len(rows),
        "bets_decided": len(decided),
        "bets_pending": int(pending),
        "pushes": sum(1 for r in rows if r["outcome"] == "PUSH"),
        "turnover": turnover,
        "realized_pnl": pnl,
        "roi": (pnl / turnover) if turnover > 0 else None,
        "win_rate": (wins / len(decided)) if decided else None,
        "expected_win_rate": (sum(modelled) / len(modelled)) if modelled else None,
        "avg_clv": (sum(r["clv_prob_delta"] for r in clv_rows) / len(clv_rows)
                    if clv_rows else None),
        "clv_measured": len(clv_rows),
    }


# ---------------------------------------------------------------------------
# Bridge A: has the tax ledger actually heard about these bets?
# ---------------------------------------------------------------------------

def unsynced_placed_bets(tax_db_path: Optional[Path] = None,
                         older_than_days: Optional[float] = None,
                         now: Optional[datetime] = None,
                         db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Placed bets with no matching wager in the TAX LEDGER.

    THE ESCROW IS ONLY AS GOOD AS THE IMPORT. Everything else in this desk can be
    right and the reserve still wrong, because the tax ledger learns about a
    wager only when the book's export is dropped in. The betslip reminds the
    operator; nothing until now CHECKED. Forget once and the escrow under-reserves
    silently and permanently.

    Matched on the ledger's own symbol shape - `BOOK:SPORT:SELECTION#TICKET` -
    when a ticket id was captured, and otherwise on book plus selection plus
    stake, which is weaker and says so.
    """
    from Tax_Reserve_Agent.database.db import DB_PATH as TAX_DB_PATH
    from Tax_Reserve_Agent.database.db import get_connection as tax_connection

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    placed = query_placed_bets(db_path=db_path)
    if not placed:
        return []

    try:
        conn = tax_connection(Path(tax_db_path) if tax_db_path else TAX_DB_PATH)
        try:
            ledger = [dict(r) for r in conn.execute(
                "SELECT symbol, total_value, notes FROM transactions "
                "WHERE asset_class = 'sports_bet' AND side = 'BET'").fetchall()]
        finally:
            conn.close()
    except Exception as e:                                  # noqa: BLE001
        print(f"[WARN] Could not read the tax ledger ({e}); treating every placed "
              f"bet as unsynced rather than reporting a clean slate.")
        ledger = []

    symbols = {str(row["symbol"]).upper() for row in ledger}
    loose = {(str(row["symbol"]).split(":")[0].upper(),
              round(float(row["total_value"]), 2)) for row in ledger}

    unsynced: List[Dict[str, Any]] = []
    for bet in placed:
        matched = False
        if bet.get("ticket_id"):
            from Tax_Reserve_Agent.ingestors.sports_betting import bet_symbol
            matched = bet_symbol(bet["book"], bet["sport"], bet["selection"],
                                 bet["ticket_id"]).upper() in symbols
        if not matched:
            matched = (str(bet["book"]).upper(),
                       round(float(bet["stake"]), 2)) in loose
        if matched:
            continue
        age_days = _age_days(bet.get("placed_at"), now)
        if older_than_days is not None and (age_days is None
                                            or age_days < older_than_days):
            continue
        record = dict(bet)
        record["age_days"] = age_days
        record["match_confidence"] = "ticket" if bet.get("ticket_id") else "loose"
        unsynced.append(record)
    return unsynced


def mark_exported(bet_ids: Sequence[int], exported_at: Optional[str] = None,
                  db_path: Path = DEFAULT_DB_PATH) -> None:
    """Records that these bets were handed to the tax ledger's drop folder."""
    if not bet_ids:
        return
    init_market_db(db_path)
    stamp = exported_at or datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany("UPDATE placed_bets SET exported_at = ? WHERE id = ?",
                         [(stamp, int(i)) for i in bet_ids])
        conn.commit()
    finally:
        conn.close()


def _age_days(placed_at: Optional[str], now: datetime) -> Optional[float]:
    if not placed_at:
        return None
    try:
        from Tax_Reserve_Agent.engine.lot_engine import as_naive_utc, parse_iso_date
        return (now - as_naive_utc(parse_iso_date(placed_at))).total_seconds() / 86400.0
    except (ValueError, TypeError):
        return None


def open_desk_exposure(db_path: Path = DEFAULT_DB_PATH) -> float:
    """
    Total staked on placed bets whose event has not settled.

    THE TAX LEDGER CANNOT ANSWER THIS. `monarch_hook` measures open exposure from
    the ledger, and the ledger only learns about a wager when the book's export is
    imported - which might be days later. Between placing and importing, every
    order is gated against a bucket that looks empty, so a betslip session can
    stake the same capital over and over.

    Measured, not accumulated in memory, so it survives restarting the betslip.
    """
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(b.stake), 0.0) FROM placed_bets b
            WHERE b.outcome IS NULL AND NOT EXISTS (
                SELECT 1 FROM settled_results r
                WHERE r.event_id = b.event_id AND r.market_type = b.market_type
                  AND r.line = b.line AND r.selection = b.selection
            )
        """).fetchone()
        return float(row[0] or 0.0)
    finally:
        conn.close()


def already_imported(content_hash: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Have these exact bytes been through the watcher before?"""
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM processed_odds_files WHERE content_hash = ?",
            (content_hash,)).fetchone()
        return row is not None
    finally:
        conn.close()


def record_import(content_hash: str, filename: str, rows_read: int,
                  markets_priced: int, edges_found: int,
                  timestamp: Optional[str] = None,
                  db_path: Path = DEFAULT_DB_PATH) -> None:
    """Logs a completed import so the same bytes are never replayed."""
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO processed_odds_files
            (content_hash, filename, imported_at, rows_read, markets_priced, edges_found)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (content_hash, filename,
              timestamp or datetime.now(timezone.utc).isoformat(),
              int(rows_read), int(markets_priced), int(edges_found)))
        conn.commit()
    finally:
        conn.close()


def query_latest_measurements(
    event_id: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Fetches all measurements for a given event_id."""
    init_market_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT * FROM fair_odds_measurements
            WHERE event_id = ?
            ORDER BY id ASC
        """, (event_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
