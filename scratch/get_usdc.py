import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY

WETH = w3.to_checksum_address(config.WETH)
USDC = w3.to_checksum_address(config.USDC)
pool = w3.eth.contract(address=w3.to_checksum_address(config.AAVE_POOL), abi=[
    {'inputs':[{'internalType':'address','name':'asset','type':'address'},{'internalType':'uint256','name':'amount','type':'uint256'},{'internalType':'address','name':'onBehalfOf','type':'address'},{'internalType':'uint16','name':'referralCode','type':'uint16'}],'name':'supply','outputs':[],'stateMutability':'nonpayable','type':'function'},
    {'inputs':[{'internalType':'address','name':'asset','type':'address'},{'internalType':'uint256','name':'amount','type':'uint256'},{'internalType':'uint256','name':'interestRateMode','type':'uint256'},{'internalType':'uint16','name':'referralCode','type':'uint16'},{'internalType':'address','name':'onBehalfOf','type':'address'}],'name':'borrow','outputs':[],'stateMutability':'nonpayable','type':'function'}
])
weth = w3.eth.contract(address=WETH, abi=[
    {'inputs':[],'name':'deposit','outputs':[],'stateMutability':'payable','type':'function'},
    {'constant':False,'inputs':[{'name':'','type':'address'},{'name':'','type':'uint256'}],'name':'approve','outputs':[{'name':'','type':'bool'}],'type':'function'},
    {'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}
])

nonce = w3.eth.get_transaction_count(wallet)
print('Wrapping ETH to WETH...')
tx = weth.functions.deposit().build_transaction({'from':wallet, 'nonce':nonce, 'gas':100000, 'gasPrice':w3.eth.gas_price, 'value':int(0.0003 * 10**18)})
w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, pk).rawTransaction)
nonce += 1
time.sleep(3)

print('Approving Aave...')
tx2 = weth.functions.approve(config.AAVE_POOL, int(0.0003 * 10**18)).build_transaction({'from':wallet, 'nonce':nonce, 'gas':100000, 'gasPrice':w3.eth.gas_price})
w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx2, pk).rawTransaction)
nonce += 1
time.sleep(3)

print('Supplying WETH to Aave...')
tx3 = pool.functions.supply(WETH, int(0.0003 * 10**18), wallet, 0).build_transaction({'from':wallet, 'nonce':nonce, 'gas':300000, 'gasPrice':w3.eth.gas_price})
w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx3, pk).rawTransaction)
nonce += 1
time.sleep(3)

print('Borrowing 1 USDC from Aave...')
tx4 = pool.functions.borrow(USDC, 1000000, 2, 0, wallet).build_transaction({'from':wallet, 'nonce':nonce, 'gas':500000, 'gasPrice':w3.eth.gas_price})
w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx4, pk).rawTransaction))

usdc_contract = w3.eth.contract(address=USDC, abi=[{'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}])
print('Wallet USDC:', usdc_contract.functions.balanceOf(wallet).call())
