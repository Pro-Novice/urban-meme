// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title LicenseStorage
 * @dev Separates storage from logic for upgradeability
 */
contract LicenseStorage {
    // Storage slot positions as constants to avoid collisions
    bytes32 private constant LICENSE_COUNTER_SLOT = keccak256("license.storage.licenseCounter");

    // Enums
    enum LicenseCategory {
        SEED,
        FERTILIZER,
        INSECTICIDE
    }
    enum LicenseLevel {
        STATE,
        DIVISION,
        DISTRICT
    }
    enum LicenseStatus {
        DRAFT,
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
    enum ActionType {
        CREATED,
        SUBMITTED,
        DOCUMENT_UPLOADED,
        DOCUMENT_VERIFIED,
        DOCUMENT_REJECTED,
        PAYMENT_RECORDED,
        INSPECTION_SCHEDULED,
        INSPECTION_COMPLETED,
        STATUS_UPDATED,
        APPROVED,
        REJECTED,
        REVOKED,
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
    enum Division {
        AJMER_DIVISION,
        BHARATPUR_DIVISION,
        BIKANER_DIVISION,
        JAIPUR_DIVISION,
        JODHPUR_DIVISION,
        KOTA_DIVISION,
        UDAIPUR_DIVISION
    }
    enum StandardDocumentType {
        AFFIDAVIT_SEED_QUALITY,
        ID_PROOF,
        SHOP_MAP,
        REGISTRATION_CERTIFICATE,
        MEMORANDUM_ARTICLES,
        PASSPORT_PHOTO,
        AUTHORIZATION_LETTER
    }
    enum InspectionFeedbackType {
        NONE,
        SATISFACTORY,
        UNSATISFACTORY,
        NEEDS_REINSPECTION
    }

    // Core License Structure
    struct License {
        uint256 licenseId;
        string licenseNumber;
        LicenseCategory category;
        LicenseLevel level;
        LicenseStatus status;
        string applicantName;
        string aadhaarNumber;
        string panNumber;
        string gstNumber;
        string mobileNumber;
        string businessName;
        string businessType;
        string businessAddress;
        string state;
        string division;
        string district;
        mapping(string => string) customFields;
        string[] customFieldKeys;
        mapping(StandardDocumentType => Document) documents;
        StandardDocumentType[] documentTypes;
        Payment paymentDetails;
        Inspection[] inspections;
        uint256 applicationDate;
        uint256 lastModifiedDate;
        uint256 approvalDate;
        uint256 rejectionDate;
        uint256 expiryDate;
        uint256 revokedDate;
        uint256 renewalDate;
        Action[] actionHistory;
        bool isActive;
        bool isPaid;
        bool documentsVerified;
        bool inspectionPassed;
    }

    struct Document {
        StandardDocumentType documentType;
        string documentName;
        string documentHash;
        bool isVerified;
        string verifiedByOfficerId; // Store officer ID instead of address
        uint256 verificationDate;
        string remarks;
    }

    struct Payment {
        uint256 amount;
        string transactionId;
        string paymentMode;
        uint256 paymentDate;
        string recordedByOfficerId; // Store officer ID instead of address
        bool isVerified;
        string receiptNumber;
    }

    struct Inspection {
        uint256 inspectionId;
        uint256 scheduledDate;
        uint256 completedDate;
        string inspectorOfficerId; // Store officer ID instead of address
        string inspectorName;
        string gpsLocation;
        bytes32[] photoHashes;
        mapping(string => string) findings;
        string[] findingKeys;
        bool passed;
        InspectionFeedbackType feedbackType;
        string remarks;
        string reportHash;
    }

    struct Action {
        uint256 timestamp;
        ActionType actionType;
        string actorName;
        userRole actorRole;
        string remarks;
        string dataHash;
    }

    // Simplified structs for API responses
    struct LicenseBasicInfo {
        uint256 licenseId;
        string licenseNumber;
        string applicantName;
        LicenseCategory category;
        LicenseLevel level;
        LicenseStatus status;
        string businessName;
        string businessAddress;
        string district;
        string state;
        string division;
        uint256 applicationDate;
        uint256 approvalDate;
        uint256 rejectionDate;
        uint256 expiryDate;
        uint256 revokedDate;
        uint256 renewalDate;
        bool isActive;
        bool isPaid;
        bool documentsVerified;
        bool inspectionPassed;
    }

    struct InspectionFeedback {
        string inspectorOfficerId;
        string inspectorName;
        string remarks;
        uint256 completedDate;
        InspectionFeedbackType feedbackType;
    }

    // Main storage mappings
    mapping(uint256 => License) internal licenses;
    mapping(string => uint256) internal licenseNumberToId;
    mapping(address => bool) internal authorizedApiCallers;

    // Tracking arrays
    uint256[] internal allLicenseIds;
    mapping(address => uint256[]) internal applicantLicenses;
    mapping(LicenseStatus => uint256[]) internal licensesByStatus;
    mapping(LicenseCategory => uint256[]) internal licensesByCategory;
    mapping(LicenseLevel => uint256[]) internal licensesByLevel;
    mapping(string => uint256[]) internal licensesByDistrict;
    mapping(address => bool) internal admins;

    // Gap for future storage variables
    uint256[50] private __gap;

    // License counter getter/setter
    function licenseIdCounter() public view returns (uint256 _counter) {
        bytes32 slot = LICENSE_COUNTER_SLOT;
        assembly {
            _counter := sload(slot)
        }
    }

    function _incrementLicenseCounter() internal returns (uint256 _newValue) {
        bytes32 slot = LICENSE_COUNTER_SLOT;
        assembly {
            _newValue := add(sload(slot), 1)
            sstore(slot, _newValue)
        }
    }
}
