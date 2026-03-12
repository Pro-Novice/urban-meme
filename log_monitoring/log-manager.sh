#!/bin/bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

CONTAINER_PID_FILE="./.container_logger.pid"
TERMINAL_MARKER_FILE="./.terminal_logger.active"

mkdir -p ./logs


if [[ -n "$PROMPT_COMMAND" && "$PROMPT_COMMAND" == *TERMINAL_LOG_FILE* ]]; then
    touch "$TERMINAL_MARKER_FILE"
else
    rm -f "$TERMINAL_MARKER_FILE"
    unset TERMINAL_LOG_FILE   
fi

log() {
    echo -e "${GREEN}####################################################################\n   $1\n####################################################################${NC}"
}

clean_log() {
    local file="$1"
    if [[ -f "$file" ]]; then
        
        sed -u -r 's/\x1B\[[0-9;?]*[ -\/]*[@-~]//g; s/\r/\n/g' "$file" 2>/dev/null || true
    fi
}

detect_compose_file() {
    if [[ -f "docker-compose.local.yml" && -f "docker-compose.yaml" ]]; then
        echo -e "${YELLOW}Select environment:${NC}"
        echo "1) Local (with Postgres)"
        echo "2) Server (no Postgres)"
        read -rp "Enter your choice [1 or 2]: " ENV_CHOICE
        if [[ "$ENV_CHOICE" == "1" ]]; then
            COMPOSE_FILE="docker-compose.local.yml"
        elif [[ "$ENV_CHOICE" == "2" ]]; then
            COMPOSE_FILE="docker-compose.yaml"
        else
            echo -e "${RED}Invalid choice.${NC}"
            exit 1
        fi
    elif [[ -f "docker-compose.local.yml" ]]; then
        COMPOSE_FILE="docker-compose.local.yml"
    elif [[ -f "docker-compose.yaml" ]]; then
        COMPOSE_FILE="docker-compose.yaml"
    else
        echo -e "${RED}No compose file found.${NC}"
        exit 1
    fi
}

