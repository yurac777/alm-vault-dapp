import os, sys
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(dotenv_path="keeper/.env")

RPC_URL    = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")
VAULT      = os.getenv("VAULT_ADDRESS")
USDC       = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

w3 = Web3(Web3.HTTPProvider(RPC_URL))
usdc_contract = w3.eth.contract(address=w3.to_checksum_address(USDC), abi=[
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}
])
vault_contract = w3.eth.contract(address=w3.to_checksum_address(VAULT), abi=[
    {"inputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}], "name": "deposit", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"}
])

def main():
    wallet = w3.to_checksum_address(WALLET)
    vault = w3.to_checksum_address(VAULT)
    
    bal = usdc_contract.functions.balanceOf(wallet).call()
    print(f"Wallet USDC Balance: {bal / 1e6}")
    
    amount_to_deposit = int(5 * 1e6)
    if bal < amount_to_deposit:
        print(f"[ERROR] Insufficient USDC! Need 5.0, have {bal/1e6}. Please fund wallet.")
        sys.exit(1)
        
    print("Approving USDC...")
    nonce = w3.eth.get_transaction_count(wallet)
    gas_price = w3.eth.gas_price
    
    tx = usdc_contract.functions.approve(vault, amount_to_deposit).build_transaction({
        "from": wallet, "nonce": nonce, "gasPrice": gas_price, "chainId": 8453
    })
    signed = w3.eth.account.sign_transaction(tx, PRIV_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    print(f"Approve Tx Hash: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    
    print("Depositing...")
    nonce = w3.eth.get_transaction_count(wallet)
    tx2 = vault_contract.functions.deposit(amount_to_deposit, wallet).build_transaction({
        "from": wallet, "nonce": nonce, "gasPrice": gas_price, "chainId": 8453
    })
    tx2["gas"] = w3.eth.estimate_gas(tx2)
    signed2 = w3.eth.account.sign_transaction(tx2, PRIV_KEY)
    tx_hash2 = w3.eth.send_raw_transaction(signed2.rawTransaction)
    print(f"Deposit Tx Hash: {tx_hash2.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash2)
    print("Deposit complete!")

if __name__ == "__main__":
    main()
