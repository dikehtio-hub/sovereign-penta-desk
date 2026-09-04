"""
Crypto Spot Trade Ingestor.
Handles spot buys, sells, DEX swaps, and CSV imports for spot crypto assets.
"""
import csv
from typing import List, Dict, Any, Optional
from pathlib import Path

class SpotIngestor:
    @staticmethod
    def create_trade(symbol: str, side: str, quantity: float, price: float, timestamp: str,
                     fee: float = 0.0, tx_hash: str = "",
                     strategy: Optional[str] = None) -> Dict[str, Any]:
        """`strategy` is stamped into `notes` for per-strategy exposure accounting."""
        from ..interfaces.monarch_hook import tag_strategy
        return tag_strategy({
            "source": "spot",
            "tx_hash": tx_hash or f"spot_{symbol}_{timestamp}_{side}",
            "timestamp": timestamp,
            "asset_class": "crypto_spot",
            "symbol": symbol.upper(),
            "side": side.upper(),
            "quantity": float(quantity),
            "price": float(price),
            "fee": float(fee),
            "total_value": float(quantity) * float(price),
            "notes": "Crypto spot trade"
        }, strategy)

    @staticmethod
    def load_from_csv(csv_path: Path) -> List[Dict[str, Any]]:
        """
        Loads spot trades from a generic CSV file:
        Columns expected: timestamp, symbol, side, quantity, price, fee (optional), tx_hash (optional)
        """
        trades = []
        if not csv_path.exists():
            return trades
            
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(SpotIngestor.create_trade(
                    symbol=row.get("symbol", "UNKNOWN"),
                    side=row.get("side", "BUY"),
                    quantity=float(row.get("quantity", 0.0)),
                    price=float(row.get("price", 0.0)),
                    timestamp=row.get("timestamp", ""),
                    fee=float(row.get("fee", 0.0)),
                    tx_hash=row.get("tx_hash", "")
                ))
        return trades
