"""
Auto CSV Drop-Folder Watcher.

Drop a broker/exchange CSV into `data/imports/` and it lands in the SQLite ledger
without another command being typed. Files are classified, parsed through the
existing ingestors, run through the FIFO lot engine, and then MOVED out of the
folder into `processed/` or `failed/` - the move is what makes the watcher
re-runnable, since a file can only be seen once.

Three failure modes this is built around, all of which corrupt a tax ledger
quietly rather than loudly:

  1. HALF-WRITTEN FILES. Copying a 40MB export into a watched folder makes it
     visible long before it is complete; parsing it then imports a truncated
     trade history that looks perfectly valid. Every file must therefore report
     the same size and mtime on two consecutive polls before it is touched.
  2. GUESSED ASSET CLASSES. `timestamp,symbol,side,quantity,price` is a plausible
     header for all three sources. Rather than defaulting to one and silently
     filing options under crypto spot, an unclassifiable file is REJECTED with an
     actionable message. A wrong asset class is invisible in the HUD and wrong
     forever after.
  3. DOUBLE IMPORTS. The same export dropped twice re-inserts every fill, doubling
     realised gains. Rows carry a deterministic `tx_hash` (from the file's own id
     column, or a content hash of the row when it has none), so the ledger's
     UNIQUE constraint absorbs the repeat.

No `watchdog` dependency - a stat-poll loop is enough for a folder a human drops
files into, and keeps the agent's dependency surface at zero.
"""
import argparse
import csv
import hashlib
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..database.db import get_connection, init_db
from ..engine.lot_engine import process_batch
from .options import OptionsIngestor
from .polymarket import PolymarketIngestor
from .spot import SpotIngestor
from .sports_betting import SportsBettingIngestor

DEFAULT_IMPORTS_DIR = Path(__file__).parent.parent / "data" / "imports"

# Filename tokens are checked before headers: an explicit `spot_binance_2026.csv`
# should win over a header that happens to look like something else.
FILENAME_HINTS = {
    "hyperliquid": ("hyperliquid", "hl_", "perp"),
    "polymarket": ("polymarket", "poly", "ctf", "prediction"),
    "options": ("option", "options", "opt", "deribit", "aevo", "lyra"),
    "spot": ("spot", "coinbase", "kraken", "binance", "swap", "dex"),
    "tradovate": ("tradovate", "futures", "cme", "ninjatrader"),
    "sports": ("sports", "sportsbook", "draftkings", "fanduel", "betmgm", "pinnacle",
               "caesars", "pointsbet", "bet365", "wager", "bets", "parlay"),
    "deposit": ("deposit", "seed_bankroll", "bankroll", "cash_in", "withdrawal"),
}

# Header columns that only ever appear on one kind of export.
HEADER_SIGNATURES = {
    "options": ("premium", "strike", "expiry", "expiration", "contract_type", "option_type"),
    "polymarket": ("condition_id", "conditionid", "outcome", "market", "token_id", "tokenid", "market_slug"),
    "spot": ("base_asset", "quote_asset", "pair"),
    "sports": ("sportsbook", "wager", "odds", "payout", "selection", "ticket_id",
               "american_odds", "decimal_odds", "bet_id", "stake"),
}

# Side vocabularies that are unambiguous on their own.
SIDE_SIGNATURES = {
    "options": ("OPTION_BUY", "OPTION_SELL", "OPTION_EXPIRE", "OPTION_SELL_TO_OPEN", "OPTION_BUY_TO_CLOSE", "EXPIRE"),
    "polymarket": ("REDEEM", "SPLIT", "MERGE", "SPLIT_YES", "SPLIT_NO"),
    "sports": ("BET", "BET_WIN", "BET_LOSS", "BET_PUSH", "BET_CASHOUT"),
    "deposit": ("DEPOSIT", "WITHDRAWAL"),
}


class ClassificationError(ValueError):
    """The file's source could not be determined. Never guessed - always raised."""


def _normalise_headers(fieldnames: Optional[List[str]]) -> List[str]:
    return [str(name).strip().lower() for name in (fieldnames or []) if name]


