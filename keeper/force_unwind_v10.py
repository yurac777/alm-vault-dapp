import sys
from web3 import Web3
import json
import time

sys.path.insert(0, 'keeper')
import config

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
V10_ADDRESS = config.VAULT_ADDRESS

def force_unwind():
    print(f"Loading V10 Vault at {V10_ADDRESS}")
    with open('contracts/out/ALMVaultV10.sol/ALMVaultV10.json', 'r') as f:
        v10_data = json.load(f)
    v10 = w3.eth.contract(address=w3.to_checksum_address(V10_ADDRESS), abi=v10_data['abi'])
    
    # Check current token id
    tokenId = v10.functions.currentTokenId().call()
    liquidity = v10.functions.currentLiquidity().call()
    print(f"Current V10 Position: TokenID {tokenId}, Liquidity {liquidity}")
    
    # Construct payload
    data_bytes = bytearray(416)
    MAX_UINT256 = (1 << 256) - 1
    
    # offset 288: aave repay WETH
    data_bytes[288:320] = MAX_UINT256.to_bytes(32, byteorder='big')
    
    # offset 320: aave withdraw USDC
    data_bytes[320:352] = MAX_UINT256.to_bytes(32, byteorder='big')
    
    # offset 192, 224: amount0Desired and amount1Desired remain 0
    
    print("Sending rebalance transaction to force unwind...")
    tx = v10.functions.rebalance(0, bytes(data_bytes)).build_transaction({
        'from': wallet,
        'nonce': w3.eth.get_transaction_count(wallet),
        'gas': 1500000,
        'gasPrice': w3.eth.gas_price
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=config.PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"Rebalance Tx Hash: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        print("[SUCCESS] Forced Unwind Complete!")
    else:
        print("[FAILED] Unwind reverted.")

if __name__ == "__main__":
    force_unwind()
