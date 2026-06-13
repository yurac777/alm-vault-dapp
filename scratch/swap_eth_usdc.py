import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY

ROUTER = w3.to_checksum_address('0x2626664c2603336E57B271c5C0b26F421741e481')
WETH = w3.to_checksum_address(config.WETH)
USDC = w3.to_checksum_address(config.USDC)

router = w3.eth.contract(address=ROUTER, abi=[
    {'inputs':[{'components':[{'internalType':'address','name':'tokenIn','type':'address'},{'internalType':'address','name':'tokenOut','type':'address'},{'internalType':'uint24','name':'fee','type':'uint24'},{'internalType':'address','name':'recipient','type':'address'},{'internalType':'uint256','name':'amountIn','type':'uint256'},{'internalType':'uint256','name':'amountOutMinimum','type':'uint256'},{'internalType':'uint160','name':'sqrtPriceLimitX96','type':'uint160'}],'internalType':'struct IV3SwapRouter.ExactInputSingleParams','name':'params','type':'tuple'}],'name':'exactInputSingle','outputs':[{'internalType':'uint256','name':'amountOut','type':'uint256'}],'stateMutability':'payable','type':'function'}
])

eth_to_swap = int(0.0003 * 10**18) # ~0.0003 ETH ~ $1.00
nonce = w3.eth.get_transaction_count(wallet)

print('Swapping ETH to USDC...')
params = (WETH, USDC, 500, wallet, eth_to_swap, 0, 0)
tx = router.functions.exactInputSingle(params).build_transaction({'from':wallet, 'nonce':nonce, 'gas':500000, 'gasPrice':w3.eth.gas_price, 'value':eth_to_swap})
h = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, pk).rawTransaction)
w3.eth.wait_for_transaction_receipt(h)
print('Swap complete!')

usdc_contract = w3.eth.contract(address=USDC, abi=[{'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}])
print('New USDC Balance:', usdc_contract.functions.balanceOf(wallet).call())
