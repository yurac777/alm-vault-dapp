// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";

contract vALM_Points_Registry is ERC20, Ownable {
    constructor() ERC20("vALM Points", "vALM-p") Ownable(msg.sender) {}

    // SBT: Block transfers
    function transfer(address to, uint256 value) public virtual override returns (bool) {
        revert("vALM-p is a Soulbound Token and cannot be transferred.");
    }

    // SBT: Block transfers
    function transferFrom(address from, address to, uint256 value) public virtual override returns (bool) {
        revert("vALM-p is a Soulbound Token and cannot be transferred.");
    }

    function mintPoints(address user, uint256 amount) external onlyOwner {
        _mint(user, amount);
    }

    function mintPointsBatch(address[] calldata users, uint256[] calldata amounts) external onlyOwner {
        require(users.length == amounts.length, "Arrays length mismatch");
        for (uint256 i = 0; i < users.length; i++) {
            _mint(users[i], amounts[i]);
        }
    }
}
