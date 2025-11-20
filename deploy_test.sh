#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose.test.yml"

echo "🧪 Starting isolated test environment"
echo ""

# Clean up any existing containers
echo "🧹 Cleaning up old containers..."
docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true

# Build test images
echo "🔨 Building test containers..."
docker compose -f "$COMPOSE_FILE" build --no-cache

# Run tests
echo "🚀 Running test suite..."
docker compose -f "$COMPOSE_FILE" run --rm test-runner

TEST_EXIT_CODE=$?

# Cleanup
echo "🧹 Cleaning up..."
docker compose -f "$COMPOSE_FILE" down -v

# Exit
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Tests passed successfully!"
else
    echo "❌ Tests failed with exit code: $TEST_EXIT_CODE"
fi

exit $TEST_EXIT_CODE