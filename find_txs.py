import sys
sys.path.insert(0, 'keeper')
from config import RPC_URL, WALLET
from web3 import Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
wallet = w3.to_checksum_address(WALLET)
latest = w3.eth.block_number
print(f"Scanning blocks {latest - 50} to {latest} for wallet {wallet}...")
for i in range(latest - 50, latest + 1):
    block = w3.eth.get_block(i, full_transactions=True)
    for tx in block.transactions:
        if tx['from'] == wallet:
            print(f"Block {i}: {tx.hash.hex()}")
