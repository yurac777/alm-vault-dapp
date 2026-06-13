"""
config.py — Central configuration for ALM Vault Keeper.
All on-chain addresses and environment-driven constants live here.
"""
import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# ── Environment ─────────────────────────────────────────────────────────────
RPC_URL       = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY   = os.getenv("PRIVATE_KEY", "")
WALLET        = os.getenv("WALLET_ADDRESS", "")
VAULT_ADDRESS = os.getenv("VAULT_ADDRESS", "")

# ── On-Chain Addresses (Base Mainnet) ─────────────────────────────────────
USDC          = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH          = "0x4200000000000000000000000000000000000006"
AAVE_POOL     = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
CHAINLINK_ETH = "0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70"  # ETH/USD feed
UNI_V3_NPM   = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"   # NonfungiblePositionManager
UNI_V3_POOL  = "0xd0b53D9277642d899DF5C87A3966A349A798F224"   # WETH/USDC 0.05% pool
L1_GAS_ORACLE = "0x420000000000000000000000000000000000000F"

# ── Strategy Constants ─────────────────────────────────────────────────────
POOL_FEE             = 500     # 0.05 % tier
POOL_TICK_SPACING    = 10
TARGET_HEALTH_FACTOR = 1.6     # Aave leverage ratio (supply / borrow)
REBALANCE_SLEEP_SEC  = 900     # 15-minute keeper interval
MAX_RBF_RETRIES      = 3       # Replace-by-fee attempts
CHAIN_ID             = 8453    # Base Mainnet
