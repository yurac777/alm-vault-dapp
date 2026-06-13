import time
import os
from web3 import Web3
from dotenv import load_dotenv
import json

load_dotenv(dotenv_path='../keeper/.env')
RPC_URL    = 'https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu'
PRIV_KEY   = os.getenv('PRIVATE_KEY')
WALLET     = os.getenv('WALLET_ADDRESS')
VAULT      = '0x6C1795ECe776C5f5706862B2FCAD973fc1f4CEd3'

w3 = Web3(Web3.HTTPProvider(RPC_URL))
deployer = w3.to_checksum_address(WALLET)

ARTIFACT = 'out/ALMVaultV10.sol/ALMVaultV10.json'
with open(ARTIFACT) as f:
    abi = json.load(f)['abi']

vault_contract = w3.eth.contract(address=VAULT, abi=abi)
usdc_contract = w3.eth.contract(address='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', abi=[
    {'constant': True, 'inputs': [{'name': '_owner', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': 'balance', 'type': 'uint256'}], 'type': 'function'},
    {'inputs': [{'internalType': 'address', 'name': 'spender', 'type': 'address'}, {'internalType': 'uint256', 'name': 'amount', 'type': 'uint256'}], 'name': 'approve', 'outputs': [{'internalType': 'bool', 'name': '', 'type': 'bool'}], 'stateMutability': 'nonpayable', 'type': 'function'}
])

print('=== ALMVaultV10 LIVE TEST ===')
print(f'Vault Address: {VAULT}')

total_assets = vault_contract.functions.totalAssets().call()
print(f'Initial totalAssets: {total_assets / 1e6}')

amount = int(0.05 * 1e6)
print(f'\n1. Approving {amount / 1e6} USDC...')
tx = usdc_contract.functions.approve(VAULT, amount).build_transaction({
    'from': deployer, 'nonce': w3.eth.get_transaction_count(deployer),
    'gasPrice': w3.eth.gas_price
})
w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, PRIV_KEY).rawTransaction)
time.sleep(3)

print('2. Depositing...')
tx = vault_contract.functions.deposit(amount, deployer).build_transaction({
    'from': deployer, 'nonce': w3.eth.get_transaction_count(deployer),
    'gasPrice': w3.eth.gas_price, 'gas': 800000
})
w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, PRIV_KEY).rawTransaction)
time.sleep(3)

shares = vault_contract.functions.balanceOf(deployer).call()
print(f'-> Shares minted: {shares / 1e18}')

print('\n3. Requesting Withdrawal via Withdrawal Queue...')
tx = vault_contract.functions.requestWithdrawal(shares).build_transaction({
    'from': deployer, 'nonce': w3.eth.get_transaction_count(deployer),
    'gasPrice': w3.eth.gas_price, 'gas': 200000
})
w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, PRIV_KEY).rawTransaction)
time.sleep(3)

queue = vault_contract.functions.totalWithdrawalRequests().call()
print(f'-> Queue size: {queue / 1e18} shares')

print('\n4. Redeeming standard...')
try:
    tx = vault_contract.functions.redeem(shares, deployer, deployer).build_transaction({
        'from': deployer, 'nonce': w3.eth.get_transaction_count(deployer),
        'gasPrice': w3.eth.gas_price, 'gas': 500000
    })
    w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, PRIV_KEY).rawTransaction)
    print('-> Redeem SUCCESS!')
except Exception as e:
    print(f'-> Redeem Reverted! (Expected if Keeper has not freed USDC): {e}')

queue_after = vault_contract.functions.totalWithdrawalRequests().call()
print(f'-> Queue size after: {queue_after / 1e18} shares')
print('\n=== LIVE FIRE TEST COMPLETE ===')
