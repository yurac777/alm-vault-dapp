import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY
WETH = w3.to_checksum_address(config.WETH)

weth = w3.eth.contract(address=WETH, abi=[
    {'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'},
    {'constant':False,'inputs':[{'name':'wad','type':'uint256'}],'name':'withdraw','outputs':[],'type':'function'}
])

bal = weth.functions.balanceOf(wallet).call()
print(f"Unwrapping {w3.from_wei(bal, 'ether')} WETH to ETH...")
if bal > 0:
    nonce = w3.eth.get_transaction_count(wallet)
    tx = weth.functions.withdraw(bal).build_transaction({
        'from': wallet, 'nonce': nonce, 'gas': 100000, 'gasPrice': w3.eth.gas_price
    })
    h = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, pk).rawTransaction)
    w3.eth.wait_for_transaction_receipt(h)
    print('Unwrapped successfully!')
print('Wallet ETH:', w3.from_wei(w3.eth.get_balance(wallet), 'ether'))
