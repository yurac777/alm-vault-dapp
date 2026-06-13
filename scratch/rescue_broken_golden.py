import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY
vault_addr = w3.to_checksum_address(config.VAULT_ADDRESS)
vault = w3.eth.contract(address=vault_addr, abi=[
    {'inputs':[{'internalType':'uint256','name':'uniV3ValueUSD','type':'uint256'},{'internalType':'bytes','name':'data','type':'bytes'}],'name':'rebalance','outputs':[],'stateMutability':'nonpayable','type':'function'},
    {'inputs':[{'internalType':'address','name':'token','type':'address'},{'internalType':'uint256','name':'amount','type':'uint256'}],'name':'rescueFunds','outputs':[],'stateMutability':'nonpayable','type':'function'}
])

# Empty data with 0s to avoid triggering any new supply/borrow/mint, but we need the correct offsets!
# Offsets:
# 288: Aave repay WETH
# 320: Aave withdraw USDC
# 64: Aave supply USDC
# 0, 32, 96: Aave borrow WETH
# 192, 224: Uniswap mint

# Since we want to withdraw USDC (offset 320) and repay WETH (offset 288):
import struct
data = bytearray(416)
MAX_UINT = (2**256) - 1

# Offset 288 (repay weth): max
data[288:320] = MAX_UINT.to_bytes(32, 'big')
# Offset 320 (withdraw usdc): max
data[320:352] = MAX_UINT.to_bytes(32, 'big')

nonce = w3.eth.get_transaction_count(wallet)

print('Unwinding Vault via rebalance...')
tx = vault.functions.rebalance(0, data).build_transaction({'from':wallet, 'nonce':nonce, 'gas':1000000, 'gasPrice':w3.eth.gas_price})
h = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, pk).rawTransaction)
r = w3.eth.wait_for_transaction_receipt(h)
print('Unwind status:', r.status)

USDC = w3.to_checksum_address(config.USDC)
WETH = w3.to_checksum_address(config.WETH)
aUSDC = w3.to_checksum_address('0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB')
usdc_contract = w3.eth.contract(address=USDC, abi=[{'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}])
weth_contract = w3.eth.contract(address=WETH, abi=[{'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}])

nonce += 1
bal_usdc = usdc_contract.functions.balanceOf(vault_addr).call()
if bal_usdc > 0:
    print('Sweeping USDC:', bal_usdc)
    tx2 = vault.functions.rescueFunds(USDC, bal_usdc).build_transaction({'from':wallet, 'nonce':nonce, 'gas':100000, 'gasPrice':w3.eth.gas_price})
    w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx2, pk).rawTransaction)
    nonce += 1
    
bal_weth = weth_contract.functions.balanceOf(vault_addr).call()
if bal_weth > 0:
    print('Sweeping WETH:', bal_weth)
    tx3 = vault.functions.rescueFunds(WETH, bal_weth).build_transaction({'from':wallet, 'nonce':nonce, 'gas':100000, 'gasPrice':w3.eth.gas_price})
    w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx3, pk).rawTransaction)
    
print('Recovery Complete! Wallet USDC:', usdc_contract.functions.balanceOf(wallet).call())
