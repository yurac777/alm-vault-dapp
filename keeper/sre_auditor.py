"""
sre_auditor.py — Independent SRE watchdog for the ALM Vault Keeper.

Checks:
  1. Daemon health (is keeper.log being updated?)
  2. Log anomaly scan (errors, timeouts, revert storms)
  3. Real on-chain metrics: unclaimed fees, Aave HF, PnL
  4. Fires Telegram alert if any metric is critical

Run manually:   python sre_auditor.py
Or as a cron:   */30 * * * * python /path/to/sre_auditor.py
"""

import os
import re
import sys
import csv
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from web3 import Web3
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from core import telegram_reporter
from core.math import get_amounts_for_liquidity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("SRE-Auditor")

# ── Thresholds ────────────────────────────────────────────────────────────────
KEEPER_LOG      = os.path.join(os.path.dirname(__file__), "keeper.log")
CSV_LOG         = os.path.join(os.path.dirname(__file__), "history_log.csv")
STATE_FILE      = os.path.join(os.path.dirname(__file__), "state_pnl.json")
STALE_SECONDS   = 1200   # 20 min — daemon considered dead if no log update
MIN_HEALTH_FACTOR = 1.15  # Liquidation warning threshold
ERROR_STORM_THRESHOLD = 10  # >10 errors in last 50 lines = storm

MAX_UINT128 = 2**128 - 1

# ── ABIs ─────────────────────────────────────────────────────────────────────
AAVE_ABI = [{
    "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
    "name": "getUserAccountData",
    "outputs": [
        {"internalType": "uint256", "name": "totalCollateralBase",  "type": "uint256"},
        {"internalType": "uint256", "name": "totalDebtBase",        "type": "uint256"},
        {"internalType": "uint256", "name": "availableBorrowsBase", "type": "uint256"},
        {"internalType": "uint256", "name": "currentLiquidationThreshold", "type": "uint256"},
        {"internalType": "uint256", "name": "ltv",                  "type": "uint256"},
        {"internalType": "uint256", "name": "healthFactor",         "type": "uint256"},
    ],
    "stateMutability": "view",
    "type": "function",
}, {
    "inputs": [{"internalType": "address", "name": "asset", "type": "address"}],
    "name": "getReserveData",
    "outputs": [{"components": [
        {"internalType": "struct DataTypes.ReserveConfigurationMap", "name": "configuration", "type": "tuple", "components": [{"internalType": "uint256", "name": "data", "type": "uint256"}]},
        {"internalType": "uint128", "name": "liquidityIndex", "type": "uint128"},
        {"internalType": "uint128", "name": "currentLiquidityRate", "type": "uint128"},
        {"internalType": "uint128", "name": "variableBorrowIndex", "type": "uint128"},
        {"internalType": "uint128", "name": "currentVariableBorrowRate", "type": "uint128"},
        {"internalType": "uint128", "name": "currentStableBorrowRate", "type": "uint128"},
        {"internalType": "uint40", "name": "lastUpdateTimestamp", "type": "uint40"},
        {"internalType": "uint16", "name": "id", "type": "uint16"},
        {"internalType": "address", "name": "aTokenAddress", "type": "address"},
        {"internalType": "address", "name": "stableDebtTokenAddress", "type": "address"},
        {"internalType": "address", "name": "variableDebtTokenAddress", "type": "address"},
        {"internalType": "address", "name": "interestRateStrategyAddress", "type": "address"},
        {"internalType": "uint128", "name": "accruedToTreasury", "type": "uint128"},
        {"internalType": "uint128", "name": "unbacked", "type": "uint128"},
        {"internalType": "uint128", "name": "isolationModeTotalDebt", "type": "uint128"}
    ], "internalType": "struct DataTypes.ReserveData", "name": "", "type": "tuple"}],
    "stateMutability": "view",
    "type": "function"
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
        "name": "params", "type": "tuple",
    }],
    "name": "collect",
    "outputs": [
        {"internalType": "uint256", "name": "amount0", "type": "uint256"},
        {"internalType": "uint256", "name": "amount1", "type": "uint256"},
    ],
    "stateMutability": "payable",
    "type": "function",
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

