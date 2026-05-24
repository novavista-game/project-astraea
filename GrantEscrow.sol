// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title GrantEscrow
 * @author Lead Enterprise AI Architect, Project Astraea
 * @notice An ERC-4626 adjacent smart contract designed to manage public and institutional grants (B2G).
 * Facilitates milestone-based stablecoin disbursements directly to whitelisted Local Hardware Vendors,
 * enforcing a strict lock preventing direct EOA extraction by residents.
 */
contract GrantEscrow {
    
    IERC20 public immutable stablecoin;
    address public oracleNode;
    address public governance;

    enum MilestoneStatus { PENDING, STAGE1_RELEASED, COMPLETED, CANCELLED }

    struct GrantProject {
        uint256 totalAllocated;
        uint256 amountReleased;
        address residentAddress;
        address vendorAddress;
        MilestoneStatus status;
        bool isRegistered;
    }

    // Project mapping: Project ID => Grant Project details
    mapping(uint256 => GrantProject) public projects;
    
    // Whitelisted Local Hardware Vendors
    mapping(address => bool) public whitelistedVendors;

    // Events
    event GrantDeposited(address indexed donor, uint256 amount);
    event ProjectRegistered(uint256 indexed projectId, address indexed resident, address indexed vendor, uint256 allocation);
    event VendorWhitelistUpdated(address indexed vendor, bool status);
    event Milestone1Disbursed(uint256 indexed projectId, address indexed vendor, uint256 amount);
    event Milestone2Disbursed(uint256 indexed projectId, address indexed vendor, uint256 amount);
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
        require(whitelistedVendors[_vendor], "ERR_VENDOR_NOT_WHITELISTED: Target supplier is not approved.");
        _;
    }

    constructor(address _stablecoin, address _oracleNode) {
        require(_stablecoin != address(0), "Invalid stablecoin token");
        require(_oracleNode != address(0), "Invalid oracle address");
        stablecoin = IERC20(_stablecoin);
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
     * @notice Allows international/donor institutions to deposit grant funds.
     */
    function depositGrant(uint256 _amount) external {
        require(_amount > 0, "Deposit must exceed zero.");
        require(stablecoin.transferFrom(msg.sender, address(this), _amount), "Grant deposit transfer failed.");
        emit GrantDeposited(msg.sender, _amount);
    }

    /**
     * @notice Registers a housing upgrade project with an escrow allocation.
     */
    function registerProject(
        uint256 _projectId,
        address _resident,
        address _vendor,
        uint256 _totalCost
    ) external onlyGovernance onlyWhitelisted(_vendor) {
        require(!projects[_projectId].isRegistered, "Project already registered.");
        require(_resident != address(0), "Invalid resident address");
        require(_totalCost > 0, "Allocation cost must exceed zero.");
        require(stablecoin.balanceOf(address(this)) >= _totalCost, "Insufficient escrow contract reserves.");

        projects[_projectId] = GrantProject({
            totalAllocated: _totalCost,
            amountReleased: 0,
            residentAddress: _resident,
            vendorAddress: _vendor,
            status: MilestoneStatus.PENDING,
            isRegistered: true
        });

        emit ProjectRegistered(_projectId, _resident, _vendor, _totalCost);
    }

    /**
     * @notice Milestone 1: Releases initial materials ordering fund (e.g. 40% of allocation).
     * @dev Funds go directly to the whitelisted vendor, never to the resident.
     */
    function releaseMilestone1(uint256 _projectId) external onlyGovernance {
        GrantProject storage project = projects[_projectId];
        require(project.isRegistered, "Project is not registered.");
        require(project.status == MilestoneStatus.PENDING, "Milestone 1 already passed or cancelled.");
        require(whitelistedVendors[project.vendorAddress], "Vendor has been removed from whitelist.");

        uint256 stage1Amount = (project.totalAllocated * 40) / 100;
        project.amountReleased += stage1Amount;
        project.status = MilestoneStatus.STAGE1_RELEASED;

        require(stablecoin.transfer(project.vendorAddress, stage1Amount), "Stage 1 transfer failed.");
        emit Milestone1Disbursed(_projectId, project.vendorAddress, stage1Amount);
    }

    /**
     * @notice Milestone 2 (Final): Triggered by the validation oracle.
     * @dev Releases the remaining 60% balance to the vendor once VLM checks pass.
     */
    function releaseMilestone2(uint256 _projectId) external onlyOracle {
        GrantProject storage project = projects[_projectId];
        require(project.isRegistered, "Project is not registered.");
        require(project.status == MilestoneStatus.STAGE1_RELEASED, "Milestone 1 must be released first.");
        require(whitelistedVendors[project.vendorAddress], "Vendor is not whitelisted.");

        uint256 stage2Amount = project.totalAllocated - project.amountReleased;
        project.amountReleased += stage2Amount;
        project.status = MilestoneStatus.COMPLETED;

        require(stablecoin.transfer(project.vendorAddress, stage2Amount), "Stage 2 final transfer failed.");
        emit Milestone2Disbursed(_projectId, project.vendorAddress, stage2Amount);
    }

    /**
     * @notice Cancels a project and returns outstanding allocation reserves to general pool.
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
}
