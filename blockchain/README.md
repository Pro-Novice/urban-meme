# Smart Contracts Compilation and Deployment using Hardhat

This repository contains the smart contracts and deployment scripts for the **License System**, designed with **UUPS upgradeability** using OpenZeppelin and deployed on **Besu** or other Ethereum-compatible networks.

The project uses **Hardhat** for development, testing, and deployment, and supports both **Dockerized workflows** (for consistency across environments) and **local Node.js setups**.

---

## 🚀 Features

* Modular and upgradeable **UUPS Proxy** pattern
* Deployment scripts for seamless upgrades (V1 → V2 → …)
* Compatible with **Besu**, testnets, and local Hardhat nodes
* Fully containerized workflow with **Docker**
* Simple `deploy.sh` wrapper for deployment without typing long Docker commands

---

## ⚡ Quick Start & Usage

You can run all project tasks either using **Docker (recommended)** or **locally with Node.js**.

---

### Option 1: Using Docker 🐳 (Recommended)

Using Docker ensures a consistent environment for building, testing, and deploying your contracts.
A helper script `deploy.sh` is included for convenience.

#### **Prerequisites**

* [Docker](https://www.docker.com/get-started) installed and running
* A running Besu node (or other EVM-compatible RPC endpoint)

#### **1. Environment Setup**

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Edit `.env` with your deployment details:

```env
PRIVATE_KEY=your_private_key
BESU_RPC_URL=http://host.docker.internal:8545
```

> ℹ️ On Linux, if using a local Besu node, the helper script already handles the
> `--add-host=host.docker.internal:host-gateway` mapping for you.

#### **2. Build the Docker Image**

```bash
docker build -t hardhat-project .
```

#### **3. Run Hardhat Tasks**

* **Deploy contracts** (using the helper script, recommended):

  ```bash
  ./deploy.sh
  ```

  This will run the deployment inside Docker and write `deployment_info.json` to your project root.

* **Run tests:**

  ```bash
  ./deploy.sh test
  ```

* **Run tests with gas report:**

  ```bash
  ./deploy.sh gas-test 
  ```

* **Start a local Hardhat node:**

  ```bash
  ./deploy.sh node
  ```

* **Get Hardhat help:**

  ```bash
  ./deploy.sh help
  ```

> You can still run raw Docker commands if needed, but `deploy.sh` simplifies the workflow.

---

### Option 2: Using a Local Node.js Environment

#### **Prerequisites**

* Node.js (v18 or later)
* npm

#### **1. Install Dependencies**

```bash
npm install
```

#### **2. Run Hardhat Tasks**

* **Get help:**

  ```bash
  npx hardhat help
  ```

* **Run tests:**

  ```bash
  npx hardhat test
  ```

* **Run tests with gas report:**

  ```bash
  REPORT_GAS=true npx hardhat test
  ```

* **Start a local Hardhat node:**

  ```bash
  npx hardhat node
  ```

* **Deploy to a network** (example with Amoy testnet):

  ```bash
  npx hardhat run scripts/deploy.ts --network amoy
  ```

---

## 📂 Project Structure

```
.
├── contracts/            # Solidity smart contracts
├── scripts/              # Deployment and upgrade scripts
├── test/                 # Unit and integration tests
├── hardhat.config.ts     # Hardhat configuration
├── Dockerfile            # Docker setup
├── deploy.sh             # Helper script for Docker commands
├── .env.example          # Environment variables template
└── deployment_info.json  # Deployment artifacts (auto-generated)
```

---

## 📝 Notes

* Default deploy script upgrades from **V1 → V2** and verifies state preservation.
* Deployment details are stored in `deployment_info.json`.
* When using Docker, volume mounting ensures that `deployment_info.json` is always written to your local project directory.
* On Linux + local Besu, the helper script already adds the host gateway for connecting to `http://host.docker.internal:8545`.