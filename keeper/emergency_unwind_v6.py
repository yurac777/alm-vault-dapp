"""
emergency_unwind_v6.py
======================
Full emergency shutdown of ALMVaultV6:
  1. Call rebalance() with close-all params → closes Uni V3 position + repays WETH debt + withdraws aUSDC
  2. Call rescueFunds() for remaining USDC → all cash back to deployer wallet

Run from:  cd keeper && python emergency_unwind_v6.py
"""
import os
import sys
import time
from decimal import Decimal

from web3 import Web3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

RPC_URL      = os.getenv("BASE_MAINNET_RPC")
PRIVATE_KEY  = os.getenv("PRIVATE_KEY")
WALLET       = os.getenv("WALLET_ADDRESS")
VAULT_ADDR   = os.getenv("VAULT_ADDRESS", "0x75fd978542e082d455879A9301567438e71db9ec")

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH = "0x4200000000000000000000000000000000000006"
AAVE_POOL = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"

MAX_UINT256 = (2**256) - 1

VAULT_ABI = [
    {
        "inputs": [{"internalType": "bytes", "name": "data", "type": "bytes"}],
        "name": "rebalance", "outputs": [], "stateMutability": "nonpayable", "type": "function"
    },
    {
        "inputs": [], "name": "currentTokenId",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function"
    },
    {
        "inputs": [], "name": "currentLiquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view", "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "token", "type": "address"},
                   {"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "rescueFunds", "outputs": [], "stateMutability": "nonpayable", "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function"
    },
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

AAVE_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getUserAccountData",
        "outputs": [
            {"internalType": "uint256", "name": "totalCollateralBase", "type": "uint256"},
            {"internalType": "uint256", "name": "totalDebtBase", "type": "uint256"},
            {"internalType": "uint256", "name": "availableBorrowsBase", "type": "uint256"},
            {"internalType": "uint256", "name": "currentLiquidationThreshold", "type": "uint256"},
            {"internalType": "uint256", "name": "ltv", "type": "uint256"},
            {"internalType": "uint256", "name": "healthFactor", "type": "uint256"},
        ],
        "stateMutability": "view", "type": "function"
    }
]


def encode_emergency_rebalance():
    """
    Encode a rebalance payload that:
      - Closes the existing Uni V3 position (handled by contract if liquidity > 0)
      - Repays ALL WETH debt (MAX_UINT256 is safe: Aave repays only what's owed)
      - Withdraws ALL aUSDC collateral (MAX_UINT256: Aave withdraws max available)
      - Does NOT open a new position (amount0Desired=0, amount1Desired=0)
    """
    from eth_abi import encode as eth_encode

    payload = eth_encode(
        ['bool','int256','uint256','uint256','int24','int24','uint256','uint256','uint24','uint256','uint256','uint256','uint256'],
        [
            False,       # isRebalance
            0,           # aaveDebtAdjustment
            0,           # amountUSDC to supply
            0,           # amountWETHToBorrow
            0,           # newTickLower  (ignored, no new position)
            0,           # newTickUpper
            0,           # amount0Desired
            0,           # amount1Desired
            500,         # poolFee       (ignored)
            MAX_UINT256, # amountWETHToRepay: repay all debt
            MAX_UINT256, # amountUSDCToWithdraw: withdraw all collateral
            0,           # amount0Min
            0,           # amount1Min
        ]
    )
    return payload


def send_tx(w3, contract_func, wallet, private_key, desc):
    """Build, sign, send and wait for a transaction."""
    nonce = w3.eth.get_transaction_count(wallet, 'pending')
    base_fee = w3.eth.gas_price
    max_priority = w3.to_wei(0.002, 'gwei')
    max_fee = base_fee + max_priority

    tx = contract_func.build_transaction({
        'from': wallet,
        'nonce': nonce,
        'maxFeePerGas': max_fee,
        'maxPriorityFeePerGas': max_priority,
        'chainId': 8453,
    })

    try:
        gas_est = w3.eth.estimate_gas(tx)
        tx['gas'] = int(gas_est * 1.3)
    except Exception as e:
        print(f"  [WARN] gas estimate failed: {e}, using 500k")
        tx['gas'] = 500_000

    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  Tx: https://basescan.org/tx/{tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt.status == 1:
        print(f"  [OK] {desc} confirmed in block {receipt.blockNumber}")
    else:
        print(f"  [FAIL] {desc} REVERTED. Receipt: {receipt}")
    return receipt


