// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./LicenseStorage.sol";

import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

contract OfficerManagement is Initializable, UUPSUpgradeable, OwnableUpgradeable, LicenseStorage {
    // Events
    event OfficerAdded(address indexed officer, OfficerRole role);
    event OfficerUpdated(address indexed officer);
    event OfficerDeactivated(address indexed officer);

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize() public initializer {
        __Ownable_init(msg.sender);
        __UUPSUpgradeable_init();
        _setAdmin(msg.sender);
    }

    function  _authorizeUpgrade(address newImplementation) internal virtual override onlyOwner {}

    // Modifiers
    modifier onlyAdmin() {
        require(msg.sender == admin(), "Only admin");
        _;
    }


    // Officer Management Functions
    function addOfficer(
        address _officer,
        string memory _name,
        string memory _employeeId,
        OfficerRole _role,
        string memory _department,
        AdminLevel _level,
        string memory _jurisdiction
    ) public onlyAdmin {
        require(!isOfficer[_officer], "Already an officer");

        officers[_officer] = Officer({
            officerAddress: _officer,
            name: _name,
            employeeId: _employeeId,
            role: _role,
            department: _department,
            level: _level,
            jurisdiction: _jurisdiction,
            isActive: true,
            addedDate: block.timestamp
        });

        isOfficer[_officer] = true;
        allOfficers.push(_officer);
        emit OfficerAdded(_officer, _role);
    }
    function isOfficerAddress(address _addr) external view returns (bool) {
    return isOfficer[_addr];
}

    function updateOfficer(
        address _officer,
        string memory _name,
        string memory _employeeId,
        string memory _department,
        bool _isActive
    ) public onlyAdmin {
        require(isOfficer[_officer], "Not an officer");

        Officer storage officer = officers[_officer];
        officer.name = _name;
        officer.employeeId = _employeeId;
        officer.department = _department;
        officer.isActive = _isActive;

        emit OfficerUpdated(_officer);
    }

    function deactivateOfficer(address _officer) public onlyAdmin {
        require(isOfficer[_officer], "Not an officer");
        officers[_officer].isActive = false;
        emit OfficerDeactivated(_officer);
    }

    // View Functions
    function getOfficerRole(address _officer) public view returns (string memory) {
        require(isOfficer[_officer], "Not an officer");
        return officerRoleToString(officers[_officer].role);
    }
    function recordAction(
    uint256 _licenseId,
    ActionType _actionType,
    string memory _remarks
) external {
    _recordAction(_licenseId, _actionType, _remarks);
}
    function getOfficerDetails(address _officer) public view returns (
        string memory name,
        string memory employeeId,
        string memory role,
        string memory department,
        AdminLevel level,
        string memory jurisdiction,
        bool isActive,
        uint256 addedDate
    ) {
        require(isOfficer[_officer], "Not an officer");
        Officer storage officer = officers[_officer];
        return (
            officer.name,
            officer.employeeId,
            officerRoleToString(officer.role),
            officer.department,
            officer.level,
            officer.jurisdiction,
            officer.isActive,
            officer.addedDate
        );
    }

    function listAllOfficers() public view returns (address[] memory) {
        return allOfficers;
    }

    function officerRoleToString(OfficerRole _role) public pure returns (string memory) {
        if (_role == OfficerRole.AGRICULTURE_OFFICER_STATE) return "AGRICULTURE_OFFICER_STATE";
        if (_role == OfficerRole.ASSISTANT_AGRICULTURE_OFFICER_STATE) return "ASSISTANT_AGRICULTURE_OFFICER_STATE";
        if (_role == OfficerRole.ASSISTANT_DIRECTOR_STATE) return "ASSISTANT_DIRECTOR_STATE";
        if (_role == OfficerRole.DEPUTY_DIRECTOR_STATE) return "DEPUTY_DIRECTOR_STATE";
        if (_role == OfficerRole.JOINT_DIRECTOR_STATE) return "JOINT_DIRECTOR_STATE";
        if (_role == OfficerRole.JOINT_DIRECTOR_INPUT_STATE) return "JOINT_DIRECTOR_INPUT_STATE";
        if (_role == OfficerRole.AGRICULTURE_OFFICER_DIVISION) return "AGRICULTURE_OFFICER_DIVISION";
        if (_role == OfficerRole.ASSISTANT_AGRICULTURE_OFFICER_DIVISION) return "ASSISTANT_AGRICULTURE_OFFICER_DIVISION";
        if (_role == OfficerRole.ASSISTANT_DIRECTOR_DIVISION) return "ASSISTANT_DIRECTOR_DIVISION";
        if (_role == OfficerRole.DEPUTY_DIRECTOR_DIVISION) return "DEPUTY_DIRECTOR_DIVISION";
        if (_role == OfficerRole.JOINT_DIRECTOR_DIVISION) return "JOINT_DIRECTOR_DIVISION";
        if (_role == OfficerRole.JOINT_DIRECTOR_INPUT_DIVISION) return "JOINT_DIRECTOR_INPUT_DIVISION";
        if (_role == OfficerRole.AGRICULTURE_OFFICER_DISTRICT) return "AGRICULTURE_OFFICER_DISTRICT";
        if (_role == OfficerRole.ASSISTANT_AGRICULTURE_OFFICER_DISTRICT) return "ASSISTANT_AGRICULTURE_OFFICER_DISTRICT";
        if (_role == OfficerRole.ASSISTANT_DIRECTOR_DISTRICT) return "ASSISTANT_DIRECTOR_DISTRICT";
        if (_role == OfficerRole.DEPUTY_DIRECTOR_DISTRICT) return "DEPUTY_DIRECTOR_DISTRICT";
        if (_role == OfficerRole.JOINT_DIRECTOR_DISTRICT) return "JOINT_DIRECTOR_DISTRICT";
        if (_role == OfficerRole.JOINT_DIRECTOR_INPUT_DISTRICT) return "JOINT_DIRECTOR_INPUT_DISTRICT";
        return "UNKNOWN";
    }

        //internal function to record action
   function _recordAction(
       uint256 _licenseId,
       ActionType _actionType,
       string memory _remarks
   ) internal {
       License storage license = licenses[_licenseId];

       string memory actorRoleStr;
       if (isOfficer[msg.sender]) {
           actorRoleStr = officerRoleToString(officers[msg.sender].role);
       } else {
           actorRoleStr = "Applicant";
       }

       license.actionHistory.push(Action({
           timestamp: block.timestamp,
           actionType: _actionType,
           actor: msg.sender,
           actorName: isOfficer[msg.sender] ? officers[msg.sender].name : license.applicantName,
           actorRole: actorRoleStr,
           department: isOfficer[msg.sender] ? officers[msg.sender].department : "",
           remarks: _remarks,
           dataHash: keccak256(abi.encodePacked(_remarks, block.timestamp))
       }));
   }

}