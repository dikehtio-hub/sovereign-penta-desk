CSV DROP FOLDER
===============
Drop trade-history CSVs directly in THIS folder. They are ingested into the
SQLite ledger and then moved into processed/ (success) or failed/ (rejected).

    python -m Tax_Reserve_Agent.main import     # one sweep, then show the HUD
    python -m Tax_Reserve_Agent.main watch      # poll every 5s until Ctrl-C

Columns (extra columns are ignored):
    timestamp, symbol, side, quantity, price, [fee], [tx_hash]

The source is detected from a `source` column, then the filename, then the
headers, then the side values. A file that matches none of these is REJECTED
rather than guessed - rename it to include spot / polymarket / options, or add a
`source` column. See samples/ for working examples of each shape.

Re-dropping the same file is safe: rows are deduplicated on their id, or on a
content hash when the export has no id column.
