import os, sys
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(dotenv_path="keeper/.env")

RPC_URL    = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")
VAULT      = os.getenv("VAULT_ADDRESS")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
vault_contract = w3.eth.contract(address=w3.to_checksum_address(VAULT), abi=[
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}], "name": "requestWithdrawal", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
])

def main():
    wallet = w3.to_checksum_address(WALLET)
    vault = w3.to_checksum_address(VAULT)
    
    shares = vault_contract.functions.balanceOf(wallet).call()
    print(f"Vault Shares Balance: {shares / 1e18}")
    
    if shares == 0:
        print("[ERROR] No shares to withdraw.")
        sys.exit(1)
        
    amount_to_request = shares // 2
    print(f"Requesting withdrawal for 50% shares: {amount_to_request / 1e18}")
    
    nonce = w3.eth.get_transaction_count(wallet)
    gas_price = w3.eth.gas_price
    
    tx = vault_contract.functions.requestWithdrawal(amount_to_request).build_transaction({
        "from": wallet, "nonce": nonce, "gasPrice": gas_price, "chainId": 8453
    })
    tx["gas"] = w3.eth.estimate_gas(tx)
    signed = w3.eth.account.sign_transaction(tx, PRIV_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    print(f"requestWithdrawal Tx Hash: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Withdrawal successfully requested and queued!")

if __name__ == "__main__":
    main()
