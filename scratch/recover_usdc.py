import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY

WETH = w3.to_checksum_address('0x4200000000000000000000000000000000000006')
USDC = w3.to_checksum_address('0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913')
ROUTER = w3.to_checksum_address('0x2626664c2603336E57B271c5C0b26F421741e481')

pool = w3.eth.contract(address=w3.to_checksum_address(config.AAVE_POOL), abi=[
    {'inputs':[{'internalType':'address','name':'asset','type':'address'},{'internalType':'uint256','name':'amount','type':'uint256'},{'internalType':'address','name':'to','type':'address'}],'name':'withdraw','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'nonpayable','type':'function'}
])

nonce = w3.eth.get_transaction_count(wallet)
print('Withdrawing WETH from Aave...')
try:
    tx = pool.functions.withdraw(WETH, 2**256 - 1, wallet).build_transaction({'from':wallet, 'nonce':nonce, 'gas':500000, 'gasPrice':w3.eth.gas_price})
    signed = w3.eth.account.sign_transaction(tx, pk)
    h = w3.eth.send_raw_transaction(signed.rawTransaction)
    w3.eth.wait_for_transaction_receipt(h)
    print('Withdrawn!')
    nonce += 1
except Exception as e:
    print('Failed to withdraw:', e)

weth = w3.eth.contract(address=WETH, abi=[
    {'constant':False,'inputs':[{'name':'','type':'address'},{'name':'','type':'uint256'}],'name':'approve','outputs':[{'name':'','type':'bool'}],'type':'function'},
    {'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}
])

bal = weth.functions.balanceOf(wallet).call()
print('WETH balance:', bal)

if bal > 0:
    print('Approving SwapRouter02...')
    tx2 = weth.functions.approve(ROUTER, bal).build_transaction({'from':wallet, 'nonce':nonce, 'gas':100000, 'gasPrice':w3.eth.gas_price})
    w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx2, pk).rawTransaction)
    time.sleep(3)
    nonce += 1

    print('Swapping WETH to USDC...')
    router = w3.eth.contract(address=ROUTER, abi=[
        {'inputs':[{'components':[{'internalType':'address','name':'tokenIn','type':'address'},{'internalType':'address','name':'tokenOut','type':'address'},{'internalType':'uint24','name':'fee','type':'uint24'},{'internalType':'address','name':'recipient','type':'address'},{'internalType':'uint256','name':'amountIn','type':'uint256'},{'internalType':'uint256','name':'amountOutMinimum','type':'uint256'},{'internalType':'uint160','name':'sqrtPriceLimitX96','type':'uint160'}],'internalType':'struct IV3SwapRouter.ExactInputSingleParams','name':'params','type':'tuple'}],'name':'exactInputSingle','outputs':[{'internalType':'uint256','name':'amountOut','type':'uint256'}],'stateMutability':'payable','type':'function'}
    ])
    params = (WETH, USDC, 500, wallet, bal, 0, 0)
    tx3 = router.functions.exactInputSingle(params).build_transaction({'from':wallet, 'nonce':nonce, 'gas':500000, 'gasPrice':w3.eth.gas_price})
    h3 = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx3, pk).rawTransaction)
    print('Swap Tx:', h3.hex())
    w3.eth.wait_for_transaction_receipt(h3)
    print('Swap complete!')

usdc_contract = w3.eth.contract(address=USDC, abi=[{'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}])
print('New USDC Balance:', usdc_contract.functions.balanceOf(wallet).call())
