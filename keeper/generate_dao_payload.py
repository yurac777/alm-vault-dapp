from web3 import Web3

w3 = Web3()

# DAO will approve 500,000 USDC
# ERC20 Approve
erc20_abi = [
    {
        "constant": False,
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Vault Deposit
vault_abi = [
    {
        "inputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}],
        "name": "deposit",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
VAULT_ADDRESS = "0x0000000000000000000000000000000000000001" 
DAO_TREASURY_ADDRESS = "0x0000000000000000000000000000000000000002"
AMOUNT = 500_000 * 10**6

erc20 = w3.eth.contract(address=USDC_ADDRESS, abi=erc20_abi)
vault = w3.eth.contract(address=VAULT_ADDRESS, abi=vault_abi)

approve_calldata = erc20.encode_abi("approve", args=[VAULT_ADDRESS, AMOUNT])
deposit_calldata = vault.encode_abi("deposit", args=[AMOUNT, DAO_TREASURY_ADDRESS])

print(f"--- DAO PROPOSAL PAYLOADS ---")
print(f"Target 1 (USDC Contract): {USDC_ADDRESS}")
print(f"Value: 0")
print(f"Approve Calldata:")
print(f"{approve_calldata}\n")

print(f"Target 2 (Vault Contract): {VAULT_ADDRESS}")
print(f"Value: 0")
print(f"Deposit Calldata:")
print(f"{deposit_calldata}\n")
