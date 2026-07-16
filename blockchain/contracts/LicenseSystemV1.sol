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
    error RenewalRequiresExpiredStatus();

    // Events
    event LicenseApplicationSubmitted(uint256 indexed licenseId, string licenseNumber, LicenseCategory category, uint256 applicationDate, int256 latitude, int256 longitude);
    event LicenseApproved(uint256 indexed licenseId, string changedBy, userRole changedByRole, uint256 approvalDate, uint256 expiryDate);
    event LicenseRevoked(uint256 indexed licenseId, string changedBy, userRole changedByRole, string reason, uint256 revokedDate);
    event LicenseRejected(uint256 indexed licenseId, string changedBy, userRole changedByRole, string reason, uint256 rejectionDate);
    event LicenseRenewed(uint256 indexed licenseId, string changedBy, userRole changedByRole, uint256 renewalDate, uint256 expiryDate);
    event StatusChanged(
        uint256 indexed licenseId,
        LicenseStatus oldStatus,
        LicenseStatus newStatus,
        string changedBy,
        userRole changedByRole,
        uint256 lastModifiedDate
    );
    event LicenseVerificationStatus(uint256 indexed licenseId, string licenseNumber, string statusMessage, uint256 verifiedDate);
    event TamperAttemptDetected(uint256 indexed licenseId, string licenseNumber, string statusMessage, uint256 detectedDate);
    event ApiCallerAuthorized(address indexed caller);
    event ApiCallerRevoked(address indexed caller);

    // Modifiers
    modifier onlyAuthorizedCallers() {
        require(msg.sender == owner() || authorizedApiCallers[msg.sender], "Only authorized addresses can perform this action");
        _;
    }

    modifier licenseExists(uint256 _licenseId) {
        string memory errorMessage = string(abi.encodePacked("License not found: ", Strings.toString(_licenseId)));
        require(_licenseIdExists(_licenseId), errorMessage);
        _;
    }

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize() public initializer {
        __Ownable_init(msg.sender);
        __UUPSUpgradeable_init();
        authorizedApiCallers[msg.sender] = true; // Add to admin mapping
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}

    function manageAuthorizedApiCallers(address admin, bool add) public onlyOwner {
        require(admin != address(0), "Invalid address");
        if (add) {
            authorizedApiCallers[admin] = true;
            emit ApiCallerAuthorized(admin);
        } else {
            require(admin != owner(), "Cannot remove owner");
            authorizedApiCallers[admin] = false;
            emit ApiCallerRevoked(admin);
        }   
    }

    // 1. Submit License Application - To be used by citizens
    function submitLicenseApplication(LicenseApplicationInput memory input) public virtual onlyAuthorizedCallers {
        _incrementLicenseCounter();
        uint256 newLicenseId = licenseIdCounter();

        License storage newLicense = licenses[newLicenseId];
        newLicense.licenseId = newLicenseId;
        newLicense.category = input.category;
        newLicense.level = input.level;
        newLicense.status = LicenseStatus.SUBMITTED;
        newLicense.registeringAuthority = input.registeringAuthority;
        newLicense.registeringOfficeName = input.registeringOfficeName;
        newLicense.applicantName = input.applicantName;
        newLicense.aadhaarNumber = input.aadhaarNumber; // Aadhar is already encrypted 
        newLicense.applicantPermanentAddress = input.applicantPermanentAddress;
        newLicense.firmName = input.firmName;
        newLicense.firmType = input.firmType;
        newLicense.firmAddress = input.firmAddress;
        newLicense.salePointAddress = input.salePointAddress;
        newLicense.saleStorageAddress = input.saleStorageAddress;
        newLicense.productionCompany = input.productionCompany;
        _setCropName(newLicense, input.cropName);
        _setCropVariety(newLicense, input.cropVariety);
        newLicense.applicationDate = block.timestamp;
        newLicense.lastModifiedDate = block.timestamp;
        newLicense.isActive = false;
       
       if (
            input.category == LicenseCategory.FERTILIZER ||
            input.category == LicenseCategory.PESTICIDE
        ) {
            require(input.latitude != 0 && input.longitude != 0, "Geo required");
            newLicense.latitude = input.latitude;
            newLicense.longitude = input.longitude;
        } else {
            require(input.latitude == 0 && input.longitude == 0, "Geo not allowed");
            newLicense.latitude = 0;
            newLicense.longitude = 0;
        }
        newLicense.actionHistory.push(
            Action({
                timestamp: block.timestamp,
                actionType: ActionType.SUBMITTED,
                actorName: input.applicantName,
                actorRole: userRole.CITIZEN,
                remarks: "License Application Successfully Submitted",
                dataHash: _toHexString(keccak256(abi.encodePacked(input.applicantName, input.firmName, block.timestamp)))
            })
        );

        newLicense.licenseNumber = _generateLicenseNumber(input.category, input.level, newLicenseId);

        // Update tracking
        allLicenseIds.push(newLicenseId);
        licensesByStatus[LicenseStatus.SUBMITTED].push(newLicenseId);
        licensesByCategory[input.category].push(newLicenseId);
        licensesByLevel[input.level].push(newLicenseId);
        licenseNumberToId[newLicense.licenseNumber] = newLicenseId;

        emit LicenseApplicationSubmitted(newLicenseId, newLicense.licenseNumber, input.category, newLicense.applicationDate, newLicense.latitude, newLicense.longitude);
    }

    // 2. Get License Basic Info - to be performed by citizens/officers
    function getLicenseBasicInfo(uint256 _licenseId) public view licenseExists(_licenseId) returns (LicenseBasicInfo memory) {
        License storage license = licenses[_licenseId];
        int256 lat = 0;
        int256 lng = 0;

        if (
            license.category == LicenseCategory.FERTILIZER ||
            license.category == LicenseCategory.PESTICIDE
        ) {
            lat = license.latitude;
            lng = license.longitude;
        }
        string[] memory cropName = _copyCropName(license);
        string[] memory cropVariety = _copyCropVariety(license);
        return
            LicenseBasicInfo({
                licenseId: license.licenseId,
                licenseNumber: license.licenseNumber,
                applicantName: license.applicantName,
                category: license.category,
                level: license.level,
                status: license.status,
                firmName: license.firmName,
                firmType: license.firmType,
                firmAddress: license.firmAddress,
                salePointAddress: license.salePointAddress,
                saleStorageAddress: license.saleStorageAddress,
                productionCompany: license.productionCompany,
                cropName: cropName,
                cropVariety: cropVariety,
                registeringOfficeName: license.registeringOfficeName,
                registeringAuthority: license.registeringAuthority,
                applicationDate: license.applicationDate,
                approvalDate: license.approvalDate,
                rejectionDate: license.rejectionDate,
                expiryDate: license.expiryDate,
                revokedDate: license.revokedDate,
                renewalDate: license.renewalDate,
                latitude: lat,
                longitude: lng,
                isActive: license.isActive,
                isPaid: license.isPaid,
                documentsVerified: license.documentsVerified,
                inspectionPassed: license.inspectionPassed,
                applicationLicenseType: license.applicationLicenseType
            });
    }

    function _setCropName(License storage license, string[] memory cropName) internal {
        delete license.cropNames;
        for (uint256 i = 0; i < cropName.length; i++) {
            license.cropNames.push(cropName[i]);
        }
        license.cropName = cropName.length > 0 ? cropName[0] : "";
    }

    function _copyCropName(License storage license) internal view returns (string[] memory) {
        if (license.cropNames.length > 0) {
            string[] memory copiedCropName = new string[](license.cropNames.length);
            for (uint256 i = 0; i < license.cropNames.length; i++) {
                copiedCropName[i] = license.cropNames[i];
            }
            return copiedCropName;
        }

        if (bytes(license.cropName).length > 0) {
            string[] memory legacyCropName = new string[](1);
            legacyCropName[0] = license.cropName;
            return legacyCropName;
        }

        return new string[](0);
    }
    function _setCropVariety(License storage license, string[] memory cropVariety) internal {
        delete license.cropVarieties;
        for (uint256 i = 0; i < cropVariety.length; i++) {
            license.cropVarieties.push(cropVariety[i]);
        }
        license.cropVariety = cropVariety.length > 0 ? cropVariety[0] : "";
    }
    function _copyCropVariety(License storage license) internal view returns (string[] memory) {
        if (license.cropVarieties.length > 0) {
            string[] memory copiedCropVariety = new string[](license.cropVarieties.length);
            for (uint256 i = 0; i < license.cropVarieties.length; i++) {
                copiedCropVariety[i] = license.cropVarieties[i];
            }
            return copiedCropVariety;
        }

        if (bytes(license.cropVariety).length > 0) {
            string[] memory legacyCropVariety = new string[](1);
            legacyCropVariety[0] = license.cropVariety;
            return legacyCropVariety;
        }

        return new string[](0);
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
    ) public onlyAuthorizedCallers licenseExists(_licenseId) {
        License storage license = licenses[_licenseId];
        LicenseStatus oldStatus = license.status;

        require(oldStatus != _newStatus, "License status already set to requested status");

        // Update common fields
        license.status = _newStatus;
        license.lastModifiedDate = block.timestamp;

        // Handle specific status updates
        if (_newStatus == LicenseStatus.APPROVED || _newStatus == LicenseStatus.RENEWED) {
            if (_newStatus == LicenseStatus.RENEWED && oldStatus != LicenseStatus.EXPIRED) {
                revert RenewalRequiresExpiredStatus();
            }
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
            require(
                oldStatus == LicenseStatus.APPROVED || oldStatus == LicenseStatus.RENEWED,
                "Only approved or renewed licenses can be revoked"
            );
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
        LicenseStatus actionType = _getActionTypeForStatus(_newStatus, oldStatus);
        string memory actionDescription = _buildActionDescription(oldStatus, _newStatus, _remarks);

        _recordAction(_licenseId, actionType, _role, actionDescription, _officerName);

        // Emit appropriate events
        _emitStatusEvent(_licenseId, oldStatus, _newStatus, _officerName, _role, _remarks);
    }

    // 5. Get QR Code data for License
    function getLicenseQRData(
        uint256 _licenseId
    ) public view licenseExists(_licenseId) returns (string memory verificationHash, string memory licenseNumber) {
        License storage license = licenses[_licenseId];
        require(license.isActive, "License must be active to generate QR data");

        verificationHash = _generateVerificationHash(license);
        licenseNumber = license.licenseNumber;
    }

    // 6. Verify License Integrity and Validity
    function verifyLicenseWithHash(string memory _licenseNumber, string memory _expectedHash) public {
        LicenseVerificationData memory data = verifyLicenseByNumber(_licenseNumber);

        require(data.isValid, data.statusMessage);

        require(
            _compareStrings(data.verificationHash, _expectedHash),
            "WARNING: Potential tampering detected!"
        );

        emit LicenseVerificationStatus(data.licenseId, _licenseNumber, data.statusMessage, block.timestamp);
    }

    // 7. Verify License by Number - Private function to be used internally
    function verifyLicenseByNumber(string memory _licenseNumber) private view returns (LicenseVerificationData memory) {
        uint256 licenseId = licenseNumberToId[_licenseNumber];

        if (!_licenseIdExists(licenseId)) {
            return
                LicenseVerificationData({
                    isValid: false,
                    isActive: false,
                    isExpired: false,
                    isRevoked: false,
                    licenseNumber: _licenseNumber,
                    licenseId: 0,
                    approvalDate: 0,
                    expiryDate: 0,
                    revokedDate: 0,
                    verificationHash: "",
                    statusMessage: "License not found or invalid license number"
                });
        }

        License storage license = licenses[licenseId];

        // Generate verification hash for tamper detection
        string memory verificationHash = _generateVerificationHash(license);

        // Check expiry
        bool isExpired = (license.expiryDate > 0 && block.timestamp > license.expiryDate);

        // Check if revoked
        bool isRevoked = (license.status == LicenseStatus.REVOKED);

        // Determine if license is valid and active
        bool hasValidStatus = (
            license.status == LicenseStatus.APPROVED ||
            license.status == LicenseStatus.RENEWED
        );
        bool isValid = (hasValidStatus && !isExpired && !isRevoked);
        bool isActive = license.isActive && isValid;

        // Generate status message
        string memory statusMessage = _generateStatusMessage(license.status, isExpired, isRevoked);

        return
            LicenseVerificationData({
                isValid: isValid,
                isActive: isActive,
                isExpired: isExpired,
                isRevoked: isRevoked,
                licenseNumber: license.licenseNumber,
                licenseId: license.licenseId,
                approvalDate: license.approvalDate,
                expiryDate: license.expiryDate,
                revokedDate: license.revokedDate,
                verificationHash: verificationHash,
                statusMessage: statusMessage
            });
    }

    // Helper functions
    function _licenseIdExists(uint256 _licenseId) internal view returns (bool) {
        return bytes(licenses[_licenseId].licenseNumber).length > 0;
    }

    function _compareStrings(string memory a, string memory b) internal pure returns (bool) {
        return keccak256(abi.encodePacked(a)) == keccak256(abi.encodePacked(b));
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
        LicenseStatus _actionType,
        userRole _userRole,
        string memory _remarks,
        string memory _officerName
    ) internal {
        License storage license = licenses[_licenseId];

        license.actionHistory.push(
            Action({
                timestamp: block.timestamp,
                actionType: ActionType(uint8(_actionType)),
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
                : "PS";
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

    function _getActionTypeForStatus(LicenseStatus _newStatus, LicenseStatus _oldStatus) private pure returns (LicenseStatus) {
        if (_newStatus == LicenseStatus.APPROVED || _newStatus == LicenseStatus.RENEWED) {
            if (_oldStatus == LicenseStatus.EXPIRED) {
                return LicenseStatus.RENEWED;
            } else {
                return LicenseStatus.APPROVED;
            }
        } else if (_newStatus == LicenseStatus.REJECTED) {
            return LicenseStatus.REJECTED;
        } else if (_newStatus == LicenseStatus.REVOKED) {
            return LicenseStatus.REVOKED;
        } else if (_newStatus == LicenseStatus.EXPIRED) {
            return LicenseStatus.EXPIRED;
        } else if (_newStatus == LicenseStatus.UNDER_REVIEW) {
            return LicenseStatus.UNDER_REVIEW;
        } else if (_newStatus == LicenseStatus.DOCUMENTS_VERIFIED) {
            return LicenseStatus.DOCUMENTS_VERIFIED;
        } else if (_newStatus == LicenseStatus.INSPECTION_SCHEDULED) {
            return LicenseStatus.INSPECTION_SCHEDULED;
        } else if (_newStatus == LicenseStatus.INSPECTION_COMPLETED) {
            return LicenseStatus.INSPECTION_COMPLETED;
        }
        return LicenseStatus.INSPECTION_COMPLETED;
    }

    function _buildActionDescription(
        LicenseStatus _oldStatus,
        LicenseStatus _newStatus,
        string memory _remarks
    ) private pure returns (string memory) {
        string memory baseMessage;

        if (_newStatus == LicenseStatus.REVOKED) {
            baseMessage = "License revoked";
        } else if (_newStatus == LicenseStatus.APPROVED) {
            if (_oldStatus == LicenseStatus.EXPIRED) {
                baseMessage = "License renewed";
            } else {
                baseMessage = "License approved";
            }
        } else {
            baseMessage = string(
                abi.encodePacked(
                    "Status changed from ",
                    _licenseStatusToString(_oldStatus),
                    " to ",
                    _licenseStatusToString(_newStatus)
                )
            );
        }

        // Append officer remarks ONLY if provided
        if (bytes(_remarks).length > 0) {
            return string(abi.encodePacked(baseMessage, ": ", _remarks));
        }

        return baseMessage;
    }


    function _emitStatusEvent(
        uint256 _licenseId,
        LicenseStatus _oldStatus,
        LicenseStatus _newStatus,
        string memory _officerName,
        userRole _role,
        string memory _remarks
    ) private {
        if (_newStatus == LicenseStatus.RENEWED && _oldStatus == LicenseStatus.EXPIRED) {
            emit LicenseRenewed(_licenseId, _officerName, _role, licenses[_licenseId].renewalDate, licenses[_licenseId].expiryDate);
        } else if (_newStatus == LicenseStatus.REVOKED) {
            emit LicenseRevoked(_licenseId, _officerName, _role, _remarks, licenses[_licenseId].revokedDate);
        } else if (_newStatus == LicenseStatus.APPROVED) {
            emit LicenseApproved(_licenseId, _officerName, _role, licenses[_licenseId].approvalDate, licenses[_licenseId].expiryDate);
        } else if (_newStatus == LicenseStatus.REJECTED) {
            emit LicenseRejected(_licenseId, _officerName, _role, _remarks, licenses[_licenseId].rejectionDate);
        } else {
            emit StatusChanged(_licenseId, _oldStatus, _newStatus, _officerName, _role, block.timestamp);
        }
    }

    function _licenseStatusToString(LicenseStatus status) internal pure returns (string memory) {
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

    function _generateVerificationHash(License storage license) internal view returns (string memory) {
        return
            _toHexString(
                keccak256(
                    abi.encodePacked(
                        license.applicantName,
                        license.firmName,
                        license.firmAddress,
                        license.salePointAddress,
                        license.saleStorageAddress
                    )
                )
            );
    }

    function _generateStatusMessage(LicenseStatus status, bool isExpired, bool isRevoked) internal pure returns (string memory) {
        if (isRevoked) {
            return "License has been revoked and is no longer valid";
        }

        if (isExpired) {
            return "License has expired and needs renewal";
        }

        if (status == LicenseStatus.APPROVED || status == LicenseStatus.RENEWED) {
            return "License is valid and active";
        } else if (status == LicenseStatus.UNDER_REVIEW) {
            return "License application is under review";
        } else if (status == LicenseStatus.REJECTED) {
            return "License application has been rejected";
        } 

        return "License application is not active";
    }
}
