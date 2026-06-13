"""
execute_unwind_v6.py
====================
Final targeted unwind of ALMVaultV6:
  1. Close Uni V3 position → WETH + USDC land in vault
  2. rescueFunds(USDC) → wallet
  3. rescueFunds(WETH) → wallet
  NOTE: Aave position ($0.046 collateral / $0.015 debt) must be
        closed manually at https://app.aave.com (too small to warrant on-chain tx).
"""
import os, sys, time
from web3 import Web3
from dotenv import load_dotenv
from eth_abi import encode as eth_encode

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

RPC_URL  = os.getenv("BASE_MAINNET_RPC")
PK       = os.getenv("PRIVATE_KEY")
WALLET   = os.getenv("WALLET_ADDRESS")
VAULT    = "0x75fd978542e082d455879A9301567438e71db9ec"
USDC_ADDR = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH_ADDR = "0x4200000000000000000000000000000000000006"

VAULT_ABI = [
    {"inputs": [{"internalType": "bytes", "name": "data", "type": "bytes"}],
     "name": "rebalance", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "token", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"}],
     "name": "rescueFunds", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]
ERC20_ABI = [
    {"inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]


def send_tx(w3, fn, wallet, pk, desc):
    nonce    = w3.eth.get_transaction_count(wallet, "pending")
    base_fee = w3.eth.gas_price
    max_fee  = base_fee + w3.to_wei(0.002, "gwei")

    tx = fn.build_transaction({
        "from": wallet, "nonce": nonce,
        "maxFeePerGas": max_fee, "maxPriorityFeePerGas": w3.to_wei(0.002, "gwei"),
        "chainId": 8453,
    })
    try:
        tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.3)
    except Exception as e:
        print(f"  [WARN] estimate_gas failed: {e}, using 500k")
        tx["gas"] = 500_000

    signed  = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    print(f"  Tx: https://basescan.org/tx/{tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    status  = "OK" if receipt.status == 1 else "REVERTED"
    print(f"  [{status}] {desc} — block {receipt.blockNumber}, gas {receipt.gasUsed}")
    return receipt


def main():
    print("=" * 60)
    print("  EXECUTE UNWIND — ALMVaultV6")
    print("=" * 60)

    w3     = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    assert w3.is_connected(), "RPC not connected"
    print(f"Connected. Block: {w3.eth.block_number}")

    wallet  = w3.to_checksum_address(WALLET)
    vault   = w3.to_checksum_address(VAULT)
    usdc_a  = w3.to_checksum_address(USDC_ADDR)
    weth_a  = w3.to_checksum_address(WETH_ADDR)
    vc      = w3.eth.contract(address=vault, abi=VAULT_ABI)
    usdc_c  = w3.eth.contract(address=usdc_a, abi=ERC20_ABI)
    weth_c  = w3.eth.contract(address=weth_a, abi=ERC20_ABI)

    # Pre-flight
    usdc_before = usdc_c.functions.balanceOf(vault).call()
    print(f"\n  PRE-UNWIND USDC in vault: ${usdc_before/1e6:.6f}")

    # ── STEP 1: Close Uni V3 position, no Aave ops ────────────────────────────
    print("\nSTEP 1: Closing Uni V3 position (rebalance with all zeros except close)")
    payload = eth_encode(
        ["bool","int256","uint256","uint256","int24","int24","uint256","uint256","uint24","uint256","uint256","uint256","uint256"],
        [False, 0, 0, 0, 0, 0, 0, 0, 500, 0, 0, 0, 0]
    )
    r1 = send_tx(w3, vc.functions.rebalance(payload), wallet, PK, "Close Uni V3 position")
    if r1.status != 1:
        print("[CRITICAL] Rebalance failed. Aborting.")
        sys.exit(1)

    time.sleep(3)
    usdc_after_uni = usdc_c.functions.balanceOf(vault).call()
    weth_after_uni = weth_c.functions.balanceOf(vault).call()
    print(f"\n  POST-UNI-CLOSE:")
    print(f"  Vault USDC: ${usdc_after_uni/1e6:.6f}")
    print(f"  Vault WETH: {weth_after_uni/1e18:.10f} WETH")

    # ── STEP 2: Rescue USDC ───────────────────────────────────────────────────
    if usdc_after_uni > 0:
        print(f"\nSTEP 2: rescueFunds -- {usdc_after_uni/1e6:.6f} USDC -> wallet")
        r2 = send_tx(w3, vc.functions.rescueFunds(usdc_a, usdc_after_uni), wallet, PK, "rescueFunds(USDC)")
    else:
        print("\nSTEP 2: No USDC to rescue.")

    # ── STEP 3: Rescue WETH ───────────────────────────────────────────────────
    if weth_after_uni > 0:
        print(f"\nSTEP 3: rescueFunds -- {weth_after_uni/1e18:.10f} WETH -> wallet")
        r3 = send_tx(w3, vc.functions.rescueFunds(weth_a, weth_after_uni), wallet, PK, "rescueFunds(WETH)")
    else:
        print("\nSTEP 3: No WETH to rescue.")

    # ── Final report ─────────────────────────────────────────────────────────
    time.sleep(2)
    wallet_usdc = usdc_c.functions.balanceOf(wallet).call()
    vault_usdc  = usdc_c.functions.balanceOf(vault).call()
    wallet_weth = weth_c.functions.balanceOf(wallet).call()

    print(f"\n{'='*60}")
    print(f"  FINAL STATE:")
    print(f"  Deployer USDC : ${wallet_usdc/1e6:.6f}")
    print(f"  Deployer WETH : {wallet_weth/1e18:.8f}")
    print(f"  Vault USDC    : ${vault_usdc/1e6:.6f}")
    print(f"\n  NOTE: Aave position (~$0.046 collateral / ~$0.015 debt) remains.")
    print(f"  Close at: https://app.aave.com (repay WETH debt first, then withdraw USDC)")
    print(f"{'='*60}")
    print("[DONE] Unwind complete.")


if __name__ == "__main__":
    main()
