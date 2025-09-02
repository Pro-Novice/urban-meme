#!/bin/bash
set -e

IMAGE_NAME="hardhat-project"
CONTAINER_NAME="hardhat-runner"

# Build image if it doesn't exist
if [[ "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
  echo "⚙️  Building Docker image: $IMAGE_NAME ..."
  docker build -t $IMAGE_NAME .
fi

TASK=${1:-deploy}
echo "🚀 Running Hardhat task: $TASK ..."

case "$TASK" in
deploy)
  docker run --rm \
    --name $CONTAINER_NAME \
    --env-file .env \
    --add-host=host.docker.internal:host-gateway \
    -v "$(pwd)":/app \
    $IMAGE_NAME \
    npx hardhat run scripts/deploy.ts --network besu
  ;;

test)
  docker run --rm \
    --name $CONTAINER_NAME \
    --env-file .env \
    -v "$(pwd)":/app \
    $IMAGE_NAME \
    npx hardhat test
  ;;

gas-test)
  docker run --rm \
    --name $CONTAINER_NAME \
    --env-file .env \
    -e REPORT_GAS=true \
    -v "$(pwd)":/app \
    $IMAGE_NAME \
    npx hardhat test
  ;;

help)
  docker run --rm \
    --name $CONTAINER_NAME \
    -v "$(pwd)":/app \
    $IMAGE_NAME \
    npx hardhat help
  ;;

node)
  docker run --rm -it \
    --name $CONTAINER_NAME \
    -p 8545:8545 \
    -v "$(pwd)":/app \
    $IMAGE_NAME \
    npx hardhat node
  ;;

*)
  echo "❌ Unknown task: $TASK"
  echo "Usage: $0 [deploy|test|gas-test|help|node]"
  exit 1
  ;;
esac
