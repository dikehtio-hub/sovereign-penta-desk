"""
Self-Growing Whale Discovery & Tracker Engine for HL_Monarch.
Monitors real-time trade flows, identifies high-net-worth wallet addresses from raw fills,
auto-appends new whales to hyperliquidusers.txt, and scans their full on-chain portfolios.
"""
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Set, Optional
from pathlib import Path
from storage.repository import MarketRepository
from api.rest_client import HyperliquidRestClient
from config.settings import (
    ALL_CORE_WATCHLIST,
    WHALE_DISCOVERY_MIN_NOTIONAL_CORE,
    WHALE_DISCOVERY_MIN_NOTIONAL_EXOTIC,
)

logger = logging.getLogger("WhaleTracker")

class WhaleTracker:
    def __init__(
        self,
        users_file_path: Optional[str] = None,
        min_whale_notional: float = WHALE_DISCOVERY_MIN_NOTIONAL_CORE,
        auto_scan_portfolio: bool = True,
        min_whale_notional_exotic: float = WHALE_DISCOVERY_MIN_NOTIONAL_EXOTIC,
    ):
        if users_file_path is None:
            self.users_file = Path(__file__).resolve().parent.parent / "data" / "hyperliquidusers.txt"
        else:
            self.users_file = Path(users_file_path)

        self.min_whale_notional = min_whale_notional
        # A $25k fill is a whale on BTC and an impossibility on a thin exotic. The
        # flat floor meant the counterparties to exotic cascades - the accounts we
        # most want on the whale list - were never discovered at all.
        self.min_whale_notional_exotic = min_whale_notional_exotic
        self._core_coins = set(ALL_CORE_WATCHLIST)
        self.auto_scan = auto_scan_portfolio
        self.repo = MarketRepository()
        self.client = HyperliquidRestClient()
        self.known_addresses: Set[str] = set()
        self._file_lock = threading.Lock()
        # A cascade can surface dozens of new whales in one frame. Spawning a
        # thread per discovery let an unbounded number of REST calls run at once;
        # a small pool keeps portfolio scans off the hot path without the pile-up.
        self._scan_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="whale-scan")
        self._load_known_addresses()

    def _load_known_addresses(self):
        """Load known addresses from hyperliquidusers.txt into memory cache."""
        if self.users_file.exists():
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    for line in f:
                        addr = line.strip().lower()
                        if addr.startswith("0x") and len(addr) == 42:
                            self.known_addresses.add(addr)
                logger.info(f"Loaded {len(self.known_addresses)} known addresses into WhaleTracker.")
            except Exception as e:
                logger.error(f"Error loading addresses from {self.users_file}: {e}")

    def discovery_floor_for(self, coin: str) -> float:
        """
        Notional a fill must reach on this market to surface its counterparties.

        Core watchlist markets are deep, so the bar stays high; anything outside it
        is treated as a thin book where a far smaller fill is equally significant.
        """
        return (
            self.min_whale_notional if coin in self._core_coins
            else self.min_whale_notional_exotic
        )

    def on_trade_fill(self, trade: Dict[str, Any]) -> List[str]:
        """
        Process a live trade event.
        Extracts user addresses and auto-discovers new whale wallets.
        Returns list of newly discovered addresses.
        """
        notional = float(trade.get("notional") or (float(trade.get("px", 0)) * float(trade.get("sz", 0))))
        users = trade.get("users", [])
        coin = trade.get("coin", "UNKNOWN")

        if not users or notional < self.discovery_floor_for(coin):
            return []

        new_discoveries = []
        for user_addr in users:
            clean_addr = str(user_addr).strip().lower()
            if not clean_addr.startswith("0x") or len(clean_addr) != 42:
                continue

            if clean_addr not in self.known_addresses:
                self.known_addresses.add(clean_addr)
                new_discoveries.append(clean_addr)
                self._persist_new_address(clean_addr, coin, notional)

        return new_discoveries

    def _persist_new_address(self, address: str, coin: str, notional: float):
        """Append newly discovered whale to disk and database, then trigger background scan."""
        # 1. Append to hyperliquidusers.txt
        try:
            self.users_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.users_file, "a", encoding="utf-8") as f:
                f.write(f"{address}\n")
        except Exception as e:
            logger.error(f"Failed to append whale address {address} to file: {e}")

        # 2. Insert into SQLite whale_wallets table
        try:
            self.repo.upsert_whale_wallet(
                address=address,
                coin=coin,
                notional=notional
            )
        except Exception as e:
            logger.error(f"Failed to persist whale wallet {address} to DB: {e}")

        # 3. Async background portfolio scan
        if self.auto_scan:
            try:
                self._scan_pool.submit(self._scan_whale_portfolio, address, coin, notional)
            except RuntimeError:
                # Pool already shut down (collector stopping) - drop the scan.
                pass

    def _scan_whale_portfolio(self, address: str, discovery_coin: str, discovery_notional: float):
        """Fetch full clearinghouse state for the new whale."""
        try:
            time.sleep(0.5)  # slight stagger
            state = self.client.get_clearinghouse_state(address)
            if not state:
                return

            margin_summary = state.get("marginSummary", {})
            account_val = float(margin_summary.get("accountValue", 0.0))
            total_pos_val = float(margin_summary.get("totalNtlPos", 0.0))

            asset_positions = state.get("assetPositions", [])
            is_liquidator = any(
                pos.get("position", {}).get("liquidationPx") is None and
                abs(float(pos.get("position", {}).get("szi", 0.0))) > 0
                for pos in asset_positions
            )

            # Update DB with rich profile
            self.repo.upsert_whale_wallet(
                address=address,
                coin=discovery_coin,
                notional=discovery_notional,
                account_value=account_val,
                total_position_value=total_pos_val,
                is_liquidator=is_liquidator
            )
            logger.info(f"🐋 Whale Discovered: {address[:8]}... Account Value: ${account_val:,.2f}, Open Positions: ${total_pos_val:,.2f}")
        except Exception as e:
            logger.error(f"Error scanning portfolio for whale {address}: {e}")

    def shutdown(self, wait: bool = False):
        """Stop accepting new portfolio scans."""
        self._scan_pool.shutdown(wait=wait)
