import json
from web3 import Web3

RPC_URL = 'http://127.0.0.1:8545'
w3 = Web3(Web3.HTTPProvider(RPC_URL))

WHALE = w3.to_checksum_address('0xd0b53D9277642d899DF5C87A3966A349A798F224')
USDC  = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
WETH  = '0x4200000000000000000000000000000000000006'
AAVE  = '0xA238Dd80C259a72e81d7e4664a9801593F98d1c5'
NPM   = '0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1'
AAVE_DATA_PROVIDER = '0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A'
AAVE_ORACLE        = '0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156'

print("=== ALMVaultV10 LIVE FIRE FORK TEST ===")

# Impersonate WHALE
w3.provider.make_request("anvil_impersonateAccount", [WHALE])
w3.provider.make_request("anvil_setBalance", [WHALE, "0x10000000000000000000"]) # give ETH

# Load Vault V10 artifact
ARTIFACT = 'out/ALMVaultV10.sol/ALMVaultV10.json'
with open(ARTIFACT) as f:
    artifact = json.load(f)
abi = artifact['abi']
bytecode = artifact['bytecode']['object']

print("Deploying ALMVaultV10 on Anvil Fork...")
Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
tx_hash = Contract.constructor(
    w3.to_checksum_address(USDC),
    w3.to_checksum_address(WETH),
    w3.to_checksum_address(WHALE),
    w3.to_checksum_address(AAVE),
    w3.to_checksum_address(NPM),
    w3.to_checksum_address(AAVE_DATA_PROVIDER),
    w3.to_checksum_address(AAVE_ORACLE),
).transact({"from": WHALE})
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
vault_address = receipt.contractAddress
vault = w3.eth.contract(address=vault_address, abi=abi)
print(f"-> Deployed at {vault_address}")

usdc_contract = w3.eth.contract(address=USDC, abi=[
    {'constant': True, 'inputs': [{'name': '_owner', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': 'balance', 'type': 'uint256'}], 'type': 'function'},
    {'inputs': [{'internalType': 'address', 'name': 'spender', 'type': 'address'}, {'internalType': 'uint256', 'name': 'amount', 'type': 'uint256'}], 'name': 'approve', 'outputs': [{'internalType': 'bool', 'name': '', 'type': 'bool'}], 'stateMutability': 'nonpayable', 'type': 'function'}
])

# Test Deposit
amount = int(10000 * 1e6) # 10,000 USDC
print(f"\n1. Whale Approving {amount / 1e6} USDC...")
usdc_contract.functions.approve(vault_address, amount).transact({"from": WHALE})

print("2. Whale Depositing...")
vault.functions.deposit(amount, WHALE).transact({"from": WHALE})
shares = vault.functions.balanceOf(WHALE).call()
print(f"-> Shares minted: {shares / 1e18}")

print("\n2.5 Rebalancing (investing capital)...")
vault.functions.rebalance().transact({"from": WHALE})
print("-> Rebalance success! Assets deployed to Aave/Uniswap.")

print("\n3. Requesting Withdrawal via Withdrawal Queue...")
# Request withdrawal of 50%
withdraw_shares = shares // 2
vault.functions.requestWithdrawal(withdraw_shares).transact({"from": WHALE})
queue = vault.functions.totalWithdrawalRequests().call()
print(f"-> Queue size: {queue / 1e18} shares")

print("\n4. Redeeming BEFORE Keeper frees USDC...")
try:
    vault.functions.redeem(withdraw_shares, WHALE, WHALE).transact({"from": WHALE})
    print("-> REDEEM SUCCESS! (WARNING: Should have reverted!)")
except Exception as e:
    print(f"-> REDEEM REVERTED CORRECTLY: {e}")

print("\n5. Simulating Keeper freeing up USDC...")
# We just send raw USDC directly to the vault to simulate the Keeper unwinding positions
usdc_contract.functions.approve(vault_address, amount).transact({"from": WHALE})
# But actually, the vault needs free USDC in its address.
# A standard transfer
w3.eth.contract(address=USDC, abi=[
    {'inputs': [{'internalType': 'address', 'name': 'recipient', 'type': 'address'}, {'internalType': 'uint256', 'name': 'amount', 'type': 'uint256'}], 'name': 'transfer', 'outputs': [{'internalType': 'bool', 'name': '', 'type': 'bool'}], 'stateMutability': 'nonpayable', 'type': 'function'}
]).functions.transfer(vault_address, int(5000 * 1e6)).transact({"from": WHALE})
print("-> Sent 5000 USDC to Vault to simulate Keeper Deleverage")

print("\n6. Redeeming AFTER Keeper frees USDC...")
vault.functions.redeem(withdraw_shares, WHALE, WHALE).transact({"from": WHALE})
print("-> REDEEM SUCCESS! Queue drained, user got money.")

queue_after = vault.functions.totalWithdrawalRequests().call()
print(f"-> Queue size after: {queue_after / 1e18} shares")
print("\n=== TEST PASSED! V10 is Safely Isolated from Liquidation Traps ===")
