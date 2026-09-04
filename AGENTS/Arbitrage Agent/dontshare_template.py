"""
TEMPLATE FOR SECURE KEYS AND RPC CREDENTIALS
=============================================
Instructions:
1. Copy this file and rename it to `dontshare.py` (which is gitignored).
2. Insert your private RPC provider key and dedicated programmatic hot wallet private key.
3. NEVER commit your private key or share it with anyone.
"""

# --- BASE L2 RPC URL ---
# Get a free key from Alchemy (https://alchemy.com), QuickNode, or Infura
BASE_RPC_URL = "https://base-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_API_KEY"

# --- PROGRAMMATIC HOT WALLET PRIVATE KEY ---
# Generate a dedicated burner keypair for your bot (eth_account.Account.create())
# Fund it with $2,950 USDC + $50 ETH on Base
HOT_WALLET_PRIVATE_KEY = "0xYOUR_DEDICATED_BOT_HOT_WALLET_PRIVATE_KEY"

# --- DEPLOYED ATOMIC EXECUTOR CONTRACT ADDRESS ON BASE ---
ATOMIC_EXECUTOR_ADDRESS = "0xYOUR_DEPLOYED_ATOMIC_EXECUTOR_CONTRACT_ADDRESS"
