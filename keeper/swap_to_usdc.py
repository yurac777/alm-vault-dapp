import os
import sys
import time
from dotenv import load_dotenv
from web3 import Web3

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
RPC_URL = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
PRIVATE_KEY = os.getenv("KEEPER_PRIVATE_KEY")
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)

SWAP_ROUTER = "0x2626664c2603336E57B271c5C0b26F421741e481"
WETH = "0x4200000000000000000000000000000000000006"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

router_abi = [{
    "inputs": [{
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
    }],
    "name": "exactInputSingle",
    "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
    "stateMutability": "payable",
    "type": "function"
}]

weth_abi = [{"constant": False, "inputs": [{"name": "wad", "type": "uint256"}], "name": "withdraw", "outputs": [], "payable": False, "stateMutability": "nonpayable", "type": "function"},
{"constant": False, "inputs": [{"name": "guy", "type": "address"}, {"name": "wad", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "payable": False, "stateMutability": "nonpayable", "type": "function"}]

weth_contract = w3.eth.contract(address=WETH, abi=weth_abi)

print("Approving WETH...")
tx1 = weth_contract.functions.approve(SWAP_ROUTER, 10000000000000000).build_transaction({
    'from': account.address,
    'nonce': w3.eth.get_transaction_count(account.address),
    'gas': 100000,
    'gasPrice': w3.eth.gas_price
})
signed1 = w3.eth.account.sign_transaction(tx1, PRIVATE_KEY)
tx_hash1 = w3.eth.send_raw_transaction(signed1.rawTransaction)
w3.eth.wait_for_transaction_receipt(tx_hash1)
print("Approved.")

print("Swapping WETH to USDC...")
router = w3.eth.contract(address=SWAP_ROUTER, abi=router_abi)
params = (WETH, USDC, 500, account.address, int(time.time())+600, 500000000000000, 0, 0)
tx2 = router.functions.exactInputSingle(params).build_transaction({
    'from': account.address,
    'nonce': w3.eth.get_transaction_count(account.address),
    'gas': 300000,
    'gasPrice': w3.eth.gas_price
})
signed2 = w3.eth.account.sign_transaction(tx2, PRIVATE_KEY)
tx_hash2 = w3.eth.send_raw_transaction(signed2.rawTransaction)
w3.eth.wait_for_transaction_receipt(tx_hash2)
print("Swapped. Hash:", tx_hash2.hex())
