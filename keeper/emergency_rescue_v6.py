"""
emergency_rescue_v6.py
======================
Direct emergency rescue from ALMVaultV6:

Problem: rebalance() fails because WETH approve to Aave was not set in constructor.
Solution: The rebalance() function sets approve inside itself on line 104:
    weth.approve(address(aavePool), amountWETHToRepay);
So rebalance SHOULD work. But we're seeing error 0xf0788fb2.

Let's try a different approach:
 - Call rebalance with a SMALL specific repay amount (actual debt in WETH, not MAX_UINT256)
   because Aave.repay() with type(uint256).max repays only the actual debt,
   but the approve must succeed first.

Actually the issue is: weth.approve(address(aavePool), amountWETHToRepay) where
amountWETHToRepay = MAX_UINT256. This sets approval to MAX but if WETH balance in vault
is 0 at the time of calling repay(), Aave will revert. The sequence is:
  1. decreaseLiquidity (gets WETH back from Uni position)
  2. collect (moves WETH to vault)
  3. weth.approve(aavePool, MAX) -- OK
  4. aavePool.repay(WETH, MAX, 2, this) -- tries to repay with WETH just received

Wait - in V6 code line 103-106:
  if (amountWETHToRepay > 0) {
      weth.approve(address(aavePool), amountWETHToRepay);   <-- 0xf0788fb2 is here?
      aavePool.repay(...);

0xf0788fb2 - let's look it up in WETH (which is OZ ERC20Permit on Base):
ERC20: approve reverts if owner==0? or spender==0? No...
Actually WETH on Base is NOT a standard OZ. It might have restrictions.
Let's just call with repay=0 but do the Uni close separately via NPM directly,
then rescueFunds for USDC, and accept that the tiny WETH debt (~$0.015) stays.
OR: we can use the vault's rescueFunds to pull USDC and separately handle the tiny debt.

ACTUAL STRATEGY:
1. The vault is owner=wallet. 
2. The Uni position (tokenId=5325693) is owned by the vault.
3. We can call NPM.decreaseLiquidity directly FROM the vault via a tx that the vault executes.
4. But we can only call vault functions: rebalance() (keeper) or rescueFunds() (owner).
5. We ARE the keeper. Let's try rebalance with amountWETHToRepay = exact_debt (not MAX).
6. Then rescueFunds for all USDC.
"""
import os
import sys
import time
from web3 import Web3
from dotenv import load_dotenv
from eth_abi import encode as eth_encode

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

RPC_URL    = os.getenv("BASE_MAINNET_RPC")
PRIV_KEY   = os.getenv("PRIVATE_KEY")
WALLET     = os.getenv("WALLET_ADDRESS")
VAULT_ADDR = os.getenv("VAULT_ADDRESS", "0x75fd978542e082d455879A9301567438e71db9ec")

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH = "0x4200000000000000000000000000000000000006"
AAVE_POOL = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"

VAULT_ABI = [
    {"inputs": [{"internalType": "bytes", "name": "data", "type": "bytes"}],
     "name": "rebalance", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "token", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"}],
     "name": "rescueFunds", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "currentTokenId",
     "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "currentLiquidity",
     "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
     "stateMutability": "view", "type": "function"},
]