POOL_SLOT0_ABI = [{
    "inputs": [], "name": "slot0",
    "outputs": [
        {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
        {"internalType": "int24", "name": "tick", "type": "int24"},
        {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
        {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
        {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
        {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
        {"internalType": "bool", "name": "unlocked", "type": "bool"}
    ],
    "stateMutability": "view", "type": "function"
}]

VAULT_ABI_MIN = [{
    "inputs": [], "name": "currentTokenId",
    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
    "stateMutability": "view", "type": "function",
}]

ERC20_ABI = [{
    "constant": True,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "type": "function",
}]

CHAINLINK_ABI = [{
    "inputs": [], "name": "latestRoundData",
    "outputs": [
        {"internalType": "uint80",  "name": "roundId",         "type": "uint80"},
        {"internalType": "int256",  "name": "answer",          "type": "int256"},
        {"internalType": "uint256", "name": "startedAt",       "type": "uint256"},
        {"internalType": "uint256", "name": "updatedAt",       "type": "uint256"},
        {"internalType": "uint80",  "name": "answeredInRound", "type": "uint80"},
    ],
    "stateMutability": "view", "type": "function",
}]


# ─────────────────────────────────────────────────────────────────────────────
def check_daemon_liveness() -> dict:
    """Returns daemon health based on keeper.log mtime."""
    if not os.path.exists(KEEPER_LOG):
        return {"alive": False, "reason": "keeper.log not found"}
    age_sec = time.time() - os.path.getmtime(KEEPER_LOG)
    if age_sec > STALE_SECONDS:
        return {"alive": False, "reason": f"keeper.log stale for {age_sec:.0f}s (>{STALE_SECONDS}s)"}
    return {"alive": True, "age_sec": age_sec}


def scan_log_anomalies() -> dict:
    """Reads the last 200 lines of keeper.log, counts errors and patterns."""
    anomalies = {
        "error_count": 0,
        "timeout_count": 0,
        "revert_count": 0,
        "skip_count": 0,
        "error_storm": False,
        "last_errors": [],
    }
    if not os.path.exists(KEEPER_LOG):
        return anomalies

    try:
        with open(KEEPER_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        tail = lines[-200:] if len(lines) > 200 else lines

        for line in tail:
            low = line.lower()
            if "[error]" in low:
                anomalies["error_count"] += 1
                if len(anomalies["last_errors"]) < 5:
                    anomalies["last_errors"].append(line.strip())
            if "timeout" in low or "timed out" in low:
                anomalies["timeout_count"] += 1
            if "reverted" in low or "revert" in low:
                anomalies["revert_count"] += 1
            if "skipping" in low or "пропуск" in low:
                anomalies["skip_count"] += 1

        last50 = tail[-50:]
        err50  = sum(1 for l in last50 if "[error]" in l.lower())
        if err50 >= ERROR_STORM_THRESHOLD:
            anomalies["error_storm"] = True
    except Exception as exc:
        logger.warning("Could not read keeper.log: %s", exc)

    return anomalies


def read_csv_summary() -> dict:
    """Reads the last 10 rows from history_log.csv for trend analysis."""
    summary = {"rows": 0, "last_action": "N/A", "reverts": 0, "no_actions": 0}
    if not os.path.exists(CSV_LOG):
        return summary
    try:
        with open(CSV_LOG, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        summary["rows"] = len(rows)
        if rows:
            last = rows[-1]
            summary["last_action"] = last.get("Action_Taken", "?")
            tail10 = rows[-10:]
            summary["reverts"]    = sum(1 for r in tail10 if "Reverted" in r.get("Action_Taken", ""))
            summary["no_actions"] = sum(1 for r in tail10 if r.get("Action_Taken") in ("No Action", "Skipped (In-Range)"))
    except Exception as exc:
        logger.warning("CSV read error: %s", exc)
    return summary


def get_onchain_metrics() -> dict:
    """Pulls live Aave, USDC balance, and V3 unclaimed fees."""
    metrics = {
        "eth_price": 0.0,
        "collateral": 0.0, "debt": 0.0, "hf": 0.0,
        "usdc_balance": 0.0,
        "token_id": 0,
        "fee_weth": 0.0, "fee_usdc": 0.0, "fee_usd": 0.0,
        "nft_value_usd": 0.0,
        "tvl": 0.0,
        "aave_supply_apy": 0.0,
        "aave_borrow_apy": 0.0,
        "aave_net_apy": 0.0,
        "error": None,
    }
    try:
        w3 = Web3(Web3.HTTPProvider(config.RPC_URL, request_kwargs={"timeout": 15}))
        if not w3.is_connected():
            metrics["error"] = "RPC not connected"
            return metrics

        vault_addr = w3.to_checksum_address(config.VAULT_ADDRESS)

        # ETH price
        oracle = w3.eth.contract(address=w3.to_checksum_address(config.CHAINLINK_ETH), abi=CHAINLINK_ABI)
        metrics["eth_price"] = float(Decimal(oracle.functions.latestRoundData().call()[1]) / Decimal(10**8))

        # Aave
        aave = w3.eth.contract(address=w3.to_checksum_address(config.AAVE_POOL), abi=AAVE_ABI)
        acct = aave.functions.getUserAccountData(vault_addr).call()
        metrics["collateral"] = float(acct[0]) / 1e8
        metrics["debt"]       = float(acct[1]) / 1e8
        metrics["hf"]         = float(acct[5]) / 1e18 if acct[5] != (2**256 - 1) else float("inf")

        # Aave rates
        try:
            usdc_res = aave.functions.getReserveData(w3.to_checksum_address(config.USDC)).call()
            weth_res = aave.functions.getReserveData(w3.to_checksum_address(config.WETH)).call()
            metrics["aave_supply_apy"] = usdc_res[2] / 1e27 * 100
            metrics["aave_borrow_apy"] = weth_res[4] / 1e27 * 100
        except Exception:
            pass

        # USDC
        usdc_c = w3.eth.contract(address=w3.to_checksum_address(config.USDC), abi=ERC20_ABI)
        metrics["usdc_balance"] = usdc_c.functions.balanceOf(vault_addr).call() / 1e6

        # V3 position value & fees
        vault_c  = w3.eth.contract(address=vault_addr, abi=VAULT_ABI_MIN)
        npm      = w3.eth.contract(address=w3.to_checksum_address(config.UNI_V3_NPM), abi=NPM_COLLECT_ABI)
        pool     = w3.eth.contract(address=w3.to_checksum_address(config.UNI_V3_POOL), abi=POOL_SLOT0_ABI)
        try:
            tok_id = vault_c.functions.currentTokenId().call()
            metrics["token_id"] = tok_id
            if tok_id != 0:
                # Fees
                res = npm.functions.collect((tok_id, vault_addr, MAX_UINT128, MAX_UINT128)).call({"from": vault_addr})
                metrics["fee_weth"] = res[0] / 1e18
                metrics["fee_usdc"] = res[1] / 1e6
                
                # Position value
                pos = npm.functions.positions(tok_id).call()
                liq, tick_lower, tick_upper = pos[7], pos[5], pos[6]
                slot0 = pool.functions.slot0().call()
                sqrtPriceX96 = slot0[0]
                if sqrtPriceX96 > 0:
                    amt0, amt1 = get_amounts_for_liquidity(sqrtPriceX96, tick_lower, tick_upper, liq)
                    metrics["nft_value_usd"] = (float(amt0) / 1e18) * metrics["eth_price"] + (float(amt1) / 1e6)
        except Exception as exc:
            logger.warning("[OnChain] Could not fetch V3 data: %s", exc)

        metrics["fee_usd"] = metrics["fee_weth"] * metrics["eth_price"] + metrics["fee_usdc"]
        metrics["tvl"]     = (metrics["collateral"] - metrics["debt"]) + metrics["usdc_balance"] + metrics["nft_value_usd"]

        if metrics["tvl"] > 0:
            metrics["aave_net_apy"] = (metrics["aave_supply_apy"] * (metrics["collateral"] / metrics["tvl"])) - (metrics["aave_borrow_apy"] * (metrics["debt"] / metrics["tvl"]))


    except Exception as exc:
        metrics["error"] = str(exc)
    return metrics


def load_state() -> dict:
    state = {
        "gas_spent_usd": 0.0,
        "initial_deposit_usd": 5.0,
        "deposit_timestamp": time.time() - 3600
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                state["gas_spent_usd"] = d.get("gas_spent_usd", 0.0)
                state["initial_deposit_usd"] = d.get("initial_deposit_usd", 5.0)
                state["deposit_timestamp"] = d.get("deposit_timestamp", state["deposit_timestamp"])
        except Exception:
            pass
    return state


# ─────────────────────────────────────────────────────────────────────────────
def run_audit():
    alerts   = []
    warnings = []

    print("\n" + "=" * 50)
    print("   🔍 SRE AUDITOR — ALM Vault V3")
    print("=" * 50)

    # 1. Daemon liveness
    health = check_daemon_liveness()
    if health["alive"]:
        logger.info("[Daemon] ✅  Alive  (last update %.0fs ago)", health["age_sec"])
    else:
        msg = f"[Daemon] ❌  DEAD — {health['reason']}"
        logger.error(msg)
        alerts.append(msg)

    # 2. Log anomaly scan
    anomalies = scan_log_anomalies()
    logger.info("[LogScan] errors=%d  timeouts=%d  reverts=%d  skips=%d",
                anomalies["error_count"], anomalies["timeout_count"],
                anomalies["revert_count"], anomalies["skip_count"])
    if anomalies["error_storm"]:
        msg = f"[LogScan] 🚨 ERROR STORM detected — {anomalies['error_count']} errors in log tail"
        logger.error(msg)
        alerts.append(msg)
    if anomalies["timeout_count"] > 5:
        msg = f"[LogScan] ⚠️  High timeout count: {anomalies['timeout_count']}"
        logger.warning(msg)
        warnings.append(msg)
    if anomalies["last_errors"]:
        logger.info("[LogScan] Sample errors:")
        for e in anomalies["last_errors"]:
            logger.info("  • %s", e)

    # 3. CSV trend
    csv_s = read_csv_summary()
    logger.info("[CSV] rows=%d  lastAction=%s  recentReverts=%d  noAction=%d",
                csv_s["rows"], csv_s["last_action"], csv_s["reverts"], csv_s["no_actions"])
    if csv_s["reverts"] >= 3:
        msg = f"[CSV] ⚠️  {csv_s['reverts']}/10 recent rows are reverts!"
        logger.warning(msg)
        warnings.append(msg)

    # 4. On-chain metrics
    m = get_onchain_metrics()
    if m["error"]:
        msg = f"[OnChain] ❌  RPC error: {m['error']}"
        logger.error(msg)
        alerts.append(msg)
    else:
        state = load_state()
        gas_spent  = state["gas_spent_usd"]
        init_dep   = state["initial_deposit_usd"]
        net_profit = m["tvl"] - gas_spent - init_dep
        
        elapsed_sec = time.time() - state["deposit_timestamp"]
        elapsed_hours = max(elapsed_sec / 3600.0, 0.01)
        apr = (m["fee_usd"] / init_dep) * (8760 / elapsed_hours) * 100 if init_dep > 0 else 0.0

        logger.info("[OnChain] ETH=$%.2f", m["eth_price"])
        logger.info("[OnChain] TVL=$%.4f  Coll=$%.4f  Debt=$%.4f  HF=%.2f",
                    m["tvl"], m["collateral"], m["debt"], m["hf"])
        logger.info("[OnChain] Aave Rates: Supply=%.2f%%  Borrow=%.2f%%  NetAPY=%.2f%%",
                    m["aave_supply_apy"], m["aave_borrow_apy"], m["aave_net_apy"])
        logger.info("[OnChain] UniV3 tokenId=%s  nftValue=$%.4f  feeWETH=%.6f  feeUSDC=%.4f  feeUSD=$%.4f",
                    m["token_id"] or "None", m["nft_value_usd"], m["fee_weth"], m["fee_usdc"], m["fee_usd"])
        logger.info("[OnChain] InitDep=$%.4f  GasSpent=$%.4f  NetProfit=%+.4f$  APR=%.2f%%", 
                    init_dep, gas_spent, net_profit, apr)

        if m["hf"] < MIN_HEALTH_FACTOR:
            msg = f"[OnChain] 🚨 LIQUIDATION RISK — HF={m['hf']:.2f} < {MIN_HEALTH_FACTOR}"
            logger.error(msg)
            alerts.append(msg)

        if net_profit < -5.0:
            msg = f"[OnChain] ⚠️  Net profit negative: ${net_profit:+.4f}"
            logger.warning(msg)
            warnings.append(msg)

    # 5. Summary & Telegram
    print("\n" + "─" * 50)
    if alerts:
        print(f"  🚨 ALERTS  ({len(alerts)})")
        for a in alerts:
            print(f"     • {a}")
        tg_msg = "🚨 *SRE AUDITOR ALERT*\n\n" + "\n".join(f"• {a}" for a in alerts)
        telegram_reporter.send_message(tg_msg)
    elif warnings:
        print(f"  ⚠️  WARNINGS ({len(warnings)})")
        for w in warnings:
            print(f"     • {w}")
        tg_msg = "⚠️ *SRE Auditor Warning*\n\n" + "\n".join(f"• {w}" for w in warnings)
        telegram_reporter.send_message(tg_msg)
    else:
        print("  ✅  ALL SYSTEMS NOMINAL")
        logger.info("Audit complete — no issues detected.")

    if not m.get("error"):
        state = load_state()
        init_dep   = state["initial_deposit_usd"]
        gas_spent  = state["gas_spent_usd"]
        net_profit = m["tvl"] - gas_spent - init_dep
        
        elapsed_sec = time.time() - state["deposit_timestamp"]
        elapsed_hours = max(elapsed_sec / 3600.0, 0.01)
        apr = (m["fee_usd"] / init_dep) * (8760 / elapsed_hours) * 100 if init_dep > 0 else 0.0
        
        print(f"\n  ETH        ${m['eth_price']:.2f}")
        print(f"  TVL        ${m['tvl']:.4f} (NFT=${m['nft_value_usd']:.4f})")
        print(f"  Aave HF    {m['hf']:.2f}")
        print(f"  Aave NetAPY {m['aave_net_apy']:.2f}% (Supply {m['aave_supply_apy']:.2f}%, Borrow {m['aave_borrow_apy']:.2f}%)")
        print(f"  V3 Fees    ${m['fee_usd']:.4f}  ({m['fee_weth']:.6f} WETH | {m['fee_usdc']:.4f} USDC)")
        print(f"  Total APR  {apr:.2f}%")
        print(f"  Net Profit ${net_profit:+.4f}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_audit()
