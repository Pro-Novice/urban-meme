#!/bin/sh
set -eu

log() { printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }

# ---- Config (with sensible defaults) ----
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-}"
REDIS_PORT="${REDIS_PORT:-}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-60}"   # seconds
RUN_MIGRATIONS="${RUN_MIGRATIONS:-auto}"  # auto|always|never

# ---- Wait for Postgres ----
if command -v nc >/dev/null 2>&1; then
  log "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT} (timeout ${WAIT_TIMEOUT}s)..."
  i=0
  until nc -z -w1 "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    i=$((i+1))
    if [ "$i" -ge "$WAIT_TIMEOUT" ]; then
      log "ERROR: Postgres not reachable after ${WAIT_TIMEOUT}s"
      exit 1
    fi
    sleep 1
  done
  log "Postgres is up."
else
  log "WARNING: 'nc' not found; skipping Postgres wait."
fi

# ---- Optional: wait for Redis if host/port provided ----
if [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ] && command -v nc >/dev/null 2>&1; then
  log "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
  j=0
  until nc -z -w1 "$REDIS_HOST" "$REDIS_PORT"; do
    j=$((j+1))
    if [ "$j" -ge "$WAIT_TIMEOUT" ]; then
      log "ERROR: Redis not reachable after ${WAIT_TIMEOUT}s"
      exit 1
    fi
    sleep 1
  done
  log "Redis is up."
fi

# ---- Decide whether to run migrations/static ----
DO_MIGRATE=0
case "$RUN_MIGRATIONS" in
  always) DO_MIGRATE=1 ;;
  never)  DO_MIGRATE=0 ;;
  auto)   [ "${1:-}" = "gunicorn" ] && DO_MIGRATE=1 || DO_MIGRATE=0 ;;
  *)      DO_MIGRATE=0 ;;
esac

if [ "$DO_MIGRATE" -eq 1 ]; then
  log "Applying Django migrations..."
  python manage.py migrate --noinput
  log "Collecting static files..."
  # Ignore non-fatal issues (e.g., no STATIC_ROOT yet)
  python manage.py collectstatic --noinput || true
fi

if [ "${1:-}" = "gunicorn" ]; then
  log "Starting Gunicorn..."
fi

exec "$@"
