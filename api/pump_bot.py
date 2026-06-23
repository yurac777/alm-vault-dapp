import os
import time
import random
from web3 import Web3
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../keeper/.env')

RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://mainnet.base.org")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

# ALM-PROMO token address
PROMO_TOKEN = "0x03a1363AafeaD13237Ac7065D3d6342CdB56a9B1"

# Uniswap V2 Router on Base (BaseSwap or similar V2 fork is often used for memecoins, 
# or standard Uniswap V3 Router. For this script, we use Uniswap Universal Router)
# Uniswap Universal Router Base: 0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD
UNI_ROUTER = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
WETH = "0x4200000000000000000000000000000000000006"

w3 = Web3(Web3.HTTPProvider(RPC_URL))
# Middleware injection removed for web3.py v7 compatibility

# Minimal ERC20 ABI for Approval
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

def approve_token():
    """Approve the router to spend our ALM-PROMO tokens"""
    print("Approving Router...")
    token = w3.eth.contract(address=PROMO_TOKEN, abi=ERC20_ABI)
    nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
    
    tx = token.functions.approve(UNI_ROUTER, 2**256 - 1).build_transaction({
        'chainId': 8453,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"Approval tx: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)

def simulate_buy():
    """Simulates a BUY transaction by sending ETH to the router to buy ALM-PROMO"""
    print(f"[{time.strftime('%X')}] 🟢 BUYING ALM-PROMO...")
    # In a real environment, this would call Uniswap Router's swapExactETHForTokens or Universal Router execute.
    # To save real funds during the demo, this script will log the intent.
    buy_amount_eth = random.uniform(0.001, 0.005)
    print(f"   -> Executed BUY of {buy_amount_eth:.4f} ETH")
    time.sleep(random.randint(5, 15))

def simulate_sell():
    """Simulates a SELL transaction by selling ALM-PROMO back to ETH"""
    print(f"[{time.strftime('%X')}] 🔴 SELLING ALM-PROMO...")
    # In a real environment, this calls swapExactTokensForETH.
    sell_amount_tokens = random.randint(1000, 5000)
    print(f"   -> Executed SELL of {sell_amount_tokens} PROMO")
    time.sleep(random.randint(5, 15))

def pump_bot_loop():
    print("=======================================")
    print("🚀 ALM-PROMO PUMP & WASH TRADING BOT 🚀")
    print("=======================================")
    print("Target: DexScreener Trending #1 on Base")
    print("Initializing...")
    
    if not w3.is_connected():
        print("Failed to connect to RPC")
        return
        
    print(f"Connected. Wallet: {WALLET_ADDRESS}")
    
    # Uncomment to actually approve the router (requires gas)
    # approve_token()
    
    print("Starting automated market making (Wash Trading) algorithm...")
    
    # We create a 3:1 Buy:Sell ratio to ensure the chart prints mostly green candles
    while True:
        try:
            action = random.choices(['BUY', 'SELL'], weights=[75, 25])[0]
            
            if action == 'BUY':
                simulate_buy()
            else:
                simulate_sell()
                
            # Random delay between trades to simulate real organic volume
            delay = random.randint(15, 60)
            print(f"   -> Waiting {delay} seconds until next trade...")
            time.sleep(delay)
            
        except KeyboardInterrupt:
            print("\nBot stopped by user.")
            break
        except Exception as e:
            print(f"Error in pump loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    pump_bot_loop()
