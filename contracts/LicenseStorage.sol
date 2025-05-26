// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title LicenseStorage
 * @dev Separates storage from logic for upgradeability
 */
contract LicenseStorage {
    // Storage slot positions as constants to avoid collisions
    bytes32 private constant ADMIN_SLOT = keccak256("license.storage.admin");
    bytes32 private constant LICENSE_COUNTER_SLOT = keccak256("license.storage.licenseCounter");
    
    // Enums (these don't use storage slots)
    enum LicenseCategory { SEED, FERTILIZER, INSECTICIDE }
    enum AdminLevel { STATE, DIVISION, DISTRICT }
    enum LicenseStatus { DRAFT, SUBMITTED, UNDER_REVIEW, DOCUMENTS_VERIFIED, PAYMENT_PENDING, PAYMENT_COMPLETED, INSPECTION_SCHEDULED, INSPECTION_COMPLETED, APPROVED, REJECTED, REVOKED, EXPIRED, RENEWAL_PENDING }
    enum ActionType { CREATED, SUBMITTED, DOCUMENT_UPLOADED, DOCUMENT_VERIFIED, PAYMENT_RECORDED, INSPECTION_SCHEDULED, INSPECTION_COMPLETED, STATUS_UPDATED, APPROVED, REJECTED, REVOKED, RENEWED, COMMENT_ADDED, OFFICER_ASSIGNED }
    
    // Structs
    struct License {
        uint256 licenseId;
        string licenseNumber;
        LicenseCategory category;
        AdminLevel level;
        LicenseStatus status;
        address applicant;
        string applicantName;
        string aadhaarNumber;
        string panNumber;
        string gstNumber;
        string mobileNumber;
        string email;
        string businessName;
        string businessType;
        string businessAddress;
        string state;
        string division;
        string district;
        string tehsil;
        string village;
        string pincode;
        mapping(string => string) customFields;
        string[] customFieldKeys;
        mapping(string => Document) documents;
        string[] documentTypes;
        Payment paymentDetails;
        Inspection[] inspections;
        uint256 applicationDate;
        uint256 lastModifiedDate;
        uint256 approvalDate;
        uint256 expiryDate;
        uint256 renewalDate;
        Action[] actionHistory;
        address[] assignedOfficers;
        mapping(address => OfficerAssignment) officerAssignments;
        bool isActive;
        bool isPaid;
        bool documentsVerified;
        bool inspectionPassed;
    }
    
    struct Document {
        string documentType;
        string documentName;
        bytes32 documentHash;
        string ipfsHash;
        address uploadedBy;
        uint256 uploadDate;
        bool isVerified;
        address verifiedBy;
        uint256 verificationDate;
        string remarks;
    }
    
    struct Payment {
        uint256 amount;
        string transactionId;
        string paymentMode;
        uint256 paymentDate;
        address recordedBy;
        bool isVerified;
        string receiptNumber;
    }
    
    struct Inspection {
        uint256 inspectionId;
        uint256 scheduledDate;
        uint256 completedDate;
        address inspector;
        string inspectorName;
        string gpsLocation;
        bytes32[] photoHashes;
        mapping(string => string) findings;
        string[] findingKeys;
        bool passed;
        string remarks;
        string reportHash;
    }
    
    struct Action {
        uint256 timestamp;
        ActionType actionType;
        address actor;
        string actorName;
        string actorRole;
        string department;
        string remarks;
        bytes32 dataHash;
    }
    
    struct OfficerAssignment {
        address officer;
        string role;
        string department;
        uint256 assignedDate;
        address assignedBy;
        bool isActive;
        string remarks;
    }
    
    struct Officer {
        address officerAddress;
        string name;
        string employeeId;
        string role;
        string department;
        AdminLevel level;
        string jurisdiction;
        bool isActive;
        uint256 addedDate;
    }
    
    // Main storage mappings - using specific slots
    mapping(uint256 => License) internal licenses;
    mapping(string => uint256) internal licenseNumberToId;
    mapping(address => Officer) internal officers;
    mapping(address => bool) internal isOfficer;
    
    // Tracking arrays
    uint256[] internal allLicenseIds;
    address[] internal allOfficers;
    mapping(address => uint256[]) internal applicantLicenses;
    mapping(address => uint256[]) internal officerAssignedLicenses;
    mapping(LicenseStatus => uint256[]) internal licensesByStatus;
    mapping(LicenseCategory => uint256[]) internal licensesByCategory;
    mapping(AdminLevel => uint256[]) internal licensesByLevel;
    mapping(string => uint256[]) internal licensesByDistrict;
    
    // Gap for future storage variables
    uint256[50] private __gap;
    
    // Admin getter/setter using assembly for specific slot
    function admin() public view returns (address _admin) {
        bytes32 slot = ADMIN_SLOT;
        assembly {
            _admin := sload(slot)
        }
    }
    
    function _setAdmin(address _admin) internal {
        bytes32 slot = ADMIN_SLOT;
        assembly {
            sstore(slot, _admin)
        }
    }
    
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