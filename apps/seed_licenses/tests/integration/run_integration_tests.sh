#!/usr/bin/env bash
set -euo pipefail
chmod +x "$0"

# =============================================================================
# Colors
# =============================================================================
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# =============================================================================
# Styled logging helpers (preserve emojis/colors)
# =============================================================================
log_info()    { echo -e "${BLUE}ℹ️  $*${NC}"; }
log_success() { echo -e "${GREEN}✅ $*${NC}"; }
log_error()   { echo -e "${RED}❌ $*${NC}"; }
log_warn()    { echo -e "${YELLOW}⚠️  $*${NC}"; }

# =============================================================================
# Cross-platform Docker wrapper
# =============================================================================
OS_TYPE="${OSTYPE:-unknown}"
run_docker() {
    if [[ "$OS_TYPE" == msys* || "$OS_TYPE" == cygwin* ]]; then
        MSYS2_ARG_CONV_EXCL="*" \
        MSYS_NO_PATHCONV=1 \
        MSYS2_ENV_CONV_EXCL="*" \
        docker "$@"
    else
        docker "$@"
    fi
}

# Fixed Centralized docker + pytest executor
docker_pytest() {
   
    local test_target="$1"
    local pytest_args="$2"
    
    run_docker exec \
        -w /app \
        -e PYTHONPATH="/app" \
        -e DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE" \
        "$CONTAINER_NAME" \
        pytest "$test_target" $pytest_args
}

# Interactive version
docker_pytest_interactive() {
   
    local test_target="$1"
    local pytest_args="$2"
    
    run_docker exec \
        -w /app \
        -e PYTHONPATH="/app" \
        -e DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE" \
        -it "$CONTAINER_NAME" \
        pytest "$test_target" $pytest_args
}

# =============================================================================
# Configuration
# =============================================================================
CONTAINER_NAME="rajasthan-seed-backend"
TEST_BASE_PATH="apps/seed_licenses/tests/integration"
LOG_DIR="$TEST_BASE_PATH/integration_test_logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MAIN_LOG="${LOG_DIR}/integration_test_run_${TIMESTAMP}.log"
SUMMARY_LOG="${LOG_DIR}/summary_${TIMESTAMP}.log"
FAILED_LOG="${LOG_DIR}/failed_tests_${TIMESTAMP}.log"
SETTINGS_MODULE="config.test_settings"

# Global flag to track if we're in interactive mode
INTERACTIVE_MODE=false

# Portable test file collection (keeps order by name)
TEST_FILES=()
if command -v find >/dev/null 2>&1 && find --version 2>&1 | grep -q GNU; then
    mapfile -t TEST_FILES < <(find "$TEST_BASE_PATH" -maxdepth 1 -type f -name "test_*.py" -printf "%f\n" 2>/dev/null | sort)
else
    # Fallback for macOS and other systems
    while IFS= read -r -d '' file; do
        TEST_FILES+=("$(basename "$file")")
    done < <(find "$TEST_BASE_PATH" -maxdepth 1 -name "test_*.py" -type f -print0 2>/dev/null | sort -z)
fi

