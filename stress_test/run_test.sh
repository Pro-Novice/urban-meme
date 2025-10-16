#!/bin/bash
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

echo "🚀 Starting Blockchain License System Stress Test..."
echo "Test Type: $TEST_TYPE"
echo "Users: $USERS | Spawn Rate: $SPAWN_RATE | Runtime: $RUNTIME"
echo "Target Host: $BASE_URL"
echo "-------------------------------------"

if [ "$TEST_TYPE" = "k6" ]; then
    echo "📊 Running K6 stress test..."
    echo "Command: k6 run $TEST_FILE"
    
    export BASE_URL="$BASE_URL"
    
    k6 run "$TEST_FILE"
    
    K6_EXIT_CODE=$?
    
    if [ $K6_EXIT_CODE -eq 0 ]; then
        echo "✅ K6 stress test completed successfully"
    else
        echo "❌ K6 stress test failed with exit code: $K6_EXIT_CODE"
    fi

else
    # Locust Stress Test
    echo "📊 Running Locust stress test..."
    echo "Command: locust -f $TEST_FILE --host=\"$BASE_URL\" --users $USERS --spawn-rate $SPAWN_RATE --run-time $RUNTIME --headless --html $REPORT_FILE"
    
    locust -f "$TEST_FILE" \
      --host="$BASE_URL" \
      --users "$USERS" \
      --spawn-rate "$SPAWN_RATE" \
      --run-time "$RUNTIME" \
      --headless \
      --html "$REPORT_FILE"

    if [ -f "$REPORT_FILE" ]; then
      PROJECT_NAME="🌿 Blockchain License System Stress Test Report"
      DATE_GENERATED="$(date +"%a, %b %d, %Y %I:%M:%S %p")"

      sed -i "s|Locust Test Report|$PROJECT_NAME|g" "$REPORT_FILE"

      sed -i "0,/<h3>.*<\/h3>/s|<h3>.*<\/h3>|<h3 style='text-align:center;color:#2E8B57;'>$PROJECT_NAME</h3><p style='text-align:center;font-style:italic;'>Generated on: $DATE_GENERATED</p>|" "$REPORT_FILE"

    fi
fi

echo "-------------------------------------"
echo "✅ $TEST_TYPE stress test completed!"
echo "📊 HTML report saved as: $REPORT_FILE"
echo "💡 Open it in your browser to view the performance graphs."

if [ "$TEST_TYPE" = "k6" ]; then
    exit $K6_EXIT_CODE
else
    exit $LOCUST_EXIT_CODE
fi