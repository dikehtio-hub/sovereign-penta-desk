"""
Data Access Repository for HL_Monarch.
Provides high-speed batch inserts and analytical queries.
"""
import logging
import time
import sqlite3
from typing import List, Dict, Any, Optional
from storage.db import DatabaseManager
from config.settings import (
    SNAPSHOT_RETENTION_HOURS,
    CLUSTER_RETENTION_HOURS,
    TRADE_RETENTION_HOURS,
)

logger = logging.getLogger("Repository")

class MarketRepository:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()
        # What the last prune's measurement pass did (Round 34), for run_maintenance.
        self.last_persistence: Optional[Dict[str, Any]] = None

    def upsert_assets(self, assets_data: List[Dict[str, Any]]):
        """Insert or update asset metadata."""
        if not assets_data:
            return
        sql = """
        INSERT INTO assets (coin, dex, sz_decimals, max_leverage, only_isolated, updated_at)
        VALUES (:coin, :dex, :sz_decimals, :max_leverage, :only_isolated, CURRENT_TIMESTAMP)
        ON CONFLICT(coin) DO UPDATE SET
            dex = excluded.dex,
            sz_decimals = excluded.sz_decimals,
            max_leverage = excluded.max_leverage,
            only_isolated = excluded.only_isolated,
            updated_at = CURRENT_TIMESTAMP;
        """
        with self.db.connection as conn:
            conn.executemany(sql, assets_data)

    def insert_snapshots(self, snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch insert real-time asset snapshots and refresh the current-state table.

        Returns {"written": n, "skipped": [coins]}. Round 121 (Ruling R119-1.B item 2): the batch is one
        transaction, and on 2026-09-06 a single coin absent from `assets` (para:CIFR, listed after startup)
        made SQLite reject all 442 rows every 10 s for 9 h 18 min. On IntegrityError this now falls back to
        row-by-row, skips the offending rows and NAMES the coins, so the stream degrades by one coin, not to zero.
        """
        if not snapshots:
            return {"written": 0, "skipped": []}
        sql = """
        INSERT INTO asset_snapshots (
            timestamp, coin, dex, mark_px, mid_px, oracle_px,
            open_interest, notional_oi, funding_rate, premium, day_ntl_vlm
        ) VALUES (
            :timestamp, :coin, :dex, :mark_px, :mid_px, :oracle_px,
            :open_interest, :notional_oi, :funding_rate, :premium, :day_ntl_vlm
        );
        """
        # Keep latest_snapshots in step in the same transaction, guarded on
        # timestamp so an out-of-order or replayed batch cannot move it backwards.
        latest_sql = """
        INSERT INTO latest_snapshots (
            coin, timestamp, dex, mark_px, mid_px, oracle_px,
            open_interest, notional_oi, funding_rate, premium, day_ntl_vlm
        ) VALUES (
            :coin, :timestamp, :dex, :mark_px, :mid_px, :oracle_px,
            :open_interest, :notional_oi, :funding_rate, :premium, :day_ntl_vlm
        )
        ON CONFLICT(coin) DO UPDATE SET
            timestamp = excluded.timestamp,
            dex = excluded.dex,
            mark_px = excluded.mark_px,
            mid_px = excluded.mid_px,
            oracle_px = excluded.oracle_px,
            open_interest = excluded.open_interest,
            notional_oi = excluded.notional_oi,
            funding_rate = excluded.funding_rate,
            premium = excluded.premium,
            day_ntl_vlm = excluded.day_ntl_vlm
        WHERE excluded.timestamp >= latest_snapshots.timestamp;
        """
        try:
            with self.db.connection as conn:
                conn.executemany(sql, snapshots)
                conn.executemany(latest_sql, snapshots)
            return {"written": len(snapshots), "skipped": []}
        except sqlite3.IntegrityError as exc:
            skipped: List[str] = []
            written = 0
            for snap in snapshots:
                try:
                    with self.db.connection as conn:
                        conn.execute(sql, snap)
                        conn.execute(latest_sql, snap)
                    written += 1
                except sqlite3.IntegrityError:
                    skipped.append(str(snap.get("coin")))
            names = sorted(set(skipped))
            logging.getLogger("HL_Collector").warning(
                "insert_snapshots: batch rejected (%s); wrote %d row-by-row, skipped %d row(s) for coin(s) unknown to assets: %s",
                exc, written, len(skipped), ", ".join(names[:10]))
            return {"written": written, "skipped": names}

    def insert_trades(self, trades: List[Dict[str, Any]]) -> int:
        """Insert trades ignoring duplicates, return number of new trades."""
        if not trades:
            return 0
        sql = """
        INSERT OR IGNORE INTO trades (
            tid, coin, side, px, sz, notional, time, hash, is_liquidation
        ) VALUES (
            :tid, :coin, :side, :px, :sz, :notional, :time, :hash, :is_liquidation
        );
        """
        with self.db.connection as conn:
            cursor = conn.executemany(sql, trades)
            return cursor.rowcount

    def insert_liquidation_events(self, events: List[Dict[str, Any]]):
        """Record detected liquidation events."""
        if not events:
            return
        sql = """
        INSERT INTO liquidation_events (
            coin, side, px, sz, notional, time, source, note
        ) VALUES (
            :coin, :side, :px, :sz, :notional, :time, :source, :note
        );
        """
        with self.db.connection as conn:
            conn.executemany(sql, events)

    def insert_orderbook_snapshots(self, snapshots: List[Dict[str, Any]]):
        """Batch form of insert_orderbook_snapshot - one transaction per sampling pass."""
        if not snapshots:
            return
        sql = """
        INSERT INTO orderbook_snapshots (
            timestamp, coin, best_bid, best_ask, spread, spread_bps,
            bid_depth_1pct, ask_depth_1pct, bid_depth_total, ask_depth_total, imbalance_ratio
        ) VALUES (
            :timestamp, :coin, :best_bid, :best_ask, :spread, :spread_bps,
            :bid_depth_1pct, :ask_depth_1pct, :bid_depth_total, :ask_depth_total, :imbalance_ratio
        );
        """
        with self.db.connection as conn:
            conn.executemany(sql, snapshots)

    def get_latest_orderbook_spreads(self, within_hours: float = 24.0,
                                     now_ms: Optional[int] = None) -> Dict[str, float]:
        """
        {coin: spread_bps} from each coin's NEWEST orderbook_snapshots row no
        older than `within_hours`.

        Round 39: candidate ranking nets a coin's funding against its last
        measured spread. A reading older than a day is history, not a cost
        estimate, so it is left out and the coin ranks on gross again.
        """
        now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
        cutoff = now_ms - int(float(within_hours) * 3_600_000)
        sql = """
        SELECT o.coin, o.spread_bps
        FROM orderbook_snapshots o
        JOIN (SELECT coin, MAX(timestamp) AS ts
              FROM orderbook_snapshots WHERE timestamp >= ? GROUP BY coin) m
          ON m.coin = o.coin AND m.ts = o.timestamp;
        """
        with self.db.connection as conn:
            rows = conn.execute(sql, (cutoff,)).fetchall()
        out: Dict[str, float] = {}
        for coin, spread in rows:
            try:
                out[str(coin)] = float(spread)
            except (TypeError, ValueError):
                continue
        return out

    def insert_orderbook_snapshot(self, snapshot: Dict[str, Any]):
        """Record order book spread and depth snapshot."""
        sql = """
        INSERT INTO orderbook_snapshots (
            timestamp, coin, best_bid, best_ask, spread, spread_bps,
            bid_depth_1pct, ask_depth_1pct, bid_depth_total, ask_depth_total, imbalance_ratio
        ) VALUES (
            :timestamp, :coin, :best_bid, :best_ask, :spread, :spread_bps,
            :bid_depth_1pct, :ask_depth_1pct, :bid_depth_total, :ask_depth_total, :imbalance_ratio
        );
        """
        with self.db.connection as conn:
            conn.execute(sql, snapshot)

    def insert_liquidation_clusters(self, clusters: List[Dict[str, Any]]):
        """Record calculated liquidation clusters."""
        if not clusters:
            return
        sql = """
        INSERT INTO liquidation_clusters (
            timestamp, coin, side, leverage, estimated_px, distance_pct,
            estimated_notional, risk_level
        ) VALUES (
            :timestamp, :coin, :side, :leverage, :estimated_px, :distance_pct,
            :estimated_notional, :risk_level
        );
        """
        with self.db.connection as conn:
            conn.executemany(sql, clusters)

    # --- Analytical Query Methods ---

    SNAPSHOT_COLUMNS = (
        "coin, timestamp, dex, mark_px, mid_px, oracle_px, "
        "open_interest, notional_oi, funding_rate, premium, day_ntl_vlm"
    )

    def get_latest_snapshots(self, coins: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get the most recent snapshot for the given coins, or for every coin.

        Served from the materialised latest_snapshots table, so cost is bounded by
        the size of the universe rather than by history. Databases written before
        that table existed fall back to the (much slower) scan over asset_snapshots
        and backfill themselves on the next collector poll.
        """
        with self.db.connection as conn:
            if coins:
                placeholders = ','.join('?' for _ in coins)
                sql = (
                    f"SELECT {self.SNAPSHOT_COLUMNS} FROM latest_snapshots "
                    f"WHERE coin IN ({placeholders}) ORDER BY notional_oi DESC;"
                )
                rows = conn.execute(sql, coins).fetchall()
            else:
                sql = (
                    f"SELECT {self.SNAPSHOT_COLUMNS} FROM latest_snapshots "
                    f"ORDER BY notional_oi DESC;"
                )
                rows = conn.execute(sql).fetchall()

            if rows:
                return [dict(row) for row in rows]
            return self._legacy_latest_snapshots(conn, coins)

    def _legacy_latest_snapshots(self, conn, coins: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Pre-migration fallback: derive the latest row per coin from history."""
        if coins:
            placeholders = ','.join('?' for _ in coins)
            sql = f"""
            SELECT s.* FROM asset_snapshots s
            INNER JOIN (
                SELECT coin, MAX(timestamp) as max_ts
                FROM asset_snapshots
                WHERE coin IN ({placeholders})
                GROUP BY coin
            ) m ON s.coin = m.coin AND s.timestamp = m.max_ts
            ORDER BY s.notional_oi DESC;
            """
            cursor = conn.execute(sql, coins)
        else:
            sql = """
            SELECT s.* FROM asset_snapshots s
            INNER JOIN (
                SELECT coin, MAX(timestamp) as max_ts
                FROM asset_snapshots
                GROUP BY coin
            ) m ON s.coin = m.coin AND s.timestamp = m.max_ts
            ORDER BY s.notional_oi DESC;
            """
            cursor = conn.execute(sql)
        return [dict(row) for row in cursor.fetchall()]

    def backfill_latest_snapshots(self) -> int:
        """
        Populate latest_snapshots from existing history (one-time migration).

        Safe to re-run: it only overwrites a row when the historical snapshot is at
        least as new as what the table already holds.
        """
        sql = """
        INSERT INTO latest_snapshots (
            coin, timestamp, dex, mark_px, mid_px, oracle_px,
            open_interest, notional_oi, funding_rate, premium, day_ntl_vlm
        )
        SELECT s.coin, s.timestamp, s.dex, s.mark_px, s.mid_px, s.oracle_px,
               s.open_interest, s.notional_oi, s.funding_rate, s.premium, s.day_ntl_vlm
        FROM asset_snapshots s
        INNER JOIN (
            SELECT coin, MAX(timestamp) AS max_ts FROM asset_snapshots GROUP BY coin
        ) m ON s.coin = m.coin AND s.timestamp = m.max_ts
        WHERE true
        ON CONFLICT(coin) DO UPDATE SET
            timestamp = excluded.timestamp,
            dex = excluded.dex,
            mark_px = excluded.mark_px,
            mid_px = excluded.mid_px,
            oracle_px = excluded.oracle_px,
            open_interest = excluded.open_interest,
            notional_oi = excluded.notional_oi,
            funding_rate = excluded.funding_rate,
            premium = excluded.premium,
            day_ntl_vlm = excluded.day_ntl_vlm
        WHERE excluded.timestamp >= latest_snapshots.timestamp;
        """
        with self.db.connection as conn:
            cursor = conn.execute(sql)
            return max(0, cursor.rowcount)

    def get_total_oi_by_dex(self) -> Dict[str, float]:
        """Aggregate total notional OI per DEX from each coin's most recent snapshot."""
        with self.db.connection as conn:
            rows = conn.execute(
                "SELECT dex, SUM(notional_oi) AS total_oi FROM latest_snapshots GROUP BY dex;"
            ).fetchall()
            if rows:
                return {row['dex']: float(row['total_oi'] or 0.0) for row in rows}
            totals: Dict[str, float] = {}
            for snap in self._legacy_latest_snapshots(conn, None):
                totals[snap["dex"]] = totals.get(snap["dex"], 0.0) + float(snap.get("notional_oi") or 0.0)
            return totals

    def get_recent_liquidations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch the most recent liquidation events."""
        with self.db.connection as conn:
            sql = """
            SELECT * FROM liquidation_events
            ORDER BY time DESC
            LIMIT ?;
            """
            cursor = conn.execute(sql, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_trades(self, coin: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent trades."""
        with self.db.connection as conn:
            if coin:
                sql = "SELECT * FROM trades WHERE coin = ? ORDER BY time DESC LIMIT ?"
                cursor = conn.execute(sql, (coin, limit))
            else:
                sql = "SELECT * FROM trades ORDER BY time DESC LIMIT ?"
                cursor = conn.execute(sql, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_clusters(self, coin: str) -> List[Dict[str, Any]]:
        """Get latest liquidation price clusters for a coin."""
        with self.db.connection as conn:
            sql = """
            SELECT c.* FROM liquidation_clusters c
            INNER JOIN (
                SELECT coin, MAX(timestamp) as max_ts
                FROM liquidation_clusters
                WHERE coin = ?
                GROUP BY coin
            ) m ON c.coin = m.coin AND c.timestamp = m.max_ts
            ORDER BY c.estimated_px ASC;
            """
            cursor = conn.execute(sql, (coin,))
            return [dict(row) for row in cursor.fetchall()]

    def upsert_whale_wallet(
        self,
        address: str,
        coin: str,
        notional: float,
        account_value: float = 0.0,
        total_position_value: float = 0.0,
        is_liquidator: bool = False
    ):
        """Insert or update discovered whale wallet."""
        now_ts = int(time.time() * 1000)
        with self.db.connection as conn:
            sql = """
            INSERT INTO whale_wallets (
                address, discovered_at, first_coin, first_notional,
                total_position_value, account_value, is_liquidator, last_scanned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
                total_position_value = CASE WHEN ? > 0 THEN ? ELSE total_position_value END,
                account_value = CASE WHEN ? > 0 THEN ? ELSE account_value END,
                is_liquidator = is_liquidator OR ?,
                last_scanned_at = ?;
            """
            conn.execute(sql, (
                address.lower(), now_ts, coin, notional,
                total_position_value, account_value, int(is_liquidator), now_ts,
                total_position_value, total_position_value,
                account_value, account_value,
                int(is_liquidator), now_ts
            ))

    def get_whale_wallets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch discovered whale wallets ordered by total position value or discovery time."""
        with self.db.connection as conn:
            sql = """
            SELECT * FROM whale_wallets
            ORDER BY total_position_value DESC, discovered_at DESC
            LIMIT ?;
            """
            cursor = conn.execute(sql, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # --- Retention & Maintenance ---

    def prune_old_data(
        self,
        snapshot_retention_hours: float = SNAPSHOT_RETENTION_HOURS,
        cluster_retention_hours: float = CLUSTER_RETENTION_HOURS,
        trade_retention_hours: float = TRADE_RETENTION_HOURS,
        persist_first: bool = True,
    ) -> Dict[str, int]:
        """
        Delete rows older than the configured retention windows.

        asset_snapshots and liquidation_clusters gain a row per asset per poll, so
        the DB grows without bound if nothing prunes it. The newest row per coin is
        always kept, so a long collector outage cannot starve get_latest_snapshots.

        ROUND 34: MEASURE BEFORE DELETING. Rows about to age out are first reduced
        to basis windows and cascade excursions (storage/incremental_persistence),
        which are never pruned. If that pass FAILS, the tables it reads from -
        asset_snapshots and liquidation_events - are NOT pruned this cycle. The
        database grows a little until the next successful pass; that is the right
        side to fail on, because a pruned row cannot be measured later and a
        warning every five minutes is impossible to miss. The other tables prune
        as before.
        """
        now_ms = int(time.time() * 1000)
        hour_ms = 3600 * 1000
        deleted: Dict[str, int] = {}

        # Round 35: orderbook_snapshots joins the measured set - the spread at a
        # window's entry is read from it, so it must not be pruned unmeasured.
        measured_tables = {"asset_snapshots", "liquidation_events", "orderbook_snapshots"}
        skip_tables: set = set()
        self.last_persistence = None
        if persist_first:
            try:
                from storage.incremental_persistence import persist_completed_measurements
                self.last_persistence = persist_completed_measurements(
                    self.db.connection, now_ms=now_ms,
                    snapshot_retention_hours=snapshot_retention_hours,
                    trade_retention_hours=trade_retention_hours)
            except Exception as e:
                logger.warning(
                    "Measurement persistence FAILED (%s); asset_snapshots and "
                    "liquidation_events are NOT pruned this pass", e)
                self.last_persistence = {"error": str(e), "pruned_measured_tables": False}
                skip_tables = measured_tables

        plan = [
            (
                "asset_snapshots",
                """
                DELETE FROM asset_snapshots
                WHERE timestamp < ?
                  AND id NOT IN (SELECT MAX(id) FROM asset_snapshots GROUP BY coin);
                """,
                snapshot_retention_hours,
            ),
            (
                "liquidation_clusters",
                """
                DELETE FROM liquidation_clusters
                WHERE timestamp < ?
                  AND id NOT IN (SELECT MAX(id) FROM liquidation_clusters GROUP BY coin);
                """,
                cluster_retention_hours,
            ),
            (
                "orderbook_snapshots",
                "DELETE FROM orderbook_snapshots WHERE timestamp < ?;",
                snapshot_retention_hours,
            ),
            (
                "trades",
                "DELETE FROM trades WHERE time < ?;",
                trade_retention_hours,
            ),
            (
                "liquidation_events",
                "DELETE FROM liquidation_events WHERE time < ?;",
                trade_retention_hours,
            ),
        ]

        with self.db.connection as conn:
            for table, sql, hours in plan:
                if not hours or hours <= 0:
                    continue
                if table in skip_tables:
                    deleted[table] = 0
                    continue
                cutoff = now_ms - int(hours * hour_ms)
                try:
                    cursor = conn.execute(sql, (cutoff,))
                    deleted[table] = max(0, cursor.rowcount)
                except Exception as e:
                    logger.warning(f"Prune failed for {table}: {e}")
                    deleted[table] = 0
        return deleted

    def run_maintenance(self, vacuum: bool = False) -> Dict[str, Any]:
        """Prune expired rows, then checkpoint the WAL back into the main DB file."""
        deleted = self.prune_old_data()
        # Cheap and idempotent; keeps the current-state table correct on a DB that
        # predates it, or if a write was interrupted mid-batch.
        self.backfill_latest_snapshots()
        total_deleted = sum(deleted.values())
        if vacuum and total_deleted > 0:
            try:
                self.db.vacuum()
            except Exception as e:
                logger.warning(f"VACUUM skipped: {e}")
        busy, wal_pages, checkpointed = self.db.checkpoint("TRUNCATE")
        return {
            "deleted": deleted,
            "total_deleted": total_deleted,
            "persisted": self.last_persistence,
            "wal_busy": busy,
            "wal_pages": wal_pages,
            "checkpointed_pages": checkpointed,
            "db_bytes": self.db.page_size_bytes(),
        }