# Final fallback
if [ ${#TEST_FILES[@]} -eq 0 ]; then
    for file in "$TEST_BASE_PATH"/test_*.py; do
        [[ -f "$file" ]] && TEST_FILES+=("$(basename "$file")")
    done
    # Sort the array
    IFS=$'\n' TEST_FILES=($(sort <<<"${TEST_FILES[*]}"))
    unset IFS
fi

# =============================================================================
# Test statistics
# =============================================================================
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# =============================================================================
# Functions (style preserved)
# =============================================================================

print_banner() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║        ${CYAN}Integration Test Suite Runner${BLUE}                   ║${NC}"
    echo -e "${BLUE}║        ${YELLOW}Seed License Management System${BLUE}                 ║${NC}"
    echo -e "${BLUE}║        ${MAGENTA}Updated for Blockchain Architecture${BLUE}            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not installed or not in PATH.${NC}"
        exit 1
    fi
}

check_container() {
    echo -e "${YELLOW}🔍 Checking if container '${CONTAINER_NAME}' is running...${NC}"
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
        echo -e "${RED}❌ Container not running. Starting...${NC}"
        docker start "$CONTAINER_NAME" || {
            echo -e "${RED}❌ Failed to start container.${NC}"
            exit 1
        }
        sleep 5
    fi

    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
        echo -e "${RED}❌ Failed to start container.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Container found and running${NC}"
    echo ""
}

create_log_directory() {
    if [ ! -d "$LOG_DIR" ]; then
        mkdir -p "$LOG_DIR"
        echo -e "${YELLOW}📁 Created log directory: ${LOG_DIR}${NC}"
    fi
    echo -e "${BLUE}📋 Logs will be saved to: ${LOG_DIR}${NC}"
    echo ""
}

print_test_header() {
    local test_file=$1
    local test_num=$2
    local total=$3

    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
    printf "${MAGENTA}║ Test File [%d/%d]: %-43s║${NC}\n" "$test_num" "$total" "$test_file"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}"
}

#parser for a pytest log
parse_counts_from_log() {
    local file_log=$1
    local passed=$(grep -oP '\d+(?= passed)' "$file_log" 2>/dev/null | tail -1 || echo 0)
    local failed=$(grep -oP '\d+(?= failed)' "$file_log" 2>/dev/null | tail -1 || echo 0)
    local skipped=$(grep -oP '\d+(?= skipped)' "$file_log" 2>/dev/null | tail -1 || echo 0)
    echo "${passed} ${failed} ${skipped}"
}

# updater for global stats
update_global_stats() {
    local passed=$1 failed=$2 skipped=$3
    TOTAL_TESTS=$((TOTAL_TESTS + passed + failed + skipped))
    PASSED_TESTS=$((PASSED_TESTS + passed))
    FAILED_TESTS=$((FAILED_TESTS + failed))
    SKIPPED_TESTS=$((SKIPPED_TESTS + skipped))
}

run_single_test_file() {
    local test_file=$1
    local test_num=$2
    local total=$3
    local test_path="/app/${TEST_BASE_PATH}/${test_file}"
    local file_log="${LOG_DIR}/${test_file%.py}_${TIMESTAMP}.log"

    print_test_header "$test_file" "$test_num" "$total"
    echo -e "${CYAN}📝 Running: ${test_path}${NC}"
    echo -e "${BLUE}📄 Log: ${file_log}${NC}"
    echo ""
    
    # Run the test and capture output
    docker_pytest "$test_path" "-v --tb=short --color=yes -ra" 2>&1 | tee "$file_log"
    
    local exit_code=${PIPESTATUS[0]}

    # Parse and update stats
    read passed failed skipped < <(parse_counts_from_log "$file_log")
    update_global_stats "${passed:-0}" "${failed:-0}" "${skipped:-0}"

    echo ""
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ PASSED: ${test_file}${NC}"
        echo -e "${GREEN}   Passed: ${passed:-0} | Failed: ${failed:-0} | Skipped: ${skipped:-0}${NC}"
    else
        echo -e "${RED}❌ FAILED: ${test_file}${NC}"
        echo -e "${RED}   Passed: ${passed:-0} | Failed: ${failed:-0} | Skipped: ${skipped:-0}${NC}"
    fi
    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
    echo ""

    return $exit_code
}

