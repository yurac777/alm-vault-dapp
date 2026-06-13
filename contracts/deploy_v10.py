import sys
sys.path.insert(0, '../keeper')
import config
from web3 import Web3
import json

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY

USDC = w3.to_checksum_address(config.USDC)
WETH = w3.to_checksum_address(config.WETH)
AAVE_POOL = w3.to_checksum_address(config.AAVE_POOL)
NPM = w3.to_checksum_address('0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1')
AAVE_DATA_PROVIDER = w3.to_checksum_address("0x2d8A3C5677189723C4cB8873CfC9C8976FDF38Ac")
AAVE_ORACLE = w3.to_checksum_address("0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156")

with open('out/ALMVaultV10.sol/ALMVaultV10.json', 'r') as f:
    artifact = json.load(f)
    
abi = artifact['abi']
bytecode = artifact['bytecode']['object']

Vault = w3.eth.contract(abi=abi, bytecode=bytecode)

nonce = w3.eth.get_transaction_count(wallet)
print('Deploying ALMVaultV10...')

tx = Vault.constructor(USDC, WETH, wallet, AAVE_POOL, NPM, AAVE_DATA_PROVIDER, AAVE_ORACLE).build_transaction({
    'from': wallet,
    'nonce': nonce,
    'gas': 3000000,
    'gasPrice': w3.eth.gas_price
})

h = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, pk).rawTransaction)
r = w3.eth.wait_for_transaction_receipt(h)

print('Deployed V10 at:', r.contractAddress)

# Update config.py
with open('../keeper/config.py', 'r') as f:
    lines = f.readlines()
with open('../keeper/config.py', 'w') as f:
    for line in lines:
        if line.startswith('VAULT_ADDRESS'):
            f.write(f'VAULT_ADDRESS = "{r.contractAddress}"\n')
        else:
            f.write(line)
