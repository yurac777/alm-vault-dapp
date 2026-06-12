// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC4626} from "openzeppelin-contracts/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {IPool} from "./interfaces/DeFiInterfaces.sol";
import {IPoolManager} from "v4-core/interfaces/IPoolManager.sol";
import {IUnlockCallback} from "v4-core/interfaces/callback/IUnlockCallback.sol";
import {PoolKey} from "v4-core/types/PoolKey.sol";
import {Currency, CurrencyLibrary} from "v4-core/types/Currency.sol";
import {IHooks} from "v4-core/interfaces/IHooks.sol";
import {TransientStateLibrary} from "v4-core/libraries/TransientStateLibrary.sol";

contract ALMVault is ERC4626, Ownable, IUnlockCallback {
    using TransientStateLibrary for IPoolManager;
    using SafeERC20 for IERC20;
    
    address public keeper;
    IPool public aavePool;
    IPoolManager public poolManager;
    IERC20 public weth;

    int24 public currentTickLower;
    int24 public currentTickUpper;
    uint256 public currentLiquidity;
    
    uint256 public withdrawalFeeBps = 50; // 0.5%
    address public feeRecipient;

    event KeeperUpdated(address indexed oldKeeper, address indexed newKeeper);
    event Rebalanced();

    modifier onlyKeeper() {
        require(msg.sender == keeper, "ALMVault: caller is not the keeper");
        _;
    }

    constructor(IERC20 _asset, IERC20 _weth, address _initialOwner, address _aavePool, address _poolManager)
        ERC4626(_asset)
        ERC20("ALM Vault", "ALMv")
        Ownable(_initialOwner)
    {
        weth = _weth;
        aavePool = IPool(_aavePool);
        poolManager = IPoolManager(_poolManager);
        feeRecipient = _initialOwner;
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
        poolManager.unlock(data);
        emit Rebalanced();
    }

    function unlockCallback(bytes calldata data) external override returns (bytes memory) {
        require(msg.sender == address(poolManager), "ALMVault: only PoolManager");
        
        (
            bool isRebalance,
            int24 oldTickLower,
            int24 oldTickUpper,
            uint256 oldLiquidity,
            int256 aaveDebtAdjustment,
            uint256 amountUSDC,
            uint256 amountWETHToBorrow,
            int24 newTickLower,
            int24 newTickUpper,
            uint256 newLiquidityDelta,
            uint256 amountWETHToRepay,
            uint256 amountUSDCToWithdraw,
            uint24 poolFee,
            int24 poolTickSpacing
        ) = abi.decode(data, (bool, int24, int24, uint256, int256, uint256, uint256, int24, int24, uint256, uint256, uint256, uint24, int24));

        address usdc = asset();
        
        Currency currency0;
        Currency currency1;
        if (address(usdc) < address(weth)) {
            currency0 = Currency.wrap(address(usdc));
            currency1 = Currency.wrap(address(weth));
        } else {
            currency0 = Currency.wrap(address(weth));
            currency1 = Currency.wrap(address(usdc));
        }
        
        PoolKey memory poolKey = PoolKey({
            currency0: currency0,
            currency1: currency1,
            fee: poolFee,
            tickSpacing: poolTickSpacing,
            hooks: IHooks(address(0))
        });

        if (isRebalance) {
            // 1. Remove old liquidity
            poolManager.modifyLiquidity(
                poolKey, 
                IPoolManager.ModifyLiquidityParams({
                    tickLower: oldTickLower, 
                    tickUpper: oldTickUpper, 
                    liquidityDelta: -int256(oldLiquidity),
                    salt: bytes32(0)
                }), 
                ""
            );
            
            // PoolManager owes us tokens. If we need to repay WETH to Aave, we must take WETH out of the poolManager first.
            int256 wethDelta = poolManager.currencyDelta(address(this), Currency.wrap(address(weth)));
            if (wethDelta > 0 && aaveDebtAdjustment < 0) {
                // If we are repaying, we need physical WETH
                uint256 amountToTake = uint256(wethDelta);
                // take max of wethDelta or absolute aaveDebtAdjustment
                uint256 amountToRepay = uint256(-aaveDebtAdjustment);
                if (amountToTake > amountToRepay) {
                    amountToTake = amountToRepay;
                }
                poolManager.take(Currency.wrap(address(weth)), address(this), amountToTake);
            }
        }

        // 2. Adjust Aave Debt
        if (amountUSDC > 0) {
            IERC20(usdc).approve(address(aavePool), amountUSDC);
            aavePool.supply(usdc, amountUSDC, address(this), 0);
        }

        if (aaveDebtAdjustment > 0) {
            aavePool.borrow(address(weth), uint256(aaveDebtAdjustment), 2, 0, address(this));
        } else if (aaveDebtAdjustment < 0) {
            uint256 amountToRepayAdjustment = uint256(-aaveDebtAdjustment);
            weth.approve(address(aavePool), amountToRepayAdjustment);
            aavePool.repay(address(weth), amountToRepayAdjustment, 2, address(this));
        }

        // Fallback for initial borrow (if amountWETHToBorrow is used in initial open)
        if (!isRebalance && amountWETHToBorrow > 0) {
            aavePool.borrow(address(weth), amountWETHToBorrow, 2, 0, address(this));
        }
        
        // --- EMERGENCY EXIT / UNWIND ---
        if (amountWETHToRepay > 0) {
            int256 wethDelta = poolManager.currencyDelta(address(this), Currency.wrap(address(weth)));
            if (wethDelta > 0) {
                poolManager.take(Currency.wrap(address(weth)), address(this), uint256(wethDelta));
            }
            
            uint256 wethBalance = weth.balanceOf(address(this));
            uint256 actualRepay = amountWETHToRepay;
            if (actualRepay == type(uint256).max || actualRepay > wethBalance) {
                actualRepay = wethBalance;
            }
            
            if (actualRepay > 0) {
                weth.approve(address(aavePool), actualRepay);
                aavePool.repay(address(weth), actualRepay, 2, address(this));
            }
        }
        if (amountUSDCToWithdraw > 0) {
            aavePool.withdraw(usdc, amountUSDCToWithdraw, address(this));
        }
        // -------------------------------

        // 3. Add new liquidity
        poolManager.modifyLiquidity(
            poolKey, 
            IPoolManager.ModifyLiquidityParams({
                tickLower: newTickLower, 
                tickUpper: newTickUpper, 
                liquidityDelta: int256(newLiquidityDelta),
                salt: bytes32(0)
            }), 
            ""
        );

        // 4. Update State
        currentTickLower = newTickLower;
        currentTickUpper = newTickUpper;
        currentLiquidity = newLiquidityDelta;

        // 5. Flash Accounting Settlement
        _settleCurrency(currency0);
        _settleCurrency(currency1);
        
        return "";
    }
    
    function _settleCurrency(Currency currency) internal {
        int256 delta = poolManager.currencyDelta(address(this), currency);
        
        if (delta < 0) {
            uint256 amountOwed = uint256(-delta);
            poolManager.sync(currency);
            IERC20(Currency.unwrap(currency)).safeTransfer(address(poolManager), amountOwed);
            poolManager.settle();
        } else if (delta > 0) {
            poolManager.take(currency, address(this), uint256(delta));
        }
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

        emit Withdraw(caller, receiver, owner, assets, shares);
    }
}
