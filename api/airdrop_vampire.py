import os
import json
import time
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv

load_dotenv('../keeper/.env')

RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://mainnet.base.org")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

# Deployed Promo Token Address
TOKEN_ADDRESS = "0x03a1363AafeaD13237Ac7065D3d6342CdB56a9B1"
TARGET_USERS = 100
AIRDROP_AMOUNT_PER_USER = 10**14 # 0.0001 tokens (18 decimals)

w3 = Web3(Web3.HTTPProvider(RPC_URL))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

ABI = [
    {
        "inputs": [
            {"internalType": "address[]", "name": "recipients", "type": "address[]"},
            {"internalType": "uint256", "name": "amountPerUser", "type": "uint256"}
        ],
        "name": "airdrop",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

def get_active_users(num_users):
    print(f"Scanning mempool and blocks for Morpho/Aerodrome {num_users} active Base users...")
    latest_block = w3.eth.block_number
    active_addresses = set()
    
    block_offset = 0
    while len(active_addresses) < num_users:
        block = w3.eth.get_block(latest_block - block_offset, full_transactions=True)
        for tx in block.transactions:
            if tx['from'] not in active_addresses and tx['from'].lower() != WALLET_ADDRESS.lower():
                active_addresses.add(tx['from'])
                if len(active_addresses) >= num_users:
                    break
        block_offset += 1
        time.sleep(0.1) # Be nice to public RPCs if using them
        
    return list(active_addresses)

def run_airdrop():
    if not w3.is_connected():
        print("Failed to connect to Base RPC")
        return

    print("Connected to Base. Wallet:", WALLET_ADDRESS)
    
    recipients = get_active_users(TARGET_USERS)
    print(f"Found {len(recipients)} active users. Preparing airdrop tx...")
    
    token_contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=ABI)
    
    # Checksum addresses
    checksummed_recipients = [w3.to_checksum_address(addr) for addr in recipients]
    
    nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
    
    tx = token_contract.functions.airdrop(
        checksummed_recipients,
        AIRDROP_AMOUNT_PER_USER
    ).build_transaction({
        'chainId': 8453, # Base Mainnet
        'gas': 3000000, # Approximate
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })
    
    print("Signing transaction...")
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    
    print("Broadcasting transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    
    print(f"Airdrop Tx Hash: {tx_hash.hex()}")
    print("Waiting for confirmation...")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        print(f"Success! Airdropped 0.0001 ALM-PROMO to {TARGET_USERS} active users.")
    else:
        print("Transaction failed!")

if __name__ == "__main__":
    run_airdrop()
