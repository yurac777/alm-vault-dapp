import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))

def verify_yield():
    npm_addr = w3.to_checksum_address(config.UNI_V3_NPM)
    vault_addr = w3.to_checksum_address("0xC29688C7ca27c2826469D3F14D417562CcF5a3b5")
    
    # Get current tokenId from ALMVault
    VAULT_ABI = [{"inputs": [], "name": "currentTokenId", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]
    vault_c = w3.eth.contract(address=vault_addr, abi=VAULT_ABI)
    token_id = vault_c.functions.currentTokenId().call()
    
    NPM_ABI = [{
        "inputs": [{
            "components": [
                {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                {"internalType": "address", "name": "recipient", "type": "address"},
                {"internalType": "uint128", "name": "amount0Max", "type": "uint128"},
                {"internalType": "uint128", "name": "amount1Max", "type": "uint128"}
            ],
            "internalType": "struct INonfungiblePositionManager.CollectParams",
            "name": "params", "type": "tuple"
        }],
        "name": "collect",
        "outputs": [
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    }]
    
    npm = w3.eth.contract(address=npm_addr, abi=NPM_ABI)
    MAX_UINT128 = 2**128 - 1
    
    print(f"Executing static call to NPM.collect for tokenId: {token_id}...")
    try:
        # We must use "from" = vault_addr because only the owner/operator can collect from NPM
        res = npm.functions.collect((token_id, vault_addr, MAX_UINT128, MAX_UINT128)).call({"from": vault_addr})
        amount0 = res[0]
        amount1 = res[1]
        print(f"\nRAW RETURN DATA: {res}")
        print(f"Decoded: tokensOwed0 (WETH) = {amount0} wei ({amount0/1e18} WETH)")
        print(f"Decoded: tokensOwed1 (USDC) = {amount1} wei ({amount1/1e6} USDC)")
    except Exception as e:
        print(f"Error executing static call: {e}")

if __name__ == "__main__":
    verify_yield()
