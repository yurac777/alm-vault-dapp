import os
import sys
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL    = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")
VAULT      = os.getenv("VAULT_ADDRESS")
USDC       = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

VAULT_ABI = [
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}, {"internalType": "address", "name": "owner", "type": "address"}], "name": "redeem", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"}
]

ERC20_ABI = [
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
]

def main():
    print("=== Rescue Operation: ERC4626 Redeem ===")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("[CRITICAL] Cannot connect to RPC")
        sys.exit(1)

    deployer = w3.to_checksum_address(WALLET)
    vault_addr = w3.to_checksum_address(VAULT)
    usdc_addr = w3.to_checksum_address(USDC)
    
    vault_contract = w3.eth.contract(address=vault_addr, abi=VAULT_ABI)
    usdc_contract = w3.eth.contract(address=usdc_addr, abi=ERC20_ABI)

    shares = vault_contract.functions.balanceOf(deployer).call()
    print(f"ALMv Shares on Deployer: {shares}")
    
    if shares == 0:
        print("[CRITICAL] No ALMv shares to redeem. Funds might already be rescued.")
        sys.exit(1)

    nonce = w3.eth.get_transaction_count(deployer)
    gas_price = w3.eth.gas_price

    print(f"Redeeming {shares} shares from Vault...")
    tx = vault_contract.functions.redeem(shares, deployer, deployer).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gasPrice": gas_price,
        "chainId": 8453
    })
    
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.3)
    signed_tx = w3.eth.account.sign_transaction(tx, PRIV_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Redeem Tx Hash: {tx_hash.hex()}")
    
    print("Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        print("[SUCCESS] Shares redeemed successfully!")
        
        # Check USDC balance
        usdc_balance = usdc_contract.functions.balanceOf(deployer).call()
        print(f"[STATUS] Hot Wallet USDC Balance: {usdc_balance / 1e6:.6f} USDC")
        
        vault_usdc_balance = usdc_contract.functions.balanceOf(vault_addr).call()
        print(f"[STATUS] Vault USDC Balance: {vault_usdc_balance / 1e6:.6f} USDC")
    else:
        print("[CRITICAL] Failed to redeem shares.")

if __name__ == "__main__":
    main()
