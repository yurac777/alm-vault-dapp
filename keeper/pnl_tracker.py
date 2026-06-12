import json
import os
from decimal import Decimal

# Файл состояния для газа
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_pnl.json")

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"gas_spent_usd": 0.0, "initial_deposit_usd": 5.0}

def load_gas_spent() -> float:
    return load_state().get("gas_spent_usd", 0.0)

def add_gas_spent(gas_cost_usd: float):
    state = load_state()
    state["gas_spent_usd"] = state.get("gas_spent_usd", 0.0) + gas_cost_usd
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)

def get_net_deposit_onchain(w3, vault_address: str) -> float:
    # Use the netTotalDeposit public variable from ALMVaultV4
    ABI = [{
        "inputs": [],
        "name": "netTotalDeposit",
        "outputs": [{"internalType": "int256", "name": "", "type": "int256"}],
        "stateMutability": "view",
        "type": "function"
    }]
    vault = w3.eth.contract(address=w3.to_checksum_address(vault_address), abi=ABI)
    try:
        net_wei = vault.functions.netTotalDeposit().call()
        # USDC has 6 decimals
        return float(net_wei) / 1e6
    except Exception as e:
        print(f"Failed to fetch netTotalDeposit: {e}")
        return 0.0

def calculate_pnl_onchain(w3, vault_address: str, usdc_balance: int, aave_pool_address: str, nft_value_usd: float = 0.0) -> dict:
    AAVE_POOL_ABI = [{
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getUserAccountData",
        "outputs": [
            {"internalType": "uint256", "name": "totalCollateralBase", "type": "uint256"},
            {"internalType": "uint256", "name": "totalDebtBase", "type": "uint256"},
            {"internalType": "uint256", "name": "availableBorrowsBase", "type": "uint256"},
            {"internalType": "uint256", "name": "currentLiquidationThreshold", "type": "uint256"},
            {"internalType": "uint256", "name": "ltv", "type": "uint256"},
            {"internalType": "uint256", "name": "healthFactor", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }]
    
    aave_pool = w3.eth.contract(address=w3.to_checksum_address(aave_pool_address), abi=AAVE_POOL_ABI)
    account_data = aave_pool.functions.getUserAccountData(w3.to_checksum_address(vault_address)).call()
    
    ERC20_ABI = [{
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }]
    
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config
    
    # Fetch Free USDC and WETH directly from chain
    usdc_c  = w3.eth.contract(address=w3.to_checksum_address(config.USDC), abi=ERC20_ABI)
    usdc_bal_actual = usdc_c.functions.balanceOf(w3.to_checksum_address(vault_address)).call() / 1e6
    
    weth_c  = w3.eth.contract(address=w3.to_checksum_address(config.WETH), abi=ERC20_ABI)
    weth_bal_actual = weth_c.functions.balanceOf(w3.to_checksum_address(vault_address)).call() / 1e18
    
    # We need eth_price to convert WETH to USD
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
    oracle   = w3.eth.contract(address=w3.to_checksum_address(config.CHAINLINK_ETH), abi=CHAINLINK_ABI)
    eth_price = float(Decimal(oracle.functions.latestRoundData().call()[1]) / Decimal(10**8))
    
    weth_worth_usd = weth_bal_actual * eth_price
    
    total_collateral = float(account_data[0]) / 1e8 # Base uses 8 decimals for USD
    total_debt = float(account_data[1]) / 1e8
    
    # Calculate exact net worth using real physical balances
    net_worth_usd = (total_collateral - total_debt) + usdc_bal_actual + weth_worth_usd + nft_value_usd
    
    state = load_state()
    gas_spent_usd = state.get("gas_spent_usd", 0.0)
    
    # DYNAMIC ON-CHAIN DEPOSIT TRACKING
    initial_deposit = get_net_deposit_onchain(w3, vault_address)
    
    net_profit = net_worth_usd - gas_spent_usd - initial_deposit
    
    return {
        "initial": initial_deposit,
        "net_worth": net_worth_usd,
        "gas_spent": gas_spent_usd,
        "net_profit": net_profit,
        "aave_collateral": total_collateral,
        "aave_debt": total_debt
    }
