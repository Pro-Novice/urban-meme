#!/bin/bash

# =============================================================================
# Integration Test Runner for Seed License System
# =============================================================================

# Configuration
CONTAINER_NAME="rajasthan-seed-backend"  # Change this to match your container name
TEST_BASE_PATH="apps/seed_licenses/tests/integration"
LOG_DIR="integration_test_logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MAIN_LOG="${LOG_DIR}/integration_test_run_${TIMESTAMP}.log"
SUMMARY_LOG="${LOG_DIR}/summary_${TIMESTAMP}.log"
FAILED_LOG="${LOG_DIR}/failed_tests_${TIMESTAMP}.log"

# Test files in order
TEST_FILES=(
    "test_license_lifecycle.py"
    "test_multiple_licenses.py"
    "test_license_updates.py"
    "test_license_verification.py"
    "test_error_scenarios.py"
    "test_concurrent_operations.py"
    "test_system_state.py"
)

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Test statistics
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# =============================================================================
# Functions
# =============================================================================

print_banner() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║        ${CYAN}Integration Test Suite Runner${BLUE}                   ║${NC}"
    echo -e "${BLUE}║        ${YELLOW}Seed License Management System${BLUE}                 ║${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_container() {
    echo -e "${YELLOW}🔍 Checking if container '${CONTAINER_NAME}' is running...${NC}"
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${RED}❌ Error: Container '${CONTAINER_NAME}' is not running${NC}"
        echo -e "${YELLOW}Available containers:${NC}"
        docker ps --format "table {{.Names}}\t{{.Status}}"
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
    echo -e "${MAGENTA}║ Test File [$test_num/$total]: $(printf '%-43s' "$test_file")║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}"
}

