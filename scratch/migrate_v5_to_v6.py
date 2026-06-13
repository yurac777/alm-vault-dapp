import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath('keeper')))
from keeper import config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
wallet = w3.to_checksum_address(config.WALLET)
pk = config.PRIVATE_KEY
v5_addr = w3.to_checksum_address("0x6B2Ec85Fb2c4CE051B71804e20aD8F2c03DADcB4")
v6_addr = w3.to_checksum_address(config.VAULT_ADDRESS)
usdc_addr = w3.to_checksum_address(config.USDC)

usdc_abi = [{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
            {"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}]
vault_abi = [
    {"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"shares","type":"uint256"},{"internalType":"address","name":"receiver","type":"address"},{"internalType":"address","name":"owner","type":"address"}],"name":"redeem","outputs":[{"internalType":"uint256","name":"assets","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"assets","type":"uint256"},{"internalType":"address","name":"receiver","type":"address"}],"name":"deposit","outputs":[{"internalType":"uint256","name":"shares","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
]

usdc = w3.eth.contract(address=usdc_addr, abi=usdc_abi)
v5 = w3.eth.contract(address=v5_addr, abi=vault_abi)
v6 = w3.eth.contract(address=v6_addr, abi=vault_abi)

wallet_v5_shares = v5.functions.balanceOf(wallet).call()
print(f"Wallet V5 shares: {wallet_v5_shares}")

if wallet_v5_shares > 0:
    print("Redeeming V5 shares...")
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    tx = v5.functions.redeem(wallet_v5_shares, wallet, wallet).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 500000, "chainId": 8453})
    signed = w3.eth.account.sign_transaction(tx, pk)
    h = w3.eth.send_raw_transaction(signed.rawTransaction)
    r = w3.eth.wait_for_transaction_receipt(h, timeout=60)
    print("Redeem Tx:", h.hex(), "->", "OK" if r.status == 1 else "REVERTED")
    time.sleep(2)

wallet_usdc = usdc.functions.balanceOf(wallet).call()
print(f"Wallet USDC after redeem: {wallet_usdc/1e6:.6f}")

if wallet_usdc > 0:
    print("Depositing to V6...")
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    h1 = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(usdc.functions.approve(v6_addr, wallet_usdc).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 100000, "chainId": 8453}), pk).rawTransaction)
    w3.eth.wait_for_transaction_receipt(h1)
    
    nonce = w3.eth.get_transaction_count(wallet, "pending")
    h2 = w3.eth.send_raw_transaction(w3.eth.account.sign_transaction(v6.functions.deposit(wallet_usdc, wallet).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price, "gas": 500000, "chainId": 8453}), pk).rawTransaction)
    r2 = w3.eth.wait_for_transaction_receipt(h2)
    print("Deposit Tx:", h2.hex(), "->", "OK" if r2.status == 1 else "REVERTED")
    print(f"Successfully migrated {wallet_usdc/1e6:.6f} USDC to ALMVaultV6!")
