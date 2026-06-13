import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY

AAVE_POOL = w3.to_checksum_address(config.AAVE_POOL)
WETH = w3.to_checksum_address(config.WETH)
USDC = w3.to_checksum_address(config.USDC)
aWETH = w3.to_checksum_address('0xD4a0e0b9149BCee3C920d2E00b5dE09138fd8bb7')

aweth_contract = w3.eth.contract(address=aWETH, abi=[
    {'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}
])

usdc_contract = w3.eth.contract(address=USDC, abi=[
    {'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'},
    {'constant':False,'inputs':[{'name':'','type':'address'},{'name':'','type':'uint256'}],'name':'approve','outputs':[{'name':'','type':'bool'}],'type':'function'}
])

pool = w3.eth.contract(address=AAVE_POOL, abi=[
    {'inputs':[{'internalType':'address','name':'asset','type':'address'},{'internalType':'uint256','name':'amount','type':'uint256'},{'internalType':'uint256','name':'rateMode','type':'uint256'},{'internalType':'address','name':'onBehalfOf','type':'address'}],'name':'repay','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'nonpayable','type':'function'},
    {'inputs':[{'internalType':'address','name':'asset','type':'address'},{'internalType':'uint256','name':'amount','type':'uint256'},{'internalType':'address','name':'to','type':'address'}],'name':'withdraw','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'nonpayable','type':'function'},
    {'inputs':[{'internalType':'address','name':'user','type':'address'}],'name':'getUserAccountData','outputs':[{'internalType':'uint256','name':'totalCollateralBase','type':'uint256'},{'internalType':'uint256','name':'totalDebtBase','type':'uint256'},{'internalType':'uint256','name':'availableBorrowsBase','type':'uint256'},{'internalType':'uint256','name':'currentLiquidationThreshold','type':'uint256'},{'internalType':'uint256','name':'ltv','type':'uint256'},{'internalType':'uint256','name':'healthFactor','type':'uint256'}],'stateMutability':'view','type':'function'}
])

nonce = w3.eth.get_transaction_count(wallet)
account_data = pool.functions.getUserAccountData(wallet).call()
debt = account_data[1]

# USDC has 6 decimals, debt is in USD base (8 decimals). Wait, if we use repay MAX_UINT, we just need to approve enough.
print(f"Approving USDC for repayment...")
# Approve max just to be safe
tx1 = usdc_contract.functions.approve(AAVE_POOL, 2**256 - 1).build_transaction({
    'from': wallet, 'nonce': nonce, 'gas': 100000, 'gasPrice': w3.eth.gas_price
})
w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx1, pk).rawTransaction)
nonce += 1
time.sleep(3)

print("Repaying USDC debt...")
tx2 = pool.functions.repay(USDC, 2**256 - 1, 2, wallet).build_transaction({
    'from': wallet, 'nonce': nonce, 'gas': 300000, 'gasPrice': w3.eth.gas_price
})
h2 = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx2, pk).rawTransaction)
r2 = w3.eth.wait_for_transaction_receipt(h2)
print(f"Repay tx: {h2.hex()}, status: {r2.status}")
nonce += 1
time.sleep(3)

bal = aweth_contract.functions.balanceOf(wallet).call()
print(f"aWETH balance: {bal}")

if bal > 0:
    print("Withdrawing WETH from Aave...")
    tx3 = pool.functions.withdraw(WETH, 2**256 - 1, wallet).build_transaction({
        'from': wallet, 'nonce': nonce, 'gas': 500000, 'gasPrice': w3.eth.gas_price
    })
    h3 = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx3, pk).rawTransaction)
    r3 = w3.eth.wait_for_transaction_receipt(h3)
    print(f"Withdraw tx: {h3.hex()}, status: {r3.status}")
else:
    print("No aWETH to withdraw.")
