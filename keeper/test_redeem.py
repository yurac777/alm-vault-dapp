import os
import sys
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv('.env')
RPC_URL    = os.getenv("BASE_MAINNET_RPC")
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")
VAULT      = os.getenv("VAULT_ADDRESS")
USDC       = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Minimal ABIs
ERC20_ABI = [
    {"inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]
VAULT_ABI = [
    {"inputs": [{"name": "shares", "type": "uint256"}, {"name": "receiver", "type": "address"}, {"name": "owner", "type": "address"}], "name": "redeem", "outputs": [{"name": "assets", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
]

def main():
    print("=== LIVE FIRE TEST: REDEEM (10% SHARES) ===")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("[CRITICAL] Cannot connect to RPC")
        sys.exit(1)

    deployer = w3.to_checksum_address(WALLET)
    vault_addr = w3.to_checksum_address(VAULT)
    usdc_contract = w3.eth.contract(address=w3.to_checksum_address(USDC), abi=ERC20_ABI)
    vault_contract = w3.eth.contract(address=vault_addr, abi=VAULT_ABI)

    usdc_before = usdc_contract.functions.balanceOf(deployer).call()
    shares_balance = vault_contract.functions.balanceOf(deployer).call()
    
    print(f"Deployer shares (almUSD): {shares_balance / 1e18:.6f}")
    print(f"Deployer USDC before  : {usdc_before / 1e6:.6f}")

    if shares_balance == 0:
        print("[ERROR] No shares to redeem!")
        return

    shares_to_burn = shares_balance // 10
    print(f"Burning 10% of shares: {shares_to_burn / 1e18:.6f} almUSD...")

    nonce = w3.eth.get_transaction_count(deployer)
    gas_price = w3.eth.gas_price

    redeem_tx = vault_contract.functions.redeem(shares_to_burn, deployer, deployer).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "maxFeePerGas": int(gas_price * 1.5),
        "maxPriorityFeePerGas": int(gas_price),
        "chainId": 8453
    })
    
    gas_est = w3.eth.estimate_gas(redeem_tx)
    redeem_tx["gas"] = int(gas_est * 1.2)
    
    signed_tx = w3.eth.account.sign_transaction(redeem_tx, PRIV_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    
    print(f"Redeem Tx Sent: {tx_hash.hex()}")
    print("Waiting for confirmation...")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        print("[SUCCESS] Redeem confirmed!")
        usdc_after = usdc_contract.functions.balanceOf(deployer).call()
        withdrawn = (usdc_after - usdc_before) / 1e6
        print(f"USDC Withdrawn: {withdrawn:.6f}")
        print(f"Deployer USDC after   : {usdc_after / 1e6:.6f}")
        print(f"Basescan: https://basescan.org/tx/{tx_hash.hex()}")
    else:
        print("[CRITICAL] Redeem TX Reverted!")

if __name__ == "__main__":
    main()
