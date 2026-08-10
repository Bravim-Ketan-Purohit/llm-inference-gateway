"""Replay backend for cache hits — simulates streaming from cached responses."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from gateway.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    UsageInfo,
)


class ReplayBackend:
    """Replays a cached response, optionally simulating token-by-token streaming.

    Used to serve cache hits with realistic latency characteristics.
    """

    def __init__(self, replay_rate_tokens_per_sec: int = 200) -> None:
        self._replay_rate = replay_rate_tokens_per_sec

    @property
    def name(self) -> str:
        return "replay"

    @property
    def is_available(self) -> bool:
        return True

    async def replay_chat(
        self, cached_content: str, model: str, usage: UsageInfo | None = None
    ) -> ChatCompletionResponse:
        """Return a full response from cached content."""
        return ChatCompletionResponse(
            model=model,
            choices=[Choice(message=ChoiceMessage(content=cached_content))],
            usage=usage or UsageInfo(),
            system_fingerprint="cache-hit",
        )

    async def replay_stream(
        self, cached_content: str, model: str
    ) -> AsyncIterator[str]:
        """Stream cached content token-by-token with simulated latency."""
        words = cached_content.split(" ")
        delay = 1.0 / self._replay_rate if self._replay_rate > 0 else 0

        stream_id = f"chatcmpl-cache-{int(time.time())}"

        for i, word in enumerate(words):
            token = word if i == 0 else f" {word}"
            chunk = {
                "id": stream_id,
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            if delay > 0:
                await asyncio.sleep(delay)

        # Final chunk
        final = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final)}\n\n"
        yield "data: [DONE]\n\n"

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Not used directly — use replay_chat instead."""
        return ChatCompletionResponse(
            model=request.model, choices=[], usage=UsageInfo()
        )

    async def chat_stream(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """Not used directly — use replay_stream instead."""
        yield "data: [DONE]\n\n"

    async def health_check(self) -> bool:
        """Replay backend is always healthy."""
        return True
