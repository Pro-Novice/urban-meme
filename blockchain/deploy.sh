#!/bin/bash
set -e

cd "$(dirname "$0")"   # ensure we are inside blockchain/

if [ ! -f .env ]; then
  echo "❌ Error: .env file not found."
  echo "Please create one with BESU_RPC_URL and BESU_PRIVATE_KEY."
  exit 1
fi

TASK=${1:-help}   # default = help if no argument

# Optional: skip Hardhat's compile step (useful when the container has no internet)
NO_COMPILE_FLAG=""
if [ "${HARDHAT_NO_COMPILE:-}" = "1" ] || [ "${HARDHAT_NO_COMPILE:-}" = "true" ] || \
   [ "${SKIP_COMPILATION:-}" = "1" ] || [ "${SKIP_COMPILATION:-}" = "true" ] || \
   [ "${NO_COMPILE:-}" = "1" ] || [ "${NO_COMPILE:-}" = "true" ]; then
  NO_COMPILE_FLAG="--no-compile"
fi

case "$TASK" in
  deploy)
    echo "🚀 Compiling + Deploying contracts to Besu..."
    docker compose -f docker-compose.hardhat.yml run --rm hardhat \
      npx hardhat run scripts/deploy.ts --network besu $NO_COMPILE_FLAG
    ;;

  compile)
    echo "🛠️ Compiling contracts..."
    docker compose -f docker-compose.hardhat.yml run --rm -e HARDHAT_OFFLINE=true hardhat \
      npx hardhat compile
    ;;

  test)
    echo "🧪 Running tests..."
    docker compose -f docker-compose.hardhat.yml run --rm -e HARDHAT_OFFLINE=true hardhat \
      npx hardhat test
    ;;

  gas-test)
    echo "⛽ Running gas usage tests..."
    docker compose -f docker-compose.hardhat.yml run --rm -e HARDHAT_OFFLINE=true -e REPORT_GAS=true hardhat \
      npx hardhat test
    ;;

  node)
    echo "🔗 Starting local Hardhat node (port 8545)..."
    docker compose -f docker-compose.hardhat.yml run --rm -e HARDHAT_OFFLINE=true -p 8545:8545 hardhat \
      npx hardhat node
    ;;

  help|*)
    echo "📖 Usage: $0 [deploy|compile|test|gas-test|node|help]"
    ;;
esac
