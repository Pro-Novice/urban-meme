#!/bin/bash
set -e

cd "$(dirname "$0")"   # always run inside blockchain/

# Use BuildKit's persistent cache and avoid a stale custom Docker Desktop
# builder when the built-in desktop-linux builder is available.
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
if [ -z "${BUILDX_BUILDER:-}" ] && docker buildx inspect desktop-linux >/dev/null 2>&1; then
  export BUILDX_BUILDER=desktop-linux
fi

COMPOSE_FILE="docker-compose.hardhat.yml"
SERVICE="hardhat"

case "$1" in
  up|start)
    echo "🚀 Starting Hardhat container..."
    docker compose -f "$COMPOSE_FILE" up -d --build
    ;;

  down|stop)
    echo "🛑 Stopping Hardhat container..."
    docker compose -f "$COMPOSE_FILE" down
    ;;

  restart)
    echo "🔄 Restarting Hardhat container..."
    docker compose -f "$COMPOSE_FILE" down
    docker compose -f "$COMPOSE_FILE" up -d --build
    ;;

  logs)
    echo "📜 Showing logs for Hardhat container..."
    docker logs -f hardhat-deployer
    ;;

  exec)
    echo "🔗 Opening shell inside Hardhat container..."
    docker exec -it hardhat-deployer sh
    ;;

  status|ps)
    echo "📊 Checking container status..."
    docker compose -f "$COMPOSE_FILE" ps
    ;;

  *)
    echo "⚡ Usage: $0 {start|stop|restart|logs|exec|status}"
    exit 1
    ;;
esac
