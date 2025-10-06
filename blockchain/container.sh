#!/bin/bash
set -e

cd "$(dirname "$0")"   # always run inside blockchain/

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
