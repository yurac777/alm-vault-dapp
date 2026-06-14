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
    print("Compiling ALMVaultV11.sol (viaIR=true) using forge...")
    subprocess.run(["contracts\\foundry_bin\\forge.exe", "build"], check=True, cwd="contracts")
    with open('contracts/out/ALMVaultV11.sol/ALMVaultV11.json', 'r') as f:
        data = json.load(f)
    os.makedirs('contracts/build', exist_ok=True)
    bytecode = data['bytecode']['object']
    if bytecode.startswith('0x'): bytecode = bytecode[2:]
    with open('contracts/build/ALMVaultV11.bin', 'w') as f: f.write(bytecode)
    with open('contracts/build/ALMVaultV11.abi', 'w') as f: json.dump(data['abi'], f)

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
    
    # Check if aUSDC needs to be withdrawn
    v10_ausdc = ausdc_contract.functions.balanceOf(V10_ADDRESS).call()
    if v10_ausdc > 0:
        # First rescue dust WETH to prevent Aave revert on debt repay!
        dust_weth = weth_contract.functions.balanceOf(V10_ADDRESS).call()
        if dust_weth > 0:
            print(f"Rescuing dust WETH: {dust_weth} to prevent rebalance revert...")
            tx = v10.functions.rescueFunds(WETH, dust_weth).build_transaction({
                'from': wallet, 'gas': 100000, 'gasPrice': w3.eth.gas_price
            })
            send_tx(tx, "Rescue Dust WETH")

        print(f"V10 has {v10_ausdc} aUSDC. Calling rebalance to withdraw all to free USDC.")
        data_bytes = bytearray(416)
        MAX_UINT256 = (1 << 256) - 1
        data_bytes[320:352] = int(v10_ausdc).to_bytes(32, byteorder='big')
        
        tx = v10.functions.rebalance(v10_ausdc, bytes(data_bytes)).build_transaction({
            'from': wallet, 'gas': 800000, 'gasPrice': w3.eth.gas_price
        })
        send_tx(tx, "Rebalance (Withdraw from Aave)")
        
    # Now V10 should have all capital in free USDC
    free_usdc = usdc_contract.functions.balanceOf(V10_ADDRESS).call()
    if free_usdc > 0:
        print(f"Rescuing {free_usdc} free USDC from V10...")
        tx = v10.functions.rescueFunds(USDC, free_usdc).build_transaction({
            'from': wallet, 'gas': 100000, 'gasPrice': w3.eth.gas_price
        })
        send_tx(tx, "Rescue USDC")

    usdc_balance = usdc_contract.functions.balanceOf(wallet).call()
    print(f"Total USDC ready for V11: {usdc_balance}")
    
    if usdc_balance == 0:
        print("No USDC available. Aborting.")
        return

    # Deploy V11
    print("\\nDeploying ALMVaultV11 to Base Mainnet...")
    with open("contracts/build/ALMVaultV11.bin", "r") as f: bytecode = f.read().strip()
    with open("contracts/build/ALMVaultV11.abi", "r") as f: abi = json.load(f)
    ALMVault = w3.eth.contract(abi=abi, bytecode=bytecode)
    constructor_tx = ALMVault.constructor(
        w3.to_checksum_address(USDC), w3.to_checksum_address(WETH), wallet,
        w3.to_checksum_address(AAVE), w3.to_checksum_address(NPM),
        w3.to_checksum_address(AAVE_DATA_PROVIDER), w3.to_checksum_address(AAVE_ORACLE)
    ).build_transaction({
        'from': wallet, 'gas': 5000000, 'gasPrice': int(w3.eth.gas_price * 1.1)
    })
    receipt = send_tx(constructor_tx, "Deploy V11")
    vault11_address = receipt.contractAddress
    print(f"\\n[SUCCESS] ALMVaultV11 deployed at: {vault11_address}")
    
    # Deposit into V11
    print(f"Approving {usdc_balance} USDC for V11...")
    tx = usdc_contract.functions.approve(vault11_address, usdc_balance).build_transaction({
        'from': wallet, 'gas': 100000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx, "Approve USDC")
    
    print("Depositing USDC into V11...")
    vault11 = w3.eth.contract(address=vault11_address, abi=abi)
    tx = vault11.functions.deposit(usdc_balance, wallet).build_transaction({
        'from': wallet, 'gas': 800000, 'gasPrice': w3.eth.gas_price
    })
    send_tx(tx, "Deposit V11")
    print(f"[SUCCESS] Migrated {usdc_balance} USDC to V11!")
        
    update_env(vault11_address)

def update_env(vault_address):
    env_path = "keeper/.env"
    with open(env_path, "r") as f: lines = f.readlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith("VAULT_ADDRESS="):
            lines[i] = f"VAULT_ADDRESS={vault_address}\n"
            found = True
            break
    if not found: lines.append(f"VAULT_ADDRESS={vault_address}\n")
    with open(env_path, "w") as f: f.writelines(lines)
    print(f"Updated {env_path} with new vault address.")
    
    frontend_path = "frontend/index.html"
    with open(frontend_path, "r", encoding="utf-8") as f: content = f.read()
    import re
    content = re.sub(r'const VAULT_ADDRESS = "0x[a-fA-F0-9]{40}";', f'const VAULT_ADDRESS = "{vault_address}";', content)
    with open(frontend_path, "w", encoding="utf-8") as f: f.write(content)
    print(f"Updated {frontend_path} with new vault address.")

if __name__ == "__main__":
    compile_contract()
    migrate()
