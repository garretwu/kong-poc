from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import AsyncGenerator, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# vllm is imported from the pre-compiled venv at /home/garywu/workspace/edge-vllm-demo/.venv
# Run this service using: scripts/run-vllm.sh

from vllm import LLM, SamplingParams
from vllm.transformers_utils.tokenizer import get_tokenizer


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="Qwen/Qwen2.5-0.5B-Instruct")
    messages: List[ChatMessage]
    stream: bool = False
    temperature: float | None = 0.7
    max_tokens: int | None = 256
    top_p: float | None = 0.9


app = FastAPI(title="vLLM Server", version="0.1.0")

# Global llm instance
_llm: LLM | None = None
_tokenizer: None = None


def get_llm():
    global _llm, _tokenizer
    if _llm is None:
        _llm = LLM(
            model="Qwen/Qwen2.5-0.5B-Instruct",
            trust_remote_code=True,
            enforce_eager=True,
            gpu_memory_utilization=0.7,  # Use 70% of GPU memory
        )
        _tokenizer = get_tokenizer("Qwen/Qwen2.5-0.5B-Instruct")
    return _llm, _tokenizer


def _build_prompt(messages: List[ChatMessage]) -> str:
    """Build prompt from chat messages in Qwen format."""
    tokenizer = get_llm()[1]
    if tokenizer is None:
        tokenizer = get_tokenizer("Qwen/Qwen2.5-0.5B-Instruct")

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    return text


def _token_count(text: str) -> int:
    """Simple token count using word count as approximation."""
    return len(text.split())


def _build_completion_payload(
    request: ChatCompletionRequest,
    output_text: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict:
    created_ts = int(time.time())
    completion_id = f"chatcmpl-vllm-{uuid.uuid4().hex[:12]}"

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": output_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@app.on_event("startup")
async def startup_event():
    """Initialize vLLM model on startup."""
    print("Initializing vLLM model...")
    get_llm()
    print("vLLM model ready.")


async def _handle_chat_completion(request: ChatCompletionRequest):
    """Shared handler for chat completions."""
    llm, _ = get_llm()

    # Build prompt
    prompt = _build_prompt(request.messages)
    prompt_tokens = _token_count(prompt)

    # Setup sampling params
    sampling_params = SamplingParams(
        temperature=request.temperature or 0.7,
        max_tokens=request.max_tokens or 256,
        top_p=request.top_p or 0.9,
    )

    if request.stream:
        # Streaming response
        async def _stream_output() -> AsyncGenerator[str, None]:
            # Generate outputs
            outputs = llm.generate([prompt], sampling_params)

            for output in outputs:
                generated_text = output.outputs[0].text
                completion_tokens = _token_count(generated_text)

                chunk = {
                    "id": f"chatcmpl-vllm-{uuid.uuid4().hex[:12]}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": generated_text},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            # Send final chunk
            final_chunk = {
                "id": f"chatcmpl-vllm-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model,
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

        return StreamingResponse(_stream_output(), media_type="text/event-stream")

    # Non-streaming response
    outputs = llm.generate([prompt], sampling_params)
    output = outputs[0]
    output_text = output.outputs[0].text
    completion_tokens = _token_count(output_text)

    payload = _build_completion_payload(request, output_text, prompt_tokens, completion_tokens)
    return JSONResponse(payload)


@app.post("/v1/chat/completions")
@app.post("/v2/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    return await _handle_chat_completion(request)


@app.get("/healthz")
async def health_check():
    return {"status": "ok", "model": "Qwen/Qwen2.5-0.5B-Instruct"}
