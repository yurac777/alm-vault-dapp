// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";

interface IALMVault_Singularity {
    function depositWithReferrer(uint256 assets, address receiver, address referrer) external returns (uint256);
}

/**
 * @title ALMZapper
 * @notice Stateless peripheral router. Zaps any ERC20 (or native ETH) into ALMVault_Singularity.
 *         Uses arbitrary DEX aggregator (1inch, 0x, Uniswap) via low-level call.
 */
contract ALMZapper is Ownable {
    using SafeERC20 for IERC20;

    IERC20 public immutable usdc;
    IALMVault_Singularity public vault;

    // Standard ETH address representation in aggregators
    address private constant ETH_ADDRESS = 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE;

    event Zapped(address indexed user, address indexed tokenIn, uint256 amountIn, uint256 usdcDeposited);
    event VaultUpdated(address oldVault, address newVault);

    constructor(address _usdc, address _vault, address _owner) Ownable(_owner) {
        require(_usdc != address(0) && _vault != address(0), "ALMZapper: Zero address");
        usdc = IERC20(_usdc);
        vault = IALMVault_Singularity(_vault);
    }

    function setVault(address _vault) external onlyOwner {
        require(_vault != address(0), "ALMZapper: Zero address");
        emit VaultUpdated(address(vault), _vault);
        vault = IALMVault_Singularity(_vault);
    }

    /**
     * @notice Zaps tokenIn to USDC and deposits into the Vault.
     * @param tokenIn The token to deposit (use 0xEeeee... for native ETH)
     * @param amountIn The amount of tokenIn to deposit
     * @param router The DEX aggregator router address (e.g. 1inch)
     * @param receiver The address that will receive the vault shares
     * @param referrer The referral address (B2B or direct)
     * @param swapData The low-level call data to execute on the router
     */
    function zapAndDeposit(
        address tokenIn,
        uint256 amountIn,
        address router,
        address receiver,
        address referrer,
        bytes calldata swapData
    ) external payable returns (uint256 shares) {
        require(amountIn > 0, "ALMZapper: Zero amount");
        require(receiver != address(0), "ALMZapper: Invalid receiver");

        bool isNative = (tokenIn == ETH_ADDRESS || tokenIn == address(0));

        if (!isNative) {
            // Transfer tokenIn from user
            IERC20(tokenIn).safeTransferFrom(msg.sender, address(this), amountIn);
        } else {
            require(msg.value >= amountIn, "ALMZapper: Insufficient msg.value");
        }

        uint256 usdcToDeposit;

        if (tokenIn == address(usdc)) {
            // No swap needed
            usdcToDeposit = amountIn;
        } else {
            require(router != address(0), "ALMZapper: Invalid router");

            // Approve router
            if (!isNative) {
                IERC20(tokenIn).forceApprove(router, amountIn);
            }

            // Execute Swap
            uint256 valueToSend = isNative ? amountIn : 0;
            (bool success, bytes memory returnData) = router.call{value: valueToSend}(swapData);
            if (!success) {
                if (returnData.length > 0) {
                    assembly {
                        let returndata_size := mload(returnData)
                        revert(add(32, returnData), returndata_size)
                    }
                } else {
                    revert("ALMZapper: Swap failed");
                }
            }

            // Clear approval just in case
            if (!isNative) {
                IERC20(tokenIn).forceApprove(router, 0);
            }

            // Check how much USDC we got
            usdcToDeposit = usdc.balanceOf(address(this));
            require(usdcToDeposit > 0, "ALMZapper: No USDC received from swap");
        }

        // Deposit into Vault
        usdc.forceApprove(address(vault), usdcToDeposit);
        shares = vault.depositWithReferrer(usdcToDeposit, receiver, referrer);

        // Refund any remaining tokenIn dust back to user
        if (!isNative && tokenIn != address(usdc)) {
            uint256 remainingIn = IERC20(tokenIn).balanceOf(address(this));
            if (remainingIn > 0) {
                IERC20(tokenIn).safeTransfer(msg.sender, remainingIn);
            }
        }

        // Refund any native ETH dust
        uint256 remainingEth = address(this).balance;
        if (remainingEth > 0) {
            (bool ethSuccess, ) = msg.sender.call{value: remainingEth}("");
            require(ethSuccess, "ALMZapper: ETH refund failed");
        }

        emit Zapped(msg.sender, tokenIn, amountIn, usdcToDeposit);
    }

    // Allow receiving ETH from swap outputs
    receive() external payable {}
}
