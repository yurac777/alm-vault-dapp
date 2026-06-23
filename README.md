# ALM Vault V3: AI-Quant Hedging Vault

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Network](https://img.shields.io/badge/Network-Base%20Mainnet-blue)](https://base.org)

ALM Vault V3 is an autonomous, Delta-Neutral Liquidity Provision protocol engineered for extreme capital efficiency. By fusing **Aave V3** (for shorting volatility) and **Uniswap V3** (for concentrated liquidity fee generation), we deliver sustainable yields with near-zero Impermanent Loss.

## Architecture: The Three Pillars

1. **Synthetic Dollar (almUSD)**: Users mint almUSD by depositing USDC.
2. **Delta-Neutral Hedging**: The vault supplies USDC to Aave V3, borrows WETH, and provides WETH/USDC liquidity on Uniswap V3.
3. **Autonomous Keeper**: An AI-driven Python bot continuously monitors ticks, gas prices, and PnL, rebalancing the position to maintain optimal health factor and fee generation.

## Getting Started
Visit our [DApp](https://alm-quant.xyz) to mint almUSD.

## Deployment
Vault Contract Address: `0x2726c74D2e0A94Ec181Beb618569b10116415289`

### Remote Deployment Server
- **Host**: `100.116.182.78`
- **User**: `aiuser`
- **Password**: *See .env file (SuperPass123!)*
- **GitHub Token**: *See .env file*
