"""
dashboard.py — Live Portfolio Dashboard for ALM Vault V3.
Run:  python dashboard.py
"""
import os
import sys
import json
import logging
import time
from decimal import Decimal

from web3 import Web3
from dotenv import load_dotenv

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from pnl_tracker import get_net_deposit_onchain

logging.basicConfig(level=logging.WARNING)  # suppress web3 noise in dashboard

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_pnl.json")
MAX_UINT128 = 2 ** 128 - 1

# ── ABIs ─────────────────────────────────────────────────────────────────────
AAVE_ABI = [{
    "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
    "name": "getUserAccountData",
    "outputs": [
        {"internalType": "uint256", "name": "totalCollateralBase",           "type": "uint256"},
        {"internalType": "uint256", "name": "totalDebtBase",                 "type": "uint256"},
        {"internalType": "uint256", "name": "availableBorrowsBase",          "type": "uint256"},
        {"internalType": "uint256", "name": "currentLiquidationThreshold",   "type": "uint256"},
        {"internalType": "uint256", "name": "ltv",                           "type": "uint256"},
        {"internalType": "uint256", "name": "healthFactor",                  "type": "uint256"},
    ],
    "stateMutability": "view",
    "type": "function",
}]

NPM_COLLECT_ABI = [{
    "inputs": [{
        "components": [
            {"internalType": "uint256", "name": "tokenId",    "type": "uint256"},
            {"internalType": "address", "name": "recipient",  "type": "address"},
            {"internalType": "uint128", "name": "amount0Max", "type": "uint128"},
            {"internalType": "uint128", "name": "amount1Max", "type": "uint128"},
        ],
        "internalType": "struct INonfungiblePositionManager.CollectParams",
        "name": "params",
        "type": "tuple",
    }],
    "name": "collect",
    "outputs": [
        {"internalType": "uint256", "name": "amount0", "type": "uint256"},
        {"internalType": "uint256", "name": "amount1", "type": "uint256"},
    ],
    "stateMutability": "payable",
    "type": "function",
}]

VAULT_ABI_MIN = [{
    "inputs": [],
    "name": "currentTokenId",
    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
    "stateMutability": "view",
    "type": "function",
}]

