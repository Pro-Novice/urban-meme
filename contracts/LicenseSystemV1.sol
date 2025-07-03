// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./LicenseStorage.sol";
import "./OfficerManagement.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

contract LicenseSystemV1 is Initializable, OwnableUpgradeable, UUPSUpgradeable, LicenseStorage {
    event LicenseCreated(uint256 indexed licenseId, address indexed applicant, LicenseCategory category);
    event LicenseUpdated(uint256 indexed licenseId, string field, address indexed updatedBy);
    event StatusChanged(uint256 indexed licenseId, LicenseStatus oldStatus, LicenseStatus newStatus, address indexed changedBy);
    event DocumentUploaded(uint256 indexed licenseId, string documentType, address indexed uploadedBy);

    OfficerManagement public officerManagement;

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address _officerManagementAddr) public initializer {
        __Ownable_init(msg.sender);
        __UUPSUpgradeable_init();
        _setAdmin(msg.sender);
        _incrementLicenseCounter();
        officerManagement = OfficerManagement(_officerManagementAddr);
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}

    // Modifiers
    modifier onlyOfficerOrAdmin() {
        require(officerManagement.isOfficerAddress(msg.sender) || msg.sender == admin(), "Only officer or admin");
        _;
    }

    modifier licenseExists(uint256 _licenseId) {
        require(licenses[_licenseId].licenseId == _licenseId, "License does not exist");
        _;
    }

    function createLicense(
        LicenseCategory _category,
        AdminLevel _level,
        string memory _applicantName,
        string memory _aadhaarNumber,
        string memory _businessName,
        string memory _state,
        string memory _division,
        string memory _district
    ) public virtual returns (uint256) {
        require(bytes(_state).length > 0, "State is required");
        require(bytes(_division).length > 0, "Division is required");
        require(bytes(_district).length > 0, "District is required");

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
        newLicense.division = _division;
        newLicense.district = _district;
        newLicense.applicationDate = block.timestamp;
        newLicense.lastModifiedDate = block.timestamp;
        newLicense.isActive = true;

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

        if (isOfficer[msg.sender] && msg.sender != admin()) {
            Officer storage officer = officers[msg.sender];
            require(
                (officer.level == AdminLevel.STATE && keccak256(bytes(officer.jurisdiction)) == keccak256(bytes(license.state))) ||
                (officer.level == AdminLevel.DIVISION)||
                (officer.level == AdminLevel.DISTRICT && keccak256(bytes(officer.jurisdiction)) == keccak256(bytes(license.district))),
                "Officer jurisdiction doesn't match license"
            );
        }

        LicenseStatus oldStatus = license.status;
        _removeFromStatusArray(oldStatus, _licenseId);
        licensesByStatus[_newStatus].push(_licenseId);

        license.status = _newStatus;
        license.lastModifiedDate = block.timestamp;
       officerManagement.recordAction(_licenseId, ActionType.STATUS_UPDATED, _remarks);

        emit StatusChanged(_licenseId, oldStatus, _newStatus, msg.sender);
    }

    // View Functions
    function getLicenseBasicInfo(uint256 _licenseId) public view returns (
        uint256,
        string memory,
        LicenseCategory,
        AdminLevel,
        LicenseStatus,
        address,
        string memory,
        string memory,
        uint256,
        uint256,
        uint256,
        bool
    ) {
        License storage license = licenses[_licenseId];
        return (
            license.licenseId,
            license.applicantName,
            license.category,
            license.level,
            license.status,
            license.applicant,
            license.businessName,
            license.district,
            license.applicationDate,
            license.approvalDate,
            license.expiryDate,
            license.isActive
        );
    }

    function getLicenseActionHistory(uint256 _licenseId)
        public
        view
        licenseExists(_licenseId)
        returns (FormattedAction[] memory)
    {
        License storage license = licenses[_licenseId];
        FormattedAction[] memory actions = new FormattedAction[](license.actionHistory.length);

        for (uint i = 0; i < license.actionHistory.length; i++) {
            Action storage action = license.actionHistory[i];
            actions[i] = FormattedAction({
                timestamp: action.timestamp,
                actionType: uint8(action.actionType),
                actor: toHexString(action.actor),
                actorName: action.actorName,
                actorRole: action.actorRole,
                department: action.department,
                remarks: action.remarks,
                dataHash: toHexString(action.dataHash)
            });
        }
        return actions;
    }



    function validateLicenseJurisdiction(
        uint256 _licenseId,
        string memory _location
    ) public view returns (bool) {
        License storage license = licenses[_licenseId];
        if (license.level == AdminLevel.STATE) {
            return true;
        } else if (license.level == AdminLevel.DIVISION) {
            string[] storage districts = divisionDistricts[license.division];
            for (uint i = 0; i < districts.length; i++) {
                if (keccak256(bytes(districts[i])) == keccak256(bytes(_location))) {
                    return true;
                }
            }
        } else if (license.level == AdminLevel.DISTRICT) {
            return keccak256(bytes(license.district)) == keccak256(bytes(_location));
        }
        return false;
    }

    function listAllFunctions() public pure returns (string[] memory) {
        string[] memory functions = new string[](7);
        functions[0] = "getOfficerRole(address)";
        functions[1] = "getOfficerDetails(address)";
        functions[2] = "addOfficer(address,string,string,string,string,uint8,string)";
        functions[3] = "createLicense(uint8,uint8,string,string,string,string,string)";
        functions[4] = "updateStatus(uint256,uint8,string)";
        functions[5] = "getLicenseBasicInfo(uint256)";
        functions[6] = "getLicenseActionHistory(uint256)";
        return functions;
    }

    function toHexString(address account) internal pure returns (string memory) {
        return Strings.toHexString(uint256(uint160(account)), 20);
    }

    function toHexString(bytes32 value) internal pure returns (string memory) {
        bytes memory alphabet = "0123456789abcdef";
        bytes memory str = new bytes(64);

        for (uint i = 0; i < 32; i++) {
            str[i*2] = alphabet[uint8(value[i] >> 4)];
            str[i*2+1] = alphabet[uint8(value[i] & 0x0f)];
        }
        return string(str);
    }
      function _removeFromStatusArray(LicenseStatus _status, uint256 _licenseId) internal {
    uint256[] storage licensesArray = licensesByStatus[_status];
    for (uint i = 0; i < licensesArray.length; i++) {
        if (licensesArray[i] == _licenseId) {
            licensesArray[i] = licensesArray[licensesArray.length - 1]; // Move last to deleted
            licensesArray.pop(); // Remove last
            break;
        }
    }
}


    struct FormattedAction {
        uint256 timestamp;
        uint8 actionType;
        string actor;      // Address as hex string
        string actorName;
        string actorRole;
        string department;
        string remarks;
        string dataHash;   // bytes32 as hex string
    }
}