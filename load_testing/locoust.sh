#!/usr/bin/env bash
set -euo pipefail

# ===== Config (env-overridable) =====
BASE_URL="${BASE_URL:-http://localhost:8000}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-50}"
DURATION="${DURATION:-1m}"

# Locustfile location (relative to this script)
LOCUSTFILE_REL="${LOCUSTFILE_REL:-locust_testing.py}"

# Make write-heavy steps optional, pass auth, Aadhaar checksum toggle
DO_HEAVY_MUTATIONS="${DO_HEAVY_MUTATIONS:-1}"   # 1=do POSTs, 0=read-only
AUTH_TOKEN="${AUTH_TOKEN:-}"                    # e.g. JWT
USE_VERHOEFF_AADHAAR="${USE_VERHOEFF_AADHAAR:-1}"

REPORT_DIR="${REPORT_DIR:-reports}"
REPORT_HTML="${REPORT_DIR}/locust_report.html"
REPORT_PDF="${REPORT_DIR}/locust_report.pdf"
CSV_PREFIX="${REPORT_DIR}/locust"

# Auto-install WeasyPrint if missing (0/1)
AUTO_INSTALL_WEASYPRINT="${AUTO_INSTALL_WEASYPRINT:-0}"

# ===== Helpers =====
fail() { echo "ERROR: $*" >&2; exit 1; }

# Resolve script directory and run from there (so locustfile path works)
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$SCRIPT_DIR"

# Resolve locustfile absolute path
LOCUSTFILE_PATH="${SCRIPT_DIR}/${LOCUSTFILE_REL}"
[ -f "$LOCUSTFILE_PATH" ] || fail "Locust file not found: $LOCUSTFILE_PATH"

# Ensure reports dir exists and clean previous outputs
mkdir -p "$REPORT_DIR"
rm -f "$REPORT_HTML" "$REPORT_PDF" "${CSV_PREFIX}"*

# Pick a locust binary (fallback to python -m locust)
if command -v locust >/dev/null 2>&1; then
  LOCUST_BIN="locust"
else
  # Use the python from PATH; adjust to a venv if needed
  LOCUST_BIN="python3 -m locust"
fi

echo "Running Locust:"
echo "  BASE_URL=${BASE_URL}"
echo "  USERS=${USERS}  SPAWN_RATE=${SPAWN_RATE}  DURATION=${DURATION}"
echo "  DO_HEAVY_MUTATIONS=${DO_HEAVY_MUTATIONS}  USE_VERHOEFF_AADHAAR=${USE_VERHOEFF_AADHAAR}"
[ -n "$AUTH_TOKEN" ] && echo "  AUTH_TOKEN set (hidden)"

# Export env so locustfile.py can read them
export BASE_URL AUTH_TOKEN DO_HEAVY_MUTATIONS USE_VERHOEFF_AADHAAR

# ===== Run Locust (headless) =====
# Note: We DO NOT pass -H, because HttpUser.host is read from BASE_URL in locustfile.py
$LOCUST_BIN \
  -f "$LOCUSTFILE_PATH" \
  --headless \
  -u "${USERS}" \
  -r "${SPAWN_RATE}" \
  -t "${DURATION}" \
  --html "${REPORT_HTML}" \
  --csv "${CSV_PREFIX}" \
  --csv-full-history

echo "Locust HTML report generated at: ${REPORT_HTML}"

# ===== macOS Chrome detection =====
chrome_bin() {
  if [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  elif [ -x "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary" ]; then
    echo "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
  elif command -v google-chrome >/dev/null 2>&1; then
    echo "google-chrome"
  elif command -v chromium >/dev/null 2>&1; then
    echo "chromium"
  elif [ -x "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" ]; then
    echo "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
  else
    echo ""
  fi
}

# ===== Convert HTML -> PDF (WeasyPrint -> Chrome -> wkhtmltopdf) =====
convert_html_to_pdf() {
  local html="$1"
  local pdf="$2"

  # 1) WeasyPrint (preferred; cross-platform)
  if python3 - <<'PY' >/dev/null 2>&1
import importlib; importlib.import_module("weasyprint")
PY
  then
    echo "Converting with WeasyPrint..."
    python3 -m weasyprint "${html}" "${pdf}" && return 0
  else
    if [ "$AUTO_INSTALL_WEASYPRINT" = "1" ]; then
      echo "WeasyPrint not found. Installing (pip)..."
      python3 -m pip install --quiet --upgrade pip
      python3 -m pip install --quiet weasyprint || true
      if python3 - <<'PY' >/dev/null 2>&1
import importlib; importlib.import_module("weasyprint")
PY
      then
        echo "Converting with WeasyPrint..."
        python3 -m weasyprint "${html}" "${pdf}" && return 0
      fi
      echo "WeasyPrint install failed or unavailable; trying Chrome..."
    fi
  fi

  # 2) Chrome/Chromium headless
  local CHROME_BIN
  CHROME_BIN="$(chrome_bin)"
  if [ -n "$CHROME_BIN" ]; then
    echo "Converting with Chrome headless (${CHROME_BIN})..."
    local abs_pdf abs_html
    abs_pdf="$(cd "$(dirname "$pdf")" && pwd)/$(basename "$pdf")"
    abs_html="$(cd "$(dirname "$html")" && pwd)/$(basename "$html")"
    "$CHROME_BIN" --headless --disable-gpu --no-sandbox \
      --print-to-pdf="${abs_pdf}" "file://${abs_html}" && return 0
  fi

  # 3) wkhtmltopdf (if present; note: discontinued on Homebrew)
  if command -v wkhtmltopdf >/dev/null 2>&1; then
    echo "Converting with wkhtmltopdf..."
    wkhtmltopdf --enable-local-file-access "${html}" "${pdf}" && return 0
  fi

  return 1
}

if convert_html_to_pdf "${REPORT_HTML}" "${REPORT_PDF}"; then
  echo "PDF report generated at: ${REPORT_PDF}"
else
  echo "WARN: Could not convert HTML to PDF."
  echo "Install one of these and re-run:"
  echo "  1) pip install weasyprint    (recommended)"
  echo "  2) Install Google Chrome     (headless print)"
  echo "  3) wkhtmltopdf               (if available)"
fi

echo "Done. HTML: ${REPORT_HTML}"

