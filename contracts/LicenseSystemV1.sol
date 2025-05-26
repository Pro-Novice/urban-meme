// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./LicenseStorage.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
/**
 * @title LicenseSystemV1
 * @dev Implementation contract with business logic
 */
contract LicenseSystemV1 is LicenseStorage, Initializable, UUPSUpgradeable, OwnableUpgradeable {
    
    // Events
    event LicenseCreated(uint256 indexed licenseId, address indexed applicant, LicenseCategory category);
    event LicenseUpdated(uint256 indexed licenseId, string field, address indexed updatedBy);
    event StatusChanged(uint256 indexed licenseId, LicenseStatus oldStatus, LicenseStatus newStatus, address indexed changedBy);
    event DocumentUploaded(uint256 indexed licenseId, string documentType, address indexed uploadedBy);
    event OfficerAdded(address indexed officer, string role);
    
    // Modifiers
    modifier onlyAdmin() {
        require(msg.sender == admin(), "Only admin");
        _;
    }
    
    modifier onlyOfficerOrAdmin() {
        require(isOfficer[msg.sender] || msg.sender == admin(), "Only officer or admin");
        _;
    }
    
    modifier licenseExists(uint256 _licenseId) {
        require(licenses[_licenseId].applicant != address(0), "License not found");
        _;
    }
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    function initialize() public initializer {
        __Ownable_init(msg.sender);
        __UUPSUpgradeable_init();
        _setAdmin(msg.sender);
        _incrementLicenseCounter(); // Start from 1
    }
    
    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}
    
    // Business Logic Functions
    
    function addOfficer(
        address _officer,
        string memory _name,
        string memory _employeeId,
        string memory _role
    ) public onlyAdmin {
        require(!isOfficer[_officer], "Already an officer");
        
        officers[_officer] = Officer({
            officerAddress: _officer,
            name: _name,
            employeeId: _employeeId,
            role: _role,
            department: "",
            level: AdminLevel.STATE,
            jurisdiction: "",
            isActive: true,
            addedDate: block.timestamp
        });
        
        isOfficer[_officer] = true;
        allOfficers.push(_officer);
        
        emit OfficerAdded(_officer, _role);
    }
    
    function createLicense(
        LicenseCategory _category,
        AdminLevel _level,
        string memory _applicantName,
        string memory _aadhaarNumber,
        string memory _businessName,
        string memory _state,
        string memory _district
    ) public virtual returns (uint256) {
        uint256 newLicenseId = licenseIdCounter();
        _incrementLicenseCounter();
        
        License storage newLicense = licenses[newLicenseId];
        newLicense.licenseId = newLicenseId;
        newLicense.category = _category;
        newLicense.level = _level;
        newLicense.status = LicenseStatus.DRAFT;
        newLicense.applicant = msg.sender;
        newLicense.applicantName = _applicantName;
        newLicense.aadhaarNumber = _aadhaarNumber;
        newLicense.businessName = _businessName;
        newLicense.state = _state;
        newLicense.district = _district;
        newLicense.applicationDate = block.timestamp;
        newLicense.lastModifiedDate = block.timestamp;
        newLicense.isActive = true;
        
        // Update tracking
        allLicenseIds.push(newLicenseId);
        applicantLicenses[msg.sender].push(newLicenseId);
        licensesByStatus[LicenseStatus.DRAFT].push(newLicenseId);
        licensesByCategory[_category].push(newLicenseId);
        licensesByLevel[_level].push(newLicenseId);
        licensesByDistrict[_district].push(newLicenseId);
        
        emit LicenseCreated(newLicenseId, msg.sender, _category);
        
        return newLicenseId;
    }
    
    function updateStatus(
        uint256 _licenseId,
        LicenseStatus _newStatus,
        string memory _remarks
    ) public onlyOfficerOrAdmin licenseExists(_licenseId) {
        License storage license = licenses[_licenseId];
        LicenseStatus oldStatus = license.status;
        
        // Remove from old status array
        _removeFromStatusArray(oldStatus, _licenseId);
        
        // Add to new status array
        licensesByStatus[_newStatus].push(_licenseId);
        
        // Update license
        license.status = _newStatus;
        license.lastModifiedDate = block.timestamp;
        
        // Record action
        _recordAction(_licenseId, ActionType.STATUS_UPDATED, _remarks);
        
        emit StatusChanged(_licenseId, oldStatus, _newStatus, msg.sender);
    }
    
    // Internal helper functions
    function _recordAction(
        uint256 _licenseId,
        ActionType _actionType,
        string memory _remarks
    ) internal {
        License storage license = licenses[_licenseId];
        
        license.actionHistory.push(Action({
            timestamp: block.timestamp,
            actionType: _actionType,
            actor: msg.sender,
            actorName: isOfficer[msg.sender] ? officers[msg.sender].name : license.applicantName,
            actorRole: isOfficer[msg.sender] ? officers[msg.sender].role : "Applicant",
            department: isOfficer[msg.sender] ? officers[msg.sender].department : "",
            remarks: _remarks,
            dataHash: keccak256(abi.encodePacked(_remarks, block.timestamp))
        }));
    }
    
    function _removeFromStatusArray(LicenseStatus _status, uint256 _licenseId) internal {
        uint256[] storage statusArray = licensesByStatus[_status];
        for (uint i = 0; i < statusArray.length; i++) {
            if (statusArray[i] == _licenseId) {
                statusArray[i] = statusArray[statusArray.length - 1];
                statusArray.pop();
                break;
            }
        }
    }
}