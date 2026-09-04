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

DEPOSITS AND WITHDRAWALS (Round 33)
-----------------------------------
The liquid balance is READ FROM THE LEDGER, not from config.yaml. Seed it once:

    python -m Tax_Reserve_Agent.main seed-bankroll --paper-bankroll 10000

or drop a file whose name contains "deposit" / "bankroll":

    timestamp,side,amount,symbol
    2026-09-04 00:00:00,DEPOSIT,10000.00,USDC
    2026-09-10 00:00:00,WITHDRAWAL,2500.00,USDC

Until the ledger holds a deposit - or a bankroll is passed explicitly with
--cash (live) or --paper-bankroll (simulation) - the safe bankroll is $0.00 and
the order gate REFUSES. That is deliberate: it used to size against a number
typed into config.yaml, and nothing had ever measured it.
