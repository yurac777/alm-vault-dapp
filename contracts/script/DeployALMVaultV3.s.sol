// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/ALMVaultV3.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";

contract DeployALMVaultV3 is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployerAddress = vm.envAddress("WALLET_ADDRESS");

        address usdc = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
        address weth = 0x4200000000000000000000000000000000000006;
        address aavePool = 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5;
        address npm = 0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1;

        vm.startBroadcast(deployerPrivateKey);

        ALMVaultV3 vault = new ALMVaultV3(
            IERC20(usdc),
            IERC20(weth),
            deployerAddress,
            aavePool,
            npm
        );

        console.log("ALMVaultV3 deployed to:", address(vault));

        vm.stopBroadcast();
    }
}
