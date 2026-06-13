import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import RPC_URL, WALLET, PRIVATE_KEY
from web3 import Web3
from eth_abi import encode

w3 = Web3(Web3.HTTPProvider(RPC_URL))
wallet = w3.to_checksum_address(WALLET)
pk = PRIVATE_KEY

# Contracts
usdc_addr = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
weth_addr = "0x4200000000000000000000000000000000000006"
aave_pool_addr = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
npm_addr = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"
v5_addr = "0x6B2Ec85Fb2c4CE051B71804e20aD8F2c03DADcB4"
v6_addr = "0x75fd978542e082d455879A9301567438e71db9ec"

usdc = w3.eth.contract(address=usdc_addr, abi=[
    {"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}
])

vault_abi = [
    {"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalAssets","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"shares","type":"uint256"},{"internalType":"address","name":"receiver","type":"address"},{"internalType":"address","name":"owner","type":"address"}],"name":"redeem","outputs":[{"internalType":"uint256","name":"assets","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"assets","type":"uint256"},{"internalType":"address","name":"receiver","type":"address"}],"name":"deposit","outputs":[{"internalType":"uint256","name":"shares","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"bytes","name":"data","type":"bytes"}],"name":"rebalance","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[],"name":"currentTokenId","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]

v5 = w3.eth.contract(address=v5_addr, abi=vault_abi)
v6 = w3.eth.contract(address=v6_addr, abi=vault_abi)

ausdc_addr = "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB"
ausdc = w3.eth.contract(address=ausdc_addr, abi=[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}])

def send(tx, label):
    signed = w3.eth.account.sign_transaction(tx, pk)
    h = w3.eth.send_raw_transaction(signed.rawTransaction)
    r = w3.eth.wait_for_transaction_receipt(h, timeout=120)
    print(f"[{label}] {h.hex()[:20]}... -> {'OK' if r.status == 1 else 'REVERTED'}")
    return r.status == 1

print("=== UNWIND ALMVAULT V5 (TWO-STEP) ===")

# Bootstrap and Step 1 already done!
# Resume at Step 2

# STEP 2: Withdraw Aave Collateral
v5_ausdc = ausdc.functions.balanceOf(v5_addr).call()
print(f"V5 aUSDC (Collateral) left: {v5_ausdc}")
if v5_ausdc > 0:
    print("Step 2: Withdraw USDC from Aave...")
    payload2 = encode(
        ['bool', 'int256', 'uint256', 'uint256', 'int24', 'int24', 'uint256', 'uint256', 'uint24', 'uint256', 'uint256', 'uint256', 'uint256'],
        [False, 0, 0, 0, 0, 0, 0, 0, 500, 0, 2**256 - 1, 0, 0]
    )
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    try:
        send(v5.functions.rebalance(payload2).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 1500000, "chainId": 8453}), "V5 Step 2: Withdraw Aave")
        time.sleep(2)
    except Exception as e:
        print(f"Step 2 failed: {e}")

# Redeem from V5
wallet_v5_shares = v5.functions.balanceOf(wallet).call()
print(f"Wallet V5 shares now: {wallet_v5_shares}")
if wallet_v5_shares > 0:
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    send(v5.functions.redeem(wallet_v5_shares, wallet, wallet).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 500000, "chainId": 8453}), "Redeem all V5")
    time.sleep(2)

# Final Deposit to V6
wallet_usdc_final = usdc.functions.balanceOf(wallet).call()
print(f"Rescued USDC: {wallet_usdc_final/1e6:.6f}")

if wallet_usdc_final > 0:
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    send(usdc.functions.approve(v6_addr, wallet_usdc_final).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 100000, "chainId": 8453}), "Approve V6")
    time.sleep(2)
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    send(v6.functions.deposit(wallet_usdc_final, wallet).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 500000, "chainId": 8453}), "Deposit everything to V6")
    print("MIGRATION TO V6 COMPLETE!")
