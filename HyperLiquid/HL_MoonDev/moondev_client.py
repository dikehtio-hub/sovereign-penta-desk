"""
MoonDev API Python SDK Reference Client.
Reference implementation connecting to https://api.moondev.com (Requires MoonDev API Key).
"""
import os
import requests
from typing import Dict, Any, List, Optional

class MoonDevClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.moondev.com"):
        self.api_key = api_key or os.getenv("MOONDEV_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # --- Market Data ---
    def get_prices(self) -> Dict[str, Any]:
        """Get all prices, funding rates, and OI."""
        return self._get("/api/prices")

    def get_price(self, coin: str) -> Dict[str, Any]:
        """Get single coin price and spread."""
        return self._get(f"/api/price/{coin.upper()}")

    def get_orderbook(self, coin: str) -> Dict[str, Any]:
        """Get L2 orderbook snapshot."""
        return self._get(f"/api/orderbook/{coin.upper()}")

    def get_candles(self, coin: str, interval: str = "1h", limit: int = 100) -> Dict[str, Any]:
        """Get OHLCV candles."""
        return self._get(f"/api/candles/{coin.upper()}", params={"interval": interval, "limit": limit})

    # --- Account & Fills ---
    def get_account(self, address: str) -> Dict[str, Any]:
        """Get full clearinghouse state."""
        return self._get(f"/api/account/{address}")

    def get_fills(self, address: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get user fills."""
        return self._get(f"/api/fills/{address}", params={"limit": limit})

    # --- HIP3 TradFi Endpoints ---
    def get_hip3_prices(self) -> Dict[str, Any]:
        """Get HIP3 TradFi prices (stocks, commodities, indices, FX)."""
        return self._get("/api/hip3/prices")

    def get_hip3_liquidations(self, asset: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get real-time TradFi liquidations."""
        endpoint = f"/api/hip3/liquidations/{asset.upper()}" if asset else "/api/hip3/liquidations"
        return self._get(endpoint)

    def get_hip3_ticks(self, asset: str) -> List[Dict[str, Any]]:
        """Get tick data for a TradFi asset."""
        return self._get(f"/api/hip3/ticks/{asset.lower()}.json")

    # --- Crypto Liquidations ---
    def get_liquidations(self) -> List[Dict[str, Any]]:
        """Get live crypto liquidation events."""
        return self._get("/api/liquidations")
