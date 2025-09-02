# Smart Contracts Compilation and Deployment using Hardhat

This repository contains the smart contracts and deployment scripts for the **License System**, designed with **UUPS upgradeability** using OpenZeppelin and deployed on **Besu** or other Ethereum-compatible networks.

The project uses **Hardhat** for development, testing, and deployment in a **local Node.js environment**.

---

## 🚀 Features

* Modular and upgradeable **UUPS Proxy** pattern
* Deployment scripts for seamless upgrades (V1 → V2 → …)
* Compatible with **Besu**, testnets, and local Hardhat nodes
* Simple commands for compile, test, and deployment

---

## ⚡ Quick Start & Usage

### Prerequisites

* [Node.js](https://nodejs.org/) (v18 or later)
* npm
* A running Besu node (or other EVM-compatible RPC endpoint)

---

### 1. Environment Setup

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Edit `.env` with your deployment details:

```env
BESU_PRIVATE_KEY=your_private_key
BESU_RPC_URL=http://127.0.0.1:8545
```

---

### 2. Install Dependencies

```bash
npm install
```

---

### 3. Run Hardhat Tasks

* **Compile contracts:**

  ```bash
  npx hardhat compile
  ```

* **Run tests:**

  ```bash
  npx hardhat test
  ```

* **Run tests with gas report:**

  ```bash
  GAS_REPORT=true npx hardhat test
  ```

* **Deploy to Besu network:**

  ```bash
  npx hardhat run scripts/deploy.ts --network besu
  ```

* **Start a local Hardhat node:**

  ```bash
  npx hardhat node
  ```

* **Get Hardhat help:**

  ```bash
  npx hardhat help
  ```

---

## 📂 Project Structure

```
.
├── contracts/            # Solidity smart contracts
├── scripts/              # Deployment and upgrade scripts
├── test/                 # Unit and integration tests
├── hardhat.config.ts     # Hardhat configuration
├── .env.example          # Environment variables template
└── deployment_info.json  # Deployment artifacts (auto-generated)
```

---

## 📝 Notes

* Default deploy script upgrades from **V1 → V2** and verifies state preservation.
* Deployment details are stored in `deployment_info.json`.
* Ensure your Besu (or other RPC endpoint) is running and accessible before deploying.