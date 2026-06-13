import os
import sys
import time
from web3 import Web3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keeper import config

def main():
    w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
    if not w3.is_connected():
        print("Failed to connect")
        return

    wallet = w3.to_checksum_address(config.WALLET)
    pk = config.PRIVATE_KEY
    
    old_vault_addr = w3.to_checksum_address("0x87eE1eCa84E9308946eEcba998625272A6ED9a00")
    new_vault_addr = w3.to_checksum_address("0x6B2Ec85Fb2c4CE051B71804e20aD8F2c03DADcB4")
    
    erc4626_abi = [
        {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
        {"inputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}, {"internalType": "address", "name": "owner", "type": "address"}], "name": "redeem", "outputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
        {"inputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}], "name": "deposit", "outputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
        {"inputs": [], "name": "asset", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"}
    ]
    
    erc20_abi = [
        {"inputs": [{"internalType": "address", "name": "spender", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
        {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
    ]
    
    old_vault = w3.eth.contract(address=old_vault_addr, abi=erc4626_abi)
    new_vault = w3.eth.contract(address=new_vault_addr, abi=erc4626_abi)
    usdc_addr = old_vault.functions.asset().call()
    usdc = w3.eth.contract(address=usdc_addr, abi=erc20_abi)
    
    # 1. Check old shares
    shares = old_vault.functions.balanceOf(wallet).call()
    print(f"Old Vault shares: {shares}")
    
    if shares > 0:
        print("Redeeming shares from old vault...")
        nonce = w3.eth.get_transaction_count(wallet, "pending")
        tx = old_vault.functions.redeem(shares, wallet, wallet).build_transaction({
            "from": wallet,
            "nonce": nonce,
            "gasPrice": w3.eth.gas_price,
            "gas": 3000000,
            "chainId": 8453
        })
        signed = w3.eth.account.sign_transaction(tx, pk)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        print(f"Redeem Tx: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print("Redeem successful.")
    
    # 2. Deposit to new vault
    usdc_bal = usdc.functions.balanceOf(wallet).call()
    print(f"USDC Balance: {usdc_bal / 1e6}")
    
    if usdc_bal > 0:
        print("Approving USDC for new vault...")
        nonce = w3.eth.get_transaction_count(wallet, "pending")
        tx = usdc.functions.approve(new_vault_addr, usdc_bal).build_transaction({
            "from": wallet,
            "nonce": nonce,
            "gasPrice": w3.eth.gas_price,
            "gas": 3000000,
            "chainId": 8453
        })
        signed = w3.eth.account.sign_transaction(tx, pk)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        print(f"Depositing {usdc_bal} USDC to new vault...")
        nonce = w3.eth.get_transaction_count(wallet, "pending")
        tx = new_vault.functions.deposit(usdc_bal, wallet).build_transaction({
            "from": wallet,
            "nonce": nonce,
            "gasPrice": w3.eth.gas_price,
            "gas": 3000000,
            "chainId": 8453
        })
        signed = w3.eth.account.sign_transaction(tx, pk)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        print(f"Deposit Tx: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print("Deposit successful.")

if __name__ == "__main__":
    main()
