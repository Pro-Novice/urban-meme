#!/bin/bash
set -e  # Exit on error

# Colors for logs
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}####################################################################"
    echo -e "   $1"
    echo -e "####################################################################${NC}"
}

# Load .env if exists
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

# Validate Redis credentials
if [[ -z "$REDIS_USER" || -z "$REDIS_PASSWORD" ]]; then
    echo -e "${RED}Error: REDIS_USER and REDIS_PASSWORD must be set in .env${NC}"
    exit 1
fi

# Ask user for environment to run
echo "Select environment to deploy:"
echo "1) Local (with Postgres)"
echo "2) Server (no Postgres)"
read -rp "Enter your choice [1 or 2]: " ENV_CHOICE

if [[ "$ENV_CHOICE" == "1" ]]; then
    COMPOSE_FILE="docker-compose.local.yml"
    ENV_NAME="Local"
elif [[ "$ENV_CHOICE" == "2" ]]; then
    COMPOSE_FILE="docker-compose.yaml"
    ENV_NAME="Server"
else
    echo -e "${RED}Invalid choice! Please run the script again and enter 1 or 2.${NC}"
    exit 1
fi

# Ask user if they want to stop containers only
read -rp "Do you want to stop existing containers only? (y/N): " STOP_ONLY
STOP_ONLY=${STOP_ONLY,,}  # lowercase

if [[ "$STOP_ONLY" == "y" || "$STOP_ONLY" == "yes" ]]; then
    log "Stopping and Removing Containers for $ENV_NAME Environment"
    docker compose -f "$COMPOSE_FILE" down 
    exit 0
fi

log "Stopping Existing Containers for $ENV_NAME Environment"
docker compose -f "$COMPOSE_FILE" down 

log "Building and Starting Containers for $ENV_NAME Environment"
docker compose -f "$COMPOSE_FILE" up -d --build

# Configure Redis ACL
log "Configuring Redis ACL"
if docker exec -i rajasthan-seed-redis redis-cli \
    ACL SETUSER "$REDIS_USER" on > password \
    ">$REDIS_PASSWORD" +@all ~*; then
    log "Redis ACL Configured Successfully"
else
    echo -e "${RED}Redis ACL Configuration Failed${NC}"
    exit 1
fi

# Done
log "Deployment Successful"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
