// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./LicenseSystemV1.sol";

/**
 * @title LicenseSystemV2
 * @dev Upgraded version with new features
 */
contract LicenseSystemV2 is LicenseSystemV1 {
    // New events for V2
    event LicenseDetailsUpdated(uint256 indexed licenseId, uint256 lastModifiedDate);
    event LicenseApplicationSubmittedV2(uint256 indexed licenseId, string licenseNumber, LicenseCategory category, uint256 applicationDate, int256 latitude, int256 longitude);

    // New function in V2
    function submitLicenseApplicationV2(LicenseApplicationInputV2 memory input) public virtual onlyAuthorizedCallers {
        require(bytes(input.licenseNumber).length > 0, "License number required");
        require(licenseNumberToId[input.licenseNumber] == 0, "License number already exists");

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
        newLicense.aadhaarNumber = input.aadhaarNumber;
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
                actionType: LicenseStatus.SUBMITTED,
                actorName: input.applicantName,
                actorRole: userRole.CITIZEN,
                remarks: "License Application Successfully Submitted",
                dataHash: _toHexString(keccak256(abi.encodePacked(input.applicantName, input.firmName, block.timestamp)))
            })
        );

        newLicense.licenseNumber = input.licenseNumber;

        // Update tracking
        allLicenseIds.push(newLicenseId);
        licensesByStatus[LicenseStatus.SUBMITTED].push(newLicenseId);
        licensesByCategory[input.category].push(newLicenseId);
        licensesByLevel[input.level].push(newLicenseId);
        licenseNumberToId[newLicense.licenseNumber] = newLicenseId;

        emit LicenseApplicationSubmittedV2(newLicenseId, newLicense.licenseNumber, input.category, newLicense.applicationDate, newLicense.latitude, newLicense.longitude);
    }

    function updateLicenseDetails(
        uint256 _licenseId,
        string memory _firmName,
        string memory _firmType,
        string memory _firmAddress,
        string memory _salePointAddress,
        string memory _saleStorageAddress,
        string memory _productionCompany,
        string memory _cropName,
        string memory _cropVariety,
        userRole _role
    ) public virtual onlyAuthorizedCallers {
        License storage license = licenses[_licenseId];
        require(license.licenseId != 0, "License does not exist");
        require(license.status == LicenseStatus.APPROVED, "Only approved licenses can be edited");

        // Only update if non-empty
        if (bytes(_firmName).length > 0) license.firmName = _firmName;
        if (bytes(_firmType).length > 0) license.firmType = _firmType;
        if (bytes(_firmAddress).length > 0) license.firmAddress = _firmAddress;
        if (bytes(_salePointAddress).length > 0) license.salePointAddress = _salePointAddress;
        if (bytes(_saleStorageAddress).length > 0) license.saleStorageAddress = _saleStorageAddress;
        if (bytes(_productionCompany).length > 0) license.productionCompany = _productionCompany;
        if (bytes(_cropName).length > 0) license.cropName = _cropName;
        if (bytes(_cropVariety).length > 0) license.cropVariety = _cropVariety;

        license.lastModifiedDate = block.timestamp;

        // Add to action history
        license.actionHistory.push(
            Action({
                timestamp: block.timestamp,
                actionType: LicenseStatus.APPROVED,
                actorName: license.registeringAuthority,
                actorRole: _role,
                remarks: "License details updated",
                dataHash: _toHexString(keccak256(abi.encodePacked(_licenseId, block.timestamp)))
            })
        );

        emit LicenseDetailsUpdated(_licenseId, block.timestamp);
    }

    // Override existing function with new logic

    // New internal function for V2
}
