// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC4626} from "openzeppelin-contracts/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {IPool, INonfungiblePositionManager} from "./interfaces/DeFiInterfaces.sol";

interface IAToken is IERC20 {}
interface IAaveOracle {
    function getAssetPrice(address asset) external view returns (uint256);
}
interface IAaveProtocolDataProvider {
    function getReserveTokensAddresses(address asset) external view returns (address aTokenAddress, address stableDebtTokenAddress, address variableDebtTokenAddress);
}

interface IERC3156FlashBorrower {
    function onFlashLoan(address initiator, address token, uint256 amount, uint256 fee, bytes calldata data) external returns (bytes32);
}

interface IERC3156FlashLender {
    function maxFlashLoan(address token) external view returns (uint256);
    function flashFee(address token, uint256 amount) external view returns (uint256);
    function flashLoan(IERC3156FlashBorrower receiver, address token, uint256 amount, bytes calldata data) external returns (bool);
}

contract ALMVault_Singularity is ERC4626, Ownable, IERC3156FlashLender {
    using SafeERC20 for IERC20;

    // ── Roles ────────────────────────────────────────────────────────────────
    address public keeper;
    address public treasury;

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
    uint256 public depositFeeBps = 100; // 1%
    uint256 public performanceFeeBps = 1000; // 10%
    address public feeRecipient;

    // --- Referrals & B2B ---
    mapping(address => address) public referrers;
    mapping(address => bool) public registeredPartners;

    // --- Accounting ---
    uint256 public cachedUniV3ValueUSD; // Off-chain evaluated value in USDC (6 dec)
    int256 public netTotalDeposit;

    // --- Withdrawal Queue ---
    mapping(address => uint256) public withdrawalRequests;
    uint256 public totalWithdrawalRequests;

    // --- Events ---
    event KeeperUpdated(address oldKeeper, address newKeeper);
    event TreasuryUpdated(address oldTreasury, address newTreasury);
    event FeesUpdated(uint256 withdrawal, uint256 deposit, uint256 performance);
    event PartnerRegistered(address partner, bool status);
    event Rebalanced(uint256 tokenId, uint128 liquidity, uint256 uniV3ValueUSD);
    event CacheUpdated(uint256 uniV3ValueUSD);
    event WithdrawalRequested(address indexed user, uint256 shares);
    event ReferralRegistered(address indexed user, address indexed referrer);
    event DepositFeeDistributed(address indexed referrer, uint256 amount);
    event RewardsClaimed(address indexed user, uint256 amount);

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
        ERC20("ALM Vault Singularity", "almUSDS")
        Ownable(_initialOwner)
    {
        weth = _weth;
        aavePool = IPool(_aavePool);
        npm = INonfungiblePositionManager(_npm);
        feeRecipient = _initialOwner;
        treasury = _initialOwner;

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

    function setTreasury(address _treasury) external onlyOwner {
        require(_treasury != address(0), "ALMVault: treasury cannot be zero address");
        emit TreasuryUpdated(treasury, _treasury);
        treasury = _treasury;
    }

    function setFees(uint256 _withdrawalBps, uint256 _depositBps, uint256 _performanceBps) external onlyOwner {
        require(_withdrawalBps <= 500 && _depositBps <= 500 && _performanceBps <= 5000, "ALMVault: fees too high");
        withdrawalFeeBps = _withdrawalBps;
        depositFeeBps = _depositBps;
        performanceFeeBps = _performanceBps;
        emit FeesUpdated(_withdrawalBps, _depositBps, _performanceBps);
    }

    function setPartnerStatus(address partner, bool status) external onlyOwner {
        registeredPartners[partner] = status;
        emit PartnerRegistered(partner, status);
    }

    // ── Core: totalAssets ──────────────────────────────────────────────────────

    function totalAssets() public view virtual override returns (uint256) {
        uint256 freeUSDC = IERC20(asset()).balanceOf(address(this));
        uint256 aUSDCBalance = 0;
        try aaveDataProvider.getReserveTokensAddresses(asset()) returns (address aTokenAddr, address, address) {
            if (aTokenAddr != address(0)) {
                aUSDCBalance = IERC20(aTokenAddr).balanceOf(address(this));
            }
        } catch {}

        uint256 uniValue = cachedUniV3ValueUSD;
        uint256 debtUSDC = 0;
        try aaveDataProvider.getReserveTokensAddresses(address(weth)) returns (address, address, address varDebtAddr) {
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

        // 1. Close old position & HARVEST PERFORMANCE FEE
        if (currentTokenId != 0 && currentLiquidity > 0) {
            // A. Collect pure fees first
            (uint256 fee0, uint256 fee1) = npm.collect(INonfungiblePositionManager.CollectParams({
                tokenId: currentTokenId,
                recipient: address(this),
                amount0Max: type(uint128).max,
                amount1Max: type(uint128).max
            }));

            // Process performance fee to Treasury
            if (fee0 > 0 && performanceFeeBps > 0) {
                uint256 pFee0 = (fee0 * performanceFeeBps) / 10000;
                IERC20(token0).safeTransfer(treasury, pFee0);
            }
            if (fee1 > 0 && performanceFeeBps > 0) {
                uint256 pFee1 = (fee1 * performanceFeeBps) / 10000;
                IERC20(token1).safeTransfer(treasury, pFee1);
            }

            // B. Decrease liquidity (Principal)
            npm.decreaseLiquidity(INonfungiblePositionManager.DecreaseLiquidityParams({
                tokenId: currentTokenId,
                liquidity: currentLiquidity,
                amount0Min: 0,
                amount1Min: 0,
                deadline: block.timestamp
            }));
            
            // C. Collect the principal
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

        // 2. Aave: repay WETH debt (Fix: check actual debt to prevent revert)
        if (_getUint256(data, 288) > 0) {
            uint256 currentDebt = _getWethDebt();
            if (currentDebt > 0) {
                uint256 reqRepay = _getUint256(data, 288);
                uint256 repayAmount = reqRepay > currentDebt ? currentDebt : reqRepay;
                aavePool.repay(address(weth), repayAmount, 2, address(this));
            }
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

        // 7. Auto-Sweep Excess WETH → repay debt (Fix: check actual debt)
        uint256 excessWeth = weth.balanceOf(address(this));
        if (excessWeth > 0) {
            uint256 currentDebt = _getWethDebt();
            if (currentDebt > 0) {
                uint256 repayAmount = excessWeth > currentDebt ? currentDebt : excessWeth;
                aavePool.repay(address(weth), repayAmount, 2, address(this));
            }
        }
    }

    function _getWethDebt() internal view returns (uint256) {
        try aaveDataProvider.getReserveTokensAddresses(address(weth)) returns (address, address, address varDebtAddr) {
            if (varDebtAddr != address(0)) {
                return IERC20(varDebtAddr).balanceOf(address(this));
            }
        } catch {}
        return 0;
    }

    function updateCache(uint256 uniV3ValueUSD) external onlyKeeper {
        cachedUniV3ValueUSD = uniV3ValueUSD;
        emit CacheUpdated(uniV3ValueUSD);
    }

    // ── Referral & Deposit Logic ──────────────────────────────────────────────

    function depositWithReferrer(uint256 assets, address receiver, address referrer) public returns (uint256) {
        require(assets > 0, "ALMVault: Assets must be > 0");
        
        // Setup referral
        if (referrer != address(0) && referrer != msg.sender && referrers[msg.sender] == address(0)) {
            referrers[msg.sender] = referrer;
            emit ReferralRegistered(msg.sender, referrer);
        }

        // Take deposit fee
        uint256 fee = (assets * depositFeeBps) / 10000;
        uint256 principal = assets - fee;

        // Calculate shares BEFORE transferring assets
        uint256 shares = previewDeposit(principal);
        require(shares > 0, "ALMVault: Zero shares minted");

        // Transfer assets from user
        SafeERC20.safeTransferFrom(IERC20(asset()), msg.sender, address(this), assets);

        if (fee > 0) {
            _distributeDepositFee(fee, referrers[msg.sender]);
        }
        
        _mint(receiver, shares);
        netTotalDeposit += int256(principal);
        
        emit Deposit(msg.sender, receiver, principal, shares);
        return shares;
    }

    function _distributeDepositFee(uint256 fee, address currentReferrer) internal {
        if (currentReferrer == address(0)) {
            IERC20(asset()).safeTransfer(treasury, fee);
            return;
        }

        if (registeredPartners[currentReferrer]) {
            uint256 partnerCut = (fee * 80) / 100;
            uint256 treasuryCut = fee - partnerCut;
            IERC20(asset()).safeTransfer(currentReferrer, partnerCut);
            emit DepositFeeDistributed(currentReferrer, partnerCut);
            if (treasuryCut > 0) IERC20(asset()).safeTransfer(treasury, treasuryCut);
        } else {
            uint256 directCut = (fee * 50) / 100;
            address grandparent = referrers[currentReferrer];
            uint256 grandCut = 0;
            if (grandparent != address(0)) {
                grandCut = (fee * 10) / 100;
                IERC20(asset()).safeTransfer(grandparent, grandCut);
                emit DepositFeeDistributed(grandparent, grandCut);
            }
            
            uint256 treasuryCut = fee - directCut - grandCut;
            IERC20(asset()).safeTransfer(currentReferrer, directCut);
            emit DepositFeeDistributed(currentReferrer, directCut);
            if (treasuryCut > 0) IERC20(asset()).safeTransfer(treasury, treasuryCut);
        }
    }

    // ── ERC-4626 Internal Overrides ───────────────────────────────────────────

    function deposit(uint256 assets, address receiver) public virtual override returns (uint256) {
        return depositWithReferrer(assets, receiver, address(0));
    }

    function mint(uint256 /* shares */, address /* receiver */) public virtual override returns (uint256) {
        revert("ALMVault: Use depositWithReferrer");
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
            IERC20(asset()).safeTransfer(treasury, fee);
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

    // ── Rewards ───────────────────────────────────────────────────────────────

    function claimRewards() external {
        // Dummy logic for event integration testing
        emit RewardsClaimed(msg.sender, 0);
    }

    // ── Emergency ─────────────────────────────────────────────────────────────

    function rescueFunds(address token, uint256 amount) external onlyOwner {
        require(token != address(0), "ALMVault: Invalid token");
        IERC20(token).safeTransfer(msg.sender, amount);
    }

    // ── ERC-3156 FlashLender ─────────────────────────────────────────────────
    bytes32 private constant CALLBACK_SUCCESS = keccak256("ERC3156FlashBorrower.onFlashLoan");

    function maxFlashLoan(address token) public view override returns (uint256) {
        if (token == asset()) {
            return totalAssets();
        }
        return 0;
    }

    function flashFee(address token, uint256 amount) public view override returns (uint256) {
        require(token == asset(), "FlashLender: Unsupported currency");
        return (amount * 1) / 10000; // 0.01%
    }

    function flashLoan(IERC3156FlashBorrower receiver, address token, uint256 amount, bytes calldata data) external override returns (bool) {
        require(token == asset(), "FlashLender: Unsupported currency");
        uint256 fee = flashFee(token, amount);
        
        uint256 initialBalance = IERC20(token).balanceOf(address(this));
        require(initialBalance >= amount, "FlashLender: Not enough liquidity");
        
        IERC20(token).safeTransfer(address(receiver), amount);
        
        require(
            receiver.onFlashLoan(msg.sender, token, amount, fee, data) == CALLBACK_SUCCESS,
            "FlashLender: Callback failed"
        );
        
        IERC20(token).safeTransferFrom(address(receiver), address(this), amount + fee);
        
        uint256 newBalance = IERC20(token).balanceOf(address(this));
        require(newBalance >= initialBalance + fee, "FlashLender: Repayment failed");
        
        return true;
    }
}
