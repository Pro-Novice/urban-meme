# Smart Contracts Compilation and Deployment using Hardhat

This repository contains the smart contracts and deployment scripts for the **License System**, designed with **UUPS upgradeability** using OpenZeppelin.

The project is fully containerized using **Docker** and managed by a simple shell script, ensuring a consistent and portable development and deployment environment. It's designed to connect to **Besu** or other Ethereum-compatible networks.

-----

## 🚀 Features

  * Modular and upgradeable **UUPS Proxy** pattern.
  * Fully containerized with **Docker** for hassle-free setup.
  * Simple `deploy.sh` script to manage all Hardhat tasks (deploy, test, etc.).
  * Compatible with **Besu**, testnets, and local Hardhat nodes.
  * Deployment scripts for seamless upgrades (V1 → V2 → …).

-----

## ⚡ Quick Start & Usage

### Prerequisites

  * [Docker](https://www.docker.com/) installed and running.
  * A running Besu node (or other EVM-compatible RPC endpoint).

-----

### 1\. Environment Setup

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Edit the `.env` file with your deployment details:

```env
BESU_PRIVATE_KEY=your_private_key
BESU_RPC_URL=http://127.0.0.1:8545
```

**Note:** If you are running the Besu node in a local Docker container, use `http://host.docker.internal:8545` for `BESU_RPC_URL` to allow the Hardhat container to connect to it.

-----

### 2\. Make Script Executable

Before first use, make the deployment script executable (you only need to do this once):

```bash
chmod +x deploy.sh
```

-----

### 3\. Run Tasks with the Script

The `deploy.sh` script handles building the Docker image and running all Hardhat commands within the container.

  * **Deploy contracts to Besu:**
    *(This is the default command)*

    ```bash
    ./deploy.sh deploy
    ```

  * **Run tests:**

    ```bash
    ./deploy.sh test
    ```

  * **Run tests with a gas report:**

    ```bash
    ./deploy.sh gas-test
    ```

  * **Start a local Hardhat node:**
    *(Exposes the node on `http://127.0.0.1:8545`)*

    ```bash
    ./deploy.sh node
    ```

  * **Get Hardhat help:**

    ```bash
    ./deploy.sh help
    ```

-----

## 📂 Project Structure

```
.
├── contracts/            # Solidity smart contracts
├── scripts/              # Deployment and upgrade scripts
├── test/                 # Unit and integration tests
├── hardhat.config.ts     # Hardhat configuration
├── Dockerfile            # Defines the container environment
├── deploy.sh             # Script to run all tasks
├── .env.example          # Environment variables template
└── deployment_info.json  # Deployment artifacts (auto-generated)
```

-----

## 📝 Notes

  * All commands are executed within a Docker container to eliminate local dependency issues. The script automatically builds the Docker image on the first run.
  * The default deploy script (`scripts/deploy.ts`) upgrades the contract from **V1 → V2** and verifies state preservation.
  * Deployment details are saved to `deployment_info.json` in your local project directory.
  * Ensure your Besu (or other RPC endpoint) is running and accessible before deploying.