run_all_tests() {
    local total_files=${#TEST_FILES[@]}
    local failed_files=()

    echo -e "${CYAN}🚀 Starting integration test suite...${NC}"
    echo -e "${BLUE}Total test files to run: ${total_files}${NC}"
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""

    for i in "${!TEST_FILES[@]}"; do
        local test_file="${TEST_FILES[$i]}"
        local test_num=$((i + 1))

        if ! run_single_test_file "$test_file" "$test_num" "$total_files"; then
            failed_files+=("$test_file")
        fi

        # Delay to keep output readable
        if [ $test_num -lt $total_files ]; then
            echo -e "${YELLOW}⏳ Waiting 2 seconds before next test file...${NC}"
            sleep 2
            echo ""
        fi
    done

    # Return number of failed files
    return ${#failed_files[@]}
}

run_failed_tests() {
    echo -e "${CYAN}Running only failed tests...${NC}"
    
    if [ "$INTERACTIVE_MODE" = true ]; then
        # In interactive mode, run with proper logging
        local failed_log="${LOG_DIR}/failed_tests_interactive_${TIMESTAMP}.log"
        echo -e "${BLUE}📄 Log: ${failed_log}${NC}"
        echo ""
        docker_pytest_interactive "/app/${TEST_BASE_PATH}" "--lf -v --tb=short --color=yes" 2>&1 | tee "$failed_log"
    else
        docker_pytest "/app/${TEST_BASE_PATH}" "--lf -v --tb=short --color=yes" 2>&1 | tee "$FAILED_LOG"
    fi
}

capture_failed_tests() {
    docker_pytest "/app/${TEST_BASE_PATH}" "--lf -vv --tb=long --showlocals -r fEX" > "$FAILED_LOG" 2>&1 || true
}

run_debug_tests() {
    echo -e "${CYAN}Running tests with debugging (stop on first failure)...${NC}"
    
    if [ "$INTERACTIVE_MODE" = true ]; then
        local debug_log="${LOG_DIR}/debug_tests_${TIMESTAMP}.log"
        echo -e "${BLUE}📄 Log: ${debug_log}${NC}"
        echo ""
        docker_pytest_interactive "/app/${TEST_BASE_PATH}" "-v -x --pdb --tb=short" 2>&1 | tee "$debug_log"
    else
        docker_pytest "/app/${TEST_BASE_PATH}" "-v -x --pdb --tb=short" 2>&1 | tee "${LOG_DIR}/debug_tests_${TIMESTAMP}.log"
    fi
}

show_test_coverage() {
    echo -e "${YELLOW}📊 Running integration tests with coverage report...${NC}"
    echo ""
    
    # Check if pytest-cov is installed
    if ! run_docker exec "$CONTAINER_NAME" python -c "import pytest_cov" 2>/dev/null; then
        echo -e "${YELLOW}Installing pytest-cov...${NC}"
        run_docker exec "$CONTAINER_NAME" pip install pytest-cov
    fi
    
    local coverage_log="${LOG_DIR}/coverage_integration_${TIMESTAMP}.log"
    
    if [ "$INTERACTIVE_MODE" = true ]; then
        echo -e "${BLUE}📄 Log: ${coverage_log}${NC}"
        echo ""
        docker_pytest_interactive "/app/${TEST_BASE_PATH}" "--cov=apps.seed_licenses --cov-report=term-missing --cov-report=html:htmlcov_integration -v" 2>&1 | tee "$coverage_log"
    else
        docker_pytest "/app/${TEST_BASE_PATH}" "--cov=apps.seed_licenses --cov-report=term-missing --cov-report=html:htmlcov_integration -v" 2>&1 | tee "$coverage_log"
    fi
}

run_specific_test_file() {
    echo -e "${CYAN}Available test files:${NC}"
    for i in "${!TEST_FILES[@]}"; do
        echo "  $((i+1)). ${TEST_FILES[$i]}"
    done
    echo ""
    read -p "Enter test file number [1-${#TEST_FILES[@]}]: " choice

    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#TEST_FILES[@]}" ]; then
        local test_file="${TEST_FILES[$((choice-1))]}"
        local file_log="${LOG_DIR}/${test_file%.py}_interactive_${TIMESTAMP}.log"
        
        echo -e "${CYAN}Running: ${test_file}${NC}"
        echo -e "${BLUE}📄 Log: ${file_log}${NC}"
        echo ""
        
        docker_pytest_interactive "/app/${TEST_BASE_PATH}/${test_file}" "-v --tb=short --color=yes" 2>&1 | tee "$file_log"
    else
        echo -e "${RED}Invalid choice${NC}"
    fi
}

run_specific_test_class() {
    echo "Enter test file and class (e.g., test_license_lifecycle.py::TestCompleteLicenseLifecycle):"
    read test_class
    
    if [ -n "$test_class" ]; then
        local class_log="${LOG_DIR}/class_${test_class//\:\:/_}_interactive_${TIMESTAMP}.log"
        
        echo -e "${CYAN}Running: ${test_class}${NC}"
        echo -e "${BLUE}📄 Log: ${class_log}${NC}"
        echo ""
        
        docker_pytest_interactive "/app/${TEST_BASE_PATH}/${test_class}" "-v --tb=short --color=yes" 2>&1 | tee "$class_log"
    else
        echo -e "${RED}No test class specified${NC}"
    fi
}

list_test_files() {
    echo -e "${CYAN}Integration Test Files:${NC}"
    for i in "${!TEST_FILES[@]}"; do
        echo "  $((i+1)). ${TEST_FILES[$i]}"
    done
}

clean_old_logs() {
    read -p "Delete logs older than how many days? [7]: " days
    days=${days:-7}
    find "$LOG_DIR" -type f -mtime +$days -delete 2>/dev/null || true
    echo -e "${GREEN}Cleaned logs older than $days days${NC}"
}

get_container_logs() {
    echo ""
    echo -e "${YELLOW}📜 Fetching recent container logs...${NC}"
    local container_log="${LOG_DIR}/container_logs_${TIMESTAMP}.log"

    docker logs --tail 200 "$CONTAINER_NAME" > "$container_log" 2>&1 || true
    echo -e "${BLUE}Container logs saved to: ${container_log}${NC}"
}

# =============================================================================
# Summary (style preserved)
# =============================================================================
print_summary() {
    local total_failed=$1

    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║                    ${CYAN}TEST SUMMARY${BLUE}                          ║${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo -e "${CYAN}📊 Overall Statistics:${NC}"
    echo -e "   Total Tests:    ${TOTAL_TESTS}"
    echo -e "   ${GREEN}✅ Passed:       ${PASSED_TESTS}${NC}"
    echo -e "   ${RED}❌ Failed:       ${FAILED_TESTS}${NC}"
    echo -e "   ${YELLOW}⏭️  Skipped:      ${SKIPPED_TESTS}${NC}"
    echo ""

    if [ $TOTAL_TESTS -gt 0 ]; then
        local success_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
        echo -e "   ${CYAN}Success Rate:   ${success_rate}%${NC}"
        echo ""
    fi

    echo -e "${CYAN}📁 Test Files Summary:${NC}"
    echo -e "   Total Files:    ${#TEST_FILES[@]}"
    echo -e "   ${GREEN}Passed Files:   $((${#TEST_FILES[@]} - total_failed))${NC}"
    echo -e "   ${RED}Failed Files:   ${total_failed}${NC}"
    echo ""

    if [ $total_failed -eq 0 ] && [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                                                            ║${NC}"
        echo -e "${GREEN}║            🎉 ALL INTEGRATION TESTS PASSED! 🎉            ║${NC}"
        echo -e "${GREEN}║                                                            ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    else
        echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║                                                            ║${NC}"
        echo -e "${RED}║              ⚠️  SOME TESTS FAILED ⚠️                      ║${NC}"
        echo -e "${RED}║                                                            ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${YELLOW}📋 Failed Test Details:${NC}"
        echo ""

        for test_file in "${TEST_FILES[@]}"; do
            local file_pattern="${test_file%.py}_*${TIMESTAMP}.log"
            local matching_logs=($(find "$LOG_DIR" -name "$file_pattern" 2>/dev/null))
            
            for file_log in "${matching_logs[@]}"; do
                if [ -f "$file_log" ]; then
                    local failed_count=$(grep -oP '\d+(?= failed)' "$file_log" 2>/dev/null | tail -1 || echo 0)
                    if [ -n "$failed_count" ] && [ "$failed_count" -gt 0 ]; then
                        echo -e "${RED}   ❌ ${test_file}: ${failed_count} test(s) failed${NC}"
                        grep "FAILED" "$file_log" 2>/dev/null | head -5 | sed 's/^/      /' || true
                        echo ""
                        break
                    fi
                fi
            done
        done
    fi

    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}📂 Log Files:${NC}"
    echo -e "   Main Log:       ${MAIN_LOG}"
    echo -e "   Failed Details: ${FAILED_LOG}"
    echo -e "   Summary:        ${SUMMARY_LOG}"
    echo -e "   Individual:     ${LOG_DIR}/*_${TIMESTAMP}.log"
    echo ""

    if [ $total_failed -gt 0 ] || [ $FAILED_TESTS -gt 0 ]; then
        echo -e "${YELLOW}💡 Quick Commands:${NC}"
        echo -e "   Re-run failed tests:"
        echo -e "   ${CYAN}docker exec -it ${CONTAINER_NAME} pytest /app/${TEST_BASE_PATH} --lf -v${NC}"
        echo ""
        echo -e "   Run specific test file:"
        echo -e "   ${CYAN}docker exec -it ${CONTAINER_NAME} pytest /app/${TEST_BASE_PATH}/[test_file] -v${NC}"
        echo ""
        echo -e "   Run with debugging:"
        echo -e "   ${CYAN}docker exec -it ${CONTAINER_NAME} pytest /app/${TEST_BASE_PATH} --lf -v -x --pdb${NC}"
        echo ""
    fi

    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

save_summary() {
    {
        echo "Integration Test Run Summary"
        echo "Timestamp: $(date)"
        echo "======================================"
        echo ""
        echo "Overall Statistics:"
        echo "  Total Tests: $TOTAL_TESTS"
        echo "  Passed: $PASSED_TESTS"
        echo "  Failed: $FAILED_TESTS"
        echo "  Skipped: $SKIPPED_TESTS"
        echo ""
        echo "Test Files:"
        for test_file in "${TEST_FILES[@]}"; do
            echo "  - $test_file"
        done
        echo ""
        echo "Log Directory: $LOG_DIR"
    } > "$SUMMARY_LOG"
}

interactive_menu() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              Integration Test Options                      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "1) Run all integration tests (default)"
    echo "2) Run with coverage report"
    echo "3) Run only failed tests"
    echo "4) Run specific test file"
    echo "5) Run specific test class"
    echo "6) Run with debugging (stops on first failure)"
    echo "7) List all test files"
    echo "8) Clean old logs"
    echo "9) Exit"
    echo ""
    read -p "Enter choice [1-9]: " choice

    case $choice in
        1|"")
            run_all_tests
            local failed_count=$?
            save_summary
            print_summary $failed_count
            ;;
        2)
            show_test_coverage
            ;;
        3)
            run_failed_tests
            ;;
        4)
            run_specific_test_file
            ;;
        5)
            run_specific_test_class
            ;;
        6)
            run_debug_tests
            ;;
        7)
            list_test_files
            ;;
        8)
            clean_old_logs
            ;;
        9)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            ;;
    esac
}

# =============================================================================
# Main Script
# =============================================================================

main() {
    print_banner
    require_docker
    check_container
    create_log_directory

    case "${1:-}" in
        --coverage|-c)
            show_test_coverage
            exit $?
            ;;
        --failed|-f)
            run_failed_tests
            exit $?
            ;;
        --interactive|-i)
            interactive_menu
            exit 0
            ;;
        --list|-l)
            list_test_files
            exit 0
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --coverage, -c      Run tests with coverage report"
            echo "  --failed, -f        Run only previously failed tests"
            echo "  --interactive, -i   Interactive mode with menu"
            echo "  --list, -l          List all test files"
            echo "  --help, -h          Show this help message"
            echo ""
            exit 0
            ;;
        *)
            # Default: run all tests
            run_all_tests
            local failed_count=$?
            save_summary
            print_summary $failed_count
            ;;
    esac
}

# Run main function
main "$@"
