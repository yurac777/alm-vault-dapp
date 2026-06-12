"""
state_reader.py — Reads on-chain state for the ALM Vault Keeper.
Sources: Chainlink (ETH price), Uniswap V3 Pool slot0 (current tick).
"""
import logging
from decimal import Decimal

from keeper.connectors.base_rpc import BaseConnector
from keeper.core.math import price_to_tick, get_closest_usable_tick
import config

logger = logging.getLogger("StateReader")

CHAINLINK_ABI = [
    {
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
    }
]

UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96",               "type": "uint160"},
            {"internalType": "int24",   "name": "tick",                        "type": "int24"},
            {"internalType": "uint16",  "name": "observationIndex",            "type": "uint16"},
            {"internalType": "uint16",  "name": "observationCardinality",      "type": "uint16"},
            {"internalType": "uint16",  "name": "observationCardinalityNext",  "type": "uint16"},
            {"internalType": "uint8",   "name": "feeProtocol",                 "type": "uint8"},
            {"internalType": "bool",    "name": "unlocked",                    "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]


class StateReader:
    def __init__(self, connector: BaseConnector):
        self.connector = connector
        self._init_contracts()

    def _init_contracts(self):
        w3 = self.connector.w3
        self.oracle = w3.eth.contract(
            address=w3.to_checksum_address(config.CHAINLINK_ETH),
            abi=CHAINLINK_ABI,
        )
        self.pool = w3.eth.contract(
            address=w3.to_checksum_address(config.UNI_V3_POOL),
            abi=UNISWAP_V3_POOL_ABI,
        )

    def get_eth_price(self) -> Decimal:
        """Returns ETH/USD from Chainlink (8 decimals)."""
        round_data = self.oracle.functions.latestRoundData().call()
        return Decimal(round_data[1]) / Decimal(10 ** 8)

    def get_current_tick(self, eth_price: Decimal, tick_spacing: int = 10) -> dict:
        """
        Returns current tick from the Uniswap V3 WETH/USDC pool (slot0).
        Falls back to Chainlink-derived tick on RPC error.
        """
        is_onchain = False
        sqrt_price_x96 = 0
        try:
            slot0 = self.pool.functions.slot0().call()
            exact_tick = slot0[1]
            sqrt_price_x96 = slot0[0]
            is_onchain = True
        except Exception as exc:
            logger.warning("[StateReader] slot0 error: %s — using Chainlink fallback.", exc)
            exact_tick = price_to_tick(eth_price, decimals0=18, decimals1=6)

        aligned_tick = get_closest_usable_tick(exact_tick, tick_spacing, lower=True)
        return {
            "exact_tick":    exact_tick,
            "aligned_tick":  aligned_tick,
            "is_onchain_tick": is_onchain,
            "sqrt_price_x96": sqrt_price_x96,
        }
