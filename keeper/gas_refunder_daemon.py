import os
import time
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

RPC_URL = os.getenv("RPC_URL", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
VAULT_ADDRESS = "0x402C6E59F44e23074C00E1541512Dde5b2045527"
REFUND_AMOUNT = Web3.to_wei(0.0001, 'ether')
MIN_DEPOSIT_USDC = 50 * 10**6  # 50 USDC

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
    assets = event['args']['assets']
    
    print(f"\n[EVENT] Detected Deposit from {sender} (Tx: {tx_hash})")
    
    if assets < MIN_DEPOSIT_USDC:
        print(f"[INFO] Deposit too small ({assets / 10**6} USDC). Minimum required: 50 USDC. Skipping refund.")
        return
        
    print(f"[ACTION] Valid deposit of {assets / 10**6} USDC. Refunding {Web3.from_wei(REFUND_AMOUNT, 'ether')} ETH...")
    
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
        from_block = w3.eth.block_number
        print(f"[INFO] Starting polling for Deposit events from block {from_block}...")
        
        while True:
            current_block = w3.eth.block_number
            if current_block >= from_block:
                try:
                    logs = vault_contract.events.Deposit.get_logs(fromBlock=from_block, toBlock=current_block)
                    for event in logs:
                        handle_event(event)
                    from_block = current_block + 1
                except Exception as e:
                    print(f"[WARN] Failed to fetch logs: {e}")
            
            print(f"[{time.strftime('%H:%M:%S')}] Heartbeat: Daemon is active and polling... (Last checked block: {current_block})")
            time.sleep(10)
            
    except Exception as e:
        print(f"[ERROR] Fatal error in listener loop: {e}")

if __name__ == '__main__':
    main()
