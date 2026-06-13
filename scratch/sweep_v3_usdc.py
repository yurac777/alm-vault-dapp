import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keeper import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY
v3_addr = w3.to_checksum_address("0x87eE1eCa84E9308946eEcba998625272A6ED9a00")
v5_addr = w3.to_checksum_address(config.VAULT_ADDRESS)
usdc_addr = w3.to_checksum_address(config.USDC)

usdc_abi = [
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
]
vault_abi = [
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalAssets","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"shares","type":"uint256"},{"name":"receiver","type":"address"},{"name":"owner","type":"address"}],"name":"redeem","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"assets","type":"uint256"},{"name":"receiver","type":"address"}],"name":"deposit","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
]

usdc = w3.eth.contract(address=usdc_addr, abi=usdc_abi)
v3c = w3.eth.contract(address=v3_addr, abi=vault_abi)
v5c = w3.eth.contract(address=v5_addr, abi=vault_abi)

def send(tx, label):
    signed = w3.eth.account.sign_transaction(tx, pk)
    h = w3.eth.send_raw_transaction(signed.rawTransaction)
    r = w3.eth.wait_for_transaction_receipt(h, timeout=120)
    stat = "OK" if r.status == 1 else "REVERTED"
    print(f"[{label}] {h.hex()[:20]}... -> {stat}")
    return r.status == 1

# State check
v3_supply = v3c.functions.totalSupply().call()
v3_assets = v3c.functions.totalAssets().call()
wallet_v3 = v3c.functions.balanceOf(wallet).call()
wallet_v5 = v5c.functions.balanceOf(wallet).call()
v5_assets = v5c.functions.totalAssets().call()

print(f"V3 supply: {v3_supply}, assets: {v3_assets/1e6:.6f}, wallet_shares: {wallet_v3}")
print(f"V5 assets: {v5_assets/1e6:.6f}, wallet_shares: {wallet_v5}")

# ERC4626 first-deposit math: shares = assets * totalSupply/totalAssets
# When totalSupply=79, totalAssets=3107579, and we deposited 79 -> we get 79*79/3107579 ≈ 0.002 shares = 0 
# We need to deposit ~3.1 USDC to get proportional shares.
# Strategy: redeem all V5 shares, then use that USDC to deposit into V3 to get proportional share

# Redeem all V5
print("\nRedeeming all V5 shares to get USDC...")
nonce = w3.eth.get_transaction_count(wallet, "pending")
send(v5c.functions.redeem(wallet_v5, wallet, wallet).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 500000, "chainId": 8453}), "Redeem all V5")
time.sleep(3)

wallet_usdc = usdc.functions.balanceOf(wallet).call()
print(f"Wallet USDC: {wallet_usdc/1e6:.6f}")

# Now deposit all into V3 to get proportional shares
# V3 totalAssets = 3107579, totalSupply = 79
# Depositing our USDC: shares = usdc * 79 / 3107579
v3_supply2 = v3c.functions.totalSupply().call()
v3_assets2 = v3c.functions.totalAssets().call()
print(f"V3 current: supply={v3_supply2}, assets={v3_assets2/1e6:.6f}")

if wallet_usdc > 0 and v3_supply2 > 0 and v3_assets2 > 0:
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    send(usdc.functions.approve(v3_addr, wallet_usdc).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 100000, "chainId": 8453}), "Approve V3")
    time.sleep(2)
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    send(v3c.functions.deposit(wallet_usdc, wallet).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 500000, "chainId": 8453}), "Deposit wallet USDC into V3")
    time.sleep(2)

wallet_v3_new = v3c.functions.balanceOf(wallet).call()
print(f"Wallet V3 shares now: {wallet_v3_new}")

if wallet_v3_new > 0:
    # Redeem ALL V3 shares
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    ok = send(v3c.functions.redeem(wallet_v3_new, wallet, wallet).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 500000, "chainId": 8453}), "Redeem all V3")
    if ok:
        time.sleep(2)
        wallet_usdc2 = usdc.functions.balanceOf(wallet).call()
        print(f"Wallet USDC after V3 redeem: {wallet_usdc2/1e6:.4f}")
        if wallet_usdc2 > 10000:
            nonce = w3.eth.get_transaction_count(wallet, "pending")
            send(usdc.functions.approve(v5_addr, wallet_usdc2).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 100000, "chainId": 8453}), "Approve V5")
            time.sleep(2)
            nonce = w3.eth.get_transaction_count(wallet, "pending")
            send(v5c.functions.deposit(wallet_usdc2, wallet).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 500000, "chainId": 8453}), "Final deposit V5")
            time.sleep(2)

# Final state
v5_final = v5c.functions.totalAssets().call()
v3_final = v3c.functions.totalAssets().call()
wallet_usdc_final = usdc.functions.balanceOf(wallet).call()
print("\n=== FINAL STATE ===")
print(f"V5 totalAssets: ${v5_final/1e6:.4f}")
print(f"V3 totalAssets: ${v3_final/1e6:.4f}")
print(f"Wallet USDC: ${wallet_usdc_final/1e6:.4f}")
