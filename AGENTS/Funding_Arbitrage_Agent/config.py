"""
Configuration module for Autonomous Funding Arbitrage Trading Agent.
Defines parameters for Binance, Hyperliquid, Aster exchanges, funding thresholds, risk sentinels, and key management.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict
from dotenv import load_dotenv

# Load .env environment variables if available
load_dotenv()

@dataclass
class Config:
    # 10 Target Trading Pairs (Exact 1:1 match with DEX Arbitrage Agent)
    TARGET_PAIRS: List[Dict[str, str]] = field(default_factory=lambda: [
        {"pair": "WETH/USDC",    "symbol": "ETH",     "role": "Core Liquidity Anchor"},
        {"pair": "AERO/USDC",    "symbol": "AERO",    "role": "Native Volatile Leader"},
        {"pair": "cbBTC/USDC",   "symbol": "BTC",     "role": "Coinbase Bitcoin Spread"},
        {"pair": "wstETH/WETH",  "symbol": "wstETH",  "role": "Liquid Staking Soft-Peg"},
        {"pair": "VIRTUAL/WETH", "symbol": "VIRTUAL", "role": "Mid-Cap Ecosystem Leader"},
        {"pair": "BRETT/WETH",   "symbol": "BRETT",   "role": "Base Meme High-Beta"},
        {"pair": "DEGEN/WETH",   "symbol": "DEGEN",   "role": "Social Native Token"},
        {"pair": "EURC/USDC",    "symbol": "EURC",    "role": "Forex Euro-Dollar Peg"},
        {"pair": "WELL/WETH",    "symbol": "WELL",    "role": "Lending Protocol Token"},
        {"pair": "DAI/USDC",     "symbol": "DAI",     "role": "Stablecoin Soft-Peg"},
    ])

    SYMBOLS: List[str] = field(default_factory=lambda: [
        'ETH', 'AERO', 'BTC', 'wstETH', 'VIRTUAL', 'BRETT', 'DEGEN', 'EURC', 'WELL', 'DAI'
    ])
    
    # Supported Exchanges
    EXCHANGES: List[str] = field(default_factory=lambda: ['binance', 'hyperliquid', 'aster'])
    
    # Funding Thresholds
    # Minimum Annualized Rate (APR %) to trigger Single-Exchange Cash-and-Carry (Long Spot / Short Perp)
    MIN_SINGLE_EXCHANGE_APR: float = 20.0  
    
    # Minimum Annualized Spread (APR % diff) to trigger Cross-Exchange Perp Arbitrage
    MIN_CROSS_EXCHANGE_SPREAD_APR: float = 12.0  
    
    # Funding Compression Exit Threshold (APR % drop where arbitrage position unwinds)
    EXIT_FUNDING_SPREAD_APR: float = 3.0  
    
    # Strategy Selection Toggles ('all', 'cash-carry', 'cross-funding')
    ENABLED_STRATEGIES: List[str] = field(default_factory=lambda: ['all'])
    
    # Risk & Position Sizing
    DEFAULT_LEVERAGE: int = 3
    MAX_LEVERAGE: int = 10
    MAX_EQUITY_PERCENT: float = 95.0  # % of tradeable balance allocated to margin
    SLIPPAGE_TOLERANCE_PCT: float = 0.2  # Max acceptable price slippage %
    
    # Exit & Trailing Profit Settings
    REGULAR_TAKE_PROFIT_PCT: float = 25.0    # Leveraged % return target
    REGULAR_STOP_LOSS_PCT: float = -5.0      # Leveraged % stop loss
    EMERGENCY_STOP_LOSS_PCT: float = -7.5    # Emergency Taker stop loss
    TRAILING_TP_ACTIVATION_PCT: float = 8.0  # Start trailing after this leveraged profit %
    TRAILING_TP_CALLBACK_PCT: float = 1.0    # Exit on this pullback % from peak
    
    # Timing & Intervals
    MONITORING_INTERVAL_SEC: float = 3.0     # Refresh interval for live dashboard & risk sentinel
    RECONNECT_DELAY_SEC: float = 5.0         # WebSocket reconnect delay
    ORDER_FILL_TIMEOUT_SEC: float = 10.0     # Time to wait for limit maker order fill
    
    # Credentials (from environment or fallback)
    HYPERLIQUID_SECRET_KEY: str = field(default_factory=lambda: os.getenv('HYPERLIQUID_SECRET_KEY', ''))
    ASTER_API_KEY: str = field(default_factory=lambda: os.getenv('ASTER_API_KEY', ''))
    ASTER_API_SECRET: str = field(default_factory=lambda: os.getenv('ASTER_API_SECRET', ''))
    BINANCE_API_KEY: str = field(default_factory=lambda: os.getenv('BINANCE_API_KEY', ''))
    BINANCE_API_SECRET: str = field(default_factory=lambda: os.getenv('BINANCE_API_SECRET', ''))

    def validate_keys(self, mode: str) -> Dict[str, bool]:
        """Returns status of configured exchange keys."""
        if mode == 'dry-run':
            return {'hyperliquid': True, 'aster': True, 'binance': True}
        return {
            'hyperliquid': bool(self.HYPERLIQUID_SECRET_KEY),
            'aster': bool(self.ASTER_API_KEY and self.ASTER_API_SECRET),
            'binance': bool(self.BINANCE_API_KEY and self.BINANCE_API_SECRET)
        }
