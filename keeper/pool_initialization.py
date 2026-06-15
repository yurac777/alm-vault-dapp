import os
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
BASE_RPC = os.getenv("BASE_MAINNET_RPC")

VALM_ADDRESS = os.getenv("VALM_ADDRESS")
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
NPM_ADDRESS = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"

# Uniswap V3 NonfungiblePositionManager Minimal ABI
NPM_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "token0", "type": "address"},
            {"internalType": "address", "name": "token1", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"}
        ],
        "name": "createAndInitializePoolIfNecessary",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{
            "components": [
                {"internalType": "address", "name": "token0", "type": "address"},
                {"internalType": "address", "name": "token1", "type": "address"},
                {"internalType": "uint24", "name": "fee", "type": "uint24"},
                {"internalType": "int24", "name": "tickLower", "type": "int24"},
                {"internalType": "int24", "name": "tickUpper", "type": "int24"},
                {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"},
                {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"},
                {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
                {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
                {"internalType": "address", "name": "recipient", "type": "address"},
                {"internalType": "uint256", "name": "deadline", "type": "uint256"}
            ],
            "internalType": "struct INonfungiblePositionManager.MintParams",
            "name": "params",
            "type": "tuple"
        }],
        "name": "mint",
        "outputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]

ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

def get_optimal_gas(w3):
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', 0)
    max_priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = int(base_fee * 1.15) + max_priority_fee
    return {'maxFeePerGas': max_fee_per_gas, 'maxPriorityFeePerGas': max_priority_fee}

def initialize_pool():
    print("Инициализация пула ликвидности...")
    w3 = Web3(Web3.HTTPProvider(BASE_RPC))
    if not w3.is_connected():
        print("Ошибка подключения к RPC")
        return

    account = w3.eth.account.from_key(PRIVATE_KEY)
    npm_contract = w3.eth.contract(address=w3.to_checksum_address(NPM_ADDRESS), abi=NPM_ABI)
    
    valm_addr = w3.to_checksum_address(VALM_ADDRESS)
    usdc_addr = w3.to_checksum_address(USDC_ADDRESS)
    
    # Сортировка токенов по адресу, как требует Uniswap V3
    token0, token1 = (valm_addr, usdc_addr) if valm_addr.lower() < usdc_addr.lower() else (usdc_addr, valm_addr)
    
    fee = 3000 # 0.3% pool
    
    # 1 USDC = 1 vALM для старта. Price ratio = 1:1.
    # Если token0 это USDC (6 dec), а token1 это vALM (18 dec)
    # sqrtPriceX96 нужно посчитать. Для упрощения возьмем 1:1 с учетом децибелов.
    # USDC has 6 decimals, vALM likely has 18.
    # We will just pass a reasonable sqrtPriceX96 for price discovery. 
    # sqrtPriceX96 = sqrt(price * 10**(decimals_token1 - decimals_token0)) * 2**96
    # If 1 vALM = 1 USDC:
    # If token0 is USDC (6), token1 is vALM (18): sqrt(1 * 10**(18-6)) * 2**96 = sqrt(10**12) * 2**96 = 10**6 * 2**96 = 79228162514264337593543950336000000
    # If token0 is vALM (18), token1 is USDC (6): sqrt(1 * 10**(6-18)) * 2**96 = sqrt(10**-12) * 2**96 = 10**-6 * 2**96 = 79228162514264337593543
    
    if token0 == usdc_addr:
        sqrtPriceX96 = 79228162514264337593543950336000000
    else:
        sqrtPriceX96 = 79228162514264337593543

    gas_params = get_optimal_gas(w3)
    
    print(f"Creating pool for {token0} and {token1}...")
    try:
        tx = npm_contract.functions.createAndInitializePoolIfNecessary(
            token0, token1, fee, sqrtPriceX96
        ).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            **gas_params
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transaction sent! Tx Hash: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash)
        print("Pool initialized successfully for price discovery.")
    except Exception as e:
        print(f"Ошибка или пул уже существует: {e}")

if __name__ == "__main__":
    initialize_pool()
