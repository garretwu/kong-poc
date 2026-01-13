#!/bin/bash
# Run vLLM backend using the pre-compiled venv from edge-vllm-demo

VENV_PATH="/home/garywu/workspace/edge-vllm-demo/.venv"
APP_PATH="/home/garywu/workspace/kong-poc/upstream/vllm"

# Activate the venv
source "${VENV_PATH}/bin/activate"

# Change to app directory
cd "${APP_PATH}"

# Run the server
echo "Starting vLLM server using venv at ${VENV_PATH}..."
exec uvicorn app:app --host 0.0.0.0 --port 8083
