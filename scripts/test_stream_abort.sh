#!/usr/bin/env bash

set -euo pipefail

URL="${URL:-http://localhost:8000/v1/chat/completions}"
API_KEY="${API_KEY:-demo-key}"
DELAY="${DELAY:-2}"

payload='{
  "model": "mock-llm",
  "stream": true,
  "messages": [
    {"role": "user", "content": "streaming connection test"}
  ]
}'

echo "Starting streaming request to ${URL} (abort after ${DELAY}s)..."

curl -N -sS \
  -H 'Accept: text/event-stream' \
  -H 'Content-Type: application/json' \
  -H "x-api-key: ${API_KEY}" \
  -X POST "${URL}" \
  -d "${payload}" &

curl_pid=$!

sleep "${DELAY}"

echo "Killing curl process ${curl_pid}"
kill -INT "${curl_pid}" 2>/dev/null || true
wait "${curl_pid}" 2>/dev/null || true

cat <<'EOF'
Curl aborted.
Check mock-llm logs (e.g., `docker compose logs mock-llm --tail 20`) to confirm it logged "client disconnected" and stopped streaming.
EOF
