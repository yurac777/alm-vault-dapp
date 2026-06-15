import os
import json
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
BASE_RPC = os.getenv("BASE_MAINNET_RPC")

def get_optimal_gas(w3):
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', 0)
    max_priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = int(base_fee * 1.15) + max_priority_fee
    return {'maxFeePerGas': max_fee_per_gas, 'maxPriorityFeePerGas': max_priority_fee}

def test_events():
    print("Интеграционное тестирование событий: отправка triggerEvent на Beacon...")
    w3 = Web3(Web3.HTTPProvider(BASE_RPC))
    if not w3.is_connected():
        print("Ошибка подключения к RPC")
        return

    # Чтение адреса задеплоенного маяка
    try:
        with open("beacon_address.txt", "r") as f:
            beacon_address = f.read().strip()
    except FileNotFoundError:
        print("Файл beacon_address.txt не найден. Задеплойте контракт сначала.")
        return

    # Чтение ABI
    ARTIFACT_PATH = "../contracts/out/ALM_Airdrop_Beacon.sol/ALM_Airdrop_Beacon.json"
    with open(ARTIFACT_PATH, "r") as f:
        artifact = json.load(f)
    abi = artifact["abi"]

    account = w3.eth.account.from_key(PRIVATE_KEY)
    beacon_contract = w3.eth.contract(address=w3.to_checksum_address(beacon_address), abi=abi)
    
    nonce = w3.eth.get_transaction_count(account.address)
    
    amount_to_claim = int(10 * 10**18) # Dummy amount

    for i in range(3):
        gas_params = get_optimal_gas(w3)
        print(f"Отправка транзакции {i+1}/3 на {beacon_address}...")
        try:
            tx = beacon_contract.functions.triggerEvent(account.address, amount_to_claim).build_transaction({
                'from': account.address,
                'nonce': nonce,
                **gas_params
            })
            signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"Transaction sent! Tx Hash: {tx_hash.hex()}")
            nonce += 1
            w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"Транзакция {i+1} успешно подтверждена.")
            time.sleep(2)
        except Exception as e:
            print(f"Ошибка при отправке: {e}")
            break

if __name__ == "__main__":
    test_events()
