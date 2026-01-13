#!/usr/bin/env bash

set -euo pipefail

URL="${URL:-http://localhost:8000/v1/chat/completions}"
API_KEY="${API_KEY:-demo-key}"

short_delay_ms="${SHORT_DELAY_MS:-1000}"
long_delay_ms="${LONG_DELAY_MS:-70000}"

payload_template='{
  "model": "mock-llm",
  "stream": %s,
  "ttft_ms": %d,
  "messages": [
    {"role": "user", "content": "timeout test"}
  ]
}'

run_request() {
  local label="$1"
  local stream="$2"
  local delay="$3"
  local payload
  payload=$(printf "$payload_template" "$stream" "$delay")

  echo
  echo "=== ${label}: stream=${stream}, ttft_ms=${delay} ==="
  curl -sS -w "\nHTTP_STATUS:%{http_code}\n" \
    -H "Content-Type: application/json" \
    -H "x-api-key: ${API_KEY}" \
    -X POST "${URL}" \
    -d "${payload}"
}

echo "Testing with short delay (${short_delay_ms} ms) to confirm no premature 504..."
run_request "Short delay" "false" "${short_delay_ms}"

echo
echo "Testing stream=true with short delay..."
run_request "Short delay stream" "true" "${short_delay_ms}"

echo
echo "Testing long delay (${long_delay_ms} ms) expecting Kong 504..."
run_request "Long delay" "false" "${long_delay_ms}"

echo
echo "Testing long delay stream expecting Kong 504..."
run_request "Long delay stream" "true" "${long_delay_ms}"

cat <<EOF

Interpretation:
- Short delay requests should return 200 with payload chunks.
- Long delay requests should hit Kong's upstream read-timeout and respond 504; if they hang indefinitely, increase logging and adjust timeout env vars.
Override SHORT_DELAY_MS/LONG_DELAY_MS as needed, then rerun.
EOF
