// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title LicenseStorage
 * @dev Separates storage from logic for upgradeability
 */
contract LicenseStorage {
    // Enums
    enum LicenseCategory {
        SEED,
        FERTILIZER,
        PESTICIDE
    }
    enum LicenseLevel {
        STATE,
        DIVISION,
        DISTRICT
    }
    enum LicenseStatus {
        SUBMITTED,
        UNDER_REVIEW,
        DOCUMENTS_VERIFIED,
        INSPECTION_SCHEDULED,
        INSPECTION_COMPLETED,
        APPROVED,
        REJECTED,
        REVOKED,
        EXPIRED,
        RENEWED
    }
    enum userRole {
        CITIZEN,
        AGRICULTURE_OFFICER,
        ASSISTANT_AGRICULTURE_OFFICER,
        ASSISTANT_DIRECTOR,
        DEPUTY_DIRECTOR,
        JOINT_DIRECTOR,
        JOINT_DIRECTOR_INPUT,
        FIELD_INSPECTOR
    }

    // Core License Structure
    struct License {
        // Unique identifier
        string licenseNumber;
        LicenseCategory category;
        LicenseStatus status;
        LicenseLevel level;
        // Registering authority details---
        string registeringAuthority;
        string registeringOfficeName;
        // Applicant details
        string applicantName;
        string aadhaarNumber;
        string applicantPermanentAddress;
        // Firm details
        string firmName;
        string firmType; // Private Ltd, Public Ltd, Partnership Firm, Proprietor Firm, etc.
        string firmAddress;
        string salePointAddress;
        string saleStorageAddress;
        // Crop details
        bool isSeedSelfProduced;
        string productionCompany;
        string cropName;
        string cropVariety;
        mapping(string => string) customFields;
        string[] customFieldKeys;
        // Payment paymentDetails;
        uint256 applicationDate;
        uint256 lastModifiedDate;
        uint256 approvalDate;
        uint256 rejectionDate;
        uint256 expiryDate;
        uint256 revokedDate;
        uint256 renewalDate;
        int256 latitude;
        int256 longitude;
        Action[] actionHistory;
        bool isActive;
        bool isPaid;
        bool documentsVerified;
        bool inspectionPassed;
    }

    struct Payment {
        uint256 amount;
        string transactionId;
        string paymentMode;
        uint256 paymentDate;
    }

    struct Action {
        uint256 timestamp;
        LicenseStatus actionType;
        string actorName;
        userRole actorRole;
        string remarks;
        string dataHash;
    }

    // Simplified structs for API responses
    struct LicenseBasicInfo {
        string licenseNumber;
        string applicantName;
        LicenseCategory category;
        LicenseLevel level;
        LicenseStatus status;
        string firmName;
        string firmType;
        string firmAddress;
        string salePointAddress;
        string saleStorageAddress;
        string productionCompany;
        string cropName;
        string cropVariety;
        string registeringOfficeName;
        string registeringAuthority;
        uint256 applicationDate;
        uint256 approvalDate;
        uint256 rejectionDate;
        uint256 expiryDate;
        uint256 revokedDate;
        uint256 renewalDate;
        int256 latitude;
        int256 longitude;
        bool isActive;
        bool isPaid;
        bool documentsVerified;
        bool inspectionPassed;
    }

    struct LicenseVerificationData {
        bool isValid;
        bool isActive;
        bool isExpired;
        bool isRevoked;
        string licenseNumber;
        uint256 approvalDate;
        uint256 expiryDate;
        uint256 revokedDate;
        string verificationHash;
        string statusMessage;
    }

    struct LicenseApplicationInput {
        LicenseCategory category;
        LicenseLevel level;
        string licenseNumber;
        string registeringAuthority;
        string registeringOfficeName;
        string applicantName;
        string aadhaarNumber;
        string applicantPermanentAddress;
        string firmName;
        string firmType;
        string firmAddress;
        string salePointAddress;
        string saleStorageAddress;
        string productionCompany;
        string cropName;
        string cropVariety;
        int256 latitude;
        int256 longitude;
    }

    // Main storage mappings
    mapping(string => License) internal licenses;
    mapping(address => bool) internal authorizedApiCallers;

    // Tracking arrays
    string[] internal allLicenseNumbers;
    mapping(LicenseStatus => string[]) internal licensesByStatus;
    mapping(LicenseCategory => string[]) internal licensesByCategory;
    mapping(LicenseLevel => string[]) internal licensesByLevel;

    // Gap for future storage variables
    uint256[50] private __gap;
}
