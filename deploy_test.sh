#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose.test.yml"
REBUILD=false

# Use the same persistent dependency caches as the application image.
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
if [[ -z "${BUILDX_BUILDER:-}" ]] && docker buildx inspect desktop-linux >/dev/null 2>&1; then
    export BUILDX_BUILDER=desktop-linux
fi

# Optional flag: --rebuild (force full rebuild)
if [[ "${1:-}" == "--rebuild" ]]; then
  REBUILD=true
fi

echo "🧪 Starting isolated test environment"
echo ""

# Clean up old containers (but don't remove images)
echo "🧹 Cleaning up old containers..."
docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true

# Build only when required
if [ "$REBUILD" = true ]; then
    echo "🔨 Forced rebuild requested..."
    docker compose -f "$COMPOSE_FILE" build --no-cache
else
    echo "🔨 Building only changed parts (cached build)..."
    docker compose -f "$COMPOSE_FILE" build
fi

# Run tests
echo "🚀 Running test suite..."
docker compose -f "$COMPOSE_FILE" run --rm test-runner
TEST_EXIT_CODE=$?

# Cleanup
echo "🧹 Cleaning up..."
docker compose -f "$COMPOSE_FILE" down -v

# Exit reporting
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Tests passed successfully!"
else
    echo "❌ Tests failed with exit code: $TEST_EXIT_CODE"
fi

exit $TEST_EXIT_CODE
