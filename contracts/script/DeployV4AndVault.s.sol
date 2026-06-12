// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import {ALMVault} from "../src/ALMVault.sol";
import {PoolManager} from "v4-core/PoolManager.sol";
import {IPoolManager} from "v4-core/interfaces/IPoolManager.sol";
import {PoolKey} from "v4-core/types/PoolKey.sol";
import {Currency, CurrencyLibrary} from "v4-core/types/Currency.sol";
import {IHooks} from "v4-core/interfaces/IHooks.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";

contract DeployV4AndVault is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        
        vm.startBroadcast(deployerPrivateKey);

        address usdc = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
        address weth = 0x4200000000000000000000000000000000000006;
        address owner = <YOUR_WALLET_ADDRESS>;
        address aavePool = 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5;

        // 1. Existing PoolManager (Uniswap V4 canonical address on Base Mainnet)
        address poolManagerAddr = 0x000000000004444c5dc75cB358380D2e3dE08A90;
        console.log("Using existing PoolManager at:", poolManagerAddr);

        // 3. Deploy ALMVault
        ALMVault vault = new ALMVault(
            IERC20(usdc),
            IERC20(weth),
            owner,
            aavePool,
            poolManagerAddr
        );
        console.log("ALMVault deployed at:", address(vault));

        vault.setKeeper(<YOUR_WALLET_ADDRESS>);
        
        vm.stopBroadcast();
    }
}
