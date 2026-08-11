"""vLLM backend adapter (OpenAI-compatible API)."""

from __future__ import annotations

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


class VLLMBackend:
    """Backend adapter for vLLM serving (OpenAI-compatible endpoint)."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._model = model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        if self._base_url:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    @property
    def name(self) -> str:
        return "vllm"

    @property
    def is_available(self) -> bool:
        return bool(self._base_url) and self._client is not None

    def _build_payload(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """Build OpenAI-compatible payload for vLLM."""
        messages = [{"role": m.role, "content": m.content or ""} for m in request.messages]
        payload: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": messages,
            "stream": request.stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stop is not None:
            payload["stop"] = request.stop
        return payload

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Send a chat completion request to vLLM."""
        assert self._client is not None
        payload = self._build_payload(request)
        payload["stream"] = False

        response = await self._client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choices = []
        for c in data.get("choices", []):
            msg = c.get("message", {})
            choices.append(
                Choice(
                    index=c.get("index", 0),
                    message=ChoiceMessage(
                        role=msg.get("role", "assistant"),
                        content=msg.get("content", ""),
                    ),
                    finish_reason=c.get("finish_reason", "stop"),
                )
            )

        usage_data = data.get("usage", {})
        return ChatCompletionResponse(
            model=data.get("model", request.model or self._model),
            choices=choices,
            usage=UsageInfo(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
        )

    async def chat_stream(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """Stream chat completions from vLLM."""
        assert self._client is not None
        payload = self._build_payload(request)
        payload["stream"] = True

        async with self._client.stream(
            "POST", "/v1/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield f"{line}\n\n"
                    if line.strip() == "data: [DONE]":
                        break

    async def health_check(self) -> bool:
        """Check if vLLM is reachable."""
        if not self._client:
            return False
        try:
            response = await self._client.get("/v1/models")
            return response.status_code == 200
        except (httpx.HTTPError, Exception):
            return False
