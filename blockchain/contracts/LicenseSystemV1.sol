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
contract LicenseSystemV1 is
    LicenseStorage,
    Initializable,
    UUPSUpgradeable,
    OwnableUpgradeable
{
    // Events
    event LicenseApplicationSubmitted(
        string licenseNumber,
        LicenseCategory category,
        uint256 applicationDate,
        int256 latitude,
        int256 longitude
    );
    event LicenseApproved(
        string licenseNumber,
        string changedBy,
        userRole changedByRole,
        uint256 approvalDate,
        uint256 expiryDate
    );
    event LicenseRevoked(
        string licenseNumber,
        string changedBy,
        userRole changedByRole,
        string reason,
        uint256 revokedDate
    );
    event LicenseRejected(
        string licenseNumber,
        string changedBy,
        userRole changedByRole,
        string reason,
        uint256 rejectionDate
    );
    event LicenseRenewed(
        string licenseNumber,
        string changedBy,
        userRole changedByRole,
        uint256 renewalDate,
        uint256 expiryDate
    );
    event StatusChanged(
        string licenseNumber,
        LicenseStatus oldStatus,
        LicenseStatus newStatus,
        string changedBy,
        userRole changedByRole,
        uint256 lastModifiedDate
    );
    event LicenseVerificationStatus(
        string licenseNumber,
        string statusMessage,
        uint256 verifiedDate
    );
    event TamperAttemptDetected(
        string licenseNumber,
        string statusMessage,
        uint256 detectedDate
    );
    event ApiCallerAuthorized(address indexed caller);
    event ApiCallerRevoked(address indexed caller);

    // Modifiers
    modifier onlyAuthorizedCallers() {
        require(
            msg.sender == owner() || authorizedApiCallers[msg.sender],
            "Only authorized addresses can perform this action"
        );
        _;
    }

    modifier licenseExists(string memory _licenseNumber) {
        string memory errorMessage = string(
            abi.encodePacked("License not found: ", _licenseNumber)
        );
        require(_licenseIdExists(_licenseNumber), errorMessage);
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

    function _authorizeUpgrade(
        address newImplementation
    ) internal override onlyOwner {}

    function manageAuthorizedApiCallers(
        address admin,
        bool add
    ) public onlyOwner {
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
    function submitLicenseApplication(
        LicenseApplicationInput memory input
    ) public virtual onlyAuthorizedCallers {
        License storage newLicense = licenses[input.licenseNumber];
        newLicense.licenseNumber = input.licenseNumber;
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
        newLicense.cropName = input.cropName;
        newLicense.cropVariety = input.cropVariety;
        newLicense.applicationDate = block.timestamp;
        newLicense.lastModifiedDate = block.timestamp;
        newLicense.isActive = false;

        if (
            input.category == LicenseCategory.FERTILIZER ||
            input.category == LicenseCategory.PESTICIDE
        ) {
            require(
                input.latitude != 0 && input.longitude != 0,
                "Geo required"
            );
            newLicense.latitude = input.latitude;
            newLicense.longitude = input.longitude;
        } else {
            require(
                input.latitude == 0 && input.longitude == 0,
                "Geo not allowed"
            );
            newLicense.latitude = 0;
            newLicense.longitude = 0;
        }
        newLicense.actionHistory.push(
            Action({
                timestamp: block.timestamp,
                actionType: LicenseStatus.SUBMITTED,
                actorName: input.applicantName,
                actorRole: userRole.CITIZEN,
                remarks: "License Application Successfully Submitted",
                dataHash: _toHexString(
                    keccak256(
                        abi.encodePacked(
                            input.applicantName,
                            input.firmName,
                            block.timestamp
                        )
                    )
                )
            })
        );

        // Update tracking
        allLicenseNumbers.push(input.licenseNumber);
        licensesByStatus[LicenseStatus.SUBMITTED].push(input.licenseNumber);
        licensesByCategory[input.category].push(input.licenseNumber);
        licensesByLevel[input.level].push(input.licenseNumber);

        emit LicenseApplicationSubmitted(
            newLicense.licenseNumber,
            input.category,
            newLicense.applicationDate,
            newLicense.latitude,
            newLicense.longitude
        );
    }

    // 2. Get License Basic Info - to be performed by citizens/officers
    function getLicenseBasicInfo(
        string memory _licenseNumber
    )
        public
        view
        licenseExists(_licenseNumber)
        returns (LicenseBasicInfo memory)
    {
        License storage license = licenses[_licenseNumber];
        int256 lat = 0;
        int256 lng = 0;

        if (
            license.category == LicenseCategory.FERTILIZER ||
            license.category == LicenseCategory.PESTICIDE
        ) {
            lat = license.latitude;
            lng = license.longitude;
        }
        return
            LicenseBasicInfo({
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
                cropName: license.cropName,
                cropVariety: license.cropVariety,
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
                inspectionPassed: license.inspectionPassed
            });
    }

    // 3. Get License Action History
    function getLicenseActionHistory(
        string memory _licenseNumber
    ) public view licenseExists(_licenseNumber) returns (Action[] memory) {
        return licenses[_licenseNumber].actionHistory;
    }

    // 4. Update Status for submitted License Applications - to be performed by officers
    function updateLicenseStatus(
        string memory _licenseNumber,
        LicenseStatus _newStatus,
        string memory _officerName,
        userRole _role,
        string memory _remarks,
        uint256 _renewalPeriodDays // Optional parameter for renewals and approvals
    ) public onlyAuthorizedCallers licenseExists(_licenseNumber) {
        License storage license = licenses[_licenseNumber];
        LicenseStatus oldStatus = license.status;

        require(
            oldStatus != _newStatus,
            "License status already set to requested status"
        );

        // Update common fields
        license.status = _newStatus;
        license.lastModifiedDate = block.timestamp;

        // Handle specific status updates
        if (
            _newStatus == LicenseStatus.APPROVED ||
            _newStatus == LicenseStatus.RENEWED
        ) {
            // For approvals (new or renewals)
            require(
                _renewalPeriodDays > 0,
                "Renewal period must be greater than 0"
            );
            license.approvalDate = block.timestamp;
            license.expiryDate =
                block.timestamp +
                (_renewalPeriodDays * 1 days);
            license.isActive = true;

            // If this was a renewal (from EXPIRED status)
            if (oldStatus == LicenseStatus.EXPIRED) {
                license.renewalDate = block.timestamp;
            }
        } else if (_newStatus == LicenseStatus.REVOKED) {
            // For revocations
            require(
                oldStatus == LicenseStatus.APPROVED,
                "Only approved licenses can be revoked"
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
        _removeFromStatusArray(oldStatus, _licenseNumber);
        licensesByStatus[_newStatus].push(_licenseNumber);

        // Record action with appropriate action type
        LicenseStatus actionType = _getActionTypeForStatus(
            _newStatus,
            oldStatus
        );
        string memory actionDescription = _buildActionDescription(
            oldStatus,
            _newStatus,
            _remarks
        );

        _recordAction(
            _licenseNumber,
            actionType,
            _role,
            actionDescription,
            _officerName
        );

        // Emit appropriate events
        _emitStatusEvent(
            _licenseNumber,
            oldStatus,
            _newStatus,
            _officerName,
            _role,
            _remarks
        );
    }

    // 5. Get QR Code data for License
    function getLicenseQRData(
        string memory _licenseNumber
    )
        public
        view
        licenseExists(_licenseNumber)
        returns (string memory verificationHash, string memory licenseNumber)
    {
        License storage license = licenses[_licenseNumber];
        require(license.isActive, "License must be active to generate QR data");

        verificationHash = _generateVerificationHash(license);
        licenseNumber = license.licenseNumber;
    }

    // 6. Verify License Integrity and Validity
    function verifyLicenseWithHash(
        string memory _licenseNumber,
        string memory _expectedHash
    ) public {
        LicenseVerificationData memory data = _verifyLicenseByNumber(
            _licenseNumber
        );

        require(data.isValid, data.statusMessage);

        require(
            _compareStrings(data.verificationHash, _expectedHash),
            "WARNING: Potential tampering detected!"
        );

        emit LicenseVerificationStatus(
            _licenseNumber,
            data.statusMessage,
            block.timestamp
        );
    }

    // 7. Verify License by Number - Private function to be used internally
    function _verifyLicenseByNumber(
        string memory _licenseNumber
    ) private view returns (LicenseVerificationData memory) {
        if (!_licenseIdExists(_licenseNumber)) {
            return
                LicenseVerificationData({
                    isValid: false,
                    isActive: false,
                    isExpired: false,
                    isRevoked: false,
                    licenseNumber: _licenseNumber,
                    approvalDate: 0,
                    expiryDate: 0,
                    revokedDate: 0,
                    verificationHash: "",
                    statusMessage: "License not found or invalid license number"
                });
        }

        License storage license = licenses[_licenseNumber];

        string memory verificationHash = _generateVerificationHash(license);
        bool isExpired = (license.expiryDate > 0 &&
            block.timestamp > license.expiryDate);
        bool isRevoked = (license.status == LicenseStatus.REVOKED);
        bool isValid = (license.status == LicenseStatus.APPROVED &&
            !isExpired &&
            !isRevoked);
        bool isActive = license.isActive && isValid;
        string memory statusMessage = _generateStatusMessage(
            license.status,
            isExpired,
            isRevoked
        );

        return
            LicenseVerificationData({
                isValid: isValid,
                isActive: isActive,
                isExpired: isExpired,
                isRevoked: isRevoked,
                licenseNumber: license.licenseNumber,
                approvalDate: license.approvalDate,
                expiryDate: license.expiryDate,
                revokedDate: license.revokedDate,
                verificationHash: verificationHash,
                statusMessage: statusMessage
            });
    }

    // Helper functions
    function _licenseIdExists(
        string memory _licenseNumber
    ) internal view returns (bool) {
        return bytes(licenses[_licenseNumber].licenseNumber).length > 0;
    }

    function _compareStrings(
        string memory a,
        string memory b
    ) internal pure returns (bool) {
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
        string memory _licenseNumber,
        LicenseStatus _actionType,
        userRole _userRole,
        string memory _remarks,
        string memory _officerName
    ) internal {
        License storage license = licenses[_licenseNumber];

        license.actionHistory.push(
            Action({
                timestamp: block.timestamp,
                actionType: _actionType,
                actorName: _officerName,
                actorRole: _userRole,
                remarks: _remarks,
                dataHash: _toHexString(
                    keccak256(abi.encodePacked(_remarks, block.timestamp))
                )
            })
        );
    }

    function _removeFromStatusArray(
        LicenseStatus _status,
        string memory _licenseNumber
    ) internal {
        string[] storage statusArray = licensesByStatus[_status];
        for (uint256 i = 0; i < statusArray.length; i++) {
            if (
                keccak256(bytes(statusArray[i])) ==
                keccak256(bytes(_licenseNumber))
            ) {
                statusArray[i] = statusArray[statusArray.length - 1];
                statusArray.pop();
                break;
            }
        }
    }

    function _getActionTypeForStatus(
        LicenseStatus _newStatus,
        LicenseStatus _oldStatus
    ) private pure returns (LicenseStatus) {
        if (
            _newStatus == LicenseStatus.APPROVED ||
            _newStatus == LicenseStatus.RENEWED
        ) {
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
        string memory _licenseNumber,
        LicenseStatus _oldStatus,
        LicenseStatus _newStatus,
        string memory _officerName,
        userRole _role,
        string memory _remarks
    ) private {
        if (
            _newStatus == LicenseStatus.RENEWED &&
            _oldStatus == LicenseStatus.EXPIRED
        ) {
            emit LicenseRenewed(
                _licenseNumber,
                _officerName,
                _role,
                licenses[_licenseNumber].renewalDate,
                licenses[_licenseNumber].expiryDate
            );
        } else if (_newStatus == LicenseStatus.REVOKED) {
            emit LicenseRevoked(
                _licenseNumber,
                _officerName,
                _role,
                _remarks,
                licenses[_licenseNumber].revokedDate
            );
        } else if (_newStatus == LicenseStatus.APPROVED) {
            emit LicenseApproved(
                _licenseNumber,
                _officerName,
                _role,
                licenses[_licenseNumber].approvalDate,
                licenses[_licenseNumber].expiryDate
            );
        } else if (_newStatus == LicenseStatus.REJECTED) {
            emit LicenseRejected(
                _licenseNumber,
                _officerName,
                _role,
                _remarks,
                licenses[_licenseNumber].rejectionDate
            );
        } else {
            emit StatusChanged(
                _licenseNumber,
                _oldStatus,
                _newStatus,
                _officerName,
                _role,
                block.timestamp
            );
        }
    }

    function _licenseStatusToString(
        LicenseStatus status
    ) internal pure returns (string memory) {
        if (status == LicenseStatus.SUBMITTED) return "SUBMITTED";
        if (status == LicenseStatus.UNDER_REVIEW) return "UNDER_REVIEW";
        if (status == LicenseStatus.DOCUMENTS_VERIFIED)
            return "DOCUMENTS_VERIFIED";
        if (status == LicenseStatus.INSPECTION_SCHEDULED)
            return "INSPECTION_SCHEDULED";
        if (status == LicenseStatus.INSPECTION_COMPLETED)
            return "INSPECTION_COMPLETED";
        if (status == LicenseStatus.APPROVED) return "APPROVED";
        if (status == LicenseStatus.REJECTED) return "REJECTED";
        if (status == LicenseStatus.REVOKED) return "REVOKED";
        if (status == LicenseStatus.EXPIRED) return "EXPIRED";
        if (status == LicenseStatus.RENEWED) return "RENEWED";
        return "UNKNOWN";
    }

    function _generateVerificationHash(
        License storage license
    ) internal view returns (string memory) {
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

    function _generateStatusMessage(
        LicenseStatus status,
        bool isExpired,
        bool isRevoked
    ) internal pure returns (string memory) {
        if (isRevoked) {
            return "License has been revoked and is no longer valid";
        }

        if (isExpired) {
            return "License has expired and needs renewal";
        }

        if (status == LicenseStatus.APPROVED) {
            return "License is valid and active";
        } else if (status == LicenseStatus.UNDER_REVIEW) {
            return "License application is under review";
        } else if (status == LicenseStatus.REJECTED) {
            return "License application has been rejected";
        }

        return "License application is not active";
    }
}