def _row_fingerprint(row: Dict[str, Any], source: str) -> str:
    """
    Stable hash of a row's content, used as `tx_hash` when the export has no id.

    Content-addressed rather than positional so that re-exporting the same trades
    in a different order, or with extra rows appended, still deduplicates against
    what is already in the ledger.
    """
    payload = "|".join(f"{k}={row.get(k, '')}" for k in sorted(row.keys()))
    return f"{source}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def classify_csv(path: Path, rows: Optional[List[Dict[str, str]]] = None,
                 headers: Optional[List[str]] = None) -> Tuple[str, str]:
    """
    Returns (source, reason). Raises ClassificationError rather than guessing.

    Precedence, most explicit first: an in-file `source`/`asset_class` column, the
    filename, a header column unique to one export shape, then the side vocabulary.
    """
    rows = rows or []
    headers = headers if headers is not None else _normalise_headers(list(rows[0].keys()) if rows else [])

    for row in rows[:5]:
        declared = str(row.get("source") or row.get("asset_class") or "").strip().lower()
        if declared:
            if declared in ("hyperliquid", "crypto_perp", "perp"):
                return "hyperliquid", "explicit `source` column"
            if declared in ("polymarket", "prediction_market"):
                return "polymarket", "explicit `source` column"
            if declared in ("options", "option"):
                return "options", "explicit `source` column"
            if declared in ("spot", "crypto_spot"):
                return "spot", "explicit `source` column"
            if declared in ("tradovate", "futures", "cme"):
                return "tradovate", "explicit `source` column"
            if declared in ("sports", "sports_bet", "sportsbook", "draftkings", "fanduel", "betmgm", "pinnacle"):
                return "sports", "explicit `source` column"
            if declared in ("deposit", "cash", "bankroll", "withdrawal"):
                return "deposit", "explicit `source` column"

    stem = path.stem.lower()
    for source, tokens in FILENAME_HINTS.items():
        if any(token in stem for token in tokens):
            return source, f"filename token '{next(t for t in tokens if t in stem)}'"

    header_set = set(headers)
    for source, signature in HEADER_SIGNATURES.items():
        hit = header_set.intersection(signature)
        if hit:
            return source, f"header column {sorted(hit)[0]!r}"

    sides = {str(row.get("side", "")).strip().upper() for row in rows}
    for source, signature in SIDE_SIGNATURES.items():
        hit = sides.intersection(signature)
        if hit:
            return source, f"side value {sorted(hit)[0]!r}"

    raise ClassificationError(
        f"Cannot tell what {path.name} is. Add a `source` column (spot|polymarket|options), "
        f"or rename the file to include one of those words."
    )


def _carry_notes(trade: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Preserves a `notes` or `strategy` column from the CSV into the ledger row.

    WITHOUT THIS THE ATTRIBUTION LOOP IS BROKEN. The ingestors build their own
    `notes` text ("Manual Polymarket entry"), which overwrote whatever the file
    carried - so an execution receipt written with `strategy:dutched_arb;` reached
    the ledger untagged, counted against no capital bucket, and silently loosened
    every ceiling. Caught by the round-trip test, not by inspection.

    A `strategy` column is accepted as a convenience and normalised to the same
    tag, so a hand-written CSV does not need to know the tag format.
    """
    from ..interfaces.monarch_hook import strategy_tag

    extra = str(row.get("notes") or "").strip()
    strategy = str(row.get("strategy") or "").strip()
    if strategy:
        tag = strategy_tag(strategy)
        if tag not in extra:
            extra = f"{tag} {extra}".strip()
    if extra:
        trade["notes"] = f"{extra} | {trade.get('notes', '')}".strip(" |")
    return trade


def load_polymarket_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Generic Polymarket CSV -> ledger transactions.

    Columns: timestamp, symbol, side, quantity, price, [fee], [tx_hash].
    A REDEEM row is priced at $1.00 by the lot engine regardless of any price
    column, matching how a resolved winning share actually settles.
    """
    trades: List[Dict[str, Any]] = []
    if not csv_path.exists():
        return trades
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            clean = {str(k).strip().lower(): v for k, v in row.items() if k}
            side = str(clean.get("side", "BUY")).strip().upper()
            symbol = str(clean.get("symbol") or clean.get("market") or "POLYMARKET_POSITION").strip()
            quantity = float(clean.get("quantity") or clean.get("size") or 0.0)
            timestamp = str(clean.get("timestamp") or clean.get("date") or "").strip()
            fee = float(clean.get("fee") or 0.0)
            tx_hash = str(clean.get("tx_hash") or clean.get("id") or "").strip() or _row_fingerprint(clean, "polymarket")

            if side in ("REDEEM", "REDEMPTION"):
                trade = PolymarketIngestor.create_redemption_trade(symbol, quantity, timestamp, fee, tx_hash)
            else:
                trade = PolymarketIngestor.create_manual_trade(
                    symbol, side, quantity, float(clean.get("price") or 0.0), timestamp, fee)
                trade["tx_hash"] = tx_hash
            trades.append(_carry_notes(trade, clean))
    return trades


def load_spot_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Spot CSV -> transactions, backfilling a content-hash id when the export has none."""
    trades = SpotIngestor.load_from_csv(csv_path)
    if not trades:
        return trades
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))
    for trade, raw in zip(trades, raw_rows):
        clean = {str(k).strip().lower(): v for k, v in raw.items() if k}
        if not str(clean.get("tx_hash") or "").strip():
            trade["tx_hash"] = _row_fingerprint(clean, "spot")
        _carry_notes(trade, clean)
    return trades


def load_options_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Options CSV -> transactions, backfilling a content-hash id when the export has none."""
    trades = OptionsIngestor.load_from_csv(csv_path)
    if not trades:
        return trades
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))
    for trade, raw in zip(trades, raw_rows):
        clean = {str(k).strip().lower(): v for k, v in raw.items() if k}
        if not str(clean.get("tx_hash") or "").strip():
            trade["tx_hash"] = _row_fingerprint(clean, "options")
        _carry_notes(trade, clean)
    return trades


