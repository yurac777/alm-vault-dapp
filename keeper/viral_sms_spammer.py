import os
import sys
import time
import logging
from hexbytes import HexBytes

# ── Bootstrap path ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
import config
from connectors.base_rpc import BaseConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] ViralSpammer: %(message)s")
logger = logging.getLogger("ViralSpammer")

# Target contracts (Base)
AAVE_V3_POOL = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5".lower()
AERODROME_ROUTER = "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43".lower()
UNI_V3_ROUTER = "0x2626664c2603336E57B271c5C0b26F421741e481".lower() # SwapRouter02

TARGET_CONTRACTS = {AAVE_V3_POOL, AERODROME_ROUTER, UNI_V3_ROUTER}

MESSAGE = "almUSD is LIVE. 127% Backed. Gas refunded on deposit. DApp: https://alm-quant.xyz/?ref=0x00000FdE9Fd1A4574D7141BC438DBCaFd4c0e153"
CALLDATA = Web3.to_hex(text=MESSAGE)

spammed_addresses = set()

def main():
    logger.info("=== Starting The Unstoppable On-Chain Spammer ===")
    connector = BaseConnector(config.RPC_URL)
    w3 = connector.w3

    while not connector.is_connected():
        logger.warning("Connecting...")
        time.sleep(2)

    wallet = w3.to_checksum_address(config.WALLET)
    
    logger.info(f"Connected. Spammer wallet: {wallet}")
    logger.info(f"Target payload: {MESSAGE}")

    latest_block = w3.eth.block_number
    tx_count = 0

    while True:
        try:
            current_block = w3.eth.block_number
            if latest_block < current_block:
                for block_num in range(latest_block + 1, current_block + 1):
                    block = w3.eth.get_block(block_num, full_transactions=True)
                    logger.info(f"Scanning block {block_num} | Txs: {len(block.transactions)}")
                    
                    for tx in block.transactions:
                        if not tx.get('to'):
                            continue
                        
                        to_addr = tx['to'].lower()
                        sender = tx['from'].lower()
                        
                        if sender in spammed_addresses:
                            continue
                            
                        # Condition: Interact with major DeFi OR have large native balance
                        is_target = False
                        if to_addr in TARGET_CONTRACTS:
                            is_target = True
                        else:
                            # Quick check on value if they transfer large amount
                            if tx.get('value', 0) > w3.to_wei(1, 'ether'):
                                is_target = True
                        
                        if is_target:
                            # Verify whale status
                            try:
                                balance = w3.eth.get_balance(w3.to_checksum_address(sender))
                                if balance >= w3.to_wei(0.5, 'ether'): # Lowered for testing speed, adjust if needed
                                    is_target = True
                                else:
                                    is_target = False
                            except:
                                pass
                                
                        if is_target and sender not in spammed_addresses:
                            logger.info(f"🎯 Whale detected: {sender} (Balance check passed). Spamming...")
                            spammed_addresses.add(sender)
                            
                            try:
                                # Prepare transaction
                                nonce = w3.eth.get_transaction_count(wallet, "pending")
                                
                                # Use EIP-1559 safely
                                base_fee = w3.eth.get_block("pending").baseFeePerGas
                                max_prio = w3.eth.max_priority_fee
                                
                                tx_dict = {
                                    'nonce': nonce,
                                    'to': w3.to_checksum_address(sender),
                                    'value': 1, # 1 wei
                                    'data': CALLDATA,
                                    'gas': 150000,
                                    'maxFeePerGas': int(base_fee * 1.5) + max_prio,
                                    'maxPriorityFeePerGas': max_prio,
                                    'chainId': w3.eth.chain_id
                                }
                                
                                signed_tx = w3.eth.account.sign_transaction(tx_dict, config.PRIVATE_KEY)
                                tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                                logger.info(f"✅ VIRUS SENT to {sender}: {tx_hash.hex()}")
                                
                                tx_count += 1
                                if tx_count >= 3:
                                    logger.info("3 Viral TXs sent. Mission complete.")
                                    return
                                    
                            except Exception as e:
                                logger.error(f"Failed to send to {sender}: {e}")
                
                latest_block = current_block
            
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Scan loop error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
