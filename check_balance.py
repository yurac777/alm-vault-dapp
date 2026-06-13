import os
from dotenv import load_dotenv
from web3 import Web3

load_dotenv("keeper/.env")
RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
WALLET = "0x00000FdE9Fd1A4574D7141BC438DBCaFd4c0e153"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

w3 = Web3(Web3.HTTPProvider(RPC_URL))
wallet_addr = w3.to_checksum_address(WALLET)
usdc_addr = w3.to_checksum_address(USDC)

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]

usdc_contract = w3.eth.contract(address=usdc_addr, abi=ERC20_ABI)
bal = usdc_contract.functions.balanceOf(wallet_addr).call()

print(f"RAW BALANCE INT: {bal}")
print(f"USDC BALANCE: {bal / 1e6} USDC")
