"""
rescue_v3_step_by_step.py
Step 1: Simulate decreaseLiquidity to see what tokens come back from V3
Step 2: If WETH comes back, attempt full rebalance unwind  
Step 3: Direct NPM decreaseLiquidity + collect + Aave repay sequence

The problem is that ALMVaultV3 doesn't expose individual steps.
We'll use the old 11-param abi.decode but with non-zero amount0/1 for the 
new LP range, so the contract can repay debt and open a tiny new position,
OR we reduce amountWETHToRepay slightly to match what we'll actually have.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keeper import config
from web3 import Web3
from eth_abi import encode

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY
v3_addr = w3.to_checksum_address("0x87eE1eCa84E9308946eEcba998625272A6ED9a00")

chainlink_abi = [{"inputs":[],"name":"latestAnswer","outputs":[{"internalType":"int256","name":"","type":"int256"}],"stateMutability":"view","type":"function"}]
chainlink = w3.eth.contract(address=w3.to_checksum_address(config.CHAINLINK_ETH), abi=chainlink_abi)
eth_price = chainlink.functions.latestAnswer().call() / 1e8

aave_abi = [{"inputs":[{"internalType":"address","name":"user","type":"address"}],"name":"getUserAccountData","outputs":[{"internalType":"uint256","name":"totalCollateralBase","type":"uint256"},{"internalType":"uint256","name":"totalDebtBase","type":"uint256"},{"internalType":"uint256","name":"availableBorrowsBase","type":"uint256"},{"internalType":"uint256","name":"currentLiquidationThreshold","type":"uint256"},{"internalType":"uint256","name":"ltv","type":"uint256"},{"internalType":"uint256","name":"healthFactor","type":"uint256"}],"stateMutability":"view","type":"function"}]
aave = w3.eth.contract(address=w3.to_checksum_address(config.AAVE_POOL), abi=aave_abi)

npm_abi = [
    {"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"amount0Min","type":"uint256"},{"internalType":"uint256","name":"amount1Min","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"internalType":"struct INonfungiblePositionManager.DecreaseLiquidityParams","name":"params","type":"tuple"}],"name":"decreaseLiquidity","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},
    {"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint128","name":"amount0Max","type":"uint128"},{"internalType":"uint128","name":"amount1Max","type":"uint128"}],"internalType":"struct INonfungiblePositionManager.CollectParams","name":"params","type":"tuple"}],"name":"collect","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],"stateMutability":"view","type":"function"},
]
npm = w3.eth.contract(address=w3.to_checksum_address(config.UNI_V3_NPM), abi=npm_abi)

vault_abi = [
    {"inputs":[],"name":"currentTokenId","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"currentLiquidity","outputs":[{"internalType":"uint128","name":"","type":"uint128"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"bytes","name":"data","type":"bytes"}],"name":"rebalance","outputs":[],"stateMutability":"nonpayable","type":"function"},
]
v3c = w3.eth.contract(address=v3_addr, abi=vault_abi)

token_id = v3c.functions.currentTokenId().call()
liquidity = v3c.functions.currentLiquidity().call()
print(f"V3 tokenId: {token_id}, liquidity: {liquidity}")

# Simulate what decreaseLiquidity returns
sim_result = npm.functions.decreaseLiquidity((
    token_id, liquidity, 0, 0, w3.eth.get_block('latest')['timestamp'] + 60
)).call({'from': v3_addr})
weth_from_lp = sim_result[0]
usdc_from_lp = sim_result[1]
print(f"Simulated LP close: WETH={weth_from_lp/1e18:.8f}, USDC={usdc_from_lp/1e6:.6f}")

# Aave state
v3_aave = aave.functions.getUserAccountData(v3_addr).call()
weth_debt_usd = v3_aave[1] / 1e8
coll_usd = v3_aave[0] / 1e8
weth_debt_wei = int(weth_debt_usd / eth_price * 1e18)
coll_usdc_wei = int(coll_usd * 1e6)

print(f"WETH from LP: {weth_from_lp/1e18:.8f}")
print(f"WETH debt:    {weth_debt_wei/1e18:.8f}")
print(f"USDC from LP: {usdc_from_lp/1e6:.6f}")
print(f"Aave collateral: {coll_usdc_wei/1e6:.4f}")

# Key question: can we repay full debt with LP WETH?
if weth_from_lp >= weth_debt_wei:
    repay_amount = weth_debt_wei
    print("OK: LP provides enough WETH to repay full debt.")
else:
    repay_amount = weth_from_lp
    print(f"WARNING: LP only gives {weth_from_lp/1e18:.8f} WETH, debt is {weth_debt_wei/1e18:.8f}")
    print("We can only do partial repay.")

# Try a partial repay if needed - cap at 99% of what LP gives
repay_amount_safe = int(repay_amount * 0.995)
withdraw_safe = int(coll_usdc_wei * 0.99)

print(f"Using safe repay: {repay_amount_safe/1e18:.8f} WETH, withdraw: {withdraw_safe/1e6:.4f} USDC")

# Build 11-param V3 payload
types_v3 = ["bool","int256","uint256","uint256","int24","int24","uint256","uint256","uint24","uint256","uint256"]
values_v3 = [
    True,            # isRebalance
    0,               # aaveDebtAdjustment
    0,               # amountUSDC
    0,               # amountWETHToBorrow
    -202300,         # newTickLower
    -201500,         # newTickUpper
    0,               # amount0Desired = 0 => no LP mint
    0,               # amount1Desired = 0
    500,             # poolFee
    repay_amount_safe,
    withdraw_safe,
]
payload = "0x" + encode(types_v3, values_v3).hex()
payload_bytes = w3.to_bytes(hexstr=payload)

nonce = w3.eth.get_transaction_count(wallet, "pending")
tx = v3c.functions.rebalance(payload_bytes).build_transaction({
    "from": wallet, "nonce": nonce,
    "gasPrice": w3.eth.gas_price, "gas": 2_000_000, "chainId": 8453
})

print("Simulating...")
try:
    w3.eth.call(tx)
    print("Simulation PASSED!")
except Exception as e:
    print(f"Simulation failed: {e}")
    sys.exit(1)

signed = w3.eth.account.sign_transaction(tx, pk)
tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
print(f"Rescue Tx: https://basescan.org/tx/{tx_hash.hex()}")
r = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
print("Status:", "OK" if r.status == 1 else "REVERTED")
