import os
import sys
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL    = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")
VAULT      = os.getenv("VAULT_ADDRESS")

VAULT_ABI = [
    {"inputs": [{"name": "_keeper", "type": "address"}], "name": "setKeeper", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]

def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("RPC not connected")
        sys.exit(1)

    deployer = w3.to_checksum_address(WALLET)
    vault_addr = w3.to_checksum_address(VAULT)
    contract = w3.eth.contract(address=vault_addr, abi=VAULT_ABI)

    nonce = w3.eth.get_transaction_count(deployer)
    gas_price = w3.eth.gas_price

    print(f"Setting keeper to {deployer} for {vault_addr}...")
    tx = contract.functions.setKeeper(deployer).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gasPrice": gas_price,
        "chainId": 8453
    })
    
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
    signed = w3.eth.account.sign_transaction(tx, PRIV_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    print(f"Tx: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        print("Success!")
    else:
        print("Failed!")

if __name__ == "__main__":
    main()
