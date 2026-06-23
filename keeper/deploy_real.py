import os
import json
from web3 import Web3
from eth_account import Account

RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "fbc6744e12e84564a714018287ce36ac905f611393fac60d4bb2b41286d165e3")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH = "0x4200000000000000000000000000000000000006"
AAVE_POOL = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
UNISWAP_NPM = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"
AAVE_DATA = "0x2d8A3C567705b26F2d361c4E12eB582e0e0176D2"
AAVE_ORACLE = "0x20571bBBdB2CceF754d97d0A1c8f43D165d6A3c5"

out_file = os.path.join("..", "contracts", "out", "ALMVault_Singularity.sol", "ALMVault_Singularity.json")

with open(out_file, "r") as f:
    data = json.load(f)
    abi = data["abi"]
    bytecode = data["bytecode"]["object"]

Vault = w3.eth.contract(abi=abi, bytecode=bytecode)

print(f"Deploying ALMVault_FlashLender from {account.address}...")

USDC = w3.to_checksum_address(USDC)
WETH = w3.to_checksum_address(WETH)
AAVE_POOL = w3.to_checksum_address(AAVE_POOL)
UNISWAP_NPM = w3.to_checksum_address(UNISWAP_NPM)
AAVE_DATA = w3.to_checksum_address(AAVE_DATA)
AAVE_ORACLE = w3.to_checksum_address(AAVE_ORACLE)

tx = Vault.constructor(
    USDC, WETH, account.address, AAVE_POOL, UNISWAP_NPM, AAVE_DATA, AAVE_ORACLE
).build_transaction({
    "from": account.address,
    "nonce": w3.eth.get_transaction_count(account.address),
    "gasPrice": w3.eth.gas_price
})

try:
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Deployment Tx Hash: {tx_hash.hex()}")
    print("Waiting for receipt...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"Contract Deployed at: {receipt.contractAddress}")
except Exception as e:
    print(f"Failed to deploy: {e}")
