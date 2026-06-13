import os
import time
import sys
from dotenv import load_dotenv
from web3 import Web3

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
VALM_ADDRESS = os.getenv("VALM_ADDRESS", "0xF5150B45f3D8430B28b7777c402b7fA80Ad702FA")
USDC_ADDRESS = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
WETH_ADDRESS = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")
SWAP_ROUTER_ADDRESS = Web3.to_checksum_address("0x2626664c2603336E57B271c5C0b26F421741e481")
NFPM_ADDRESS = Web3.to_checksum_address("0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

ERC20_ABI = [
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"inputs": [{"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "mint", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]

SWAP_ROUTER_ABI = [
    {"inputs": [{"components": [{"internalType": "address", "name": "tokenIn", "type": "address"}, {"internalType": "address", "name": "tokenOut", "type": "address"}, {"internalType": "uint24", "name": "fee", "type": "uint24"}, {"internalType": "address", "name": "recipient", "type": "address"}, {"internalType": "uint256", "name": "amountIn", "type": "uint256"}, {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"}, {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}], "internalType": "struct IV3SwapRouter.ExactInputSingleParams", "name": "params", "type": "tuple"}], "name": "exactInputSingle", "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}], "stateMutability": "payable", "type": "function"}
]

NFPM_ABI = [
    {"inputs": [{"components": [{"internalType": "address", "name": "token0", "type": "address"}, {"internalType": "address", "name": "token1", "type": "address"}, {"internalType": "uint24", "name": "fee", "type": "uint24"}, {"internalType": "int24", "name": "tickLower", "type": "int24"}, {"internalType": "int24", "name": "tickUpper", "type": "int24"}, {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"}, {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"}, {"internalType": "uint256", "name": "amount0Min", "type": "uint256"}, {"internalType": "uint256", "name": "amount1Min", "type": "uint256"}, {"internalType": "address", "name": "recipient", "type": "address"}, {"internalType": "uint256", "name": "deadline", "type": "uint256"}], "internalType": "struct INonfungiblePositionManager.MintParams", "name": "params", "type": "tuple"}], "name": "mint", "outputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}, {"internalType": "uint128", "name": "liquidity", "type": "uint128"}, {"internalType": "uint256", "name": "amount0", "type": "uint256"}, {"internalType": "uint256", "name": "amount1", "type": "uint256"}], "stateMutability": "payable", "type": "function"}
]

def execute_tx(tx, private_key, wait=True):
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
    if not PRIVATE_KEY:
        print("PRIVATE_KEY not found.")
        sys.exit(1)

    account = w3.eth.account.from_key(PRIVATE_KEY)
    valm = Web3.to_checksum_address(VALM_ADDRESS)
    
    # 1. Fetch Nonce (Pending)
    nonce = w3.eth.get_transaction_count(account.address, 'pending')
    print(f"Starting Nonce: {nonce}")

    try:
        # 2. Auto-Fund USDC
        print("1. Auto-Funding USDC (Swapping 0.0003 WETH to USDC)...")
        weth = w3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)
        amount_in = int(0.0003 * 10**18)
        
        # Approve WETH to Router
        tx_weth_app = weth.functions.approve(SWAP_ROUTER_ADDRESS, amount_in).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })
        execute_tx(tx_weth_app, PRIVATE_KEY)
        nonce += 1
        
        router = w3.eth.contract(address=SWAP_ROUTER_ADDRESS, abi=SWAP_ROUTER_ABI)
        params = (WETH_ADDRESS, USDC_ADDRESS, 500, account.address, amount_in, 0, 0)
        
        tx_fund = router.functions.exactInputSingle(params).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price
        })
        execute_tx(tx_fund, PRIVATE_KEY)
        nonce += 1

        # 3. Mint vALM to Self
        print("2. Minting 100,000 vALM to self...")
        valm_contract = w3.eth.contract(address=valm, abi=ERC20_ABI)
        valm_amount = 100_000 * 10**18
        tx_mint = valm_contract.functions.mint(account.address, valm_amount).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })
        execute_tx(tx_mint, PRIVATE_KEY)
        nonce += 1

        # 4. Approve Tokens
        print("3. Approving Tokens for NFPM...")
        token0, token1 = (valm, USDC_ADDRESS) if valm.lower() < USDC_ADDRESS.lower() else (USDC_ADDRESS, valm)
        usdc_amount = 500000 # 0.5 USDC
        amount0 = valm_amount if token0 == valm else usdc_amount
        amount1 = usdc_amount if token0 == valm else valm_amount

        erc20_0 = w3.eth.contract(address=token0, abi=ERC20_ABI)
        erc20_1 = w3.eth.contract(address=token1, abi=ERC20_ABI)

        tx_app0 = erc20_0.functions.approve(NFPM_ADDRESS, amount0).build_transaction({
            'from': account.address, 'nonce': nonce, 'gas': 100000, 'gasPrice': w3.eth.gas_price
        })
        execute_tx(tx_app0, PRIVATE_KEY)
        nonce += 1

        tx_app1 = erc20_1.functions.approve(NFPM_ADDRESS, amount1).build_transaction({
            'from': account.address, 'nonce': nonce, 'gas': 100000, 'gasPrice': w3.eth.gas_price
        })
        execute_tx(tx_app1, PRIVATE_KEY)
        nonce += 1

        # 5. Mint Liquidity
        print("4. Minting Initial Liquidity (Adding to Pool)...")
        nfpm = w3.eth.contract(address=NFPM_ADDRESS, abi=NFPM_ABI)
        tx_liq = nfpm.functions.mint((
            token0, token1, 10000, -887200, 887200, amount0, amount1, 0, 0, account.address, int(time.time()) + 600
        )).build_transaction({
            'from': account.address, 'nonce': nonce, 'gas': 1500000, 'gasPrice': w3.eth.gas_price
        })
        execute_tx(tx_liq, PRIVATE_KEY)
        nonce += 1

        print("Listing Complete! Liquidity added.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
