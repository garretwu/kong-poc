"""Test script for vLLM server."""
import json
import os
import sys
import time

import pytest
import requests

BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8100")

if os.getenv("VLLM_E2E") != "1":
    pytest.skip("vLLM E2E tests disabled. Set VLLM_E2E=1 to enable.", allow_module_level=True)


def wait_for_server(url: str, timeout: int = 60) -> bool:
    """Wait for server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{url}/healthz", timeout=5)
            if resp.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    return False


def test_health():
    """Test health endpoint."""
    resp = requests.get(f"{BASE_URL}/healthz", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    print("Health check passed!")


def test_non_streaming():
    """Test non-streaming chat completion."""
    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": "Qwen/Qwen2.5-0.5B-Instruct",
            "messages": [
                {"role": "user", "content": "Say hello!"}
            ],
            "stream": False,
        },
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] != ""
    print(f"Non-streaming test passed! Response: {data['choices'][0]['message']['content']}")


def test_streaming():
    """Test streaming chat completion."""
    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": "Qwen/Qwen2.5-0.5B-Instruct",
            "messages": [
                {"role": "user", "content": "Count to 5:"}
            ],
            "stream": True,
        },
        stream=True,
        timeout=30,
    )
    assert resp.status_code == 200

    chunks = []
    for line in resp.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data = line[6:]
                if data != "[DONE]":
                    chunks.append(json.loads(data))

    assert len(chunks) > 0
    # Last chunk should have finish_reason
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    print(f"Streaming test passed! Received {len(chunks)} chunks.")


if __name__ == "__main__":
    # Wait for server
    print(f"Waiting for server at {BASE_URL}...")
    if not wait_for_server(BASE_URL):
        print("Server not ready!")
        sys.exit(1)

    print("Server ready! Running tests...")

    # Run tests
    test_health()
    test_non_streaming()
    test_streaming()

    print("\nAll tests passed!")
