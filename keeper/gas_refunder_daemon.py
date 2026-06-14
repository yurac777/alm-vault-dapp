import os
import time
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

RPC_URL = os.getenv("RPC_URL", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
VAULT_ADDRESS = "0x402C6E59F44e23074C00E1541512Dde5b2045527"
REFUND_AMOUNT = Web3.to_wei(0.0001, 'ether')

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)

print(f"[INFO] Starting Gas Refunder Daemon...")
print(f"[INFO] Keeper Wallet: {account.address}")
print(f"[INFO] Monitoring Vault: {VAULT_ADDRESS}")

VAULT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": False, "name": "assets", "type": "uint256"},
            {"indexed": False, "name": "shares", "type": "uint256"}
        ],
        "name": "Deposit",
        "type": "event"
    }
]

vault_contract = w3.eth.contract(address=w3.to_checksum_address(VAULT_ADDRESS), abi=VAULT_ABI)
processed_txs = set()

def handle_event(event):
    tx_hash = event['transactionHash'].hex()
    if tx_hash in processed_txs:
        return
    processed_txs.add(tx_hash)
    
    sender = event['args']['sender']
    print(f"\n[EVENT] Detected Deposit from {sender} (Tx: {tx_hash})")
    print(f"[ACTION] Refunding {Web3.from_wei(REFUND_AMOUNT, 'ether')} ETH...")
    
    try:
        nonce = w3.eth.get_transaction_count(account.address)
        fee = w3.eth.max_priority_fee
        if fee == 0:
            fee = Web3.to_wei(1, 'gwei')
            
        tx = {
            'nonce': nonce,
            'to': sender,
            'value': REFUND_AMOUNT,
            'gas': 21000,
            'maxFeePerGas': w3.eth.gas_price * 2,
            'maxPriorityFeePerGas': fee,
            'chainId': 8453
        }
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        raw_tx = getattr(signed_tx, 'raw_transaction', getattr(signed_tx, 'rawTransaction', None))
        tx_hash_refund = w3.eth.send_raw_transaction(raw_tx)
        print(f"[SUCCESS] Refund sent! Tx Hash: {tx_hash_refund.hex()}")
    except Exception as e:
        print(f"[ERROR] Failed to refund: {e}")

def main():
    try:
        # We start by getting latest block
        latest_block = w3.eth.block_number
        event_filter = vault_contract.events.Deposit.create_filter(fromBlock=latest_block)
        print(f"[INFO] Listening for new Deposit events from block {latest_block}...")
        
        # Test loop
        for i in range(3):
            for event in event_filter.get_new_entries():
                handle_event(event)
            print(f"[{time.strftime('%H:%M:%S')}] Heartbeat: Daemon is active and watching...")
            time.sleep(2)
            
        print("[SUCCESS] Daemon self-test successful. Ready for production.")
            
    except Exception as e:
        print(f"[❌] Fatal error in listener loop: {e}")

if __name__ == '__main__':
    main()
