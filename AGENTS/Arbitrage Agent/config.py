"""
Configuration Module for Base L2 DEX-to-DEX Atomic Arbitrage Agent
"""

import os

# --- NETWORK & RPC CONFIGURATION ---
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
CHAIN_ID = 8453  # Base Mainnet Chain ID

# --- CAPITAL & RISK MANAGEMENT CONFIGURATION ($3,000 Starting Principal) ---
CAPITAL_CONFIG = {
    "TOTAL_BANKROLL_USD": 3000.0,
    "WORKING_USDC": 2950.0,         # Capital deployed into paired DEX swaps
    "GAS_RESERVE_ETH": 0.015,       # ~$50 ETH on Base for tx fees and revert checks
    "MIN_PROFIT_USD": 6.0,          # Minimum net profit requirement per trade
    "MIN_SPREAD_PCT": 0.80,         # Minimum gross price spread percentage (0.80% to clear 0.60% swap fees)
    "CUMULATIVE_FEE_PCT": 0.60,     # Combined 2-leg protocol swap fee (0.3% * 2)
    "OFFRAMP_TRIGGER_USDC": 3273.0, # Milestone profit trigger (+10.95% net / +$323 profit harvest)
    "MAX_SLIPPAGE_PCT": 0.30,       # Maximum allowed slippage (reserved; not yet enforced — see README "Going Live")
    "MAX_CONSECUTIVE_REVERTS": 3,   # Circuit breaker threshold
    "MIN_GAS_RESERVE_ETH": 0.003,   # Floor below which the agent pauses instead of trading (~$10)
}

# --- DEX ROUTERS & PROTOCOL ADDRESSES ON BASE L2 ---
DEX_ADDRESSES = {
    "UNISWAP_V3_ROUTER": "0x2626664c2603336E57B271c5C0b26F421741e481",
    "UNISWAP_V3_QUOTER": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
    "AERODROME_ROUTER": "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43",
    "AERODROME_QUOTER": "0x7F268357A8c2552623316e2562D90e642bB538E5",
}

# --- VERIFIED TOKEN ADDRESSES ON BASE L2 ---
TOKEN_ADDRESSES = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006",
    "AERO": "0x940181a94A35A4569E4529A3CDfB74e38FD98631",
    "cbBTC": "0xcbB7C00001B6669d40f322A31e51D688D2c4161C",
    "wstETH": "0xc1C03083c070BE9fA643a68B4bC3FCEFEf68D843",
    "VIRTUAL": "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
    "BRETT": "0x532f27101965dd16442E59d40670FaF5eBB142E4",
    "DEGEN": "0x4ed4E862860bed51a9570b96d89af5e1b0efefed",
    "EURC": "0x60a3E35Cc1051386f1df21966144e6E87515a812",
    "WELL": "0xA88594D73d50864d4220F65D6b328a6f3765eE8f",
    "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
}

# --- TOP 10 TARGET ARBITRAGE PRODUCTS (TOKEN PAIRS) ---
TARGET_PRODUCTS = [
    {
        "symbol": "WETH/USDC",
        "base": "WETH",
        "quote": "USDC",
        "role": "Core Liquidity Anchor",
        "min_spread": 0.80,
    },
    {
        "symbol": "AERO/USDC",
        "base": "AERO",
        "quote": "USDC",
        "role": "Native Volatile Leader",
        "min_spread": 0.90,
    },
    {
        "symbol": "cbBTC/USDC",
        "base": "cbBTC",
        "quote": "USDC",
        "role": "Coinbase Bitcoin Spread",
        "min_spread": 0.80,
    },
    {
        "symbol": "wstETH/WETH",
        "base": "wstETH",
        "quote": "WETH",
        "role": "Liquid Staking Soft-Peg",
        "min_spread": 0.40,
    },
    {
        "symbol": "VIRTUAL/WETH",
        "base": "VIRTUAL",
        "quote": "WETH",
        "role": "Mid-Cap Ecosystem Leader",
        "min_spread": 1.00,
    },
    {
        "symbol": "BRETT/WETH",
        "base": "BRETT",
        "quote": "WETH",
        "role": "Base Meme High-Beta",
        "min_spread": 1.20,
    },
    {
        "symbol": "DEGEN/WETH",
        "base": "DEGEN",
        "quote": "WETH",
        "role": "Social Native Token",
        "min_spread": 1.20,
    },
    {
        "symbol": "EURC/USDC",
        "base": "EURC",
        "quote": "USDC",
        "role": "Forex Euro-Dollar Peg",
        "min_spread": 0.35,
    },
    {
        "symbol": "WELL/WETH",
        "base": "WELL",
        "quote": "WETH",
        "role": "Lending Protocol Token",
        "min_spread": 1.00,
    },
    {
        "symbol": "DAI/USDC",
        "base": "DAI",
        "quote": "USDC",
        "role": "Stablecoin Soft-Peg",
        "min_spread": 0.20,
    },
]
