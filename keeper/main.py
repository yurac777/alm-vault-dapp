"""
main.py — The Money Printer: Autonomous ALM Vault SRE Loop (Uniswap V3).
Interval: 15 minutes. Rebalances only when price exits tick range or is initially empty.
No --force flag in production. All addresses centralised in config.py.
"""
import os
import sys
import time
import csv
import argparse
import logging
from logging.handlers import RotatingFileHandler
import web3.exceptions
from datetime import datetime, timezone
from decimal import Decimal
import subprocess
import json

# ── Bootstrap path ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
import config
from core.state_reader import StateReader
from core.encoder import encode_rebalance_payload_v3
from core.ai_oracle import AIOracle
from connectors.base_rpc import BaseConnector
from pnl_tracker import calculate_pnl_onchain, add_gas_spent
from core import telegram_reporter
from core.math import get_liquidity_for_amounts, tick_to_sqrt_ratio_x96, get_amounts_for_liquidity

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler("keeper.log", mode='a', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("KeeperMain")

# ── ABIs ────────────────────────────────────────────────────────────────────
VAULT_ABI = [
    {
        "inputs": [{"internalType": "bytes", "name": "data", "type": "bytes"}],
        "name": "rebalance",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "currentLiquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "currentTokenId",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

NPM_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "positions",
        "outputs": [
            {"internalType": "uint96",  "name": "nonce",                      "type": "uint96"},
            {"internalType": "address", "name": "operator",                   "type": "address"},
            {"internalType": "address", "name": "token0",                     "type": "address"},
            {"internalType": "address", "name": "token1",                     "type": "address"},
            {"internalType": "uint24",  "name": "fee",                        "type": "uint24"},
            {"internalType": "int24",   "name": "tickLower",                  "type": "int24"},
            {"internalType": "int24",   "name": "tickUpper",                  "type": "int24"},
            {"internalType": "uint128", "name": "liquidity",                  "type": "uint128"},
            {"internalType": "uint256", "name": "feeGrowthInside0LastX128",   "type": "uint256"},
            {"internalType": "uint256", "name": "feeGrowthInside1LastX128",   "type": "uint256"},
            {"internalType": "uint128", "name": "tokensOwed0",                "type": "uint128"},
            {"internalType": "uint128", "name": "tokensOwed1",                "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]

L1_ORACLE_ABI = [
    {
        "inputs": [{"internalType": "bytes", "name": "_data", "type": "bytes"}],
        "name": "getL1Fee",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]

CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_log.csv")


# ── Helpers ──────────────────────────────────────────────────────────────────
def append_to_csv(timestamp, eth_price, net_worth, gas_spent, profit, llm_decision, action_taken):
    file_exists = os.path.isfile(CSV_FILE)
    try:
        with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ["Timestamp", "ETH_Price", "Net_Worth_USD", "Gas_Spent_USD",
                     "Profit_USD", "LLM_Decision", "Action_Taken"]
                )
            writer.writerow([timestamp, eth_price, net_worth, gas_spent, profit, llm_decision, action_taken])
    except Exception as exc:
        logger.error("CSV write error: %s", exc)

def export_json_and_push():
    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            lines = list(csv.DictReader(f))
        last_50 = lines[-50:]
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "pnl_history.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(last_50, f)
        
        # Git operations (Anti-Silent Fail)
        subprocess.run(["git", "add", json_path], check=True, cwd=os.path.dirname(json_path))
        subprocess.run(["git", "commit", "-m", "update pnl history"], check=False, cwd=os.path.dirname(json_path))
        subprocess.run(["git", "push"], check=False, cwd=os.path.dirname(json_path))
        logger.info("[Git] PnL history pushed to repo.")
    except Exception as e:
        logger.error("[Git] Error pushing PnL history: %s", e)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ALM Vault V3 SRE Loop")
    parser.add_argument("--force",    action="store_true", help="Force rebalance ignoring profitability threshold")
    parser.add_argument("--run-once", action="store_true", help="Run a single iteration then exit")
    args = parser.parse_args()
    force_mode = args.force
    run_once   = args.run_once

    logger.info("=== Initialising ALM Vault Keeper (Uniswap V3) ===")

    if not all([config.RPC_URL, config.PRIVATE_KEY, config.WALLET, config.VAULT_ADDRESS]):
        logger.error("Missing required .env variables. Aborting.")
        return

    connector = BaseConnector(config.RPC_URL)
    w3 = connector.w3

    while not connector.is_connected():
        logger.warning("Cannot connect to Base Mainnet — rotating RPC …")
        connector.rotate_rpc()
        w3 = connector.w3
        time.sleep(2)

    logger.info("Connected! Latest block: %d", connector.get_latest_block_number())
    telegram_reporter.send_startup_message()

    reader    = StateReader(connector)
    ai_oracle = AIOracle()

    wallet = w3.to_checksum_address(config.WALLET)
    vault  = w3.to_checksum_address(config.VAULT_ADDRESS)

    usdc_contract  = w3.eth.contract(address=w3.to_checksum_address(config.USDC),     abi=ERC20_ABI)
    vault_contract = w3.eth.contract(address=vault,                                     abi=VAULT_ABI)
    npm_contract   = w3.eth.contract(address=w3.to_checksum_address(config.UNI_V3_NPM), abi=NPM_ABI)
    l1_oracle      = w3.eth.contract(address=w3.to_checksum_address(config.L1_GAS_ORACLE), abi=L1_ORACLE_ABI)

    loop_count = 0
    tick_down_delta = 200
    tick_up_delta = 200
    current_target_hf = Decimal(str(config.TARGET_HEALTH_FACTOR))

    while True:
        action_taken = "No Action"
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        try:
            logger.info("--- [Iteration %d] ---", loop_count)
            if loop_count >= 2:
                logger.info("Stopping after 2 iterations to show proof.")
                break

            # ── Read state ───────────────────────────────────────────────
            try:
                eth_price  = reader.get_eth_price()
                tick_data  = reader.get_current_tick(eth_price, tick_spacing=config.POOL_TICK_SPACING)
                current_tick  = tick_data["exact_tick"]
                aligned_tick  = tick_data["aligned_tick"]
                is_onchain    = tick_data["is_onchain_tick"]
                tick_src = "V3 slot0" if is_onchain else "Chainlink"
                logger.info("[TickEngine] tick=%d (%s)  ETH=$%.2f", current_tick, tick_src, eth_price)

                total_usdc_wei   = usdc_contract.functions.balanceOf(vault).call()
                current_liquidity = vault_contract.functions.currentLiquidity().call()
                current_token_id  = vault_contract.functions.currentTokenId().call()

                nft_value_usd = 0.0
                expected_fees_weth = 0
                expected_fees_usdc = 0
                if current_token_id != 0:
                    pos = npm_contract.functions.positions(current_token_id).call()
                    old_tick_lower, old_tick_upper = pos[5], pos[6]
                    liq = pos[7]
                    sqrtPriceX96 = tick_data.get("sqrt_price_x96", 0)
                    if sqrtPriceX96 > 0:
                        amt0, amt1 = get_amounts_for_liquidity(sqrtPriceX96, old_tick_lower, old_tick_upper, liq)
                        nft_value_usd = float(Decimal(amt0) / Decimal(10**18) * eth_price) + (amt1 / 1e6)
                    
                    # Off-chain Zero-Dust Compounding: Fetch expected fees to add to virtual capital
                    NPM_COLLECT_ABI = [{
                        "inputs": [{
                            "components": [
                                {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                                {"internalType": "address", "name": "recipient", "type": "address"},
                                {"internalType": "uint128", "name": "amount0Max", "type": "uint128"},
                                {"internalType": "uint128", "name": "amount1Max", "type": "uint128"}
                            ],
                            "internalType": "struct INonfungiblePositionManager.CollectParams",
                            "name": "params", "type": "tuple"
                        }],
                        "name": "collect",
                        "outputs": [
                            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
                            {"internalType": "uint256", "name": "amount1", "type": "uint256"}
                        ],
                        "stateMutability": "payable",
                        "type": "function"
                    }]
                    npm_collect_c = w3.eth.contract(address=config.UNI_V3_NPM, abi=NPM_COLLECT_ABI)
                    MAX_UINT128 = 2**128 - 1
                    try:
                        res = npm_collect_c.functions.collect((current_token_id, vault, MAX_UINT128, MAX_UINT128)).call({"from": vault})
                        expected_fees_weth = res[0]
                        expected_fees_usdc = res[1]
                        logger.info(f"[Zero-Dust] Expected Fees: {expected_fees_weth/1e18:.6f} WETH, {expected_fees_usdc/1e6:.6f} USDC")
                        nft_value_usd += float(Decimal(expected_fees_weth) / Decimal(10**18) * eth_price) + (expected_fees_usdc / 1e6)
                    except Exception as e:
                        logger.warning(f"Static call to collect failed: {e}")
                else:
                    old_tick_lower, old_tick_upper = 0, 0

            except Exception as exc:
                logger.error("State read error: %s — skipping iteration.", exc)
                telegram_reporter.send_error_message(f"State read error: {exc}")
                time.sleep(15)
                continue

            # ── PnL ──────────────────────────────────────────────────────
            pnl = calculate_pnl_onchain(w3, vault, total_usdc_wei, config.AAVE_POOL, nft_value_usd)
            logger.info("[PnL] TVL=$%.4f  GasSpent=$%.4f  NetProfit=%+.4f$",
                        pnl["net_worth"], pnl["gas_spent"], pnl["net_profit"])

            # ── AI Oracle (every 4 iters) ─────────────────────────────────
            if loop_count % 4 == 0:
                logger.info("[AIOracle] Requesting directional tick recommendation …")
                trend, tick_down_delta, tick_up_delta = ai_oracle.get_directional_ticks(float(eth_price))
                logger.info("[AIOracle] Trend=%s | tickDown=%d | tickUp=%d", trend, tick_down_delta, tick_up_delta)
                
                # Dynamic HF calculation
                current_target_hf = Decimal(str(config.TARGET_HEALTH_FACTOR))
                if trend == "bullish":
                    current_target_hf = current_target_hf + Decimal("0.4")
                elif trend == "bearish":
                    current_target_hf = max(Decimal("1.1"), current_target_hf - Decimal("0.3"))
                logger.info("[SRE] Dynamic HF set to %.2f (Base: %.2f)", current_target_hf, config.TARGET_HEALTH_FACTOR)

            new_tick_lower = aligned_tick - tick_down_delta
            new_tick_upper = aligned_tick + tick_up_delta

            # ── Gas estimate ─────────────────────────────────────────────
            try:
                gas_params  = connector.get_optimal_gas_fee()
                dummy_call  = b"\x00" * 350
                l1_fee_wei  = l1_oracle.functions.getL1Fee(dummy_call).call()
            except Exception as exc:
                logger.error("Gas params error: %s — skipping.", exc)
                telegram_reporter.send_error_message(f"Gas params error: {exc}")
                time.sleep(15)
                continue

            base_fee_gwei = float(Decimal(gas_params["maxFeePerGas"]) / Decimal(10 ** 9))
            l2_gas_wei    = 150_000 * gas_params["maxFeePerGas"]
            total_gas_wei = l2_gas_wei + l1_fee_wei
            est_gas_usd   = float(Decimal(total_gas_wei) / Decimal(10 ** 18)) * float(eth_price)

            if base_fee_gwei > 0.05:
                profit_multiplier = 5.0
                logger.info("[GasEngine] High congestion (%.4f gwei) — 5x threshold", base_fee_gwei)
            elif base_fee_gwei < 0.01:
                profit_multiplier = 1.5
                logger.info("[GasEngine] Low congestion (%.4f gwei) — 1.5x threshold", base_fee_gwei)
            else:
                profit_multiplier = 3.0
                logger.info("[GasEngine] Normal congestion (%.4f gwei) — 3x threshold", base_fee_gwei)

            logger.info("[GasEngine] EstCost=$%.4f", est_gas_usd)

            # ── Decision logic ───────────────────────────────────────────
            is_rebalance       = False
            amount_usdc_to_aave = 0.0
            amount_weth_borrow  = 0.0
            aave_debt_adj       = 0
            need_transaction    = False

            if current_liquidity == 0:
                logger.info("[SRE] Position empty — Initial Open.")
                if total_usdc_wei == 0:
                    logger.warning("Vault is empty. Halting.")
                    break
                total_usdc_human    = float(total_usdc_wei) / 1e6
                amount_usdc_to_aave = total_usdc_human / (1 + 0.80 / float(current_target_hf))
                amount_weth_borrow  = (total_usdc_human - amount_usdc_to_aave) / float(eth_price)
                need_transaction    = True
                action_taken        = "Initial Open"

            elif force_mode:
                logger.info("[SRE] FORCE mode — forced rebalance.")
                is_rebalance     = True
                need_transaction = True
                action_taken     = "Forced Rebalance"

            else:
                buf = 20
                if (old_tick_lower + buf) < current_tick < (old_tick_upper - buf):
                    logger.info("[SRE] Price in-range [%d, %d] — no action.", old_tick_lower, old_tick_upper)
                    action_taken = "Skipped (In-Range)"
                    telegram_reporter.send_message(
                        f"ℹ️ In-range tick={current_tick} [{old_tick_lower},{old_tick_upper}]"
                    )
                else:
                    logger.warning("[SRE] BOUNDARY HIT tick=%d [%d,%d] — rebalancing!", current_tick, old_tick_lower, old_tick_upper)
                    telegram_reporter.send_message(
                        f"🚨 Boundary hit! tick={current_tick} — rebalancing position."
                    )
                    is_rebalance     = True
                    need_transaction = True
                    action_taken     = "Boundary Rebalance"

            # ── Build and send transaction ────────────────────────────────
            if need_transaction:
                if action_taken != "Initial Open":
                    # For Rebalances (Forced or Boundary), compute using virtual total capital
                    virtual_capital_usd = pnl["net_worth"]
                    logger.info(f"[Math Engine] Using Virtual Capital (incl. expected fees): ${virtual_capital_usd:.4f}")
                    amount_usdc_to_aave = virtual_capital_usd / (1 + 0.80 / float(current_target_hf))
                    amount_weth_borrow  = (virtual_capital_usd - amount_usdc_to_aave) / float(eth_price)

                amountUSDC_wei    = int(amount_usdc_to_aave * 1e6)
                amountWETH_wei    = int(amount_weth_borrow  * 1e18)
                
                if action_taken != "Initial Open":
                    # For rebalance, we want to supply/borrow the DIFF between target and current Aave balances.
                    # Current Aave collateral in USDC wei:
                    current_aave_coll_wei = int(pnl["aave_collateral"] * 1e6)
                    # Current Aave debt in WETH wei:
                    current_aave_debt_wei = int(pnl["aave_debt"] / float(eth_price) * 1e18) if float(eth_price) > 0 else 0
                    
                    # We calculate exactly what tokens we physically hold after decreaseLiquidity
                    weth_contract = w3.eth.contract(address=w3.to_checksum_address(config.WETH), abi=[{"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}])
                    idle_weth = weth_contract.functions.balanceOf(vault).call()
                    max_weth_available = idle_weth + expected_fees_weth + int(amt0)
                    
                    # aave_debt_adj > 0 means borrow more WETH. < 0 means repay WETH.
                    aave_debt_adj = amountWETH_wei - current_aave_debt_wei
                    
                    # Prevent STF on Aave repay by capping the repayment to physical WETH available
                    if aave_debt_adj < 0 and abs(aave_debt_adj) > max_weth_available:
                        logger.warning(f"[SRE] Capping Aave repay to available WETH! Target: {abs(aave_debt_adj)}, Available: {max_weth_available}")
                        aave_debt_adj = -max_weth_available
                    
                    # For USDC, amountUSDC in payload means Supply. amountUSDCToWithdraw means Withdraw.
                    # We pass the DIFF to ALMVault
                    coll_diff_wei = amountUSDC_wei - current_aave_coll_wei
                    amountUSDC_payload = coll_diff_wei if coll_diff_wei > 0 else 0
                    amountUSDCToWithdraw_payload = -coll_diff_wei if coll_diff_wei < 0 else 0
                    
                    # For Uniswap mint, allocate exactly what's left after Aave operations.
                    # If coll_diff_wei > 0, we SUPPLY to Aave, meaning we have LESS physical USDC for Uni.
                    # If coll_diff_wei < 0, we WITHDRAW from Aave, meaning we have MORE physical USDC for Uni.
                    usdc_for_uni = (total_usdc_wei + expected_fees_usdc + int(amt1)) - coll_diff_wei
                    # Same for WETH: If aave_debt_adj > 0, we BORROW from Aave, meaning MORE physical WETH for Uni.
                    # If aave_debt_adj < 0, we REPAY Aave, meaning LESS physical WETH for Uni.
                    weth_for_uni = max_weth_available + aave_debt_adj
                    
                    # Add 1% safety margin for V3 rounding math to prevent STF on mint
                    usdc_for_uni = int(usdc_for_uni * 0.99) if usdc_for_uni > 0 else 0
                    weth_for_uni = int(weth_for_uni * 0.99) if weth_for_uni > 0 else 0
                    logger.info(f"[Zero-Dust] Passing safe balances to Uni: WETH={weth_for_uni/1e18:.6f}, USDC={usdc_for_uni/1e6:.6f}")
                else:
                    # Initial Open logic
                    total_usdc_human = float(total_usdc_wei) / 1e6
                    usdc_for_uni     = int((total_usdc_human - amount_usdc_to_aave) * 1e6)
                    weth_for_uni     = amountWETH_wei
                    amountUSDC_payload = amountUSDC_wei
                    amountUSDCToWithdraw_payload = 0

                sqrt_px96 = tick_to_sqrt_ratio_x96(current_tick)
                L_raw = get_liquidity_for_amounts(
                    sqrt_price_x96=sqrt_px96,
                    tick_lower=new_tick_lower,
                    tick_upper=new_tick_upper,
                    amount0=weth_for_uni,
                    amount1=usdc_for_uni,
                )
                req_weth, req_usdc = get_amounts_for_liquidity(sqrt_px96, new_tick_lower, new_tick_upper, L_raw)
                
                # SRE Capital Optimization (95%+ Efficiency)
                # We need exactly req_usdc and req_weth. We add a 3% cash buffer for slippage during minting.
                usdc_needed_safe = int(req_usdc * 1.03)
                weth_needed_safe = int(req_weth * 1.03)
                
                excess_usdc = usdc_for_uni - usdc_needed_safe
                if excess_usdc > 0:
                    logger.info(f"[SRE] Capital Optimization: Reallocating {excess_usdc/1e6:.4f} excess USDC to Aave")
                    usdc_for_uni = usdc_needed_safe
                    if action_taken == "Initial Open":
                        amountUSDC_payload += excess_usdc
                    else:
                        coll_diff_wei += excess_usdc
                        amountUSDC_payload = coll_diff_wei if coll_diff_wei > 0 else 0
                        amountUSDCToWithdraw_payload = -coll_diff_wei if coll_diff_wei < 0 else 0

                excess_weth = weth_for_uni - weth_needed_safe
                if excess_weth > 0:
                    logger.info(f"[SRE] Capital Optimization: Reducing WETH borrow by {excess_weth/1e18:.4f}")
                    weth_for_uni = weth_needed_safe
                    if action_taken == "Initial Open":
                        amountWETH_wei -= excess_weth
                    else:
                        aave_debt_adj -= excess_weth
                        if aave_debt_adj < 0 and abs(aave_debt_adj) > max_weth_available:
                            aave_debt_adj = -max_weth_available

                # Recalculate L safely for the new reduced amounts
                L = get_liquidity_for_amounts(
                    sqrt_price_x96=sqrt_px96,
                    tick_lower=new_tick_lower,
                    tick_upper=new_tick_upper,
                    amount0=weth_for_uni,
                    amount1=usdc_for_uni,
                )

                logger.debug("amountUSDC=%d  amountWETH=%d  usdcUni=%d  wethUni=%d  L=%d",
                             amountUSDC_payload, amountWETH_wei, usdc_for_uni, weth_for_uni, L)

                payload_hex   = encode_rebalance_payload_v3(
                    isRebalance=is_rebalance,
                    aaveDebtAdjustment=aave_debt_adj,
                    amountUSDC=amountUSDC_payload,
                    amountWETHToBorrow=amountWETH_wei if action_taken == "Initial Open" else 0, # handled by aaveDebtAdjustment for rebalance
                    newTickLower=new_tick_lower,
                    newTickUpper=new_tick_upper,
                    amount0Desired=weth_for_uni,
                    amount1Desired=usdc_for_uni,
                    poolFee=config.POOL_FEE,
                    amountWETHToRepay=abs(aave_debt_adj) if aave_debt_adj < 0 else 0,
                    amountUSDCToWithdraw=amountUSDCToWithdraw_payload,
                )
                payload_bytes = w3.to_bytes(hexstr=payload_hex)
                nonce         = w3.eth.get_transaction_count(wallet, "pending")

                rebalance_tx = vault_contract.functions.rebalance(payload_bytes).build_transaction({
                    "from":                 wallet,
                    "nonce":                nonce,
                    "maxFeePerGas":         gas_params["maxFeePerGas"],
                    "maxPriorityFeePerGas": gas_params["maxPriorityFeePerGas"],
                    "gas":                  5_000_000,
                })

                logger.info("Simulating transaction (estimate_gas) …")
                try:
                    gas_est = w3.eth.estimate_gas(rebalance_tx)
                    rebalance_tx["gas"] = int(gas_est * 1.2)
                except Exception as exc:
                    logger.error("Simulation reverted: %s", exc)
                    action_taken = "Reverted in Simulation"
                    append_to_csv(timestamp_str, eth_price, pnl["net_worth"],
                                  pnl["gas_spent"], pnl["net_profit"], f"{tick_down_delta}/{tick_up_delta}", action_taken)
                    time.sleep(60)
                    continue

                # RBF retry loop
                receipt = None
                for attempt in range(config.MAX_RBF_RETRIES):
                    signed_tx = w3.eth.account.sign_transaction(rebalance_tx, config.PRIVATE_KEY)
                    try:
                        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                        logger.info("Tx sent: %s", tx_hash.hex())
                        try:
                            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                            break
                        except web3.exceptions.TimeExhausted:
                            logger.warning("[RBF] Tx stuck — bumping gas (attempt %d/%d)",
                                           attempt + 1, config.MAX_RBF_RETRIES)
                            rebalance_tx["maxFeePerGas"]         = int(rebalance_tx["maxFeePerGas"] * 1.2)
                            rebalance_tx["maxPriorityFeePerGas"] = int(rebalance_tx["maxPriorityFeePerGas"] * 1.2)
                    except ValueError as exc:
                        if "nonce too low" in str(exc).lower() or "already known" in str(exc).lower():
                            logger.info("Tx already in block/mempool: %s", exc)
                        else:
                            logger.error("RPC send error: %s", exc)
                            action_taken = "Failed Tx"
                        break
                    except Exception as exc:
                        logger.error("Critical send error: %s", exc)
                        telegram_reporter.send_error_message(f"Critical tx error: {exc}")
                        action_taken = "Failed Tx"
                        break

                if receipt and receipt.status == 1:
                    gas_used   = receipt.gasUsed
                    l2_cost    = float(Decimal(rebalance_tx["maxFeePerGas"]) / Decimal(10**18)) * float(eth_price) * gas_used
                    l1_fee_act = receipt.get("l1Fee", 0)
                    if isinstance(l1_fee_act, str):
                        l1_fee_act = int(l1_fee_act, 16)
                    if not l1_fee_act:
                        try:
                            l1_fee_act = l1_oracle.functions.getL1Fee(signed_tx.raw_transaction).call()
                        except Exception:
                            l1_fee_act = 0
                    l1_cost    = float(Decimal(l1_fee_act) / Decimal(10**18)) * float(eth_price)
                    gas_cost   = l2_cost + l1_cost
                    add_gas_spent(gas_cost)
                    logger.info("✅ Rebalance OK  gas=%d  L1=%d wei  total=$%.4f",
                                gas_used, l1_fee_act, gas_cost)
                    telegram_reporter.send_rebalance_message(
                        f"{tick_down_delta}/{tick_up_delta}",
                        float(Decimal(amount_weth_borrow) * Decimal(eth_price)),
                        receipt.transactionHash.hex(),
                    )
                    action_taken = "Rebalanced"
                elif receipt and receipt.status == 0:
                    logger.error("Tx reverted on-chain!")
                    action_taken = "Reverted On-Chain"
                else:
                    logger.warning("All RBF retries exhausted — tx may be stuck.")
                    action_taken = "Stuck in Mempool"

            # ── CSV log ──────────────────────────────────────────────────
            append_to_csv(timestamp_str, float(eth_price), pnl["net_worth"],
                          pnl["gas_spent"], pnl["net_profit"], f"{tick_down_delta}/{tick_up_delta}", action_taken)
            export_json_and_push()

            # ── 4-hour Telegram report ───────────────────────────────────
            if loop_count > 0 and loop_count % 16 == 0:
                telegram_reporter.send_pnl_report(
                    pnl["net_worth"], pnl["net_profit"], pnl["gas_spent"]
                )

            if run_once:
                logger.info("--run-once flag set. Exiting cleanly.")
                break

            loop_count += 1
            logger.info("Sleeping %d s …", config.REBALANCE_SLEEP_SEC)
            time.sleep(config.REBALANCE_SLEEP_SEC)

        except Exception as exc:
            err = str(exc).lower()
            if any(t in err for t in ["429", "too many requests", "connection", "timeout",
                                      "max retries", "disconnected"]):
                logger.warning("[RPC Failover] %s — rotating node.", exc)
                telegram_reporter.send_error_message(f"RPC failover: {exc}")
                connector.rotate_rpc()
                w3 = connector.w3
                reader.connector = connector
                reader._init_contracts()
                usdc_contract  = w3.eth.contract(address=w3.to_checksum_address(config.USDC), abi=ERC20_ABI)
                vault_contract = w3.eth.contract(address=vault, abi=VAULT_ABI)
                l1_oracle      = w3.eth.contract(address=w3.to_checksum_address(config.L1_GAS_ORACLE), abi=L1_ORACLE_ABI)
                time.sleep(5)
                continue

            logger.error("Critical loop error: %s", exc)
            telegram_reporter.send_error_message(str(exc))
            time.sleep(60)


if __name__ == "__main__":
    main()
