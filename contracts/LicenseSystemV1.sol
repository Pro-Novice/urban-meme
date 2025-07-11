// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./LicenseStorage.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

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
    event OfficerAdded(address indexed officer, OfficerRole role);
    event FeedbackAdded(uint256 indexed licenseId, address indexed inspector, string remarks, uint256 timestamp);
    event DebugInput(AdminLevel level,string state,string division,string district);
    event DocumentVerificationResult(
    uint256 indexed licenseId,
    StandardDocumentType indexed documentType,
    address indexed officer,
    string documentHash,
    bool isVerified,
    string remarks,
    uint256 timestamp
    );
    event DocumentScrutinyStarted(
        uint256 indexed licenseId,
        string indexed documentType,
        address indexed officer
    );

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
    // add Officer -- all level- state, division, district
    function addOfficer(
    address _officer,
    string memory _name,
    string memory _employeeId,
    OfficerRole _role,
    string memory _department,
    AdminLevel _level,
    string memory _state,
    string memory _district,
    string memory _division
) public onlyAdmin {
    require(!isOfficer[_officer], "Already an officer");

emit DebugInput(_level, _state, _division, _district);
    // Validate based on AdminLevel
    if (_level == AdminLevel.STATE) {
        require(bytes(_state).length > 0, "State is required for STATE level");
        require(bytes(_district).length == 0, "District must be empty for STATE level");
        require(bytes(_division).length == 0, "Division must be empty for STATE level");
    } else if (_level == AdminLevel.DIVISION) {
        require(bytes(_division).length > 0, "Division is required for DIVISION level");
        require(bytes(_state).length == 0, "State must be empty for DIVISION level");
        require(bytes(_district).length == 0, "District must be empty for DIVISION level");
    } else if (_level == AdminLevel.DISTRICT) {
        require(bytes(_district).length > 0, "District is required for DISTRICT level");
        require(bytes(_state).length == 0, "State must be empty for DISTRICT level");
        require(bytes(_division).length == 0, "Division must be empty for DISTRICT level");
    } else {
        revert("Invalid admin level");
    }

    officers[_officer] = Officer({
        officerAddress: _officer,
        name: _name,
        employeeId: _employeeId,
        role: _role,
        department: _department,
        level: _level,
        state: _state,
        district: _district,
        division: _division,
        isActive: true,
        addedDate: block.timestamp

    });

    isOfficer[_officer] = true;
    allOfficers.push(_officer);

    emit OfficerAdded(_officer, _role);
}