ERC20_ABI = [
    {"inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]

AAVE_ABI = [
    {"inputs": [{"name": "user", "type": "address"}], "name": "getUserAccountData",
     "outputs": [{"type": "uint256"}, {"type": "uint256"}, {"type": "uint256"},
                 {"type": "uint256"}, {"type": "uint256"}, {"type": "uint256"}],
     "stateMutability": "view", "type": "function"},
]

NPM_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
     "name": "positions",
     "outputs": [
         {"internalType": "uint96",  "name": "nonce",             "type": "uint96"},
         {"internalType": "address", "name": "operator",          "type": "address"},
         {"internalType": "address", "name": "token0",            "type": "address"},
         {"internalType": "address", "name": "token1",            "type": "address"},
         {"internalType": "uint24",  "name": "fee",               "type": "uint24"},
         {"internalType": "int24",   "name": "tickLower",         "type": "int24"},
         {"internalType": "int24",   "name": "tickUpper",         "type": "int24"},
         {"internalType": "uint128", "name": "liquidity",         "type": "uint128"},
         {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
         {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
         {"internalType": "uint128", "name": "tokensOwed0",       "type": "uint128"},
         {"internalType": "uint128", "name": "tokensOwed1",       "type": "uint128"},
     ],
     "stateMutability": "view", "type": "function"},
]

CHAINLINK_ABI = [
    {"inputs": [], "name": "latestRoundData",
     "outputs": [{"type": "uint80"}, {"type": "int256"}, {"type": "uint256"},
                 {"type": "uint256"}, {"type": "uint80"}],
     "stateMutability": "view", "type": "function"},
]


def send_tx(w3, fn, wallet, pk, desc):
    nonce     = w3.eth.get_transaction_count(wallet, 'pending')
    base_fee  = w3.eth.gas_price
    max_prio  = w3.to_wei(0.002, 'gwei')
    max_fee   = base_fee + max_prio

    tx = fn.build_transaction({
        'from': wallet, 'nonce': nonce,
        'maxFeePerGas': max_fee, 'maxPriorityFeePerGas': max_prio,
        'chainId': 8453,
    })
    try:
        tx['gas'] = int(w3.eth.estimate_gas(tx) * 1.3)
    except Exception as e:
        print(f"  [WARN] gas estimate failed ({e}), using 600k")
        tx['gas'] = 600_000

    signed  = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  Tx: https://basescan.org/tx/{tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    status  = "OK" if receipt.status == 1 else "REVERTED"
    print(f"  [{status}] {desc} — block {receipt.blockNumber}, gas {receipt.gasUsed}")
    return receipt


def main():
    print("=" * 60)
    print("  EMERGENCY RESCUE — ALMVaultV6")
    print("=" * 60)

    w3     = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    assert w3.is_connected(), "RPC not connected"
    print(f"Connected. Block: {w3.eth.block_number}")

    wallet  = w3.to_checksum_address(WALLET)
    vault   = w3.to_checksum_address(VAULT_ADDR)
    vault_c = w3.eth.contract(address=vault,  abi=VAULT_ABI)
    aave_c  = w3.eth.contract(address=w3.to_checksum_address(AAVE_POOL), abi=AAVE_ABI)
    usdc_c  = w3.eth.contract(address=w3.to_checksum_address(USDC), abi=ERC20_ABI)
    weth_c  = w3.eth.contract(address=w3.to_checksum_address(WETH), abi=ERC20_ABI)
    npm_c   = w3.eth.contract(address=w3.to_checksum_address("0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"), abi=NPM_ABI)
    eth_oracle = w3.eth.contract(
        address=w3.to_checksum_address("0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70"),
        abi=CHAINLINK_ABI
    )

    # Pre-flight
    token_id  = vault_c.functions.currentTokenId().call()
    liquidity = vault_c.functions.currentLiquidity().call()
    aave_d    = aave_c.functions.getUserAccountData(vault).call()
    free_usdc = usdc_c.functions.balanceOf(vault).call()
    eth_price = eth_oracle.functions.latestRoundData().call()[1] / 1e8

    print(f"\n  ETH price     : ${eth_price:.2f}")
    print(f"  Token ID      : {token_id}")
    print(f"  Liquidity     : {liquidity}")
    print(f"  Aave Coll     : ${aave_d[0]/1e8:.6f}")
    print(f"  Aave Debt     : ${aave_d[1]/1e8:.6f}")
    print(f"  Free USDC     : ${free_usdc/1e6:.6f}")

    # Get exact WETH debt amount from positions NFT liquidity info
    # and compute an exact repay amount
    weth_debt_approx = 0
    if token_id != 0:
        try:
            pos = npm_c.functions.positions(token_id).call()
            print(f"  NFT liquidity : {pos[7]}")
            print(f"  tokensOwed0   : {pos[10]}")
            print(f"  tokensOwed1   : {pos[11]}")
        except Exception as e:
            print(f"  [WARN] positions() failed: {e}")

    # Calculate exact WETH debt from Aave USD values
    if aave_d[1] > 0 and eth_price > 0:
        weth_debt_approx = int(aave_d[1] / eth_price * 1e18 / 1e8 * 1.02)  # +2% buffer
        print(f"  Est WETH debt : {weth_debt_approx/1e18:.10f} WETH")

    print()
    print("STEP 1: Rebalance — close Uni + repay exact WETH debt + withdraw all aUSDC")

    # Use exact repay amount (not MAX) to avoid potential issues
    # Also use a sensible MAX for USDC withdraw
    usdc_withdraw = (2**128) - 1  # MAX_UINT128 (Aave uses this safely)
    weth_repay    = weth_debt_approx if weth_debt_approx > 0 else 0

    payload = eth_encode(
        ['bool','int256','uint256','uint256','int24','int24','uint256','uint256','uint24','uint256','uint256','uint256','uint256'],
        [
            False,           # isRebalance
            0,               # aaveDebtAdjustment
            0,               # amountUSDC to supply
            0,               # amountWETHToBorrow
            0,               # newTickLower
            0,               # newTickUpper
            0,               # amount0Desired (no new position)
            0,               # amount1Desired
            500,             # poolFee (ignored)
            weth_repay,      # amountWETHToRepay (exact or 0)
            usdc_withdraw,   # amountUSDCToWithdraw (MAX_UINT128)
            0,               # amount0Min
            0,               # amount1Min
        ]
    )

    # Simulate first
    try:
        vault_c.functions.rebalance(payload).call({'from': wallet})
        print("  [SIM OK] Rebalance simulation passed.")
    except Exception as e:
        print(f"  [SIM FAIL] {e}")
        print("  Trying with wethRepay=0 (accept residual debt)...")
        payload = eth_encode(
            ['bool','int256','uint256','uint256','int24','int24','uint256','uint256','uint24','uint256','uint256','uint256','uint256'],
            [False, 0, 0, 0, 0, 0, 0, 0, 500, 0, usdc_withdraw, 0, 0]
        )
        try:
            vault_c.functions.rebalance(payload).call({'from': wallet})
            print("  [SIM OK] Rebalance (no repay) simulation passed.")
        except Exception as e2:
            print(f"  [SIM FAIL] Even no-repay fails: {e2}")
            print("\n  Falling back to STEP 2: direct rescueFunds only (free USDC).")
            if free_usdc > 0:
                print(f"\nSTEP 2: rescueFunds — pulling ${free_usdc/1e6:.6f} free USDC")
                receipt = send_tx(
                    w3, vault_c.functions.rescueFunds(
                        w3.to_checksum_address(USDC), free_usdc
                    ), wallet, PRIV_KEY, "rescueFunds(USDC)"
                )
            print("\n  [NOTE] Aave positions (${:.4f} coll - ${:.4f} debt) remain.".format(
                aave_d[0]/1e8, aave_d[1]/1e8))
            print("  These can be managed via Aave UI: https://app.aave.com")
            return

    receipt = send_tx(w3, vault_c.functions.rebalance(payload), wallet, PRIV_KEY, "Emergency Rebalance")

    if receipt.status != 1:
        print("[CRITICAL] Rebalance failed. Check tx on Basescan.")
        sys.exit(1)

    time.sleep(3)

    # Post-rebalance
    free_usdc2 = usdc_c.functions.balanceOf(vault).call()
    free_weth2 = weth_c.functions.balanceOf(vault).call()
    aave_d2    = aave_c.functions.getUserAccountData(vault).call()
    print(f"\n  POST-REBALANCE:")
    print(f"  Free USDC in vault : ${free_usdc2/1e6:.6f}")
    print(f"  Free WETH in vault : {free_weth2/1e18:.8f}")
    print(f"  Aave Collateral    : ${aave_d2[0]/1e8:.6f}")
    print(f"  Aave Debt          : ${aave_d2[1]/1e8:.6f}")

    if free_usdc2 == 0:
        print("\n  No USDC to rescue. Done.")
        return

    # STEP 2: rescueFunds
    print(f"\nSTEP 2: rescueFunds — pulling ${free_usdc2/1e6:.6f} USDC to deployer wallet")
    receipt2 = send_tx(
        w3,
        vault_c.functions.rescueFunds(w3.to_checksum_address(USDC), free_usdc2),
        wallet, PRIV_KEY, "rescueFunds(USDC)"
    )

    # Also rescue any WETH if present
    if free_weth2 > 0:
        print(f"\nSTEP 3: rescueFunds — pulling {free_weth2/1e18:.8f} WETH to deployer")
        receipt3 = send_tx(
            w3,
            vault_c.functions.rescueFunds(w3.to_checksum_address(WETH), free_weth2),
            wallet, PRIV_KEY, "rescueFunds(WETH)"
        )

    # Final state
    time.sleep(2)
    wallet_usdc = usdc_c.functions.balanceOf(wallet).call()
    vault_usdc  = usdc_c.functions.balanceOf(vault).call()
    aave_final  = aave_c.functions.getUserAccountData(vault).call()

    print(f"\n{'='*60}")
    print(f"  FINAL STATE:")
    print(f"  Deployer USDC    : ${wallet_usdc/1e6:.6f}")
    print(f"  Vault USDC left  : ${vault_usdc/1e6:.6f}")
    print(f"  Aave Coll left   : ${aave_final[0]/1e8:.6f}")
    print(f"  Aave Debt left   : ${aave_final[1]/1e8:.6f}")
    print(f"{'='*60}")
    if aave_final[0] > 0 or aave_final[1] > 0:
        print(f"  [NOTE] Residual Aave position remains.")
        print(f"  Manage at: https://app.aave.com/")
    print("[DONE] Emergency Rescue complete.")


if __name__ == "__main__":
    main()
