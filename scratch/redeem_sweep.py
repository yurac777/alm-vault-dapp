import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY

vaults = [
    '0xfFeAE0f67C0471fDBe11F5210F3d1B193b4DAfEB', '0xC29688C7ca27c2826469D3F14D417562CcF5a3b5',
    '0xE53117F9Bd6D13E54C870fDF636472Bc811c3101', '0x87eE1eCa84E9308946eEcba998625272A6ED9a00',
    '0xF5150B45f3D8430B28b7777c402b7fA80Ad702FA', '0x6B2Ec85Fb2c4CE051B71804e20aD8F2c03DADcB4',
    '0x75fd978542e082d455879A9301567438e71db9ec', '0x80968E24355D449202206FEEA6dB829F2c1CaBCE',
    '0xE641B48B5B5ea0b88367B681e3e416c0588Cfd44', '0x5BE2DA950F8F15588bb0B670e9b8c3f538aE8E5d',
    '0x6C1795ECe776C5f5706862B2FCAD973fc1f4CEd3', '0xB3A06a02b283F7271EFe6B2DF4Fc0F3c8Ef0413C',
    '0x263e18540DCCcc296c51ae239D8f2e56ECAbB1f1', '0x9a45aC52cDDe7e0865F2b39BABAE486188Cc88c7'
]

vault_abi = [
    {'inputs':[],'name':'emergencyUnwind','outputs':[],'stateMutability':'nonpayable','type':'function'},
    {'inputs':[{'internalType':'uint256','name':'shares','type':'uint256'},{'internalType':'address','name':'receiver','type':'address'},{'internalType':'address','name':'owner','type':'address'}],'name':'redeem','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'nonpayable','type':'function'},
    {'inputs':[{'internalType':'address','name':'account','type':'address'}],'name':'balanceOf','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'view','type':'function'}
]

def send_tx(tx):
    try:
        signed = w3.eth.account.sign_transaction(tx, pk)
        h = w3.eth.send_raw_transaction(signed.rawTransaction)
        r = w3.eth.wait_for_transaction_receipt(h)
        return r.status == 1
    except Exception as e:
        return False

nonce = w3.eth.get_transaction_count(wallet)
for v in vaults:
    addr = w3.to_checksum_address(v)
    c = w3.eth.contract(address=addr, abi=vault_abi)
    
    # Try emergencyUnwind
    tx = c.functions.emergencyUnwind().build_transaction({'from': wallet, 'nonce': nonce, 'gas': 1000000, 'gasPrice': w3.eth.gas_price})
    if send_tx(tx):
        print(f'Unwound {addr}')
        nonce += 1
    
    # Redeem
    try:
        bal = c.functions.balanceOf(wallet).call()
        if bal > 0:
            tx = c.functions.redeem(bal, wallet, wallet).build_transaction({'from': wallet, 'nonce': nonce, 'gas': 1000000, 'gasPrice': w3.eth.gas_price})
            if send_tx(tx):
                print(f'Redeemed {bal} shares from {addr}')
                nonce += 1
            else:
                print(f'Redeem failed for {addr}')
    except Exception as e:
        pass

usdc = w3.eth.contract(address=w3.to_checksum_address('0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'), abi=[{'constant':True,'inputs':[{'name':'','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}])
print('Final USDC:', usdc.functions.balanceOf(wallet).call() / 1e6)