// create license -- for all levels and for all types
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

    // for update status for license -
    function updateStatus(
    uint256 _licenseId,
    LicenseStatus _newStatus,
    string memory _remarks
) public onlyOfficerOrAdmin licenseExists(_licenseId) {
    License storage license = licenses[_licenseId];
    LicenseStatus oldStatus = license.status;

    // Enforce level match between officer and license
    require(
        officers[msg.sender].level == license.level,
        "Officer level mismatch with license level"
    );

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
            actorRole: isOfficer[msg.sender] ? officers[msg.sender].role : OfficerRole.AGRICULTURE_OFFICER,
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

    function getLicenseBasicInfo(uint256 _licenseId) public view returns (LicenseBasicInfo memory) {
        License storage license = licenses[_licenseId];
        return LicenseBasicInfo({
            licenseId: license.licenseId,
            applicantName: license.applicantName,
            category: license.category,
            level: license.level,
            status: license.status,
            applicant: license.applicant,
            businessName: license.businessName,
            district: license.district,
            applicationDate: license.applicationDate,
            approvalDate: license.approvalDate,
            rejectionDate: license.rejectionDate,
            expiryDate: license.expiryDate,
            revokedDate: license.revokedDate,
            renewalDate: license.renewalDate,
            isActive: license.isActive
        });
    }

    function getOfficerRole(address _officer) public view returns (OfficerRole) {
    require(isOfficer[_officer], "Address is not an officer");
    return officers[_officer].role;
}
    function getOfficerDetails(address _officer) public view returns (
    string memory name,
    string memory employeeId,
    OfficerRole role,
    string memory department,
    AdminLevel level,
    bool isActive,
    uint256 addedDate
) {
    require(isOfficer[_officer], "Address is not an officer");
    Officer storage officer = officers[_officer];
    return (
        officer.name,
        officer.employeeId,
        officer.role,
        officer.department,
        officer.level,
        officer.isActive,
        officer.addedDate
    );
}
    function listAllFunctions() public pure returns (string[] memory) {
    string[] memory functions = new string[](14);
    functions[0] = "getOfficerRole(address)";
    functions[1] = "getOfficerDetails(address)";
    functions[2] = "addOfficer(address,string,string,string,string,uint8,string)";
    functions[3] = "createLicense(uint8,uint8,string,string,string,string,string)";
    functions[4] = "updateStatus(uint256,uint8,string)";
    functions[5] = "getLicenseBasicInfo(uint256)";
    functions[6] = "getLicenseActionHistory(uint256)";
    functions[7] = "verifyDocument(uint256,uint256,string ,bool ,string )";
    functions[8] = "toDocTypeString(uint256)";
    functions[9] = " getDocumentStatus(uint256,uint256)";
    functions[10] = "addInspectionFeedback(uint256,address,uint256, string)";
    functions[11] = "getFeedbackTypeName(uint256)";
    functions[12] = "countFeedbackByType(uint256,uint256)";
    functions[13] = "getAllInspectionFeedback(uint256)";

    return functions;
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
                actorRole:  action.actorRole,
                department: action.department,
                remarks: action.remarks,
                dataHash: toHexString(action.dataHash)
            });
        }

        return actions;
    }

    // Proper hex conversion functions
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


       // Add the document verification function
   function verifyDocument(
    uint256 _licenseId,
    StandardDocumentType _documentType,
    string memory _documentHash,
    bool _isVerified,
    string memory _remarks
) public onlyOfficerOrAdmin licenseExists(_licenseId) {
    License storage license = licenses[_licenseId];

    Document storage doc = license.documents[_documentType];
    require(!doc.isVerified, "Document already verified");
    require(bytes(_documentHash).length > 0, "Document hash is required");

    doc.documentType = _documentType;
    doc.documentHash = _documentHash;
    doc.isVerified = _isVerified;
    doc.verifiedBy = msg.sender;
    doc.verificationDate = block.timestamp;
    doc.remarks = _remarks;

    // Track the document type if new
    bool exists = false;
    for (uint i = 0; i < license.documentTypes.length; i++) {
        if (license.documentTypes[i] == _documentType) {
            exists = true;
            break;
        }
    }
    if (!exists) {
        license.documentTypes.push(_documentType);
    }

    string memory actionRemark = string(
        abi.encodePacked(toDocTypeString(_documentType), _isVerified ? " verified: " : " rejected: ", _remarks)
    );

    _recordAction(
        _licenseId,
        _isVerified ? ActionType.DOCUMENT_VERIFIED : ActionType.DOCUMENT_REJECTED,
        actionRemark
    );

    emit DocumentVerificationResult(
        _licenseId,
        _documentType,
        msg.sender,
        _documentHash,
        _isVerified,
        _remarks,
        block.timestamp
    );

    _checkAllDocumentsVerified(_licenseId);
}
    function toDocTypeString(StandardDocumentType _type) public pure returns (string memory) {
    if (_type == StandardDocumentType.AFFIDAVIT_SEED_QUALITY) return "Affidavit Seed Quality";
    if (_type == StandardDocumentType.ID_PROOF) return "ID Proof";
    if (_type == StandardDocumentType.SHOP_MAP) return "Shop Map";
    if (_type == StandardDocumentType.REGISTRATION_CERTIFICATE) return "Registration Certificate";
    if (_type == StandardDocumentType.MEMORANDUM_ARTICLES) return "Memorandum of Articles";
    if (_type == StandardDocumentType.PASSPORT_PHOTO) return "Passport Photo";
    if (_type == StandardDocumentType.AUTHORIZATION_LETTER) return "Authorization Letter";
    return "Unknown";
}


      // Add helper function to check all documents
    function _checkAllDocumentsVerified(uint256 _licenseId) internal {
        License storage license = licenses[_licenseId];
        bool allVerified = true;

        for (uint i = 0; i < license.documentTypes.length; i++) {
            if (!license.documents[license.documentTypes[i]].isVerified) {
                allVerified = false;
                break;
            }
        }

        if (allVerified && !license.documentsVerified) {
            license.documentsVerified = true;
            _recordAction(_licenseId, ActionType.DOCUMENT_VERIFIED, "All documents verified");

            if (license.status == LicenseStatus.DOCUMENTS_VERIFIED) {
                updateStatus(_licenseId, LicenseStatus.PAYMENT_PENDING, "Documents verified, pending payment");
            }
        }
    }

    function getDocumentStatus(
    uint256 _licenseId,
    StandardDocumentType _documentType
) public view licenseExists(_licenseId) returns (
    bool isVerified,
    address verifiedBy,
    uint256 verificationDate,
    string memory remarks,
    string memory documentHash
) {
    Document storage doc = licenses[_licenseId].documents[_documentType];
    return (
        doc.isVerified,
        doc.verifiedBy,
        doc.verificationDate,
        doc.remarks,
        doc.documentHash
    );
}
    function getAllDocumentStatuses(
    uint256 _licenseId
) public view licenseExists(_licenseId) returns (
    string[] memory documentTypes,
    bool[] memory verificationStatuses,
    string[] memory remarks
) {
    License storage license = licenses[_licenseId];
    uint256 count = license.documentTypes.length;

    documentTypes = new string[](count);
    verificationStatuses = new bool[](count);
    remarks = new string[](count);

    for (uint i = 0; i < count; i++) {
        StandardDocumentType docType = license.documentTypes[i];
        documentTypes[i] = toDocTypeString(docType);  // Use your converter function here
        verificationStatuses[i] = license.documents[docType].isVerified;
        remarks[i] = license.documents[docType].remarks;
    }

    return (documentTypes, verificationStatuses, remarks);
}
    /// New function to add inspection feedback
    function addInspectionFeedback(
        uint256 _licenseId,
        address _inspector,
        InspectionFeedbackType _feedbackType,
        string memory _remarks
    )
        public
        onlyOfficerOrAdmin
        licenseExists(_licenseId)
    {
        require(isOfficer[_inspector], "Inspector is not a registered officer");
        require(_feedbackType != InspectionFeedbackType.NONE, "Invalid feedback type");

        License storage license = licenses[_licenseId];

        uint256 inspectionIndex = license.inspections.length;
        if (
            inspectionIndex == 0 ||
            license.inspections[inspectionIndex - 1].completedDate != 0
        ) {
            license.inspections.push();
            inspectionIndex++;
        }

        Inspection storage inspection = license.inspections[inspectionIndex - 1];
        inspection.inspector = _inspector;
        inspection.inspectorName = officers[_inspector].name;
        inspection.completedDate = block.timestamp;
        inspection.feedbackType = _feedbackType;
        inspection.remarks = _remarks;
        inspection.passed = (_feedbackType == InspectionFeedbackType.SATISFACTORY);

        _recordAction(_licenseId, ActionType.COMMENT_ADDED, _remarks);

        emit FeedbackAdded(_licenseId, _inspector, _remarks, block.timestamp);
    }

    function getFeedbackTypeName(InspectionFeedbackType _type) public pure returns (string memory) {
        if (_type == InspectionFeedbackType.SATISFACTORY) return "Satisfactory";
        if (_type == InspectionFeedbackType.UNSATISFACTORY) return "Unsatisfactory";
        if (_type == InspectionFeedbackType.NEEDS_REINSPECTION) return "Needs Reinspection";
        return "None";
    }

    function countFeedbackByType(uint256 _licenseId, InspectionFeedbackType _type)
        public
        view
        licenseExists(_licenseId)
        returns (uint256 count)
        {
            Inspection[] storage inspections = licenses[_licenseId].inspections;
            for (uint i = 0; i < inspections.length; i++) {
                if (inspections[i].feedbackType == _type) {
                    count++;
                }
            }
        }

    function getAllInspectionFeedback(uint256 _licenseId)
        public
        view
        licenseExists(_licenseId)
        returns (getAllFeedback[] memory)
    {
        License storage license = licenses[_licenseId];
        uint256 count = license.inspections.length;

        getAllFeedback[] memory feedback = new getAllFeedback[](count);

        for (uint i = 0; i < count; i++) {
            Inspection storage ins = license.inspections[i];
            feedback[i] = getAllFeedback({
                inspector: ins.inspector,
                inspectorName: ins.inspectorName,
                remarks: ins.remarks,
                completedDate: ins.completedDate,
                feedbackType: ins.feedbackType
            });
        }

        return feedback;
    }


}