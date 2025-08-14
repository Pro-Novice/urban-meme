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

    // New function in V2
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
