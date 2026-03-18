#!/bin/bash
set -euo pipefail

BASE_URL=${1:-http://localhost:8000}
PATH_TO_TEST=${2:-/}
URL="${BASE_URL}${PATH_TO_TEST}"

echo "Testing Nginx IP rate limit at: ${URL}"
echo "Sending 60 rapid requests..."

RESULTS=$(for i in {1..60}; do
  curl -s -o /dev/null -w "%{http_code}\n" "$URL" || true
done | sort | uniq -c)

echo "HTTP status counts:"
echo "$RESULTS"

if echo "$RESULTS" | grep -q "429"; then
  echo "OK: Saw 429 responses (rate limit triggered)."
else
  echo "WARN: No 429 responses. You may need a faster endpoint or higher request burst."
fi

echo ""
echo "Testing DRF throttling at: ${URL}"
echo "Sending 200 rapid requests..."

RESULTS=$(for i in {1..200}; do
  curl -s -o /dev/null -w "%{http_code}\n" "$URL" || true
done | sort | uniq -c)

echo "HTTP status counts:"
echo "$RESULTS"

if echo "$RESULTS" | grep -q "429"; then
  echo "OK: Saw 429 responses (DRF throttle triggered)."
else
  echo "WARN: No 429 responses. Check DRF_THROTTLE_* values and endpoint selection."
fi
