// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./LicenseStorage.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title LicenseSystemV1
 * @dev Implementation contract optimized for API integration
 */
contract LicenseSystemV1 is LicenseStorage, Initializable, UUPSUpgradeable, OwnableUpgradeable {
    // Events
    event LicenseApplicationSubmitted(uint256 indexed licenseId, string licenseNumber, LicenseCategory category);
    event LicenseApproved(uint256 indexed licenseId, string changedByOfficerName, userRole changedByOfficerRole, uint256 expiryDate);
    event LicenseRevoked(uint256 indexed licenseId, string changedByOfficerName, userRole changedByOfficerRole, string reason);
    event LicenseRenewed(uint256 indexed licenseId, string changedByOfficerName, userRole changedByOfficerRole, uint256 newExpiryDate);
    event StatusChanged(
        uint256 indexed licenseId,
        LicenseStatus oldStatus,
        LicenseStatus newStatus,
        string changedByOfficerName,
        userRole changedByOfficerRole
    );
    event ApiCallerAuthorized(address indexed caller);
    event ApiCallerRevoked(address indexed caller);

    // Modifiers
    modifier onlyAdmins() {
        require(msg.sender == owner() || admins[msg.sender], "Only authorized addresses can perform this action");
        _;
    }

    modifier licenseExists(uint256 _licenseId) {
        string memory errorMessage = string(abi.encodePacked("License not found: ", Strings.toString(_licenseId)));
        require(licenseIdExists(_licenseId), errorMessage);
        _;
    }

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize() public initializer {
        __Ownable_init(msg.sender);
        __UUPSUpgradeable_init();
        admins[msg.sender] = true; // also add to admin mapping
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}

    function addAdmin(address newAdmin) public {
        require(msg.sender == owner(), "Only owner can add admins");
        require(newAdmin != address(0), "Invalid address");
        admins[newAdmin] = true;
        emit ApiCallerAuthorized(newAdmin);
    }

    function removeAdmin(address adminToRemove) public {
        require(msg.sender == owner(), "Only owner can remove admins");
        require(adminToRemove != address(0), "Invalid address");
        require(adminToRemove != owner(), "Cannot remove owner");
        admins[adminToRemove] = false;
        emit ApiCallerRevoked(adminToRemove);
    }

    // 1. Submit License Application - To be used by citizens
    function submitLicenseApplication(
        LicenseCategory _category,
        LicenseLevel _level,
        string memory _applicantName,
        string memory _aadhaarNumber,
        string memory _businessName,
        string memory _businessAddress,
        string memory _district,
        string memory _division
    ) public virtual onlyAdmins returns (uint256) {
        _incrementLicenseCounter();
        uint256 newLicenseId = licenseIdCounter();

        License storage newLicense = licenses[newLicenseId];
        newLicense.licenseId = newLicenseId;
        newLicense.category = _category;
        newLicense.level = _level;
        newLicense.status = LicenseStatus.SUBMITTED;
        newLicense.applicantName = _applicantName;
        newLicense.aadhaarNumber = _hashAadhaar(_aadhaarNumber); // hashed
        newLicense.businessName = _businessName;
        newLicense.businessAddress = _businessAddress;
        newLicense.state = "RAJASTHAN";
        newLicense.district = _district;
        newLicense.division = _division;
        newLicense.applicationDate = block.timestamp;
        newLicense.lastModifiedDate = block.timestamp;
        newLicense.isActive = false;

        newLicense.actionHistory.push(
            Action({
                timestamp: block.timestamp,
                actionType: ActionType.SUBMITTED,
                actorName: _applicantName,
                actorRole: userRole.CITIZEN,
                remarks: "License Application Successfully Submitted",
                dataHash: _toHexString(keccak256(abi.encodePacked(_applicantName, _businessName, block.timestamp)))
            })
        );

        newLicense.licenseNumber = _generateLicenseNumber(_category, _level, newLicenseId);

        // Update tracking
        allLicenseIds.push(newLicenseId);
        applicantLicenses[msg.sender].push(newLicenseId);
        licensesByStatus[LicenseStatus.SUBMITTED].push(newLicenseId);
        licensesByCategory[_category].push(newLicenseId);
        licensesByLevel[_level].push(newLicenseId);
        licensesByDistrict[_district].push(newLicenseId);
        licenseNumberToId[newLicense.licenseNumber] = newLicenseId;

        emit LicenseApplicationSubmitted(newLicenseId, newLicense.licenseNumber, _category);

        return newLicenseId;
    }

    // 2. Get License Basic Info - to be performed by citizens/officers
    function getLicenseBasicInfo(uint256 _licenseId) public view licenseExists(_licenseId) returns (LicenseBasicInfo memory) {
        License storage license = licenses[_licenseId];

        return
            LicenseBasicInfo({
                licenseId: license.licenseId,
                licenseNumber: license.licenseNumber,
                applicantName: license.applicantName,
                category: license.category,
                level: license.level,
                status: license.status,
                businessName: license.businessName,
                businessAddress: license.businessAddress,
                district: license.district,
                state: license.state,
                division: license.division,
                applicationDate: license.applicationDate,
                approvalDate: license.approvalDate,
                rejectionDate: license.rejectionDate,
                expiryDate: license.expiryDate,
                revokedDate: license.revokedDate,
                renewalDate: license.renewalDate,
                isActive: license.isActive,
                isPaid: license.isPaid,
                documentsVerified: license.documentsVerified,
                inspectionPassed: license.inspectionPassed
            });
    }

    // 3. Get License Action History
    function getLicenseActionHistory(uint256 _licenseId) public view licenseExists(_licenseId) returns (Action[] memory) {
        return licenses[_licenseId].actionHistory;
    }

    // 4. Update Status for submitted License Applications - to be performed by officers
    function updateLicenseStatus(
        uint256 _licenseId,
        LicenseStatus _newStatus,
        string memory _officerName,
        userRole _role,
        string memory _remarks,
        uint256 _renewalPeriodDays // Optional parameter for renewals and approvals
    ) public onlyAdmins licenseExists(_licenseId) {
        License storage license = licenses[_licenseId];
        LicenseStatus oldStatus = license.status;

        require(oldStatus != _newStatus, "License status already set to requested status");

        // Update common fields
        license.status = _newStatus;
        license.lastModifiedDate = block.timestamp;

        // Handle specific status updates
        if (_newStatus == LicenseStatus.APPROVED) {
            // For approvals (new or renewals)
            require(_renewalPeriodDays > 0, "Renewal period must be greater than 0");
            license.approvalDate = block.timestamp;
            license.expiryDate = block.timestamp + (_renewalPeriodDays * 1 days);
            license.isActive = true;

            // If this was a renewal (from EXPIRED status)
            if (oldStatus == LicenseStatus.EXPIRED) {
                license.renewalDate = block.timestamp;
            }
        } else if (_newStatus == LicenseStatus.REVOKED) {
            // For revocations
            require(oldStatus == LicenseStatus.APPROVED, "Only approved licenses can be revoked");
            license.revokedDate = block.timestamp;
            license.isActive = false;
        } else if (_newStatus == LicenseStatus.EXPIRED) {
            // For expirations
            license.expiryDate = block.timestamp;
            license.isActive = false;
        } else if (_newStatus == LicenseStatus.REJECTED) {
            license.rejectionDate = block.timestamp;
            license.isActive = false;
        } else {
            // For other statuses (SUBMITTED, UNDER_REVIEW, etc.)
            license.isActive = false;
        }

        // Update tracking arrays
        _removeFromStatusArray(oldStatus, _licenseId);
        licensesByStatus[_newStatus].push(_licenseId);

        // Record action with appropriate action type
        ActionType actionType = _getActionTypeForStatus(_newStatus, oldStatus);
        string memory actionDescription = _buildActionDescription(oldStatus, _newStatus, _remarks);

        _recordAction(_licenseId, actionType, _role, actionDescription, _officerName);

        // Emit appropriate events
        _emitStatusEvent(_licenseId, oldStatus, _newStatus, _officerName, _role, _remarks);
    }

    // Internal functions
    function _hashAadhaar(string memory _aadhaarNumber) internal pure returns (string memory) {
        return _toHexString(keccak256(abi.encodePacked(_aadhaarNumber)));
    }

    function _toHexString(bytes32 data) internal pure returns (string memory) {
        bytes memory alphabet = "0123456789abcdef";
        bytes memory str = new bytes(64);
        for (uint256 i = 0; i < 32; i++) {
            str[i * 2] = alphabet[uint8(data[i] >> 4)];
            str[1 + i * 2] = alphabet[uint8(data[i] & 0x0f)];
        }
        return string(str);
    }

    function _recordAction(
        uint256 _licenseId,
        ActionType _actionType,
        userRole _userRole,
        string memory _remarks,
        string memory _officerName
    ) internal {
        License storage license = licenses[_licenseId];

        license.actionHistory.push(
            Action({
                timestamp: block.timestamp,
                actionType: _actionType,
                actorName: _officerName,
                actorRole: _userRole,
                remarks: _remarks,
                dataHash: _toHexString(keccak256(abi.encodePacked(_remarks, block.timestamp)))
            })
        );
    }

    function _generateLicenseNumber(LicenseCategory _category, LicenseLevel _level, uint256 _licenseId) internal pure returns (string memory) {
        string memory categoryCode = _category == LicenseCategory.SEED
            ? "SD"
            : _category == LicenseCategory.FERTILIZER
                ? "FT"
                : "IN";
        string memory levelCode = _level == LicenseLevel.STATE
            ? "ST"
            : _level == LicenseLevel.DIVISION
                ? "DV"
                : "DT";

        return string(abi.encodePacked("RJ", categoryCode, levelCode, Strings.toString(_licenseId)));
    }

    function _removeFromStatusArray(LicenseStatus _status, uint256 _licenseId) internal {
        uint256[] storage statusArray = licensesByStatus[_status];
        for (uint256 i = 0; i < statusArray.length; i++) {
            if (statusArray[i] == _licenseId) {
                statusArray[i] = statusArray[statusArray.length - 1];
                statusArray.pop();
                break;
            }
        }
    }

    function _getActionTypeForStatus(LicenseStatus _newStatus, LicenseStatus _oldStatus) private pure returns (ActionType) {
        if (_newStatus == LicenseStatus.APPROVED) {
            if (_oldStatus == LicenseStatus.EXPIRED) {
                return ActionType.RENEWED;
            } else {
                return ActionType.APPROVED;
            }
        }

        if (_newStatus == LicenseStatus.REJECTED) {
            return ActionType.REJECTED;
        }

        if (_newStatus == LicenseStatus.REVOKED) {
            return ActionType.REVOKED;
        }

        // For all other status changes (SUBMITTED → UNDER_REVIEW, etc.)
        return ActionType.STATUS_UPDATED;
    }

    function _buildActionDescription(
        LicenseStatus _oldStatus,
        LicenseStatus _newStatus,
        string memory _remarks
    ) private pure returns (string memory) {
        if (_newStatus == LicenseStatus.REVOKED) {
            return string(abi.encodePacked("License revoked: ", _remarks));
        } else if (_newStatus == LicenseStatus.APPROVED) {
            if (_oldStatus == LicenseStatus.EXPIRED) {
                return "License renewed";
            } else {
                return "License approved";
            }
        } else {
            return
                string(
                    abi.encodePacked(
                        "Status changed from ",
                        _licenseStatusToString(_oldStatus),
                        " to ",
                        _licenseStatusToString(_newStatus),
                        ": ",
                        _remarks
                    )
                );
        }
    }

    function _emitStatusEvent(
        uint256 _licenseId,
        LicenseStatus _oldStatus,
        LicenseStatus _newStatus,
        string memory _officerName,
        userRole _role,
        string memory _remarks
    ) private {
        if (_newStatus == LicenseStatus.APPROVED && _oldStatus == LicenseStatus.EXPIRED) {
            emit LicenseRenewed(_licenseId, _officerName, _role, licenses[_licenseId].expiryDate);
        } else if (_newStatus == LicenseStatus.REVOKED) {
            emit LicenseRevoked(_licenseId, _officerName, _role, _remarks);
        } else if (_newStatus == LicenseStatus.APPROVED) {
            emit LicenseApproved(_licenseId, _officerName, _role, licenses[_licenseId].expiryDate);
        } else {
            emit StatusChanged(_licenseId, _oldStatus, _newStatus, _officerName, _role);
        }
    }

    function _licenseStatusToString(LicenseStatus status) internal pure returns (string memory) {
        if (status == LicenseStatus.DRAFT) return "DRAFT";
        if (status == LicenseStatus.SUBMITTED) return "SUBMITTED";
        if (status == LicenseStatus.UNDER_REVIEW) return "UNDER_REVIEW";
        if (status == LicenseStatus.DOCUMENTS_VERIFIED) return "DOCUMENTS_VERIFIED";
        if (status == LicenseStatus.INSPECTION_SCHEDULED) return "INSPECTION_SCHEDULED";
        if (status == LicenseStatus.INSPECTION_COMPLETED) return "INSPECTION_COMPLETED";
        if (status == LicenseStatus.APPROVED) return "APPROVED";
        if (status == LicenseStatus.REJECTED) return "REJECTED";
        if (status == LicenseStatus.REVOKED) return "REVOKED";
        if (status == LicenseStatus.EXPIRED) return "EXPIRED";
        if (status == LicenseStatus.RENEWED) return "RENEWED";
        return "UNKNOWN";
    }

    function licenseIdExists(uint256 _licenseId) public view returns (bool) {
        return bytes(licenses[_licenseId].licenseNumber).length > 0;
    }
}
