#!/bin/bash
set -e
chmod +x "$0"

echo "🎯 Choose test type:"
echo "1) K6 Stress Test"
echo "2) Locust Stress Test"
read -p "Enter choice (1-2): " choice

case $choice in
    1)
        TEST_TYPE="k6"
        TEST_FILE="stress-test.js"
        REPORT_FILE="stress_report.html"
        ;;
    2)
        TEST_TYPE="locust"
        TEST_FILE="locustfile.py"
        REPORT_FILE="locust_report.html"
        ;;
    *)
        echo "❌ Invalid choice!"
        exit 1
        ;;
esac

# 🧾 Load environment variables
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
elif [ -f "../.env" ]; then
  export $(grep -v '^#' ../.env | xargs)
else
  echo "❌ .env file not found!"
  exit 1
fi

USERS=${1:-500}
SPAWN_RATE=${2:-50}
RUNTIME=${3:-1m}

if [ -z "$BASE_URL" ]; then
  echo "❌ BASE_URL is not defined in .env file!"
  exit 1
fi

# Default RPC URLs if not set
if [ -z "$RPC_URLS" ]; then
  RPC_URLS="http://host.docker.internal:8545,http://host.docker.internal:8546,http://host.docker.internal:8547,http://host.docker.internal:8548"
  echo "⚙️  Using default RPC_URLS: $RPC_URLS"
fi

echo "🚀 Starting Blockchain License System Stress Test..."
echo "Test Type: $TEST_TYPE"
echo "Users: $USERS | Spawn Rate: $SPAWN_RATE | Runtime: $RUNTIME"
echo "Target Host: $BASE_URL"
echo "RPC Nodes:"
IFS=',' read -ra RPCS <<< "$RPC_URLS"
for url in "${RPCS[@]}"; do
  echo "   • $url"
done
echo "-------------------------------------"

# Detect if running inside Docker container
if [ "$PWD" = "/app" ] || [ -f "/.dockerenv" ]; then
    IN_DOCKER=true
    WORK_DIR="."
    REPORT_DIR="./reports"
else
    IN_DOCKER=false
    WORK_DIR="stress_test"
    REPORT_DIR="stress_test/reports"
fi

# Timestamped report
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
mkdir -p "$REPORT_DIR"
REPORT_PATH="${REPORT_DIR}/${TEST_TYPE}_${TIMESTAMP}.html"

# Detect project root (directory with manage.py or git) - only if not in Docker
if [ "$IN_DOCKER" = false ]; then
    PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
fi

# ---------------------- K6 TEST ---------------------- #
if [ "$TEST_TYPE" = "k6" ]; then
    echo "📊 Running K6 stress test..."
    
    if [ "$IN_DOCKER" = true ]; then
        # Already in Docker, just run k6
        echo "Command: k6 run $TEST_FILE"
        BASE_URL="$BASE_URL" RPC_URLS="$RPC_URLS" k6 run "$TEST_FILE"
    else
        # Running locally
        echo "Command: k6 run $WORK_DIR/$TEST_FILE"
        
        if ! command -v k6 &>/dev/null; then
            echo "🐳 k6 not found locally — running via Docker..."
            
            docker run --rm -i \
                -v "$PROJECT_ROOT":/scripts \
                -w /scripts/stress_test \
                -e BASE_URL="$BASE_URL" \
                -e RPC_URLS="$RPC_URLS" \
                grafana/k6 run "$TEST_FILE"
        else
            BASE_URL="$BASE_URL" RPC_URLS="$RPC_URLS" k6 run "$WORK_DIR/$TEST_FILE"
        fi
    fi

    K6_EXIT_CODE=$?
    [ $K6_EXIT_CODE -eq 0 ] && echo "✅ K6 stress test completed!" || echo "❌ K6 test failed"

# ---------------------- LOCUST TEST ---------------------- #
else
    echo "📊 Running Locust stress test..."
    
    if [ "$IN_DOCKER" = true ]; then
        # Already in Docker, just run locust
        echo "Command: locust -f $TEST_FILE --host=\"$BASE_URL\" --users $USERS --spawn-rate $SPAWN_RATE --run-time $RUNTIME --headless --html $REPORT_PATH"
        
        locust -f "$TEST_FILE" \
            --host="$BASE_URL" \
            --users "$USERS" \
            --spawn-rate "$SPAWN_RATE" \
            --run-time "$RUNTIME" \
            --headless \
            --html "$REPORT_PATH"
    else
        # Running locally
        echo "Command: locust -f $WORK_DIR/$TEST_FILE --host=\"$BASE_URL\" --users $USERS --spawn-rate $SPAWN_RATE --run-time $RUNTIME --headless --html $REPORT_PATH"
        
        if ! command -v locust &>/dev/null; then
            echo "🐳 Locust not found locally — running via Docker..."

            # Prevent Git Bash / MSYS from rewriting POSIX paths to Windows paths
            if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
                MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" docker run --rm -i \
                    -v "$PROJECT_ROOT":/mnt/project \
                    -w /mnt/project/stress_test \
                    -e PYTHONPATH="/mnt/project" \
                    -e BASE_URL="$BASE_URL" \
                    -e RPC_URLS="$RPC_URLS" \
                    stress_test-stress_tester \
                    -f "$TEST_FILE" \
                    --host="$BASE_URL" \
                    --users "$USERS" \
                    --spawn-rate "$SPAWN_RATE" \
                    --run-time "$RUNTIME" \
                    --headless \
                    --html "$REPORT_PATH"
            else
                docker run --rm -i \
                    -v "$PROJECT_ROOT":/mnt/project \
                    -w /mnt/project/stress_test \
                    -e PYTHONPATH="/mnt/project" \
                    -e BASE_URL="$BASE_URL" \
                    -e RPC_URLS="$RPC_URLS" \
                    stress_test-stress_tester \
                    -f "$TEST_FILE" \
                    --host="$BASE_URL" \
                    --users "$USERS" \
                    --spawn-rate "$SPAWN_RATE" \
                    --run-time "$RUNTIME" \
                    --headless \
                    --html "$REPORT_PATH"
            fi
        else
            locust -f "$WORK_DIR/$TEST_FILE" \
                --host="$BASE_URL" \
                --users "$USERS" \
                --spawn-rate "$SPAWN_RATE" \
                --run-time "$RUNTIME" \
                --headless \
                --html "$REPORT_PATH"
        fi
    fi

    LOCUST_EXIT_CODE=$?

    # Custom report branding
    if [ -f "$REPORT_PATH" ]; then
        PROJECT_NAME="🌿 Blockchain License System Stress Test"
        DATE_GENERATED="$(date +"%a, %b %d, %Y %I:%M:%S %p")"
        sed -i "s|Locust Test Report|$PROJECT_NAME|g" "$REPORT_PATH" || true
        sed -i "0,/<h3>.*<\/h3>/s|<h3>.*<\/h3>|<h3 style='text-align:center;color:#2E8B57;'>$PROJECT_NAME</h3><p style='text-align:center;font-style:italic;'>$DATE_GENERATED</p>|" "$REPORT_PATH" || true
    fi

    [ $LOCUST_EXIT_CODE -eq 0 ] && echo "✅ Locust stress test completed!" || echo "❌ Locust test failed"
fi

echo "-------------------------------------"
echo "📊 HTML report saved as: $REPORT_PATH"
echo "💡 Open it in browser to view results."
exit 0