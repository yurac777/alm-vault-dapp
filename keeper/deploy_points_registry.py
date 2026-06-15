import os
import json
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
BASE_RPC = os.getenv("BASE_MAINNET_RPC")

ARTIFACT_PATH = "../contracts/out/vALM_Points_Registry.sol/vALM_Points_Registry.json"

def get_optimal_gas(w3):
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', 0)
    max_priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = int(base_fee * 1.15) + max_priority_fee
    return {'maxFeePerGas': max_fee_per_gas, 'maxPriorityFeePerGas': max_priority_fee}

def deploy():
    print("Чтение артефакта vALM_Points_Registry...")
    with open(ARTIFACT_PATH, "r") as f:
        artifact = json.load(f)
    
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]["object"]

    w3 = Web3(Web3.HTTPProvider(BASE_RPC))
    if not w3.is_connected():
        print("Ошибка подключения к RPC")
        return

    account = w3.eth.account.from_key(PRIVATE_KEY)
    
    print(f"Деплой vALM_Points_Registry с кошелька {account.address}...")
    
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    gas_params = get_optimal_gas(w3)
    
    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.constructor().build_transaction({
        'from': account.address,
        'nonce': nonce,
        **gas_params
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    print(f"Транзакция деплоя отправлена! Tx Hash: {tx_hash.hex()}")
    print("Ожидание подтверждения...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    contract_address = receipt.contractAddress
    print(f"Контракт успешно развернут по адресу: {contract_address}")
    
    with open("points_registry_address.txt", "w") as f:
        f.write(contract_address)

if __name__ == "__main__":
    deploy()
