import os
import json
import time
import sys
from dotenv import load_dotenv
from web3 import Web3

env_path = os.path.join(os.path.dirname(__file__), 'keeper', '.env')
load_dotenv(env_path)

RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)

# Load compiled artifact
artifact_path = os.path.join(os.path.dirname(__file__), 'contracts', 'out', 'ALMToken.sol', 'ALMToken.json')
with open(artifact_path, 'r') as f:
    artifact = json.load(f)

abi = artifact['abi']
bytecode = artifact['bytecode']['object']

ALMToken = w3.eth.contract(abi=abi, bytecode=bytecode)
print("Deploying ALMToken...")

try:
    tx = ALMToken.constructor("0x00000FdE9Fd1A4574D7141BC438DBCaFd4c0e153").build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price
    })

    signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print("Tx Sent:", tx_hash.hex())

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Contract Deployed At:", receipt.contractAddress)
    
    # Save the address to .env
    with open(env_path, 'a') as env_file:
        env_file.write(f"\nVALM_ADDRESS={receipt.contractAddress}\n")
    print("VALM_ADDRESS saved to .env")
    
except Exception as e:
    print("CRITICAL ERROR [deploy]:", e)
    sys.exit(1)
