"""Ollama backend adapter."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from gateway.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    UsageInfo,
)

logger = logging.getLogger(__name__)


class OllamaBackend:
    """Backend adapter for Ollama local inference."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)
        self._available = bool(base_url)

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def is_available(self) -> bool:
        return self._available

    def _convert_messages(self, request: ChatCompletionRequest) -> list[dict[str, Any]]:
        """Convert request messages to Ollama format."""
        return [{"role": m.role, "content": m.content or ""} for m in request.messages]

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Send a chat completion request to Ollama."""
        payload: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": self._convert_messages(request),
            "stream": False,
        }
        if request.temperature is not None:
            payload["options"] = {"temperature": request.temperature}

        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return ChatCompletionResponse(
            model=request.model or self._model,
            choices=[Choice(message=ChoiceMessage(content=content))],
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def chat_stream(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """Stream chat completions from Ollama."""
        payload: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": self._convert_messages(request),
            "stream": True,
        }
        if request.temperature is not None:
            payload["options"] = {"temperature": request.temperature}

        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    chunk = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "model": request.model or self._model,
                        "choices": [
                            {"index": 0, "delta": {"content": content}, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                if data.get("done"):
                    final_chunk = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "model": request.model or self._model,
                        "choices": [
                            {"index": 0, "delta": {}, "finish_reason": "stop"}
                        ],
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    yield "data: [DONE]\n\n"

    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except (httpx.HTTPError, Exception):
            return False
