// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";

/**
 * @title ALMToken
 * @dev Utility Token ($vALM) for the ALM Vault ecosystem.
 * Used for Liquidity Mining and Protocol Rewards.
 * Only the ALMVault (owner) can mint new tokens to reward depositors.
 */
contract ALMToken is ERC20, Ownable {
    
    // The ALMVault contract will be the owner
    constructor(address initialOwner) 
        ERC20("ALM Vault Token", "vALM") 
        Ownable(initialOwner) 
    {}

    /**
     * @dev Mints new $vALM tokens. Can only be called by the Vault (Owner).
     * @param to The address to receive the minted tokens.
     * @param amount The amount of tokens to mint.
     */
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}
