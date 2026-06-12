# ALM Vault V3: AI-Quant Hedging Vault

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Network](https://img.shields.io/badge/Network-Base%20Mainnet-blue)](https://base.org)

ALM Vault V3 is an autonomous, Delta-Neutral Liquidity Provision protocol engineered for extreme capital efficiency. By fusing **Aave V3** (for shorting volatility) and **Uniswap V3** (for concentrated liquidity fee generation), we deliver sustainable yields with near-zero Impermanent Loss.

---

## 🧠 Architecture: The Three Pillars

1. **Delta-Neutrality via Aave V3**
   We completely neutralize the directional risk of WETH. The vault takes user deposits (USDC), supplies them as collateral to Aave V3, and borrows WETH. By shorting WETH against the USDC, any depreciation in WETH price decreases the vault's debt, perfectly hedging the impermanent loss typically suffered in an LP position.

2. **Hyper-Concentrated Liquidity (Uniswap V3)**
   The borrowed WETH and remaining USDC are injected into Uniswap V3. Our custom logic calculates exact token ratios for asymmetric tick ranges, dynamically capturing trading fees while maintaining 95%+ capital efficiency. `Zero-Dust` algorithms sweep excess WETH back to Aave instantly to prevent "bleeding loans".

3. **Autonomous AI SRE Keeper (Python)**
   The brain of the operation. Our off-chain Python Keeper uses `gemini-pro-agent` to read market trends and calculate optimal `tickSpacing`. It performs fully autonomous rebalancing (Withdraw -> Repay -> Borrow -> Mint/Burn) and seamlessly interfaces with the blockchain.

## 📊 Live On-Chain Metrics (Base Mainnet)

Our rigorous production tests have proven the viability of HFT (High-Frequency Trading) liquidity provisioning on Base Mainnet. 

- **Full Rebalance Cycle Gas:** `~900,000` to `1,000,000` gas.
- **Average Rebalance Cost:** **<$0.005 USD**.
- **Capital Efficiency:** **> 99%** (Idle vault USDC stays below $0.01).
- **Target Health Factor:** `1.6` (Dynamically scales up to `2.1` in bullish trends to prevent liquidations).

## 🧰 Repository Structure

- `contracts/`: Foundry-based Solidity smart contracts (`ALMVaultV3.sol`).
- `contracts/src/ALMToken.sol`: Our native `$vALM` ERC-20 utility token used for future Liquidity Mining rewards.
- `keeper/`: The Python SRE-Engine (`main.py`, `dashboard.py`) handling all AI oracle and transaction submission logic.

## 🚀 Quick Start for Developers

### 1. Smart Contracts
You'll need [Foundry](https://getfoundry.sh/) installed.
```bash
cd contracts
forge install
forge test --match-contract ALMVaultFuzzTest
```

### 2. Off-Chain Keeper
```bash
cd keeper
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `keeper` directory (see `keeper/.env.example`):
```env
WALLET_ADDRESS=YOUR_WALLET_ADDRESS
PRIVATE_KEY=YOUR_PRIVATE_KEY
BASE_MAINNET_RPC=https://base-mainnet.g.alchemy.com/v2/...
VAULT_ADDRESS=YOUR_DEPLOYED_VAULT
```

Run the dashboard or the autonomous loop:
```bash
# View live metrics
python dashboard.py

# Run a single forced rebalance cycle
python main.py --force --run-once
```

## 🔒 Security
- **No External Reentrancy:** Core rebalancing functions are guarded by `onlyKeeper`.
- **Anti-Sandwich:** Rebalances are triggered exclusively by our proprietary off-chain engine, insulating deposits from public mempool sandwich attacks.
- **Zero-Dust Protocol:** Prevents capital bloat by instantly sweeping all unbound assets.

## 📄 License
This project is licensed under the MIT License.
