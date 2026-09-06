"""
Execution receipts - the single writer for the fills drop folder.

A receipt is one filled trade, written as a CSV into `data/imports/` where
`csv_watcher` picks it up and ingests it with its strategy tag intact. That tag is
what places the position in a capital bucket; a fill that reaches the ledger
untagged counts against nothing and silently loosens every ceiling.

THIS LIVES IN THE TAX AGENT, NOT IN A BOT. Two separate trading projects
(Polymarket Monarch and HL Monarch) now write receipts, and the CSV contract -
column order, tag format, filename shape - belongs to whoever ingests them.
Duplicating the writer per bot is how the two drift until one of them silently
stops being attributed.

NEVER RAISES. A bookkeeping failure must not take down an execution path, so
every problem is reported and swallowed. The caller gets None and can log it.
"""
import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_IMPORTS_DIR = Path(__file__).parent.parent / "data" / "imports"

# The column order csv_watcher expects. `notes` is the load-bearing one.
RECEIPT_COLUMNS = ["timestamp", "symbol", "side", "quantity", "price",
                   "fee", "tx_hash", "source", "notes"]


def build_notes(strategy: str, exit_reason: Optional[str] = None,
                extra: Optional[str] = None,
                gross_edge: Optional[float] = None,
                after_tax_hurdle: Optional[float] = None) -> str:
    """
    The `notes` cell: `strategy:<name>; exit_reason:<reason>; edge:<f>; hurdle:<f>; <extra>`.

    Each tag is terminated with `;` because the ledger matches them with a LIKE.
    Without the terminator `strategy:sandbox` also matches `strategy:sandbox_v2`,
    pooling one strategy's exposure into another's bucket.

    `edge` and `hurdle` (Round 101, Ruling 100-b) are the gross edge the caller
    priced and the after-tax hurdle it had to clear, as fractions, so a journal
    can check the fill against the rule it was placed under without re-deriving
    either from the ledger. Both are optional: a fill that carries neither is
    reported as UNCHECKED, never as passing.
    """
    parts = [f"strategy:{str(strategy).strip()};"]
    if exit_reason:
        parts.append(f"exit_reason:{str(exit_reason).strip()};")
    if gross_edge is not None:
        parts.append(f"edge:{float(gross_edge):.4f};")
    if after_tax_hurdle is not None:
        parts.append(f"hurdle:{float(after_tax_hurdle):.4f};")
    if extra:
        parts.append(str(extra).strip())
    return " ".join(parts)


def log_execution_receipt(symbol: str,
                          side: str,
                          quantity: float,
                          price: float,
                          strategy: str,
                          venue: str = "polymarket",
                          fee: float = 0.0,
                          exit_reason: Optional[str] = None,
                          tx_hash: Optional[str] = None,
                          timestamp: Optional[str] = None,
                          imports_dir: Optional[Path] = None,
                          extra_notes: Optional[str] = None,
                          gross_edge: Optional[float] = None,
                          after_tax_hurdle: Optional[float] = None) -> Optional[Path]:
    """
    Writes one filled trade to the drop folder. Returns the path, or None.

    `venue` becomes part of the filename so `csv_watcher` can classify the file
    without guessing - it matches on filename tokens before falling back to
    headers. Use `polymarket` for anything the CTF/CLOB ledger should treat as a
    prediction-market position; `hyperliquid` fills are perpetuals and are
    labelled as such in the notes, since the ledger has no perp asset class.

    ONE FILE PER RECEIPT, with a uuid4 suffix. The watcher MOVES a file once it
    has ingested it, so appending to a shared file races that move; and two fills
    in the same millisecond are ordinary, so a clock suffix would collide and
    overwrite a real receipt.

    `tx_hash` should be the venue's own fill id where one exists. It is the
    ledger's dedupe key, so passing the real id is what stops the same fill being
    counted twice when another source imports it later.
    """
    try:
        quantity = float(quantity)
        price = float(price)
    except (TypeError, ValueError):
        print(f"[WARN] Receipt for {symbol} has a non-numeric size or price; not written.")
        return None
    if quantity <= 0:
        return None

    name = str(strategy or "unattributed").strip() or "unattributed"
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    target = Path(imports_dir) if imports_dir else DEFAULT_IMPORTS_DIR
    key = str(tx_hash) if tx_hash else f"{name}_{symbol}_{stamp}_{uuid.uuid4().hex[:8]}"

    try:
        target.mkdir(parents=True, exist_ok=True)
        filename = (f"fills_{venue}_{name}_"
                    f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_"
                    f"{uuid.uuid4().hex[:8]}.csv")
        path = target / filename
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(RECEIPT_COLUMNS)
            writer.writerow([stamp, symbol, str(side).upper(), f"{quantity:.8f}",
                             f"{price:.8f}", f"{float(fee):.8f}",
                             str(key).replace(" ", "_"), venue,
                             build_notes(name, exit_reason, extra_notes, gross_edge, after_tax_hurdle)])
        return path
    except Exception as e:
        print(f"[WARN] Could not write execution receipt for {symbol} ({type(e).__name__}: "
              f"{e}). The fill will reach the ledger UNTAGGED and will not count "
              f"against the {name} bucket.")
        return None


def receipt_row(path: Path) -> Dict[str, Any]:
    """Reads a receipt back. Test helper, and useful for debugging a drop folder."""
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.DictReader(handle))
