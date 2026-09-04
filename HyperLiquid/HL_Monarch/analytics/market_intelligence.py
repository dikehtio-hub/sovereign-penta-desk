"""
Market Intelligence & TradFi Cross-Asset Aggregator.
Computes Open Interest distribution, 24h volume rankings, funding rate APRs, and momentum.
"""
from typing import List, Dict, Any

class MarketIntelligence:
    @staticmethod
    def calculate_annualized_funding_apr(hourly_funding: float) -> float:
        """Convert hourly funding rate to annualized APR (%)."""
        return hourly_funding * 24 * 365 * 100.0

    @staticmethod
    def summarize_tradfi_metrics(snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate total TradFi OI, 24h volume, and category breakdowns."""
        total_tradfi_oi = 0.0
        total_tradfi_vol = 0.0
        
        category_oi = {
            "STOCKS": 0.0,
            "COMMODITIES": 0.0,
            "INDICES": 0.0,
            "FX": 0.0,
            "CRYPTO": 0.0,
            "OTHER": 0.0
        }

        top_oi_assets = []

        for s in snapshots:
            coin = s.get("coin", "")
            notional_oi = float(s.get("notional_oi") or 0.0)
            vol_24h = float(s.get("day_ntl_vlm") or 0.0)

            total_tradfi_oi += notional_oi
            total_tradfi_vol += vol_24h

            # Categorize
            if any(k in coin for k in ["TSLA", "NVDA", "AAPL", "META", "MSFT", "GOOGL", "AMZN", "AMD", "INTC", "PLTR", "COIN", "HOOD", "MSTR", "ORCL", "MU", "NFLX", "RIVN", "BABA"]):
                category_oi["STOCKS"] += notional_oi
            elif any(k in coin for k in ["GOLD", "SILVER", "COPPER", "CL", "NATGAS", "URANIUM", "OIL"]):
                category_oi["COMMODITIES"] += notional_oi
            elif any(k in coin for k in ["XYZ100", "SP500", "US500", "USTECH", "JP225"]):
                category_oi["INDICES"] += notional_oi
            elif any(k in coin for k in ["EUR", "JPY", "GBP", "DXY", "KRW"]):
                category_oi["FX"] += notional_oi
            elif not coin.startswith("xyz:") and not coin.startswith("km:") and not coin.startswith("flx:"):
                category_oi["CRYPTO"] += notional_oi
            else:
                category_oi["OTHER"] += notional_oi

            top_oi_assets.append({
                "coin": coin,
                "mark_px": float(s.get("mark_px") or 0.0),
                "notional_oi": notional_oi,
                "vol_24h": vol_24h,
                "funding_rate": float(s.get("funding_rate") or 0.0),
                "funding_apr": MarketIntelligence.calculate_annualized_funding_apr(float(s.get("funding_rate") or 0.0))
            })

        top_oi_assets.sort(key=lambda x: x["notional_oi"], reverse=True)

        return {
            "total_oi": total_tradfi_oi,
            "total_volume_24h": total_tradfi_vol,
            "category_oi": category_oi,
            "top_assets": top_oi_assets
        }
