import os
import sys
import json
import subprocess
import requests
from web3 import Web3

sys.path.insert(0, 'keeper')
import config

# ── Addresses ──
USDC = config.USDC
WETH = config.WETH
AAVE = config.AAVE_POOL
NPM = config.UNI_V3_NPM
AAVE_DATA_PROVIDER = "0x2d8A3C5677189723C4cB8873CfC9C8976FDF38Ac"
AAVE_ORACLE = "0x51Ea49D2c76aB826fAEd18dc0c3C16fc29Cbd5d4"

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)

import subprocess

def compile_contract():
    print("Compiling ALMVault.sol (viaIR=true) using forge...")
    subprocess.run(["contracts\\foundry_bin\\forge.exe", "build"], check=True, cwd="contracts")
    
    with open('contracts/out/ALMVault.sol/ALMVault.json', 'r') as f:
        data = json.load(f)
        
    os.makedirs('contracts/build', exist_ok=True)
    with open('contracts/build/ALMVault.bin', 'w') as f:
        bytecode = data['bytecode']['object']
        if bytecode.startswith('0x'):
            bytecode = bytecode[2:]
        f.write(bytecode)
    with open('contracts/build/ALMVault.abi', 'w') as f:
        json.dump(data['abi'], f)

def deploy():
    print("\\nDeploying ALMVault to Base Mainnet...")
    with open("contracts/build/ALMVault.bin", "r") as f:
        bytecode = f.read().strip()
    with open("contracts/build/ALMVault.abi", "r") as f:
        abi = json.load(f)

    ALMVault = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    constructor_tx = ALMVault.constructor(
        w3.to_checksum_address(USDC),
        w3.to_checksum_address(WETH),
        wallet,
        w3.to_checksum_address(AAVE),
        w3.to_checksum_address(NPM),
        w3.to_checksum_address(AAVE_DATA_PROVIDER),
        w3.to_checksum_address(AAVE_ORACLE)
    ).build_transaction({
        'from': wallet,
        'nonce': w3.eth.get_transaction_count(wallet),
        'gas': 5000000,
        'gasPrice': w3.eth.gas_price
    })
    
    signed_tx = w3.eth.account.sign_transaction(constructor_tx, private_key=config.PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"Tx Hash: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    vault_address = receipt.contractAddress
    print(f"\\n[SUCCESS] ALMVault deployed at: {vault_address}")
    
    # Update config
    update_env(vault_address)
    
    return vault_address

def update_env(vault_address):
    env_path = "keeper/.env"
    with open(env_path, "r") as f:
        lines = f.readlines()
    
    found = False
    for i, line in enumerate(lines):
        if line.startswith("VAULT_ADDRESS="):
            lines[i] = f"VAULT_ADDRESS={vault_address}\\n"
            found = True
            break
            
    if not found:
        lines.append(f"VAULT_ADDRESS={vault_address}\\n")
        
    with open(env_path, "w") as f:
        f.writelines(lines)
    print(f"Updated {env_path} with new vault address.")

if __name__ == "__main__":
    compile_contract()
    deploy()
