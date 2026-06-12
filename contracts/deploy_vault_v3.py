"""
deploy_vault_v3.py -- Deploys ALMVaultV3 to Base Mainnet via Python/Web3.
"""
import json
import os
import sys
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(dotenv_path="../keeper/.env")

RPC_URL    = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")

USDC    = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH    = "0x4200000000000000000000000000000000000006"
OWNER   = WALLET
AAVE    = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
NPM     = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"

ARTIFACT = os.path.join(os.path.dirname(__file__), "out", "ALMVaultV3.sol", "ALMVaultV3.json")

def main():
    print("=== ALMVaultV3 Deploy (Python/Web3) ===")

    # 1. Connect
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        print(f"[CRITICAL] Cannot connect to {RPC_URL}")
        sys.exit(1)
    block = w3.eth.block_number
    print(f"Connected to Base Mainnet. Block: {block}")

    # 2. Load compiled artifact
    with open(ARTIFACT) as f:
        artifact = json.load(f)
    bytecode = artifact["bytecode"]["object"]
    abi = artifact["abi"]

    # 3. Build deploy tx
    deployer = w3.to_checksum_address(WALLET)
    balance_eth = w3.eth.get_balance(deployer) / 1e18
    print(f"Deployer: {deployer}")
    print(f"Balance:  {balance_eth:.8f} ETH")

    if balance_eth < 0.0001:
        print("[CRITICAL] Insufficient ETH for deployment gas!")
        sys.exit(1)

    nonce = w3.eth.get_transaction_count(deployer)
    gas_price = w3.eth.gas_price
    print(f"Gas price: {gas_price / 1e9:.4f} gwei | Nonce: {nonce}")

    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    GAS_LIMIT = 3_500_000
    cost_eth = GAS_LIMIT * gas_price / 1e18
    print(f"Gas limit (pre-set): {GAS_LIMIT} | Estimated cost: {cost_eth:.8f} ETH")

    constructor_tx = Contract.constructor(
        w3.to_checksum_address(USDC),
        w3.to_checksum_address(WETH),
        w3.to_checksum_address(OWNER),
        w3.to_checksum_address(AAVE),
        w3.to_checksum_address(NPM),
    ).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gasPrice": gas_price,
        "gas": GAS_LIMIT,
        "chainId": 8453,  # Base Mainnet
    })

    # 5. Sign & send
    signed = w3.eth.account.sign_transaction(constructor_tx, PRIV_KEY)
    print("\nSending deployment transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Tx Hash: {tx_hash.hex()}")
    print(f"Track on Basescan: https://basescan.org/tx/{tx_hash.hex()}")

    # 6. Wait for receipt
    print("Waiting for confirmation (up to 120s)...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt.status == 1:
        vault_address = receipt.contractAddress
        print(f"\n[SUCCESS] ALMVaultV3 deployed at: {vault_address}")

        # 7. Save to .env
        env_path = "../keeper/.env"
        with open(env_path, "r") as f:
            env_content = f.read()
        
        # Replace or add VAULT_ADDRESS
        if "VAULT_ADDRESS=" in env_content:
            old_vault = os.getenv('VAULT_ADDRESS', '')
            if old_vault:
                env_content = env_content.replace(f"VAULT_ADDRESS={old_vault}", f"VAULT_ADDRESS={vault_address}")
            else:
                lines = []
                for line in env_content.split('\n'):
                    if line.startswith("VAULT_ADDRESS="):
                        lines.append(f"VAULT_ADDRESS={vault_address}")
                    else:
                        lines.append(line)
                env_content = '\n'.join(lines)
        else:
            env_content += f"\nVAULT_ADDRESS={vault_address}\n"
            
        with open(env_path, "w") as f:
            f.write(env_content)
        print(f".env updated: VAULT_ADDRESS={vault_address}")
    else:
        print(f"[CRITICAL] Transaction REVERTED! Receipt: {receipt}")
        sys.exit(1)

if __name__ == "__main__":
    main()
