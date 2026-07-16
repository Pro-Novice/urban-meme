import { expect } from "chai";
import { ethers, upgrades } from "hardhat";

describe("LicenseSystemV2 application license type", function () {
  async function deployV2() {
    const LicenseSystemV1 = await ethers.getContractFactory("LicenseSystemV1");
    const v1 = await upgrades.deployProxy(LicenseSystemV1, [], {
      initializer: "initialize",
      kind: "uups",
    });
    await v1.waitForDeployment();

    const LicenseSystemV2 = await ethers.getContractFactory("LicenseSystemV2");
    const v2 = await upgrades.upgradeProxy(await v1.getAddress(), LicenseSystemV2);
    await v2.waitForDeployment();
    return v2;
  }

  function seedSubmission(applicationLicenseType = "NEW_APPLICATION") {
    return {
      category: 0, // SEED
      applicationLicenseType,
      level: 0, // STATE
      licenseNumber: "RJSDST-V2-001",
      registeringAuthority: "Department of Agriculture",
      registeringOfficeName: "District Agri Office, Jaipur",
      applicantName: "Ravi Kumar",
      aadhaarNumber: "encrypted-aadhaar",
      applicantPermanentAddress: "H.No 45, Green Colony, Jaipur",
      firmName: "Ravi Agro Traders",
      firmType: "Partnership",
      firmAddress: "Plot No 22, Mandi Road, Jaipur",
      salePointAddress: "Shop No 5, Krishi Market, Jaipur",
      saleStorageAddress: "Warehouse No 3, Outer Ring Road, Jaipur",
      productionCompany: "Ravi Agro Traders",
      cropName: ["Wheat"],
      cropVariety: ["HD2967"],
      latitude: 0,
      longitude: 0,
    };
  }

  function applicationTypeUpdate(applicationLicenseType: string) {
    return {
      applicationLicenseType,
      applicantName: "",
      aadhaarNumber: "",
      applicantPermanentAddress: "",
      firmName: "",
      firmType: "",
      firmAddress: "",
      salePointAddress: "",
      saleStorageAddress: "",
      productionCompany: "",
      cropName: [],
      cropVariety: [],
      isSeedSelfProduced: false,
      isSeedSelfProducedProvided: false,
      latitude: 0,
      longitude: 0,
      coordinatesProvided: false,
    };
  }

  async function createRenewedSeedLicense() {
    const contract = await deployV2();
    await contract.submitLicenseApplicationV2(seedSubmission());

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

    return { contract, licenseId, officerRole };
  }

  it("updates a renewed license to another type allowed for its category", async function () {
    const { contract, licenseId, officerRole } =
      await createRenewedSeedLicense();

    await expect(
      contract.updateLicenseDetails(
        licenseId,
        applicationTypeUpdate("OLD_APPLICATION"),
        officerRole
      )
    ).to.emit(contract, "LicenseDetailsUpdated");

    const license = await contract.getLicenseBasicInfo(licenseId);
    expect(license.status).to.equal(9); // RENEWED
    expect(license.applicationLicenseType).to.equal("OLD_APPLICATION");
  });

  it("rejects a cross-category type update and preserves the stored value", async function () {
    const { contract, licenseId, officerRole } =
      await createRenewedSeedLicense();

    await expect(
      contract.updateLicenseDetails(
        licenseId,
        applicationTypeUpdate("RETAIL_DEALER"), // FERTILIZER only
        officerRole
      )
    ).to.be.revertedWith("Invalid application license type for category");

    const license = await contract.getLicenseBasicInfo(licenseId);
    expect(license.applicationLicenseType).to.equal("NEW_APPLICATION");
  });

  it("rejects a cross-category type during V2 submission", async function () {
    const contract = await deployV2();

    await expect(
      contract.submitLicenseApplicationV2(seedSubmission("SALES_LICENSE"))
    ).to.be.revertedWith("Invalid application license type for category");
    expect(await contract.licenseIdCounter()).to.equal(0);
  });
});
