import sys, time
sys.path.insert(0, 'keeper')
import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY

NPM_ADDRESS = w3.to_checksum_address('0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1')

npm = w3.eth.contract(address=NPM_ADDRESS, abi=[
    {'inputs':[{'internalType':'address','name':'owner','type':'address'}],'name':'balanceOf','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'view','type':'function'},
    {'inputs':[{'internalType':'address','name':'owner','type':'address'},{'internalType':'uint256','name':'index','type':'uint256'}],'name':'tokenOfOwnerByIndex','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'view','type':'function'},
    {'inputs':[{'internalType':'uint256','name':'tokenId','type':'uint256'}],'name':'positions','outputs':[{'internalType':'uint96','name':'nonce','type':'uint96'},{'internalType':'address','name':'operator','type':'address'},{'internalType':'address','name':'token0','type':'address'},{'internalType':'address','name':'token1','type':'address'},{'internalType':'uint24','name':'fee','type':'uint24'},{'internalType':'int24','name':'tickLower','type':'int24'},{'internalType':'int24','name':'tickUpper','type':'int24'},{'internalType':'uint128','name':'liquidity','type':'uint128'},{'internalType':'uint256','name':'feeGrowthInside0LastX128','type':'uint256'},{'internalType':'uint256','name':'feeGrowthInside1LastX128','type':'uint256'},{'internalType':'uint128','name':'tokensOwed0','type':'uint128'},{'internalType':'uint128','name':'tokensOwed1','type':'uint128'}],'stateMutability':'view','type':'function'},
    {'inputs':[{'components':[{'internalType':'uint256','name':'tokenId','type':'uint256'},{'internalType':'uint128','name':'liquidity','type':'uint128'},{'internalType':'uint256','name':'amount0Min','type':'uint256'},{'internalType':'uint256','name':'amount1Min','type':'uint256'},{'internalType':'uint256','name':'deadline','type':'uint256'}],'internalType':'struct INonfungiblePositionManager.DecreaseLiquidityParams','name':'params','type':'tuple'}],'name':'decreaseLiquidity','outputs':[{'internalType':'uint256','name':'amount0','type':'uint256'},{'internalType':'uint256','name':'amount1','type':'uint256'}],'stateMutability':'payable','type':'function'},
    {'inputs':[{'components':[{'internalType':'uint256','name':'tokenId','type':'uint256'},{'internalType':'address','name':'recipient','type':'address'},{'internalType':'uint128','name':'amount0Max','type':'uint128'},{'internalType':'uint128','name':'amount1Max','type':'uint128'}],'internalType':'struct INonfungiblePositionManager.CollectParams','name':'params','type':'tuple'}],'name':'collect','outputs':[{'internalType':'uint256','name':'amount0','type':'uint256'},{'internalType':'uint256','name':'amount1','type':'uint256'}],'stateMutability':'payable','type':'function'}
])

balance = npm.functions.balanceOf(wallet).call()
print(f"Found {balance} NFTs owned by {wallet}")

nonce = w3.eth.get_transaction_count(wallet)

for i in range(balance):
    token_id = npm.functions.tokenOfOwnerByIndex(wallet, i).call()
    pos = npm.functions.positions(token_id).call()
    liquidity = pos[7]
    print(f"\nToken ID: {token_id}, Liquidity: {liquidity}")
    
    if liquidity > 0:
        print("Decreasing liquidity...")
        tx1 = npm.functions.decreaseLiquidity((token_id, liquidity, 0, 0, 2**256 - 1)).build_transaction({
            'from': wallet, 'nonce': nonce, 'gas': 1000000, 'gasPrice': w3.eth.gas_price
        })
        h1 = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx1, pk).rawTransaction)
        w3.eth.wait_for_transaction_receipt(h1)
        nonce += 1
        print(f"Decrease tx: {h1.hex()}")
        time.sleep(2)
        
    print("Collecting tokens...")
    tx2 = npm.functions.collect((token_id, wallet, 2**128 - 1, 2**128 - 1)).build_transaction({
        'from': wallet, 'nonce': nonce, 'gas': 1000000, 'gasPrice': w3.eth.gas_price
    })
    h2 = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(tx2, pk).rawTransaction)
    w3.eth.wait_for_transaction_receipt(h2)
    nonce += 1
    print(f"Collect tx: {h2.hex()}")
    time.sleep(2)

print("\nAll NFTs burned/collected.")
