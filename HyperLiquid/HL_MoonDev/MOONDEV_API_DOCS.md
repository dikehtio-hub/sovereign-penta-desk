# MoonDev API Documentation (Reference Benchmark)

**Source**: `https://moondev.com/docs`  
**Base URL**: `https://api.moondev.com`  
**Authentication**: `X-API-Key: YOUR_API_KEY` or `?api_key=YOUR_API_KEY`

---

## 📌 Overview

MoonDev provides an aggregation layer and proxy over Hyperliquid and Polymarket data feeds. This folder (`HL_MoonDev`) serves as our **fixed benchmark and reference implementation**.

---

## 🔗 Endpoint Categories & Specifications

### 1. Market Data Endpoints
| Endpoint | Description | Native Hyperliquid Equivalent |
|---|---|---|
| `GET /api/prices` | All prices, funding rates, and open interest | `POST /info` with `{"type": "metaAndAssetCtxs"}` |
| `GET /api/price/{coin}` | Single coin price, spread, best bid/ask | `POST /info` with `{"type": "l2Book", "coin": coin}` |
| `GET /api/orderbook/{coin}` | L2 orderbook snapshot (~20 levels) | `POST /info` with `{"type": "l2Book", "coin": coin}` |
| `GET /api/candles/{coin}?interval=1h` | OHLCV historical candles | `POST /info` with `{"type": "candleSnapshot", ...}` |
| `GET /api/account/{address}` | Account state, positions, margin summary | `POST /info` with `{"type": "clearinghouseState", "user": address}` |
| `GET /api/fills/{address}` | Trade fills and execution history | `POST /info` with `{"type": "userFills", "user": address}` |

### 2. HIP3 TradFi Market & Liquidation Endpoints
| Endpoint | Description | Native Hyperliquid Equivalent |
|---|---|---|
| `GET /api/hip3/prices` | Real-time prices, OI, and funding for Stocks, Commodities, Indices, FX | `POST /info` with `{"type": "metaAndAssetCtxs", "dex": "xyz"}` |
| `GET /api/hip3/liquidations` | Real-time liquidation feed for TradFi perps | Native trade stream / block fills on DEX `xyz` |
| `GET /api/hip3/ticks/{asset}` | High-frequency tick data for TradFi tickers | WebSocket `trades` channel for `xyz:{asset}` |

### 3. Hyperliquid Crypto Liquidations
| Endpoint | Description | Native Hyperliquid Equivalent |
|---|---|---|
| `GET /api/liquidations` | Aggregated liquidation stream across crypto markets | Native WebSocket `trades` and `explorerBlock` streams |
| `GET /api/liquidations/recent` | Recent liquidation fills | Native `trades` feed filtered by liquidation flags |

---

## 💻 Sample Code (MoonDev API)

```python
import requests

API_KEY = "YOUR_MOONDEV_API_KEY"
BASE_URL = "https://api.moondev.com"
headers = {"X-API-Key": API_KEY}

# Fetch HIP3 TradFi Prices
hip3_prices = requests.get(f"{BASE_URL}/api/hip3/prices", headers=headers).json()
print("TradFi Prices:", hip3_prices)

# Fetch HIP3 Liquidations
hip3_liqs = requests.get(f"{BASE_URL}/api/hip3/liquidations", headers=headers).json()
print("TradFi Liquidations:", hip3_liqs)
```
