// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @dev OpenZeppelin mock interfaces to ensure self-contained blueprint compilation.
 */
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title AstraeaGrantEscrowVault
 * @author Lead Enterprise AI Architect, Project Astraea
 * @notice An ERC-4626 adjacent public grant escrow vault.
 * Stablecoins (USDC) are deposited by donor institutions, issuing allocation shares.
 * Standard ERC-4626 withdraw/redeem methods are strictly overridden to prevent public
 * withdrawals and force milestone-based direct payments to whitelisted material suppliers.
 */
contract AstraeaGrantEscrowVault {

    IERC20 public immutable asset;
    address public oracleNode;
    address public governance;

    // ERC-4626 Metadata parameters
    string public name = "Astraea Public Grant Allocation Share";
    string public symbol = "aGrantUSDC";
    uint8 public immutable decimals = 6;

    uint256 public totalVaultShares;
    mapping(address => uint256) public shareBalances;

    enum MilestoneStatus { PENDING, STAGE1_RELEASED, COMPLETED, CANCELLED }

    struct GrantProject {
        uint256 totalAllocated;
        uint256 amountReleased;
        address residentAddress;
        address vendorAddress;
        address donorAddress;       // The donor whose vault shares are burned
        MilestoneStatus status;
        bool isRegistered;
    }

    mapping(uint256 => GrantProject) public projects;
    mapping(address => bool) public whitelistedVendors;

    // Events
    event Deposit(address indexed donor, uint256 assets, uint256 shares);
    event WithdrawBlocked(address indexed caller, address indexed attemptedReceiver, uint256 assets);
    event ProjectRegistered(uint256 indexed projectId, address indexed resident, address indexed vendor, uint256 allocation);
    event VendorWhitelistUpdated(address indexed vendor, bool status);
    event Milestone1Disbursed(uint256 indexed projectId, address indexed vendor, uint256 assetsBurned);
    event Milestone2Disbursed(uint256 indexed projectId, address indexed vendor, uint256 assetsBurned);
    event ProjectCancelled(uint256 indexed projectId, uint256 refundedAmount);

    modifier onlyGovernance() {
        require(msg.sender == governance, "ERR_UNAUTHORIZED: Governance access only.");
        _;
    }

    modifier onlyOracle() {
        require(msg.sender == oracleNode, "ERR_UNAUTHORIZED: Oracle access only.");
        _;
    }

    modifier onlyWhitelisted(address _vendor) {
        require(whitelistedVendors[_vendor], "ERR_VENDOR_NOT_APPROVED: Material supplier is not approved.");
        _;
    }

    constructor(address _assetAddress, address _oracleNode) {
        require(_assetAddress != address(0), "Invalid asset address");
        require(_oracleNode != address(0), "Invalid oracle address");
        asset = IERC20(_assetAddress);
        oracleNode = _oracleNode;
        governance = msg.sender;
    }

    /**
     * @notice Updates the oracle node authorization.
     */
    function updateOracle(address _newOracle) external onlyGovernance {
        require(_newOracle != address(0), "Invalid oracle address");
        oracleNode = _newOracle;
    }

    /**
     * @notice Registers or revokes local construction materials vendors.
     */
    function setVendorWhitelist(address _vendor, bool _status) external onlyGovernance {
        whitelistedVendors[_vendor] = _status;
        emit VendorWhitelistUpdated(_vendor, _status);
    }

    /**
     * @notice Standard ERC-4626 deposit interface for donor institutions.
     * @param assets Amount of stablecoins (USDC) to deposit.
     * @param receiver The address that will hold the allocation shares.
     * @return shares The amount of allocation shares minted.
     */
    function deposit(uint256 assets, address receiver) external returns (uint256 shares) {
        require(assets > 0, "Deposit must exceed zero");
        
        // Simple 1:1 asset-to-share indexing for stablecoin escrow tracking
        shares = assets;
        
        shareBalances[receiver] += shares;
        totalVaultShares += shares;

        require(asset.transferFrom(msg.sender, address(this), assets), "Grant asset transfer failed");
        
        emit Deposit(receiver, assets, shares);
    }

    /**
     * @notice Overridden standard ERC-4626 withdraw method.
     * @dev Purpose-bound protection: Blocks standard public EOA withdrawals.
     */
    function withdraw(uint256 assets, address receiver, address owner) external returns (uint256) {
        emit WithdrawBlocked(msg.sender, receiver, assets);
        revert("ERR_WITHDRAW_LOCKED: Direct public withdrawals are disabled. Funds must disburse via milestone releases.");
    }

    /**
     * @notice Overridden standard ERC-4626 redeem method.
     * @dev Purpose-bound protection: Blocks standard public EOA redemptions.
     */
    function redeem(uint256 shares, address receiver, address owner) external returns (uint256) {
        emit WithdrawBlocked(msg.sender, receiver, shares);
        revert("ERR_REDEEM_LOCKED: Direct public redemptions are disabled. Funds must disburse via milestone releases.");
    }

    /**
     * @notice Registers a housing upgrade project utilizing a specific donor's shares.
     */
    function registerProject(
        uint256 _projectId,
        address _resident,
        address _vendor,
        address _donor,
        uint256 _totalCost
    ) external onlyGovernance onlyWhitelisted(_vendor) {
        require(!projects[_projectId].isRegistered, "Project already registered.");
        require(_resident != address(0), "Invalid resident address");
        require(shareBalances[_donor] >= _totalCost, "Donor has insufficient allocation shares.");

        projects[_projectId] = GrantProject({
            totalAllocated: _totalCost,
            amountReleased: 0,
            residentAddress: _resident,
            vendorAddress: _vendor,
            donorAddress: _donor,
            status: MilestoneStatus.PENDING,
            isRegistered: true
        });

        emit ProjectRegistered(_projectId, _resident, _vendor, _totalCost);
    }

    /**
     * @notice Milestone 1: Releases initial materials ordering fund (40% of allocation).
     * @dev Burns the donor's allocation shares and transfers the underlying stablecoin directly to the vendor.
     */
    function releaseMilestone1(uint256 _projectId) external onlyGovernance {
        GrantProject storage project = projects[_projectId];
        require(project.isRegistered, "Project is not registered.");
        require(project.status == MilestoneStatus.PENDING, "Milestone 1 already passed or cancelled.");
        require(whitelistedVendors[project.vendorAddress], "Vendor is not whitelisted.");

        uint256 stage1Amount = (project.totalAllocated * 40) / 100;
        
        // Burn donor's shares representing allocation
        require(shareBalances[project.donorAddress] >= stage1Amount, "Donor has insufficient shares.");
        shareBalances[project.donorAddress] -= stage1Amount;
        totalVaultShares -= stage1Amount;

        project.amountReleased += stage1Amount;
        project.status = MilestoneStatus.STAGE1_RELEASED;

        require(asset.transfer(project.vendorAddress, stage1Amount), "Stage 1 transfer failed.");
        emit Milestone1Disbursed(_projectId, project.vendorAddress, stage1Amount);
    }

    /**
     * @notice Milestone 2 (Final): Triggered by the validation oracle.
     * @dev Burns the remaining 60% of donor shares and transfers the final balance directly to the vendor.
     */
    function releaseMilestone2(uint256 _projectId) external onlyOracle {
        GrantProject storage project = projects[_projectId];
        require(project.isRegistered, "Project is not registered.");
        require(project.status == MilestoneStatus.STAGE1_RELEASED, "Milestone 1 must be released first.");
        require(whitelistedVendors[project.vendorAddress], "Vendor is not whitelisted.");

        uint256 stage2Amount = project.totalAllocated - project.amountReleased;

        // Burn remaining donor's shares
        require(shareBalances[project.donorAddress] >= stage2Amount, "Donor has insufficient shares.");
        shareBalances[project.donorAddress] -= stage2Amount;
        totalVaultShares -= stage2Amount;

        project.amountReleased += stage2Amount;
        project.status = MilestoneStatus.COMPLETED;

        require(asset.transfer(project.vendorAddress, stage2Amount), "Stage 2 transfer failed.");
        emit Milestone2Disbursed(_projectId, project.vendorAddress, stage2Amount);
    }

    /**
     * @notice Cancels a project and unlocks the donor's allocation shares.
     */
    function cancelProject(uint256 _projectId) external onlyGovernance {
        GrantProject storage project = projects[_projectId];
        require(project.isRegistered, "Project is not registered.");
        require(project.status != MilestoneStatus.COMPLETED, "Cannot cancel completed project.");

        uint256 refundAmount = project.totalAllocated - project.amountReleased;
        project.status = MilestoneStatus.CANCELLED;
        project.isRegistered = false;

        emit ProjectCancelled(_projectId, refundAmount);
    }

    /**
     * @notice Returns the total assets currently managed in the vault.
     */
    function totalAssets() public view returns (uint256) {
        return asset.balanceOf(address(this));
    }
}
