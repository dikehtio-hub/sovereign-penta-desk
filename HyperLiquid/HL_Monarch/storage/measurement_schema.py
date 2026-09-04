"""
DDL for the flat measurement tables (Round 34, option b).

Kept in a module with NO imports so both `storage.db` (which applies it at
connection init) and `storage.incremental_persistence` (which fills it) can use
it without a cycle. Every statement is IF NOT EXISTS: a database written before
this round gains the tables on its next open.

WHY THESE TABLES EXIST. Raw snapshots run ~12M rows/day and are pruned at 192h.
Ruling D asks for 720h of observation across at least two regimes before the
basis edge is called enduring, and 720h cannot be held in a 192h window at any
disk size. So the raw rows are reduced, BEFORE they are deleted, to the two
things the walk-forward actually consumes: what a basis window realised, and
how far a cascade moved for and against a fade. Both are a few thousand rows a
day instead of twelve million, and neither is ever pruned.
"""

MEASUREMENT_SCHEMA_SQL = """
-- One row per (asset, hold, entry instant). Entries sit on a fixed epoch-aligned
-- grid so a re-run lands on the same instants and the UNIQUE constraint makes a
-- duplicate impossible rather than merely unlikely.
CREATE TABLE IF NOT EXISTS basis_realised_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    window_start_utc INTEGER NOT NULL,       -- unix ms
    window_end_utc INTEGER NOT NULL,         -- unix ms = start + hold
    hold_hours REAL NOT NULL,
    quote_apr_entry REAL,                    -- NULL: no quote within the gap tolerance at entry
    realised_apr REAL,                       -- NULL: coverage below the minimum; NEVER zero-filled
    observed_hours REAL NOT NULL,
    coverage REAL NOT NULL,                  -- observed_hours / hold_hours, 0..1
    funding_payments_count INTEGER NOT NULL,
    spread_bps_entry REAL,                   -- from orderbook_snapshots at entry, when one exists
    net_apr_after_fees REAL,                 -- NULL unless the spread was MEASURED
    fee_basis TEXT NOT NULL,                 -- 'measured' | 'unmeasured'
    regime_tag TEXT NOT NULL,                -- see incremental_persistence.regime_at
    regime_vol_pct REAL,
    regime_funding_apr REAL,
    entry_px REAL,
    exit_px REAL,
    samples INTEGER NOT NULL,
    persisted_at INTEGER NOT NULL,
    UNIQUE(asset, hold_hours, window_start_utc)
);
CREATE INDEX IF NOT EXISTS idx_brw_hold_start ON basis_realised_windows(hold_hours, window_start_utc);
CREATE INDEX IF NOT EXISTS idx_brw_asset_hold ON basis_realised_windows(asset, hold_hours);

-- One row per liquidation event. event_id IS liquidation_events.id, so the
-- primary key is the dedup. `source` is kept because the two event sources
-- answer different questions and must never be pooled (see wick_benchmark).
CREATE TABLE IF NOT EXISTS cascade_excursions (
    event_id INTEGER PRIMARY KEY,
    coin TEXT NOT NULL,
    timestamp_utc INTEGER NOT NULL,
    source TEXT NOT NULL,
    cascade_side TEXT NOT NULL,              -- raw event side: 'A' forced sell, 'B' forced buy
    fade_is_long INTEGER NOT NULL,
    notional_usd REAL NOT NULL,
    event_px REAL NOT NULL,
    entry_px REAL,                           -- first mark at or after the event
    mfe_5m REAL,  mae_5m REAL,
    mfe_15m REAL, mae_15m REAL,
    mfe_30m REAL, mae_30m REAL,
    mfe_60m REAL, mae_60m REAL,              -- any horizon is NULL when its window was unmeasurable
    samples_60m INTEGER NOT NULL,
    regime_tag TEXT NOT NULL,
    persisted_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cx_source_time ON cascade_excursions(source, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_cx_coin ON cascade_excursions(coin);

-- Where each materialiser got to. basis jobs store the last grid instant (ms);
-- the cascade job stores the last liquidation_events.id it looked at.
CREATE TABLE IF NOT EXISTS measurement_watermarks (
    job TEXT PRIMARY KEY,
    watermark INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    note TEXT
);
"""
