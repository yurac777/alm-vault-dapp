import os
import time
from web3 import Web3
from eth_account import Account

RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "fbc6744e12e84564a714018287ce36ac905f611393fac60d4bb2b41286d165e3")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)

VAULT_V1 = w3.to_checksum_address("0x402C6E59F44e23074C00E1541512Dde5b2045527")
VAULT_V2 = w3.to_checksum_address("0x94b74C2d16D694AB7f5F102F879a505c82CAB5a8")
USDC_ADDR = w3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")

# We will migrate the exact balance
AMOUNT_USDC = 2812053

erc4626_abi = [
    {"inputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}, {"internalType": "address", "name": "owner", "type": "address"}], "name": "withdraw", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}], "name": "deposit", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"}
]
erc20_abi = [
    {"inputs": [{"internalType": "address", "name": "spender", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"}
]

v1 = w3.eth.contract(address=VAULT_V1, abi=erc4626_abi)
v2 = w3.eth.contract(address=VAULT_V2, abi=erc4626_abi)
usdc = w3.eth.contract(address=USDC_ADDR, abi=erc20_abi)

print(f"Starting Real Migration from {account.address}")
nonce = w3.eth.get_transaction_count(account.address)

def send_tx(tx_build):
    global nonce
    signed_tx = account.sign_transaction(tx_build)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Broadcasted Tx: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    nonce += 1
    return tx_hash.hex()

try:
    print(f"1. Withdrawing {AMOUNT_USDC} from V1...")
    tx1 = v1.functions.withdraw(AMOUNT_USDC, account.address, account.address).build_transaction({
        "from": account.address, "nonce": nonce, "gasPrice": w3.eth.gas_price
    })
    send_tx(tx1)

    print(f"2. Approving V2...")
    tx2 = usdc.functions.approve(VAULT_V2, AMOUNT_USDC).build_transaction({
        "from": account.address, "nonce": nonce, "gasPrice": w3.eth.gas_price
    })
    send_tx(tx2)

    print(f"3. Depositing to V2...")
    tx3 = v2.functions.deposit(AMOUNT_USDC, account.address).build_transaction({
        "from": account.address, "nonce": nonce, "gasPrice": w3.eth.gas_price
    })
    final_tx = send_tx(tx3)

    print("\n--- REAL MIGRATION COMPLETE ---")
    print(f"Final Tx Hash: {final_tx}")

except Exception as e:
    print(f"Migration Error: {e}")
