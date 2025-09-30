#!/bin/bash
set -e

cd "$(dirname "$0")"   # ensure we are inside blockchain/

if [ ! -f .env ]; then
  echo "❌ Error: .env file not found."
  echo "Please create one with BESU_RPC_URL and BESU_PRIVATE_KEY."
  exit 1
fi

TASK=${1:-help}   # default = help if no argument

case "$TASK" in
  deploy)
    echo "🚀 Compiling + Deploying contracts to Besu..."
    docker compose -f docker-compose.hardhat.yml run --rm hardhat \
      npx hardhat run scripts/deploy.ts --network besu
    ;;

  compile)
    echo "🛠️ Compiling contracts..."
    docker compose -f docker-compose.hardhat.yml run --rm hardhat \
      npx hardhat compile
    ;;

  test)
    echo "🧪 Running tests..."
    docker compose -f docker-compose.hardhat.yml run --rm hardhat \
      npx hardhat test
    ;;

  gas-test)
    echo "⛽ Running gas usage tests..."
    docker compose -f docker-compose.hardhat.yml run --rm -e REPORT_GAS=true hardhat \
      npx hardhat test
    ;;

  node)
    echo "🔗 Starting local Hardhat node (port 8545)..."
    docker compose -f docker-compose.hardhat.yml run --rm -p 8545:8545 hardhat \
      npx hardhat node
    ;;

  help|*)
    echo "📖 Usage: $0 [deploy|compile|test|gas-test|node|help]"
    ;;
esac
