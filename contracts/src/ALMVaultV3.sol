// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC4626} from "openzeppelin-contracts/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {IPool, INonfungiblePositionManager} from "./interfaces/DeFiInterfaces.sol";

contract ALMVaultV3 is ERC4626, Ownable {
    using SafeERC20 for IERC20;
    
    address public keeper;
    IPool public aavePool;
    INonfungiblePositionManager public npm;
    IERC20 public weth;

    uint256 public currentTokenId;
    uint128 public currentLiquidity;
    
    uint256 public withdrawalFeeBps = 50; // 0.5%
    address public feeRecipient;
    
    int256 public netTotalDeposit; // tracks net USDC deposited into the vault

    event KeeperUpdated(address indexed oldKeeper, address indexed newKeeper);
    event Rebalanced(uint256 newTokenId, uint128 newLiquidity);

    modifier onlyKeeper() {
        require(msg.sender == keeper, "ALMVault: caller is not the keeper");
        _;
    }

    constructor(IERC20 _asset, IERC20 _weth, address _initialOwner, address _aavePool, address _npm)
        ERC4626(_asset)
        ERC20("ALM Vault V3", "ALMv3")
        Ownable(_initialOwner)
    {
        weth = _weth;
        aavePool = IPool(_aavePool);
        npm = INonfungiblePositionManager(_npm);
        feeRecipient = _initialOwner;
        
        // Max approve NPM
        _asset.approve(_npm, type(uint256).max);
        _weth.approve(_npm, type(uint256).max);
    }

    function setKeeper(address _keeper) external onlyOwner {
        require(_keeper != address(0), "ALMVault: keeper cannot be zero address");
        emit KeeperUpdated(keeper, _keeper);
        keeper = _keeper;
    }

    function setFeeRecipient(address _recipient) external onlyOwner {
        require(_recipient != address(0), "ALMVault: feeRecipient cannot be zero address");
        feeRecipient = _recipient;
    }

    function rebalance(bytes calldata data) external onlyKeeper {
        (
            bool isRebalance,
            int256 aaveDebtAdjustment,
            uint256 amountUSDC,
            uint256 amountWETHToBorrow,
            int24 newTickLower,
            int24 newTickUpper,
            uint256 amount0Desired,
            uint256 amount1Desired,
            uint24 poolFee,
            uint256 amountWETHToRepay,
            uint256 amountUSDCToWithdraw
        ) = abi.decode(data, (bool, int256, uint256, uint256, int24, int24, uint256, uint256, uint24, uint256, uint256));

        address usdc = asset();
        address token0 = address(usdc) < address(weth) ? address(usdc) : address(weth);
        address token1 = address(usdc) < address(weth) ? address(weth) : address(usdc);

        // 1. Close old position if exists
        if (currentTokenId != 0 && currentLiquidity > 0) {
            npm.decreaseLiquidity(INonfungiblePositionManager.DecreaseLiquidityParams({
                tokenId: currentTokenId,
                liquidity: currentLiquidity,
                amount0Min: 0,
                amount1Min: 0,
                deadline: block.timestamp
            }));
            npm.collect(INonfungiblePositionManager.CollectParams({
                tokenId: currentTokenId,
                recipient: address(this),
                amount0Max: type(uint128).max,
                amount1Max: type(uint128).max
            }));
            // We just leave the empty NFT in the contract, or burn it, but burn requires 0 liquidity and 0 uncollected tokens.
            currentTokenId = 0;
            currentLiquidity = 0;
        }

        // 2. Adjust Aave Debt
        if (amountWETHToRepay > 0) {
            weth.approve(address(aavePool), amountWETHToRepay);
            aavePool.repay(address(weth), amountWETHToRepay, 2, address(this));
        }

        if (amountUSDCToWithdraw > 0) {
            aavePool.withdraw(usdc, amountUSDCToWithdraw, address(this));
        }

        if (amountUSDC > 0) {
            IERC20(usdc).approve(address(aavePool), amountUSDC);
            aavePool.supply(usdc, amountUSDC, address(this), 0);
        }

        if (isRebalance && aaveDebtAdjustment > 0) {
            aavePool.borrow(address(weth), uint256(aaveDebtAdjustment), 2, 0, address(this));
        } else if (amountWETHToBorrow > 0) {
            aavePool.borrow(address(weth), amountWETHToBorrow, 2, 0, address(this));
        }

        // 3. Open new position
        if (amount0Desired > 0 || amount1Desired > 0) {
            (uint256 tokenId, uint128 liquidity, , ) = npm.mint(INonfungiblePositionManager.MintParams({
                token0: token0,
                token1: token1,
                fee: poolFee,
                tickLower: newTickLower,
                tickUpper: newTickUpper,
                amount0Desired: amount0Desired,
                amount1Desired: amount1Desired,
                amount0Min: 0,
                amount1Min: 0,
                recipient: address(this),
                deadline: block.timestamp
            }));
            currentTokenId = tokenId;
            currentLiquidity = liquidity;
            emit Rebalanced(tokenId, liquidity);
        } else {
            emit Rebalanced(0, 0);
        }
        
        // 4. Auto-Sweep Excess WETH
        uint256 excessWeth = weth.balanceOf(address(this));
        if (excessWeth > 0) {
            weth.approve(address(aavePool), excessWeth);
            aavePool.repay(address(weth), excessWeth, 2, address(this));
        }
    }

    function totalAssets() public view virtual override returns (uint256) {
        uint256 balanceUSDC = IERC20(asset()).balanceOf(address(this));
        // Note: For a robust implementation, totalAssets should compute the value of the Uniswap V3 position
        // and the net value of the Aave position (aUSDC - debtWETH * price). 
        // For simplicity in this demo, we return the balance.
        return balanceUSDC;
    }

    function _deposit(
        address caller,
        address receiver,
        uint256 assets,
        uint256 shares
    ) internal virtual override {
        super._deposit(caller, receiver, assets, shares);
        netTotalDeposit += int256(assets);
    }

    function _withdraw(
        address caller,
        address receiver,
        address owner,
        uint256 assets,
        uint256 shares
    ) internal virtual override {
        if (caller != owner) {
            _spendAllowance(owner, caller, shares);
        }

        uint256 fee = (assets * withdrawalFeeBps) / 10000;
        uint256 payout = assets - fee;

        _burn(owner, shares);
        
        if (fee > 0) {
            IERC20(asset()).safeTransfer(feeRecipient, fee);
        }
        IERC20(asset()).safeTransfer(receiver, payout);

        netTotalDeposit -= int256(assets);

        emit Withdraw(caller, receiver, owner, assets, shares);
    }
}
