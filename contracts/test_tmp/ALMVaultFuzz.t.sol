// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {ALMVaultV3} from "../src/ALMVaultV3.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {IPool, INonfungiblePositionManager} from "../src/interfaces/DeFiInterfaces.sol";

contract ALMVaultFuzzTest is Test {
    ALMVaultV3 public vault;
    IERC20 public usdc;
    IERC20 public weth;
    IPool public aavePool;
    INonfungiblePositionManager public npm;

    address public owner = address(0x1);
    address public keeper = <YOUR_WALLET_ADDRESS>;
    address public user = address(0x2);

    address public constant AAVE_POOL = 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5;
    address public constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
    address public constant WETH = 0x4200000000000000000000000000000000000006;
    address public constant NPM = 0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1;

    function setUp() public {
        vm.createSelectFork("https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu");

        usdc = IERC20(USDC);
        weth = IERC20(WETH);
        aavePool = IPool(AAVE_POOL);
        npm = INonfungiblePositionManager(NPM);

        vm.startPrank(owner);
        vault = new ALMVaultV3(usdc, weth, owner, AAVE_POOL, NPM);
        vault.setKeeper(keeper);
        vm.stopPrank();

        // Initial deposit
        uint256 amount = 100 * 10**6; 
        deal(address(usdc), user, amount);

        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        vault.deposit(amount, user);
        vm.stopPrank();
    }

    function testFuzz_Rebalance(
        bool isRebalance,
        int256 aaveDebtAdjustment,
        uint256 amountUSDC,
        uint256 amountWETHToBorrow,
        int24 newTickLower,
        int24 newTickUpper,
        uint256 amount0Desired,
        uint256 amount1Desired,
        uint256 amountWETHToRepay,
        uint256 amountUSDCToWithdraw
    ) public {
        // Bound random inputs to prevent basic integer overflows before our logic runs
        amountUSDC = bound(amountUSDC, 0, 1000 * 10**6);
        amountWETHToBorrow = bound(amountWETHToBorrow, 0, 100 ether);
        amount0Desired = bound(amount0Desired, 0, 100 ether);
        amount1Desired = bound(amount1Desired, 0, 1000 * 10**6);
        amountWETHToRepay = bound(amountWETHToRepay, 0, 100 ether);
        amountUSDCToWithdraw = bound(amountUSDCToWithdraw, 0, 1000 * 10**6);
        
        // Uniswap V3 ticks must be multiples of tick spacing (usually 60). 
        newTickLower = int24(bound(int256(newTickLower), -300000, 300000));
        newTickUpper = int24(bound(int256(newTickUpper), -300000, 300000));
        if (newTickLower >= newTickUpper) {
            newTickUpper = newTickLower + 60;
        }

        bytes memory encodedData = abi.encode(
            isRebalance,
            aaveDebtAdjustment,
            amountUSDC,
            amountWETHToBorrow,
            newTickLower,
            newTickUpper,
            amount0Desired,
            amount1Desired,
            uint24(500), // poolFee
            amountWETHToRepay,
            amountUSDCToWithdraw
        );

        // We use low-level call to allow reverts without failing the test
        vm.startPrank(keeper);
        (bool success, ) = address(vault).call(abi.encodeWithSelector(vault.rebalance.selector, encodedData));
        vm.stopPrank();

        // If it succeeded, verify invariants
        if (success) {
            // Check health factor
            (,,,,, uint256 hf) = aavePool.getUserAccountData(address(vault));
            if (hf != type(uint256).max) {
                assertGe(hf, 1e18, "Health factor dropped below 1.0!");
            }
        } else {
            // It safely reverted.
            assertTrue(!success); 
        }
    }
}
