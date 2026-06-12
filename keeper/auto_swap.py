import os
import sys
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL    = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")

WETH       = "0x4200000000000000000000000000000000000006"
USDC       = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
ROUTER     = "0x2626664c2603336E57B271c5C0b26F421741e481"

SWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "internalType": "struct IV3SwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

def main():
    print("=== Auto Swap ETH -> USDC ===")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("[CRITICAL] Cannot connect to RPC")
        sys.exit(1)

    deployer = w3.to_checksum_address(WALLET)
    balance_eth = w3.eth.get_balance(deployer)
    print(f"Deployer Balance: {balance_eth / 1e18:.6f} ETH")

    if balance_eth < int(0.005 * 1e18):
        print("[CRITICAL] Balance too low to safely swap and pay gas.")
        sys.exit(1)

    swap_amount_wei = int(0.003 * 1e18)
    
    router = w3.eth.contract(address=w3.to_checksum_address(ROUTER), abi=SWAP_ROUTER_ABI)
    
    # Swap ETH -> USDC
    params = {
        "tokenIn": w3.to_checksum_address(WETH),
        "tokenOut": w3.to_checksum_address(USDC),
        "fee": 500,
        "recipient": deployer,
        "amountIn": swap_amount_wei,
        "amountOutMinimum": 0,
        "sqrtPriceLimitX96": 0
    }
    
    nonce = w3.eth.get_transaction_count(deployer)
    gas_price = w3.eth.gas_price
    
    print(f"Swapping {swap_amount_wei / 1e18} ETH to USDC...")
    
    try:
        swap_tx = router.functions.exactInputSingle(params).build_transaction({
            "from": deployer,
            "nonce": nonce,
            "gasPrice": gas_price,
            "value": swap_amount_wei, # Send ETH directly
            "chainId": 8453
        })
        swap_tx["gas"] = int(w3.eth.estimate_gas(swap_tx) * 1.3)
    except Exception as e:
        print(f"SwapRouter02 estimate gas failed, trying legacy SwapRouter (V1) interface... Error: {e}")
        # Legacy Router ABI (has deadline)
        LEGACY_ABI = [
            {
                "inputs": [
                    {
                        "components": [
                            {"internalType": "address", "name": "tokenIn", "type": "address"},
                            {"internalType": "address", "name": "tokenOut", "type": "address"},
                            {"internalType": "uint24", "name": "fee", "type": "uint24"},
                            {"internalType": "address", "name": "recipient", "type": "address"},
                            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                            {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                        ],
                        "internalType": "struct ISwapRouter.ExactInputSingleParams",
                        "name": "params",
                        "type": "tuple"
                    }
                ],
                "name": "exactInputSingle",
                "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        router = w3.eth.contract(address=w3.to_checksum_address(ROUTER), abi=LEGACY_ABI)
        params["deadline"] = int(time.time()) + 600
        swap_tx = router.functions.exactInputSingle(params).build_transaction({
            "from": deployer,
            "nonce": nonce,
            "gasPrice": gas_price,
            "value": swap_amount_wei,
            "chainId": 8453
        })
        swap_tx["gas"] = int(w3.eth.estimate_gas(swap_tx) * 1.3)

    signed_tx = w3.eth.account.sign_transaction(swap_tx, PRIV_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Swap Tx Hash: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        print("[SUCCESS] Swap successful!")
    else:
        print("[CRITICAL] Swap failed!")

if __name__ == "__main__":
    main()
