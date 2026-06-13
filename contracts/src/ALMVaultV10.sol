// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC4626} from "openzeppelin-contracts/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {IPool, INonfungiblePositionManager} from "./interfaces/DeFiInterfaces.sol";

// ── Aave aToken (to read live collateral balance) ─────────────────────────
interface IAToken is IERC20 {
}

// ── Aave Price Oracle (to convert debt WETH → USD) ────────────────────────
interface IAaveOracle {
    function getAssetPrice(address asset) external view returns (uint256);
}

// ── Aave Data Provider (to get aToken and debt token addresses) ───────────
interface IAaveProtocolDataProvider {
    function getReserveTokensAddresses(address asset)
        external
        view
        returns (
            address aTokenAddress,
            address stableDebtTokenAddress,
            address variableDebtTokenAddress
        );
}

/**
 * @title  ALMVaultV10
 * @notice THE GOLDEN RELEASE. Delta-neutral ERC-4626 vault: USDC collateral in Aave, short WETH,
 *         liquidity in Uniswap V3.
 */
contract ALMVaultV10 is ERC4626, Ownable {
    using SafeERC20 for IERC20;

    // ── Roles ────────────────────────────────────────────────────────────────
    address public keeper;

    // ── External contracts ───────────────────────────────────────────────────
    IPool public aavePool;
    INonfungiblePositionManager public npm;
    IERC20 public weth;
    IAaveProtocolDataProvider public aaveDataProvider;
    IAaveOracle public aaveOracle;

    // ── Uniswap V3 position state ────────────────────────────────────────────
    uint256 public currentTokenId;
    uint128 public currentLiquidity;

    // --- Fees ---
    uint256 public withdrawalFeeBps = 50; // 0.5%
    address public feeRecipient;

    // --- Accounting ---
    uint256 public cachedUniV3ValueUSD; // Off-chain evaluated value in USDC (6 dec)
    int256 public netTotalDeposit;

    // --- Withdrawal Queue ---
    mapping(address => uint256) public withdrawalRequests;
    uint256 public totalWithdrawalRequests;

    // --- Events ---
    event KeeperUpdated(address oldKeeper, address newKeeper);
    event WithdrawalFeeUpdated(uint256 oldFee, uint256 newFee);
    event Rebalanced(uint256 tokenId, uint128 liquidity, uint256 uniV3ValueUSD);
    event CacheUpdated(uint256 uniV3ValueUSD);
    event WithdrawalRequested(address indexed user, uint256 shares);

    // ── Modifiers ─────────────────────────────────────────────────────────────
    modifier onlyKeeper() {
        require(msg.sender == keeper, "ALMVault: caller is not the keeper");
        _;
    }

    // ── Constructor ───────────────────────────────────────────────────────────
    constructor(
        IERC20 _asset,
        IERC20 _weth,
        address _initialOwner,
        address _aavePool,
        address _npm,
        address _aaveDataProvider,
        address _aaveOracle
    )
        ERC4626(_asset)
        ERC20("ALM Vault", "almUSD")
        Ownable(_initialOwner)
    {
        weth = _weth;
        aavePool = IPool(_aavePool);
        npm = INonfungiblePositionManager(_npm);
        feeRecipient = _initialOwner;

        aaveDataProvider = IAaveProtocolDataProvider(_aaveDataProvider);
        aaveOracle = IAaveOracle(_aaveOracle);

        // Max approvals
        _asset.approve(_npm, type(uint256).max);
        _asset.approve(_aavePool, type(uint256).max);
        _weth.approve(_npm, type(uint256).max);
        _weth.approve(_aavePool, type(uint256).max);
    }

    // ── Admin ─────────────────────────────────────────────────────────────────

    function setKeeper(address _keeper) external onlyOwner {
        require(_keeper != address(0), "ALMVault: keeper cannot be zero address");
        emit KeeperUpdated(keeper, _keeper);
        keeper = _keeper;
    }

    function setFeeRecipient(address _recipient) external onlyOwner {
        require(_recipient != address(0), "ALMVault: feeRecipient cannot be zero address");
        feeRecipient = _recipient;
    }

    function setWithdrawalFeeBps(uint256 _bps) external onlyOwner {
        require(_bps <= 500, "ALMVault: fee too high"); // max 5%
        withdrawalFeeBps = _bps;
    }

    // ── Core: totalAssets ──────────────────────────────────────────────────────

    function totalAssets() public view virtual override returns (uint256) {
        // 1. Free USDC in this contract
        uint256 freeUSDC = IERC20(asset()).balanceOf(address(this));

        // 2. Aave collateral: read aToken balance directly (auto-accrues interest)
        uint256 aUSDCBalance = 0;
        try aaveDataProvider.getReserveTokensAddresses(asset()) returns (
            address aTokenAddr, address, address
        ) {
            if (aTokenAddr != address(0)) {
                aUSDCBalance = IERC20(aTokenAddr).balanceOf(address(this));
            }
        } catch {}

        // 3. Uniswap V3 NFT value (keeper-cached, USDC 6-dec)
        uint256 uniValue = cachedUniV3ValueUSD;

        // 4. WETH debt → subtract at current oracle price
        uint256 debtUSDC = 0;
        try aaveDataProvider.getReserveTokensAddresses(address(weth)) returns (
            address, address, address varDebtAddr
        ) {
            if (varDebtAddr != address(0)) {
                uint256 wethDebt = IERC20(varDebtAddr).balanceOf(address(this));
                if (wethDebt > 0) {
                    uint256 wethPriceUSD8 = aaveOracle.getAssetPrice(address(weth));
                    debtUSDC = (wethDebt * wethPriceUSD8) / 1e20;
                }
            }
        } catch {}

        uint256 netAave = (aUSDCBalance > debtUSDC) ? (aUSDCBalance - debtUSDC) : 0;
        return freeUSDC + netAave + uniValue;
    }

    // ── Core: Rebalance ────────────────────────────────────────────────────────

    function _getUint256(bytes calldata data, uint256 offset) internal pure returns (uint256 res) {
        assembly { res := calldataload(add(data.offset, offset)) }
    }

    function _getInt256(bytes calldata data, uint256 offset) internal pure returns (int256 res) {
        assembly { res := calldataload(add(data.offset, offset)) }
    }

    function rebalance(uint256 uniV3ValueUSD, bytes calldata data) external onlyKeeper {
        cachedUniV3ValueUSD = uniV3ValueUSD;
        emit CacheUpdated(uniV3ValueUSD);

        address usdc = asset();
        address token0 = address(usdc) < address(weth) ? address(usdc) : address(weth);
        address token1 = address(usdc) < address(weth) ? address(weth) : address(usdc);

        // 1. Close old position
        if (currentTokenId != 0 && currentLiquidity > 0) {
            npm.decreaseLiquidity(INonfungiblePositionManager.DecreaseLiquidityParams({
                tokenId: currentTokenId,
                liquidity: currentLiquidity,
                amount0Min: 0,
                amount1Min: 0,
                deadline: block.timestamp
            }));
            npm.collect(INonfungiblePositionManager.CollectParams({
                tokenId: currentTokenId,
                recipient: address(this),
                amount0Max: type(uint128).max,
                amount1Max: type(uint128).max
            }));
            currentTokenId = 0;
            currentLiquidity = 0;
            cachedUniV3ValueUSD = 0;
        }

        // 2. Aave: repay WETH debt
        if (_getUint256(data, 288) > 0) {
            aavePool.repay(address(weth), _getUint256(data, 288), 2, address(this));
        }

        // 3. Aave: withdraw USDC collateral
        if (_getUint256(data, 320) > 0) {
            aavePool.withdraw(usdc, _getUint256(data, 320), address(this));
        }

        // 4. Aave: supply USDC
        if (_getUint256(data, 64) > 0) {
            aavePool.supply(usdc, _getUint256(data, 64), address(this), 0);
        }

        // 5. Aave: borrow WETH
        if (_getUint256(data, 0) != 0 && _getInt256(data, 32) > 0) {
            aavePool.borrow(address(weth), uint256(_getInt256(data, 32)), 2, 0, address(this));
        } else if (_getUint256(data, 96) > 0) {
            aavePool.borrow(address(weth), _getUint256(data, 96), 2, 0, address(this));
        }

        // 6. Open new Uniswap V3 position
        if (_getUint256(data, 192) > 0 || _getUint256(data, 224) > 0) {
            (uint256 tokenId, uint128 liquidity, , ) = npm.mint(INonfungiblePositionManager.MintParams({
                token0: token0,
                token1: token1,
                fee: uint24(_getUint256(data, 256)),
                tickLower: int24(int256(_getInt256(data, 128))),
                tickUpper: int24(int256(_getInt256(data, 160))),
                amount0Desired: _getUint256(data, 192),
                amount1Desired: _getUint256(data, 224),
                amount0Min: _getUint256(data, 352),
                amount1Min: _getUint256(data, 384),
                recipient: address(this),
                deadline: block.timestamp
            }));
            currentTokenId = tokenId;
            currentLiquidity = liquidity;
            cachedUniV3ValueUSD = uniV3ValueUSD;
            emit Rebalanced(tokenId, liquidity, uniV3ValueUSD);
        } else {
            emit Rebalanced(0, 0, uniV3ValueUSD);
        }

        // 7. Auto-Sweep Excess WETH → repay debt
        uint256 excessWeth = weth.balanceOf(address(this));
        if (excessWeth > 0) {
            aavePool.repay(address(weth), excessWeth, 2, address(this));
        }
    }

    function updateCache(uint256 uniV3ValueUSD) external onlyKeeper {
        cachedUniV3ValueUSD = uniV3ValueUSD;
        emit CacheUpdated(uniV3ValueUSD);
    }

    // ── ERC-4626 Internal Overrides ───────────────────────────────────────────

    function _deposit(
        address caller,
        address receiver,
        uint256 assets,
        uint256 shares
    ) internal virtual override {
        super._deposit(caller, receiver, assets, shares);
        netTotalDeposit += int256(assets);
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

        uint256 freeUSDC = IERC20(asset()).balanceOf(address(this));
        require(freeUSDC >= assets, "ALMVault: Insufficient free USDC. Request withdrawal first.");

        if (withdrawalRequests[owner] > 0) {
            if (withdrawalRequests[owner] >= shares) {
                withdrawalRequests[owner] -= shares;
                totalWithdrawalRequests -= shares;
            } else {
                totalWithdrawalRequests -= withdrawalRequests[owner];
                withdrawalRequests[owner] = 0;
            }
        }

        if (fee > 0) {
            IERC20(asset()).safeTransfer(feeRecipient, fee);
        }
        IERC20(asset()).safeTransfer(receiver, payout);

        netTotalDeposit -= int256(assets);
        emit Withdraw(caller, receiver, owner, assets, shares);
    }

    function requestWithdrawal(uint256 shares) external {
        require(balanceOf(msg.sender) >= shares, "ALMVault: Insufficient shares");
        withdrawalRequests[msg.sender] += shares;
        totalWithdrawalRequests += shares;
        emit WithdrawalRequested(msg.sender, shares);
    }

    // ── Emergency ─────────────────────────────────────────────────────────────

    function rescueFunds(address token, uint256 amount) external onlyOwner {
        require(token != address(0), "ALMVault: Invalid token");
        IERC20(token).safeTransfer(msg.sender, amount);
    }
}
