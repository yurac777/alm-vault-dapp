import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY
vault_addr = w3.to_checksum_address(config.VAULT_ADDRESS)

vault = w3.eth.contract(address=vault_addr, abi=[
    {'inputs':[{'internalType':'address','name':'','type':'address'}],'name':'balanceOf','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'view','type':'function'},
    {'inputs':[{'internalType':'uint256','name':'shares','type':'uint256'}],'name':'requestWithdrawal','outputs':[],'stateMutability':'nonpayable','type':'function'}
])

shares = vault.functions.balanceOf(wallet).call()
half_shares = shares // 2
print(f'Total Shares: {shares}, Requesting withdrawal for 50%: {half_shares}')

if half_shares > 0:
    nonce = w3.eth.get_transaction_count(wallet)
    tx = vault.functions.requestWithdrawal(half_shares).build_transaction({
        'from': wallet,
        'nonce': nonce,
        'gas': 150000,
        'gasPrice': w3.eth.gas_price
    })
    h = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx, pk).rawTransaction)
    print('Tx sent:', h.hex())
    r = w3.eth.wait_for_transaction_receipt(h)
    print('Request successful! status:', r.status)
else:
    print('No shares to withdraw.')
