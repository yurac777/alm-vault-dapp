import os
import sys
from web3 import Web3

# Bootstrap path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keeper import config

def main():
    w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
    if not w3.is_connected():
        print("Failed to connect to Base Mainnet RPC")
        return
        
    vault_address = w3.to_checksum_address("0x87eE1eCa84E9308946eEcba998625272A6ED9a00")
    
    vault_abi = [
        {"inputs":[],"name":"currentTokenId","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
    ]
    vault = w3.eth.contract(address=vault_address, abi=vault_abi)
    
    print("Reading ALMVault current position...")
    try:
        token_id = vault.functions.currentTokenId().call()
        if token_id == 0:
            print("Vault has no active Uniswap V3 position (tokenId = 0).")
            return
        print(f"Vault active tokenId: {token_id}")
    except Exception as e:
        print(f"Failed to read currentTokenId: {e}")
        return
        
    npm_address = w3.to_checksum_address(config.UNI_V3_NPM)
    npm_abi = [
        {
            "inputs": [
                {
                    "components": [
                        {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                        {"internalType": "address", "name": "recipient", "type": "address"},
                        {"internalType": "uint128", "name": "amount0Max", "type": "uint128"},
                        {"internalType": "uint128", "name": "amount1Max", "type": "uint128"}
                    ],
                    "internalType": "struct INonfungiblePositionManager.CollectParams",
                    "name": "params",
                    "type": "tuple"
                }
            ],
            "name": "collect",
            "outputs": [
                {"internalType": "uint256", "name": "amount0", "type": "uint256"},
                {"internalType": "uint256", "name": "amount1", "type": "uint256"}
            ],
            "stateMutability": "payable",
            "type": "function"
        }
    ]
    npm = w3.eth.contract(address=npm_address, abi=npm_abi)
    
    print(f"Executing staticcall to NPM.collect for tokenId {token_id}...")
    
    try:
        # eth_call from the vault address since it owns the NFT
        params = (
            token_id,
            vault_address,
            2**128 - 1, # max amount0
            2**128 - 1  # max amount1
        )
        res = npm.functions.collect(params).call({'from': vault_address})
        amount0 = res[0]
        amount1 = res[1]
        
        # WETH (18 decimals), USDC (6 decimals)
        weth_fee = amount0 / 1e18
        usdc_fee = amount1 / 1e6
        
        # Assume ETH is ~$3000 for display
        eth_price = 3000.0
        total_usd = (weth_fee * eth_price) + usdc_fee
        
        print(f"--- RESULTS ---")
        print(f"Uncollected WETH: {weth_fee:.8f}")
        print(f"Uncollected USDC: {usdc_fee:.6f}")
        print(f"Total Fees (USD estimate): ${total_usd:.4f}")
        
    except Exception as e:
        print(f"Error during npm.collect call: {e}")

if __name__ == "__main__":
    main()
