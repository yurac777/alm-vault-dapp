import os
import time
import subprocess
from dotenv import load_dotenv
from web3 import Web3

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
WALLET = os.getenv("WALLET_ADDRESS", "0x00000FdE9Fd1A4574D7141BC438DBCaFd4c0e153")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
wallet_address = w3.to_checksum_address(WALLET)

print(f"Starting Watchdog on wallet: {wallet_address} (Watching Native ETH)")

while True:
    try:
        bal_wei = w3.eth.get_balance(wallet_address)
        eth_amount = bal_wei / 1e18
        
        if eth_amount > 0.0005:
            print(f"[ALERT] GAS REFILLED: {eth_amount:.6f} ETH")
            
            print("[Watchdog] Triggering deposit.py...")
            subprocess.run(["python", "keeper/deposit.py"], check=False)
            
            print("[Watchdog] Triggering main.py --force --run-once...")
            subprocess.run(["python", "keeper/main.py", "--force", "--run-once"], check=False)
            
            print("[Watchdog] Rebalance complete. Exiting watchdog.")
            break
        else:
            print(f"[Watchdog] Waiting for ETH from bridge... Current: {eth_amount:.6f} ETH")
            
    except Exception as e:
        print(f"[Watchdog] RPC Error during eth_call: {e}")

    time.sleep(30)
