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

# Stop containers if requested
if [[ $1 == "stop" ]]; then
    log "Stopping and Removing Containers"
    docker compose down -v
    exit 0
fi

# Set environment (dev or staging)
if [[ $1 == "production" ]]; then
    log "Connecting to prod Server"
    export AUTH_PORT=8080
else
    log "Connecting to Staging or Dev Server"
    export AUTH_PORT=8080
fi

# Restart containers
log "Stopping Existing Containers"
docker compose down -v

log "Building and Starting Containers"
docker compose up -d --build

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