run_single_test_file() {
    local test_file=$1
    local test_num=$2
    local total=$3
    local test_path="${TEST_BASE_PATH}/${test_file}"
    local file_log="${LOG_DIR}/${test_file%.py}_${TIMESTAMP}.log"
    
    print_test_header "$test_file" "$test_num" "$total"
    echo -e "${CYAN}📝 Running: ${test_path}${NC}"
    echo -e "${BLUE}📄 Log: ${file_log}${NC}"
    echo ""
    
    # Run the test and capture output
    docker exec $CONTAINER_NAME pytest "$test_path" \
        -v \
        --tb=short \
        --color=yes \
        -ra \
        2>&1 | tee "$file_log"
    
    local exit_code=${PIPESTATUS[0]}
    
    # Parse test results from the log
    local passed=$(grep -oP '\d+(?= passed)' "$file_log" | tail -1)
    local failed=$(grep -oP '\d+(?= failed)' "$file_log" | tail -1)
    local skipped=$(grep -oP '\d+(?= skipped)' "$file_log" | tail -1)
    
    # Update statistics
    TOTAL_TESTS=$((TOTAL_TESTS + ${passed:-0} + ${failed:-0} + ${skipped:-0}))
    PASSED_TESTS=$((PASSED_TESTS + ${passed:-0}))
    FAILED_TESTS=$((FAILED_TESTS + ${failed:-0}))
    SKIPPED_TESTS=$((SKIPPED_TESTS + ${skipped:-0}))
    
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
        
        run_single_test_file "$test_file" "$test_num" "$total_files"
        
        if [ $? -ne 0 ]; then
            failed_files+=("$test_file")
        fi
        
        # Add delay between test files
        if [ $test_num -lt $total_files ]; then
            echo -e "${YELLOW}⏳ Waiting 2 seconds before next test file...${NC}"
            sleep 2
            echo ""
        fi
    done
    
    return ${#failed_files[@]}
}

capture_failed_tests() {
    echo ""
    echo -e "${YELLOW}📝 Capturing detailed information for failed tests...${NC}"
    
    # Run all tests again but only failed ones with maximum detail
    docker exec $CONTAINER_NAME pytest "${TEST_BASE_PATH}" \
        --lf \
        -vv \
        --tb=long \
        --showlocals \
        -r fEX \
        2>&1 > "$FAILED_LOG"
    
    echo -e "${BLUE}Failed tests details saved to: ${FAILED_LOG}${NC}"
}

print_summary() {
    local total_failed=$1
    
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║                    ${CYAN}TEST SUMMARY${BLUE}                          ║${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Overall statistics
    echo -e "${CYAN}📊 Overall Statistics:${NC}"
    echo -e "   Total Tests:    ${TOTAL_TESTS}"
    echo -e "   ${GREEN}✅ Passed:       ${PASSED_TESTS}${NC}"
    echo -e "   ${RED}❌ Failed:       ${FAILED_TESTS}${NC}"
    echo -e "   ${YELLOW}⏭️  Skipped:      ${SKIPPED_TESTS}${NC}"
    echo ""
    
    # Calculate success rate
    if [ $TOTAL_TESTS -gt 0 ]; then
        local success_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
        echo -e "   ${CYAN}Success Rate:   ${success_rate}%${NC}"
        echo ""
    fi
    
    # Test files summary
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
        
        # Show failed test summary
        for test_file in "${TEST_FILES[@]}"; do
            local file_log="${LOG_DIR}/${test_file%.py}_${TIMESTAMP}.log"
            if [ -f "$file_log" ]; then
                local failed_count=$(grep -oP '\d+(?= failed)' "$file_log" | tail -1)
                if [ -n "$failed_count" ] && [ "$failed_count" -gt 0 ]; then
                    echo -e "${RED}   ❌ ${test_file}: ${failed_count} test(s) failed${NC}"
                    grep "FAILED" "$file_log" | head -5 | sed 's/^/      /'
                    echo ""
                fi
            fi
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
        echo -e "   ${CYAN}docker exec -it ${CONTAINER_NAME} pytest ${TEST_BASE_PATH} --lf -v${NC}"
        echo ""
        echo -e "   Run specific test file:"
        echo -e "   ${CYAN}docker exec -it ${CONTAINER_NAME} pytest ${TEST_BASE_PATH}/[test_file] -v${NC}"
        echo ""
        echo -e "   Run with debugging:"
        echo -e "   ${CYAN}docker exec -it ${CONTAINER_NAME} pytest ${TEST_BASE_PATH} --lf -v -x --pdb${NC}"
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

show_test_coverage() {
    echo -e "${YELLOW}📊 Running integration tests with coverage report...${NC}"
    echo ""
    
    docker exec $CONTAINER_NAME pytest "${TEST_BASE_PATH}" \
        --cov=apps.seed_licenses \
        --cov-report=term-missing \
        --cov-report=html:htmlcov_integration \
        -v \
        2>&1 | tee "${LOG_DIR}/coverage_integration_${TIMESTAMP}.log"
}

run_specific_test_file() {
    echo -e "${CYAN}Available test files:${NC}"
    for i in "${!TEST_FILES[@]}"; do
        echo "  $((i+1)). ${TEST_FILES[$i]}"
    done
    echo ""
    read -p "Enter test file number [1-${#TEST_FILES[@]}]: " choice
    
    if [ "$choice" -ge 1 ] && [ "$choice" -le "${#TEST_FILES[@]}" ]; then
        local test_file="${TEST_FILES[$((choice-1))]}"
        local test_path="${TEST_BASE_PATH}/${test_file}"
        
        echo -e "${CYAN}Running: ${test_file}${NC}"
        docker exec -it $CONTAINER_NAME pytest "$test_path" -v --tb=short
    else
        echo -e "${RED}Invalid choice${NC}"
    fi
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
            return 0
            ;;
        2)
            show_test_coverage
            exit 0
            ;;
        3)
            docker exec -it $CONTAINER_NAME pytest "${TEST_BASE_PATH}" --lf -v
            exit 0
            ;;
        4)
            run_specific_test_file
            exit 0
            ;;
        5)
            echo "Enter test file and class (e.g., test_license_lifecycle.py::TestCompleteLicenseLifecycle):"
            read test_class
            docker exec -it $CONTAINER_NAME pytest "${TEST_BASE_PATH}/${test_class}" -v
            exit 0
            ;;
        6)
            docker exec -it $CONTAINER_NAME pytest "${TEST_BASE_PATH}" -v -x --pdb
            exit 0
            ;;
        7)
            echo -e "${CYAN}Integration Test Files:${NC}"
            for i in "${!TEST_FILES[@]}"; do
                echo "  $((i+1)). ${TEST_FILES[$i]}"
            done
            exit 0
            ;;
        8)
            read -p "Delete logs older than how many days? [7]: " days
            days=${days:-7}
            find "$LOG_DIR" -type f -mtime +$days -delete
            echo -e "${GREEN}Cleaned logs older than $days days${NC}"
            exit 0
            ;;
        9)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
}

get_container_logs() {
    echo ""
    echo -e "${YELLOW}📜 Fetching recent container logs...${NC}"
    local container_log="${LOG_DIR}/container_logs_${TIMESTAMP}.log"
    
    docker logs --tail 200 $CONTAINER_NAME > "$container_log" 2>&1
    echo -e "${BLUE}Container logs saved to: ${container_log}${NC}"
}

# =============================================================================
# Main Script
# =============================================================================

main() {
    print_banner
    check_container
    create_log_directory
    
    # Check for command line arguments
    case "$1" in
        --coverage|-c)
            show_test_coverage
            exit $?
            ;;
        --failed|-f)
            docker exec -it $CONTAINER_NAME pytest "${TEST_BASE_PATH}" --lf -v
            exit $?
            ;;
        --interactive|-i)
            interactive_menu
            ;;
        --list|-l)
            echo -e "${CYAN}Integration Test Files:${NC}"
            for i in "${!TEST_FILES[@]}"; do
                echo "  $((i+1)). ${TEST_FILES[$i]}"
            done
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
    esac
    
    # Run all tests
    run_all_tests
    FAILED_COUNT=$?
    
    # Append all logs to main log
    cat ${LOG_DIR}/*_${TIMESTAMP}.log > "$MAIN_LOG" 2>/dev/null
    
    # If tests failed, capture detailed information
    if [ $FAILED_COUNT -gt 0 ] || [ $FAILED_TESTS -gt 0 ]; then
        capture_failed_tests
        get_container_logs
    fi
    
    # Save and print summary
    save_summary
    print_summary $FAILED_COUNT
    
    # Return appropriate exit code
    if [ $FAILED_TESTS -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main "$@"