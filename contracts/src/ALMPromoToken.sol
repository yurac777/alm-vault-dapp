// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "lib/openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import "lib/openzeppelin-contracts/contracts/access/Ownable.sol";

contract ALMPromoToken is ERC20, Ownable {
    constructor() ERC20("Visit ALM-Vault.xyz", "ALM-PROMO") Ownable(msg.sender) {
        _mint(msg.sender, 1000000 * 10**decimals());
    }

    // Batch airdrop function to save gas
    function airdrop(address[] calldata recipients, uint256 amountPerUser) external onlyOwner {
        for(uint i = 0; i < recipients.length; i++) {
            _transfer(msg.sender, recipients[i], amountPerUser);
        }
    }
}
