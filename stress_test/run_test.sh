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

# Timestamped report
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
REPORT_DIR="./reports"
mkdir -p "$REPORT_DIR"
REPORT_PATH="${REPORT_DIR}/${TEST_TYPE}_${TIMESTAMP}.html"

# ---------------------- K6 TEST ---------------------- #
if [ "$TEST_TYPE" = "k6" ]; then
    echo "📊 Running K6 stress test..."
    echo "Command: k6 run $TEST_FILE"

    # Prefer local k6; fallback to Docker if not found
    if ! command -v k6 &>/dev/null; then
        echo "🐳 k6 not found locally — running via Docker..."
        
        # Detect correct mount path dynamically
        if [ -f "stress_test/$TEST_FILE" ]; then
            SCRIPT_DIR="$(pwd)/stress_test"
        else
            SCRIPT_DIR="$(pwd)"
        fi
        
        docker run --rm -i \
          -v "$SCRIPT_DIR":/scripts \
          -w /scripts \
          -e BASE_URL="$BASE_URL" \
          -e RPC_URLS="$RPC_URLS" \
          grafana/k6 run "$TEST_FILE"
    else
        BASE_URL="$BASE_URL" RPC_URLS="$RPC_URLS" \
        k6 run "$TEST_FILE"
    fi

    K6_EXIT_CODE=$?

    if [ $K6_EXIT_CODE -eq 0 ]; then
        echo "✅ K6 stress test completed successfully"
    else
        echo "❌ K6 stress test failed with exit code: $K6_EXIT_CODE"
    fi

# ---------------------- LOCUST TEST ---------------------- #
else
    echo "📊 Running Locust stress test..."
    echo "Command: locust -f $TEST_FILE --host=\"$BASE_URL\" --users $USERS --spawn-rate $SPAWN_RATE --run-time $RUNTIME --headless --html $REPORT_PATH"

    if ! command -v locust &>/dev/null; then
        echo "🐳 Locust not found locally — running via Docker..."
        
        # Detect correct mount path dynamically
        if [ -f "stress_test/$TEST_FILE" ]; then
            SCRIPT_DIR="$(pwd)/stress_test"
        else
            SCRIPT_DIR="$(pwd)"
        fi

        docker run --rm -i \
          -v "$SCRIPT_DIR":/mnt/locust \
          -w /mnt/locust \
          -e BASE_URL="$BASE_URL" \
          -e RPC_URLS="$RPC_URLS" \
          locustio/locust -f "$TEST_FILE" \
          --host="$BASE_URL" \
          --users "$USERS" \
          --spawn-rate "$SPAWN_RATE" \
          --run-time "$RUNTIME" \
          --headless \
          --html "$REPORT_PATH"
    else
        locust -f "$TEST_FILE" \
          --host="$BASE_URL" \
          --users "$USERS" \
          --spawn-rate "$SPAWN_RATE" \
          --run-time "$RUNTIME" \
          --headless \
          --html "$REPORT_PATH"
    fi

    LOCUST_EXIT_CODE=$?

    # Custom report header
    if [ -f "$REPORT_PATH" ]; then
      PROJECT_NAME="🌿 Blockchain License System Stress Test"
      DATE_GENERATED="$(date +"%a, %b %d, %Y %I:%M:%S %p")"
      sed -i "s|Locust Test Report|$PROJECT_NAME|g" "$REPORT_PATH" || true
      sed -i "0,/<h3>.*<\/h3>/s|<h3>.*<\/h3>|<h3 style='text-align:center;color:#2E8B57;'>$PROJECT_NAME</h3><p style='text-align:center;font-style:italic;'>Generated on: $DATE_GENERATED</p>|" "$REPORT_PATH" || true
    fi

    if [ $LOCUST_EXIT_CODE -eq 0 ]; then
        echo "✅ Locust stress test completed successfully"
    else
        echo "❌ Locust stress test failed with exit code: $LOCUST_EXIT_CODE"
    fi
fi

echo "-------------------------------------"
echo "✅ $TEST_TYPE stress test completed!"
echo "📊 HTML report saved as: $REPORT_PATH"
echo "💡 Open it in your browser to view the performance graphs."

exit 0
