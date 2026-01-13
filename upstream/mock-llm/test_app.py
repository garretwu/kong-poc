import pytest
from fastapi.testclient import TestClient
from app import app, ChatCompletionRequest, ChatMessage


client = TestClient(app)


class TestHealthCheck:
    """Health check endpoint tests."""

    def test_healthz_returns_ok(self):
        """Test that health endpoint returns 200 with ok status."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestChatCompletion:
    """Chat completion endpoint tests."""

    def test_non_streaming_completion(self):
        """Test basic non-streaming chat completion."""
        request = {
            "model": "mock-llm",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        }
        response = client.post("/v1/chat/completions", json=request)
        assert response.status_code == 200

        data = response.json()
        assert data["object"] == "chat.completion"
        assert "id" in data
        assert "choices" in data
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["finish_reason"] == "stop"

    def test_streaming_completion(self):
        """Test streaming chat completion returns SSE format."""
        request = {
            "model": "mock-llm",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=request)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Consume the stream and verify SSE format
        content = b"".join(response.iter_bytes()).decode("utf-8")
        lines = content.split("\n")
        data_lines = [line for line in lines if line.startswith("data:")]

        assert len(data_lines) >= 2  # At least [DONE] and one data chunk

        # Verify last chunk is [DONE]
        assert "[DONE]" in data_lines[-1]

    def test_echo_user_message(self):
        """Test that response echoes user message."""
        request = {
            "model": "mock-llm",
            "messages": [{"role": "user", "content": "test message"}],
            "stream": False,
        }
        response = client.post("/v1/chat/completions", json=request)
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        assert content == "Echo: test message"

    def test_empty_messages_returns_default(self):
        """Test with empty messages returns default response."""
        request = {
            "model": "mock-llm",
            "messages": [],
            "stream": False,
        }
        response = client.post("/v1/chat/completions", json=request)
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        assert content == "Hello from mock LLM."

    def test_token_count_calculation(self):
        """Test that token count is calculated correctly."""
        request = {
            "model": "mock-llm",
            "messages": [{"role": "user", "content": "one two three"}],
            "stream": False,
        }
        response = client.post("/v1/chat/completions", json=request)
        data = response.json()

        prompt_tokens = data["usage"]["prompt_tokens"]
        completion_tokens = data["usage"]["completion_tokens"]

        # User message has 3 words = 3 tokens
        assert prompt_tokens == 3
        # Response has 3 words + "Echo:" = 4 tokens
        assert completion_tokens == 4


class TestRequestValidation:
    """Request validation tests."""

    def test_default_model(self):
        """Test that default model is used when not specified."""
        request = {
            "messages": [{"role": "user", "content": "Hello"}],
        }
        response = client.post("/v1/chat/completions", json=request)
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "mock-llm"

    def test_default_non_streaming(self):
        """Test that default is non-streaming when not specified."""
        request = {
            "messages": [{"role": "user", "content": "Hello"}],
        }
        response = client.post("/v1/chat/completions", json=request)
        assert response.status_code == 200
        # Should be JSON, not SSE
        assert "text/event-stream" not in response.headers.get("content-type", "")

    def test_multiple_messages(self):
        """Test with multiple messages in conversation."""
        request = {
            "model": "mock-llm",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"},
            ],
            "stream": False,
        }
        response = client.post("/v1/chat/completions", json=request)
        assert response.status_code == 200
        data = response.json()
        # Should count tokens from all messages
        assert data["usage"]["prompt_tokens"] > 0


class TestTTFTDelay:
    """Time to first token delay tests."""

    def test_ttft_ms_delay(self):
        """Test that ttft_ms parameter adds delay."""
        import time

        request = {
            "model": "mock-llm",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
            "ttft_ms": 500,
        }

        start = time.time()
        response = client.post("/v1/chat/completions", json=request)
        elapsed = time.time() - start

        assert response.status_code == 200
        # Should take at least 0.5s (with some tolerance)
        assert elapsed >= 0.4


class TestStreamingChunks:
    """Streaming chunk format tests."""

    def test_streaming_chunks_format(self):
        """Test that streaming chunks have correct OpenAI format."""
        request = {
            "model": "mock-llm",
            "messages": [{"role": "user", "content": "AB"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=request)
        content = b"".join(response.iter_bytes()).decode("utf-8")

        import json as json_module

        for line in content.split("\n"):
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    continue
                chunk = json_module.loads(data_str)

                assert chunk["object"] == "chat.completion.chunk"
                assert "choices" in chunk
                assert len(chunk["choices"]) == 1
                assert "delta" in chunk["choices"][0]
                assert "finish_reason" in chunk["choices"][0]

                # Either has content or is final chunk
                has_content = chunk["choices"][0]["delta"].get("content")
                is_final = chunk["choices"][0]["finish_reason"] == "stop"

                assert has_content or is_final