def load_hyperliquid_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Hyperliquid perp fills -> ledger transactions.

    Booked under `asset_class = "crypto_perp"`, NOT crypto_spot. The FIFO engine
    treats them identically for cost basis, but keeping them a distinct class
    matters twice over: they show separately in the HUD breakdown, and the
    Polymarket category sizer filters on `prediction_market`, so perp history
    cannot leak into a prediction-market win rate and size those positions off
    the wrong book.

    PERP TAX TREATMENT IS NOT MODELLED. These are booked as ordinary capital
    gains like any other position. Funding payments in particular are periodic
    income rather than price appreciation, and the basis harvester deliberately
    does not send them here - see its `_emit_receipts`. Anything beyond
    straightforward capital gain treatment needs a CPA, not this loader.
    """
    trades: List[Dict[str, Any]] = []
    if not csv_path.exists():
        return trades
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            clean = {str(k).strip().lower(): v for k, v in row.items() if k}
            symbol = str(clean.get("symbol") or "").strip()
            timestamp = str(clean.get("timestamp") or clean.get("date") or "").strip()
            if not symbol or not timestamp:
                continue
            try:
                quantity = float(clean.get("quantity") or clean.get("size") or 0.0)
                price = float(clean.get("price") or 0.0)
            except (TypeError, ValueError):
                continue
            if quantity <= 0:
                continue
            tx_hash = str(clean.get("tx_hash") or clean.get("id") or "").strip()                 or _row_fingerprint(clean, "hyperliquid")
            side = str(clean.get("side", "BUY")).strip().upper()
            is_funding = side in ("INCOME", "EXPENSE")
            asset_class = "crypto_perp_funding" if is_funding else "crypto_perp"
            default_notes = "Hyperliquid funding payment" if is_funding else "Hyperliquid perp fill"
            trade = {
                "source": "hyperliquid",
                "tx_hash": tx_hash,
                "timestamp": timestamp,
                "asset_class": asset_class,
                "symbol": symbol.upper(),
                "side": side,
                "quantity": quantity,
                "price": price,
                "fee": float(clean.get("fee") or 0.0),
                "total_value": quantity * price,
                "notes": default_notes,
            }
            trades.append(_carry_notes(trade, clean))
    return trades


def load_tradovate_csv(path: Path) -> List[Dict[str, Any]]:
    """Loads Tradovate / CME futures fills exported as receipts."""
    trades = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k}
            symbol = clean.get("symbol") or clean.get("contract") or ""
            timestamp = clean.get("timestamp") or clean.get("time") or clean.get("date") or ""
            if not symbol or not timestamp:
                continue
            try:
                quantity = float(clean.get("quantity") or clean.get("size") or clean.get("contracts") or 0.0)
                price = float(clean.get("price") or 0.0)
            except (TypeError, ValueError):
                continue
            if quantity <= 0:
                continue
            tx_hash = str(clean.get("tx_hash") or clean.get("id") or clean.get("order_id") or "").strip() or _row_fingerprint(clean, "tradovate")
            trade = {
                "source": "tradovate",
                "tx_hash": tx_hash,
                "timestamp": timestamp,
                "asset_class": "futures",
                "symbol": symbol.upper(),
                "side": str(clean.get("side", "BUY")).strip().upper(),
                "quantity": quantity,
                "price": price,
                "fee": float(clean.get("fee") or clean.get("commission") or 0.0),
                "total_value": quantity * price,
                "notes": "Tradovate CME futures fill",
            }
            trades.append(_carry_notes(trade, clean))
    return trades


def load_deposit_csv(path: Path) -> List[Dict[str, Any]]:
    """
    Cash deposits and withdrawals -> ledger rows under `asset_class = "cash"`.

    Columns (extra columns ignored): timestamp, side (DEPOSIT | WITHDRAWAL),
    amount (or quantity / total_value), [symbol, default USDC], [tx_hash],
    [notes]. Quantity is the amount and the price is 1.0, so `total_value` is the
    dollar figure and the ledger's existing sums need no special case.

    This is the row that ROUND 33 makes the ledger's cash balance depend on. A
    ledger with deposit rows reports what was actually put in; a ledger without
    them, and nothing declared, reports $0.00 - never a placeholder.
    """
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for line_no, raw in enumerate(csv.DictReader(f), start=2):
            row = {str(k).strip().lower(): (v or "").strip() for k, v in raw.items() if k}
            side = str(row.get("side") or "DEPOSIT").strip().upper()
            if side not in ("DEPOSIT", "WITHDRAWAL"):
                raise ValueError(f"{path.name}:{line_no} side must be DEPOSIT or "
                                 f"WITHDRAWAL, got {side!r}")
            amount_text = (row.get("amount") or row.get("quantity")
                           or row.get("total_value") or row.get("usd") or "")
            try:
                amount = float(str(amount_text).replace(",", "").replace("$", ""))
            except ValueError:
                raise ValueError(f"{path.name}:{line_no} amount {amount_text!r} is not a number")
            if amount <= 0:
                raise ValueError(f"{path.name}:{line_no} amount must be positive; a "
                                 f"withdrawal is its own side, not a negative deposit")
            timestamp = str(row.get("timestamp") or row.get("date") or "").strip()
            symbol = str(row.get("symbol") or row.get("asset") or "USDC").strip().upper()
            tx_hash = str(row.get("tx_hash") or "").strip() or _row_fingerprint(row, "deposit")
            trade = {
                "source": "deposit", "tx_hash": tx_hash, "timestamp": timestamp,
                "asset_class": "cash", "symbol": symbol, "side": side,
                "quantity": amount, "price": 1.0, "fee": 0.0, "total_value": amount,
                "notes": f"{side.title()} of {symbol}",
            }
            out.append(_carry_notes(trade, row))
    return out


def load_sports_csv(path: Path) -> List[Dict[str, Any]]:
    """
    Loads sports wagers and settlements exported from sportsbooks.

    No `_carry_notes` pass here, unlike the other loaders: the ingestor already
    writes the `strategy:` tag itself (reading a `strategy` column when the file
    has one), and running both would emit the tag twice into the same note.
    """
    try:
        from ..config import load_config
        gambling = load_config().get("gambling", {}) or {}
    except Exception:
        gambling = {}
    tolerance = gambling.get("odds_payout_tolerance_pct")
    return SportsBettingIngestor.load_from_csv(
        path,
        default_odds_format=gambling.get("default_odds_format") or None,
        tolerance_pct=None if tolerance is None else float(tolerance))


LOADERS = {
    "hyperliquid": load_hyperliquid_csv,
    "polymarket": load_polymarket_csv,
    "spot": load_spot_csv,
    "options": load_options_csv,
    "tradovate": load_tradovate_csv,
    "sports": load_sports_csv,
    "deposit": load_deposit_csv,
}


class CSVWatcher:
    """
    Polls a drop folder and ingests whatever lands in it.

    `scan_once()` is the whole engine; `watch()` just calls it on a timer. Both
    are safe to run repeatedly - a file is only ever processed once because
    processing ends with a move out of the watched folder.
    """

    def __init__(self,
                 imports_dir: Optional[Path] = None,
                 db_path: Optional[Path] = None,
                 archive: bool = True):
        self.imports_dir = Path(imports_dir) if imports_dir else DEFAULT_IMPORTS_DIR
        self.processed_dir = self.imports_dir / "processed"
        self.failed_dir = self.imports_dir / "failed"
        self.db_path = db_path
        self.archive = archive
        self._stat_cache: Dict[str, Tuple[int, float]] = {}
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for directory in (self.imports_dir, self.processed_dir, self.failed_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def pending_files(self) -> List[Path]:
        """CSVs sitting directly in the drop folder (archive subfolders are ignored)."""
        return sorted(
            p for p in self.imports_dir.glob("*.csv")
            if p.is_file() and p.parent == self.imports_dir
        )

    def is_stable(self, path: Path) -> bool:
        """
        True once the file's (size, mtime) is unchanged since the previous poll.

        The first sighting always returns False, so a file is picked up on the
        NEXT scan - one deliberate cycle of latency bought in exchange for never
        parsing a partially copied export.
        """
        try:
            stat = path.stat()
        except OSError:
            return False
        signature = (stat.st_size, stat.st_mtime)
        previous = self._stat_cache.get(str(path))
        self._stat_cache[str(path)] = signature
        return previous == signature and stat.st_size > 0

    @staticmethod
    def read_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = _normalise_headers(reader.fieldnames)
            rows = [{str(k).strip().lower(): v for k, v in row.items() if k} for row in reader]
        return rows, headers

    def _archive_to(self, path: Path, destination_dir: Path) -> Optional[Path]:
        """Moves the file, timestamp-suffixed so re-dropping the same name never clobbers."""
        if not self.archive:
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = destination_dir / f"{path.stem}_{stamp}{path.suffix}"
        counter = 1
        while target.exists():
            target = destination_dir / f"{path.stem}_{stamp}_{counter}{path.suffix}"
            counter += 1
        try:
            shutil.move(str(path), str(target))
            self._stat_cache.pop(str(path), None)
            return target
        except OSError as e:
            print(f"[WARN] Could not archive {path.name}: {e}")
            return None

    def ingest_file(self, path: Path) -> Dict[str, Any]:
        """
        Classifies, parses and commits one CSV. Never raises - the result dict
        carries the outcome so one bad file cannot abort a batch of good ones.
        """
        result: Dict[str, Any] = {
            "file": path.name, "status": "failed", "source": None,
            "rows": 0, "reason": "", "archived_to": None,
        }
        try:
            rows, headers = self.read_rows(path)
            if not rows:
                raise ValueError("file contains a header but no data rows")

            source, reason = classify_csv(path, rows, headers)
            result["source"] = source
            result["reason"] = f"classified as {source} by {reason}"

            transactions = LOADERS[source](path)
            transactions = [t for t in transactions if str(t.get("timestamp", "")).strip()]
            if not transactions:
                raise ValueError("no rows carried a usable timestamp")

            process_batch(transactions, db_path=self.db_path)
            self.backfill_strategy_tags(transactions)
            result["status"] = "ok"
            result["rows"] = len(transactions)
            result["archived_to"] = str(self._archive_to(path, self.processed_dir) or "")
        except (ClassificationError, ValueError, KeyError, OSError, UnicodeDecodeError) as e:
            result["reason"] = f"{type(e).__name__}: {e}"
            result["archived_to"] = str(self._archive_to(path, self.failed_dir) or "")
        return result

    def backfill_strategy_tags(self, transactions: List[Dict[str, Any]]) -> int:
        """
        Attaches a strategy tag to a row that was already in the ledger untagged.

        THE RACE THIS CLOSES. An execution receipt and the Data API sync describe
        the same fill. The ledger dedupes on (source, tx_hash, symbol, side) with
        ON CONFLICT IGNORE, so whichever arrives second is DISCARDED - and if that
        is the receipt, its strategy tag is discarded with it. The position then
        counts against no capital bucket and every ceiling silently loosens.

        Re-inserting is not an option (that would double the fill), so the tag is
        written onto the row that won instead. Matching is on the full unique key,
        not `tx_hash` alone: one Polygon transaction can carry several markets, and
        keying on the hash would stamp one strategy's tag onto another's position.

        The `NOT LIKE '%strategy:%'` guard means an already-attributed row is never
        re-attributed - a later strategy cannot steal an earlier one's trade.

        Returns how many rows were tagged.
        """
        from ..interfaces.monarch_hook import STRATEGY_TAG_PREFIX

        tagged = [t for t in transactions
                  if STRATEGY_TAG_PREFIX in str(t.get("notes") or "")]
        if not tagged:
            return 0

        conn = get_connection(self.db_path)
        updated = 0
        try:
            with conn:
                for tx in tagged:
                    note = str(tx.get("notes") or "")
                    tag = next((token for token in note.split()
                                if token.startswith(STRATEGY_TAG_PREFIX)), "")
                    if not tag:
                        continue
                    cursor = conn.execute(
                        """
                        UPDATE transactions
                        SET notes = COALESCE(notes || ' ', '') || ?
                        WHERE tx_hash = ? AND source = ? AND symbol = ? AND side = ?
                          AND (notes IS NULL OR notes NOT LIKE '%strategy:%')
                        """,
                        (tag, tx.get("tx_hash"), tx.get("source"), tx.get("symbol"),
                         str(tx.get("side", "")).upper()))
                    updated += cursor.rowcount or 0
        except Exception as e:
            print(f"[WARN] Could not back-fill strategy tags ({type(e).__name__}: {e}); "
                  f"affected positions will not count against their capital bucket.")
        finally:
            conn.close()

        if updated:
            print(f"[INFO] Attached a strategy tag to {updated} row(s) that were already "
                  f"in the ledger untagged.")
        return updated

    def scan_once(self, require_stable: bool = True) -> List[Dict[str, Any]]:
        """
        One sweep of the drop folder.

        `require_stable=False` skips the two-poll settling check - correct for a
        one-shot manual import where nothing is being copied concurrently, wrong
        for the polling loop.
        """
        self.ensure_dirs()
        results = []
        for path in self.pending_files():
            if require_stable and not self.is_stable(path):
                print(f"[WAIT] {path.name} is still changing on disk; deferring to next scan.")
                continue
            result = self.ingest_file(path)
            marker = "OK " if result["status"] == "ok" else "ERR"
            print(f"[{marker}] {result['file']}: {result['reason']}"
                  + (f" ({result['rows']} rows)" if result["status"] == "ok" else ""))
            results.append(result)
        return results

    def watch(self, interval_s: float = 5.0, max_cycles: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Poll loop. `max_cycles` bounds the run (tests use it; Ctrl-C ends a live one).
        """
        print(f"[WATCH] Monitoring {self.imports_dir} every {interval_s:g}s. Ctrl-C to stop.")
        all_results: List[Dict[str, Any]] = []
        cycle = 0
        try:
            while max_cycles is None or cycle < max_cycles:
                all_results.extend(self.scan_once())
                cycle += 1
                if max_cycles is None or cycle < max_cycles:
                    time.sleep(interval_s)
        except KeyboardInterrupt:
            print("\n[WATCH] Stopped.")
        return all_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch data/imports/ and auto-ingest trade CSVs")
    parser.add_argument("--dir", type=Path, default=None, help="Folder to watch (default: data/imports)")
    parser.add_argument("--db", type=Path, default=None, help="SQLite ledger path override")
    parser.add_argument("--watch", action="store_true", help="Poll continuously instead of a single sweep")
    parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds (default: 5)")
    parser.add_argument("--cycles", type=int, default=None, help="Stop after N poll cycles")
    parser.add_argument("--no-archive", action="store_true", help="Leave files in place after ingesting")
    args = parser.parse_args()

    init_db(args.db)
    watcher = CSVWatcher(imports_dir=args.dir, db_path=args.db, archive=not args.no_archive)

    if args.watch:
        results = watcher.watch(interval_s=args.interval, max_cycles=args.cycles)
    else:
        # A one-shot run has no concurrent writer to race, so files are taken immediately.
        results = watcher.scan_once(require_stable=False)

    ok = sum(1 for r in results if r["status"] == "ok")
    rows = sum(r["rows"] for r in results)
    print(f"\n[DONE] {ok}/{len(results)} files ingested, {rows} transactions committed.")


if __name__ == "__main__":
    main()
