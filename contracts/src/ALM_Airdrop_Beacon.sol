// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract ALM_Airdrop_Beacon {
    event RewardsClaimed(address indexed user, uint256 amount);

    function triggerEvent(address user, uint256 amount) external {
        emit RewardsClaimed(user, amount);
    }
}
