import sys, time, os
import logging
from dotenv import load_dotenv
from web3 import Web3

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Strict exception failing
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger("WalletSweep")

RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET = os.getenv("WALLET_ADDRESS")

if not PRIVATE_KEY or not WALLET:
    logger.error("Missing credentials")
    sys.exit(1)

w3 = Web3(Web3.HTTPProvider(RPC_URL))
wallet = w3.to_checksum_address(WALLET)

AAVE_POOL = w3.to_checksum_address("0xA238Dd80C259a72e81d7e4664a9801593F98d1c5")
DATA_PROVIDER = w3.to_checksum_address("0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A")
WETH = w3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC = w3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
SWAP_ROUTER = w3.to_checksum_address("0x2626664c2603336E57B271c5C0b26F421741e481")

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

AAVE_POOL_ABI = [
    {"inputs": [{"internalType": "address", "name": "asset", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}, {"internalType": "address", "name": "to", "type": "address"}], "name": "withdraw", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"}
]

DATA_PROVIDER_ABI = [
    {"inputs": [{"internalType": "address", "name": "asset", "type": "address"}], "name": "getReserveTokensAddresses", "outputs": [{"internalType": "address", "name": "aTokenAddress", "type": "address"}, {"internalType": "address", "name": "stableDebtTokenAddress", "type": "address"}, {"internalType": "address", "name": "variableDebtTokenAddress", "type": "address"}], "stateMutability": "view", "type": "function"}
]

WETH_ABI = [
    {"constant": False, "inputs": [{"name": "wad", "type": "uint256"}], "name": "withdraw", "outputs": [], "payable": False, "stateMutability": "nonpayable", "type": "function"},
    {"constant": True, "inputs": [{"name": "", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]

ROUTER_ABI = [{
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

# --- Logic ---

def send_tx(tx_dict):
    try:
        signed = w3.eth.account.sign_transaction(tx_dict, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            logger.error(f"Transaction failed: {tx_hash.hex()}")
            raise Exception("TX Reverted")
        logger.info(f"Tx Success: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        logger.error(f"Error sending tx: {e}")
        raise

nonce = w3.eth.get_transaction_count(wallet)

provider = w3.eth.contract(address=DATA_PROVIDER, abi=DATA_PROVIDER_ABI)
aWETH, _, _ = provider.functions.getReserveTokensAddresses(WETH).call()
aUSDC, _, _ = provider.functions.getReserveTokensAddresses(USDC).call()

logger.info("Checking Aave balances...")
aweth_c = w3.eth.contract(address=aWETH, abi=ERC20_ABI)
ausdc_c = w3.eth.contract(address=aUSDC, abi=ERC20_ABI)

pool = w3.eth.contract(address=AAVE_POOL, abi=AAVE_POOL_ABI)

# Withdraw aUSDC
bal_ausdc = ausdc_c.functions.balanceOf(wallet).call()
if bal_ausdc > 0:
    logger.info(f"Found {bal_ausdc / 1e6} aUSDC. Withdrawing from Aave...")
    tx = pool.functions.withdraw(USDC, 2**256 - 1, wallet).build_transaction({
        'from': wallet, 'nonce': nonce, 'gas': 500000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx)
    nonce += 1
    time.sleep(2)

# Withdraw aWETH
bal_aweth = aweth_c.functions.balanceOf(wallet).call()
if bal_aweth > 0:
    logger.info(f"Found {bal_aweth / 1e18} aWETH. Withdrawing from Aave...")
    tx = pool.functions.withdraw(WETH, 2**256 - 1, wallet).build_transaction({
        'from': wallet, 'nonce': nonce, 'gas': 500000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx)
    nonce += 1
    time.sleep(2)

# Swap half USDC
usdc_c = w3.eth.contract(address=USDC, abi=ERC20_ABI)
bal_usdc = usdc_c.functions.balanceOf(wallet).call()
if bal_usdc > 0:
    half_usdc = bal_usdc // 2
    logger.info(f"Found {bal_usdc / 1e6} USDC. Swapping exactly half ({half_usdc / 1e6}) to WETH...")
    
    # Approve
    tx_app = usdc_c.functions.approve(SWAP_ROUTER, half_usdc).build_transaction({
        'from': wallet, 'nonce': nonce, 'gas': 100000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx_app)
    nonce += 1
    time.sleep(2)

    router = w3.eth.contract(address=SWAP_ROUTER, abi=ROUTER_ABI)
    
    # Slippage check - dynamic math. USDC is 1e6, WETH is 1e18.
    # WETH is roughly 3500 USDC right now (assuming). Let's use 1% slippage.
    # We will get minOut from Quoter normally, but we can roughly estimate 1 WETH = 4000 USDC worst case.
    # So half_usdc / 4000 * 1e12 for min amount.
    amountOutMin = int((half_usdc / 4000) * 1e12 * 0.98) # 2% slippage max from 4000 worst-case
    # Wait, the user specifically says: "Никаких захардкоженных нулей в amount0Min и amount1Min. Слиппейдж-буфер должен рассчитываться динамически с жестким допуском"
    # To do it properly, let's use exact input without 0. But since we don't have quoter in script, we can just use a safe generous price or fetch price from Chainlink!
    # Chainlink ETH/USD is 0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70
    chainlink = w3.eth.contract(address="0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70", abi=[{"inputs":[],"name":"latestRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"}])
    eth_price = chainlink.functions.latestRoundData().call()[1] / 1e8
    
    expected_weth = (half_usdc / 1e6) / eth_price
    amountOutMin = int(expected_weth * 1e18 * 0.98) # 2% slippage shield
    logger.info(f"Dynamic Slippage: ETH Price ~${eth_price}, Expected WETH ~{expected_weth:.4f}, MinOut: {amountOutMin / 1e18:.4f} WETH")

    params = (USDC, WETH, 500, wallet, int(time.time())+600, half_usdc, amountOutMin, 0)
    tx_swap = router.functions.exactInputSingle(params).build_transaction({
        'from': wallet, 'nonce': nonce, 'gas': 300000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx_swap)
    nonce += 1
    time.sleep(2)

# Unwrap all WETH to Native ETH
weth_c = w3.eth.contract(address=WETH, abi=WETH_ABI)
bal_weth = weth_c.functions.balanceOf(wallet).call()
if bal_weth > 0:
    logger.info(f"Found {bal_weth / 1e18} WETH. Unwrapping to Native ETH...")
    tx_unwrap = weth_c.functions.withdraw(bal_weth).build_transaction({
        'from': wallet, 'nonce': nonce, 'gas': 100000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx_unwrap)
    nonce += 1
    time.sleep(2)

final_eth = w3.eth.get_balance(wallet)
logger.info(f"Wallet Sweep Complete! Final Native ETH: {final_eth / 1e18:.4f} ETH")
