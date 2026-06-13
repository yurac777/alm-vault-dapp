import os
import sys
import json
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL    = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")
VAULT      = os.getenv("VAULT_ADDRESS")

USDC       = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# ERC20 minimal ABI
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]

# Vault minimal ABI
VAULT_ABI = [
    {"inputs": [{"name": "assets", "type": "uint256"}, {"name": "receiver", "type": "address"}], "name": "deposit", "outputs": [{"name": "shares", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"}
]

def main():
    print("=== USDC Deposit to ALMVault ===")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("[CRITICAL] Cannot connect to RPC")
        sys.exit(1)

    deployer = w3.to_checksum_address(WALLET)
    vault_addr = w3.to_checksum_address(VAULT)
    print("Using Vault:", vault_addr)
    usdc_contract = w3.eth.contract(address=w3.to_checksum_address(USDC), abi=ERC20_ABI)
    vault_contract = w3.eth.contract(address=vault_addr, abi=VAULT_ABI)

    balance = usdc_contract.functions.balanceOf(deployer).call()
    print(f"Deployer USDC Balance: {balance / 1e6:.6f} USDC")

    if balance == 0:
        print("[INFO] No USDC to deposit. Exiting.")
        return

    nonce = w3.eth.get_transaction_count(deployer)
    gas_price = w3.eth.gas_price

    # 1. Approve
    allowance = usdc_contract.functions.allowance(deployer, vault_addr).call()
    if allowance < balance:
        print("Approving USDC...")
        approve_tx = usdc_contract.functions.approve(vault_addr, balance).build_transaction({
            "from": deployer,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": 8453
        })
        approve_tx["gas"] = int(w3.eth.estimate_gas(approve_tx) * 1.2)
        signed_approve = w3.eth.account.sign_transaction(approve_tx, PRIV_KEY)
        tx_hash_approve = w3.eth.send_raw_transaction(signed_approve.rawTransaction)
        print(f"Approve Tx Hash: {tx_hash_approve.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash_approve)
        nonce += 1
        print("Approval confirmed.")
    else:
        print("USDC already approved.")

    # 2. Deposit
    print(f"Depositing {balance / 1e6:.6f} USDC to Vault...")
    deposit_tx = vault_contract.functions.deposit(balance, deployer).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gasPrice": gas_price,
        "chainId": 8453
    })
    
    deposit_tx["gas"] = int(w3.eth.estimate_gas(deposit_tx) * 1.2)
    signed_deposit = w3.eth.account.sign_transaction(deposit_tx, PRIV_KEY)
    tx_hash_deposit = w3.eth.send_raw_transaction(signed_deposit.rawTransaction)
    print(f"Deposit Tx Hash: {tx_hash_deposit.hex()}")
    
    print("Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_deposit)
    if receipt.status == 1:
        print("[SUCCESS] Deposit successful!")
        print(f"Basescan: https://basescan.org/tx/{tx_hash_deposit.hex()}")
        
        # Save state to state_pnl.json
        state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_pnl.json")
        state = {}
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                pass
        
        import time
        deposit_usd = balance / 1e6
        state["initial_deposit_usd"] = state.get("initial_deposit_usd", 0.0) + deposit_usd
        state["deposit_timestamp"] = time.time()
        
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f)
        print(f"[STATE] Saved initial_deposit_usd = {state['initial_deposit_usd']} to {state_file}")
    else:
        print("[CRITICAL] Deposit failed!")

if __name__ == "__main__":
    main()
