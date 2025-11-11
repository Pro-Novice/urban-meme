#!/usr/bin/env bash
# =============================================================================
#  run_tests.sh
#  -------------------------------------------------
#  Runs the seed_licenses pytest suite
#  Place this script anywhere (even inside apps/seed_licenses)
# =============================================================================

set -euo pipefail

# ---------- AUTO-DETECT PROJECT ROOT ----------
# Start from the script's location and go up until we find manage.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

while [[ "$PROJECT_ROOT" != "/" ]]; do
    if [[ -f "$PROJECT_ROOT/manage.py" ]]; then
        break
    fi
    PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done

if [[ ! -f "$PROJECT_ROOT/manage.py" ]]; then
    echo "Error: Could not find manage.py in any parent directory."
    echo "Make sure this script is inside your Django project (or a subdirectory)."
    exit 1
fi

echo "Django project root detected: $PROJECT_ROOT"

# ---------- CONFIGURATION ----------
TEST_FILE="apps/seed_licenses/tests/test_license_apis.py"
SETTINGS_MODULE="config.settings"  # CHANGE IF NEEDED

# Export settings
export DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE"

# ---------- HELP ----------
show_help() {
    cat <<EOF
Usage: ${0##*/} [options]

Options:
  -k <expr>      Run only tests matching expression
  -m <marker>    Run tests with marker (e.g. -m "django_db")
  --pdb          Drop into debugger on failure
  -x             Stop after first failure
  -v             Verbose output
  -h, --help     Show this help

Examples:
  ${0##*/}                    # Run all tests
  ${0##*/} -k public_key      # Run only public key test
  ${0##*/} -v -x              # Verbose, stop on first failure
EOF
}

# ---------- ARGUMENT PARSING ----------
PYTEST_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -k) PYTEST_ARGS+=("-k" "$2"); shift 2 ;;
        -m) PYTEST_ARGS+=("-m" "$2"); shift 2 ;;
        --pdb) PYTEST_ARGS+=("--pdb"); shift ;;
        -x) PYTEST_ARGS+=("-x"); shift ;;
        -v) PYTEST_ARGS+=("-v"); shift ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

# ---------- VALIDATE TEST FILE ----------
FULL_TEST_PATH="$PROJECT_ROOT/$TEST_FILE"
if [[ ! -f "$FULL_TEST_PATH" ]]; then
    echo "Error: Test file not found: $FULL_TEST_PATH"
    echo "Check if the file exists and the path is correct."
    exit 1
fi

# ---------- RUN MIGRATIONS ----------
echo "Applying migrations to test database..."
python "$PROJECT_ROOT/manage.py" migrate --noinput

# ---------- RUN PYTEST ----------
echo "Running tests: $TEST_FILE"
echo "Command: pytest ${PYTEST_ARGS[*]:-} \"$FULL_TEST_PATH\""
cd "$PROJECT_ROOT"
pytest "${PYTEST_ARGS[@]}" "$FULL_TEST_PATH"

echo "All tests completed!"