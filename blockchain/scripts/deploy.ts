import { ethers, upgrades, network, artifacts } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
    console.log("===================== Deploying License System =============================");

    // Network information
    const chainId = network.config.chainId!;
    const networkName = network.name === "unknown" ? "Ganache" : network.name;

    // Deployer address
    const [deployer] = await ethers.getSigners();
    const deployerAddress = await deployer.getAddress();
    
    console.log(`Deploying from account: ${deployerAddress}`);
    console.log(`Network: ${networkName} (Chain ID: ${chainId})`);

    const LicenseSystemV1 = await ethers.getContractFactory("LicenseSystemV1");
    const LicenseSystemV2 = await ethers.getContractFactory("LicenseSystemV2");

    console.log("Deploying UUPS proxy with V1...");
    
    // Deploying UUPS proxy with V1
    const proxy = await upgrades.deployProxy(LicenseSystemV1, [], {
        initializer: "initialize",
        kind: "uups",
    });
    
    // Wait for deployment to complete
    await proxy.waitForDeployment();
    
    const proxyAddress = await proxy.getAddress();
    console.log(`Proxy deployed at: ${proxyAddress}`);

    // V1 implementation address
    const v1ImplAddress = await upgrades.erc1967.getImplementationAddress(proxyAddress);
    console.log(`V1 Implementation deployed at: ${v1ImplAddress}`);

    // Testing V1 functionality before upgrading
    console.log("Testing V1 functionality...");
    try {
        const owner = await proxy.owner();
        const counter = await proxy.licenseIdCounter();
        console.log(`V1 Contract owner: ${owner}`);
        console.log(`V1 Initial counter: ${counter}`);
    } catch (error) {
        console.error("V1 Testing failed:", error);
        throw error;
    }

    console.log("Upgrading to V2...");
    
    // Upgrade to V2
    const upgraded = await upgrades.upgradeProxy(proxyAddress, LicenseSystemV2);
    await upgraded.waitForDeployment();
    
    // Get V2 implementation address
    const v2ImplAddress = await upgrades.erc1967.getImplementationAddress(proxyAddress);
    console.log(`Upgraded to V2. New implementation at: ${v2ImplAddress}`);

    // Test V2 functionality
    console.log("Testing V2 functionality...");
    try {
        const owner = await upgraded.owner();
        const counter = await upgraded.licenseIdCounter();
        console.log(`V2 Contract owner: ${owner}`);
        console.log(`V2 Counter (preserved): ${counter}`);
    } catch (error) {
        console.error("V2 Testing failed:", error);
        throw error;
    }

    // Get contract ABIs from artifacts
    const v1Artifact = await artifacts.readArtifact("LicenseSystemV1");
    const v2Artifact = await artifacts.readArtifact("LicenseSystemV2");

    // Prepare deployment info
    const deploymentInfo = {
        network: chainId,
        networkName: networkName,
        deployer: deployerAddress,
        proxy: proxyAddress,
        currentImplementation: "V2",
        admin: deployerAddress,
        deploymentTime: new Date().toISOString(),
        implementations: {
            V1: {
                address: v1ImplAddress,
                abi: v1Artifact.abi,
                deploymentHash: proxy.deploymentTransaction()?.hash
            },
            V2: {
                address: v2ImplAddress,
                abi: v2Artifact.abi,
                upgradeHash: upgraded.deploymentTransaction()?.hash
            }
        }
    };

    // Save deployment info
    const filename = path.resolve(process.cwd(), "deployment_info.json");
    fs.writeFileSync(filename, JSON.stringify(deploymentInfo, null, 2));
    console.log(`Deployment information saved to ${filename}`);

    console.log("\nDeployment completed successfully!");
    console.log(`Contract Address: ${proxyAddress}`);
    console.log(`Current Version: V2`);
    console.log(`Network: ${networkName}`);
}

main().catch((error) => {
    console.error("Deployment failed:");
    console.error(error);
    process.exit(1);
});