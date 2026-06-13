import os
from web3 import Web3

RPC = "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu"
w3 = Web3(Web3.HTTPProvider(RPC))

vault_addr = w3.to_checksum_address("0x2726c74D2e0A94Ec181Beb618569b10116415289")
aave_pool_addr = w3.to_checksum_address("0xA238Dd80C259a72e81d7e4664a9801593F98d1c5")

vault_abi = [
    {"inputs":[],"name":"netTotalDeposit","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"cachedUniV3ValueUSD","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"}
]
vault = w3.eth.contract(address=vault_addr, abi=vault_abi)

aave_abi = [
    {"inputs":[{"name":"user","type":"address"}],"name":"getUserAccountData","outputs":[{"type":"uint256"},{"type":"uint256"},{"type":"uint256"},{"type":"uint256"},{"type":"uint256"},{"type":"uint256"}],"stateMutability":"view","type":"function"}
]
aave = w3.eth.contract(address=aave_pool_addr, abi=aave_abi)

netDep = vault.functions.netTotalDeposit().call()
accountData = aave.functions.getUserAccountData(vault_addr).call()
cachedUni = vault.functions.cachedUniV3ValueUSD().call()

netDepUsd = netDep / 1e6
colBaseUsd = accountData[0] / 1e8
uniUsd = cachedUni / 1e6

if netDepUsd > 0:
    ratio = ((colBaseUsd + uniUsd) / netDepUsd) * 100
else:
    ratio = 100.0

print(f"[Solvency Math] netDepUsd: {netDepUsd:.6f}, colBaseUsd(Aave): {colBaseUsd:.6f}, uniUsd: {uniUsd:.6f}, ratio: {ratio:.6f}%")
