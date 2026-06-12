import os
import sys
import time
from dotenv import load_dotenv
from web3 import Web3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keeper.core.encoder import encode_rebalance_payload_v3
from keeper.connectors.base_rpc import BaseConnector

def main():
    print("=== 🚨 EMERGENCY UNWIND 🚨 ===")
    
    load_dotenv()
    rpc_url = os.getenv("BASE_MAINNET_RPC")
    private_key = os.getenv("PRIVATE_KEY")
    wallet_address = os.getenv("WALLET_ADDRESS")
    vault_address = os.getenv("VAULT_ADDRESS")
    
    if not all([rpc_url, private_key, wallet_address, vault_address]):
        print("Ошибка: Отсутствуют необходимые переменные в .env")
        return
        
    connector = BaseConnector(rpc_url)
    w3 = connector.w3
    
    while not connector.is_connected():
        print("Ошибка: Не удалось подключиться к Base Mainnet. Переключение на резервный RPC...")
        connector.rotate_rpc()
        w3 = connector.w3
        time.sleep(2)
        
    print(f"Успешное подключение! Последний блок: {connector.get_latest_block_number()}")
        
    wallet = w3.to_checksum_address(wallet_address)
    vault = w3.to_checksum_address(vault_address)
    
    VAULT_ABI = [
        {"inputs": [{"internalType": "bytes", "name": "data", "type": "bytes"}], "name": "rebalance", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
        {"inputs": [], "name": "currentLiquidity", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "currentTickLower", "outputs": [{"internalType": "int24", "name": "", "type": "int24"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "currentTickUpper", "outputs": [{"internalType": "int24", "name": "", "type": "int24"}], "stateMutability": "view", "type": "function"},
        {"inputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}, {"internalType": "address", "name": "owner", "type": "address"}], "name": "withdraw", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
        {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
        {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}], "name": "maxWithdraw", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
    ]
    
    vault_contract = w3.eth.contract(address=vault, abi=VAULT_ABI)
    
    current_liquidity = vault_contract.functions.currentLiquidity().call()
    current_liquidity = vault_contract.functions.currentLiquidity().call()
    
    print(f"Текущая ликвидность: {current_liquidity}")
    if current_liquidity == 0:
        print("Позиция уже закрыта. Ликвидность = 0.")
    
    MAX_UINT256 = (2**256) - 1
    
    payload = encode_rebalance_payload_v3(
        isRebalance=False,
        aaveDebtAdjustment=0,
        amountUSDC=0,
        amountWETHToBorrow=0,
        newTickLower=0,
        newTickUpper=0,
        amount0Desired=0,
        amount1Desired=0,
        poolFee=500,
        amountWETHToRepay=MAX_UINT256,
        amountUSDCToWithdraw=MAX_UINT256
    )
    
    print("Отправка Rebalance(Emergency)...")
    nonce = w3.eth.get_transaction_count(wallet, 'pending')
    gas_params = connector.get_optimal_gas_fee()
    
    tx = vault_contract.functions.rebalance(payload).build_transaction({
        'from': wallet,
        'nonce': nonce,
        'maxFeePerGas': gas_params['maxFeePerGas'],
        'maxPriorityFeePerGas': gas_params['maxPriorityFeePerGas'],
    })
    
    gas_est = w3.eth.estimate_gas(tx)
    tx['gas'] = int(gas_est * 1.2)
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Tx Hash: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Emergency Rebalance подтвержден! Позиция закрыта.")
    
    # 2. Withdraw ERC4626
    shares = vault_contract.functions.balanceOf(wallet).call()
    assets = vault_contract.functions.maxWithdraw(wallet).call()
    print(f"Выводим {assets / 10**6} USDC из Vault...")
    
    nonce = w3.eth.get_transaction_count(wallet, 'pending')
    withdraw_tx = vault_contract.functions.withdraw(assets, wallet, wallet).build_transaction({
        'from': wallet,
        'nonce': nonce,
        'maxFeePerGas': gas_params['maxFeePerGas'],
        'maxPriorityFeePerGas': gas_params['maxPriorityFeePerGas'],
    })
    
    gas_est = w3.eth.estimate_gas(withdraw_tx)
    withdraw_tx['gas'] = int(gas_est * 1.2)
    signed_withdraw = w3.eth.account.sign_transaction(withdraw_tx, private_key)
    tx_hash_withdraw = w3.eth.send_raw_transaction(signed_withdraw.raw_transaction)
    print(f"Withdraw Tx Hash: {tx_hash_withdraw.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash_withdraw)
    print("Успех! Все средства вернулись на кошелек.")

if __name__ == "__main__":
    main()
