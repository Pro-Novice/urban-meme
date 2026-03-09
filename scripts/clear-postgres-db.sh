#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/.env"
  set +a
fi

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-rajasthan-seed-postgres}"
POSTGRES_DB="${POSTGRES_DB:-agri_db}"
POSTGRES_USER="${POSTGRES_USER:-agriadmin}"

if ! docker ps --format '{{.Names}}' | rg -q "^${POSTGRES_CONTAINER}$"; then
  echo "Postgres container '${POSTGRES_CONTAINER}' not running."
  exit 1
fi

if [[ "${1:-}" != "-y" ]]; then
  echo "This will DELETE ALL DATA in database '${POSTGRES_DB}' inside container '${POSTGRES_CONTAINER}'."
  read -r -p "Continue? (y/N): " confirm
  if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

docker exec -i "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 <<SQL
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO ${POSTGRES_USER};
GRANT ALL ON SCHEMA public TO PUBLIC;
SQL

echo "Database cleared: ${POSTGRES_DB}"