start_container_logs() {
    # Always stop existing first
    if [[ -f "$CONTAINER_PID_FILE" ]]; then
        while IFS= read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < "$CONTAINER_PID_FILE"
        rm -f "$CONTAINER_PID_FILE"
    fi

    detect_compose_file

    CURRENT_LOG="./logs/container_$(date +"%Y-%m-%d").txt"
    > "$CURRENT_LOG"
    echo "========================================================================" >> "$CURRENT_LOG"
    echo " Container logging started : $(date)"                                      >> "$CURRENT_LOG"
    echo " Compose file              : $COMPOSE_FILE"                                >> "$CURRENT_LOG"
    echo "========================================================================" >> "$CURRENT_LOG"

    START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    
    mapfile -t CONTAINERS < <(docker compose -f "$COMPOSE_FILE" ps --format "{{.Name}}" 2>/dev/null)

    if [[ ${#CONTAINERS[@]} -eq 0 ]]; then
        echo -e "${YELLOW}No running containers found for $COMPOSE_FILE.${NC}"
        return
    fi

    for CONTAINER in "${CONTAINERS[@]}"; do
        if [[ -n "$CONTAINER" ]]; then
            echo " Tracking: $CONTAINER" >> "$CURRENT_LOG"
            docker logs "$CONTAINER" -f --since "$START_TIME" --timestamps 2>&1 \
            | sed -u "s/^/[$CONTAINER] /" \
            | sed -u -r 's/\x1B\[[0-9;?]*[ -\/]*[@-~]//g; s/\r/\n/g' >> "$CURRENT_LOG" &
            echo $! >> "$CONTAINER_PID_FILE"
        fi
    done

    echo "========================================================================" >> "$CURRENT_LOG"
    clean_log "$CURRENT_LOG"
    echo -e "${GREEN}Container logging started → $CURRENT_LOG${NC}"
    echo -e "${CYAN}Tracking: ${CONTAINERS[*]}${NC}"
}

stop_container_logs() {
    if [[ -f "$CONTAINER_PID_FILE" ]]; then
        while IFS= read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < "$CONTAINER_PID_FILE"
        rm -f "$CONTAINER_PID_FILE"
        echo -e "${GREEN}Container logging stopped.${NC}"
    else
        echo -e "${YELLOW}Container logging is not running.${NC}"
    fi
}

start_terminal_logs() {
    # Always kill any existing PROMPT_COMMAND first 
    unset PROMPT_COMMAND
    unset TERMINAL_LOG_FILE
    rm -f "$TERMINAL_MARKER_FILE"

    CURRENT_LOG="./logs/terminal_$(date +"%Y-%m-%d").txt"
    > "$CURRENT_LOG"
    echo "========================================================================" >> "$CURRENT_LOG"
    echo " Terminal logging started  : $(date)"                                      >> "$CURRENT_LOG"
    echo "========================================================================" >> "$CURRENT_LOG"

    export TERMINAL_LOG_FILE="$CURRENT_LOG"
    export PROMPT_COMMAND='_last_cmd=$(history 1 | sed -u -r "s/\x1B\[[0-9;?]*[ -\/]*[@-~]//g; s/\r/\n/g"); echo "[$(date +"%Y-%m-%d %H:%M:%S")] $_last_cmd" >> "$TERMINAL_LOG_FILE"'
    touch "$TERMINAL_MARKER_FILE"

    echo -e "${GREEN}Terminal logging started → $CURRENT_LOG${NC}"
    echo -e "${CYAN}Every command you run will be recorded.${NC}"
    echo -e "${CYAN}Run: source log-manager.sh → option 5 to stop.${NC}"
}

stop_terminal_logs() {
    # Always unset regardless of marker file state
    unset PROMPT_COMMAND
    unset TERMINAL_LOG_FILE
    rm -f "$TERMINAL_MARKER_FILE"
    echo -e "${GREEN}Terminal logging stopped.${NC}"
}

show_status() {
    echo ""
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}   Log Tracking Status${NC}"
    echo -e "${CYAN}================================================${NC}"

    if [[ -f "$CONTAINER_PID_FILE" ]]; then
        ALIVE=0
        while IFS= read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                ALIVE=$((ALIVE + 1))
            fi
        done < "$CONTAINER_PID_FILE"
        if [[ $ALIVE -gt 0 ]]; then
            echo -e "  Container logs : ${GREEN}RUNNING${NC} ($ALIVE watchers active)"
            echo    "  Log file       : ./logs/container_$(date +"%Y-%m-%d").txt"
        else
            echo -e "  Container logs : ${RED}STOPPED${NC} (stale PID file)"
            rm -f "$CONTAINER_PID_FILE"
        fi
    else
        echo -e "  Container logs : ${RED}NOT RUNNING${NC}"
    fi

   
    if [[ -n "$PROMPT_COMMAND" && "$PROMPT_COMMAND" == *TERMINAL_LOG_FILE* ]]; then
        echo -e "  Terminal logs  : ${GREEN}RUNNING${NC}"
        echo    "  Log file       : $TERMINAL_LOG_FILE"
    else
        echo -e "  Terminal logs  : ${RED}NOT RUNNING${NC}"
    fi

    if [[ -f "./.live_logger.pid" ]]; then
       
        ALIVE=0
        while IFS= read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                ALIVE=$((ALIVE + 1))
            fi
        done < "./.live_logger.pid"
        if [[ $ALIVE -gt 0 ]]; then
            echo -e "  Deploy logger  : ${GREEN}RUNNING${NC} ($ALIVE watchers) <- docker-manage.sh"
        else
            echo -e "  Deploy logger  : ${RED}NOT RUNNING${NC}"
        fi
    else
        echo -e "  Deploy logger  : ${RED}NOT RUNNING${NC}"
    fi

    echo -e "${CYAN}================================================${NC}"
    echo ""
}

# Main menu
echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}   Log Manager${NC}"
echo -e "${CYAN}================================================${NC}"
echo "  1) Start container logs only"
echo "  2) Start terminal logs only"
echo "  3) Start both (container + terminal)"
echo "  4) Stop container logs"
echo "  5) Stop terminal logs"
echo "  6) Stop all logs (container + terminal only)"
echo "  7) Status"
echo "  8) Exit"
echo -e "${CYAN}================================================${NC}"
echo ""
read -rp "Enter your choice [1-8]: " CHOICE

case "$CHOICE" in
    1) log "Starting Container Logs";       start_container_logs ;;
    2) log "Starting Terminal Logs";        start_terminal_logs ;;
    3) log "Starting Container + Terminal"; start_container_logs; start_terminal_logs ;;
    4) log "Stopping Container Logs";       stop_container_logs ;;
    5) log "Stopping Terminal Logs";        stop_terminal_logs ;;
    6)
        log "Stopping All Logs (Container + Terminal)"
        stop_container_logs
        stop_terminal_logs
        ;;
    
    7) show_status ;;
    8) echo "Exiting."; exit 0 ;;
    *) echo -e "${RED}Invalid choice.${NC}"; exit 1 ;;
esac