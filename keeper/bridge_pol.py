import os
import requests
from web3 import Web3
from dotenv import load_dotenv

load_dotenv("keeper/.env")

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
if not PRIVATE_KEY:
    raise Exception("CRITICAL: PRIVATE_KEY not found in .env")
POLYGON_RPC = "https://polygon.drpc.org"
w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))

wallet = w3.eth.account.from_key(PRIVATE_KEY)

balance = w3.eth.get_balance(wallet.address)
print(f"Actual POL Balance: {balance / 1e18}")

# To leave enough for gas, bridge the balance minus 0.05 POL
amount_to_bridge = balance - int(0.5 * 1e18)

if amount_to_bridge <= 0:
    print("Insufficient funds to perform bridge operation.")
    # For testing API routing even if balance is 0
    amount_to_bridge = int(17.8 * 1e18)

url = "https://li.quest/v1/quote"
params = {
    "fromChain": "137",
    "toChain": "8453",
    "fromToken": "0x0000000000000000000000000000000000000000",
    "toToken": "0x0000000000000000000000000000000000000000",
    "fromAmount": str(amount_to_bridge),
    "fromAddress": wallet.address
}

print(f"Requesting quote from Li.Fi for {amount_to_bridge / 1e18} POL to Base ETH...")
response = requests.get(url, params=params)
if response.status_code != 200:
    print(f"Failed to get quote: {response.text}")
    exit(1)

quote = response.json()
tx_request = quote['transactionRequest']

print(f"Quote received. Expected Output: {int(quote['estimate']['toAmount']) / 1e18} ETH")

tx = {
    'to': w3.to_checksum_address(tx_request['to']),
    'data': tx_request['data'],
    'value': int(tx_request['value'], 16),
    'gas': 600000,
    'gasPrice': w3.eth.gas_price,
    'nonce': w3.eth.get_transaction_count(wallet.address),
    'chainId': 137
}

print("Sending transaction to Polygon network...")
try:
    signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"Tx Hash: {tx_hash.hex()}")
except Exception as e:
    print(f"Error sending tx: {e}")
