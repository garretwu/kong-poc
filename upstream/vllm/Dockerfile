# Use pre-compiled vllm from edge-vllm-demo venv via volume mount
FROM nvidia/cuda:12.8.0-runtime-ubuntu24.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install Python 3.12 (Ubuntu 24.04 ships with Python 3.12)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app.py .

# The venv site-packages and vllm source will be mounted at runtime:
#   - /venv -> /home/garywu/workspace/edge-vllm-demo/.venv
#   - /home/garywu/workspace/vllm -> vllm source (for editable install)
# Use container's Python with venv's site-packages via PYTHONPATH
# Include vllm source path for editable install
ENV PYTHONPATH=/venv/lib/python3.12/site-packages:/home/garywu/workspace/vllm

EXPOSE 8000

CMD ["python3.12", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
