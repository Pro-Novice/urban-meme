#!/usr/bin/env bash
set -euo pipefail

echo "🧪 Starting Test Suite"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ----- Locate project root -----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ----- Environment Variables -----
export POSTGRES_HOST="${POSTGRES_HOST:-test-db}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_DB="${POSTGRES_DB:-test_db}"
export POSTGRES_USER="${POSTGRES_USER:-test_user}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-test_password}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.test_settings}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

echo "📦 Configuration:"
echo "   → Database: ${POSTGRES_USER}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo "   → Settings: ${DJANGO_SETTINGS_MODULE}"
echo ""

# ----- Wait for PostgreSQL -----
echo "⏳ Waiting for PostgreSQL..."
RETRIES=30
COUNT=0

while ! pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
    COUNT=$((COUNT + 1))
    if [ $COUNT -ge $RETRIES ]; then
        echo ""
        echo "❌ PostgreSQL not ready after ${RETRIES} attempts"
        echo "   → Checking network connectivity..."
        
        # Debug information
        echo "   → Testing DNS resolution..."
        getent hosts "$POSTGRES_HOST" || echo "   ⚠️ Cannot resolve $POSTGRES_HOST"
        
        echo "   → Testing port connectivity..."
        nc -zv "$POSTGRES_HOST" "$POSTGRES_PORT" 2>&1 || echo "   ⚠️ Cannot connect to port"
        
        exit 1
    fi
    printf "."
    sleep 2
done

echo ""
echo "✅ PostgreSQL is ready!"

# ----- Verify database connection with psql -----
echo "🔍 Verifying database connection..."
if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT version();" >/dev/null 2>&1; then
    echo "✅ Database connection verified"
else
    echo "❌ Cannot connect to database"
    exit 1
fi

# ----- Run migrations -----
# echo "⚙️ Running migrations..."
# python manage.py migrate --noinput --run-syncdb 2>&1 | grep -v "WARNING" || true
# echo "✅ Migrations completed"

# ----- Run pytest -----
echo ""
echo "🚀 Running Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run pytest with coverage
pytest -v \
    --disable-warnings \
    --tb=short \
    --no-header \
    --maxfail=5 \
    -x \
    apps/seed_licenses/tests/test_license_apis.py 

TEST_EXIT=$?

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $TEST_EXIT -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Tests failed (exit code: $TEST_EXIT)"
fi

exit $TEST_EXIT