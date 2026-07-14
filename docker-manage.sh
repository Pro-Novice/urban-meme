#!/bin/bash
set -e  # Exit on error

# Colors for logs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}####################################################################\n   $1\n####################################################################${NC}"
}


mkdir -p ./logs
LOG_DATE=$(date +"%Y-%m-%d")
LOG_FILE="./logs/deployment_${LOG_DATE}.txt" 
PID_FILE="./.live_logger.pid"


> "$LOG_FILE"                                          
exec > >(tee >(sed -u -r 's/\x1B\[[0-9;?]*[ -\/]*[@-~]//g; s/\r/\n/g' > "$LOG_FILE")) 2>&1

echo "========================================================================"
echo " Session started : $(date)"
echo " Log file        : $LOG_FILE"
echo "========================================================================"


# ── Live logger functions ─────────────────────────────────────────────────────
stop_live_logger() {
    if [[ -f "$PID_FILE" ]]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
}

start_live_logger() {
    stop_live_logger
    # Always append to today's dated file
    CURRENT_LOG="./logs/deployment_$(date +"%Y-%m-%d").txt"
    docker compose -f "$COMPOSE_FILE" logs -f --no-color >> "$CURRENT_LOG" 2>&1 &
    echo $! > "$PID_FILE"
}

# Load .env if exists
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

# BuildKit is required for the persistent apt/pip caches in the Dockerfile.
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
if [[ -z "${BUILDX_BUILDER:-}" ]] && docker buildx inspect desktop-linux >/dev/null 2>&1; then
    export BUILDX_BUILDER=desktop-linux
fi

# Validate Redis credentials
if [[ -z "$REDIS_USER" || -z "$REDIS_PASSWORD" ]]; then
    echo -e "${RED}Error: REDIS_USER and REDIS_PASSWORD must be set in .env${NC}"
    exit 1
fi

# Ask user for environment to run
echo -e "${YELLOW}Select environment:${NC}"
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

# Ask user what action to perform
echo ""
echo -e "${YELLOW}What do you want to do?${NC}"
echo "1) Deploy/Restart all services (stops existing, rebuilds, and starts)"
echo "2) Stop and remove containers of this service only"
echo "3) Deploy without rebuild (faster restart)"
read -rp "Enter your choice [1/2/3]: " ACTION_CHOICE

case "$ACTION_CHOICE" in
    1)
        # Full deployment with rebuild
        log "Stopping Existing Containers for $ENV_NAME Environment"
        stop_live_logger                                                  
        docker compose -f "$COMPOSE_FILE" down 
        
        log "Building and Starting Containers for $ENV_NAME Environment"
        docker compose -f "$COMPOSE_FILE" up -d --build
        
        # Configure Redis ACL
        log "Configuring Redis ACL"
        sleep 2  # Give Redis time to start
        if docker exec -i rajasthan-seed-redis redis-cli \
            ACL SETUSER "$REDIS_USER" on ">$REDIS_PASSWORD" +@all ~*; then
            log "Redis ACL Configured Successfully"
        else
            echo -e "${RED}Redis ACL Configuration Failed${NC}"
            exit 1
        fi
        
        log "Deployment Successful ✓"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        start_live_logger                                                  
        ;;
        
    2)
        # Stop only
        log "Stopping and Removing All Containers for $ENV_NAME Environment"
        stop_live_logger                                                  
        docker compose -f "$COMPOSE_FILE" down
        log "All Containers Stopped Successfully ✓"
        echo ""
        echo "Remaining running containers:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
        
    3)
        # Quick restart without rebuild
        log "Restarting Containers for $ENV_NAME Environment (No Rebuild)"
        stop_live_logger                                                  
        docker compose -f "$COMPOSE_FILE" down
        docker compose -f "$COMPOSE_FILE" up -d
        
        log "Restart Successful ✓"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        start_live_logger                                                  
        ;;
        
    *)
        echo -e "${RED}Invalid choice! Please enter 1, 2, or 3.${NC}"
        exit 1
        ;;
esac
