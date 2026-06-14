import sys
import json
import os
import subprocess
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
V10_ADDRESS = config.VAULT_ADDRESS
AUSDC_ADDRESS = "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB"

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
current_nonce = w3.eth.get_transaction_count(wallet, 'pending')

def send_tx(tx_dict, name):
    global current_nonce
    tx_dict['nonce'] = current_nonce
    signed_tx = w3.eth.account.sign_transaction(tx_dict, private_key=config.PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"{name} Tx Hash: {tx_hash.hex()}")
    current_nonce += 1
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise Exception(f"Transaction {name} failed!")
    return receipt

def compile_contract():
    pass

def migrate():
    print(f"Loading V10 Vault at {V10_ADDRESS}")
    with open('contracts/out/ALMVaultV10.sol/ALMVaultV10.json', 'r') as f:
        v10_data = json.load(f)
    v10 = w3.eth.contract(address=w3.to_checksum_address(V10_ADDRESS), abi=v10_data['abi'])
    
    ERC20_ABI = [
        {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
        {"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"}
    ]
    ausdc_contract = w3.eth.contract(address=w3.to_checksum_address(AUSDC_ADDRESS), abi=ERC20_ABI)
    usdc_contract = w3.eth.contract(address=w3.to_checksum_address(USDC), abi=ERC20_ABI)
    weth_contract = w3.eth.contract(address=w3.to_checksum_address(WETH), abi=ERC20_ABI)
    
    # 1. Withdraw aUSDC from Aave via rebalance
    v10_ausdc = ausdc_contract.functions.balanceOf(V10_ADDRESS).call()
    if v10_ausdc > 0:
        print(f"V10 has {v10_ausdc} aUSDC. Withdrawing to USDC via rebalance...")
        data_bytes = bytearray(416)
        MAX_UINT = (1 << 256) - 1
        data_bytes[320:352] = MAX_UINT.to_bytes(32, byteorder='big')
        
        tx = v10.functions.rebalance(0, bytes(data_bytes)).build_transaction({
            'from': wallet, 'gas': 400000, 'gasPrice': w3.eth.gas_price
        })
        send_tx(tx, "Rebalance Workaround (Withdraw aUSDC)")
        
    # 2. Rescue all WETH from vault
    v10_weth = weth_contract.functions.balanceOf(V10_ADDRESS).call()
    if v10_weth > 0:
        print(f"Rescuing {v10_weth} WETH from V10...")
        tx = v10.functions.rescueFunds(WETH, v10_weth).build_transaction({
            'from': wallet, 'gas': 100000, 'gasPrice': w3.eth.gas_price
        })
        send_tx(tx, "Rescue WETH")
        
    # 3. Rescue all USDC from vault
    v10_usdc = usdc_contract.functions.balanceOf(V10_ADDRESS).call()
    if v10_usdc > 0:
        print(f"Rescuing {v10_usdc} USDC from V10...")
        tx = v10.functions.rescueFunds(USDC, v10_usdc).build_transaction({
            'from': wallet, 'gas': 100000, 'gasPrice': w3.eth.gas_price
        })
        send_tx(tx, "Rescue USDC")

    usdc_balance = usdc_contract.functions.balanceOf(wallet).call()
    print(f"Total USDC ready for Singularity: {usdc_balance}")
    
    if usdc_balance == 0:
        print("No USDC available. Aborting.")
        return

    # 4. Deploy ALMVault_Singularity
    print("\\nDeploying ALMVault_Singularity to Base Mainnet...")
    with open("contracts/build/ALMVault_Singularity.bin", "r") as f: vault_bc = f.read().strip()
    with open("contracts/build/ALMVault_Singularity.abi", "r") as f: vault_abi = json.load(f)
    ALMVault = w3.eth.contract(abi=vault_abi, bytecode=vault_bc)
    
    vault_constructor_tx = ALMVault.constructor(
        w3.to_checksum_address(USDC), w3.to_checksum_address(WETH), wallet,
        w3.to_checksum_address(AAVE), w3.to_checksum_address(NPM),
        w3.to_checksum_address(AAVE_DATA_PROVIDER), w3.to_checksum_address(AAVE_ORACLE)
    ).build_transaction({
        'from': wallet, 'gas': 6000000, 'gasPrice': int(w3.eth.gas_price * 1.1)
    })
    vault_receipt = send_tx(vault_constructor_tx, "Deploy ALMVault_Singularity")
    vault_address = vault_receipt.contractAddress
    print(f"[SUCCESS] ALMVault_Singularity deployed at: {vault_address}")
    
    # 5. Deploy ALMZapper
    print("\\nDeploying ALMZapper to Base Mainnet...")
    with open("contracts/build/ALMZapper.bin", "r") as f: zap_bc = f.read().strip()
    with open("contracts/build/ALMZapper.abi", "r") as f: zap_abi = json.load(f)
    ALMZapper = w3.eth.contract(abi=zap_abi, bytecode=zap_bc)
    
    zap_constructor_tx = ALMZapper.constructor(
        w3.to_checksum_address(USDC), vault_address, wallet
    ).build_transaction({
        'from': wallet, 'gas': 2000000, 'gasPrice': int(w3.eth.gas_price * 1.1)
    })
    zap_receipt = send_tx(zap_constructor_tx, "Deploy ALMZapper")
    zap_address = zap_receipt.contractAddress
    print(f"[SUCCESS] ALMZapper deployed at: {zap_address}")

    # Set keeper
    vault = w3.eth.contract(address=vault_address, abi=vault_abi)
    tx = vault.functions.setKeeper(wallet).build_transaction({
        'from': wallet, 'gas': 100000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx, "Set Keeper")
    
    # Deposit into Singularity
    print(f"Approving {usdc_balance} USDC for Singularity Vault...")
    tx = usdc_contract.functions.approve(vault_address, usdc_balance).build_transaction({
        'from': wallet, 'gas': 100000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx, "Approve USDC")
    
    print("Depositing USDC into Singularity Vault...")
    tx = vault.functions.depositWithReferrer(usdc_balance, wallet, "0x0000000000000000000000000000000000000000").build_transaction({
        'from': wallet, 'gas': 800000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx, "Deposit Singularity")
    print(f"[SUCCESS] Migrated {usdc_balance} USDC to Singularity Vault!")
        
    update_env(vault_address, zap_address)

def update_env(vault_address, zapper_address):
    env_path = "keeper/.env"
    with open(env_path, "r") as f: lines = f.readlines()
    vault_found = False
    zap_found = False
    for i, line in enumerate(lines):
        if line.startswith("VAULT_ADDRESS="):
            lines[i] = f"VAULT_ADDRESS={vault_address}\n"
            vault_found = True
        elif line.startswith("ZAPPER_ADDRESS="):
            lines[i] = f"ZAPPER_ADDRESS={zapper_address}\n"
            zap_found = True
            
    if not vault_found: lines.append(f"VAULT_ADDRESS={vault_address}\n")
    if not zap_found: lines.append(f"ZAPPER_ADDRESS={zapper_address}\n")
    
    with open(env_path, "w") as f: f.writelines(lines)
    print(f"Updated {env_path} with new vault and zapper addresses.")

if __name__ == "__main__":
    compile_contract()
    migrate()
