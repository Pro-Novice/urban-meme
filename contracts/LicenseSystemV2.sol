// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./LicenseSystemV1.sol";

/**
 * @title LicenseSystemV2
 * @dev Upgraded version with new features
 */
contract LicenseSystemV2 is LicenseSystemV1 {

    // New events for V2
    event BulkOperationPerformed(uint256[] licenseIds, string operation);

    // New function in V2
    function bulkUpdateStatus(
        uint256[] memory _licenseIds,
        LicenseStatus _newStatus,
        string memory _remarks
    ) public onlyOfficerOrAdmin {
        for (uint i = 0; i < _licenseIds.length; i++) {
            if (licenses[_licenseIds[i]].applicant != address(0)) {
                updateStatus(_licenseIds[i], _newStatus, _remarks);
            }
        }

        emit BulkOperationPerformed(_licenseIds, "bulkStatusUpdate");
    }

    // Override existing function with new logic
    function createLicense(
        LicenseCategory _category,
        AdminLevel _level,
        string memory _applicantName,
        string memory _aadhaarNumber,
        string memory _businessName,
        string memory _state,
        string memory _district,
        string memory _division
    ) public override returns (uint256) {
        // Call parent function
        uint256 licenseId = super.createLicense(
            _category,
            _level,
            _applicantName,
            _aadhaarNumber,
            _businessName,
            _state,
            _district,
            _division
        );

        // New V2 logic: Auto-assign to district officer
        address districtOfficer = _getDistrictOfficer(_district);
        if (districtOfficer != address(0)) {
            _autoAssignOfficer(licenseId, districtOfficer);
        }

        return licenseId;
    }

    // New internal function for V2
    function _getDistrictOfficer(string memory _district) internal view returns (address) {
        // Logic to find district officer
        // This is just an example
        for (uint i = 0; i < allOfficers.length; i++) {
            if (keccak256(bytes(officers[allOfficers[i]].jurisdiction)) == keccak256(bytes(_district))) {
                return allOfficers[i];
            }
        }
        return address(0);
    }

    function _autoAssignOfficer(uint256 _licenseId, address _officer) internal {
        License storage license = licenses[_licenseId];
        license.assignedOfficers.push(_officer);
        license.officerAssignments[_officer] = OfficerAssignment({
            officer: _officer,
            role: officers[_officer].role,
            department: officers[_officer].department,
            assignedDate: block.timestamp,
            assignedBy: address(this),
            isActive: true,
            remarks: "Auto-assigned"
        });

        officerAssignedLicenses[_officer].push(_licenseId);
    }
}