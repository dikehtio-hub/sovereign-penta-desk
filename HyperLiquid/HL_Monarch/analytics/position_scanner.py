"""
High-Throughput Native Hyperliquid Wallet & Position Liquidation Scanner.
Self-hosted, free, and rate-limited scanner tracking positions and liquidation distances
across active trader addresses in data/hyperliquidusers.txt.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from config.settings import DATA_DIR, HL_SYSTEM_LIQUIDATOR_ADDRESSES
from api.rest_client import HyperliquidRestClient
from storage.repository import MarketRepository

USERS_FILE = DATA_DIR / "hyperliquidusers.txt"

class PositionScanner:
    def __init__(self, users_file: Path = USERS_FILE):
        self.users_file = users_file
        self.client = HyperliquidRestClient()
        self.repo = MarketRepository()
        self.addresses: List[str] = self._load_addresses()

    def _load_addresses(self) -> List[str]:
        if not self.users_file.exists():
            return []
        with open(self.users_file, "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip().startswith("0x")]

    def inspect_wallet(self, address: str) -> Optional[Dict[str, Any]]:
        """Deep dive inspect a single wallet's full clearinghouse state."""
        try:
            clean_addr = address.strip().lower()
            state = self.client.get_clearinghouse_state(clean_addr)
            if not state:
                return None

            margin = state.get("marginSummary", {})
            acc_value = float(margin.get("accountValue", 0.0))
            total_pos = float(margin.get("totalNtlPos", 0.0))
            margin_used = float(margin.get("totalMarginUsed", 0.0))
            withdrawable = float(state.get("withdrawable", 0.0))

            raw_positions = state.get("assetPositions", [])
            positions = []
            for item in raw_positions:
                pos = item.get("position", {})
                size = float(pos.get("szi", 0))
                if size == 0:
                    continue

                coin = pos.get("coin", "")
                entry_px = float(pos.get("entryPx", 0))
                val = abs(float(pos.get("positionValue", 0)))
                pnl = float(pos.get("unrealizedPnl", 0))
                lev = float(pos.get("leverage", {}).get("value", 1))
                liq_px = float(pos.get("liquidationPx") or 0.0)
                is_long = size > 0

                # Compute distance to liquidation
                dist_pct = 999.0
                if liq_px > 0 and entry_px > 0:
                    dist_pct = (abs(entry_px - liq_px) / entry_px) * 100.0

                positions.append({
                    "coin": coin,
                    "size": size,
                    "is_long": is_long,
                    "entry_price": entry_px,
                    "position_value": val,
                    "unrealized_pnl": pnl,
                    "leverage": lev,
                    "liquidation_price": liq_px,
                    "distance_pct": dist_pct
                })

            is_liquidator = clean_addr in HL_SYSTEM_LIQUIDATOR_ADDRESSES

            return {
                "address": clean_addr,
                "account_value": acc_value,
                "total_position_value": total_pos,
                "margin_used": margin_used,
                "withdrawable": withdrawable,
                "is_liquidator": is_liquidator,
                "positions": positions
            }
        except Exception:
            return None

    def scan_user_positions(self, address: str) -> List[Dict[str, Any]]:
        """Fetch active positions and liquidation prices for a user."""
        try:
            clean_addr = address.strip().lower()
            state = self.client.get_clearinghouse_state(clean_addr)
            if not state or "assetPositions" not in state:
                return []
            
            positions = []
            for item in state["assetPositions"]:
                pos = item.get("position", {})
                size = float(pos.get("szi", 0))
                if size == 0:
                    continue
                
                coin = pos.get("coin", "")
                entry_px = float(pos.get("entryPx", 0))
                val = abs(float(pos.get("positionValue", 0)))
                pnl = float(pos.get("unrealizedPnl", 0))
                lev = float(pos.get("leverage", {}).get("value", 1))
                liq_px = float(pos.get("liquidationPx") or 0.0)
                is_long = size > 0

                dist_pct = 999.0
                if liq_px > 0 and entry_px > 0:
                    dist_pct = (abs(entry_px - liq_px) / entry_px) * 100.0

                positions.append({
                    "address": clean_addr,
                    "coin": coin,
                    "size": size,
                    "is_long": is_long,
                    "entry_price": entry_px,
                    "position_value": val,
                    "unrealized_pnl": pnl,
                    "leverage": lev,
                    "liquidation_price": liq_px,
                    "distance_pct": dist_pct,
                    "is_liquidator": clean_addr in HL_SYSTEM_LIQUIDATOR_ADDRESSES
                })
            return positions
        except Exception:
            return []

    def scan_batch(
        self,
        addresses: List[str],
        min_value_usd: float = 50000.0,
        max_danger_dist_pct: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Scan a list of addresses and return whale or dangerously leveraged positions."""
        all_positions = []
        for addr in addresses:
            user_positions = self.scan_user_positions(addr)
            for p in user_positions:
                if p["position_value"] < min_value_usd:
                    continue
                if max_danger_dist_pct is not None and p["distance_pct"] > max_danger_dist_pct:
                    continue
                all_positions.append(p)
        return all_positions