def main():
    print("=" * 56)
    print("  EMERGENCY UNWIND — ALMVaultV6")
    print("=" * 56)

    if not all([RPC_URL, PRIVATE_KEY, WALLET]):
        print("[CRITICAL] Missing env vars. Check keeper/.env")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        print("[CRITICAL] Cannot connect to RPC.")
        sys.exit(1)
    print(f"Connected. Block: {w3.eth.block_number}")

    wallet  = w3.to_checksum_address(WALLET)
    vault   = w3.to_checksum_address(VAULT_ADDR)
    usdc_c  = w3.eth.contract(address=w3.to_checksum_address(USDC), abi=ERC20_ABI)
    vault_c = w3.eth.contract(address=vault, abi=VAULT_ABI)
    aave_c  = w3.eth.contract(address=w3.to_checksum_address(AAVE_POOL), abi=AAVE_ABI)

    # ── Pre-flight state ──────────────────────────────────────────────────────
    token_id  = vault_c.functions.currentTokenId().call()
    liquidity = vault_c.functions.currentLiquidity().call()
    aave_data = aave_c.functions.getUserAccountData(vault).call()
    coll_usd  = aave_data[0] / 1e8
    debt_usd  = aave_data[1] / 1e8
    free_usdc = usdc_c.functions.balanceOf(vault).call() / 1e6

    print(f"\n  PRE-UNWIND STATE:")
    print(f"  Uni V3 Token ID   : {token_id}")
    print(f"  Uni V3 Liquidity  : {liquidity}")
    print(f"  Aave Collateral   : ${coll_usd:.4f}")
    print(f"  Aave Debt         : ${debt_usd:.4f}")
    print(f"  Free USDC in vault: ${free_usdc:.4f}")
    print()

    # ── STEP 1: Emergency Rebalance (close position + repay debt + withdraw USDC) ──
    print("STEP 1: Emergency Rebalance — close Uni + repay WETH debt + withdraw aUSDC")
    payload = encode_emergency_rebalance()
    receipt = send_tx(
        w3,
        vault_c.functions.rebalance(payload),
        wallet, PRIVATE_KEY,
        "Emergency Rebalance"
    )

    if receipt.status != 1:
        print("[CRITICAL] Rebalance failed. Aborting.")
        sys.exit(1)

    # ── Post-rebalance state ──────────────────────────────────────────────────
    time.sleep(3)
    free_usdc_after = usdc_c.functions.balanceOf(vault).call()
    aave_after = aave_c.functions.getUserAccountData(vault).call()
    print(f"\n  POST-REBALANCE STATE:")
    print(f"  Free USDC in vault  : ${free_usdc_after / 1e6:.4f}")
    print(f"  Aave Collateral     : ${aave_after[0] / 1e8:.4f}")
    print(f"  Aave Debt           : ${aave_after[1] / 1e8:.4f}")

    if free_usdc_after == 0:
        print("\n  No USDC to rescue. Unwind complete.")
        return

    # ── STEP 2: rescueFunds — move all USDC from vault to deployer ────────────
    print(f"\nSTEP 2: rescueFunds — pulling {free_usdc_after / 1e6:.6f} USDC to deployer")
    receipt2 = send_tx(
        w3,
        vault_c.functions.rescueFunds(
            w3.to_checksum_address(USDC),
            free_usdc_after
        ),
        wallet, PRIVATE_KEY,
        "rescueFunds(USDC)"
    )

    # ── Final state ───────────────────────────────────────────────────────────
    wallet_usdc = usdc_c.functions.balanceOf(wallet).call() / 1e6
    vault_usdc  = usdc_c.functions.balanceOf(vault).call() / 1e6
    print(f"\n  FINAL STATE:")
    print(f"  Deployer USDC balance : ${wallet_usdc:.6f}")
    print(f"  Vault USDC remaining  : ${vault_usdc:.6f}")
    print("\n[DONE] Emergency Unwind complete.")


if __name__ == "__main__":
    main()
