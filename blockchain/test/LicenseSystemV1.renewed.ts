import { expect } from "chai";
import { anyValue } from "@nomicfoundation/hardhat-chai-matchers/withArgs";
import { ethers, upgrades } from "hardhat";

describe("LicenseSystemV1 renewed licenses", function () {
  async function deployRenewedLicense() {
    const LicenseSystemV1 = await ethers.getContractFactory("LicenseSystemV1");
    const contract = await upgrades.deployProxy(LicenseSystemV1, [], {
      initializer: "initialize",
      kind: "uups",
    });
    await contract.waitForDeployment();

    const applicantName = "Ravi Kumar";
    const firmName = "Ravi Agro Traders";
    const firmAddress = "Plot No 22, Mandi Road, Jaipur";
    const salePointAddress = "Shop No 5, Krishi Market, Jaipur";
    const saleStorageAddress = "Warehouse No 3, Outer Ring Road, Jaipur";

    await contract.submitLicenseApplication({
      category: 0, // SEED
      level: 0, // STATE
      registeringAuthority: "Department of Agriculture",
      registeringOfficeName: "District Agri Office, Jaipur",
      applicantName,
      aadhaarNumber: "encrypted-aadhaar",
      applicantPermanentAddress: "H.No 45, Green Colony, Jaipur",
      firmName,
      firmType: "Partnership",
      firmAddress,
      salePointAddress,
      saleStorageAddress,
      productionCompany: firmName,
      cropName: ["Wheat"],
      cropVariety: ["HD2967"],
      latitude: 0,
      longitude: 0,
    });

    const licenseId = 1;
    const officerRole = 5; // JOINT_DIRECTOR

    await contract.updateLicenseStatus(
      licenseId,
      5, // APPROVED
      "Department of Agriculture",
      officerRole,
      "Approved",
      365
    );
    await contract.updateLicenseStatus(
      licenseId,
      8, // EXPIRED
      "Department of Agriculture",
      officerRole,
      "Expired",
      0
    );
    await contract.updateLicenseStatus(
      licenseId,
      9, // RENEWED
      "Department of Agriculture",
      officerRole,
      "Renewed",
      365
    );

    const verificationHash = ethers
      .solidityPackedKeccak256(
        ["string", "string", "string", "string", "string"],
        [
          applicantName,
          firmName,
          firmAddress,
          salePointAddress,
          saleStorageAddress,
        ]
      )
      .slice(2);

    return { contract, licenseId, officerRole, verificationHash };
  }

  it("verifies a renewed license as valid and active", async function () {
    const { contract, licenseId, verificationHash } =
      await deployRenewedLicense();

    await expect(contract.verifyLicenseWithHash("RJSDST1", verificationHash))
      .to.emit(contract, "LicenseVerificationStatus")
      .withArgs(licenseId, "RJSDST1", "License is valid and active", anyValue);
  });

  it("allows a renewed license to be revoked", async function () {
    const { contract, licenseId, officerRole } = await deployRenewedLicense();

    await expect(
      contract.updateLicenseStatus(
        licenseId,
        7, // REVOKED
        "Department of Agriculture",
        officerRole,
        "Compliance violation",
        0
      )
    ).to.emit(contract, "LicenseRevoked");

    const license = await contract.getLicenseBasicInfo(licenseId);
    expect(license.status).to.equal(7);
    expect(license.isActive).to.equal(false);
    expect(license.revokedDate).to.be.greaterThan(0);
  });

  it("rejects revocation from any status other than approved or renewed", async function () {
    const { contract, licenseId, officerRole } = await deployRenewedLicense();

    await contract.updateLicenseStatus(
      licenseId,
      8, // EXPIRED
      "Department of Agriculture",
      officerRole,
      "Expired",
      0
    );

    await expect(
      contract.updateLicenseStatus(
        licenseId,
        7, // REVOKED
        "Department of Agriculture",
        officerRole,
        "Invalid revocation",
        0
      )
    ).to.be.revertedWith("Only approved or renewed licenses can be revoked");
  });
});
