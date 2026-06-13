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
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}], "name": "withdrawalRequests", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}, {"internalType": "address", "name": "owner", "type": "address"}], "name": "redeem", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"}
])

def main():
    wallet = w3.to_checksum_address(WALLET)
    vault = w3.to_checksum_address(VAULT)
    
    pending_shares = vault_contract.functions.withdrawalRequests(wallet).call()
    print(f"Pending requested shares: {pending_shares / 1e18}")
    
    if pending_shares == 0:
        print("[ERROR] No pending requested shares to redeem.")
        sys.exit(1)
        
    nonce = w3.eth.get_transaction_count(wallet)
    gas_price = w3.eth.gas_price
    
    print("Redeeming queued shares...")
    tx = vault_contract.functions.redeem(pending_shares, wallet, wallet).build_transaction({
        "from": wallet, "nonce": nonce, "gasPrice": gas_price, "chainId": 8453
    })
    tx["gas"] = w3.eth.estimate_gas(tx)
    signed = w3.eth.account.sign_transaction(tx, PRIV_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    print(f"Redeem Tx Hash: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Successfully redeemed USDC from Vault!")

if __name__ == "__main__":
    main()
