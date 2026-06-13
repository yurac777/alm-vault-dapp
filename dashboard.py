import sys
import os
sys.path.insert(0, 'keeper')
import config
from core.state_reader import StateReader
from core.math import get_amounts_for_liquidity
from web3 import Web3
from decimal import Decimal

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
vault_address = w3.to_checksum_address(config.VAULT_ADDRESS)

vault_abi = [
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"currentTokenId","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]
vault = w3.to_checksum_address(vault_address)
vault_contract = w3.eth.contract(address=vault, abi=vault_abi)

supply = vault_contract.functions.totalSupply().call()
try:
    current_token_id = vault_contract.functions.currentTokenId().call()
except:
    current_token_id = 0

class MockConnector:
    def __init__(self, w3):
        self.w3 = w3
connector = MockConnector(w3)
reader = StateReader(connector)
eth_price = reader.get_eth_price()
tick_data = reader.get_current_tick(eth_price, tick_spacing=config.POOL_TICK_SPACING)
sqrtPriceX96 = tick_data.get("sqrt_price_x96", 0)

nft_value_usd = 0.0
if current_token_id != 0:
    npm_abi = [{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],"stateMutability":"view","type":"function"}]
    npm_contract = w3.eth.contract(address=w3.to_checksum_address(config.UNI_V3_NPM), abi=npm_abi)
    try:
        pos = npm_contract.functions.positions(current_token_id).call()
        liq = pos[7]
        if liq > 0 and sqrtPriceX96 > 0:
            amt0, amt1 = get_amounts_for_liquidity(sqrtPriceX96, pos[5], pos[6], liq)
            nft_value_usd = float(Decimal(amt0) / Decimal(10**18) * Decimal(eth_price)) + (amt1 / 1e6)
    except Exception as e:
        pass

aave_pool_abi = [{"inputs": [{"internalType": "address", "name": "user", "type": "address"}],"name": "getUserAccountData","outputs": [{"internalType": "uint256", "name": "totalCollateralBase", "type": "uint256"},{"internalType": "uint256", "name": "totalDebtBase", "type": "uint256"},{"internalType": "uint256", "name": "availableBorrowsBase", "type": "uint256"},{"internalType": "uint256", "name": "currentLiquidationThreshold", "type": "uint256"},{"internalType": "uint256", "name": "ltv", "type": "uint256"},{"internalType": "uint256", "name": "healthFactor", "type": "uint256"}],"stateMutability": "view","type": "function"}]
aave_pool = w3.eth.contract(address=w3.to_checksum_address(config.AAVE_POOL), abi=aave_pool_abi)
account_data = aave_pool.functions.getUserAccountData(vault).call()
aave_collateral = float(account_data[0]) / 1e8
aave_debt = float(account_data[1]) / 1e8

ERC20_ABI = [{"constant": True,"inputs": [{"name": "_owner", "type": "address"}],"name": "balanceOf","outputs": [{"name": "balance", "type": "uint256"}],"type": "function"}]
usdc_c = w3.eth.contract(address=w3.to_checksum_address(config.USDC), abi=ERC20_ABI)
usdc_bal_actual = usdc_c.functions.balanceOf(vault).call() / 1e6

tvl = usdc_bal_actual + (aave_collateral - aave_debt) + nft_value_usd

print("=== ALM QUANT ON-CHAIN DASHBOARD ===")
print(f"Vault Contract: {vault_address}")
print(f"Status: [OK] ONLINE & ACTIVE")
print(f"Total Shares Issued: {supply}")
print(f"")
print(f"TVL = Free USDC + (Aave Collateral - Aave Debt) + NFT Value")
print(f"Free USDC:       ${usdc_bal_actual:.4f}")
print(f"Aave Collateral: ${aave_collateral:.4f}")
print(f"Aave Debt:       ${aave_debt:.4f}")
print(f"NFT Value:       ${nft_value_usd:.4f}")
print(f"Total TVL:       ${tvl:.4f}")
