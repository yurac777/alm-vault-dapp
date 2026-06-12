"""
encoder.py — ABI-encodes the rebalance payload for ALMVaultV3.
"""
from eth_abi import encode


def encode_rebalance_payload_v3(
    isRebalance: bool,
    aaveDebtAdjustment: int,
    amountUSDC: int,
    amountWETHToBorrow: int,
    newTickLower: int,
    newTickUpper: int,
    amount0Desired: int,
    amount1Desired: int,
    poolFee: int = 500,
    amountWETHToRepay: int = 0,
    amountUSDCToWithdraw: int = 0,
) -> str:
    """
    Encodes the calldata ``bytes`` parameter for ``ALMVaultV3.rebalance()``.

    Solidity signature (decoded order):
        (bool, int256, uint256, uint256, int24, int24,
         uint256, uint256, uint24, uint256, uint256)
    """
    types = [
        "bool",    # isRebalance
        "int256",  # aaveDebtAdjustment
        "uint256", # amountUSDC
        "uint256", # amountWETHToBorrow
        "int24",   # newTickLower
        "int24",   # newTickUpper
        "uint256", # amount0Desired  (WETH, token0)
        "uint256", # amount1Desired  (USDC, token1)
        "uint24",  # poolFee
        "uint256", # amountWETHToRepay
        "uint256", # amountUSDCToWithdraw
    ]
    values = [
        isRebalance,
        aaveDebtAdjustment,
        amountUSDC,
        amountWETHToBorrow,
        newTickLower,
        newTickUpper,
        amount0Desired,
        amount1Desired,
        poolFee,
        amountWETHToRepay,
        amountUSDCToWithdraw,
    ]
    return "0x" + encode(types, values).hex()
