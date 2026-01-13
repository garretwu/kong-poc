from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="mock-llm")
    messages: List[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    ttft_ms: int | None = Field(
        default=None,
        ge=0,
        description="Optional delay before first token / response in milliseconds.",
    )


app = FastAPI(title="Mock LLM", version="0.1.0")


def _mock_completion_text(messages: List[ChatMessage]) -> str:
    """Return a deterministic helper response so debugging stays easy."""
    last_user_message = next(
        (message.content for message in reversed(messages) if message.role == "user"),
        None,
    )

    if last_user_message:
        return f"Echo: {last_user_message}"

    return "Hello from mock LLM."


def _token_count(text: str) -> int:
    # Naive tokenizer good enough for a mock.
    return len(text.split())


def _build_completion_payload(request: ChatCompletionRequest) -> dict:
    created_ts = int(time.time())
    completion_id = f"chatcmpl-mock-{uuid.uuid4().hex[:12]}"
    completion_content = _mock_completion_text(request.messages)

    prompt_tokens = sum(_token_count(msg.content) for msg in request.messages)
    completion_tokens = _token_count(completion_content)

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": completion_content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


async def _stream_payload(
    request: ChatCompletionRequest,
    initial_delay: float = 0,
) -> AsyncGenerator[str, None]:
    if initial_delay > 0:
        await asyncio.sleep(initial_delay)

    payload = _build_completion_payload(request)
    payload_id = payload["id"]
    created_ts = payload["created"]
    model = payload["model"]
    full_content = payload["choices"][0]["message"]["content"]

    for character in full_content:
        chunk = {
            "id": payload_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": character},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0)

    final_chunk = {
        "id": payload_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    if request.ttft_ms:
        await asyncio.sleep(request.ttft_ms / 1000)

    if request.stream:
        generator = _stream_payload(
            request, initial_delay=0
        )  # delay already applied above
        return StreamingResponse(generator, media_type="text/event-stream")

    payload = _build_completion_payload(request)
    return JSONResponse(payload)


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}
