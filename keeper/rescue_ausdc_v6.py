"""
rescue_ausdc_v6.py
==================
Rescue aUSDC (Aave collateral token) from ALMVaultV6.

Current state of V6:
  - Uni V3 position: CLOSED (tokenId=0)
  - WETH debt: $0.00 (fully repaid by auto-sweep)
  - aUSDC balance: 0.046630 USDC (trapped in vault)
  - USDC balance: $0.00 (already rescued)

Strategy:
  aUSDC is a standard ERC20. The vault holds it.
  rescueFunds(aUSDC_address, amount) transfers aUSDC tokens to owner wallet.
  Once wallet holds aUSDC, the EOA can withdraw it directly from Aave UI
  (EOA holding aUSDC = EOA has a deposit position in Aave, redeemable).
"""
import os, time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

RPC_URL = os.getenv("BASE_MAINNET_RPC")
PK      = os.getenv("PRIVATE_KEY")
WALLET  = os.getenv("WALLET_ADDRESS")

VAULT_V6  = "0x75fd978542e082d455879A9301567438e71db9ec"
aUSDC_ADDR = "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB"
USDC_ADDR  = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
AAVE_POOL  = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"

ERC20_ABI = [
    {"inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]
RESCUE_ABI = [
    {"inputs": [{"internalType": "address", "name": "token", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"}],
     "name": "rescueFunds", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]
AAVE_POOL_ABI = [
    {"inputs": [{"name": "user", "type": "address"}], "name": "getUserAccountData",
     "outputs": [{"type": "uint256"}, {"type": "uint256"}, {"type": "uint256"},
                 {"type": "uint256"}, {"type": "uint256"}, {"type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "asset", "type": "address"}, {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"}], "name": "withdraw",
     "outputs": [{"type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
]


def send_tx(w3, fn, wallet, pk, desc):
    nonce    = w3.eth.get_transaction_count(wallet, "pending")
    base_fee = w3.eth.gas_price
    tx = fn.build_transaction({
        "from": wallet, "nonce": nonce,
        "maxFeePerGas": base_fee + w3.to_wei(0.002, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(0.002, "gwei"),
        "chainId": 8453,
    })
    try:
        tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.3)
    except Exception as e:
        print(f"  [WARN] estimate_gas: {e}, using 200k")
        tx["gas"] = 200_000
    signed  = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    full_hash = tx_hash.hex()
    print(f"  TX:     {full_hash}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    status  = "OK" if receipt.status == 1 else "REVERTED"
    print(f"  Status: {status} | Block: {receipt.blockNumber} | Gas: {receipt.gasUsed}")
    return receipt, full_hash


def main():
    print("=" * 60)
    print("  RESCUE aUSDC from ALMVaultV6")
    print("=" * 60)

    w3     = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    assert w3.is_connected(), "RPC not connected"
    print(f"Connected. Block: {w3.eth.block_number}")

    wallet   = w3.to_checksum_address(WALLET)
    vault    = w3.to_checksum_address(VAULT_V6)
    ausdc_a  = w3.to_checksum_address(aUSDC_ADDR)
    usdc_a   = w3.to_checksum_address(USDC_ADDR)

    vc       = w3.eth.contract(address=vault,  abi=RESCUE_ABI)
    ausdc_c  = w3.eth.contract(address=ausdc_a, abi=ERC20_ABI)
    usdc_c   = w3.eth.contract(address=usdc_a,  abi=ERC20_ABI)
    aave_c   = w3.eth.contract(address=w3.to_checksum_address(AAVE_POOL), abi=AAVE_POOL_ABI)

    # Pre-flight
    aave_state  = aave_c.functions.getUserAccountData(vault).call()
    ausdc_in_vault = ausdc_c.functions.balanceOf(vault).call()
    usdc_in_vault  = usdc_c.functions.balanceOf(vault).call()

    print(f"\n  PRE-RESCUE STATE (V6 VAULT):")
    print(f"  aUSDC in vault : {ausdc_in_vault} raw = {ausdc_in_vault/1e6:.8f} USDC")
    print(f"  USDC in vault  : {usdc_in_vault/1e6:.8f}")
    print(f"  Aave Debt      : {aave_state[1]/1e8:.8f} USD")
    hf_display = "INF" if aave_state[5] > 10**54 else f"{aave_state[5]/1e18:.4f}"
    print(f"  Health Factor  : {hf_display}")

    if aave_state[1] > 0:
        print(f"\n  [ERROR] WETH debt is not zero! Cannot safely rescue aUSDC.")
        print(f"  Debt: {aave_state[1]/1e8:.8f} USD. Repay first.")
        return

    if ausdc_in_vault == 0:
        print("\n  No aUSDC to rescue. Vault is already clean.")
        return

    # STEP 1: rescueFunds(aUSDC) — moves Aave collateral token to wallet
    print(f"\nSTEP 1: rescueFunds(aUSDC, {ausdc_in_vault}) -> wallet")
    print("  aUSDC is a standard ERC20. Vault owner can transfer it directly.")
    r1, hash1 = send_tx(w3, vc.functions.rescueFunds(ausdc_a, ausdc_in_vault), wallet, PK,
                        "rescueFunds(aUSDC)")

    if r1.status != 1:
        print("\n  [FAIL] rescueFunds(aUSDC) reverted. Check Basescan.")
        return

    time.sleep(3)
    wallet_ausdc = ausdc_c.functions.balanceOf(wallet).call()
    vault_ausdc  = ausdc_c.functions.balanceOf(vault).call()
    vault_usdc2  = usdc_c.functions.balanceOf(vault).call()
    aave_final   = aave_c.functions.getUserAccountData(vault).call()

    print(f"\n  POST-RESCUE STATE:")
    print(f"  Wallet aUSDC   : {wallet_ausdc} raw = {wallet_ausdc/1e6:.8f}")
    print(f"  Vault aUSDC    : {vault_ausdc/1e6:.8f}")
    print(f"  Vault USDC     : {vault_usdc2/1e6:.8f}")
    print(f"  Aave Coll left : {aave_final[0]/1e8:.8f} USD")
    print(f"  Aave Debt left : {aave_final[1]/1e8:.8f} USD")

    # STEP 2: Now wallet holds aUSDC. Withdraw via Aave Pool directly from EOA.
    print(f"\nSTEP 2: EOA withdraws aUSDC from Aave directly (wallet holds aUSDC)")
    print("  EOA holding aUSDC can call aavePool.withdraw() directly...")

    aave_pool_c = w3.eth.contract(address=w3.to_checksum_address(AAVE_POOL), abi=AAVE_POOL_ABI)

    # Check if wallet has aUSDC allowance to withdraw
    if wallet_ausdc > 0:
        try:
            # Simulate
            aave_pool_c.functions.withdraw(usdc_a, wallet_ausdc, wallet).call({"from": wallet})
            print("  Simulation OK. Sending withdraw tx...")
            r2, hash2 = send_tx(
                w3,
                aave_pool_c.functions.withdraw(usdc_a, wallet_ausdc, wallet),
                wallet, PK,
                "Aave.withdraw(USDC)"
            )
            if r2.status == 1:
                final_usdc = usdc_c.functions.balanceOf(wallet).call()
                print(f"\n  Wallet USDC (final): {final_usdc/1e6:.8f}")
                print(f"\n{'='*60}")
                print(f"  COMPLETE. All funds rescued from V6.")
                print(f"  Total USDC in wallet: {final_usdc/1e6:.6f}")
                print(f"  TX1 (rescueFunds aUSDC): {hash1}")
                print(f"  TX2 (Aave withdraw):     {hash2}")
                print(f"{'='*60}")
            else:
                print(f"  Aave withdraw failed. Wallet holds {wallet_ausdc/1e6:.6f} aUSDC.")
                print(f"  Redeem at https://app.aave.com (EOA can withdraw own aUSDC)")
        except Exception as e:
            print(f"  Aave withdraw sim failed: {e}")
            print(f"  Wallet holds {wallet_ausdc/1e6:.6f} aUSDC.")
            print(f"  Redeem at https://app.aave.com (EOA holds aUSDC, can withdraw it)")
    else:
        print("  Wallet has no aUSDC. Check if rescue succeeded.")


if __name__ == "__main__":
    main()
