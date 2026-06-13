import sys
import os
import time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3
from eth_account import Account

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
account = Account.from_key(config.PRIVATE_KEY)
wallet = w3.to_checksum_address(config.WALLET)

vault_addresses = [
    "0xfFeAE0f67C0471fDBe11F5210F3d1B193b4DAfEB",
    "0xC29688C7ca27c2826469D3F14D417562CcF5a3b5",
    "0xE53117F9Bd6D13E54C870fDF636472Bc811c3101",
    "0x87eE1eCa84E9308946eEcba998625272A6ED9a00",
    "0xF5150B45f3D8430B28b7777c402b7fA80Ad702FA",
    "0x6B2Ec85Fb2c4CE051B71804e20aD8F2c03DADcB4",
    "0x75fd978542e082d455879A9301567438e71db9ec",
    "0x80968E24355D449202206FEEA6dB829F2c1CaBCE",
    "0xE641B48B5B5ea0b88367B681e3e416c0588Cfd44",
    "0x5BE2DA950F8F15588bb0B670e9b8c3f538aE8E5d",
    "0x6C1795ECe776C5f5706862B2FCAD973fc1f4CEd3",
    "0xB3A06a02b283F7271EFe6B2DF4Fc0F3c8Ef0413C",
    "0x263e18540DCCcc296c51ae239D8f2e56ECAbB1f1",
    "0x9a45aC52cDDe7e0865F2b39BABAE486188Cc88c7"
]

tokens = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "aUSDC": "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB",
    "WETH": "0x4200000000000000000000000000000000000006"
}

ERC20_ABI = [{"constant": True,"inputs": [{"name": "_owner", "type": "address"}],"name": "balanceOf","outputs": [{"name": "balance", "type": "uint256"}],"type": "function"}]
RESCUE_ABI = [{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"rescueFunds","outputs":[],"stateMutability":"nonpayable","type":"function"}]
UNWIND_ABI = [{"inputs":[],"name":"emergencyUnwind","outputs":[],"stateMutability":"nonpayable","type":"function"}]

print("=== FINAL UNWIND PROTOCOL ===")
current_nonce = w3.eth.get_transaction_count(wallet)

for v_addr in vault_addresses:
    print(f"\\nInspecting Vault: {v_addr}")
    v = w3.to_checksum_address(v_addr)
    for name, t_addr in tokens.items():
        t = w3.to_checksum_address(t_addr)
        token_contract = w3.eth.contract(address=t, abi=ERC20_ABI)
        bal = token_contract.functions.balanceOf(v).call()
        if bal > 0:
            print(f"  Found {bal} {name}!")
            vault_contract = w3.eth.contract(address=v, abi=RESCUE_ABI)
            try:
                tx = vault_contract.functions.rescueFunds(t, bal).build_transaction({
                    'from': wallet,
                    'nonce': current_nonce,
                    'gas': 100000,
                    'gasPrice': w3.eth.gas_price
                })
                signed = w3.eth.account.sign_transaction(tx, private_key=config.PRIVATE_KEY)
                tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
                current_nonce += 1
                w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"  [OK] Swept {name} via rescueFunds: {tx_hash.hex()}")
            except Exception as e:
                print(f"  [ERROR] rescueFunds failed: {e}")

print("\\nSweeping Wallet aUSDC back to USDC...")
aave_pool = w3.eth.contract(address=w3.to_checksum_address(config.AAVE_POOL), abi=[{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"address","name":"to","type":"address"}],"name":"withdraw","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}])
ausdc_contract = w3.eth.contract(address=w3.to_checksum_address(tokens["aUSDC"]), abi=ERC20_ABI)
bal_ausdc = ausdc_contract.functions.balanceOf(wallet).call()
if bal_ausdc > 0:
    try:
        tx = aave_pool.functions.withdraw(w3.to_checksum_address(tokens["USDC"]), 2**256 - 1, wallet).build_transaction({
            'from': wallet,
            'nonce': current_nonce,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price
        })
        signed = w3.eth.account.sign_transaction(tx, private_key=config.PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        current_nonce += 1
        w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"  [OK] Withdrew aUSDC to USDC: {tx_hash.hex()}")
    except Exception as e:
        print(f"  [ERROR] Aave withdraw failed: {e}")

usdc_contract = w3.eth.contract(address=w3.to_checksum_address(tokens["USDC"]), abi=ERC20_ABI)
print(f"\\nFINAL WALLET USDC BALANCE: {usdc_contract.functions.balanceOf(wallet).call() / 1e6:.4f}")
