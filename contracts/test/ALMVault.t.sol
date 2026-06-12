// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {ALMVault} from "../src/ALMVault.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {PoolManager} from "v4-core/PoolManager.sol";
import {PoolKey} from "v4-core/types/PoolKey.sol";
import {Currency, CurrencyLibrary} from "v4-core/types/Currency.sol";
import {IHooks} from "v4-core/interfaces/IHooks.sol";

contract ALMVaultTest is Test {
    ALMVault public vault;
    IERC20 public usdc;
    IERC20 public weth;
    PoolManager public poolManager;

    address public owner = address(0x1);
    address public keeper = <YOUR_WALLET_ADDRESS>;
    address public user = address(0x2);

    address public constant AAVE_POOL = 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5;

    function setUp() public {
        vm.createSelectFork("https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu");

        usdc = IERC20(0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913);
        weth = IERC20(0x4200000000000000000000000000000000000006);

        // Деплоим настоящий PoolManager
        poolManager = new PoolManager(address(this));

        // Формируем PoolKey
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
            fee: 3000,
            tickSpacing: 60,
            hooks: IHooks(address(0))
        });

        // Инициализируем пул 1:1 price
        poolManager.initialize(poolKey, 79228162514264337593543950336);

        // Деплоим Vault
        vm.startPrank(owner);
        vault = new ALMVault(usdc, weth, owner, AAVE_POOL, address(poolManager));
        vault.setKeeper(keeper);
        vm.stopPrank();
    }

    function testDepositAndRebalance() public {
        uint256 amount = 100 * 10**6; 
        deal(address(usdc), user, amount);

        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        uint256 shares = vault.deposit(amount, user);
        vm.stopPrank();

        assertEq(vault.balanceOf(user), shares);
        assertGt(shares, 0);

        int24 tickLower = -6000;
        int24 tickUpper = 6000;
        uint256 liquidityDelta = 10000; // Немного ликвидности

        // We supply 50 USDC to Aave, and borrow 0.01 WETH. 
        uint256 amountToSupply = 50 * 10**6;
        bytes memory encodedData = abi.encode(
            false, // isRebalance
            int24(0), // oldTickLower
            int24(0), // oldTickUpper
            uint256(0), // oldLiquidity
            int256(0), // aaveDebtAdjustment
            amountToSupply, // amountUSDC
            0.01 ether, // amountWETHToBorrow
            tickLower, // newTickLower
            tickUpper, // newTickUpper
            liquidityDelta, // newLiquidityDelta
            uint256(0), // amountWETHToRepay
            uint256(0)  // amountUSDCToWithdraw
        );
        
        vm.startPrank(keeper);
        vault.rebalance(encodedData);
        vm.stopPrank();

        uint256 wethBalance = weth.balanceOf(address(vault));
        console.log("WETH balance after rebalance:", wethBalance);
        
        uint256 usdcBalance = usdc.balanceOf(address(vault));
        console.log("USDC balance after rebalance:", usdcBalance);
    }

    function testEmergencyUnwind() public {
        testDepositAndRebalance();

        uint256 currentLiquidity = vault.currentLiquidity();
        int24 currentTickLower = vault.currentTickLower();
        int24 currentTickUpper = vault.currentTickUpper();
        
        uint256 maxUint = type(uint256).max;
        
        bytes memory unwindData = abi.encode(
            true, // isRebalance
            currentTickLower, // oldTickLower
            currentTickUpper, // oldTickUpper
            currentLiquidity, // oldLiquidity
            int256(0), // aaveDebtAdjustment
            uint256(0), // amountUSDC
            uint256(0), // amountWETHToBorrow
            currentTickLower, // newTickLower
            currentTickUpper, // newTickUpper
            uint256(0), // newLiquidityDelta
            maxUint, // amountWETHToRepay (MAX)
            maxUint  // amountUSDCToWithdraw (MAX)
        );

        vm.startPrank(keeper);
        vault.rebalance(unwindData);
        vm.stopPrank();

        assertEq(vault.currentLiquidity(), 0);
        
        // Vault should have its USDC back
        uint256 usdcBalanceAfterUnwind = usdc.balanceOf(address(vault));
        console.log("USDC balance after unwind:", usdcBalanceAfterUnwind);
        assertGt(usdcBalanceAfterUnwind, 50 * 10**6);
        
        // User should be able to withdraw
        vm.startPrank(user);
        uint256 maxWithdraw = vault.maxWithdraw(user);
        vault.withdraw(maxWithdraw, user, user);
        vm.stopPrank();
        
        console.log("User USDC balance after withdraw:", usdc.balanceOf(user));
    }
}
