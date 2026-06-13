import os
import time
import random
import sys
from dotenv import load_dotenv
from web3 import Web3

# Load from keeper/.env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Configuration
RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
VALM_ADDRESS = os.getenv("VALM_ADDRESS", "0xF5150B45f3D8430B28b7777c402b7fA80Ad702FA")
USDC_ADDRESS = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
WETH_ADDRESS = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")

# Uniswap V3 SwapRouter on Base
SWAP_ROUTER_ADDRESS = Web3.to_checksum_address("0x2626664c2603336E57B271c5C0b26F421741e481")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

SWAP_ROUTER_ABI = [
    {
        "inputs": [{
            "components": [
                {"internalType": "address", "name": "tokenIn", "type": "address"},
                {"internalType": "address", "name": "tokenOut", "type": "address"},
                {"internalType": "uint24", "name": "fee", "type": "uint24"},
                {"internalType": "address", "name": "recipient", "type": "address"},
                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
            ],
            "internalType": "struct ISwapRouter.ExactInputSingleParams",
            "name": "params",
            "type": "tuple"
        }],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

ERC20_ABI = [
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

def execute_tx(w3, tx, private_key, wait=True):
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"Tx Hash: {tx_hash.hex()}")
    if wait:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise Exception("Transaction failed in block!")
        return receipt
    return tx_hash

def main():
    if not PRIVATE_KEY or VALM_ADDRESS == "0x0000000000000000000000000000000000000000":
        print("Set PRIVATE_KEY and VALM_ADDRESS in .env!")
        sys.exit(1)

    account = w3.eth.account.from_key(PRIVATE_KEY)
    valm = Web3.to_checksum_address(VALM_ADDRESS)
    router = w3.eth.contract(address=SWAP_ROUTER_ADDRESS, abi=SWAP_ROUTER_ABI)

    print("Market Maker Bot Initialized.")
    print("MEV-Shield active (Alchemy Private RPC).")
    
    # 1. Fetch initial nonce
    nonce = w3.eth.get_transaction_count(account.address, 'pending')
    
    # Auto-fund USDC
    # Already funded in previous run
    # print("Auto-funding USDC for bot swaps...")
    # ...
    # weth = w3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)
    # fund_in = int(0.0003 * 10**18)
    # tx_wapp = weth.functions.approve(SWAP_ROUTER_ADDRESS, fund_in).build_transaction({
    #     'from': account.address, 'nonce': nonce, 'gas': 100000, 'gasPrice': w3.eth.gas_price
    # })
    # execute_tx(w3, tx_wapp, PRIVATE_KEY)
    # nonce += 1
    # params_fund = (WETH_ADDRESS, USDC_ADDRESS, 500, account.address, fund_in, 0, 0)
    # tx_fund = router.functions.exactInputSingle(params_fund).build_transaction({
    #     'from': account.address, 'nonce': nonce, 'gas': 300000, 'gasPrice': w3.eth.gas_price
    # })
    # execute_tx(w3, tx_fund, PRIVATE_KEY)
    # nonce += 1
    
    buy_count = 0
    while True:
        is_buy = True if buy_count < 3 else random.choice([True, False])
        buy_count += 1
        # Random amount between 0.01 and 0.05 USDC equivalent
        amount_usd = random.uniform(0.01, 0.05)
        
        token_in = USDC_ADDRESS if is_buy else valm
        token_out = valm if is_buy else USDC_ADDRESS
        
        # Convert amount to decimals (assuming 1 USDC = 1 USD for simplicity)
        if is_buy:
            amount_in = int(amount_usd * 10**6)
        else:
            # Need to know vALM price to calculate correct amount_in, or just guess
            amount_in = int(amount_usd * 200_000 * 10**18) # Rough estimate based on initial pool

        print(f"\nAction: {'BUY' if is_buy else 'SELL'} vALM")
        print(f"Amount In: {amount_in}")
        
        # Check allowance and approve if necessary
        try:
            erc20 = w3.eth.contract(address=token_in, abi=ERC20_ABI)
            print(f"Approving {amount_in} of token_in...")
            tx_app = erc20.functions.approve(SWAP_ROUTER_ADDRESS, amount_in).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price
            })
            execute_tx(w3, tx_app, PRIVATE_KEY)
            nonce += 1
            
            params = (
                token_in, token_out, 10000, account.address, amount_in, 0, 0
            )
            print("Executing swap...")
            tx = router.functions.exactInputSingle(params).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 300000,
                'gasPrice': w3.eth.gas_price
            })
            execute_tx(w3, tx, PRIVATE_KEY)
            nonce += 1
            
        except Exception as e:
            print(f"CRITICAL ERROR [volume_bot execution]: {e}")
            sys.exit(1)
        
        delay = random.randint(3, 10) # 3 to 10 seconds for testing
        print(f"Swap successful. MEV-Shield active. Sleeping for {delay} seconds before next swap...")
        time.sleep(delay)
        
        if buy_count >= 3:
            break

if __name__ == "__main__":
    main()
