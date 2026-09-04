"""
Options Ingestor.
Tracks Crypto (Deribit/Aevo/Lyra) and TradFi options lifecycles:
- Buying Calls/Puts (Premiums paid)
- Selling to close
- Expiring worthless ($0 capital loss or short premium harvest)
- Selling to open / buying to close
"""
import csv
from typing import List, Dict, Any
from pathlib import Path

class OptionsIngestor:
    @staticmethod
    def create_long_option_buy(symbol: str, quantity: float, premium: float, timestamp: str, fee: float = 0.0, tx_hash: str = "") -> Dict[str, Any]:
        """Buy a Call or Put option."""
        return {
            "source": "options",
            "tx_hash": tx_hash or f"opt_buy_{symbol}_{timestamp}",
            "timestamp": timestamp,
            "asset_class": "option",
            "symbol": symbol.upper(),
            "side": "OPTION_BUY",
            "quantity": float(quantity),
            "price": float(premium),
            "fee": float(fee),
            "total_value": float(quantity) * float(premium),
            "notes": f"Long option purchase at premium ${premium}"
        }

    @staticmethod
    def create_long_option_sell(symbol: str, quantity: float, premium: float, timestamp: str, fee: float = 0.0, tx_hash: str = "") -> Dict[str, Any]:
        """Sell to close a Call or Put option before expiration."""
        return {
            "source": "options",
            "tx_hash": tx_hash or f"opt_sell_{symbol}_{timestamp}",
            "timestamp": timestamp,
            "asset_class": "option",
            "symbol": symbol.upper(),
            "side": "OPTION_SELL",
            "quantity": float(quantity),
            "price": float(premium),
            "fee": float(fee),
            "total_value": float(quantity) * float(premium),
            "notes": f"Close long option at premium ${premium}"
        }

    @staticmethod
    def create_option_expiration(symbol: str, quantity: float, timestamp: str, tx_hash: str = "") -> Dict[str, Any]:
        """
        Record option expiring worthless (100% loss of initial premium paid).
        Realizes a full loss and immediately lowers tax reserve.
        """
        return {
            "source": "options",
            "tx_hash": tx_hash or f"opt_exp_{symbol}_{timestamp}",
            "timestamp": timestamp,
            "asset_class": "option",
            "symbol": symbol.upper(),
            "side": "OPTION_EXPIRE",
            "quantity": float(quantity),
            "price": 0.0,  # Expired to zero
            "fee": 0.0,
            "total_value": 0.0,
            "notes": "Option expired worthless (realized capital loss)"
        }

    @staticmethod
    def load_from_csv(csv_path: Path) -> List[Dict[str, Any]]:
        trades = []
        if not csv_path.exists():
            return trades
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                side = row.get("side", "OPTION_BUY").upper()
                symbol = row.get("symbol", "").upper()
                qty = float(row.get("quantity", 0.0))
                premium = float(row.get("price", row.get("premium", 0.0)))
                ts = row.get("timestamp", "")
                fee = float(row.get("fee", 0.0))
                
                if "EXPIRE" in side:
                    trades.append(OptionsIngestor.create_option_expiration(symbol, qty, ts))
                elif "SELL" in side:
                    trades.append(OptionsIngestor.create_long_option_sell(symbol, qty, premium, ts, fee))
                else:
                    trades.append(OptionsIngestor.create_long_option_buy(symbol, qty, premium, ts, fee))
        return trades