NPM_DECREASE_ABI = [{
    "inputs": [{
        "components": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "internalType": "struct INonfungiblePositionManager.DecreaseLiquidityParams",
        "name": "params",
        "type": "tuple"
    }],
    "name": "decreaseLiquidity",
    "outputs": [
        {"internalType": "uint256", "name": "amount0", "type": "uint256"},
        {"internalType": "uint256", "name": "amount1", "type": "uint256"}
    ],
    "stateMutability": "payable",
    "type": "function"
}, {
    "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
    "name": "positions",
    "outputs": [
        {"internalType": "uint96", "name": "nonce", "type": "uint96"},
        {"internalType": "address", "name": "operator", "type": "address"},
        {"internalType": "address", "name": "token0", "type": "address"},
        {"internalType": "address", "name": "token1", "type": "address"},
        {"internalType": "uint24", "name": "fee", "type": "uint24"},
        {"internalType": "int24", "name": "tickLower", "type": "int24"},
        {"internalType": "int24", "name": "tickUpper", "type": "int24"},
        {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
        {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
        {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
        {"internalType": "uint128", "name": "tokensOwed0", "type": "uint128"},
        {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"}
    ],
    "stateMutability": "view",
    "type": "function"
}]

ERC20_ABI = [{
    "constant": True,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "type": "function",
}]

CHAINLINK_ABI = [{
    "inputs": [],
    "name": "latestRoundData",
    "outputs": [
        {"internalType": "uint80",  "name": "roundId",         "type": "uint80"},
        {"internalType": "int256",  "name": "answer",          "type": "int256"},
        {"internalType": "uint256", "name": "startedAt",       "type": "uint256"},
        {"internalType": "uint256", "name": "updatedAt",       "type": "uint256"},
        {"internalType": "uint80",  "name": "answeredInRound", "type": "uint80"},
    ],
    "stateMutability": "view",
    "type": "function",
}]


def load_state() -> dict:
    state = {
        "gas_spent_usd": 0.0,
        "deposit_timestamp": time.time() - 3600  # fallback 1 hour
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                state["gas_spent_usd"] = d.get("gas_spent_usd", 0.0)
                state["deposit_timestamp"] = d.get("deposit_timestamp", state["deposit_timestamp"])
        except Exception:
            pass
    return state


def main():
    w3 = Web3(Web3.HTTPProvider(config.RPC_URL, request_kwargs={"timeout": 15}))
    if not w3.is_connected():
        print("❌ RPC not connected.")
        sys.exit(1)

    vault_addr = w3.to_checksum_address(config.VAULT_ADDRESS)

    # ── ETH price ────────────────────────────────────────────────────────────
    oracle   = w3.eth.contract(address=w3.to_checksum_address(config.CHAINLINK_ETH), abi=CHAINLINK_ABI)
    eth_price = float(Decimal(oracle.functions.latestRoundData().call()[1]) / Decimal(10**8))

    # ── Aave account data ─────────────────────────────────────────────────────
    aave  = w3.eth.contract(address=w3.to_checksum_address(config.AAVE_POOL), abi=AAVE_ABI)
    acct  = aave.functions.getUserAccountData(vault_addr).call()
    coll  = float(acct[0]) / 1e8
    debt  = float(acct[1]) / 1e8
    hf    = float(acct[5]) / 1e18 if acct[5] != (2**256 - 1) else float("inf")

    # ── Free Balances ──────────────────────────────────────────────────────────
    usdc_c  = w3.eth.contract(address=w3.to_checksum_address(config.USDC), abi=ERC20_ABI)
    usdc_bal = usdc_c.functions.balanceOf(vault_addr).call() / 1e6
    usdc_worth = usdc_bal
    
    weth_c  = w3.eth.contract(address=w3.to_checksum_address(config.WETH), abi=ERC20_ABI)
    weth_bal = weth_c.functions.balanceOf(vault_addr).call() / 1e18
    weth_worth = weth_bal * eth_price

    # ── Uniswap V3 fees (simulate collect) ───────────────────────────────────
    vault_c  = w3.eth.contract(address=vault_addr, abi=VAULT_ABI_MIN)
    npm      = w3.eth.contract(address=w3.to_checksum_address(config.UNI_V3_NPM), abi=NPM_COLLECT_ABI)

    token_id     = 0
    fee0_weth    = 0.0
    fee1_usdc    = 0.0
    try:
        token_id = vault_c.functions.currentTokenId().call()
        if token_id != 0:
            res      = npm.functions.collect((token_id, vault_addr, MAX_UINT128, MAX_UINT128)).call(
                {"from": vault_addr}
            )
            fee0_weth = res[0] / 1e18
            fee1_usdc = res[1] / 1e6
            
    except Exception:
        pass  # position may be empty or collect call unsupported by node
        
    # ── Uniswap V3 Principal (simulate decreaseLiquidity) ────────────────────
    npm_dec = w3.eth.contract(address=w3.to_checksum_address(config.UNI_V3_NPM), abi=NPM_DECREASE_ABI)
    nft_weth = 0.0
    nft_usdc = 0.0
    nft_worth_usd = 0.0
    if token_id != 0:
        try:
            pos = npm_dec.functions.positions(token_id).call()
            liquidity = pos[7]
            if liquidity > 0:
                dec_res = npm_dec.functions.decreaseLiquidity((
                    token_id,
                    liquidity,
                    0,
                    0,
                    int(time.time() + 60)
                )).call({"from": vault_addr})
                nft_weth = dec_res[0] / 1e18
                nft_usdc = dec_res[1] / 1e6
                nft_worth_usd = nft_weth * eth_price + nft_usdc
        except Exception as e:
            logging.warning(f"Failed to fetch NFT principal: {e}")

    # ── PnL & APR ─────────────────────────────────────────────────────────────
    state       = load_state()
    tvl         = (coll - debt) + usdc_worth + weth_worth + nft_worth_usd
    gas_spent   = state["gas_spent_usd"]
    init_dep    = get_net_deposit_onchain(w3, vault_addr)
    net_profit  = tvl - gas_spent - init_dep
    fee_usd     = fee0_weth * eth_price + fee1_usdc

    elapsed_sec = time.time() - state["deposit_timestamp"]
    elapsed_hours = max(elapsed_sec / 3600.0, 0.01)
    if init_dep > 0:
        apr = (fee_usd / init_dep) * (8760 / elapsed_hours) * 100
    else:
        apr = 0.0

    # ── Display ───────────────────────────────────────────────────────────────
    sep = "─" * 44
    print(f"\n{'='*44}")
    print(f"  ALM Vault V3 Dashboard  |  ETH=${eth_price:.2f}")
    print(f"{'='*44}")
    print(f"  Vault:          {vault_addr[:20]}…")
    print(sep)
    print(f"  {'Total TVL':20} ${tvl:>10.4f}")
    print(sep)
    print(f"  {'Aave Collateral':20} ${coll:>10.4f}")
    print(f"  {'Aave Debt':20} ${debt:>10.4f}")
    print(f"  {'Health Factor':20}  {hf:>10.2f}")
    print(sep)
    print(f"  {'Free USDC in Vault':20} ${usdc_worth:>10.4f}")
    print(f"  {'Free WETH in Vault':20} ${weth_worth:>10.4f}")
    print(sep)
    print(f"  {'Uni V3 Token ID':20}  {token_id if token_id else 'None':>10}")
    print(f"  {'NFT WETH':20}  {nft_weth:>10.6f}")
    print(f"  {'NFT USDC':20}  {nft_usdc:>10.4f}")
    print(f"  {'NFT Value':20} ${nft_worth_usd:>10.4f}")
    print(f"  {'Unclaimed WETH fees':20}  {fee0_weth:>10.6f}  (${fee0_weth*eth_price:.4f})")
    print(f"  {'Unclaimed USDC fees':20}  {fee1_usdc:>10.4f}  (${fee1_usdc:.4f})")
    print(f"  {'Total Unclaimed $':20} ${fee_usd:>10.4f}")
    print(f"  {'Current APR':20}  {apr:>10.2f}%")
    print(sep)
    print(f"  {'Initial Deposit':20} ${init_dep:>10.4f}")
    print(f"  {'Gas Spent':20} ${gas_spent:>10.4f}")
    print(f"  {'Net Profit':20} ${net_profit:>+10.4f}")
    
    daily_gross_yield_usd = (tvl * apr) / 365 / 100
    daily_gas_cost_usd = 0.0180
    net_daily_profit = daily_gross_yield_usd - daily_gas_cost_usd
    profit_status = "(PROFITABLE)" if net_daily_profit > 0 else "(UNPROFITABLE - INCREASE TVL)"
    
    print(sep)
    print("  ESTIMATED DAILY METRICS:")
    print(f"  Est. Gross Yield/Day: ${daily_gross_yield_usd:.4f}")
    print(f"  Est. Gas Cost/Day:    ${daily_gas_cost_usd:.4f}")
    print(f"  Net Profit/Day:       ${net_daily_profit:+.4f} {profit_status}")
    print(f"{'='*44}\n")


if __name__ == "__main__":
    main()
