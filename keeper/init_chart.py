import os
import json
import time
from datetime import datetime
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("RPC_URL", "https://mainnet.base.org")
web3 = Web3(Web3.HTTPProvider(RPC_URL))

VAULT_ADDRESS = "0x402C6E59F44e23074C00E1541512Dde5b2045527"
VAULT_ABI = [
    {
        "inputs": [],
        "name": "totalAssets",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

def main():
    if not web3.is_connected():
        print("Failed to connect to Base RPC")
        return

    vault = web3.eth.contract(address=VAULT_ADDRESS, abi=VAULT_ABI)
    
    try:
        total_assets = vault.functions.totalAssets().call()
        tvl_usd = total_assets / 10**6
    except Exception as e:
        print(f"Error fetching totalAssets: {e}")
        return

    # Create the single data point
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    data = [
        {
            "timestamp": timestamp,
            "net_worth": round(tvl_usd, 6)
        }
    ]
    
    os.makedirs('frontend', exist_ok=True)
    with open('frontend/pnl_history.json', 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Created frontend/pnl_history.json with TVL: ${tvl_usd}")

if __name__ == "__main__":
    main()
