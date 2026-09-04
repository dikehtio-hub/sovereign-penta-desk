# Autonomous Funding Rate Arbitrage Agent

An automated, real-time delta-neutral trading agent designed to monitor, scan, and execute funding rate arbitrage across crypto exchanges (Binance, Hyperliquid, Aster).

---

## 📌 Project Location & Setup

**Project Folder:** [`C:\Users\ixis1\.agents\arbitrage_agent`](file:///C:/Users/ixis1/.agents/arbitrage_agent)

### Quick Start Commands

```powershell
# 1. Open Terminal and navigate to the project
cd C:\Users\ixis1\.agents\arbitrage_agent

# 2. Activate pre-configured Virtual Environment
.\.venv\Scripts\Activate.ps1

# 3. Run Agent Dashboard (Paper Trading / Dry-Run Mode)
python agent.py --mode dry-run
```

---

## 💡 Strategy Descriptions

The agent supports **two core delta-neutral strategies**:

### 1. Single-Exchange Cash & Carry (`cash-carry`)
* **Mechanism**: Long Spot asset + Short Perpetual Futures on the same exchange when the perpetual funding rate is high positive.
* **Yield Source**: Accrues funding payouts paid by perpetual long holders every 8 hours.
* **Risk Profile**: Delta-neutral (spot appreciation/depreciation offsets perp price movement). Zero cross-exchange transfer risk.

### 2. Cross-Exchange Funding Arbitrage (`cross-funding`)
* **Mechanism**: Long Perp on Exchange A (low/negative rate) + Short Perp on Exchange B (high positive rate).
* **Yield Source**: Captures the net funding APR spread differential between two exchanges.
* **Risk Profile**: Delta-neutral. Requires margin balance on both exchanges.

---

## ⚙️ How to Select Which Strategy to Run

You do **not** have to run all strategies at once. You can choose which one to execute via terminal CLI flags or configuration settings.

### Option A: Command Line Selection (CLI Flags)

```powershell
# Run Cash & Carry Strategy Only
python agent.py --strategy cash-carry --auto-trade --mode dry-run

# Run Cross-Exchange Arbitrage Strategy Only
python agent.py --strategy cross-funding --auto-trade --mode dry-run

# Run All Strategies (Default)
python agent.py --strategy all --auto-trade --mode dry-run
```

### Option B: Centralized Configuration ([`config.py`](file:///C:/Users/ixis1/.agents/arbitrage_agent/config.py))

Open `config.py` and modify the `ENABLED_STRATEGIES` list:

```python
# Select which strategies are active ('all', 'cash-carry', 'cross-funding')
ENABLED_STRATEGIES = ['cash-carry']
```

---

## 📊 Capital Requirements & Risk Controls

All risk parameters and threshold triggers are centralized in [`config.py`](file:///C:/Users/ixis1/.agents/arbitrage_agent/config.py):

| Parameter | Recommended Starting Value | Max / Aggressive Limit | Description |
| :--- | :--- | :--- | :--- |
| `DEFAULT_LEVERAGE` | `3` | `10` | Default leverage multiplier per order |
| `MAX_EQUITY_PERCENT` | `95.0%` | `95.0%` | Max % of available equity allocated to margin |
| `MIN_SINGLE_EXCHANGE_APR` | `20.0%` | `10.0%` | Min annualized funding APR to trigger Cash & Carry |
| `MIN_CROSS_EXCHANGE_SPREAD_APR` | `12.0%` | `5.0%` | Min APR spread diff to trigger Cross-Exchange Arb |
| `REGULAR_TAKE_PROFIT_PCT` | `25.0%` | `50.0%` | Target leveraged profit target % |
| `REGULAR_STOP_LOSS_PCT` | `-5.0%` | `-10.0%` | Hard stop loss limit % |
| `EMERGENCY_STOP_LOSS_PCT` | `-7.5%` | `-15.0%` | Emergency market exit trigger |

---

## 📁 File Structure & Architecture

```
C:\Users\ixis1\.agents\arbitrage_agent/
├── README.md               # Detailed user guide & documentation
├── config.py               # Centralized parameters, APR triggers, leverage caps & API keys
├── market_data.py          # Real-time WebSocket & REST streams for Binance, Hyperliquid, Aster
├── arbitrage_engine.py     # Opportunity scanner & position size calculation logic
├── execution_manager.py    # Order routing, dry-run paper trading & active position tracker
├── risk_sentinel.py        # Automated trailing profit lock, stop losses & emergency exits
├── agent.py                # Main CLI live terminal dashboard & orchestrator
├── test_arbitrage_agent.py # Comprehensive unit test suite
├── .env.example            # Template file for live exchange credentials
└── requirements.txt        # Python package dependencies
```

---

## 🧪 Testing & Verification

Run the automated test suite to ensure system health and logic integrity:

```powershell
python -m unittest test_arbitrage_agent.py
```
