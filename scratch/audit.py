import sys; sys.path.insert(0, '.')
from keeper import config
from web3 import Web3
w3 = Web3(Web3.HTTPProvider(config.RPC_URL))

v3 = w3.to_checksum_address('0x87eE1eCa84E9308946eEcba998625272A6ED9a00')
v5 = w3.to_checksum_address(config.VAULT_ADDRESS)

aave_data_abi = [{'inputs':[{'internalType':'address','name':'user','type':'address'}],'name':'getUserAccountData','outputs':[{'internalType':'uint256','name':'totalCollateralBase','type':'uint256'},{'internalType':'uint256','name':'totalDebtBase','type':'uint256'},{'internalType':'uint256','name':'availableBorrowsBase','type':'uint256'},{'internalType':'uint256','name':'currentLiquidationThreshold','type':'uint256'},{'internalType':'uint256','name':'ltv','type':'uint256'},{'internalType':'uint256','name':'healthFactor','type':'uint256'}],'stateMutability':'view','type':'function'}]
aave = w3.eth.contract(address=w3.to_checksum_address(config.AAVE_POOL), abi=aave_data_abi)

v3_aave = aave.functions.getUserAccountData(v3).call()
v5_aave = aave.functions.getUserAccountData(v5).call()

print("=== CAPITAL AUDIT ===")
print(f"V3 Aave Collateral: ${v3_aave[0]/1e8:.4f}")
print(f"V3 Aave Debt:       ${v3_aave[1]/1e8:.4f}")
print(f"V3 Net Equity LOCKED: ${(v3_aave[0] - v3_aave[1])/1e8:.4f}")
print()
print(f"V5 Aave Collateral: ${v5_aave[0]/1e8:.4f}")
print(f"V5 Aave Debt:       ${v5_aave[1]/1e8:.4f}")
print(f"V5 HF: {v5_aave[5]/1e18:.4f}")
print()
print("DIAGNOSIS: The migrate.py script only redeemed vault shares (free USDC),")
print("           NOT the Aave collateral position. ~$1.33 equity is LOCKED in V3 Aave!")
print()

# Check NFT value in V5
npm_abi = [
    {'inputs':[{'components':[{'internalType':'uint256','name':'tokenId','type':'uint256'},{'internalType':'address','name':'recipient','type':'address'},{'internalType':'uint128','name':'amount0Max','type':'uint128'},{'internalType':'uint128','name':'amount1Max','type':'uint128'}],'internalType':'struct INonfungiblePositionManager.CollectParams','name':'params','type':'tuple'}],'name':'collect','outputs':[{'internalType':'uint256','name':'amount0','type':'uint256'},{'internalType':'uint256','name':'amount1','type':'uint256'}],'stateMutability':'payable','type':'function'},
    {'inputs':[{'internalType':'uint256','name':'tokenId','type':'uint256'}],'name':'positions','outputs':[{'internalType':'uint96','name':'nonce','type':'uint96'},{'internalType':'address','name':'operator','type':'address'},{'internalType':'address','name':'token0','type':'address'},{'internalType':'address','name':'token1','type':'address'},{'internalType':'uint24','name':'fee','type':'uint24'},{'internalType':'int24','name':'tickLower','type':'int24'},{'internalType':'int24','name':'tickUpper','type':'int24'},{'internalType':'uint128','name':'liquidity','type':'uint128'},{'internalType':'uint256','name':'feeGrowthInside0LastX128','type':'uint256'},{'internalType':'uint256','name':'feeGrowthInside1LastX128','type':'uint256'},{'internalType':'uint128','name':'tokensOwed0','type':'uint128'},{'internalType':'uint128','name':'tokensOwed1','type':'uint128'}],'stateMutability':'view','type':'function'},
]
vault_abi = [{'inputs':[],'name':'currentTokenId','outputs':[{'internalType':'uint256','name':'','type':'uint256'}],'stateMutability':'view','type':'function'}]
npm = w3.eth.contract(address=w3.to_checksum_address(config.UNI_V3_NPM), abi=npm_abi)
v5_c = w3.eth.contract(address=v5, abi=vault_abi)
token_id = v5_c.functions.currentTokenId().call()
print(f"V5 TokenId: {token_id}")
if token_id > 0:
    pos = npm.functions.positions(token_id).call()
    liq = pos[7]
    print(f"  Liquidity: {liq}")
    print(f"  Ticks: [{pos[5]}, {pos[6]}]")
    res = npm.functions.collect((token_id, v5, 2**128-1, 2**128-1)).call({'from': v5})
    print(f"  Uncollected fees WETH: {res[0]/1e18:.8f}")
    print(f"  Uncollected fees USDC: {res[1]/1e6:.6f}")
