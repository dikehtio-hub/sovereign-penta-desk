# 👑 HL_Monarch: Native Hyperliquid & HIP3 TradFi Market Intelligence Suite

**HL_Monarch** is a 100% free, self-hosted, native market intelligence and liquidation tracking system connecting directly to Hyperliquid's public infrastructure (REST & WebSockets). It requires **zero paid API keys, zero third-party proxies, and zero monthly fees**.

---

## 🌟 Key Features

- **Full HIP3 TradFi Coverage ($1.11B+ Open Interest)**:
  - **Stocks**: TSLA, NVDA, AAPL, META, MSFT, GOOGL, AMZN, AMD, INTC, PLTR, COIN, HOOD, MSTR, ORCL, MU, NFLX, RIVN, BABA
  - **Commodities**: GOLD, SILVER, COPPER, CL (Crude Oil), NATGAS, URANIUM
  - **Indices**: XYZ100 (Nasdaq proxy), SP500
  - **FX**: EUR, JPY, GBP, DXY
  - **Crypto Benchmarks**: BTC, ETH, SOL, HYPE, SUI, DOGE
- **Real-Time Liquidation & Whale Flow Monitoring**:
  - Live trade stream analyzer flagging sweeps, large orders, and protocol liquidation events.
- **Liquidation Heatmap & Cluster Estimation**:
  - Dynamic calculations for theoretical liquidation bands (Long & Short clusters across 5x, 10x, 20x, 25x, 30x, 50x leverage tiers).
- **High-Performance SQLite WAL Persistence**:
  - `hyperliquid_data.db` storing tick-level trade history, order book snapshots, and market context history for offline backtesting and analysis.
- **Rich Windows-Compatible Terminal Dashboard**:
  - Auto-refreshing UTF-8 terminal interface with live market metrics, funding APRs, and order book depth.
- **1-Click Windows Launchers**:
  - `launch_dashboard.bat` (Terminal UI)
  - `launch_collector.bat` (Background Ingestion Engine)

---

## 🚀 Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Run Live Terminal Dashboard
```bash
# Via 1-click batch launcher:
launch_dashboard.bat

# Or directly in Python:
python main.py dashboard
```

### 3. Run Continuous Background Ingestion Daemon
```bash
# Via 1-click batch launcher:
launch_collector.bat

# Or directly in Python:
python main.py collector
```

### 4. Instant CLI Market Summary
```bash
python main.py summary --dex xyz
```

---

## 🏗 Directory Architecture

```
HL_Monarch/
├── config/
│   ├── __init__.py
│   └── settings.py               # Universe definitions, endpoints, rate limits
├── api/
│   ├── __init__.py
│   ├── rest_client.py            # Token bucket rate-limited REST client
│   └── ws_client.py              # Async WebSocket client with auto-reconnect
├── storage/
│   ├── __init__.py
│   ├── db.py                     # SQLite WAL connection manager
│   └── repository.py             # Data access repository
├── analytics/
│   ├── __init__.py
│   ├── liquidation_engine.py     # Real-time liquidation & cluster algorithm
│   └── market_intelligence.py    # TradFi OI & funding APR analytics
├── collectors/
│   ├── __init__.py
│   └── market_collector.py       # Async background daemon
├── ui/
│   ├── __init__.py
│   ├── components.py             # Rich UI widgets
│   └── terminal_dashboard.py     # Live multi-panel terminal dashboard
├── tests/
│   ├── test_db.py                # Database unit tests
│   ├── test_analytics.py         # Analytics unit tests
│   ├── test_rest_api.py          # Live REST API tests
│   └── test_ws_api.py            # Live WebSocket tests
├── launch_dashboard.bat          # 1-Click Dashboard launcher
├── launch_collector.bat          # 1-Click Ingestion launcher
├── requirements.txt              # Dependencies (rich, websockets)
├── main.py                       # CLI Entrypoint
└── README.md
```
