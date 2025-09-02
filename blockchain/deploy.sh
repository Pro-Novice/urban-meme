#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "🚀 Starting deployment process..."

# 1. Check for the .env file
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found."
    echo "Please create it by copying .env.example and adding your BESU_PRIVATE_KEY and BESU_RPC_URL."
    exit 1
fi

# 2. Build the Docker image -> image will be tagged as 'hardhat-deployer'
echo "🛠️  Building Docker image 'hardhat-deployer'..."
docker build -t hardhat-deployer .

echo "Docker image built successfully."

# Task argument (default = deploy)
TASK=${1:-deploy}
# 3. Run the deployment script inside the container
echo "🚀 Running Hardhat task: $TASK ..."

case "$TASK" in
    deploy)
        docker run --rm \
        --env-file .env \
        --add-host=host.docker.internal:host-gateway \
        -v "$(pwd)":/app \
        hardhat-deployer \
        npx hardhat run scripts/deploy.ts --network besu
    ;;

    test)
        docker run --rm \
        --env-file .env \
        -v "$(pwd)":/app \
        hardhat-deployer npx hardhat test
    ;;

    gas-test)
        docker run --rm \
        --env-file .env \
        -e REPORT_GAS=true \
        -v "$(pwd)":/app \
        hardhat-deployer npx hardhat test
    ;;

    help)
        docker run --rm \
        -v "$(pwd)":/app \
        hardhat-deployer npx hardhat help
    ;;

    node)
        docker run --rm -it \
        -p 8545:8545 \
        -v "$(pwd)":/app \
        hardhat-deployer npx hardhat node
    ;;

    *)
        echo "❌ Unknown task: $TASK"
        echo "Usage: $0 [deploy|test|gas-test|help|node]"
        exit 1
    ;;
esac
